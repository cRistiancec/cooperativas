# -*- coding: utf-8 -*-
"""
Módulo 13: Modelos Predictivos
Forecast ARIMA de series del sistema (activos, cartera, depósitos,
morosidad) y predicción de morosidad a un mes con Random Forest,
entrenados en tiempo real sobre los datos oficiales, con métricas de
validación reales (backtest / holdout temporal).
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from models.forecast import evaluar_backtest, forecast_serie
from models.prediccion_morosidad import entrenar_y_evaluar, proyectar_proximo_mes
from ui import aplicar_tema, render_filtro_segmento, render_sidebar
from utils.charts import COLORES
from utils.data_loader import cargar_indicadores, cargar_metadata, cargar_metricas_sistema

st.set_page_config(
    page_title="Modelos Predictivos | Radar Cooperativo Ecuador",
    page_icon="📉",
    layout="wide",
)
aplicar_tema()

_SERIES_DISPONIBLES = {
    "Activos Totales": "1",
    "Cartera de Créditos": "14",
    "Depósitos del Público": "21",
    "Patrimonio": "3",
}


@st.cache_data(ttl=3600)
def _serie_sistema(codigo: str, segmento: str = "Todos") -> pd.Series:
    """
    Serie mensual del sistema para ARIMA, con filtro opcional por segmento.

    Usa el mismo agregado (`agg_metricas_sistema`) y la misma lógica de suma
    que el resto de la plataforma, de modo que la serie proyectada coincide
    exactamente con la que muestran los KPIs del home y de Panorama.
    """
    df = cargar_metricas_sistema()
    df_f = df[df["codigo"] == codigo]
    if segmento != "Todos":
        df_f = df_f[df_f["segmento"] == segmento]
    serie = df_f.groupby("fecha", observed=True)["valor_total"].sum().sort_index()
    serie.index = pd.DatetimeIndex(serie.index, freq="ME")
    return serie


@st.cache_resource(ttl=3600, show_spinner="Entrenando modelo de predicción de morosidad...")
def _modelo_morosidad_entrenado():
    df_ind, _ = cargar_indicadores()
    resultado = entrenar_y_evaluar(df_ind, meses_holdout=6)
    return resultado, df_ind


def main():
    metadata = cargar_metadata()
    render_sidebar(metadata)

    st.title("📉 Modelos Predictivos")
    st.markdown("Forecast de series del sistema (ARIMA) y predicción de morosidad a un mes (Random Forest).")
    st.warning(
        "**ANALÍTICO NO VALIDADO / EXPERIMENTAL.** Ambos modelos usan una separación temporal "
        "correcta (entrenan con meses pasados, validan contra los más recientes) y reportan sus "
        "métricas reales de error (no simuladas), pero se evalúan sobre **una única ventana de "
        "holdout**, no sobre múltiples cortes temporales — no hay evidencia de estabilidad del "
        "desempeño a través del tiempo. No se han contrastado contra los eventos de "
        "`analytics.eventos`/`analytics.backtesting` (deterioro real observado). No usar como "
        "predicción operativa sin revisión de un analista de riesgos."
    )

    # Filtro Global de Segmento (ui/filtros.py) — un único selector para toda
    # la página, aplicado tanto al forecast ARIMA (tab 1) como a la
    # proyección de morosidad (tab 2). Antes cada tab tenía su propio
    # selector de segmento independiente; ahora comparten el mismo valor,
    # consistente con el resto de la plataforma.
    st.sidebar.markdown("### Filtros")
    segmento_sel = render_filtro_segmento()

    tab1, tab2 = st.tabs(["📈 Forecast del Sistema (ARIMA)", "🌲 Predicción de Morosidad (Random Forest)"])

    # ------------------------------------------------------------ TAB 1
    with tab1:
        col_sel, col_pasos = st.columns([2, 1])
        with col_sel:
            variable_sel = st.selectbox("Variable a proyectar", list(_SERIES_DISPONIBLES.keys()), key="var_forecast")
        with col_pasos:
            pasos = st.slider("Meses a proyectar", 3, 12, 6, key="pasos_forecast")

        serie = _serie_sistema(_SERIES_DISPONIBLES[variable_sel], segmento_sel)

        try:
            resultado = forecast_serie(serie, pasos=pasos)
            backtest = evaluar_backtest(serie, pasos_holdout=6)
        except ValueError as e:
            st.warning(str(e))
            return

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Orden ARIMA seleccionado (por AIC)", f"{resultado['orden']}")
        with col2:
            st.metric("Error de validación (MAPE, backtest 6m)", f"{backtest['mape']:.2f}%")
        with col3:
            variacion = (resultado["valores"][-1] - serie.iloc[-1]) / serie.iloc[-1] * 100
            st.metric(f"Variación proyectada a {pasos} meses", f"{variacion:+.1f}%")

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=serie.index, y=serie.values / 1_000_000, mode="lines",
                                  name="Histórico", line=dict(color=COLORES["primario"], width=2)))
        fig.add_trace(go.Scatter(x=resultado["fechas_futuras"], y=resultado["valores"] / 1_000_000, mode="lines+markers",
                                  name="Forecast", line=dict(color=COLORES["advertencia"], width=2, dash="dash")))
        fig.add_trace(go.Scatter(
            x=list(resultado["fechas_futuras"]) + list(resultado["fechas_futuras"][::-1]),
            y=list(resultado["limite_superior"] / 1_000_000) + list(resultado["limite_inferior"][::-1] / 1_000_000),
            fill="toself", fillcolor="rgba(245, 158, 11, 0.15)", line=dict(color="rgba(0,0,0,0)"),
            name="IC 95%", hoverinfo="skip",
        ))
        fig.update_layout(height=450, hovermode="x unified", yaxis_title="USD Millones",
                           paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color=COLORES["texto"],
                           legend=dict(orientation="h", y=-0.15, x=0.5, xanchor="center"))
        fig.update_xaxes(gridcolor=COLORES["grid"])
        fig.update_yaxes(gridcolor=COLORES["grid"])
        st.plotly_chart(fig, width="stretch")

        st.caption(
            f"El modelo se re-entrena en cada ejecución sobre el histórico real ({len(serie)} meses). El MAPE de "
            "backtest se calcula ocultando los últimos 6 meses reales, prediciéndolos, y comparando contra "
            "el valor observado — es una medida honesta de desempeño, no una proyección sin validar."
        )

    # ------------------------------------------------------------ TAB 2
    with tab2:
        resultado_mora, df_ind = _modelo_morosidad_entrenado()

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Error absoluto medio (MAE)", f"{resultado_mora['mae_pp']:.2f} pp")
        with col2:
            st.metric("R² (holdout temporal)", f"{resultado_mora['r2']:.3f}")
        with col3:
            st.metric("Observaciones de entrenamiento", f"{resultado_mora['n_train']:,}")
        with col4:
            st.metric("Observaciones de prueba", f"{resultado_mora['n_test']:,}")

        st.caption(
            f"Validación con split **temporal**: entrena con datos anteriores a "
            f"{pd.Timestamp(resultado_mora['fecha_corte']).strftime('%B %Y').title()} y evalúa contra los "
            "6 meses posteriores (no vistos durante el entrenamiento)."
        )

        col_izq, col_der = st.columns([1, 1])
        with col_izq:
            st.markdown("**Importancia de variables**")
            imp = resultado_mora["importancias"]
            fig_imp = go.Figure(go.Bar(
                x=imp["importancia"], y=imp["feature"], orientation="h",
                marker_color=COLORES["primario"],
            ))
            fig_imp.update_layout(height=320, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                   font_color=COLORES["texto"], margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig_imp, width="stretch")

        with col_der:
            st.markdown("**Predicho vs. Real (holdout)**")
            fig_scatter = go.Figure(go.Scatter(
                x=resultado_mora["test_real"], y=resultado_mora["test_predicho"], mode="markers",
                marker=dict(color=COLORES["primario"], size=5, opacity=0.5),
            ))
            max_val = max(resultado_mora["test_real"].max(), resultado_mora["test_predicho"].max())
            fig_scatter.add_trace(go.Scatter(x=[0, max_val], y=[0, max_val], mode="lines",
                                              line=dict(color=COLORES["neutro"], dash="dash"), showlegend=False))
            fig_scatter.update_layout(height=320, xaxis_title="Morosidad Real (%)", yaxis_title="Morosidad Predicha (%)",
                                       paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                       font_color=COLORES["texto"], margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig_scatter, width="stretch")

        st.markdown("---")
        st.markdown("**Proyección de morosidad — próximo mes**")
        if segmento_sel != "Todos":
            st.caption(f"Filtrado por **{segmento_sel}** (Filtro Global de Segmento, sidebar).")

        proyeccion = proyectar_proximo_mes(resultado_mora["modelo"], df_ind, segmento_sel)
        if not proyeccion.empty:
            st.dataframe(
                proyeccion.head(30).rename(columns={
                    "cooperativa": "Cooperativa", "segmento": "Segmento",
                    "mora_actual_pct": "Mora Actual (%)", "mora_proyectada_pct": "Mora Proyectada (%)",
                    "variacion_pp": "Variación (pp)",
                }).round(2),
                width="stretch", height=420,
            )
            st.caption("Ordenado por mayor deterioro proyectado (variación en puntos porcentuales).")
        else:
            st.info("Sin datos suficientes para esta selección.")


if __name__ == "__main__":
    main()
