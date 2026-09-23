# -*- coding: utf-8 -*-
"""
Módulo 5: Riesgo de Liquidez
Indicador oficial LIQ (SEPS) + liquidez ampliada calculada, distribución,
percentiles y un simulador simple de estrés de retiro de depósitos.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import plotly.express as px
import streamlit as st

from analytics.financial_engine import calcular_liquidez_ampliada, calcular_cobertura_retiro
from ui import aplicar_tema, render_filtro_segmento, render_sidebar
from utils.charts import COLORES, crear_ranking_barras
from utils.data_loader import (
    cargar_indicadores,
    cargar_metadata,
    cargar_ranking_cooperativas,
    obtener_cooperativas_por_segmento,
)

st.set_page_config(
    page_title="Riesgo de Liquidez | Radar Cooperativo Ecuador",
    page_icon="💧",
    layout="wide",
)
aplicar_tema()


@st.cache_data(ttl=3600)
def _serie_liq_sistema(df_indicadores: pd.DataFrame, segmento: str = "Todos") -> pd.DataFrame:
    """Serie temporal del promedio simple de LIQ (oficial) para el sistema."""
    df_f = df_indicadores[df_indicadores["codigo"] == "LIQ"]
    if segmento != "Todos":
        df_f = df_f[df_f["segmento"] == segmento]
    serie = df_f.groupby("fecha", observed=True)["valor"].mean().reset_index()
    serie["valor_pct"] = serie["valor"] * 100
    return serie.sort_values("fecha")


def main():
    metadata = cargar_metadata()
    render_sidebar(metadata)

    st.title("💧 Riesgo de Liquidez")
    st.markdown(
        "Indicador oficial **LIQ** (Fondos Disponibles / Depósitos de Corto Plazo) de la SEPS, "
        "complementado con una **liquidez ampliada calculada** (Fondos Disponibles + Inversiones) / Depósitos."
    )

    df_ind, calidad = cargar_indicadores()
    df_ranking = cargar_ranking_cooperativas()

    st.sidebar.markdown("### Filtros")
    # Filtro Global de Segmento (ui/filtros.py) — compartido con toda la plataforma
    segmento_sel = render_filtro_segmento()

    fechas = sorted(df_ind["fecha"].unique(), reverse=True)
    fecha_sel = st.sidebar.selectbox(
        "Fecha de análisis", fechas, format_func=lambda x: pd.Timestamp(x).strftime("%B %Y").title(),
        index=0, key="fecha_liq",
    )

    # ---------------------------------------------------------------- KPIs
    df_liq_fecha = df_ind[(df_ind["codigo"] == "LIQ") & (df_ind["fecha"] == fecha_sel)]
    if segmento_sel != "Todos":
        df_liq_fecha = df_liq_fecha[df_liq_fecha["segmento"] == segmento_sel]

    liq_ampliada = calcular_liquidez_ampliada(df_ranking, fecha_sel, segmento_sel)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("LIQ oficial (promedio)", f"{df_liq_fecha['valor'].mean() * 100:,.1f}%" if not df_liq_fecha.empty else "—")
    with col2:
        st.metric("LIQ oficial (mediana)", f"{df_liq_fecha['valor'].median() * 100:,.1f}%" if not df_liq_fecha.empty else "—")
    with col3:
        st.metric("Liquidez ampliada (promedio)", f"{liq_ampliada['liquidez_ampliada'].mean():,.1f}%" if not liq_ampliada.empty else "—")
    with col4:
        bajo_umbral = (df_liq_fecha["valor"] < 0.10).sum() if not df_liq_fecha.empty else 0
        st.metric("Instituciones con LIQ < 10%", f"{bajo_umbral}")

    st.markdown("---")

    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Ranking", "📈 Evolución del Sistema", "📉 Distribución", "🧪 Simulador de Estrés",
    ])

    # ------------------------------------------------------------ TAB 1
    with tab1:
        col_izq, col_der = st.columns(2)
        with col_izq:
            st.markdown("**Ranking por LIQ oficial (mayor a menor)**")
            if not df_liq_fecha.empty:
                df_r = df_liq_fecha.copy()
                df_r["valor_pct"] = df_r["valor"] * 100
                df_r = df_r.nlargest(20, "valor_pct")
                fig = crear_ranking_barras(df_r, x_col="valor_pct", y_col="cooperativa", formato_valor="{:.1f}%")
                st.plotly_chart(fig, width="stretch")
            else:
                st.info("Sin datos para esta selección.")

        with col_der:
            st.markdown("**Ranking por liquidez ampliada (calculada)**")
            if not liq_ampliada.empty:
                df_r2 = liq_ampliada.nlargest(20, "liquidez_ampliada")
                fig2 = crear_ranking_barras(df_r2, x_col="liquidez_ampliada", y_col="cooperativa", formato_valor="{:.1f}%")
                st.plotly_chart(fig2, width="stretch")
            else:
                st.info("Sin datos para esta selección.")

    # ------------------------------------------------------------ TAB 2
    with tab2:
        serie = _serie_liq_sistema(df_ind, segmento_sel)
        if not serie.empty:
            fig = px.line(serie, x="fecha", y="valor_pct", markers=True,
                          labels={"fecha": "Fecha", "valor_pct": "LIQ promedio (%)"})
            fig.update_traces(line_color=COLORES["primario"], fill="tozeroy")
            fig.update_layout(height=420, hovermode="x unified", paper_bgcolor="rgba(0,0,0,0)",
                               plot_bgcolor="rgba(0,0,0,0)", font_color=COLORES["texto"])
            fig.update_xaxes(gridcolor=COLORES["grid"])
            fig.update_yaxes(gridcolor=COLORES["grid"])
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("Sin datos suficientes.")

    # ------------------------------------------------------------ TAB 3
    with tab3:
        if not df_liq_fecha.empty:
            df_box = df_liq_fecha.copy()
            df_box["valor_pct"] = df_box["valor"] * 100
            fig = px.box(df_box, y="valor_pct", points="all",
                         labels={"valor_pct": "LIQ (%)"}, color_discrete_sequence=[COLORES["primario"]])
            fig.update_layout(height=420, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                               font_color=COLORES["texto"])
            st.plotly_chart(fig, width="stretch")
            st.caption(
                f"P10: {df_box['valor_pct'].quantile(.10):.1f}% · "
                f"P25: {df_box['valor_pct'].quantile(.25):.1f}% · "
                f"P50: {df_box['valor_pct'].quantile(.50):.1f}% · "
                f"P75: {df_box['valor_pct'].quantile(.75):.1f}% · "
                f"P90: {df_box['valor_pct'].quantile(.90):.1f}%"
            )
        else:
            st.info("Sin datos suficientes.")

    # ------------------------------------------------------------ TAB 4
    with tab4:
        st.markdown(
            "**Simulador informativo**: estima los días de cobertura de una cooperativa ante una "
            "salida diaria estimada de depósitos, usando sus Fondos Disponibles reportados. "
            "No es un modelo de estrés regulatorio; es una aproximación simple para priorizar revisión."
        )
        cooperativas = obtener_cooperativas_por_segmento(segmento_sel)
        if cooperativas:
            coop_sel = st.selectbox("Cooperativa", cooperativas, key="coop_stress_liq")
            fila = liq_ampliada[liq_ampliada["cooperativa"] == coop_sel]
            if not fila.empty:
                fondos_m = fila.iloc[0]["fondos_disponibles"] / 1_000_000
                depositos_m = fila.iloc[0]["depositos"] / 1_000_000
                st.metric("Fondos Disponibles", f"${fondos_m:,.1f}M")
                salida_pct = st.slider("Salida diaria estimada de depósitos (%)", 0.1, 5.0, 1.0, 0.1)
                salida_m = depositos_m * (salida_pct / 100)
                dias = calcular_cobertura_retiro(fondos_m, salida_m)
                dias_txt = f"{dias:,.0f} días" if dias != float("inf") else "Sin salida estimada"
                st.metric("Días de cobertura estimados", dias_txt)
            else:
                st.info("Sin datos de balance para esta cooperativa en la fecha seleccionada.")
        else:
            st.info("Sin cooperativas disponibles para este segmento.")

    st.markdown("---")
    st.caption(
        "LIQ oficial: Fondos Disponibles / Depósitos de Corto Plazo (SEPS). "
        "Liquidez ampliada: (Fondos Disponibles + Inversiones) / Depósitos del Público — cálculo propio, no oficial."
    )


if __name__ == "__main__":
    main()
