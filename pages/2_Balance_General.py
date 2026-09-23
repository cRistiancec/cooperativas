# -*- coding: utf-8 -*-
"""
Módulo 2: Balance General
Análisis temporal de las cuentas de balance del sistema cooperativo.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))

from utils.data_loader import (
    cargar_catalogo_cuentas_balance,
    cargar_balance_por_codigos,
    obtener_ranking_rapido,
    cargar_metadata,
)
from analytics.financial_engine import calcular_crecimiento_yoy_mensual
from utils.charts import (
    altura_por_categorias,
    layout_leyenda_series,
    truncar_nombre,
    truncar_nombres_unicos,
)
from config.indicator_mapping import obtener_color_cooperativa
from config.constants import MESES
from ui import aplicar_tema, render_filtro_segmento, render_sidebar

# =============================================================================
# CONFIGURACION
# =============================================================================

st.set_page_config(
    page_title="Balance General | Radar Cooperativo Ecuador",
    page_icon="⚖️",
    layout="wide",
)

aplicar_tema()

# =============================================================================
# FUNCIONES CACHEADAS DE GRAFICOS
# =============================================================================

@st.cache_data(ttl=3600)
def _crear_evolucion_cached(series_data, titulo, y_title, incluir_sistema_data=None):
    """Cachea la creación del gráfico de evolución comparativa."""
    fig = go.Figure()

    for nombre, datos in series_data.items():
        if nombre == "__SISTEMA__":
            continue
        fig.add_trace(go.Scatter(
            x=datos['fechas'],
            y=datos['valores'],
            name=datos['nombre_corto'],
            mode='lines',
            line=dict(width=2, color=datos['color']),
            hovertemplate=f'<b>{nombre}</b><br>Fecha: %{{x|%b %Y}}<br>Valor: %{{y:,.1f}}<extra></extra>'
        ))

    if incluir_sistema_data is not None:
        fig.add_trace(go.Scatter(
            x=incluir_sistema_data['fechas'],
            y=incluir_sistema_data['valores'],
            name="SISTEMA",
            mode='lines',
            line=dict(width=3, color='black', dash='dash'),
        ))

    # Leyenda escalada al número de series comparadas: con 10 cooperativas y
    # una leyenda horizontal de margen fijo, las entradas se envolvían en
    # varias filas y se superponían con el título del eje X.
    n_series = len([n for n in series_data if n != "__SISTEMA__"]) + (1 if incluir_sistema_data is not None else 0)

    fig.update_layout(
        title=titulo,
        height=450,
        xaxis_title="Fecha",
        yaxis_title=y_title,
        hovermode="x unified",
        **layout_leyenda_series(n_series),
    )

    return fig


@st.cache_data(ttl=3600)
def _crear_heatmap_cached(z_values, x_labels, y_labels, titulo, altura):
    """Cachea la creación del heatmap de variación YoY."""
    colorscale_divergente = [
        [0.0, 'rgb(165, 0, 38)'],
        [0.25, 'rgb(215, 48, 39)'],
        [0.4, 'rgb(244, 109, 67)'],
        [0.5, 'rgb(255, 255, 255)'],
        [0.6, 'rgb(166, 217, 106)'],
        [0.75, 'rgb(102, 189, 99)'],
        [1.0, 'rgb(0, 104, 55)'],
    ]

    fig = go.Figure(data=go.Heatmap(
        z=z_values,
        x=x_labels,
        y=y_labels,
        colorscale=colorscale_divergente,
        zmid=0,
        zmin=-30,
        zmax=30,
        hovertemplate='Cooperativa: %{y}<br>Período: %{x}<br>Variación YoY: %{z:.1f}%<extra></extra>',
        colorbar=dict(title="Variación %", ticksuffix="%")
    ))

    fig.update_layout(
        title=titulo,
        height=altura,
        xaxis_title="Período",
        yaxis_title="",
        xaxis=dict(tickangle=-45, tickfont=dict(size=9), automargin=True),
        yaxis=dict(tickfont=dict(size=10), automargin=True),
        margin=dict(l=10, r=10, t=40, b=80)
    )

    return fig


@st.cache_data(ttl=3600)
def _crear_ranking_cached(cooperativas, valores, colores, titulo, altura):
    """Cachea la creación del gráfico de ranking."""
    # Etiquetas truncadas de forma consistente con el resto de la plataforma
    # (`truncar_nombres_unicos` garantiza que dos cooperativas no colapsen en
    # la misma categoría) y nombre completo preservado en el tooltip.
    etiquetas = truncar_nombres_unicos([str(c) for c in cooperativas])

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=etiquetas,
        x=valores,
        orientation='h',
        marker=dict(color=colores),
        text=[f"${v:,.0f}M" for v in valores],
        textposition='outside',
        cliponaxis=False,
        customdata=[str(c) for c in cooperativas],
        hovertemplate='Cooperativa: %{customdata}<br>Valor: $%{x:,.0f}M<extra></extra>'
    ))

    fig.update_layout(
        title=titulo,
        height=altura,
        xaxis_title="Valor (Millones USD)",
        yaxis_title="",
        showlegend=False,
        margin=dict(l=10, r=70, t=40, b=10),
        yaxis=dict(autorange="reversed", tickfont=dict(size=10), automargin=True)
    )

    return fig


@st.cache_data(ttl=3600)
def _obtener_series_batch(df_evol_hash, cooperativas, codigo, modo_viz, serie_sistema_hash=None):
    """Obtiene series temporales para múltiples cooperativas de forma batch."""
    series_data = {}

    # Reconstruir desde hash (el df viene cacheado por streamlit)
    for cooperativa in cooperativas:
        df_filtrado = df_evol_hash[(df_evol_hash['cooperativa'] == cooperativa) & (df_evol_hash['codigo'] == codigo)]
        df_filtrado = df_filtrado.sort_values('fecha')

        if df_filtrado.empty:
            continue

        valor_millones = df_filtrado['valor'].values / 1_000_000
        fechas = df_filtrado['fecha'].tolist()

        if modo_viz == "Indexado (Base 100)":
            base = valor_millones[0]
            y_values = (valor_millones / base * 100).tolist() if base > 0 else valor_millones.tolist()
        elif modo_viz == "Participación %" and serie_sistema_hash is not None:
            merged = df_filtrado.merge(serie_sistema_hash[['fecha', 'valor_millones']], on='fecha')
            y_values = (merged['valor'].values / 1_000_000 / merged['valor_millones'].values * 100).tolist()
            fechas = merged['fecha'].tolist()
        else:
            y_values = valor_millones.tolist()

        color_coop = obtener_color_cooperativa(cooperativa)
        nombre_corto = truncar_nombre(cooperativa)

        series_data[cooperativa] = {
            'fechas': fechas,
            'valores': y_values,
            'color': color_coop,
            'nombre_corto': nombre_corto,
        }

    return series_data


# =============================================================================
# FUNCIONES DE DATOS
# =============================================================================

@st.cache_data(ttl=3600)
def obtener_jerarquia_cuentas(df: pd.DataFrame) -> dict:
    """Construye un diccionario jerárquico de cuentas."""
    cuentas = df[['codigo', 'cuenta']].drop_duplicates()
    cuentas = cuentas[cuentas['codigo'].str.match(r'^[0-9]+$', na=False)]

    # Separar por nivel usando longitud del código
    code_len = cuentas['codigo'].str.len()
    n1 = cuentas[code_len == 1]
    n2 = cuentas[code_len == 2]
    n3 = cuentas[code_len == 4]
    n4 = cuentas[code_len == 6]

    # Nivel 1
    codigos_validos = {'1', '2', '3', '4', '5', '6', '7'}
    jerarquia = {
        row.codigo: {'nombre': row.cuenta, 'subcuentas': {}}
        for row in n1.itertuples(index=False)
        if row.codigo in codigos_validos
    }

    # Nivel 2: mapear a su padre de 1 dígito
    for row in n2.itertuples(index=False):
        parent = row.codigo[0]
        if parent in jerarquia:
            jerarquia[parent]['subcuentas'][row.codigo] = {
                'nombre': row.cuenta, 'subcuentas': {}
            }

    # Nivel 3: mapear a padre de 2 dígitos
    for row in n3.itertuples(index=False):
        p1, p2 = row.codigo[0], row.codigo[:2]
        if p1 in jerarquia and p2 in jerarquia[p1]['subcuentas']:
            jerarquia[p1]['subcuentas'][p2]['subcuentas'][row.codigo] = {
                'nombre': row.cuenta, 'subcuentas': {}
            }

    # Nivel 4: mapear a padre de 4 dígitos
    for row in n4.itertuples(index=False):
        p1, p2, p4 = row.codigo[0], row.codigo[:2], row.codigo[:4]
        if (p1 in jerarquia and p2 in jerarquia[p1]['subcuentas'] and
            p4 in jerarquia[p1]['subcuentas'][p2]['subcuentas']):
            jerarquia[p1]['subcuentas'][p2]['subcuentas'][p4]['subcuentas'][row.codigo] = row.cuenta

    return jerarquia


@st.cache_data
def obtener_serie_cooperativa(df: pd.DataFrame, cooperativa: str, codigo: str) -> pd.DataFrame:
    """Obtiene serie temporal de una cooperativa para una cuenta específica."""
    df_filtrado = df[(df['cooperativa'] == cooperativa) & (df['codigo'] == codigo)].copy()
    df_filtrado = df_filtrado.sort_values('fecha')
    df_filtrado['valor_millones'] = df_filtrado['valor'] / 1_000_000
    return df_filtrado[['fecha', 'valor', 'valor_millones']]


@st.cache_data
def _serie_sistema_balance(df: pd.DataFrame, codigo: str, segmento: str = "Todos") -> pd.DataFrame:
    """
    Serie temporal agregada del sistema calculada sobre el DataFrame de balance
    ya cargado en la página.

    No se sustituye por `utils.data_loader.obtener_serie_sistema` (que lee los
    agregados) porque esta página permite seleccionar cuentas de nivel 3 y 4
    (1563 cuentas contables) y los agregados solo contienen 9 códigos de nivel
    1-2. Se renombró con prefijo `_` para dejar explícito que es la variante
    local sobre el balance completo, y no una duplicación de la otra.
    """
    df_filtrado = df[df['codigo'] == codigo].copy()
    if segmento != "Todos":
        df_filtrado = df_filtrado[df_filtrado['segmento'] == segmento]
    serie = df_filtrado.groupby('fecha')['valor'].sum().reset_index()
    serie['valor_millones'] = serie['valor'] / 1_000_000
    serie = serie.sort_values('fecha')
    return serie


@st.cache_data
def obtener_datos_heatmap_mensual(df_completo: pd.DataFrame, codigo: str, cooperativas: list = None,
                                   fecha_inicio: pd.Timestamp = None, fecha_fin: pd.Timestamp = None,
                                   segmento: str = "Todos") -> pd.DataFrame:
    """Prepara datos para heatmap de crecimiento YoY mensual por cooperativa."""
    # El cálculo de crecimiento YoY mes a mes está centralizado en
    # analytics/crecimiento.py::calcular_crecimiento_yoy_mensual() desde el
    # 14-sep-2026 (hardening) — antes se reimplementaba aquí. Misma fórmula,
    # mismo resultado (verificado por CrecimientoYoYMensualTests).
    df_filtrado = calcular_crecimiento_yoy_mensual(df_completo, codigo, segmento=segmento, cooperativas=cooperativas)

    if df_filtrado.empty:
        return pd.DataFrame()

    df_filtrado['valor_millones'] = df_filtrado['valor'] / 1_000_000
    df_filtrado['fecha_str'] = df_filtrado['fecha'].dt.strftime('%Y-%m')

    # Filtrar por rango de fechas
    if fecha_inicio is not None:
        df_filtrado = df_filtrado[df_filtrado['fecha'] >= fecha_inicio]
    if fecha_fin is not None:
        df_filtrado = df_filtrado[df_filtrado['fecha'] <= fecha_fin]

    if df_filtrado.empty:
        return pd.DataFrame()

    # Pivotar
    heatmap_data = df_filtrado.pivot_table(
        index='cooperativa',
        columns='fecha_str',
        values='crecimiento_yoy',
        aggfunc='first',
        observed=True
    )

    # Ordenar cooperativas por valor del último período
    ultima_fecha = df_filtrado['fecha'].max()
    valores_ultima_fecha = df_filtrado[df_filtrado['fecha'] == ultima_fecha].set_index('cooperativa')['valor_millones']
    orden_cooperativas = valores_ultima_fecha.sort_values(ascending=True).index
    heatmap_data = heatmap_data.reindex(orden_cooperativas)

    return heatmap_data


@st.cache_data
def obtener_valores_cooperativas_mes(df: pd.DataFrame, codigo: str, fecha: pd.Timestamp,
                                      segmento: str = "Todos") -> pd.DataFrame:
    """Obtiene valores de todas las cooperativas para una cuenta y mes específicos."""
    df_filtrado = df[
        (df['codigo'] == codigo) &
        (df['fecha'].dt.year == fecha.year) &
        (df['fecha'].dt.month == fecha.month)
    ].copy()

    if segmento != "Todos":
        df_filtrado = df_filtrado[df_filtrado['segmento'] == segmento]

    if df_filtrado.empty:
        return pd.DataFrame()

    df_filtrado['valor_millones'] = df_filtrado['valor'] / 1_000_000

    df_filtrado = df_filtrado[
        (df_filtrado['valor_millones'].notna()) &
        (df_filtrado['valor_millones'] > 0)
    ]

    if df_filtrado.empty:
        return pd.DataFrame()

    resultado = df_filtrado.groupby('cooperativa', as_index=False, observed=True).agg({
        'valor_millones': 'first',
        'segmento': 'first'
    })

    resultado = resultado.sort_values('valor_millones', ascending=False)

    return resultado


# =============================================================================
# PAGINA PRINCIPAL
# =============================================================================

def main():
    render_sidebar(cargar_metadata())

    st.title("📊 Balance General")
    st.markdown("Análisis temporal del sistema cooperativo ecuatoriano.")

    # CSS para selectbox
    st.markdown("""
        <style>
        div[data-baseweb="select"] > div {
            max-width: none !important;
        }
        div[data-baseweb="select"] span {
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: clip !important;
        }
        </style>
    """, unsafe_allow_html=True)

    # Catálogo liviano de cuentas (codigo/cuenta) para poblar los selectores.
    # El balance completo (24M filas, ~1 GB en memoria) NO se carga aquí: se
    # excedía el límite de ~1 GB RAM de Streamlit Cloud y hacía caer la app
    # al abrir esta página. Cada sección más abajo carga solo la cuenta que
    # el usuario selecciona, vía `cargar_balance_por_codigos` (pushdown).
    try:
        catalogo_cuentas = cargar_catalogo_cuentas_balance()
        metadata = cargar_metadata()
    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
        st.info("Ejecuta primero el script de procesamiento: `python scripts/procesar_balance_cooperativas.py`")
        return

    # Lista de cooperativas y fechas — usar funciones rápidas pre-agregadas
    from utils.data_loader import obtener_cooperativas_por_segmento
    cooperativas = obtener_cooperativas_por_segmento("Todos")

    # Rango de fechas disponibles
    fecha_min = pd.Timestamp(metadata['fecha_min'])
    fecha_max = pd.Timestamp(metadata['fecha_max'])

    # ==========================================================================
    # SIDEBAR
    # ==========================================================================

    st.sidebar.markdown("### Filtros Globales")

    # Filtro Global de Segmento (ui/filtros.py) — compartido con toda la plataforma
    segmento_global = render_filtro_segmento()

    st.sidebar.markdown("---")
    st.sidebar.markdown("### Información")
    st.sidebar.markdown(f"**Datos disponibles:** {fecha_min.strftime('%b %Y')} - {fecha_max.strftime('%b %Y')}")
    st.sidebar.markdown(f"**Cooperativas:** {len(cooperativas)}")

    # Obtener top cooperativas para defaults — usar pre-agregados (rápido)
    df_ranking_default = obtener_ranking_rapido(
        fecha_max, '1', top_n=5,
        segmento=segmento_global if segmento_global != "Todos" else "Todos"
    )
    top_cooperativas_default = df_ranking_default['cooperativa'].tolist() if not df_ranking_default.empty else []

    # ==========================================================================
    # SECCION 1: EVOLUCION COMPARATIVA
    # ==========================================================================

    st.markdown("---")
    st.markdown("### 1. Evolución Comparativa")
    st.caption("Compara la evolución temporal de múltiples cooperativas")

    # Obtener jerarquía de cuentas
    jerarquia = obtener_jerarquia_cuentas(catalogo_cuentas)

    # Filtros de cuenta
    st.markdown("**Seleccionar Cuenta:**")
    opciones_nivel1 = {f"{k} - {v['nombre']}": k for k, v in jerarquia.items()}

    col_n1, col_n2, col_n3, col_n4 = st.columns(4)

    with col_n1:
        nivel1_label = st.selectbox(
            "Categoría",
            options=list(opciones_nivel1.keys()),
            index=0,
            key="cuenta_nivel1"
        )
        codigo_nivel1 = opciones_nivel1[nivel1_label]

    # Nivel 2
    subcuentas_nivel2 = jerarquia[codigo_nivel1]['subcuentas']
    opciones_nivel2 = {"Todas (agregado)": codigo_nivel1}
    for k, v in subcuentas_nivel2.items():
        label = f"{k} - {v['nombre']}"
        opciones_nivel2[label] = k

    with col_n2:
        nivel2_label = st.selectbox(
            "Grupo",
            options=list(opciones_nivel2.keys()),
            index=0,
            key="cuenta_nivel2"
        )
        codigo_nivel2 = opciones_nivel2[nivel2_label]

    # Nivel 3
    codigo_cuenta_final = codigo_nivel2

    with col_n3:
        if codigo_nivel2 != codigo_nivel1 and codigo_nivel2 in subcuentas_nivel2:
            subcuentas_nivel3 = subcuentas_nivel2[codigo_nivel2]['subcuentas']
            if subcuentas_nivel3:
                opciones_nivel3 = {"Todas (agregado)": codigo_nivel2}
                for k, v in subcuentas_nivel3.items():
                    if isinstance(v, dict):
                        label = f"{k} - {v['nombre']}"
                    else:
                        label = f"{k} - {str(v)}"
                    opciones_nivel3[label] = k

                nivel3_label = st.selectbox(
                    "Subcuenta",
                    options=list(opciones_nivel3.keys()),
                    index=0,
                    key="cuenta_nivel3"
                )
                codigo_nivel3 = opciones_nivel3[nivel3_label]
                codigo_cuenta_final = codigo_nivel3
            else:
                codigo_nivel3 = codigo_nivel2
                st.selectbox("Subcuenta", options=["N/A"], disabled=True, key="cuenta_nivel3_disabled")
        else:
            codigo_nivel3 = codigo_nivel2
            st.selectbox("Subcuenta", options=["N/A"], disabled=True, key="cuenta_nivel3_disabled2")

    # Nivel 4
    with col_n4:
        if (codigo_nivel3 != codigo_nivel2 and
            codigo_nivel2 != codigo_nivel1 and
            codigo_nivel2 in subcuentas_nivel2 and
            codigo_nivel3 in subcuentas_nivel2[codigo_nivel2]['subcuentas'] and
            isinstance(subcuentas_nivel2[codigo_nivel2]['subcuentas'][codigo_nivel3], dict)):
            subcuentas_nivel4 = subcuentas_nivel2[codigo_nivel2]['subcuentas'][codigo_nivel3]['subcuentas']
            if subcuentas_nivel4:
                opciones_nivel4 = {"Todas (agregado)": codigo_nivel3}
                for k, v in subcuentas_nivel4.items():
                    label = f"{k} - {str(v)}"
                    opciones_nivel4[label] = k

                nivel4_label = st.selectbox(
                    "Detalle",
                    options=list(opciones_nivel4.keys()),
                    index=0,
                    key="cuenta_nivel4"
                )
                codigo_cuenta_final = opciones_nivel4[nivel4_label]
            else:
                st.selectbox("Detalle", options=["N/A"], disabled=True, key="cuenta_nivel4_disabled")
        else:
            st.selectbox("Detalle", options=["N/A"], disabled=True, key="cuenta_nivel4_disabled2")

    # Selector de cooperativas
    st.markdown("**Cooperativas a Comparar:**")

    # Filtrar cooperativas por segmento si aplica — usar pre-agregados
    if segmento_global != "Todos":
        cooperativas_filtradas = obtener_cooperativas_por_segmento(segmento_global)
    else:
        cooperativas_filtradas = cooperativas

    cooperativas_seleccionadas = st.multiselect(
        "Selecciona hasta 10 cooperativas",
        options=cooperativas_filtradas,
        default=top_cooperativas_default[:5] if top_cooperativas_default else cooperativas_filtradas[:5],
        max_selections=10,
        key="cooperativas_evol",
        label_visibility="collapsed"
    )

    # Gráfico + Filtros de tiempo
    col_chart, col_tiempo = st.columns([4, 1])

    with col_tiempo:
        st.markdown("**Período**")
        mes_inicio = st.selectbox(
            "Mes desde",
            options=list(range(1, 13)),
            format_func=lambda x: MESES[x],
            index=0,
            key="mes_inicio_evol"
        )
        ano_inicio_evol = st.selectbox(
            "Año desde",
            options=range(fecha_min.year, fecha_max.year + 1),
            index=max(0, 2020 - fecha_min.year),
            key="ano_inicio_evol"
        )
        st.markdown("---")
        mes_fin = st.selectbox(
            "Mes hasta",
            options=list(range(1, 13)),
            format_func=lambda x: MESES[x],
            index=11,
            key="mes_fin_evol"
        )
        ano_fin_evol = st.selectbox(
            "Año hasta",
            options=range(fecha_min.year, fecha_max.year + 1),
            index=fecha_max.year - fecha_min.year,
            key="ano_fin_evol"
        )

        st.markdown("---")

        modo_viz = st.radio(
            "Modo",
            options=["Valores Absolutos", "Indexado (Base 100)", "Participación %"],
            index=0,
            key="modo_evol"
        )
        incluir_sistema = st.checkbox("Incluir Total Sistema", value=False, key="sistema_evol")

    # Crear fechas de filtro
    fecha_inicio_evol = pd.Timestamp(f"{ano_inicio_evol}-{mes_inicio:02d}-01")
    if mes_fin == 12:
        fecha_fin_evol = pd.Timestamp(f"{ano_fin_evol}-12-31")
    else:
        fecha_fin_evol = pd.Timestamp(f"{ano_fin_evol}-{mes_fin + 1:02d}-01") - pd.Timedelta(days=1)

    # Filtrar datos — acotado a la cuenta seleccionada (pushdown), no al
    # balance completo
    df_evol = cargar_balance_por_codigos((codigo_cuenta_final,))
    df_evol = df_evol[
        (df_evol['fecha'] >= fecha_inicio_evol) &
        (df_evol['fecha'] <= fecha_fin_evol)
    ]

    if segmento_global != "Todos":
        df_evol = df_evol[df_evol['segmento'] == segmento_global]

    # Obtener nombre de la cuenta
    cuenta_info = catalogo_cuentas[catalogo_cuentas['codigo'] == codigo_cuenta_final]['cuenta'].iloc[0] if \
        not catalogo_cuentas[catalogo_cuentas['codigo'] == codigo_cuenta_final].empty else codigo_cuenta_final

    # Dibujar gráfico
    with col_chart:
        if cooperativas_seleccionadas:
            y_title = {"Valores Absolutos": "Millones USD", "Indexado (Base 100)": "Índice (Base 100)", "Participación %": "Participación (%)"}[modo_viz]

            # Serie del sistema (si necesario)
            serie_sistema_data = None
            if modo_viz == "Participación %" or incluir_sistema:
                serie_sistema = _serie_sistema_balance(df_evol, codigo_cuenta_final, segmento_global)
                if not serie_sistema.empty:
                    serie_sistema_data = serie_sistema

            # Obtener series batch (cacheado)
            series_data = _obtener_series_batch(
                df_evol, cooperativas_seleccionadas, codigo_cuenta_final,
                modo_viz, serie_sistema_data
            )

            # Preparar datos del sistema si se solicita
            incluir_sistema_data = None
            if incluir_sistema and modo_viz != "Participación %" and serie_sistema_data is not None:
                if modo_viz == "Indexado (Base 100)":
                    base = serie_sistema_data['valor_millones'].iloc[0]
                    sys_values = (serie_sistema_data['valor_millones'] / base * 100).tolist() if base > 0 else serie_sistema_data['valor_millones'].tolist()
                else:
                    sys_values = serie_sistema_data['valor_millones'].tolist()
                incluir_sistema_data = {
                    'fechas': serie_sistema_data['fecha'].tolist(),
                    'valores': sys_values,
                }

            titulo_cuenta = cuenta_info if len(str(cuenta_info)) < 50 else str(cuenta_info)[:47] + "..."

            fig_evol = _crear_evolucion_cached(series_data, f"Evolución: {titulo_cuenta}", y_title, incluir_sistema_data)
            st.plotly_chart(fig_evol, width='stretch')
        else:
            st.info("Selecciona al menos una cooperativa para visualizar.")

    # ==========================================================================
    # SECCION 2: HEATMAP TEMPORAL
    # ==========================================================================

    st.markdown("---")
    st.markdown("### 2. Heatmap de Variación Porcentual Anual")
    st.caption("Matriz Cooperativa x Mes mostrando crecimiento YoY")

    # Filtros de cuenta jerárquicos (igual que módulo 1)
    st.markdown("**Seleccionar Cuenta:**")
    col_h_n1, col_h_n2, col_h_n3, col_h_n4 = st.columns(4)

    with col_h_n1:
        opciones_nivel1_h = {f"{k} - {v['nombre']}": k for k, v in jerarquia.items()}
        nivel1_label_h = st.selectbox(
            "Categoría",
            options=list(opciones_nivel1_h.keys()),
            index=0,
            key="cuenta_nivel1_heat"
        )
        codigo_nivel1_h = opciones_nivel1_h[nivel1_label_h]

    # Nivel 2
    subcuentas_nivel2_h = jerarquia[codigo_nivel1_h]['subcuentas']
    opciones_nivel2_h = {"Todas (agregado)": codigo_nivel1_h}
    for k, v in subcuentas_nivel2_h.items():
        label = f"{k} - {v['nombre']}"
        opciones_nivel2_h[label] = k

    with col_h_n2:
        nivel2_label_h = st.selectbox(
            "Grupo",
            options=list(opciones_nivel2_h.keys()),
            index=0,
            key="cuenta_nivel2_heat"
        )
        codigo_nivel2_h = opciones_nivel2_h[nivel2_label_h]

    # Nivel 3
    codigo_cuenta_heat = codigo_nivel2_h

    with col_h_n3:
        if codigo_nivel2_h != codigo_nivel1_h and codigo_nivel2_h in subcuentas_nivel2_h:
            subcuentas_nivel3_h = subcuentas_nivel2_h[codigo_nivel2_h]['subcuentas']
            if subcuentas_nivel3_h:
                opciones_nivel3_h = {"Todas (agregado)": codigo_nivel2_h}
                for k, v in subcuentas_nivel3_h.items():
                    if isinstance(v, dict):
                        label = f"{k} - {v['nombre']}"
                    else:
                        label = f"{k} - {str(v)}"
                    opciones_nivel3_h[label] = k

                nivel3_label_h = st.selectbox(
                    "Subcuenta",
                    options=list(opciones_nivel3_h.keys()),
                    index=0,
                    key="cuenta_nivel3_heat"
                )
                codigo_nivel3_h = opciones_nivel3_h[nivel3_label_h]
                codigo_cuenta_heat = codigo_nivel3_h
            else:
                codigo_nivel3_h = codigo_nivel2_h
                st.selectbox("Subcuenta", options=["N/A"], disabled=True, key="cuenta_nivel3_heat_disabled")
        else:
            codigo_nivel3_h = codigo_nivel2_h
            st.selectbox("Subcuenta", options=["N/A"], disabled=True, key="cuenta_nivel3_heat_disabled2")

    # Nivel 4
    with col_h_n4:
        if (codigo_nivel3_h != codigo_nivel2_h and
            codigo_nivel2_h != codigo_nivel1_h and
            codigo_nivel2_h in subcuentas_nivel2_h and
            codigo_nivel3_h in subcuentas_nivel2_h[codigo_nivel2_h]['subcuentas'] and
            isinstance(subcuentas_nivel2_h[codigo_nivel2_h]['subcuentas'][codigo_nivel3_h], dict)):
            subcuentas_nivel4_h = subcuentas_nivel2_h[codigo_nivel2_h]['subcuentas'][codigo_nivel3_h]['subcuentas']
            if subcuentas_nivel4_h:
                opciones_nivel4_h = {"Todas (agregado)": codigo_nivel3_h}
                for k, v in subcuentas_nivel4_h.items():
                    label = f"{k} - {str(v)}"
                    opciones_nivel4_h[label] = k

                nivel4_label_h = st.selectbox(
                    "Detalle",
                    options=list(opciones_nivel4_h.keys()),
                    index=0,
                    key="cuenta_nivel4_heat"
                )
                codigo_cuenta_heat = opciones_nivel4_h[nivel4_label_h]
            else:
                st.selectbox("Detalle", options=["N/A"], disabled=True, key="cuenta_nivel4_heat_disabled")
        else:
            st.selectbox("Detalle", options=["N/A"], disabled=True, key="cuenta_nivel4_heat_disabled2")

    # Obtener nombre de la cuenta para el heatmap
    cuenta_info_heat = catalogo_cuentas[catalogo_cuentas['codigo'] == codigo_cuenta_heat]['cuenta'].iloc[0] if \
        not catalogo_cuentas[catalogo_cuentas['codigo'] == codigo_cuenta_heat].empty else codigo_cuenta_heat

    # Datos de balance acotados a la cuenta seleccionada (pushdown)
    df_heat = cargar_balance_por_codigos((codigo_cuenta_heat,))

    # Selector de top cooperativas
    top_n_heat = st.selectbox(
        "Cooperativas a mostrar",
        options=[20, 30, 0],
        index=0,
        format_func=lambda x: "Todas" if x == 0 else f"Top {x}",
        key="top_n_heat"
    )

    # Obtener top cooperativas
    if top_n_heat == 0:
        # Todas las cooperativas del segmento — usar pre-agregados
        top_cooperativas_heat = obtener_cooperativas_por_segmento(
            segmento_global if segmento_global != "Todos" else "Todos"
        )
    else:
        df_rank_heat = obtener_ranking_rapido(
            fecha_max, codigo_cuenta_heat, top_n=top_n_heat,
            segmento=segmento_global if segmento_global != "Todos" else "Todos"
        )
        top_cooperativas_heat = df_rank_heat['cooperativa'].tolist() if not df_rank_heat.empty else []

        # `agg_ranking_cooperativas` solo contiene 9 códigos de nivel 1-2. Para
        # cualquier cuenta de nivel 3 o 4 el ranking rápido venía vacío, la
        # lista de top quedaba en [] y el heatmap dejaba de filtrar: mostraba
        # las ~200 instituciones en vez del "Top 20" que indica el selector.
        # Se resuelve con la misma función que ya usa la sección de ranking de
        # esta página, sobre el balance ya cargado en memoria.
        if not top_cooperativas_heat:
            df_top_fallback = obtener_valores_cooperativas_mes(
                df_heat, codigo_cuenta_heat, pd.Timestamp(fecha_max), segmento_global
            )
            if not df_top_fallback.empty:
                top_cooperativas_heat = df_top_fallback.head(top_n_heat)['cooperativa'].tolist()

    # Filtros de tiempo
    col_heat_chart, col_heat_tiempo = st.columns([4, 1])

    with col_heat_tiempo:
        st.markdown("**Período**")
        ano_inicio_heat = st.selectbox(
            "Año desde",
            options=range(fecha_min.year, fecha_max.year + 1),
            index=max(0, 2020 - fecha_min.year),
            key="ano_inicio_heat"
        )
        ano_fin_heat = st.selectbox(
            "Año hasta",
            options=range(fecha_min.year, fecha_max.year + 1),
            index=fecha_max.year - fecha_min.year,
            key="ano_fin_heat"
        )

    # Crear fechas de filtro
    fecha_inicio_heat = pd.Timestamp(f"{ano_inicio_heat}-01-01")
    fecha_fin_heat = pd.Timestamp(f"{ano_fin_heat}-12-31")

    # Generar datos del heatmap
    heatmap_data = obtener_datos_heatmap_mensual(
        df_heat,
        codigo_cuenta_heat,
        top_cooperativas_heat,
        fecha_inicio_heat,
        fecha_fin_heat,
        segmento_global
    )

    with col_heat_chart:
        if not heatmap_data.empty:
            etiquetas_x = [f"{MESES[int(col.split('-')[1])][:3]} {col.split('-')[0][2:]}" for col in heatmap_data.columns]
            titulo_cuenta_heat = cuenta_info_heat if len(str(cuenta_info_heat)) < 50 else str(cuenta_info_heat)[:47] + "..."

            fig_heat = _crear_heatmap_cached(
                heatmap_data.values.tolist(),
                etiquetas_x,
                truncar_nombres_unicos([str(n) for n in heatmap_data.index]),
                f"Variación YoY: {titulo_cuenta_heat}",
                altura_por_categorias(len(heatmap_data))
            )
            st.plotly_chart(fig_heat, width='stretch')
        else:
            st.warning("No hay datos suficientes para el heatmap.")

    # ==========================================================================
    # SECCION 3: RANKING POR COOPERATIVA
    # ==========================================================================

    st.markdown("---")
    st.markdown("### 3. Ranking de Cooperativas por Cuenta")
    st.caption("Comparación de valores para una cuenta y mes específicos")

    # Filtros de cuenta jerárquicos (igual que módulo 1)
    st.markdown("**Seleccionar Cuenta:**")
    col_r_n1, col_r_n2, col_r_n3, col_r_n4 = st.columns(4)

    with col_r_n1:
        opciones_nivel1_r = {f"{k} - {v['nombre']}": k for k, v in jerarquia.items()}
        nivel1_label_r = st.selectbox(
            "Categoría",
            options=list(opciones_nivel1_r.keys()),
            index=0,
            key="cuenta_nivel1_rank"
        )
        codigo_nivel1_r = opciones_nivel1_r[nivel1_label_r]

    # Nivel 2
    subcuentas_nivel2_r = jerarquia[codigo_nivel1_r]['subcuentas']
    opciones_nivel2_r = {"Todas (agregado)": codigo_nivel1_r}
    for k, v in subcuentas_nivel2_r.items():
        label = f"{k} - {v['nombre']}"
        opciones_nivel2_r[label] = k

    with col_r_n2:
        nivel2_label_r = st.selectbox(
            "Grupo",
            options=list(opciones_nivel2_r.keys()),
            index=0,
            key="cuenta_nivel2_rank"
        )
        codigo_nivel2_r = opciones_nivel2_r[nivel2_label_r]

    # Nivel 3
    codigo_rank = codigo_nivel2_r

    with col_r_n3:
        if codigo_nivel2_r != codigo_nivel1_r and codigo_nivel2_r in subcuentas_nivel2_r:
            subcuentas_nivel3_r = subcuentas_nivel2_r[codigo_nivel2_r]['subcuentas']
            if subcuentas_nivel3_r:
                opciones_nivel3_r = {"Todas (agregado)": codigo_nivel2_r}
                for k, v in subcuentas_nivel3_r.items():
                    if isinstance(v, dict):
                        label = f"{k} - {v['nombre']}"
                    else:
                        label = f"{k} - {str(v)}"
                    opciones_nivel3_r[label] = k

                nivel3_label_r = st.selectbox(
                    "Subcuenta",
                    options=list(opciones_nivel3_r.keys()),
                    index=0,
                    key="cuenta_nivel3_rank"
                )
                codigo_nivel3_r = opciones_nivel3_r[nivel3_label_r]
                codigo_rank = codigo_nivel3_r
            else:
                codigo_nivel3_r = codigo_nivel2_r
                st.selectbox("Subcuenta", options=["N/A"], disabled=True, key="cuenta_nivel3_rank_disabled")
        else:
            codigo_nivel3_r = codigo_nivel2_r
            st.selectbox("Subcuenta", options=["N/A"], disabled=True, key="cuenta_nivel3_rank_disabled2")

    # Nivel 4
    with col_r_n4:
        if (codigo_nivel3_r != codigo_nivel2_r and
            codigo_nivel2_r != codigo_nivel1_r and
            codigo_nivel2_r in subcuentas_nivel2_r and
            codigo_nivel3_r in subcuentas_nivel2_r[codigo_nivel2_r]['subcuentas'] and
            isinstance(subcuentas_nivel2_r[codigo_nivel2_r]['subcuentas'][codigo_nivel3_r], dict)):
            subcuentas_nivel4_r = subcuentas_nivel2_r[codigo_nivel2_r]['subcuentas'][codigo_nivel3_r]['subcuentas']
            if subcuentas_nivel4_r:
                opciones_nivel4_r = {"Todas (agregado)": codigo_nivel3_r}
                for k, v in subcuentas_nivel4_r.items():
                    label = f"{k} - {str(v)}"
                    opciones_nivel4_r[label] = k

                nivel4_label_r = st.selectbox(
                    "Detalle",
                    options=list(opciones_nivel4_r.keys()),
                    index=0,
                    key="cuenta_nivel4_rank"
                )
                codigo_rank = opciones_nivel4_r[nivel4_label_r]
            else:
                st.selectbox("Detalle", options=["N/A"], disabled=True, key="cuenta_nivel4_rank_disabled")
        else:
            st.selectbox("Detalle", options=["N/A"], disabled=True, key="cuenta_nivel4_rank_disabled2")

    # Obtener nombre de la cuenta para el ranking
    cuenta_info_rank = catalogo_cuentas[catalogo_cuentas['codigo'] == codigo_rank]['cuenta'].iloc[0] if \
        not catalogo_cuentas[catalogo_cuentas['codigo'] == codigo_rank].empty else codigo_rank

    # Datos de balance acotados a la cuenta seleccionada (pushdown)
    df_rank = cargar_balance_por_codigos((codigo_rank,))

    # Filtros de fecha y top N
    col_r_mes, col_r_ano, col_r_top = st.columns(3)

    with col_r_mes:
        mes_r = st.selectbox(
            "Mes",
            options=list(MESES.keys()),
            format_func=lambda x: MESES[x],
            index=fecha_max.month - 1,
            key="mes_r"
        )

    with col_r_ano:
        ano_r = st.selectbox(
            "Año",
            options=range(fecha_min.year, fecha_max.year + 1),
            index=fecha_max.year - fecha_min.year,
            key="ano_r"
        )

    with col_r_top:
        top_n_rank = st.selectbox(
            "Mostrar",
            options=[20, 30, 0],
            index=0,
            format_func=lambda x: "Todas" if x == 0 else f"Top {x}",
            key="top_n_rank"
        )

    # Construir fecha seleccionada
    fecha_r = pd.Timestamp(year=ano_r, month=mes_r, day=1)

    # Obtener datos de ranking
    datos_ranking = obtener_valores_cooperativas_mes(df_rank, codigo_rank, fecha_r, segmento_global)

    if not datos_ranking.empty:
        if top_n_rank > 0:
            datos_ranking = datos_ranking.head(top_n_rank)

        # Crear gráfico de barras (cacheado)
        colores = [obtener_color_cooperativa(coop) for coop in datos_ranking['cooperativa']]
        titulo_cuenta_rank = cuenta_info_rank if len(str(cuenta_info_rank)) < 50 else str(cuenta_info_rank)[:47] + "..."
        altura = altura_por_categorias(len(datos_ranking))

        fig_ranking = _crear_ranking_cached(
            datos_ranking['cooperativa'].tolist(),
            datos_ranking['valor_millones'].tolist(),
            colores,
            f"Ranking: {titulo_cuenta_rank} ({MESES[mes_r]} {ano_r})",
            altura
        )
        st.plotly_chart(fig_ranking, width='stretch')

        # Estadísticas
        col_s1, col_s2, col_s3 = st.columns(3)
        total = datos_ranking['valor_millones'].sum()
        with col_s1:
            st.metric("Total Sistema", f"${total:,.0f}M")
        with col_s2:
            participacion_top = (datos_ranking.iloc[0]['valor_millones'] / total * 100) if total > 0 else 0
            st.metric("Participación #1", f"{participacion_top:.1f}%")
        with col_s3:
            participacion_top5 = (datos_ranking.head(5)['valor_millones'].sum() / total * 100) if total > 0 and len(datos_ranking) >= 5 else 0
            st.metric("Concentración Top 5", f"{participacion_top5:.1f}%")
    else:
        st.warning("No hay datos disponibles para el periodo seleccionado.")


if __name__ == "__main__":
    main()
