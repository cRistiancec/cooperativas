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
from ui import (
    aplicar_tema, botones_descarga, exigir_datos, render_filtros_globales, render_resumen_filtro, render_sidebar,
    selector_fecha_corte,
)
from utils.charts import COLORES, crear_ranking_barras
from utils.data_loader import (
    cargar_metadata,
    datos_filtrados,
    obtener_cooperativas_filtro,
)

st.set_page_config(
    page_title="Riesgo de Liquidez | Radar Cooperativo Ecuador",
    page_icon="💧",
    layout="wide",
)
aplicar_tema()


@st.cache_data(ttl=3600)
def _serie_liq_sistema(df_indicadores: pd.DataFrame) -> pd.DataFrame:
    """Serie temporal del promedio simple de LIQ (oficial) de la población filtrada (df ya filtrado)."""
    df_f = df_indicadores[df_indicadores["codigo"] == "LIQ"]
    serie = df_f.groupby("fecha", observed=True).agg(valor=("valor", "mean"), entidades=("entidad", "nunique")).reset_index()
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

    filtro = render_filtros_globales()
    fecha_sel = selector_fecha_corte(filtro)
    df_ind = datos_filtrados("indicadores", filtro)
    df_ranking = datos_filtrados("ranking", filtro)
    render_resumen_filtro(filtro, df_ind[df_ind["fecha"] == fecha_sel] if not df_ind.empty else df_ind,
                          corte=pd.Timestamp(metadata["fecha_max"]), fecha_analisis=fecha_sel)
    exigir_datos(df_ind)

    # ---------------------------------------------------------------- KPIs
    df_liq_fecha = df_ind[(df_ind["codigo"] == "LIQ") & (df_ind["fecha"] == fecha_sel)]

    liq_ampliada = calcular_liquidez_ampliada(df_ranking, fecha_sel)

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
                with st.expander("Datos del ranking LIQ (descarga)"):
                    _t = df_r[["fecha", "cooperativa", "entidad", "segmento", "procedencia_clasif", "codigo", "valor", "valor_pct"]]
                    st.dataframe(_t, width="stretch", hide_index=True)
                    botones_descarga(_t, filtro, f"liquidez_ranking_liq_{pd.Timestamp(fecha_sel):%Y%m}", "Ranking LIQ", "dl_liq_rank", corte=fecha_sel)
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
        serie = _serie_liq_sistema(df_ind)
        if not serie.empty:
            fig = px.line(serie, x="fecha", y="valor_pct", markers=True,
                          labels={"fecha": "Fecha", "valor_pct": "LIQ promedio (%)"})
            fig.update_traces(line_color=COLORES["primario"], fill="tozeroy")
            fig.update_layout(height=420, hovermode="x unified", paper_bgcolor="rgba(0,0,0,0)",
                               plot_bgcolor="rgba(0,0,0,0)", font_color=COLORES["texto"])
            fig.update_xaxes(gridcolor=COLORES["grid"])
            fig.update_yaxes(gridcolor=COLORES["grid"])
            st.plotly_chart(fig, width="stretch")
            st.caption("Promedio simple de LIQ de las entidades de la selección en cada mes (la composición puede variar entre meses).")
            with st.expander("Datos de la serie (descarga)"):
                st.dataframe(serie, width="stretch", hide_index=True)
                botones_descarga(serie, filtro, "liquidez_serie_liq", "Serie LIQ promedio", "dl_liq_serie", corte=fecha_sel)
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
        _con_balance = set(liq_ampliada["cooperativa"].astype(str)) if not liq_ampliada.empty else set()
        cooperativas = [c for c in obtener_cooperativas_filtro(filtro) if c in _con_balance]
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
            st.info("Sin cooperativas con datos de balance para la selección.")

    st.markdown("---")
    st.caption(
        "LIQ oficial: Fondos Disponibles / Depósitos de Corto Plazo (SEPS). "
        "Liquidez ampliada: (Fondos Disponibles + Inversiones) / Depósitos del Público — cálculo propio, no oficial."
    )


if __name__ == "__main__":
    main()
