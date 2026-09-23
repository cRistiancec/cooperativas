# -*- coding: utf-8 -*-
"""
Módulo 10: CAMEL — Score Compuesto
Score 0-100 por institución, agregando en percentiles los indicadores
oficiales de Capital, Calidad de Activos, Management, Earnings y Liquidez.
La dimensión "V - Vulnerabilidad Patrimonial" se muestra como métrica
complementaria (ver metodología).
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from analytics.financial_engine import CATEGORIAS_CAMEL, calcular_score_camel, clasificar_score
from ui import aplicar_tema, render_filtro_segmento, render_sidebar
from utils.charts import COLORES, altura_por_categorias, crear_radar, crear_ranking_barras, truncar_nombres_unicos
from utils.data_loader import cargar_indicadores, cargar_metadata

st.set_page_config(
    page_title="CAMEL Score | Radar Cooperativo Ecuador",
    page_icon="🧮",
    layout="wide",
)
aplicar_tema()

_SEMAFORO_CLASE = {
    "Sólido": "sps-light--ok", "Adecuado": "sps-light--ok",
    "Vigilancia": "sps-light--warn", "Crítico": "sps-light--crit", "Sin datos": "sps-light--warn",
}


def main():
    metadata = cargar_metadata()
    render_sidebar(metadata)

    st.title("🧮 CAMEL — Score Compuesto")
    st.markdown("Score 0-100 por institución (100 = mejor desempeño relativo), calculado a partir de percentiles de indicadores oficiales SEPS.")

    df_ind, calidad = cargar_indicadores()

    st.sidebar.markdown("### Filtros")
    # Filtro Global de Segmento (ui/filtros.py) — compartido con toda la plataforma
    segmento_sel = render_filtro_segmento()

    fechas = sorted(df_ind["fecha"].unique(), reverse=True)
    fecha_sel = st.sidebar.selectbox(
        "Fecha de análisis", fechas, format_func=lambda x: pd.Timestamp(x).strftime("%B %Y").title(),
        index=0, key="fecha_score",
    )

    score = calcular_score_camel(df_ind, fecha_sel, segmento_sel)
    if score.empty:
        st.warning("Sin datos suficientes para esta selección.")
        return

    score["clasificacion"] = score["score_total"].apply(clasificar_score)
    distribucion = score["clasificacion"].value_counts()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Score promedio del sistema", f"{score['score_total'].mean():.1f}")
    with col2:
        st.metric("Institución con mejor score", score.iloc[0]["cooperativa"][:28])
    with col3:
        st.metric("Instituciones en 'Vigilancia'", int(distribucion.get("Vigilancia", 0)))
    with col4:
        st.metric("Instituciones en 'Crítico'", int(distribucion.get("Crítico", 0)))

    st.markdown("---")

    tab1, tab2, tab3 = st.tabs(["🏆 Ranking", "🕸️ Radar por Cooperativa", "🗺️ Heatmap por Categoría"])

    with tab1:
        df_r = score.nlargest(20, "score_total")
        fig = crear_ranking_barras(df_r, x_col="score_total", y_col="cooperativa", formato_valor="{:.1f}")
        st.plotly_chart(fig, width="stretch")

        with st.expander("Ver clasificación completa"):
            st.dataframe(
                score[["cooperativa", "segmento", "score_total", "clasificacion"]].rename(columns={
                    "cooperativa": "Cooperativa", "segmento": "Segmento",
                    "score_total": "Score", "clasificacion": "Clasificación",
                }).round({"Score": 1}),
                width="stretch", height=380,
            )

    with tab2:
        coop_sel = st.selectbox("Cooperativa", score["cooperativa"].tolist(), key="coop_radar_score")
        fila = score[score["cooperativa"] == coop_sel].iloc[0]
        letras = list(CATEGORIAS_CAMEL.keys())
        valores_coop = [round(float(fila.get(f"score_{letra}", 0)), 1) for letra in letras]
        valores_sistema = [round(float(score[f"score_{letra}"].mean()), 1) for letra in letras]

        clase_sem = _SEMAFORO_CLASE.get(fila["clasificacion"], "sps-light--warn")
        st.markdown(
            f'<span class="sps-light {clase_sem}"><span class="sps-light__dot"></span>'
            f'{coop_sel} — {fila["clasificacion"]} (Score: {fila["score_total"]:.1f})</span>',
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)

        fig = crear_radar(
            letras, {coop_sel: valores_coop, "Promedio del sistema": valores_sistema},
            titulo="Score por categoría CAMEL (0-100)",
        )
        st.plotly_chart(fig, width="stretch")

        if "score_vulnerabilidad" in fila:
            st.caption(
                f"Métrica complementaria — Vulnerabilidad Patrimonial (V, no forma parte del score CAMEL): "
                f"{fila['score_vulnerabilidad']:.1f}/100."
            )

    with tab3:
        top_n = st.selectbox("Cooperativas a mostrar", [20, 30, 0], index=0,
                              format_func=lambda x: "Todas" if x == 0 else f"Top {x}", key="topn_heat_score")
        letras = list(CATEGORIAS_CAMEL.keys())
        columnas_score = [f"score_{letra}" for letra in letras]
        df_heat = score.nlargest(top_n if top_n else len(score), "score_total").set_index("cooperativa")[columnas_score]
        df_heat.columns = letras

        fig = go.Figure(go.Heatmap(
            z=df_heat.values, x=df_heat.columns, y=truncar_nombres_unicos([str(n) for n in df_heat.index]),
            colorscale="RdYlGn", zmin=0, zmax=100,
            hovertemplate="Cooperativa: %{y}<br>Categoría: %{x}<br>Score: %{z:.1f}<extra></extra>",
            colorbar=dict(title="Score"),
        ))
        fig.update_layout(height=altura_por_categorias(len(df_heat)), paper_bgcolor="rgba(0,0,0,0)",
                           font_color=COLORES["texto"], margin=dict(l=10, r=10, t=20, b=10),
                           yaxis=dict(tickfont=dict(size=10), automargin=True))
        st.plotly_chart(fig, width="stretch")

    st.markdown("---")
    with st.expander("ℹ️ Metodología del score"):
        st.markdown(
            """
            1. Para cada indicador oficial se calcula el **percentil** de cada cooperativa dentro del
               universo comparado (100 = mejor desempeño relativo, 0 = peor), orientado según si un
               valor alto es deseable o no.
            2. Los percentiles de una misma categoría (**C**apital, **A**ctivos, **M**anagement,
               **E**arnings, **L**iquidez) se promedian con igual ponderación → *score de categoría*.
            3. El **score compuesto** es el promedio simple de las 5 categorías (igual ponderación).

            **Nota sobre "S"**: la SEPS no publica en estos archivos indicadores de sensibilidad al
            riesgo de mercado (duración, brechas de tasa, VaR); el score cubre las 5 letras clásicas
            **C-A-M-E-L**, no "CAMELS" completo. La dimensión "V - Vulnerabilidad Patrimonial" que sí
            reporta la SEPS se muestra aparte, como métrica complementaria de capital.
            """
        )


if __name__ == "__main__":
    main()
