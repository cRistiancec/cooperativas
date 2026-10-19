# -*- coding: utf-8 -*-
"""
Módulo 4: Indicadores CAMEL
Análisis de indicadores financieros del sistema cooperativo ecuatoriano.
Carga indicadores pre-calculados extraídos de las tablas dinámicas de la Superintendencia.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))

from utils.data_loader import (
    datos_filtrados,
    obtener_cooperativas_filtro,
    cargar_metadata,
)
from config.indicator_mapping import (
    GRUPOS_INDICADORES,
    ETIQUETAS_INDICADORES,
    ESCALAS_COLORES_HEATMAP,
    RANGOS_HEATMAP,
)
from utils.charts import (
    altura_por_categorias,
    layout_leyenda_series,
    obtener_color_cooperativa,
    truncar_nombre,
    truncar_nombres_unicos,
)
from ui import (
    aplicar_tema, botones_descarga, exigir_datos, render_filtros_globales, render_resumen_filtro, render_sidebar,
    selector_fecha_corte,
)
from ui.filtros import multiselect_validado

# =============================================================================
# CONFIGURACION
# =============================================================================

st.set_page_config(
    page_title="CAMEL | Radar Cooperativo Ecuador",
    page_icon="📈",
    layout="wide",
)

aplicar_tema()


# =============================================================================
# FUNCIONES DE CONSULTA
# =============================================================================

@st.cache_data
def obtener_ranking_indicador(df, codigo, fecha, top_n=20):
    """Ranking de cooperativas para un indicador en una fecha. `df` ya viene filtrado por la selección global."""
    df_f = df[(df['codigo'] == codigo) & (df['fecha'] == fecha)]
    df_f = df_f.copy()
    df_f['valor_pct'] = df_f['valor'] * 100
    df_f = df_f.sort_values('valor_pct', ascending=False)
    resultado = df_f[['fecha', 'cooperativa', 'entidad', 'segmento', 'procedencia_clasif', 'codigo', 'valor', 'valor_pct']]
    return resultado if top_n == 0 else resultado.head(top_n)


@st.cache_data
def obtener_evolucion_indicador(df, codigo, cooperativas):
    """Serie temporal de un indicador para cooperativas seleccionadas. `df` ya viene filtrado por la selección global."""
    df_f = df[(df['codigo'] == codigo) & (df['cooperativa'].isin(cooperativas))]
    df_f = df_f.copy()
    df_f['valor_pct'] = df_f['valor'] * 100
    return df_f[['fecha', 'cooperativa', 'entidad', 'segmento', 'procedencia_clasif', 'codigo', 'valor_pct']].sort_values(['cooperativa', 'fecha'])


@st.cache_data
def obtener_heatmap_indicador(df, codigo, cooperativas_ordenadas, top_n=15):
    """Datos para heatmap: cooperativas x periodos. `df` ya viene filtrado por la selección global."""
    df_f = df[df['codigo'] == codigo].copy()

    if df_f.empty:
        return pd.DataFrame()

    # Tomar cooperativas ordenadas por activos, agregar las que falten al final
    coops_en_datos = set(df_f['cooperativa'].unique())
    coops_con_orden = [c for c in cooperativas_ordenadas if c in coops_en_datos]
    coops_sin_orden = sorted(coops_en_datos - set(coops_con_orden))
    coops_todas = coops_con_orden + coops_sin_orden
    top_coops = coops_todas if top_n == 0 else coops_todas[:top_n]
    df_f = df_f[df_f['cooperativa'].isin(top_coops)]

    df_f['periodo'] = df_f['fecha'].dt.strftime('%Y-%m')

    heatmap = df_f.pivot_table(
        index='cooperativa', columns='periodo', values='valor', aggfunc='first'
    )

    # Ordenar cooperativas según el orden de activos (invertido: más grande abajo)
    orden = [c for c in top_coops if c in heatmap.index]
    orden.reverse()
    heatmap = heatmap.reindex(orden)

    return heatmap * 100  # ratio -> porcentaje


# =============================================================================
# UTILIDADES
# =============================================================================

# =============================================================================
# PAGINA PRINCIPAL
# =============================================================================

def main():
    render_sidebar(cargar_metadata())

    st.title("📈 Indicadores CAMEL")
    st.markdown("Indicadores financieros oficiales del sistema cooperativo ecuatoriano.")

    # Filtros globales (período ∩ segmentos ∩ entidades ∩ calidad), únicos para toda la plataforma
    filtro = render_filtros_globales()
    fecha_seleccionada = selector_fecha_corte(filtro)
    try:
        df_camel = datos_filtrados("indicadores", filtro)
        metadata = cargar_metadata()
    except FileNotFoundError:
        st.error("No se encontró el archivo de indicadores.")
        st.info("Ejecuta: `python scripts/procesar_camel.py`")
        return

    render_resumen_filtro(filtro, df_camel[df_camel['fecha'] == fecha_seleccionada] if not df_camel.empty else df_camel,
                          corte=pd.Timestamp(metadata['fecha_max']), fecha_analisis=fecha_seleccionada)
    exigir_datos(df_camel)
    fecha_min, fecha_max = pd.Timestamp(filtro.fecha_ini), pd.Timestamp(filtro.fecha_fin)

    # Cooperativas de la selección ordenadas por activos (para ordenar rankings y valores por defecto)
    _con_datos = set(df_camel['cooperativa'].astype(str).unique())
    cooperativas_ordenadas = [c for c in obtener_cooperativas_filtro(filtro) if c in _con_datos]
    if not cooperativas_ordenadas:
        cooperativas_ordenadas = sorted(df_camel['cooperativa'].astype(str).unique())
    cooperativas_default = cooperativas_ordenadas[:4]

    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**Indicadores:** {df_camel['codigo'].nunique()}")
    st.sidebar.markdown(f"**Cooperativas en la selección:** {df_camel['cooperativa'].nunique()}")
    st.sidebar.markdown(f"**Período:** {fecha_min:%Y-%m} - {fecha_max:%Y-%m}")

    # ==========================================================================
    # TABS PRINCIPALES
    # ==========================================================================

    tab1, tab2, tab3 = st.tabs([
        "📊 Ranking por Indicador",
        "📈 Evolución Temporal",
        "🗺️ Heatmap Mensual"
    ])

    # ==========================================================================
    # TAB 1: RANKING POR INDICADOR
    # ==========================================================================

    with tab1:
        col_filtros, col_grafico = st.columns([1, 3])

        with col_filtros:
            categorias = list(GRUPOS_INDICADORES.keys())
            categoria_sel = st.selectbox(
                "Categoría CAMEL",
                categorias,
                index=0,
                key="categoria_rank"
            )

            codigos_cat = GRUPOS_INDICADORES[categoria_sel]
            indicador_opciones = {ETIQUETAS_INDICADORES.get(c, c): c for c in codigos_cat}
            indicador_nombre = st.selectbox(
                "Indicador",
                list(indicador_opciones.keys()),
                key="indicador_rank"
            )
            indicador_codigo = indicador_opciones[indicador_nombre]

            top_n = st.selectbox(
                "Cooperativas a mostrar",
                options=[30, 50, 0],
                index=0,
                format_func=lambda x: "Todas" if x == 0 else f"Top {x}",
                key="top_n_rank"
            )

        with col_grafico:
            df_ranking = obtener_ranking_indicador(
                df_camel, indicador_codigo, fecha_seleccionada, top_n
            )

            if not df_ranking.empty:
                df_ranking_plot = df_ranking.sort_values('valor_pct', ascending=True)

                # Colores por cooperativa
                colores = [obtener_color_cooperativa(coop) for coop in df_ranking_plot['cooperativa']]

                nombres_rank = [str(c) for c in df_ranking_plot['cooperativa']]

                fig = go.Figure(go.Bar(
                    x=df_ranking_plot['valor_pct'],
                    y=truncar_nombres_unicos(nombres_rank),
                    orientation='h',
                    marker=dict(color=colores),
                    text=df_ranking_plot['valor_pct'].apply(lambda x: f"{x:.1f}%"),
                    textposition='outside',
                    cliponaxis=False,
                    customdata=nombres_rank,
                    hovertemplate='<b>%{customdata}</b><br>Valor: %{x:.2f}%<extra></extra>'
                ))

                fig.update_layout(
                    title=f"{indicador_nombre} - {pd.Timestamp(fecha_seleccionada).strftime('%B %Y').title()}",
                    height=altura_por_categorias(len(df_ranking_plot), px_por_categoria=25),
                    xaxis_title='Valor (%)',
                    yaxis_title='',
                    yaxis=dict(tickfont=dict(size=10), automargin=True),
                    showlegend=False,
                    margin=dict(l=10, r=70, t=40, b=40)
                )

                st.plotly_chart(fig, width='stretch')
                with st.expander("Datos del ranking (descarga)"):
                    st.dataframe(df_ranking, width="stretch", hide_index=True)
                    botones_descarga(df_ranking, filtro, f"camel_ranking_{indicador_codigo}_{pd.Timestamp(fecha_seleccionada):%Y%m}",
                                     "Ranking de indicador CAMEL", "dl_camel_rank", corte=fecha_seleccionada)

                # Estadísticas
                col_s1, col_s2, col_s3 = st.columns(3)
                with col_s1:
                    st.metric("Promedio", f"{df_ranking['valor_pct'].mean():.2f}%")
                with col_s2:
                    st.metric("Máximo", f"{df_ranking['valor_pct'].max():.2f}%")
                with col_s3:
                    st.metric("Mínimo", f"{df_ranking['valor_pct'].min():.2f}%")
            else:
                st.warning("No hay datos disponibles para este indicador.")

    # ==========================================================================
    # TAB 2: EVOLUCION TEMPORAL
    # ==========================================================================

    with tab2:
        col_filtros2, col_grafico2 = st.columns([1, 3])

        with col_filtros2:
            categoria_evol = st.selectbox(
                "Categoría CAMEL",
                list(GRUPOS_INDICADORES.keys()),
                index=0,
                key="categoria_evol"
            )

            codigos_evol = GRUPOS_INDICADORES[categoria_evol]
            indicador_opciones_evol = {ETIQUETAS_INDICADORES.get(c, c): c for c in codigos_evol}
            indicador_nombre_evol = st.selectbox(
                "Indicador",
                list(indicador_opciones_evol.keys()),
                key="indicador_evol"
            )
            indicador_codigo_evol = indicador_opciones_evol[indicador_nombre_evol]

            cooperativas_evol = multiselect_validado(
                "Cooperativas a comparar",
                cooperativas_ordenadas,
                default=cooperativas_default,
                max_selections=8,
                key="cooperativas_evol"
            )

            st.caption(f"Período: {fecha_min:%m/%Y} – {fecha_max:%m/%Y} (filtro global)")

        with col_grafico2:
            if not cooperativas_evol:
                st.info("Selecciona al menos una cooperativa para ver la evolución.")
            else:
                df_serie = obtener_evolucion_indicador(df_camel, indicador_codigo_evol, cooperativas_evol)

                if not df_serie.empty:
                    color_map = {coop: obtener_color_cooperativa(coop) for coop in cooperativas_evol}

                    fig_evol = px.line(
                        df_serie,
                        x='fecha',
                        y='valor_pct',
                        color='cooperativa',
                        title=f"Evolución: {indicador_nombre_evol}",
                        labels={'fecha': 'Fecha', 'valor_pct': 'Valor (%)', 'cooperativa': 'Cooperativa'},
                        color_discrete_map=color_map,
                    )

                    # Los nombres completos de las cooperativas desbordaban la
                    # leyenda horizontal y se superponían entre sí. Se muestran
                    # truncados de forma consistente con el resto de módulos; el
                    # nombre completo se conserva en el tooltip de cada punto.
                    for trazo in fig_evol.data:
                        trazo.hovertemplate = (
                            f'<b>{trazo.name}</b><br>Fecha: %{{x|%b %Y}}<br>Valor: %{{y:.2f}}%<extra></extra>'
                        )
                        trazo.name = truncar_nombre(trazo.name)

                    fig_evol.update_layout(
                        height=450,
                        hovermode='x unified',
                        **layout_leyenda_series(len(fig_evol.data)),
                    )

                    st.plotly_chart(fig_evol, width='stretch')
                    with st.expander("Datos de la evolución (descarga)"):
                        st.dataframe(df_serie, width="stretch", hide_index=True)
                        botones_descarga(df_serie, filtro, f"camel_evolucion_{indicador_codigo_evol}", "Evolución de indicador CAMEL",
                                         "dl_camel_evol", corte=fecha_seleccionada)
                else:
                    st.warning("No hay datos disponibles para las cooperativas seleccionadas.")

    # ==========================================================================
    # TAB 3: HEATMAP MENSUAL
    # ==========================================================================

    with tab3:
        col_filtros3, col_grafico3 = st.columns([1, 3])

        with col_filtros3:
            categoria_heat = st.selectbox(
                "Categoría CAMEL",
                list(GRUPOS_INDICADORES.keys()),
                index=0,
                key="categoria_heat"
            )

            codigos_heat = GRUPOS_INDICADORES[categoria_heat]
            indicador_opciones_heat = {ETIQUETAS_INDICADORES.get(c, c): c for c in codigos_heat}
            indicador_nombre_heat = st.selectbox(
                "Indicador",
                list(indicador_opciones_heat.keys()),
                key="indicador_heat"
            )
            indicador_codigo_heat = indicador_opciones_heat[indicador_nombre_heat]

            top_n_heat = st.selectbox(
                "Cooperativas a mostrar",
                options=[30, 50, 0],
                index=0,
                format_func=lambda x: "Todas" if x == 0 else f"Top {x}",
                key="top_n_heat"
            )

            st.caption(f"Período: {fecha_min:%m/%Y} – {fecha_max:%m/%Y} (filtro global)")

        with col_grafico3:
            heatmap_data = obtener_heatmap_indicador(
                df_camel, indicador_codigo_heat, cooperativas_ordenadas, top_n_heat
            )

            if not heatmap_data.empty:
                # Escala de colores
                colorscale = ESCALAS_COLORES_HEATMAP.get(indicador_codigo_heat, 'RdYlGn')

                # Rangos
                rango = RANGOS_HEATMAP.get(indicador_codigo_heat)
                zmin = rango[0] if rango else None
                zmax = rango[1] if rango else None

                # Truncar nombres largos (mantener final para diferenciar)
                y_labels = truncar_nombres_unicos([str(n) for n in heatmap_data.index])

                fig_heat = go.Figure(data=go.Heatmap(
                    z=heatmap_data.values,
                    x=heatmap_data.columns,
                    y=y_labels,
                    colorscale=colorscale,
                    zmin=zmin,
                    zmax=zmax,
                    hovertemplate='Cooperativa: %{y}<br>Período: %{x}<br>Valor: %{z:.2f}%<extra></extra>',
                    colorbar=dict(title='Valor (%)')
                ))

                fig_heat.update_layout(
                    title=f"Evolución Mensual: {indicador_nombre_heat}",
                    height=altura_por_categorias(len(heatmap_data), px_por_categoria=28),
                    xaxis_title='Período',
                    yaxis_title='',
                    xaxis={'tickangle': -45, 'automargin': True},
                    yaxis={'tickfont': {'size': 10}, 'automargin': True},
                    margin=dict(l=10, r=10, t=40, b=80)
                )

                st.plotly_chart(fig_heat, width='stretch')
                _hm = heatmap_data.reset_index().melt(id_vars='cooperativa', var_name='periodo', value_name='valor_pct').dropna(subset=['valor_pct'])
                _hm['fecha'] = pd.to_datetime(_hm['periodo'] + '-01') + pd.offsets.MonthEnd(0)
                _hm = _hm.merge(df_camel[df_camel['codigo'] == indicador_codigo_heat][['cooperativa', 'fecha', 'entidad', 'segmento', 'procedencia_clasif']],
                                on=['cooperativa', 'fecha'], how='left')
                with st.expander("Datos del heatmap (descarga)"):
                    st.dataframe(_hm, width="stretch", hide_index=True)
                    botones_descarga(_hm, filtro, f"camel_heatmap_{indicador_codigo_heat}", "Heatmap de indicador CAMEL",
                                     "dl_camel_heat", corte=fecha_seleccionada)
            else:
                st.warning("No hay datos suficientes para el heatmap.")


if __name__ == "__main__":
    main()
