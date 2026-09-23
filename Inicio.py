# -*- coding: utf-8 -*-
"""
RADAR COOPERATIVO ECUADOR — COSEDE
Sistema Inteligente para el Monitoreo Integral del Sector Financiero Popular y Solidario.

Marca corporativa: DATAMETRICS — Business Intelligence and Analytics
Autor institucional: Eco. Cristian Coronel Quezada MBA
CEO · DATAMETRICS

Ejecutar con: streamlit run Inicio.py
"""

from datetime import datetime

import pandas as pd
import streamlit as st

from ui import aplicar_tema, render_filtro_segmento, render_header, render_sidebar
from ui.header import LOGO_PATH
from utils.charts import crear_sparkline, crear_gauge, COLORES
from utils.data_loader import (
    cargar_metadata,
    obtener_serie_sistema,
    obtener_ultima_fecha,
)

# =============================================================================
# CONFIGURACION DE PAGINA (debe ser lo primero)
# =============================================================================

st.set_page_config(
    page_title="Radar Cooperativo Ecuador | COSEDE",
    # Icono de la pestaña del navegador: logo oficial DATAMETRICS (mismo
    # archivo que el header). Si aún no está colocado, cae al escudo anterior.
    page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": """
        ## RADAR COOPERATIVO ECUADOR
        Sistema Inteligente para el Monitoreo Integral del Sector Financiero
        Popular y Solidario.

        **Marca:** DATAMETRICS — Business Intelligence and Analytics

        **Autor:** Eco. Cristian Coronel Quezada MBA — CEO · DATAMETRICS.

        **Fuente de datos:** Superintendencia de Economía Popular y Solidaria (SEPS).
        """
    },
)

aplicar_tema()


# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================

def _anios_de_historia(metadata: dict) -> int:
    """Calcula los años de historia a partir de fecha_min/fecha_max."""
    try:
        f_min = datetime.fromisoformat(metadata["fecha_min"])
        f_max = datetime.fromisoformat(metadata["fecha_max"])
        return f_max.year - f_min.year + 1
    except (KeyError, ValueError, TypeError):
        meses = metadata.get("meses", 0)
        return max(1, round(meses / 12)) if meses else 0


# =============================================================================
# PAGINA PRINCIPAL
# =============================================================================

def main():
    # `cargar_metadata()` es la misma lectura de master_data/metadata.json que
    # usan todas las demás páginas, pero cacheada (`st.cache_data`): reutilizarla
    # evita releer el JSON en cada rerun del home.
    metadata = cargar_metadata()

    render_sidebar(metadata)

    # Header institucional (marca + estado del sistema)
    render_header(metadata, estado="ok")

    # ------------------------------------------------------------------ KPIs
    cooperativas = metadata.get("cooperativas", 0)
    meses = metadata.get("meses", 0)
    anios = _anios_de_historia(metadata)
    registros = metadata.get("registros_totales", 0)
    cuentas = metadata.get("cuentas", 0)

    # "Datos al" se deriva del último período realmente presente en los
    # agregados, no del JSON de metadata: si el ETL incorpora un mes nuevo y el
    # metadata quedara desactualizado, el home seguiría mostrando el período
    # correcto. El metadata solo actúa como respaldo.
    fecha_max_str = "—"
    ultima_fecha = obtener_ultima_fecha()
    if ultima_fecha is not None:
        fecha_max_str = pd.Timestamp(ultima_fecha).strftime("%b %Y").title()
    elif metadata.get("fecha_max"):
        try:
            fecha_max_str = datetime.fromisoformat(metadata["fecha_max"]).strftime("%b %Y").title()
        except (ValueError, TypeError):
            pass

    kpis = [
        ("Instituciones", f"{cooperativas}", "sps-kpi"),
        ("Años de historia", f"{anios}", "sps-kpi sps-kpi--petrol"),
        ("Meses de datos", f"{meses}", "sps-kpi sps-kpi--petrol"),
        ("Cuentas contables", f"{cuentas:,}", "sps-kpi sps-kpi--green"),
        ("Datos al", fecha_max_str, "sps-kpi sps-kpi--amber"),
    ]

    cols = st.columns(len(kpis))
    for col, (label, valor, clase) in zip(cols, kpis):
        with col:
            st.markdown(
                f"""
                <div class="{clase}">
                    <div class="sps-kpi__label">{label}</div>
                    <div class="sps-kpi__value">{valor}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ------------------------------------------------------------ Introducción
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        """
        Plataforma institucional de **inteligencia de riesgos** para el monitoreo integral
        del Sector Financiero Popular y Solidario del Ecuador, con datos oficiales de la
        **Superintendencia de Economía Popular y Solidaria (SEPS)**. Utilice el menú lateral
        para navegar entre los módulos analíticos.
        """
    )
    st.markdown("---")

    # ==========================================================================
    # EXECUTIVE DASHBOARD: KPIs FINANCIEROS + SPARKLINES + GAUGE + RESUMEN
    # ==========================================================================

    st.markdown('<div class="sps-section-title">Indicadores Financieros del Sistema</div>', unsafe_allow_html=True)

    # Filtro Global de Segmento (ui/filtros.py): mismo componente y misma
    # key de session_state que usan las demás páginas, de modo que el
    # segmento elegido aquí sigue activo al navegar a Panorama, CAMEL, etc.
    st.sidebar.markdown("### Filtros")
    segmento_home = render_filtro_segmento()
    if segmento_home != "Todos":
        st.caption(f"Indicadores filtrados por **{segmento_home}**.")

    series_financieras = {
        "Activos Totales": ("1", "sps-kpi"),
        "Cartera de Créditos": ("14", "sps-kpi sps-kpi--petrol"),
        "Depósitos del Público": ("21", "sps-kpi sps-kpi--green"),
        "Patrimonio": ("3", "sps-kpi sps-kpi--amber"),
    }

    resultados_financieros = {}
    # Las series se guardan al obtenerlas para reutilizarlas más abajo en el
    # gauge de intermediación, en vez de volver a pedir las de cartera (14) y
    # depósitos (21) por separado.
    series_obtenidas = {}
    cols_fin = st.columns(4)
    for col, (nombre, (codigo, clase)) in zip(cols_fin, series_financieras.items()):
        serie = obtener_serie_sistema(codigo, segmento_home)
        series_obtenidas[codigo] = serie
        with col:
            if serie.empty:
                st.markdown(
                    f'<div class="{clase}"><div class="sps-kpi__label">{nombre}</div>'
                    f'<div class="sps-kpi__value">—</div></div>',
                    unsafe_allow_html=True,
                )
                continue

            valor_actual = serie["valor_total"].iloc[-1]
            valor_anterior = serie["valor_total"].iloc[-13] if len(serie) > 12 else None
            delta = (
                ((valor_actual - valor_anterior) / valor_anterior * 100)
                if valor_anterior and valor_anterior > 0 else None
            )
            resultados_financieros[nombre] = delta

            delta_html = ""
            if delta is not None:
                signo = "+" if delta >= 0 else ""
                clase_delta = "sps-kpi__delta--up" if delta >= 0 else "sps-kpi__delta--down"
                delta_html = f'<div class="sps-kpi__delta {clase_delta}">{signo}{delta:.1f}% interanual</div>'

            st.markdown(
                f"""
                <div class="{clase}">
                    <div class="sps-kpi__label">{nombre}</div>
                    <div class="sps-kpi__value">${valor_actual / 1_000_000:,.0f}M</div>
                    {delta_html}
                </div>
                """,
                unsafe_allow_html=True,
            )
            ultimos_24m = serie["valor_total"].tail(24).tolist()
            color_spark = {
                "Activos Totales": COLORES["primario"],
                "Cartera de Créditos": COLORES["secundario"],
                "Depósitos del Público": COLORES["exito"],
                "Patrimonio": COLORES["advertencia"],
            }[nombre]
            st.plotly_chart(
                crear_sparkline(ultimos_24m, color=color_spark),
                width="stretch",
                config={"displayModeBar": False},
            )

    st.markdown("<br>", unsafe_allow_html=True)
    col_gauge, col_resumen = st.columns([1, 2])

    serie_cartera_g = series_obtenidas.get("14", pd.DataFrame())
    serie_depositos_g = series_obtenidas.get("21", pd.DataFrame())

    with col_gauge:
        if not serie_cartera_g.empty and not serie_depositos_g.empty:
            cartera_actual = serie_cartera_g["valor_total"].iloc[-1]
            depositos_actual = serie_depositos_g["valor_total"].iloc[-1]
            indice_intermediacion = (
                (cartera_actual / depositos_actual * 100) if depositos_actual > 0 else 0
            )
            st.plotly_chart(
                crear_gauge(
                    indice_intermediacion,
                    titulo="Índice de Intermediación Referencial (Cartera / Depósitos)",
                    rango=(0, 150),
                ),
                width="stretch",
                config={"displayModeBar": False},
            )
        else:
            st.info("Sin datos suficientes para el índice de intermediación.")

    with col_resumen:
        st.markdown('<div class="sps-section-title">Resumen Ejecutivo Automático</div>', unsafe_allow_html=True)
        puntos = []
        for nombre, delta in resultados_financieros.items():
            if delta is None:
                continue
            direccion = "creció" if delta >= 0 else "se contrajo"
            puntos.append(f"- **{nombre}** {direccion} **{abs(delta):.1f}%** interanual.")

        if puntos:
            st.markdown("\n".join(puntos))
            st.caption(
                "Resumen generado automáticamente a partir de los agregados del sistema "
                "(variación interanual, mismo mes del año anterior). No sustituye el "
                "análisis detallado disponible en cada módulo."
            )
        else:
            st.info("No hay suficiente historia (12 meses) para calcular variaciones interanuales.")

    st.markdown("---")

    # ------------------------------------------------------------- Módulos
    st.markdown('<div class="sps-section-title">Módulos de análisis</div>', unsafe_allow_html=True)

    modulos = [
        ("📊", "Panorama del Sistema",
         "Vista consolidada con KPIs de mercado, treemaps de activos y pasivos, "
         "rankings y crecimiento interanual por institución."),
        ("⚖️", "Balance General",
         "Análisis temporal del balance con navegación jerárquica de cuentas, "
         "evolución comparativa y heatmaps de variación interanual."),
        ("💰", "Pérdidas y Ganancias",
         "Rentabilidad y resultados con valores anualizados (suma móvil 12 meses), "
         "modos absoluto/indexado/participación y ranking por cuenta."),
        ("📈", "Indicadores CAMEL",
         "37 indicadores financieros oficiales de la SEPS en 7 categorías, con ranking, "
         "evolución temporal y heatmaps mensuales calibrados por percentiles."),
    ]

    fila1 = st.columns(2)
    fila2 = st.columns(2)
    for col, (icono, titulo, desc) in zip(fila1 + fila2, modulos):
        with col:
            st.markdown(
                f"""
                <div class="sps-card">
                    <h3>{icono}&nbsp;&nbsp;{titulo}</h3>
                    <p>{desc}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown("<div style='height:0.9rem'></div>", unsafe_allow_html=True)

    st.markdown("---")

    # ------------------------------------------------------- Módulos de Riesgo
    st.markdown('<div class="sps-section-title">Módulos de Riesgo</div>', unsafe_allow_html=True)

    modulos_riesgo = [
        ("💧", "Riesgo de Liquidez",
         "Indicador oficial LIQ, liquidez ampliada calculada, distribución y simulador de estrés de retiro."),
        ("🧾", "Riesgo de Crédito",
         "Morosidad y cobertura oficiales por tipo de cartera, cartera vencida, provisiones y heatmap mensual."),
        ("🏛️", "Riesgo de Solvencia",
         "Capitalización, patrimonio/activos y vulnerabilidad patrimonial (FK, FI, CAP_NETO)."),
        ("🧩", "Riesgo de Concentración",
         "HHI, CR5/CR10, curva de Lorenz y coeficiente de Gini sobre activos, cartera y depósitos."),
        ("🕸️", "Riesgo Sistémico",
         "Índice de Importancia Sistémica por tamaño y sustituibilidad de mercado."),
        ("🧮", "CAMEL — Score Compuesto",
         "Score 0-100 por institución (percentiles C-A-M-E-L), radar y heatmap comparativo."),
        ("🚨", "Alertas Tempranas",
         "Motor de reglas con semáforo agregado y ranking de deterioro institucional."),
    ]

    filas_riesgo = [st.columns(4), st.columns(3)]
    celdas_riesgo = filas_riesgo[0] + filas_riesgo[1]
    for col, (icono, titulo, desc) in zip(celdas_riesgo, modulos_riesgo):
        with col:
            st.markdown(
                f"""
                <div class="sps-card">
                    <h3 style="font-size:0.95rem;">{icono}&nbsp;&nbsp;{titulo}</h3>
                    <p style="font-size:0.82rem;">{desc}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown("<div style='height:0.7rem'></div>", unsafe_allow_html=True)

    st.markdown("---")

    # ------------------------------------------------------- Analítica Avanzada
    st.markdown('<div class="sps-section-title">Analítica Avanzada</div>', unsafe_allow_html=True)

    modulos_avanzados = [
        ("🧪", "Stress Testing / Escenarios",
         "Prueba de resistencia con shocks de liquidez y deterioro crediticio (Base, Moderado, Severo, Extremo)."),
        ("📉", "Modelos Predictivos",
         "Forecast ARIMA de series del sistema y predicción de morosidad a un mes (Random Forest), con métricas de validación reales."),
        ("🤖", "Machine Learning",
         "Detección de anomalías (Isolation Forest) y segmentación de riesgo (KMeans), entrenados en tiempo real."),
        ("🧠", "Asistente Inteligente",
         "Chat institucional anclado a datos reales, con integración opcional a Claude (Anthropic)."),
    ]

    fila_avanzada = st.columns(4)
    for col, (icono, titulo, desc) in zip(fila_avanzada, modulos_avanzados):
        with col:
            st.markdown(
                f"""
                <div class="sps-card">
                    <h3 style="font-size:0.95rem;">{icono}&nbsp;&nbsp;{titulo}</h3>
                    <p style="font-size:0.82rem;">{desc}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.markdown("<div style='height:0.7rem'></div>", unsafe_allow_html=True)

    st.markdown("---")

    # -------------------------------------------------------- Acceso rápido
    st.markdown('<div class="sps-section-title">Acceso rápido</div>', unsafe_allow_html=True)
    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        st.page_link("pages/1_Panorama.py", label="Panorama", icon="📊", width="stretch")
    with col_b:
        st.page_link("pages/2_Balance_General.py", label="Balance General", icon="⚖️", width="stretch")
    with col_c:
        st.page_link("pages/3_Perdidas_Ganancias.py", label="Pérdidas y Ganancias", icon="💰", width="stretch")
    with col_d:
        st.page_link("pages/4_CAMEL.py", label="Indicadores CAMEL", icon="📈", width="stretch")

    col_e, col_f, col_g, col_h = st.columns(4)
    with col_e:
        st.page_link("pages/5_Riesgo_Liquidez.py", label="Riesgo de Liquidez", icon="💧", width="stretch")
    with col_f:
        st.page_link("pages/6_Riesgo_Credito.py", label="Riesgo de Crédito", icon="🧾", width="stretch")
    with col_g:
        st.page_link("pages/7_Riesgo_Solvencia.py", label="Riesgo de Solvencia", icon="🏛️", width="stretch")
    with col_h:
        st.page_link("pages/8_Riesgo_Concentracion.py", label="Riesgo de Concentración", icon="🧩", width="stretch")

    col_i, col_j, col_k, col_l = st.columns(4)
    with col_i:
        st.page_link("pages/9_Riesgo_Sistemico.py", label="Riesgo Sistémico", icon="🕸️", width="stretch")
    with col_j:
        st.page_link("pages/10_CAMEL_Score.py", label="CAMEL Score", icon="🧮", width="stretch")
    with col_k:
        st.page_link("pages/11_Alertas_Tempranas.py", label="Alertas Tempranas", icon="🚨", width="stretch")
    with col_l:
        st.page_link("pages/12_Stress_Testing.py", label="Stress Testing", icon="🧪", width="stretch")

    col_m, col_n, col_o = st.columns(3)
    with col_m:
        st.page_link("pages/13_Modelos_Predictivos.py", label="Modelos Predictivos", icon="📉", width="stretch")
    with col_n:
        st.page_link("pages/14_Machine_Learning.py", label="Machine Learning", icon="🤖", width="stretch")
    with col_o:
        st.page_link("pages/15_Asistente_IA.py", label="Asistente Inteligente", icon="🧠", width="stretch")

    st.markdown("---")

    # --------------------------------------------------------- Segmentos
    st.markdown('<div class="sps-section-title">Segmentos del sector</div>', unsafe_allow_html=True)
    segmentos = [
        ("Segmento 1", "Activos > $80 millones"),
        ("Segmento 2", "Activos $20 – $80 millones"),
        ("Segmento 3", "Activos $5 – $20 millones"),
        ("Mutualistas", "Segmento 1 Mutualista"),
    ]
    for col, (nombre, desc) in zip(st.columns(4), segmentos):
        with col:
            st.markdown(
                f"""
                <div class="sps-segment">
                    <h4>{nombre}</h4>
                    <p>{desc}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # ------------------------------------------------------- Info del sistema
    st.markdown('<div class="sps-section-title">Información del sistema</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        - **Fuente de datos:** Superintendencia de Economía Popular y Solidaria (SEPS)
        - **Período cubierto:** {metadata.get('fecha_min', '—')[:7]} a {fecha_max_str} · {meses} meses
        - **Instituciones:** {cooperativas} (Segmentos 1, 2, 3 y Mutualistas)
        - **Registros de balance procesados:** {registros:,}
        - **Formato:** Archivos Parquet optimizados con agregados pre-calculados para consultas eficientes
        """
    )

    st.markdown("---")

    # ------------------------------------------------------------- Footer
    col_f1, col_f2 = st.columns([2, 1])
    with col_f1:
        st.markdown(
            """
            <div style='color: var(--sps-text-dim); font-size: 0.82rem;'>
                <strong>Tecnologías:</strong> Python, Streamlit, Plotly, Pandas, PyArrow<br>
                <strong>Fuente:</strong> Superintendencia de Economía Popular y Solidaria (SEPS)
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_f2:
        st.markdown(
            """
            <div style='text-align: right; color: var(--sps-text-dim); font-size: 0.82rem;'>
                <strong>CEO · DATAMETRICS</strong><br>
                Eco. Cristian Coronel Quezada MBA
            </div>
            """,
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
