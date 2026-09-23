# -*- coding: utf-8 -*-
"""
Componentes gráficos reutilizables para el dashboard de cooperativas.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from typing import List, Optional, Dict, Any
from pathlib import Path
import sys

# Agregar path para imports
sys.path.append(str(Path(__file__).parent.parent))
from config.indicator_mapping import obtener_color_cooperativa


# =============================================================================
# COLORES Y ESTILOS
# =============================================================================

COLORES = {
    'primario': '#2563EB',
    'secundario': '#14657F',
    'acento': '#22D3EE',
    'exito': '#22C55E',
    'advertencia': '#F59E0B',
    'error': '#EF4444',
    'neutro': '#9DB0CE',
    'fondo': '#131C2E',
    'texto': '#E7EEF9',
    'grid': 'rgba(148, 163, 191, 0.14)',
}

PALETA_COOPERATIVAS = px.colors.qualitative.Set2 + px.colors.qualitative.Pastel1

# Layout base oscuro institucional (fondos transparentes para heredar el tema)
LAYOUT_BASE = {
    'font': {'family': 'Inter, sans-serif', 'color': COLORES['texto']},
    'paper_bgcolor': 'rgba(0,0,0,0)',
    'plot_bgcolor': 'rgba(0,0,0,0)',
    'margin': {'l': 10, 'r': 10, 't': 40, 'b': 10},
    'colorway': ['#2563EB', '#22D3EE', '#22C55E', '#F59E0B', '#EF4444',
                 '#A78BFA', '#14657F', '#F472B6', '#38BDF8', '#FACC15'],
}


# =============================================================================
# FUNCIONES DE COLORES
# =============================================================================

def obtener_colores_para_cooperativas(cooperativas: List[str]) -> Dict[str, str]:
    """Obtiene un diccionario de colores para una lista de cooperativas."""
    return {coop: obtener_color_cooperativa(coop) for coop in cooperativas}


# =============================================================================
# ETIQUETAS Y LEYENDAS (LEGIBILIDAD)
# =============================================================================

def truncar_nombre(nombre: str, max_len: int = 30) -> str:
    """
    Trunca nombres largos de institución manteniendo inicio y final, que es lo
    que permite diferenciar cooperativas con prefijos comunes ("COOPERATIVA DE
    AHORRO Y CREDITO ..."). Fuente única de verdad: antes cada página aplicaba
    su propio recorte (`[:25]`, `[:30]`, cabeza+cola), lo que producía
    etiquetas distintas para la misma institución según el módulo.
    """
    nombre = str(nombre)
    if len(nombre) <= max_len:
        return nombre
    return nombre[:12] + '...' + nombre[-(max_len - 15):]


def truncar_nombres_unicos(nombres: List[str], max_len: int = 30) -> List[str]:
    """
    Trunca una lista de nombres garantizando que no haya colisiones.

    Necesario porque Plotly trata dos categorías con la misma etiqueta como
    una sola: si dos cooperativas se truncaran al mismo texto, sus barras se
    fusionarían silenciosamente (pérdida de información, no solo estética).
    Ante una colisión se conserva el nombre completo del segundo elemento.
    """
    vistos: Dict[str, int] = {}
    resultado: List[str] = []
    for nombre in nombres:
        corto = truncar_nombre(nombre, max_len)
        if corto in vistos:
            corto = str(nombre)  # colisión: preferir el nombre completo
        vistos[corto] = vistos.get(corto, 0) + 1
        resultado.append(corto)
    return resultado


def altura_por_categorias(n: int, px_por_categoria: int = 22, minimo: int = 400) -> int:
    """
    Altura recomendada para un gráfico de barras horizontales / heatmap con
    `n` categorías, de modo que cada etiqueta tenga espacio propio y no se
    solape con la siguiente. Reemplaza los `max(400, n * 22)` repetidos.
    """
    return max(minimo, int(n) * px_por_categoria + 80)


def layout_leyenda_series(n_series: int) -> Dict[str, Any]:
    """
    Devuelve `legend` + `margin` para gráficos de series comparadas
    (módulos "Cooperativas a Comparar").

    Con leyenda horizontal y nombres largos, Plotly envuelve las entradas en
    varias filas; con un margen inferior fijo esas filas se superponían con el
    título del eje X o quedaban recortadas. Aquí el margen inferior y la
    posición de la leyenda escalan con el número de filas estimadas
    (~3 entradas por fila con `itemwidth=70`), de modo que la leyenda nunca
    invade el área de trazado ni se corta.
    """
    n = max(1, int(n_series))
    filas = -(-n // 3)  # techo de n/3
    alto_leyenda = 22 * filas
    margen_inferior = 60 + alto_leyenda
    return {
        'legend': dict(
            orientation='h',
            yanchor='top',
            y=-(0.16 + 0.05 * (filas - 1)),
            xanchor='center',
            x=0.5,
            font=dict(size=10),
            itemwidth=70,
            itemsizing='constant',
            traceorder='normal',
        ),
        'margin': dict(l=10, r=30, t=50, b=margen_inferior),
    }


# =============================================================================
# TARJETAS KPI
# =============================================================================

def render_kpi_card(
    valor: str,
    label: str,
    delta: Optional[float] = None,
    delta_label: str = "",
    color: str = COLORES['acento']
):
    """Renderiza una tarjeta KPI con estilos personalizados."""
    delta_html = ""
    if delta is not None:
        signo = "+" if delta >= 0 else ""
        delta_color = COLORES['exito'] if delta >= 0 else COLORES['error']
        delta_html = f'<div style="color: {delta_color}; font-size: 0.85rem; margin-top: 4px;">{signo}{delta:.1f}% {delta_label}</div>'

    st.markdown(f"""
        <div style="
            background: linear-gradient(160deg, #131C2E 0%, #0E1526 100%);
            border: 1px solid #24304A;
            border-radius: 12px;
            padding: 1.1rem 1.2rem;
            box-shadow: 0 2px 12px rgba(0,0,0,0.25);
            border-left: 4px solid {color};
            margin-bottom: 1rem;
        ">
            <div style="font-family: 'JetBrains Mono', ui-monospace, monospace; font-size: 1.55rem; font-weight: 700; color: #ffffff;">{valor}</div>
            <div style="font-size: 0.72rem; color: #9DB0CE; text-transform: uppercase; letter-spacing: 0.08em; font-weight: 600;">{label}</div>
            {delta_html}
        </div>
    """, unsafe_allow_html=True)


# =============================================================================
# GRAFICOS DE RANKING
# =============================================================================

def crear_ranking_barras(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    titulo: str = "",
    formato_valor: str = "${:,.0f}M",
    altura: int = 400,
    usar_colores_cooperativas: bool = True
) -> go.Figure:
    """
    Crea gráfico de barras horizontales para ranking.

    Legibilidad (auditoría de producción): varias páginas de riesgo llamaban a
    esta función con 30 instituciones y la altura por defecto de 400 px, lo que
    dejaba ~12 px por etiqueta y hacía que los nombres de las cooperativas se
    superpusieran verticalmente. Ahora la altura se ajusta automáticamente al
    número de categorías (`altura` actúa como piso, nunca como techo), las
    etiquetas del eje Y se truncan de forma consistente y el nombre completo se
    conserva en el tooltip. El margen derecho deja sitio a las etiquetas de
    valor `textposition='outside'`, que antes se recortaban.
    """
    df_sorted = df.sort_values(x_col, ascending=True)

    # Determinar colores
    if usar_colores_cooperativas and y_col == 'cooperativa':
        colors = [obtener_color_cooperativa(coop) for coop in df_sorted[y_col]]
        marker_dict = dict(color=colors)
    else:
        colors = df_sorted[x_col]
        marker_dict = dict(color=colors, colorscale='Blues')

    nombres_completos = [str(v) for v in df_sorted[y_col]]
    etiquetas_y = truncar_nombres_unicos(nombres_completos)

    fig = go.Figure(go.Bar(
        y=etiquetas_y,
        x=df_sorted[x_col],
        orientation='h',
        marker=marker_dict,
        text=[formato_valor.format(v) for v in df_sorted[x_col]],
        textposition='outside',
        cliponaxis=False,
        customdata=nombres_completos,
        hovertemplate="<b>%{customdata}</b><br>Valor: %{x:,.2f}<extra></extra>"
    ))

    layout = dict(LAYOUT_BASE)
    layout['margin'] = {'l': 10, 'r': 70, 't': 40, 'b': 10}

    fig.update_layout(
        **layout,
        title=titulo,
        height=altura_por_categorias(len(df_sorted), minimo=altura),
        xaxis_title="",
        yaxis_title="",
        yaxis=dict(categoryorder='total ascending', tickfont=dict(size=10), automargin=True),
        showlegend=False
    )

    return fig


# =============================================================================
# TREEMAP
# =============================================================================

def crear_treemap(
    df: pd.DataFrame,
    path_col: str = None,
    values_col: str = None,
    titulo: str = "",
    altura: int = 450,
    jerarquico: bool = False
) -> go.Figure:
    """Crea un treemap para visualizar composición."""
    df_clean = df.copy()

    if jerarquico:
        required_cols = ['labels', 'parents', 'values']
        if not all(col in df_clean.columns for col in required_cols):
            fig = go.Figure()
            fig.add_annotation(
                text="Estructura de datos incorrecta",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=16)
            )
            fig.update_layout(height=altura, title=titulo)
            return fig

        df_clean = df_clean.dropna(subset=['values'])
        df_clean = df_clean[df_clean['values'] > 0]

        if df_clean.empty:
            fig = go.Figure()
            fig.add_annotation(
                text="No hay datos disponibles",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=16)
            )
            fig.update_layout(height=altura, title=titulo)
            return fig

        labels = df_clean['labels'].tolist()
        parents = df_clean['parents'].tolist()
        values = df_clean['values'].tolist()

        if 'id' in df_clean.columns:
            ids = df_clean['id'].tolist()
        else:
            ids = None

        if 'participacion' in df_clean.columns:
            colors = df_clean['participacion'].tolist()
        else:
            colors = values

        texttemplate = "%{label}<br>$%{value:,.0f}M"

        if 'participacion' in df_clean.columns:
            customdata = df_clean[['participacion']].values.tolist()
            hovertemplate = "<b>%{label}</b><br>Valor: $%{value:,.0f}M<br>Participación: %{customdata[0]:.1f}%<extra></extra>"
        else:
            customdata = None
            hovertemplate = "<b>%{label}</b><br>Valor: $%{value:,.0f}M<extra></extra>"

        fig = go.Figure(go.Treemap(
            labels=labels,
            ids=ids,
            parents=parents,
            values=values,
            marker=dict(
                colors=colors,
                colorscale='Blues',
                showscale=False,
                line=dict(width=2, color='white')
            ),
            texttemplate=texttemplate,
            customdata=customdata,
            hovertemplate=hovertemplate,
            branchvalues="total"
        ))

    else:
        df_clean = df_clean.dropna(subset=[values_col, path_col])
        df_clean = df_clean[df_clean[values_col] > 0]

        if df_clean.empty:
            fig = go.Figure()
            fig.add_annotation(
                text="No hay datos disponibles",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=16)
            )
            fig.update_layout(height=altura, title=titulo)
            return fig

        labels = df_clean[path_col].tolist()
        parents = [''] * len(labels)
        values = df_clean[values_col].tolist()
        colors = values

        fig = go.Figure(go.Treemap(
            labels=labels,
            parents=parents,
            values=values,
            marker=dict(
                colors=colors,
                colorscale='Blues',
                showscale=True
            ),
            hovertemplate="<b>%{label}</b><br>Valor: $%{value:,.0f}M<extra></extra>"
        ))

    fig.update_layout(
        **LAYOUT_BASE,
        title=titulo,
        height=altura,
    )

    return fig


# =============================================================================
# GRAFICO DE LINEAS (SERIES TEMPORALES)
# =============================================================================

def crear_linea_temporal(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    color_col: Optional[str] = None,
    titulo: str = "",
    y_label: str = "Valor",
    altura: int = 400,
    mostrar_area: bool = False,
    usar_colores_cooperativas: bool = True
) -> go.Figure:
    """Crea gráfico de líneas para series temporales."""
    if color_col:
        if usar_colores_cooperativas and color_col == 'cooperativa':
            cooperativas = df[color_col].unique().tolist()
            color_map = obtener_colores_para_cooperativas(cooperativas)

            fig = px.line(
                df,
                x=x_col,
                y=y_col,
                color=color_col,
                markers=True,
                line_shape='spline',
                color_discrete_map=color_map,
            )
        else:
            fig = px.line(
                df,
                x=x_col,
                y=y_col,
                color=color_col,
                markers=True,
                line_shape='spline',
                color_discrete_sequence=PALETA_COOPERATIVAS,
            )
    else:
        fig = px.line(
            df,
            x=x_col,
            y=y_col,
            markers=True,
            line_shape='spline',
        )
        if mostrar_area:
            fig.update_traces(fill='tozeroy', line_color=COLORES['acento'])

    fig.update_layout(
        **LAYOUT_BASE,
        title=titulo,
        height=altura,
        xaxis_title="",
        yaxis_title=y_label,
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )

    fig.update_xaxes(showgrid=True, gridcolor=COLORES['grid'])
    fig.update_yaxes(showgrid=True, gridcolor=COLORES['grid'])

    return fig


# =============================================================================
# SPARKLINES Y GAUGES (EXECUTIVE DASHBOARD)
# =============================================================================

def _hex_a_rgba(color_hex: str, alpha: float = 0.14) -> str:
    """Convierte un color hex (#RRGGBB) a una cadena rgba con transparencia."""
    color_hex = color_hex.lstrip('#')
    r, g, b = (int(color_hex[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {alpha})"


def crear_sparkline(
    valores: List[float],
    color: str = COLORES['primario'],
    altura: int = 56,
) -> go.Figure:
    """Crea una mini-tendencia (sparkline) sin ejes, para tarjetas KPI."""
    fig = go.Figure(go.Scatter(
        y=valores,
        mode='lines',
        line=dict(width=2, color=color, shape='spline'),
        fill='tozeroy',
        fillcolor=_hex_a_rgba(color),
        hoverinfo='skip',
    ))
    fig.update_layout(
        height=altura,
        margin=dict(l=0, r=0, t=2, b=2),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        showlegend=False,
    )
    return fig


def crear_gauge(
    valor: float,
    titulo: str = "",
    rango: tuple = (0, 100),
    zonas: Optional[List[Dict[str, Any]]] = None,
    sufijo: str = "%",
    altura: int = 220,
) -> go.Figure:
    """
    Crea un gauge (velocímetro) institucional para indicadores referenciales.

    `zonas` es una lista de dicts {'range': [a, b], 'color': '#...'} que
    define las bandas de color (semáforo) del indicador.
    """
    zonas = zonas or [
        {'range': [rango[0], rango[1] * 0.5], 'color': 'rgba(239, 68, 68, 0.25)'},
        {'range': [rango[1] * 0.5, rango[1] * 0.8], 'color': 'rgba(245, 158, 11, 0.25)'},
        {'range': [rango[1] * 0.8, rango[1]], 'color': 'rgba(34, 197, 94, 0.25)'},
    ]

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=valor,
        number={'suffix': sufijo, 'font': {'color': '#E7EEF9', 'size': 30}},
        title={'text': titulo, 'font': {'color': '#9DB0CE', 'size': 13}},
        gauge={
            'axis': {'range': list(rango), 'tickcolor': '#9DB0CE'},
            'bar': {'color': COLORES['primario']},
            'bgcolor': 'rgba(0,0,0,0)',
            'borderwidth': 1,
            'bordercolor': '#24304A',
            'steps': zonas,
        },
    ))

    fig.update_layout(
        height=altura,
        margin=dict(l=20, r=20, t=50, b=10),
        paper_bgcolor='rgba(0,0,0,0)',
        font={'family': 'Inter, sans-serif'},
    )
    return fig


# =============================================================================
# RADAR (CAMEL / SOLVENCIA)
# =============================================================================

def crear_radar(
    categorias: List[str],
    series: Dict[str, List[float]],
    titulo: str = "",
    altura: int = 420,
    rango: tuple = (0, 100),
) -> go.Figure:
    """
    Crea un radar chart comparando una o más entidades a través de varias
    categorías (p. ej. scores C-A-M-E-L de una o varias cooperativas).

    `series` es un dict {nombre_entidad: [valores en el mismo orden que categorias]}.
    """
    fig = go.Figure()
    paleta = LAYOUT_BASE['colorway']

    for i, (nombre, valores) in enumerate(series.items()):
        valores_cerrado = valores + [valores[0]]
        categorias_cerrado = categorias + [categorias[0]]
        color = paleta[i % len(paleta)]
        fig.add_trace(go.Scatterpolar(
            r=valores_cerrado,
            theta=categorias_cerrado,
            fill='toself',
            name=nombre,
            line=dict(color=color, width=2),
            opacity=0.75,
        ))

    fig.update_layout(
        title=titulo,
        height=altura,
        paper_bgcolor='rgba(0,0,0,0)',
        font={'family': 'Inter, sans-serif', 'color': COLORES['texto']},
        polar=dict(
            bgcolor='rgba(0,0,0,0)',
            radialaxis=dict(visible=True, range=list(rango), gridcolor=COLORES['grid']),
            angularaxis=dict(gridcolor=COLORES['grid']),
        ),
        showlegend=len(series) > 1,
        legend=dict(orientation='h', yanchor='bottom', y=-0.15, xanchor='center', x=0.5),
        margin=dict(l=40, r=40, t=50, b=30),
    )
    return fig


# =============================================================================
# CURVA DE LORENZ (CONCENTRACION)
# =============================================================================

def crear_lorenz(
    df_lorenz: pd.DataFrame,
    titulo: str = "",
    altura: int = 420,
) -> go.Figure:
    """
    Crea la curva de Lorenz junto con la línea de igualdad perfecta, a partir
    del DataFrame producido por `analytics.concentracion.curva_lorenz`.
    """
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=[0, 1], y=[0, 1],
        mode='lines',
        name='Igualdad perfecta',
        line=dict(color=COLORES['neutro'], width=1.5, dash='dash'),
        hoverinfo='skip',
    ))

    fig.add_trace(go.Scatter(
        x=df_lorenz['pct_instituciones'],
        y=df_lorenz['pct_valor_acumulado'],
        mode='lines',
        name='Curva de Lorenz',
        fill='tonexty',
        line=dict(color=COLORES['primario'], width=3),
        hovertemplate='Instituciones acum.: %{x:.0%}<br>Valor acum.: %{y:.0%}<extra></extra>',
    ))

    fig.update_layout(
        **LAYOUT_BASE,
        title=titulo,
        height=altura,
        xaxis=dict(title='% acumulado de instituciones', tickformat='.0%', gridcolor=COLORES['grid']),
        yaxis=dict(title='% acumulado del valor', tickformat='.0%', gridcolor=COLORES['grid']),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
    )
    return fig


# =============================================================================
# HEATMAP
# =============================================================================

def crear_heatmap(
    df: pd.DataFrame,
    titulo: str = "",
    color_scale: str = 'RdYlGn',
    altura: int = 400,
    mostrar_valores: bool = True
) -> go.Figure:
    """Crea heatmap a partir de un DataFrame pivotado."""
    fig = px.imshow(
        df,
        color_continuous_scale=color_scale,
        aspect='auto',
    )

    if mostrar_valores:
        fig.update_traces(
            text=df.values,
            texttemplate="%{text:.1f}",
            textfont={"size": 10},
        )

    fig.update_layout(
        **LAYOUT_BASE,
        title=titulo,
        height=altura,
    )

    return fig
