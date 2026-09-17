# -*- coding: utf-8 -*-
"""
Radar Cooperativo Ecuador
Dashboard de análisis financiero para cooperativas ecuatorianas.

Ejecutar con: streamlit run Inicio.py --server.port 8502
"""

import streamlit as st
import json
from pathlib import Path

# =============================================================================
# CONFIGURACION DE PAGINA (debe ser lo primero)
# =============================================================================

st.set_page_config(
    page_title="Radar Cooperativo Ecuador",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'About': """
        ## Radar Cooperativo Ecuador
        Plataforma de análisis del sistema cooperativo ecuatoriano.

        **Fuente de datos:** Superintendencia de Economía Popular y Solidaria
        **Período:** 2018 - 2025 (8 años de historia)
        **Cooperativas:** 259 instituciones (Segmentos 1, 2, 3 y Mutualistas)
        """
    },
)

# =============================================================================
# ESTILOS CSS GLOBALES
# =============================================================================

st.markdown("""
<style>
    /* Fuente principal */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* Header principal */
    .main-header {
        background: linear-gradient(135deg, #1a4731 0%, #276749 50%, #2f855a 100%);
        padding: 1.5rem 2rem;
        border-radius: 16px;
        margin-bottom: 2rem;
        box-shadow: 0 10px 40px rgba(26, 71, 49, 0.3);
    }

    .main-header h1 {
        color: white;
        font-size: 2.2rem;
        font-weight: 700;
        margin: 0;
        text-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }

    .main-header p {
        color: rgba(255,255,255,0.85);
        font-size: 1rem;
        margin: 0.5rem 0 0 0;
    }

    /* Tarjetas */
    .card {
        background: linear-gradient(145deg, #ffffff 0%, #f7fafc 100%);
        border-radius: 16px;
        padding: 1.5rem;
        box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        border: 1px solid rgba(226, 232, 240, 0.8);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }

    .card:hover {
        transform: translateY(-4px);
        box-shadow: 0 12px 40px rgba(0,0,0,0.12);
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #f7fafc 0%, #edf2f7 100%);
        min-width: 220px !important;
        max-width: 220px !important;
        width: 220px !important;
    }

    /* Ocultar elementos de Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Tabs personalizados */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: #f7fafc;
        padding: 0.5rem;
        border-radius: 12px;
    }

    .stTabs [data-baseweb="tab"] {
        background: transparent;
        border-radius: 8px;
        padding: 0.75rem 1.5rem;
        font-weight: 500;
    }

    .stTabs [aria-selected="true"] {
        background: white;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }

    /* Metricas */
    [data-testid="stMetricValue"] {
        font-size: 1.8rem;
        font-weight: 700;
        color: #1a4731;
    }

    [data-testid="stMetricLabel"] {
        font-size: 0.85rem;
        color: #718096;
        text-transform: uppercase;
    }

    /* Info box */
    .info-box {
        background: linear-gradient(135deg, #276749 0%, #2f855a 100%);
        color: white;
        padding: 1rem;
        border-radius: 12px;
        margin-bottom: 1rem;
        text-align: center;
        box-shadow: 0 4px 15px rgba(39, 103, 73, 0.3);
    }

    .info-box h4 {
        margin: 0;
        font-size: 0.9rem;
        font-weight: 600;
        opacity: 0.95;
        letter-spacing: 0.5px;
    }

    .info-box p {
        margin: 0.5rem 0 0 0;
        font-size: 1.5rem;
        font-weight: 700;
    }

    /* Segmentos */
    .segment-box {
        background: linear-gradient(145deg, #ffffff 0%, #f0fff4 100%);
        border-radius: 12px;
        padding: 1rem 1.25rem;
        border: 1px solid #c6f6d5;
        text-align: center;
    }

    .segment-box h4 {
        margin: 0;
        color: #1a4731;
        font-size: 1rem;
        font-weight: 600;
    }

    .segment-box p {
        margin: 0.3rem 0 0 0;
        color: #718096;
        font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================

def obtener_metadata():
    """Obtiene información sobre la actualización de datos."""
    metadata_path = Path(__file__).parent / 'master_data' / 'metadata.json'
    if metadata_path.exists():
        with open(metadata_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


# =============================================================================
# PAGINA PRINCIPAL
# =============================================================================

def main():
    # Header con gradiente verde (distinto al azul de bancos)
    st.markdown("""
        <div class="main-header">
            <h1>🏦 Radar Cooperativo Ecuador</h1>
            <p>Análisis Financiero del Sistema Cooperativo | Datos oficiales SEPS (2018-2026)</p>
        </div>
    """, unsafe_allow_html=True)

    # KPIs dinámicos
    metadata = obtener_metadata()

    col1, col2, col3, col4 = st.columns(4)

    cooperativas = metadata.get('cooperativas', 259) if metadata else 259
    meses = metadata.get('meses', 96) if metadata else 96

    with col1:
        st.markdown(f"""
        <div class="info-box">
            <h4>COOPERATIVAS</h4>
            <p>{cooperativas}</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="info-box">
            <h4>AÑOS DE HISTORIA</h4>
            <p>8</p>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="info-box">
            <h4>MESES DE DATOS</h4>
            <p>{meses}</p>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        if metadata and 'fecha_max' in metadata:
            from datetime import datetime
            try:
                fecha = datetime.fromisoformat(metadata['fecha_max'])
                fecha_str = fecha.strftime('%b %Y').title()
            except Exception:
                fecha_str = "Dic 2025"
        else:
            fecha_str = "Dic 2025"
        st.markdown(f"""
        <div class="info-box">
            <h4>DATOS AL</h4>
            <p>{fecha_str}</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Introducción
    st.markdown("""
    ### Bienvenido al Radar Cooperativo

    Esta plataforma permite explorar y analizar el sistema cooperativo de ahorro y crédito del Ecuador
    con datos oficiales de la **Superintendencia de Economía Popular y Solidaria (SEPS)**.
    Utiliza el menú lateral para navegar entre los diferentes módulos de análisis.
    """)

    st.markdown("---")

    # =========================================================================
    # MODULOS DE ANALISIS
    # =========================================================================

    st.markdown("### Módulos de Análisis")
    st.markdown("<br>", unsafe_allow_html=True)

    # MODULO 1: PANORAMA
    st.markdown("""
    <div class="card">
        <h3 style="color: #276749; margin-bottom: 0.5rem;">📊 1. Panorama del Sistema</h3>
        <p style="color: #4a5568; margin-bottom: 1rem; font-size: 0.95rem;">
            Vista consolidada del sistema cooperativo con indicadores clave de mercado y concentración.
        </p>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top: 1rem;">
            <div>
                <p style="margin: 0; font-weight: 600; color: #1a4731; font-size: 0.9rem;">KPIs del Sistema</p>
                <p style="margin: 0.25rem 0 0 0; color: #718096; font-size: 0.85rem;">Activos totales, cartera, depósitos, patrimonio y número de cooperativas</p>
            </div>
            <div>
                <p style="margin: 0; font-weight: 600; color: #1a4731; font-size: 0.9rem;">Mapa de Mercado</p>
                <p style="margin: 0.25rem 0 0 0; color: #718096; font-size: 0.85rem;">Treemaps jerárquicos interactivos de activos y pasivos con drill-down</p>
            </div>
            <div>
                <p style="margin: 0; font-weight: 600; color: #1a4731; font-size: 0.9rem;">Rankings</p>
                <p style="margin: 0.25rem 0 0 0; color: #718096; font-size: 0.85rem;">Top cooperativas por activos y pasivos con participación de mercado</p>
            </div>
            <div>
                <p style="margin: 0; font-weight: 600; color: #1a4731; font-size: 0.9rem;">Crecimiento YoY</p>
                <p style="margin: 0.25rem 0 0 0; color: #718096; font-size: 0.85rem;">Variación anual de cartera y depósitos por cooperativa</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # MODULO 2: BALANCE GENERAL
    st.markdown("""
    <div class="card">
        <h3 style="color: #276749; margin-bottom: 0.5rem;">⚖️ 2. Balance General</h3>
        <p style="color: #4a5568; margin-bottom: 1rem; font-size: 0.95rem;">
            Análisis temporal detallado del balance con navegación jerárquica de cuentas contables.
        </p>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top: 1rem;">
            <div>
                <p style="margin: 0; font-weight: 600; color: #1a4731; font-size: 0.9rem;">Evolución Comparativa</p>
                <p style="margin: 0.25rem 0 0 0; color: #718096; font-size: 0.85rem;">Series temporales multi-cooperativa con comparación directa</p>
            </div>
            <div>
                <p style="margin: 0; font-weight: 600; color: #1a4731; font-size: 0.9rem;">Filtros Jerárquicos</p>
                <p style="margin: 0.25rem 0 0 0; color: #718096; font-size: 0.85rem;">Navegación por categoría, grupo, subcuenta y detalle contable</p>
            </div>
            <div>
                <p style="margin: 0; font-weight: 600; color: #1a4731; font-size: 0.9rem;">Heatmap YoY</p>
                <p style="margin: 0.25rem 0 0 0; color: #718096; font-size: 0.85rem;">Matriz cooperativa x mes mostrando crecimiento vs año anterior</p>
            </div>
            <div>
                <p style="margin: 0; font-weight: 600; color: #1a4731; font-size: 0.9rem;">Ranking por Cuenta</p>
                <p style="margin: 0.25rem 0 0 0; color: #718096; font-size: 0.85rem;">Comparación de cooperativas para un mes y cuenta específicos</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # MODULO 3: PERDIDAS Y GANANCIAS
    st.markdown("""
    <div class="card">
        <h3 style="color: #276749; margin-bottom: 0.5rem;">💰 3. Pérdidas y Ganancias</h3>
        <p style="color: #4a5568; margin-bottom: 1rem; font-size: 0.95rem;">
            Análisis de rentabilidad y resultados con valores anualizados (suma móvil 12 meses).
        </p>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top: 1rem;">
            <div>
                <p style="margin: 0; font-weight: 600; color: #1a4731; font-size: 0.9rem;">Evolución Comparativa</p>
                <p style="margin: 0.25rem 0 0 0; color: #718096; font-size: 0.85rem;">Comparación multi-cooperativa de ingresos y gastos anualizados</p>
            </div>
            <div>
                <p style="margin: 0; font-weight: 600; color: #1a4731; font-size: 0.9rem;">Modos de Visualización</p>
                <p style="margin: 0.25rem 0 0 0; color: #718096; font-size: 0.85rem;">Valores absolutos (millones USD), indexado (base 100) y participación (%)</p>
            </div>
            <div>
                <p style="margin: 0; font-weight: 600; color: #1a4731; font-size: 0.9rem;">Ranking por Cuenta</p>
                <p style="margin: 0.25rem 0 0 0; color: #718096; font-size: 0.85rem;">Clasificación de cooperativas por cuenta y estadísticas del sistema</p>
            </div>
            <div>
                <p style="margin: 0; font-weight: 600; color: #1a4731; font-size: 0.9rem;">Cuentas Jerárquicas</p>
                <p style="margin: 0.25rem 0 0 0; color: #718096; font-size: 0.85rem;">Selector de 4-Gastos y 5-Ingresos con subcuentas detalladas</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # MODULO 4: CAMEL
    st.markdown("""
    <div class="card">
        <h3 style="color: #276749; margin-bottom: 0.5rem;">📈 4. Indicadores CAMEL</h3>
        <p style="color: #4a5568; margin-bottom: 1rem; font-size: 0.95rem;">
            37 indicadores financieros oficiales de la SEPS en 7 categorías, extraídos de tablas dinámicas.
        </p>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top: 1rem;">
            <div>
                <p style="margin: 0; font-weight: 600; color: #1a4731; font-size: 0.9rem;">C - Capital</p>
                <p style="margin: 0.25rem 0 0 0; color: #718096; font-size: 0.85rem;">Capitalización, FK, FI y vulnerabilidad patrimonial</p>
            </div>
            <div>
                <p style="margin: 0; font-weight: 600; color: #1a4731; font-size: 0.9rem;">A - Activos</p>
                <p style="margin: 0.25rem 0 0 0; color: #718096; font-size: 0.85rem;">Morosidad y cobertura por tipo de cartera, calidad de activos</p>
            </div>
            <div>
                <p style="margin: 0; font-weight: 600; color: #1a4731; font-size: 0.9rem;">M - Management / E - Earnings</p>
                <p style="margin: 0.25rem 0 0 0; color: #718096; font-size: 0.85rem;">Eficiencia operativa, ROE, ROA, intermediación y rendimientos</p>
            </div>
            <div>
                <p style="margin: 0; font-weight: 600; color: #1a4731; font-size: 0.9rem;">L - Liquidez</p>
                <p style="margin: 0.25rem 0 0 0; color: #718096; font-size: 0.85rem;">Ranking, evolución temporal y heatmaps mensuales con escalas de colores</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # =========================================================================
    # ACCESO RAPIDO
    # =========================================================================

    st.markdown("### Acceso Rápido")
    st.markdown("<br>", unsafe_allow_html=True)

    col_a, col_b, col_c, col_d = st.columns(4)

    with col_a:
        st.page_link("pages/1_Panorama.py", label="📊 Panorama", width='stretch')

    with col_b:
        st.page_link("pages/2_Balance_General.py", label="⚖️ Balance General", width='stretch')

    with col_c:
        st.page_link("pages/3_Perdidas_Ganancias.py", label="💰 Pérdidas y Ganancias", width='stretch')

    with col_d:
        st.page_link("pages/4_CAMEL.py", label="📈 Indicadores CAMEL", width='stretch')

    st.markdown("---")

    # =========================================================================
    # SEGMENTOS
    # =========================================================================

    st.markdown("### Segmentos del Sistema Cooperativo")
    st.markdown("<br>", unsafe_allow_html=True)

    col_s1, col_s2, col_s3, col_s4 = st.columns(4)

    with col_s1:
        st.markdown("""
        <div class="segment-box">
            <h4>Segmento 1</h4>
            <p>Activos > $80 millones</p>
        </div>
        """, unsafe_allow_html=True)

    with col_s2:
        st.markdown("""
        <div class="segment-box">
            <h4>Segmento 2</h4>
            <p>Activos $20 - $80 millones</p>
        </div>
        """, unsafe_allow_html=True)

    with col_s3:
        st.markdown("""
        <div class="segment-box">
            <h4>Segmento 3</h4>
            <p>Activos $5 - $20 millones</p>
        </div>
        """, unsafe_allow_html=True)

    with col_s4:
        st.markdown("""
        <div class="segment-box">
            <h4>Mutualistas</h4>
            <p>Segmento 1 Mutualista</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # =========================================================================
    # CROSS-PROMO: RADAR BANCARIO
    # =========================================================================

    st.markdown("""
    <div style="
        background: linear-gradient(135deg, #1a365d 0%, #2c5282 50%, #3182ce 100%);
        border-radius: 16px;
        padding: 2rem;
        margin: 1rem 0;
        box-shadow: 0 10px 40px rgba(26, 54, 93, 0.3);
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 1rem;
    ">
        <div style="flex: 1; min-width: 280px;">
            <h3 style="color: white; margin: 0 0 0.5rem 0; font-size: 1.4rem;">
                🏛️ Conoce también el Radar del Sistema Bancario
            </h3>
            <p style="color: rgba(255,255,255,0.85); margin: 0; font-size: 0.95rem;">
                Explora el análisis financiero completo de los bancos privados del Ecuador:
                Balance General, Pérdidas y Ganancias, Series Temporales, Rentabilidad e Indicadores CAMEL.
            </p>
        </div>
        <div style="flex-shrink: 0;">
            <a href="https://bancos-dqebh5jqc3r5scsjrlwfxp.streamlit.app/Balance_General"
               target="_blank"
               style="
                   background: white;
                   color: #1a365d;
                   padding: 0.75rem 1.5rem;
                   border-radius: 10px;
                   text-decoration: none;
                   font-weight: 600;
                   font-size: 0.95rem;
                   display: inline-block;
                   box-shadow: 0 4px 12px rgba(0,0,0,0.15);
               ">
                Visitar Radar Bancario →
            </a>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # =========================================================================
    # INFO Y FOOTER
    # =========================================================================

    st.markdown("""
    ### Información del Sistema

    **Fuente de Datos:** Superintendencia de Economía Popular y Solidaria (SEPS)
    **Período Cubierto:** Enero 2018 - Diciembre 2025 (96 meses)
    **Instituciones:** 259 cooperativas + 4 mutualistas (Segmentos 1, 2 y 3)
    **Formato:** Archivos Parquet optimizados (~22.7 millones de registros de balance)

    Los datos son procesados con normalización de nombres y validaciones de calidad
    para garantizar consistencia y consultas eficientes.
    """)

    st.markdown("---")

    col_f1, col_f2 = st.columns([2, 1])

    with col_f1:
        st.markdown(
            """
            <div style='color: #718096; font-size: 0.85rem;'>
                <p><strong>Tecnologías:</strong> Python 3.8+, Streamlit, Plotly, Pandas, NumPy<br>
                <strong>Fuente de datos:</strong> Superintendencia de Economía Popular y Solidaria<br>
                <strong>Versión:</strong> 1.0.0</p>
            </div>
            """,
            unsafe_allow_html=True
        )

    with col_f2:
        st.markdown(
            """
            <div style='text-align: right; color: #718096; font-size: 0.85rem;'>
                <p><strong>Desarrollado por</strong><br>Eco. Cristian Coronel Quezada, MBA<br><strong>DATAMETRICS</strong></p>
            </div>
            """,
            unsafe_allow_html=True
        )


if __name__ == "__main__":
    main()
