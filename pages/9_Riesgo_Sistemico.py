# -*- coding: utf-8 -*-
"""
Módulo 9: Riesgo Sistémico
Índice de Importancia Sistémica (IIS) basado en tamaño y sustituibilidad de
mercado (participación en activos, cartera y depósitos).

Limitación declarada: no existen en las fuentes oficiales datos de
exposiciones interbancarias/intercooperativas, por lo que no es posible
construir un mapa de conectividad o contagio real. El componente de
"interconectividad" de la metodología D-SIB del Comité de Basilea queda
fuera de este índice por esa razón.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import plotly.express as px
import streamlit as st

from analytics.financial_engine import (
    ESQUEMAS_NO_IMPLEMENTADOS, ESTADOS, PESOS_IIS,
    calcular_indice_importancia_sistemica, calcular_serie_ipsf, correlacion_componentes,
    diagnostico_esquemas, evaluar_estado_sistemico,
)
from ui import aplicar_tema, render_filtro_segmento, render_sidebar
from utils.charts import COLORES, crear_ranking_barras
from utils.data_loader import cargar_indicadores, cargar_metadata, cargar_ranking_cooperativas

st.set_page_config(
    page_title="Riesgo Sistémico | Radar Cooperativo Ecuador",
    page_icon="🕸️",
    layout="wide",
)
aplicar_tema()


def main():
    metadata = cargar_metadata()
    render_sidebar(metadata)

    st.title("🕸️ Riesgo Sistémico")
    st.markdown("Índice de Importancia Sistémica (IIS) por institución, basado en tamaño y sustituibilidad de mercado.")

    st.info(
        "**Metodología y limitación de datos**: el IIS pondera participación de mercado en "
        f"activos ({PESOS_IIS['participacion_activos']:.0%}), cartera ({PESOS_IIS['participacion_cartera']:.0%}) "
        f"y depósitos ({PESOS_IIS['participacion_depositos']:.0%}) — los componentes de *tamaño* y "
        "*sustituibilidad* de la metodología D-SIB de Basilea. El componente de **interconectividad** "
        "(exposiciones interbancarias/intercooperativas) no está disponible en las fuentes oficiales "
        "de la SEPS usadas por esta plataforma, por lo que **no** se incluye un mapa de red real."
    )

    df_ranking = cargar_ranking_cooperativas()

    st.sidebar.markdown("### Filtros")
    # Filtro Global de Segmento (ui/filtros.py) — compartido con toda la plataforma
    segmento_sel = render_filtro_segmento()

    fechas = sorted(df_ranking["fecha"].unique(), reverse=True)
    fecha_sel = st.sidebar.selectbox(
        "Fecha de análisis", fechas, format_func=lambda x: pd.Timestamp(x).strftime("%B %Y").title(),
        index=0, key="fecha_sist",
    )

    iis = calcular_indice_importancia_sistemica(df_ranking, fecha_sel, segmento_sel)

    if iis.empty:
        st.warning("Sin datos suficientes para esta selección.")
        return

    top5_iis = iis.nlargest(5, "iis_normalizado")["iis_normalizado"].sum()
    top10_iis = iis.nlargest(10, "iis_normalizado")["iis_normalizado"].sum()
    total_iis = iis["iis_normalizado"].sum()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Instituciones evaluadas", f"{len(iis)}")
    with col2:
        st.metric("Institución más importante", iis.iloc[0]["cooperativa"][:28])
    with col3:
        st.metric("Concentración del IIS en Top 5", f"{(top5_iis / total_iis * 100):.1f}%" if total_iis > 0 else "—")
    with col4:
        st.metric("Concentración del IIS en Top 10", f"{(top10_iis / total_iis * 100):.1f}%" if total_iis > 0 else "—")

    st.markdown("---")

    tab1, tab2, tab3, tab4 = st.tabs([
        "🏆 Ranking IIS", "🫧 Huella Sistémica (Activos × Cartera × Depósitos)",
        "🧭 Estado Sistémico (Experimental)", "🌡️ IPSF (Experimental)",
    ])

    with tab1:
        df_r = iis.nlargest(20, "iis_normalizado")
        fig = crear_ranking_barras(df_r, x_col="iis_normalizado", y_col="cooperativa", formato_valor="{:.1f}")
        st.plotly_chart(fig, width="stretch")

    with tab2:
        df_bubble = iis.head(40).copy()
        df_bubble["activos_millones"] = df_bubble["activos"] / 1_000_000
        df_bubble["cartera_millones"] = df_bubble["cartera"] / 1_000_000
        df_bubble["depositos_millones"] = df_bubble["depositos"] / 1_000_000

        fig = px.scatter(
            df_bubble, x="activos_millones", y="cartera_millones", size="depositos_millones",
            color="iis_normalizado", color_continuous_scale="Blues", hover_name="cooperativa",
            labels={"activos_millones": "Activos (USD M)", "cartera_millones": "Cartera (USD M)",
                    "iis_normalizado": "IIS", "depositos_millones": "Depósitos (USD M)"},
            size_max=50,
        )
        fig.update_layout(height=500, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                           font_color=COLORES["texto"])
        fig.update_xaxes(gridcolor=COLORES["grid"])
        fig.update_yaxes(gridcolor=COLORES["grid"])
        st.plotly_chart(fig, width="stretch")
        st.caption("Tamaño de burbuja = Depósitos. Color = Índice de Importancia Sistémica (IIS). Top 40 instituciones por IIS.")

    # ------------------------------------------------------------ TAB 3
    with tab3:
        st.warning(
            "**ANALÍTICO EXPERIMENTAL** — árbol de decisión transparente y documentado, "
            "sin validación completa por backtesting histórico. No es un indicador oficial. "
            "Nunca usa 'CRISIS'; el estado más severo posible es 'EVENTO EXTREMO'."
        )
        df_ind, _ = cargar_indicadores()
        fechas_ind = sorted(df_ind["fecha"].unique())
        idx_actual = fechas_ind.index(fecha_sel) if fecha_sel in fechas_ind else None
        fecha_anterior_yoy = None
        for f in fechas_ind:
            if f <= pd.Timestamp(fecha_sel) - pd.DateOffset(months=11):
                fecha_anterior_yoy = f

        if fecha_anterior_yoy is None:
            st.info("No hay suficiente historia (≥12 meses) para comparar interanualmente en esta fecha.")
        else:
            resultado = evaluar_estado_sistemico(df_ind, df_ranking, fecha_sel, fecha_anterior_yoy, segmento_sel)

            _colores_estado = {
                "NORMAL": "sps-light--ok", "DESACELERACIÓN": "sps-light--warn",
                "CONTRACCIÓN SECTORIAL": "sps-light--warn", "CONTRACCIÓN SIGNIFICATIVA": "sps-light--crit",
                "ESTRÉS SISTÉMICO POTENCIAL": "sps-light--crit", "EVENTO EXTREMO": "sps-light--crit",
            }
            st.markdown(
                f'<span class="sps-light {_colores_estado.get(resultado["estado"], "sps-light--warn")}">'
                f'<span class="sps-light__dot"></span><strong>{resultado["estado"]}</strong></span>',
                unsafe_allow_html=True,
            )
            st.caption(
                f"Comparación interanual: {pd.Timestamp(fecha_sel):%B %Y} vs {pd.Timestamp(fecha_anterior_yoy):%B %Y}"
                f" · Confianza declarada: {resultado['confianza']}"
            )
            st.markdown("<br>", unsafe_allow_html=True)

            colA, colB, colC = st.columns(3)
            with colA:
                st.markdown("**DRIVERS**")
                for d in resultado["drivers"]:
                    st.markdown(f"- {d}")
                if not resultado["drivers"]:
                    st.markdown("_Ninguno_")
            with colB:
                st.markdown("**EVIDENCIA EN CONTRA**")
                for e in resultado["evidencia_en_contra"]:
                    st.markdown(f"- {e}")
                if not resultado["evidencia_en_contra"]:
                    st.markdown("_Ninguna_")
            with colC:
                st.markdown("**CRECIMIENTO YoY**")
                for dim, val in resultado["crecimiento_yoy_pct"].items():
                    st.markdown(f"- {dim}: {f'{val:.1f}%' if val is not None else 'sin datos'}")

            st.markdown("---")
            colD, colE = st.columns(2)
            with colD:
                st.markdown("**AMPLITUD**")
                st.json(resultado["amplitud"])
                st.markdown("**CONCENTRACIÓN (contexto)**")
                st.json(resultado["concentracion"])
            with colE:
                st.markdown("**PERSISTENCIA**")
                st.json(resultado["persistencia"])

            with st.expander("⚠️ Limitaciones declaradas"):
                for lim in resultado["limitaciones"]:
                    st.markdown(f"- {lim}")

            st.caption(f"Estados posibles (orden de severidad): {' → '.join(ESTADOS)}")

    # ------------------------------------------------------------ TAB 4
    with tab4:
        st.warning(
            "**IPSF — ÍNDICE ANALÍTICO EXPERIMENTAL.** No es un indicador oficial, no está validado "
            "para uso operativo y no debe interpretarse como capacidad predictiva sin backtesting "
            "(ver Alertas Tempranas → Persistencia para la evidencia disponible)."
        )
        df_ind, _ = cargar_indicadores()
        fechas_ipsf = sorted(df_ind["fecha"].unique())[-24:]
        with st.spinner("Calculando serie IPSF..."):
            df_serie = calcular_serie_ipsf(df_ind, df_ranking, fechas_ipsf, segmento_sel)

        if df_serie.empty:
            st.info("Sin datos suficientes para construir la serie IPSF en esta selección.")
        else:
            fig = px.line(df_serie, x="fecha", y=["ipsf_A_igual", "ipsf_B_experto"],
                           labels={"value": "IPSF (0-100)", "fecha": "Fecha", "variable": "Esquema de pesos"})
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                               font_color=COLORES["texto"], height=400)
            fig.update_xaxes(gridcolor=COLORES["grid"])
            fig.update_yaxes(gridcolor=COLORES["grid"])
            st.plotly_chart(fig, width="stretch")

            diag = diagnostico_esquemas(df_serie)
            if diag.get("valido"):
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.metric("Correlación esquemas A/B", f"{diag['correlacion_esquemas_A_B']}")
                with c2:
                    st.metric("Diferencia promedio", f"{diag['diferencia_promedio']:.1f} pts")
                with c3:
                    st.metric("Períodos evaluados", diag["n_periodos"])
                st.caption(diag["interpretacion"])

            diag_comp = correlacion_componentes(df_serie)
            if diag_comp.get("valido"):
                with st.expander("⚠️ ¿Robustez o redundancia? Correlación entre los 3 componentes"):
                    st.caption(diag_comp["interpretacion"])
                    st.dataframe(pd.DataFrame(diag_comp["matriz"]).round(2), width="stretch")

            with st.expander("Esquemas de ponderación NO implementados y por qué"):
                for nombre, razon in ESQUEMAS_NO_IMPLEMENTADOS.items():
                    st.markdown(f"**{nombre}**: {razon}")


if __name__ == "__main__":
    main()
