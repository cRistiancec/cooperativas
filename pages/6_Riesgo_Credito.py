# -*- coding: utf-8 -*-
"""
Módulo 6: Riesgo de Crédito
Morosidad y cobertura oficiales por tipo de cartera (SEPS), evolución de
cartera vencida y provisiones, y heatmap mensual de morosidad total.

Limitación declarada: la SEPS no publica en estos archivos información de
crédito a nivel de operación, por lo que vintage curves, roll-rate y
matrices de transición reales no son calculables con los datos disponibles.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from analytics.financial_engine import (
    CARTERAS_COBERTURA,
    CARTERAS_MOROSIDAD,
    CODIGO_CARTERA_VENCIDA,
    CODIGO_PROVISION_CARTERA,
    construir_panel_morosidad_cobertura,
    construir_serie_cartera_vencida,
)
from ui import aplicar_tema, render_filtro_segmento, render_sidebar
from utils.charts import COLORES, altura_por_categorias, crear_ranking_barras, truncar_nombres_unicos
from utils.data_loader import cargar_balance_por_codigos, cargar_indicadores, cargar_metadata

st.set_page_config(
    page_title="Riesgo de Crédito | Radar Cooperativo Ecuador",
    page_icon="🧾",
    layout="wide",
)
aplicar_tema()


def main():
    metadata = cargar_metadata()
    render_sidebar(metadata)

    st.title("🧾 Riesgo de Crédito")
    st.markdown("Morosidad, cobertura y cartera vencida del sistema cooperativo, con indicadores oficiales de la SEPS.")

    df_ind, calidad = cargar_indicadores()

    st.sidebar.markdown("### Filtros")
    # Filtro Global de Segmento (ui/filtros.py) — compartido con toda la plataforma
    segmento_sel = render_filtro_segmento()

    fechas = sorted(df_ind["fecha"].unique(), reverse=True)
    fecha_sel = st.sidebar.selectbox(
        "Fecha de análisis", fechas, format_func=lambda x: pd.Timestamp(x).strftime("%B %Y").title(),
        index=0, key="fecha_credito",
    )

    # ---------------------------------------------------------------- KPIs
    df_mor_tot = df_ind[(df_ind["codigo"] == "MOR_TOT") & (df_ind["fecha"] == fecha_sel)]
    df_cob_tot = df_ind[(df_ind["codigo"] == "COB_TOT") & (df_ind["fecha"] == fecha_sel)]
    if segmento_sel != "Todos":
        df_mor_tot = df_mor_tot[df_mor_tot["segmento"] == segmento_sel]
        df_cob_tot = df_cob_tot[df_cob_tot["segmento"] == segmento_sel]

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Morosidad Total (promedio)", f"{df_mor_tot['valor'].mean() * 100:,.1f}%" if not df_mor_tot.empty else "—")
    with col2:
        st.metric("Morosidad Total (mediana)", f"{df_mor_tot['valor'].median() * 100:,.1f}%" if not df_mor_tot.empty else "—")
    with col3:
        st.metric("Cobertura Total (promedio)", f"{df_cob_tot['valor'].mean() * 100:,.0f}%" if not df_cob_tot.empty else "—")
    with col4:
        criticas = (df_mor_tot["valor"] > 0.14).sum() if not df_mor_tot.empty else 0
        st.metric("Instituciones con MOR > 14%", f"{criticas}")

    st.markdown("---")

    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Mora y Cobertura por Cartera", "🏆 Ranking", "📈 Cartera Vencida y Provisiones", "🗺️ Heatmap Mensual",
    ])

    # ------------------------------------------------------------ TAB 1
    with tab1:
        panel = construir_panel_morosidad_cobertura(df_ind, fecha_sel, segmento_sel)
        col_izq, col_der = st.columns(2)

        with col_izq:
            st.markdown("**Morosidad por tipo de cartera (promedio del sistema)**")
            df_mor = panel[panel["codigo"].isin(CARTERAS_MOROSIDAD.keys())].copy()
            df_mor["cartera"] = df_mor["codigo"].map(CARTERAS_MOROSIDAD)
            df_mor = df_mor.sort_values("valor_pct", ascending=True)
            fig = go.Figure(go.Bar(
                x=df_mor["valor_pct"], y=df_mor["cartera"], orientation="h",
                marker=dict(color=df_mor["valor_pct"], colorscale="RdYlGn_r"),
                text=df_mor["valor_pct"].apply(lambda v: f"{v:.1f}%"), textposition="outside",
            ))
            fig.update_layout(height=380, margin=dict(l=10, r=10, t=20, b=10),
                               paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                               font_color=COLORES["texto"], xaxis_title="Morosidad (%)")
            st.plotly_chart(fig, width="stretch")

        with col_der:
            st.markdown("**Cobertura por tipo de cartera (promedio del sistema)**")
            df_cob = panel[panel["codigo"].isin(CARTERAS_COBERTURA.keys())].copy()
            df_cob["cartera"] = df_cob["codigo"].map(CARTERAS_COBERTURA)
            df_cob = df_cob.sort_values("valor_pct", ascending=True)
            fig2 = go.Figure(go.Bar(
                x=df_cob["valor_pct"], y=df_cob["cartera"], orientation="h",
                marker=dict(color=df_cob["valor_pct"], colorscale="RdYlGn"),
                text=df_cob["valor_pct"].apply(lambda v: f"{v:.0f}%"), textposition="outside",
            ))
            fig2.update_layout(height=380, margin=dict(l=10, r=10, t=20, b=10),
                                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                font_color=COLORES["texto"], xaxis_title="Cobertura (%)")
            st.plotly_chart(fig2, width="stretch")

    # ------------------------------------------------------------ TAB 2
    with tab2:
        st.markdown("**Ranking por Morosidad Total (menor a mayor = mejor)**")
        if not df_mor_tot.empty:
            df_r = df_mor_tot.copy()
            df_r["valor_pct"] = df_r["valor"] * 100
            df_r = df_r.nsmallest(30, "valor_pct")
            fig = crear_ranking_barras(df_r, x_col="valor_pct", y_col="cooperativa", formato_valor="{:.1f}%")
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("Sin datos para esta selección.")

    # ------------------------------------------------------------ TAB 3
    with tab3:
        df_bal = cargar_balance_por_codigos((CODIGO_CARTERA_VENCIDA, CODIGO_PROVISION_CARTERA))
        serie_cv = construir_serie_cartera_vencida(df_bal, segmento_sel)
        if not serie_cv.empty:
            fig = px.line(serie_cv, x="fecha", y="valor_millones", color="cuenta", markers=True,
                          labels={"fecha": "Fecha", "valor_millones": "USD Millones", "cuenta": ""})
            fig.update_layout(height=430, hovermode="x unified", paper_bgcolor="rgba(0,0,0,0)",
                               plot_bgcolor="rgba(0,0,0,0)", font_color=COLORES["texto"],
                               legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center"))
            fig.update_xaxes(gridcolor=COLORES["grid"])
            fig.update_yaxes(gridcolor=COLORES["grid"])
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("Sin datos suficientes.")

        st.info(
            "**Limitación de datos**: vintage curves, roll-rate y matrices de transición requieren "
            "microdata de crédito a nivel de operación (fecha de originación, días de mora por "
            "operación), información que no está disponible en los archivos oficiales de la SEPS "
            "utilizados por esta plataforma. Esta sección se ampliará si se incorpora esa fuente."
        )

    # ------------------------------------------------------------ TAB 4
    with tab4:
        df_mor_serie = df_ind[df_ind["codigo"] == "MOR_TOT"].copy()
        if segmento_sel != "Todos":
            df_mor_serie = df_mor_serie[df_mor_serie["segmento"] == segmento_sel]

        if not df_mor_serie.empty:
            top_n = st.selectbox("Cooperativas a mostrar", [20, 30, 0], index=0,
                                  format_func=lambda x: "Todas" if x == 0 else f"Top {x}", key="topn_heat_credito")
            ultima_fecha = df_mor_serie["fecha"].max()
            top_coops = (
                df_mor_serie[df_mor_serie["fecha"] == ultima_fecha]
                .nlargest(top_n if top_n else len(df_mor_serie), "valor")["cooperativa"].tolist()
            )
            df_mor_serie = df_mor_serie[df_mor_serie["cooperativa"].isin(top_coops)]
            df_mor_serie["periodo"] = df_mor_serie["fecha"].dt.strftime("%Y-%m")
            heatmap = df_mor_serie.pivot_table(index="cooperativa", columns="periodo", values="valor", aggfunc="first") * 100

            fig = go.Figure(go.Heatmap(
                z=heatmap.values, x=heatmap.columns,
                y=truncar_nombres_unicos([str(n) for n in heatmap.index]), colorscale="RdYlGn_r",
                hovertemplate="Cooperativa: %{y}<br>Período: %{x}<br>Morosidad: %{z:.1f}%<extra></extra>",
                colorbar=dict(title="Mora %"),
            ))
            fig.update_layout(height=altura_por_categorias(len(heatmap)),
                               xaxis=dict(tickangle=-45, automargin=True),
                               yaxis=dict(tickfont=dict(size=10), automargin=True),
                               paper_bgcolor="rgba(0,0,0,0)", font_color=COLORES["texto"],
                               margin=dict(l=10, r=10, t=20, b=60))
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("Sin datos suficientes.")


if __name__ == "__main__":
    main()
