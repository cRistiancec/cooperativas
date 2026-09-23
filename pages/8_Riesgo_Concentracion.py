# -*- coding: utf-8 -*-
"""
Módulo 8: Riesgo de Concentración
HHI, CR5/CR10, curva de Lorenz, coeficiente de Gini y ranking Pareto,
calculados sobre participaciones de mercado reales (activos, cartera o
depósitos), por segmento y fecha.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from analytics.financial_engine import (
    calcular_cr,
    calcular_hhi,
    clasificar_hhi,
    coeficiente_gini,
    curva_lorenz,
)
from ui import aplicar_tema, render_filtro_segmento, render_sidebar
from utils.charts import COLORES, altura_por_categorias, crear_lorenz, truncar_nombres_unicos
from utils.data_loader import cargar_metadata, cargar_ranking_cooperativas

st.set_page_config(
    page_title="Riesgo de Concentración | Radar Cooperativo Ecuador",
    page_icon="🧩",
    layout="wide",
)
aplicar_tema()

_VARIABLES = {
    "Activos": "1",
    "Cartera de Créditos": "14",
    "Depósitos del Público": "21",
}


@st.cache_data(ttl=3600)
def _serie_hhi(df_ranking: pd.DataFrame, codigo: str, segmento: str = "Todos") -> pd.DataFrame:
    """Evolución del HHI en el tiempo para una variable dada."""
    df_f = df_ranking[df_ranking["codigo"] == codigo]
    if segmento != "Todos":
        df_f = df_f[df_f["segmento"] == segmento]

    registros = []
    for fecha, grupo in df_f.groupby("fecha", observed=True):
        registros.append({"fecha": fecha, "hhi": calcular_hhi(grupo["valor"])})
    return pd.DataFrame(registros).sort_values("fecha")


def main():
    metadata = cargar_metadata()
    render_sidebar(metadata)

    st.title("🧩 Riesgo de Concentración")
    st.markdown("Concentración de mercado del sistema cooperativo: HHI, razones CR-N, curva de Lorenz y Gini.")

    df_ranking = cargar_ranking_cooperativas()

    st.sidebar.markdown("### Filtros")
    # Filtro Global de Segmento (ui/filtros.py) — compartido con toda la plataforma
    segmento_sel = render_filtro_segmento()

    variable_sel = st.sidebar.selectbox("Variable", list(_VARIABLES.keys()), index=0, key="var_conc")
    codigo_sel = _VARIABLES[variable_sel]

    fechas = sorted(df_ranking["fecha"].unique(), reverse=True)
    fecha_sel = st.sidebar.selectbox(
        "Fecha de análisis", fechas, format_func=lambda x: pd.Timestamp(x).strftime("%B %Y").title(),
        index=0, key="fecha_conc",
    )

    mask = (df_ranking["fecha"] == fecha_sel) & (df_ranking["codigo"] == codigo_sel)
    if segmento_sel != "Todos":
        mask &= df_ranking["segmento"] == segmento_sel
    valores = df_ranking[mask]["valor"]

    hhi = calcular_hhi(valores)
    cr5 = calcular_cr(valores, 5)
    cr10 = calcular_cr(valores, 10)
    gini = coeficiente_gini(valores)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("HHI", f"{hhi:,.0f}", clasificar_hhi(hhi))
    with col2:
        st.metric("CR5", f"{cr5:.1f}%", "Top 5 instituciones")
    with col3:
        st.metric("CR10", f"{cr10:.1f}%", "Top 10 instituciones")
    with col4:
        st.metric("Coeficiente de Gini", f"{gini:.3f}", "0=igualdad, 1=máxima concentración")

    st.markdown("---")

    tab1, tab2, tab3, tab4 = st.tabs([
        "📈 Curva de Lorenz", "🏆 Top Instituciones (Pareto)", "📉 Evolución del HHI", "📋 Ranking Completo",
    ])

    with tab1:
        lorenz = curva_lorenz(valores)
        fig = crear_lorenz(lorenz, titulo=f"Curva de Lorenz — {variable_sel} ({pd.Timestamp(fecha_sel).strftime('%B %Y').title()})")
        st.plotly_chart(fig, width="stretch")
        st.caption(
            "Cuanto más se aleja la curva de la línea de igualdad perfecta, mayor es la concentración "
            f"de {variable_sel.lower()} en pocas instituciones (Gini = {gini:.3f})."
        )

    with tab2:
        df_top = df_ranking[mask].nlargest(20, "valor").copy()
        total = df_ranking[mask]["valor"].sum()
        df_top["participacion_pct"] = df_top["valor"] / total * 100 if total > 0 else 0
        df_top = df_top.sort_values("participacion_pct", ascending=True)

        nombres_top = [str(c) for c in df_top["cooperativa"]]
        fig = go.Figure(go.Bar(
            x=df_top["participacion_pct"], y=truncar_nombres_unicos(nombres_top), orientation="h",
            marker=dict(color=COLORES["primario"]), cliponaxis=False, customdata=nombres_top,
            hovertemplate="<b>%{customdata}</b><br>Participación: %{x:.1f}%<extra></extra>",
            text=df_top["participacion_pct"].apply(lambda v: f"{v:.1f}%"), textposition="outside",
        ))
        fig.update_layout(height=altura_por_categorias(len(df_top)), xaxis_title="Participación de mercado (%)",
                           yaxis=dict(tickfont=dict(size=10), automargin=True),
                           paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                           font_color=COLORES["texto"], margin=dict(l=10, r=70, t=20, b=10))
        st.plotly_chart(fig, width="stretch")

        acumulado_top20 = df_top["participacion_pct"].sum()
        st.caption(f"Las 20 mayores instituciones concentran el **{acumulado_top20:.1f}%** de {variable_sel.lower()} en el universo filtrado.")

    with tab3:
        serie_hhi = _serie_hhi(df_ranking, codigo_sel, segmento_sel)
        if not serie_hhi.empty:
            fig = go.Figure(go.Scatter(
                x=serie_hhi["fecha"], y=serie_hhi["hhi"], mode="lines+markers",
                line=dict(color=COLORES["primario"], width=2), fill="tozeroy",
            ))
            fig.add_hline(y=1500, line_dash="dash", line_color=COLORES["exito"], annotation_text="Umbral no concentrado")
            fig.add_hline(y=2500, line_dash="dash", line_color=COLORES["error"], annotation_text="Umbral alta concentración")
            fig.update_layout(height=420, hovermode="x unified", yaxis_title="HHI",
                               paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                               font_color=COLORES["texto"])
            fig.update_xaxes(gridcolor=COLORES["grid"])
            fig.update_yaxes(gridcolor=COLORES["grid"])
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("Sin datos suficientes.")

    with tab4:
        df_completo = df_ranking[mask][["cooperativa", "segmento", "valor"]].copy()
        df_completo["valor_millones"] = df_completo["valor"] / 1_000_000
        df_completo["participacion_pct"] = (df_completo["valor"] / df_completo["valor"].sum() * 100) if df_completo["valor"].sum() > 0 else 0
        df_completo = df_completo.sort_values("valor", ascending=False).reset_index(drop=True)
        df_completo.index += 1
        st.dataframe(
            df_completo[["cooperativa", "segmento", "valor_millones", "participacion_pct"]].rename(columns={
                "cooperativa": "Cooperativa", "segmento": "Segmento",
                "valor_millones": "Valor (USD M)", "participacion_pct": "Participación (%)",
            }),
            width="stretch", height=420,
        )


if __name__ == "__main__":
    main()
