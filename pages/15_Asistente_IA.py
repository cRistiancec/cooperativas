# -*- coding: utf-8 -*-
"""
Módulo 15: Asistente Inteligente
Chat institucional con dos modos: respuestas locales determinísticas
(siempre disponibles, ancladas a datos reales) y, si se configura una
clave de API, respuestas con Claude (Anthropic) con contexto real inyectado.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import streamlit as st

from analytics.financial_engine import calcular_score_camel, evaluar_alertas
from services.asistente_ia import (
    MODELO_CLAUDE_DEFECTO,
    claude_disponible,
    construir_contexto_sistema,
    responder_con_claude,
    responder_local,
)
from ui import (
    aplicar_tema, exigir_datos, render_filtros_globales, render_resumen_filtro, render_sidebar, selector_fecha_corte,
)
from utils.data_loader import acotar_entidades, cargar_metadata, datos_filtrados, datos_universo

st.set_page_config(
    page_title="Asistente Inteligente | Radar Cooperativo Ecuador",
    page_icon="🧠",
    layout="wide",
)
aplicar_tema()


def _resumen_alertas_y_score(filtro, fecha):
    """Alertas (umbrales por entidad) y score CAMEL (relativo al universo) de la selección global en la fecha de análisis."""
    df_ind = datos_filtrados("indicadores", filtro)
    alertas = evaluar_alertas(df_ind, fecha)
    score = calcular_score_camel(datos_universo("indicadores", filtro), fecha)
    if not score.empty and filtro.entidades:
        meta = datos_universo("indicadores", filtro)
        meta = meta[meta["fecha"] == fecha][["cooperativa", "entidad"]].drop_duplicates("cooperativa")
        score = acotar_entidades(score.merge(meta, on="cooperativa", how="left"), filtro)

    resumen_alertas = alertas["semaforo"].value_counts().to_dict() if not alertas.empty else {}
    resumen_score = {"promedio": round(float(score["score_total"].mean()), 1)} if not score.empty else {}
    return alertas, score, resumen_alertas, resumen_score


def main():
    metadata = cargar_metadata()
    render_sidebar(metadata)

    st.title("🧠 Asistente Inteligente")
    st.markdown("Chat institucional anclado a los datos reales de la plataforma.")

    filtro = render_filtros_globales()
    fecha_sel = selector_fecha_corte(filtro)
    df_ind = datos_filtrados("indicadores", filtro)
    render_resumen_filtro(filtro, df_ind[df_ind["fecha"] == fecha_sel] if not df_ind.empty else df_ind,
                          corte=pd.Timestamp(metadata["fecha_max"]), fecha_analisis=fecha_sel)
    exigir_datos(df_ind)
    alertas_df, score_df, resumen_alertas, resumen_score = _resumen_alertas_y_score(filtro, fecha_sel)
    # El asistente responde sobre la MISMA población que el resto de la aplicación
    metadata = {**metadata, "cooperativas": int(df_ind.loc[df_ind["fecha"] == fecha_sel, "entidad"].nunique()),
                "fecha_min": str(pd.Timestamp(filtro.fecha_ini).date()), "fecha_max": str(pd.Timestamp(fecha_sel).date()),
                "seleccion_activa": filtro.descripcion(), "meses": int(df_ind["fecha"].nunique())}

    with st.sidebar:
        st.markdown("---")
        st.markdown("### Configuración del Asistente")
        if claude_disponible():
            st.success("Claude (Anthropic) configurado")
        else:
            with st.expander("Configurar clave de Claude"):
                clave_manual = st.text_input("Clave de API de Anthropic", type="password", key="input_clave_claude")
                if st.button("Guardar para esta sesión", key="btn_guardar_clave"):
                    st.session_state["sps_anthropic_key_manual"] = clave_manual
                    st.rerun()
                st.caption(
                    "La clave solo se guarda en memoria de esta sesión de navegador; no se persiste "
                    "en disco. En producción, configúrala en `st.secrets['ANTHROPIC_API_KEY']`."
                )

    modo_ia = claude_disponible()
    if modo_ia:
        st.info(f"🟢 Modo conversacional con **Claude** (`{MODELO_CLAUDE_DEFECTO}`) activo.")
    else:
        st.warning(
            "🟡 Modo local determinístico activo (sin clave de Claude configurada). "
            "Responde preguntas frecuentes con datos reales del sistema; para preguntas "
            "abiertas, configura una clave en el sidebar."
        )

    if "sps_chat_historial" not in st.session_state:
        st.session_state["sps_chat_historial"] = []

    for mensaje in st.session_state["sps_chat_historial"]:
        with st.chat_message(mensaje["role"]):
            st.markdown(mensaje["content"])

    pregunta = st.chat_input("Pregunta al asistente sobre el sistema...")

    if pregunta:
        st.session_state["sps_chat_historial"].append({"role": "user", "content": pregunta})
        with st.chat_message("user"):
            st.markdown(pregunta)

        with st.chat_message("assistant"):
            if modo_ia:
                try:
                    contexto = construir_contexto_sistema(metadata, resumen_alertas, resumen_score)
                    respuesta = responder_con_claude(pregunta, st.session_state["sps_chat_historial"], contexto)
                except Exception as e:
                    respuesta = (
                        f"No pude conectar con Claude en este momento ({e}). "
                        f"Respuesta local: {responder_local(pregunta, metadata, alertas_df, score_df)}"
                    )
            else:
                respuesta = responder_local(pregunta, metadata, alertas_df, score_df)

            st.markdown(respuesta)

        st.session_state["sps_chat_historial"].append({"role": "assistant", "content": respuesta})

    if st.session_state["sps_chat_historial"]:
        if st.button("🗑️ Limpiar conversación"):
            st.session_state["sps_chat_historial"] = []
            st.rerun()

    st.markdown("---")
    with st.expander("ℹ️ Cómo funciona este asistente"):
        st.markdown(
            """
            - **Modo local** (siempre activo): responde preguntas frecuentes consultando directamente
              los datos reales ya calculados en la plataforma (número de instituciones, período de
              datos, alertas críticas, score CAMEL promedio). No usa ningún modelo de lenguaje ni
              requiere clave — nunca inventa cifras.
            - **Modo Claude** (opcional, requiere clave de Anthropic): habilita preguntas abiertas en
              lenguaje natural. El prompt de sistema incluye un resumen de los datos reales más
              recientes para anclar las respuestas, pero Claude puede complementar con razonamiento
              general — para cifras exactas, siempre verifica en el módulo correspondiente.
            - Preparado para extender a otros proveedores (OpenAI, Gemini, LLM local) sin cambiar la
              interfaz de esta página (ver `services/asistente_ia.py`).
            """
        )


if __name__ == "__main__":
    main()
