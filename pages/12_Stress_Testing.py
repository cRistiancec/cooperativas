# -*- coding: utf-8 -*-
"""
Módulo 12: Stress Testing / Escenarios
Prueba de resistencia determinística sobre el balance real: shocks de
salida de depósitos y deterioro de morosidad, con impacto resultante en
solvencia y liquidez por institución y a nivel de sistema.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from analytics.financial_engine import ESCENARIOS, aplicar_escenario, construir_panel_balance
from ui import aplicar_tema, render_filtro_segmento, render_sidebar
from utils.charts import COLORES, altura_por_categorias, crear_gauge, truncar_nombres_unicos
from utils.data_loader import cargar_metadata, cargar_ranking_cooperativas

st.set_page_config(
    page_title="Stress Testing | Radar Cooperativo Ecuador",
    page_icon="🧪",
    layout="wide",
)
aplicar_tema()


def main():
    metadata = cargar_metadata()
    render_sidebar(metadata)

    st.title("🧪 Stress Testing / Escenarios")
    st.markdown("Prueba de resistencia sobre el balance real ante shocks de liquidez y deterioro crediticio.")

    st.info(
        "**Metodología simplificada** (no es un modelo regulatorio ICAAP/Basilea): cada escenario "
        "aplica una salida de depósitos y un incremento de morosidad sobre la cartera vigente; la "
        "pérdida crediticia estimada (cartera adicional en mora × una tasa de pérdida aproximada, "
        "tipo LGD) se carga contra patrimonio y activos, y la salida de depósitos se financia con "
        "fondos disponibles. Ver supuestos completos en el expander al final de la página."
    )

    df_ranking = cargar_ranking_cooperativas()

    st.sidebar.markdown("### Filtros")
    # Filtro Global de Segmento (ui/filtros.py) — compartido con toda la plataforma
    segmento_sel = render_filtro_segmento()

    fechas = sorted(df_ranking["fecha"].unique(), reverse=True)
    fecha_sel = st.sidebar.selectbox(
        "Fecha de análisis", fechas, format_func=lambda x: pd.Timestamp(x).strftime("%B %Y").title(),
        index=0, key="fecha_stress",
    )

    escenario_sel = st.selectbox("Escenario", list(ESCENARIOS.keys()), index=0, key="escenario_stress")
    parametros = ESCENARIOS[escenario_sel]

    col_p1, col_p2, col_p3 = st.columns(3)
    with col_p1:
        st.metric("Salida de depósitos", f"{parametros['shock_depositos_pct']:.0f}%")
    with col_p2:
        st.metric("Incremento de morosidad", f"+{parametros['shock_mora_pp']:.1f} pp")
    with col_p3:
        st.metric("Tasa de pérdida (LGD aprox.)", f"{parametros['tasa_perdida_incremental']:.0%}")

    panel = construir_panel_balance(df_ranking, fecha_sel, segmento_sel)
    resultado = aplicar_escenario(panel, escenario_sel)

    activos_total_pre = resultado["activos"].sum()
    activos_total_post = resultado["activos_post"].sum()
    patrimonio_total_pre = resultado["patrimonio"].sum()
    patrimonio_total_post = resultado["patrimonio_post"].sum()
    solvencia_sistema_pre = (patrimonio_total_pre / activos_total_pre * 100) if activos_total_pre > 0 else 0
    solvencia_sistema_post = (patrimonio_total_post / activos_total_post * 100) if activos_total_post > 0 else 0

    instituciones_brecha_liq = int(resultado["brecha_liquidez"].sum())
    instituciones_capital_insuf = int(resultado["capital_insuficiente"].sum())

    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Solvencia del sistema (antes)", f"{solvencia_sistema_pre:.1f}%")
    with col2:
        delta_solv = solvencia_sistema_post - solvencia_sistema_pre
        st.metric("Solvencia del sistema (después)", f"{solvencia_sistema_post:.1f}%", f"{delta_solv:+.1f} pp")
    with col3:
        st.metric("Instituciones con brecha de liquidez", instituciones_brecha_liq)
    with col4:
        st.metric("Instituciones con capital insuficiente", instituciones_capital_insuf)

    st.markdown("---")

    tab1, tab2, tab3 = st.tabs(["📊 Impacto en el Sistema", "🏆 Instituciones Más Afectadas", "📋 Detalle por Cooperativa"])

    with tab1:
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.plotly_chart(
                crear_gauge(max(solvencia_sistema_post, 0), titulo="Solvencia del Sistema Post-Shock (%)", rango=(0, 20)),
                width="stretch", config={"displayModeBar": False},
            )
        with col_g2:
            perdida_total_m = resultado["perdida_credito"].sum() / 1_000_000
            salida_total_m = resultado["salida_efectivo"].sum() / 1_000_000
            fig = go.Figure(go.Bar(
                x=["Pérdida crediticia estimada", "Salida de depósitos"],
                y=[perdida_total_m, salida_total_m],
                marker_color=[COLORES["error"], COLORES["advertencia"]],
                text=[f"${perdida_total_m:,.0f}M", f"${salida_total_m:,.0f}M"], textposition="outside",
            ))
            fig.update_layout(height=300, title="Impacto agregado (USD Millones)",
                               paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                               font_color=COLORES["texto"], margin=dict(l=10, r=10, t=40, b=10))
            st.plotly_chart(fig, width="stretch")

    with tab2:
        df_afectadas = resultado.nsmallest(20, "solvencia_post")[
            ["cooperativa", "segmento", "solvencia_pre", "solvencia_post", "liquidez_post"]
        ].copy()
        nombres_afectadas = [str(c) for c in df_afectadas["cooperativa"]]
        etiquetas_afectadas = truncar_nombres_unicos(nombres_afectadas)
        fig = go.Figure()
        fig.add_trace(go.Bar(name="Solvencia antes", y=etiquetas_afectadas, x=df_afectadas["solvencia_pre"],
                              orientation="h", marker_color=COLORES["neutro"], customdata=nombres_afectadas,
                              hovertemplate="<b>%{customdata}</b><br>Solvencia antes: %{x:.1f}%<extra></extra>"))
        fig.add_trace(go.Bar(name="Solvencia después", y=etiquetas_afectadas, x=df_afectadas["solvencia_post"],
                              orientation="h", marker_color=COLORES["error"], customdata=nombres_afectadas,
                              hovertemplate="<b>%{customdata}</b><br>Solvencia después: %{x:.1f}%<extra></extra>"))
        fig.update_layout(barmode="group",
                           height=altura_por_categorias(len(df_afectadas), px_por_categoria=32, minimo=420),
                           title="Top 20 instituciones con menor solvencia post-shock",
                           paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color=COLORES["texto"],
                           legend=dict(orientation="h", y=-0.1, x=0.5, xanchor="center"),
                           yaxis=dict(tickfont=dict(size=10), automargin=True),
                           margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig, width="stretch")

    with tab3:
        df_detalle = resultado[[
            "cooperativa", "segmento", "activos", "patrimonio", "solvencia_pre", "solvencia_post",
            "liquidez_pre", "liquidez_post", "brecha_liquidez", "capital_insuficiente",
        ]].copy().sort_values("solvencia_post")
        df_detalle["activos"] = (df_detalle["activos"] / 1_000_000).round(1)
        df_detalle[["solvencia_pre", "solvencia_post", "liquidez_pre", "liquidez_post"]] = df_detalle[
            ["solvencia_pre", "solvencia_post", "liquidez_pre", "liquidez_post"]
        ].round(1)
        st.dataframe(
            df_detalle.rename(columns={
                "cooperativa": "Cooperativa", "segmento": "Segmento", "activos": "Activos (USD M)",
                "patrimonio": "Patrimonio", "solvencia_pre": "Solvencia Pre (%)", "solvencia_post": "Solvencia Post (%)",
                "liquidez_pre": "Liquidez Pre (%)", "liquidez_post": "Liquidez Post (%)",
                "brecha_liquidez": "Brecha Liquidez", "capital_insuficiente": "Capital Insuficiente",
            }),
            width="stretch", height=420,
        )

    st.markdown("---")
    with st.expander("ℹ️ Supuestos del escenario"):
        st.markdown(
            """
            - **Salida de depósitos**: se resta directamente de Fondos Disponibles (se asume que la
              institución paga la salida con efectivo/caja disponible, sin recurrir a venta de activos
              o líneas de liquidez de contingencia).
            - **Pérdida crediticia**: `Cartera × incremento de morosidad (pp) × tasa de pérdida (LGD
              aproximada)`. Se carga contra Patrimonio y Activos simultáneamente para mantener la
              identidad contable Activos = Pasivos + Patrimonio.
            - **No incluye**: efectos de segunda ronda (contagio entre instituciones), costo de
              fondeo de contingencia, ni venta forzada de inversiones a descuento.
            - Los parámetros de cada escenario son ajustables en `analytics/stress_testing.py`.
            """
        )

    with st.expander("⚠️ Advertencia metodológica: lectura correcta del ratio de solvencia post-shock"):
        st.markdown(
            """
            Cuando la salida de depósitos es grande frente a la pérdida crediticia, la **razón**
            Patrimonio/Activos puede subir levemente, porque al pagar la salida con caja el
            denominador (Activos) se contrae más rápido que el numerador (Patrimonio). **Esto no
            significa que la institución quedó mejor capitalizada** — el Patrimonio en dólares
            absolutos siempre cae con la pérdida crediticia (ver columna "Patrimonio" en el detalle).
            Es una limitación conocida de los ratios de solvencia no ponderados por riesgo (la misma
            crítica que reciben los ratios de apalancamiento simples tipo Basilea). Por eso esta
            página siempre muestra el ratio **junto con** el impacto en dólares — nunca uno sin el otro.
            """
        )


if __name__ == "__main__":
    main()
