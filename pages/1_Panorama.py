# -*- coding: utf-8 -*-
"""
Módulo 1: Panorama del Sistema Cooperativo
Visión general del sistema cooperativo ecuatoriano.
Optimizado para carga rápida usando datos pre-agregados.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))

from utils.data_loader import (
    obtener_fechas_disponibles_rapido,
    obtener_metricas_kpi,
    obtener_ranking_rapido,
    obtener_datos_treemap_rapido,
    obtener_datos_treemap_pasivos_rapido,
    obtener_crecimiento_anual,
    cargar_entidades,
    cargar_indicadores,
    cargar_ranking_cooperativas,
)
from analytics.financial_engine import reporte_calidad_fecha
from utils.charts import (
    render_kpi_card,
    crear_ranking_barras,
    crear_treemap,
    altura_por_categorias,
    truncar_nombres_unicos,
    COLORES,
)
from config.indicator_mapping import CODIGOS_BALANCE
from ui import aplicar_tema, render_filtro_segmento, render_sidebar
from utils.data_loader import cargar_metadata

# =============================================================================
# FUNCIONES CACHEADAS DE GRAFICOS
# =============================================================================

@st.cache_data(ttl=3600)
def _crear_treemap_cached(df_tree, altura=500):
    """Cachea la creación del treemap para evitar reconstruirlo."""
    return crear_treemap(df_tree, jerarquico=True, altura=altura)


@st.cache_data(ttl=3600)
def _crear_ranking_cached(ranking, x_col, y_col, formato_valor, altura):
    """Cachea la creación del gráfico de ranking."""
    fig = crear_ranking_barras(ranking, x_col=x_col, y_col=y_col, formato_valor=formato_valor)
    fig.update_layout(height=altura)
    return fig


@st.cache_data(ttl=3600)
def _crear_crecimiento_cached(df_crec, titulo):
    """Cachea la creación del gráfico de crecimiento."""
    nombres_completos = [str(c) for c in df_crec['cooperativa']]

    fig = go.Figure(go.Bar(
        x=df_crec['crecimiento'],
        y=truncar_nombres_unicos(nombres_completos),
        orientation='h',
        marker=dict(
            color=df_crec['crecimiento'],
            colorscale='RdYlGn',
            cmin=-10,
            cmax=30,
        ),
        text=df_crec['crecimiento'].apply(lambda x: f"{x:.1f}%"),
        textposition='outside',
        cliponaxis=False,
        customdata=nombres_completos,
        hovertemplate="<b>%{customdata}</b><br>Crecimiento: %{x:.1f}%<extra></extra>",
    ))

    fig.update_layout(
        title=titulo,
        height=altura_por_categorias(len(df_crec)),
        xaxis_title="Crecimiento (%)",
        yaxis_title="",
        yaxis=dict(tickfont=dict(size=10), automargin=True),
        showlegend=False,
        margin=dict(l=10, r=60, t=40, b=10)
    )
    fig.add_vline(x=0, line_dash="dash", line_color="gray", line_width=1)

    return fig


# =============================================================================
# CONFIGURACION
# =============================================================================

st.set_page_config(
    page_title="Panorama | Radar Cooperativo Ecuador",
    page_icon="📊",
    layout="wide",
)

aplicar_tema()

# =============================================================================
# PAGINA PRINCIPAL
# =============================================================================

def main():
    render_sidebar(cargar_metadata())

    st.title("📊 Panorama del Sistema Cooperativo")
    st.markdown("Visión general del sistema cooperativo de ahorro y crédito del Ecuador.")

    # Verificar datos pre-agregados
    fechas = obtener_fechas_disponibles_rapido()
    if not fechas:
        st.error("No se encontraron datos pre-agregados.")
        st.info("Ejecuta: `python scripts/generar_agregados.py`")
        return

    # Sidebar - Filtros
    st.sidebar.markdown("### Filtros")

    # Filtro Global de Segmento (ui/filtros.py) — compartido con toda la plataforma
    segmento_seleccionado = render_filtro_segmento()

    # Selector de fecha
    fecha_seleccionada = st.sidebar.selectbox(
        "Fecha de análisis",
        options=fechas,
        format_func=lambda x: pd.Timestamp(x).strftime('%B %Y').title(),
        index=0,
        key="fecha_panorama"
    )

    # Obtener fecha anterior (12 meses atrás)
    idx_fecha = list(fechas).index(fecha_seleccionada)
    fecha_anterior = fechas[idx_fecha + 12] if idx_fecha + 12 < len(fechas) else None

    # ==========================================================================
    # SECCION 1: KPIs PRINCIPALES (OPTIMIZADO)
    # ==========================================================================

    st.markdown("### Indicadores del Sistema")

    # Obtener métricas actuales (usando datos pre-agregados)
    metricas = obtener_metricas_kpi(fecha_seleccionada, segmento_seleccionado)

    # Calcular deltas si hay fecha anterior
    deltas = {}
    if fecha_anterior:
        metricas_ant = obtener_metricas_kpi(fecha_anterior, segmento_seleccionado)
        for key in ['total_activos', 'total_cartera', 'total_depositos', 'total_patrimonio']:
            if metricas_ant.get(key, 0) > 0:
                deltas[key] = ((metricas.get(key, 0) - metricas_ant[key]) / metricas_ant[key]) * 100

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        render_kpi_card(
            f"${metricas.get('total_activos', 0):,.0f}M",
            "Total Activos",
            delta=deltas.get('total_activos'),
            delta_label="vs año ant."
        )

    with col2:
        render_kpi_card(
            f"${metricas.get('total_cartera', 0):,.0f}M",
            "Cartera de Créditos",
            delta=deltas.get('total_cartera'),
            delta_label="vs año ant."
        )

    with col3:
        render_kpi_card(
            f"${metricas.get('total_depositos', 0):,.0f}M",
            "Depósitos del Público",
            delta=deltas.get('total_depositos'),
            delta_label="vs año ant."
        )

    with col4:
        render_kpi_card(
            f"${metricas.get('total_patrimonio', 0):,.0f}M",
            "Patrimonio",
            delta=deltas.get('total_patrimonio'),
            delta_label="vs año ant."
        )

    with col5:
        render_kpi_card(
            f"{int(metricas.get('num_cooperativas', 0))}",
            "Cooperativas",
            color=COLORES['acento']
        )

    st.markdown("---")

    # ==========================================================================
    # SECCION 2: MAPA DE MERCADO Y RANKING (OPTIMIZADO)
    # ==========================================================================

    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.markdown("### Mapa de Activos por Cooperativa")
        st.caption("Top 20 cooperativas - Haz clic para ver composición de activos")

        df_tree = obtener_datos_treemap_rapido(fecha_seleccionada, segmento_seleccionado, top_n=20)

        if not df_tree.empty and df_tree['values'].sum() > 0:
            fig_tree = _crear_treemap_cached(df_tree, altura=500)
            st.plotly_chart(fig_tree, width='stretch')
        else:
            st.warning("No hay datos de activos disponibles para esta fecha.")

    with col_right:
        st.markdown("### Ranking por Activos")

        top_n_ranking = st.selectbox(
            "Mostrar",
            options=[20, 30, 0],
            index=0,
            format_func=lambda x: "Todas" if x == 0 else f"Top {x}"
        )

        ranking = obtener_ranking_rapido(
            fecha_seleccionada,
            codigo=CODIGOS_BALANCE['activo_total'],
            top_n=top_n_ranking,
            segmento=segmento_seleccionado
        )

        if not ranking.empty:
            fig_rank = _crear_ranking_cached(
                ranking, x_col='valor_millones', y_col='cooperativa',
                formato_valor="${:,.0f}M", altura=altura_por_categorias(len(ranking))
            )
            st.plotly_chart(fig_rank, width='stretch')

    st.markdown("---")

    # ==========================================================================
    # SECCION 2B: MAPA DE PASIVOS Y PATRIMONIO
    # ==========================================================================

    col_left2, col_right2 = st.columns([2, 1])

    with col_left2:
        st.markdown("### Mapa de Pasivos y Patrimonio por Cooperativa")
        st.caption("Top 20 cooperativas - Haz clic para ver composición de pasivos")

        df_tree_pasivos = obtener_datos_treemap_pasivos_rapido(fecha_seleccionada, segmento_seleccionado, top_n=20)

        if not df_tree_pasivos.empty and df_tree_pasivos['values'].sum() > 0:
            fig_tree_pas = _crear_treemap_cached(df_tree_pasivos, altura=500)
            st.plotly_chart(fig_tree_pas, width='stretch')
        else:
            st.warning("No hay datos de pasivos disponibles para esta fecha.")

    with col_right2:
        st.markdown("### Ranking por Pasivos Totales")
        st.caption("Pasivo total (sin patrimonio)")

        ranking_pasivos = obtener_ranking_rapido(
            fecha_seleccionada,
            codigo=CODIGOS_BALANCE['pasivo_total'],
            top_n=top_n_ranking,
            segmento=segmento_seleccionado
        )

        if not ranking_pasivos.empty:
            fig_rank_pas = _crear_ranking_cached(
                ranking_pasivos, x_col='valor_millones', y_col='cooperativa',
                formato_valor="${:,.0f}M", altura=altura_por_categorias(len(ranking_pasivos))
            )
            st.plotly_chart(fig_rank_pas, width='stretch')

    st.markdown("---")

    # ==========================================================================
    # SECCION 3: CRECIMIENTO ANUAL (OPTIMIZADO)
    # ==========================================================================

    st.markdown("### Crecimiento Anual por Cooperativa")
    fecha_label = pd.Timestamp(fecha_seleccionada).strftime('%B %Y').title()
    st.caption(f"Variación vs mismo mes del año anterior ({fecha_label})")

    col_cartera, col_depositos = st.columns(2)

    with col_cartera:
        st.markdown("**Cartera de Créditos**")

        if fecha_anterior:
            df_crec_cartera = obtener_crecimiento_anual(
                fecha_seleccionada, fecha_anterior,
                codigo=CODIGOS_BALANCE['cartera_creditos'],
                segmento=segmento_seleccionado,
                top_n=20
            )

            if not df_crec_cartera.empty:
                fig_cartera = _crear_crecimiento_cached(df_crec_cartera, "Crecimiento Anual (%)")
                st.plotly_chart(fig_cartera, width='stretch')
            else:
                st.info("Sin datos de crecimiento disponibles.")
        else:
            st.info("No hay datos del año anterior para comparar.")

    with col_depositos:
        st.markdown("**Depósitos del Público**")

        if fecha_anterior:
            df_crec_depositos = obtener_crecimiento_anual(
                fecha_seleccionada, fecha_anterior,
                codigo=CODIGOS_BALANCE['obligaciones_publico'],
                segmento=segmento_seleccionado,
                top_n=20
            )

            if not df_crec_depositos.empty:
                fig_depositos = _crear_crecimiento_cached(df_crec_depositos, "Crecimiento Anual (%)")
                st.plotly_chart(fig_depositos, width='stretch')
            else:
                st.info("Sin datos de crecimiento disponibles.")
        else:
            st.info("No hay datos del año anterior para comparar.")

    st.markdown("---")

    # ==========================================================================
    # SECCION 4: CALIDAD DE DATOS E IDENTIDAD DE ENTIDADES
    # ==========================================================================

    with st.expander("🔍 Calidad de datos e identidad de entidades (para esta fecha)"):
        df_ind, _ = cargar_indicadores()
        df_ranking = cargar_ranking_cooperativas()
        if df_ind.empty or df_ranking.empty:
            st.info("Sin datos suficientes para el reporte de calidad.")
        else:
            reporte = reporte_calidad_fecha(df_ind, df_ranking, fecha_seleccionada)
            if reporte["confiable"]:
                st.success("Sin anomalías de calidad de datos detectadas para esta fecha.")
            else:
                st.warning(
                    "Se detectaron anomalías de calidad de datos — revisar antes de interpretar "
                    "alertas o rankings de esta fecha como señal financiera:"
                )
                for razon in reporte["razones"]:
                    st.markdown(f"- {razon}")
            st.caption(
                "Esta verificación distingue una anomalía de datos (fecha faltante, duplicado, "
                "denominador en cero) de una señal financiera real — ver docs/RIESGO_METODOLOGIA.md."
            )

        st.markdown("##### Identidad de entidades")
        df_entidades = cargar_entidades()
        if df_entidades.empty:
            st.info(
                "Tabla de identidad no generada. Ejecutar `python scripts/generar_entidades.py`."
            )
        else:
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Entidades registradas", len(df_entidades))
            with c2:
                st.metric("Con RUC identificado", int(df_entidades["ruc"].notna().sum()))
            with c3:
                st.metric("Posible salida / liquidación",
                          int((df_entidades["estado"] != "activa").sum()))
            st.dataframe(
                df_entidades[df_entidades["estado"] != "activa"][
                    ["nombre", "segmento_actual", "estado", "fecha_fin_datos", "observaciones"]
                ],
                width="stretch", hide_index=True,
            )
            st.caption(
                "RUC disponible solo para entidades cubiertas por el boletín SEPS de Patrimonio "
                "Técnico (Segmento 1, Mutualistas, FINANCOOP). 'Posible salida' es un PROXY "
                "(cese de reporte) — no confirma la causa (liquidación/fusión/absorción/atraso). "
                "Ver `analytics/eventos.py` y `scripts/generar_entidades.py`."
            )


if __name__ == "__main__":
    main()
