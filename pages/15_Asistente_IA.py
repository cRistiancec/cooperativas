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

import streamlit as st

from analytics.financial_engine import calcular_score_camel, evaluar_alertas
from services.asistente_ia import (
    MODELO_CLAUDE_DEFECTO,
    claude_disponible,
    construir_contexto_sistema,
    responder_con_claude,
    responder_local,
)
from ui import aplicar_tema, render_sidebar
from utils.data_loader import cargar_indicadores, cargar_metadata

st.set_page_config(
    page_title="Asistente Inteligente | Radar Cooperativo Ecuador",
    page_icon="🧠",
    layout="wide",
)
aplicar_tema()


@st.cache_data(ttl=1800)
def _resumen_alertas_y_score():
    df_ind, _ = cargar_indicadores()
    fecha_max = df_ind["fecha"].max()
    alertas = evaluar_alertas(df_ind, fecha_max)
    score = calcular_score_camel(df_ind, fecha_max)

    resumen_alertas = alertas["semaforo"].value_counts().to_dict() if not alertas.empty else {}
    resumen_score = {"promedio": round(float(score["score_total"].mean()), 1)} if not score.empty else {}
    return alertas, score, resumen_alertas, resumen_score


def main():
    metadata = cargar_metadata()
    render_sidebar(metadata)

    st.title("🧠 Asistente Inteligente")
    st.markdown("Chat institucional anclado a los datos reales de la plataforma.")

    alertas_df, score_df, resumen_alertas, resumen_score = _resumen_alertas_y_score()

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
