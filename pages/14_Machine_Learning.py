# -*- coding: utf-8 -*-
"""
Módulo 14: Machine Learning
Detección de anomalías (Isolation Forest) y segmentación de riesgo
(KMeans) sobre indicadores oficiales, entrenados en tiempo real.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import plotly.express as px
import streamlit as st

from analytics.financial_engine import calcular_score_camel
from models.anomalias import detectar_anomalias, explicar_anomalia
from models.clustering import COLUMNAS_CLUSTER, resumen_clusters, segmentar_riesgo
from ui import aplicar_tema, render_filtro_segmento, render_sidebar
from utils.charts import COLORES
from utils.data_loader import cargar_indicadores, cargar_metadata

st.set_page_config(
    page_title="Machine Learning | Radar Cooperativo Ecuador",
    page_icon="🤖",
    layout="wide",
)
aplicar_tema()


def main():
    metadata = cargar_metadata()
    render_sidebar(metadata)

    st.title("🤖 Machine Learning")
    st.markdown("Modelos no supervisados entrenados en tiempo real: detección de anomalías y segmentación de riesgo.")
    st.warning(
        "**Detección de anomalías ≠ predicción de crisis.** El Isolation Forest mide qué tan atípica es "
        "la combinación de indicadores de una institución frente al resto del sistema **en un corte del "
        "tiempo** — no predice un evento futuro, no estima probabilidad de insolvencia y no reemplaza el "
        "motor de reglas de Alertas Tempranas. Una institución puede ser 'anómala' por ser excepcionalmente "
        "sólida, no solo por estar en problemas — la dirección se interpreta caso por caso "
        "(ver 'Explicación' en cada resultado), nunca se asume automáticamente."
    )

    df_ind, calidad = cargar_indicadores()

    st.sidebar.markdown("### Filtros")
    # Filtro Global de Segmento (ui/filtros.py) — compartido con toda la plataforma
    segmento_sel = render_filtro_segmento()

    fechas = sorted(df_ind["fecha"].unique(), reverse=True)
    fecha_sel = st.sidebar.selectbox(
        "Fecha de análisis", fechas, format_func=lambda x: pd.Timestamp(x).strftime("%B %Y").title(),
        index=0, key="fecha_ml",
    )

    tab1, tab2 = st.tabs(["🔍 Detección de Anomalías (Isolation Forest)", "🧬 Segmentación de Riesgo (KMeans)"])

    # ------------------------------------------------------------ TAB 1
    with tab1:
        st.caption(
            "Isolation Forest identifica instituciones cuya **combinación** de indicadores "
            "(morosidad, cobertura, ROE, ROA, liquidez, capitalización, eficiencia, calidad de activos) "
            "es atípica frente al resto del sistema. Es un modelo no supervisado: no reemplaza el motor "
            "de reglas de Alertas Tempranas, es una lente complementaria basada en patrones."
        )
        contaminacion = st.slider("Proporción esperada de instituciones atípicas", 0.05, 0.25, 0.10, 0.01, key="contam_ml")

        anomalias = detectar_anomalias(df_ind, fecha_sel, segmento_sel, contaminacion)
        if anomalias.empty:
            st.warning("Sin datos suficientes para esta selección (se requieren al menos 15 instituciones con datos completos).")
        else:
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Instituciones evaluadas", len(anomalias))
            with col2:
                st.metric("Instituciones marcadas como atípicas", int(anomalias["es_anomalia"].sum()))

            st.markdown("**Instituciones más atípicas**")
            top_anomalias = anomalias[anomalias["es_anomalia"]].head(15)
            for _, fila in top_anomalias.iterrows():
                razones = explicar_anomalia(fila, anomalias)
                razones_txt = "; ".join(razones) if razones else "combinación atípica de indicadores"
                st.markdown(
                    f"""
                    <div style="padding:8px 4px; border-bottom:1px solid var(--sps-border);">
                        <strong>{fila['cooperativa']}</strong>
                        <span style="color:var(--sps-text-dim); font-size:0.8rem;"> · {fila['segmento']}</span><br>
                        <span style="font-size:0.78rem; color:var(--sps-text-dim);">{razones_txt}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            st.markdown("---")
            st.markdown("**Mapa de dispersión: Morosidad vs. ROE** (color = score de anomalía)")
            fig = px.scatter(
                anomalias, x="MOR_TOT", y="ROE", color="score_anomalia", color_continuous_scale="RdYlGn",
                hover_name="cooperativa", symbol="es_anomalia",
                labels={"MOR_TOT": "Morosidad Total (ratio)", "ROE": "ROE (ratio)", "score_anomalia": "Score"},
            )
            fig.update_layout(height=450, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                               font_color=COLORES["texto"])
            fig.update_xaxes(gridcolor=COLORES["grid"])
            fig.update_yaxes(gridcolor=COLORES["grid"])
            st.plotly_chart(fig, width="stretch")

    # ------------------------------------------------------------ TAB 2
    with tab2:
        st.caption(
            "KMeans agrupa a las cooperativas según sus scores CAMEL por categoría (C-A-M-E-L, "
            "0-100). Las etiquetas de cada grupo se derivan del score promedio observado en cada "
            "corrida, no son categorías fijas de negocio."
        )
        n_clusters = st.slider("Número de segmentos", 3, 6, 4, key="n_clusters_ml")

        score = calcular_score_camel(df_ind, fecha_sel, segmento_sel)
        segmentado = segmentar_riesgo(score, n_clusters=n_clusters)

        if segmentado.empty:
            st.warning("Sin datos suficientes para esta selección.")
        else:
            resumen = resumen_clusters(segmentado)
            st.dataframe(resumen, width="stretch")

            fig = px.scatter(
                segmentado, x="score_A", y="score_E", color="etiqueta_cluster", size="score_total",
                hover_name="cooperativa",
                labels={"score_A": "Score Calidad de Activos", "score_E": "Score Earnings", "etiqueta_cluster": "Segmento"},
            )
            fig.update_layout(height=450, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                               font_color=COLORES["texto"],
                               legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center"))
            fig.update_xaxes(gridcolor=COLORES["grid"])
            fig.update_yaxes(gridcolor=COLORES["grid"])
            st.plotly_chart(fig, width="stretch")

            with st.expander("Ver instituciones por segmento"):
                segmento_ver = st.selectbox("Segmento de riesgo", segmentado["etiqueta_cluster"].unique(), key="ver_cluster")
                df_ver = segmentado[segmentado["etiqueta_cluster"] == segmento_ver][
                    ["cooperativa", "segmento", "score_total"] + COLUMNAS_CLUSTER
                ].sort_values("score_total", ascending=False)
                st.dataframe(df_ver.round(1), width="stretch", height=350)


if __name__ == "__main__":
    main()
