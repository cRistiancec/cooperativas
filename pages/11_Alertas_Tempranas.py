# -*- coding: utf-8 -*-
"""
Módulo 11: Alertas Tempranas
Motor de reglas sobre indicadores oficiales (morosidad, rentabilidad,
liquidez, capitalización, vulnerabilidad patrimonial) y crecimiento
interanual de depósitos, con semáforo agregado y ranking de deterioro.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from analytics.financial_engine import (
    REGLAS_INTERACCION, UMBRAL_GENERALIZADO_PCT, UMBRAL_PERSISTENTE_MESES,
    calcular_breadth, calcular_persistencia_alertas, evaluar_alertas, evaluar_interacciones,
    ventana_fechas,
)
from config.umbrales_alerta import REGLAS_ALERTA
from ui import aplicar_tema, render_filtro_segmento, render_sidebar
from utils.charts import COLORES, altura_por_categorias, crear_radar, truncar_nombres_unicos
from utils.data_loader import (
    cargar_indicadores, cargar_metadata, cargar_ranking_cooperativas,
    obtener_crecimiento_anual, obtener_fechas_disponibles_rapido,
)

st.set_page_config(
    page_title="Alertas Tempranas | Radar Cooperativo Ecuador",
    page_icon="🚨",
    layout="wide",
)
aplicar_tema()

_SEMAFORO_CLASE = {"ok": "sps-light--ok", "warn": "sps-light--warn", "crit": "sps-light--crit"}
_SEMAFORO_LABEL = {"ok": "Sin alertas relevantes", "warn": "Vigilancia", "crit": "Crítico"}


def main():
    metadata = cargar_metadata()
    render_sidebar(metadata)

    st.title("🚨 Alertas Tempranas")
    st.markdown(
        "Sistema de priorización basado en reglas sobre indicadores oficiales. "
        "**No sustituye el juicio experto de un analista de riesgos** — enfoca la revisión manual "
        "en las instituciones con mayor número de señales de deterioro."
    )

    df_ind, calidad = cargar_indicadores()

    st.sidebar.markdown("### Filtros")
    # Filtro Global de Segmento (ui/filtros.py) — compartido con toda la plataforma
    segmento_sel = render_filtro_segmento()

    fechas = sorted(df_ind["fecha"].unique(), reverse=True)
    fecha_sel = st.sidebar.selectbox(
        "Fecha de análisis", fechas, format_func=lambda x: pd.Timestamp(x).strftime("%B %Y").title(),
        index=0, key="fecha_alertas",
    )

    fechas_rapido = obtener_fechas_disponibles_rapido()
    crecim = None
    if fecha_sel in fechas_rapido:
        idx = list(fechas_rapido).index(fecha_sel)
        if idx + 12 < len(fechas_rapido):
            fecha_anterior = fechas_rapido[idx + 12]
            crecim = obtener_crecimiento_anual(fecha_sel, fecha_anterior, codigo="21", segmento=segmento_sel, top_n=0)

    alertas = evaluar_alertas(df_ind, fecha_sel, segmento_sel, crecim)
    if alertas.empty:
        st.warning("Sin datos suficientes para esta selección.")
        return

    conteo = alertas["semaforo"].value_counts()
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Instituciones evaluadas", f"{len(alertas)}")
    with col2:
        st.metric("🟢 Sin alertas relevantes", int(conteo.get("ok", 0)))
    with col3:
        st.metric("🟡 En vigilancia", int(conteo.get("warn", 0)))
    with col4:
        st.metric("🔴 Críticas", int(conteo.get("crit", 0)))

    st.markdown("---")

    tab1, tab2, tab3, tab4 = st.tabs([
        "🏆 Ranking de Deterioro", "🕸️ Radar de Riesgo por Cooperativa", "🗺️ Heatmap de Alertas",
        "⏱️ Persistencia, Amplitud e Interacción",
    ])

    # ------------------------------------------------------------ TAB 1
    with tab1:
        top_n = st.selectbox("Instituciones a mostrar", [20, 40, 0], index=0,
                              format_func=lambda x: "Todas" if x == 0 else f"Top {x}", key="topn_alertas")
        df_r = alertas.head(top_n if top_n else len(alertas))

        for _, fila in df_r.iterrows():
            clase = _SEMAFORO_CLASE[fila["semaforo"]]
            label = _SEMAFORO_LABEL[fila["semaforo"]]
            st.markdown(
                f"""
                <div style="display:flex; justify-content:space-between; align-items:center;
                            padding:8px 4px; border-bottom:1px solid var(--sps-border);">
                    <div>
                        <strong>{fila['cooperativa']}</strong>
                        <span style="color:var(--sps-text-dim); font-size:0.8rem;"> · {fila['segmento']}</span>
                    </div>
                    <div style="display:flex; align-items:center; gap:10px;">
                        <span style="font-size:0.78rem; color:var(--sps-text-dim);">
                            {int(fila['alertas_rojas'])} rojas · {int(fila['alertas_amarillas'])} amarillas
                        </span>
                        <span class="sps-light {clase}"><span class="sps-light__dot"></span>{label}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ------------------------------------------------------------ TAB 2
    with tab2:
        coop_sel = st.selectbox("Cooperativa", alertas["cooperativa"].tolist(), key="coop_radar_alertas")
        fila = alertas[alertas["cooperativa"] == coop_sel].iloc[0]

        codigos = list(REGLAS_ALERTA.keys())
        df_fecha_ind = df_ind[df_ind["fecha"] == fecha_sel]
        if segmento_sel != "Todos":
            df_fecha_ind = df_fecha_ind[df_fecha_ind["segmento"] == segmento_sel]

        valores_coop = []
        for codigo in codigos:
            serie_ind = df_fecha_ind[df_fecha_ind["codigo"] == codigo]
            fila_coop = serie_ind[serie_ind["cooperativa"] == coop_sel]
            if serie_ind.empty or fila_coop.empty:
                valores_coop.append(50.0)
                continue
            percentil = serie_ind["valor"].rank(pct=True) * 100
            idx = fila_coop.index[0]
            pct = percentil.loc[idx] if idx in percentil.index else 50.0
            direccion = REGLAS_ALERTA[codigo]["direccion"]
            pct = pct if direccion == "mayor_es_peor" else (100 - pct)
            valores_coop.append(round(float(pct), 1))

        clase_sem = _SEMAFORO_CLASE[fila["semaforo"]]
        st.markdown(
            f'<span class="sps-light {clase_sem}"><span class="sps-light__dot"></span>'
            f'{coop_sel} — {_SEMAFORO_LABEL[fila["semaforo"]]} '
            f'({int(fila["alertas_rojas"])} alertas rojas, {int(fila["alertas_amarillas"])} amarillas)</span>',
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)

        etiquetas_cortas = [REGLAS_ALERTA[c]["etiqueta"] for c in codigos]
        fig = crear_radar(etiquetas_cortas, {coop_sel: valores_coop},
                           titulo="Percentil de riesgo por regla (100 = peor percentil relativo)")
        st.plotly_chart(fig, width="stretch")

    # ------------------------------------------------------------ TAB 3
    with tab3:
        top_n_heat = st.selectbox("Instituciones a mostrar", [20, 40, 0], index=0,
                                   format_func=lambda x: "Todas" if x == 0 else f"Top {x}", key="topn_heat_alertas")
        columnas_sev = [f"sev_{c}" for c in REGLAS_ALERTA if f"sev_{c}" in alertas.columns]
        df_heat = alertas.head(top_n_heat if top_n_heat else len(alertas)).set_index("cooperativa")[columnas_sev]
        df_heat.columns = [REGLAS_ALERTA[c]["etiqueta"] for c in REGLAS_ALERTA if f"sev_{c}" in columnas_sev]

        fig = go.Figure(go.Heatmap(
            z=df_heat.values, x=df_heat.columns, y=truncar_nombres_unicos([str(n) for n in df_heat.index]),
            colorscale="RdYlGn_r", zmin=0, zmax=2,
            hovertemplate="Cooperativa: %{y}<br>Regla: %{x}<br>Severidad: %{z}<extra></extra>",
            colorbar=dict(title="Severidad", tickvals=[0, 1, 2], ticktext=["OK", "Amarilla", "Roja"]),
        ))
        fig.update_layout(height=altura_por_categorias(len(df_heat), px_por_categoria=20),
                           paper_bgcolor="rgba(0,0,0,0)",
                           font_color=COLORES["texto"], margin=dict(l=10, r=10, t=20, b=100),
                           xaxis=dict(tickangle=-30, automargin=True),
                           yaxis=dict(tickfont=dict(size=10), automargin=True))
        st.plotly_chart(fig, width="stretch")

    # ------------------------------------------------------------ TAB 4
    with tab4:
        st.caption(
            "Evalúa la ventana de los últimos meses disponibles (hasta la fecha seleccionada) para "
            "distinguir alertas nuevas, persistentes y recurrentes — una sola foto mensual no muestra "
            "si un deterioro es puntual o sostenido."
        )
        meses_ventana = st.selectbox("Ventana de análisis (meses)", [3, 6, 12], index=1, key="ventana_persistencia")

        fechas_todas = sorted(df_ind["fecha"].unique())
        ventana = ventana_fechas(fechas_todas, fecha_sel, meses_ventana)

        if len(ventana) < 2:
            st.warning("No hay suficientes meses previos en los datos para evaluar persistencia en esta ventana.")
        else:
            df_persist = calcular_persistencia_alertas(df_ind, ventana, segmento_sel,
                                                         umbral_persistente_meses=UMBRAL_PERSISTENTE_MESES)
            df_activas = df_persist[df_persist["meses_consecutivos_activa"] > 0]

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Con alerta activa hoy", int((df_persist["meses_consecutivos_activa"] > 0).sum()))
            with c2:
                st.metric("Nuevas (1er mes)", int(df_persist["alerta_nueva"].sum()))
            with c3:
                st.metric(f"Persistentes (≥{UMBRAL_PERSISTENTE_MESES}m)", int(df_persist["alerta_persistente"].sum()))
            with c4:
                st.metric("Recurrentes (reaparecen)", int(df_persist["alerta_recurrente"].sum()))

            st.dataframe(
                df_activas[["cooperativa", "segmento", "meses_consecutivos_activa", "alerta_nueva",
                            "alerta_persistente", "alerta_recurrente", "alertas_rojas_hoy", "alertas_amarillas_hoy"]]
                .rename(columns={
                    "meses_consecutivos_activa": "Meses consecutivos activa",
                    "alerta_nueva": "Nueva", "alerta_persistente": "Persistente",
                    "alerta_recurrente": "Recurrente", "alertas_rojas_hoy": "Rojas hoy",
                    "alertas_amarillas_hoy": "Amarillas hoy",
                }),
                width="stretch", hide_index=True,
            )

            st.markdown("#### Amplitud (breadth) de las entidades con alerta roja hoy")
            df_ranking = cargar_ranking_cooperativas()
            afectadas_rojas = alertas.loc[alertas["alertas_rojas"] > 0, "cooperativa"].tolist()
            if df_ranking.empty or not afectadas_rojas:
                st.info("Sin entidades con alerta roja en esta fecha/segmento, o sin datos de ranking disponibles.")
            else:
                breadth = calcular_breadth(afectadas_rojas, df_ranking, fecha_sel, segmento_sel)
                b1, b2, b3, b4 = st.columns(4)
                with b1:
                    st.metric("% entidades afectadas", f"{breadth['pct_entidades']:.1f}%")
                with b2:
                    st.metric("% activos del sistema", f"{breadth['dimensiones'].get('activos') or 0:.1f}%")
                with b3:
                    st.metric("% cartera del sistema", f"{breadth['dimensiones'].get('cartera') or 0:.1f}%")
                with b4:
                    st.metric("% depósitos del sistema", f"{breadth['dimensiones'].get('depositos') or 0:.1f}%")
                clase_breadth = "sps-light--crit" if breadth["clasificacion"] == "RIESGO GENERALIZADO" else "sps-light--warn"
                st.markdown(
                    f'<span class="sps-light {clase_breadth}"><span class="sps-light__dot"></span>'
                    f'{breadth["clasificacion"]}</span>',
                    unsafe_allow_html=True,
                )
                st.caption(
                    f"Umbral analítico (no regulatorio) para 'generalizado': ≥{UMBRAL_GENERALIZADO_PCT:.0f}% "
                    "de activos del sistema en entidades con alerta roja. Universo comparado: "
                    f"{'sistema completo' if segmento_sel == 'Todos' else segmento_sel}."
                )

            st.markdown("#### Reglas de interacción entre indicadores")
            df_inter = evaluar_interacciones(alertas)
            cols_inter = [c for c in REGLAS_INTERACCION if c in df_inter.columns]
            if not cols_inter:
                st.info(
                    "Ninguna regla de interacción pudo evaluarse en esta corrida (faltan columnas de "
                    "severidad requeridas, p. ej. crecimiento de depósitos no disponible en esta fecha)."
                )
            else:
                for nombre in cols_inter:
                    n_activas = int(df_inter[nombre].sum())
                    with st.expander(f"{nombre} — {n_activas} cooperativa(s) activa(s)"):
                        st.caption(REGLAS_INTERACCION[nombre]["descripcion"])
                        if n_activas:
                            st.dataframe(
                                df_inter.loc[df_inter[nombre], ["cooperativa", "segmento", "alertas_rojas",
                                                                 "alertas_amarillas"]],
                                width="stretch", hide_index=True,
                            )

    st.markdown("---")
    with st.expander("ℹ️ Reglas y umbrales (referenciales, no regulatorios)"):
        for codigo, regla in REGLAS_ALERTA.items():
            direccion_txt = "≥" if regla["direccion"] == "mayor_es_peor" else "≤"
            st.markdown(
                f"- **{regla['etiqueta']}** ({codigo}): 🟡 {direccion_txt} {regla['alerta_amarilla']*100:.1f}% · "
                f"🔴 {direccion_txt} {regla['alerta_roja']*100:.1f}%"
            )
        st.caption(
            "Además: caída interanual de depósitos ≥15% (roja) o ≥5% (amarilla). "
            "Umbrales calibrados sobre percentiles P75/P90 de la distribución real del sistema; "
            "ajustables en `config/umbrales_alerta.py`."
        )


if __name__ == "__main__":
    main()
