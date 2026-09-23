# -*- coding: utf-8 -*-
"""
Sidebar premium del RADAR COOPERATIVO ECUADOR (COSEDE).

Bloque institucional que se antepone a los filtros propios de cada página
(segmento, fecha, etc.), que se mantienen intactos debajo. Incluye:
buscador de cooperativas, favoritos, indicadores rápidos, estado de
conexión de datos y ayuda.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd
import streamlit as st

from utils.data_loader import cargar_catalogo_cooperativas, obtener_serie_sistema

_PAGINAS_DISPONIBLES = [
    ("📊", "Panorama", "pages/1_Panorama.py"),
    ("⚖️", "Balance General", "pages/2_Balance_General.py"),
    ("💰", "Pérdidas y Ganancias", "pages/3_Perdidas_Ganancias.py"),
    ("📈", "Indicadores CAMEL", "pages/4_CAMEL.py"),
    ("💧", "Riesgo de Liquidez", "pages/5_Riesgo_Liquidez.py"),
    ("🧾", "Riesgo de Crédito", "pages/6_Riesgo_Credito.py"),
    ("🏛️", "Riesgo de Solvencia", "pages/7_Riesgo_Solvencia.py"),
    ("🧩", "Riesgo de Concentración", "pages/8_Riesgo_Concentracion.py"),
    ("🕸️", "Riesgo Sistémico", "pages/9_Riesgo_Sistemico.py"),
    ("🧮", "CAMEL Score", "pages/10_CAMEL_Score.py"),
    ("🚨", "Alertas Tempranas", "pages/11_Alertas_Tempranas.py"),
    ("🧪", "Stress Testing", "pages/12_Stress_Testing.py"),
    ("📉", "Modelos Predictivos", "pages/13_Modelos_Predictivos.py"),
    ("🤖", "Machine Learning", "pages/14_Machine_Learning.py"),
    ("🧠", "Asistente Inteligente", "pages/15_Asistente_IA.py"),
]

_MASTER_DATA_DIR = Path(__file__).resolve().parent.parent / "master_data"


def _estado_archivos_datos() -> Dict[str, bool]:
    """Verifica la presencia de los archivos de datos clave (estado de conexión)."""
    archivos = ["balance.parquet", "pyg.parquet", "indicadores.parquet", "agg_metricas_sistema.parquet"]
    return {a: (_MASTER_DATA_DIR / a).exists() for a in archivos}


def _buscador_cooperativas() -> None:
    """Buscador rápido: nombre → segmento, ranking y activos."""
    catalogo = cargar_catalogo_cooperativas()
    if catalogo.empty:
        return

    termino = st.text_input("🔎 Buscar cooperativa", key="sps_buscador", placeholder="Ej. JARDIN AZUAYO")
    if not termino:
        return

    coincidencias = catalogo[
        catalogo["cooperativa"].str.contains(termino, case=False, na=False)
    ].sort_values("ranking").head(5)

    if coincidencias.empty:
        st.caption("Sin coincidencias.")
        return

    for _, fila in coincidencias.iterrows():
        activos_m = fila["activos_ultimo"] / 1_000_000
        st.markdown(
            f"""
            <div style="font-size:0.78rem; padding:6px 0; border-bottom:1px solid var(--sps-border);">
                <strong>#{int(fila['ranking'])}</strong> — {fila['cooperativa']}<br>
                <span style="color:var(--sps-text-dim);">{fila['segmento']} · Activos ${activos_m:,.1f}M</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _favoritos() -> None:
    """Marcado de módulos favoritos, persistido en la sesión del usuario."""
    if "sps_favoritos" not in st.session_state:
        st.session_state["sps_favoritos"] = []

    seleccion = st.multiselect(
        "⭐ Favoritos",
        options=[nombre for _, nombre, _ in _PAGINAS_DISPONIBLES],
        default=st.session_state["sps_favoritos"],
        key="sps_favoritos_select",
        placeholder="Marca tus módulos frecuentes",
    )
    st.session_state["sps_favoritos"] = seleccion

    if seleccion:
        for icono, nombre, ruta in _PAGINAS_DISPONIBLES:
            if nombre in seleccion:
                st.page_link(ruta, label=nombre, icon=icono)


def _indicadores_rapidos() -> None:
    """Mini KPIs del sistema (última fecha disponible), sin cargar el balance completo."""
    serie_activos = obtener_serie_sistema("1")
    serie_cartera = obtener_serie_sistema("14")

    if serie_activos.empty:
        st.caption("Sin datos agregados disponibles.")
        return

    activos_m = serie_activos["valor_total"].iloc[-1] / 1_000_000
    cartera_m = serie_cartera["valor_total"].iloc[-1] / 1_000_000 if not serie_cartera.empty else 0

    st.markdown(
        f"""
        <div style="font-size:0.78rem; line-height:1.9;">
            <div>Activos del sistema: <strong>${activos_m:,.0f}M</strong></div>
            <div>Cartera de créditos: <strong>${cartera_m:,.0f}M</strong></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _estado_conexion() -> None:
    """Semáforo de disponibilidad de los archivos de datos fuente."""
    estado = _estado_archivos_datos()
    ok = sum(estado.values())
    total = len(estado)

    if ok == total:
        clase, texto = "sps-light--ok", "Datos disponibles"
    elif ok == 0:
        clase, texto = "sps-light--crit", "Datos no disponibles"
    else:
        clase, texto = "sps-light--warn", "Datos parciales"

    st.markdown(
        f"""
        <span class="sps-light {clase}"><span class="sps-light__dot"></span>{texto}</span>
        <div style="color:var(--sps-text-dim); font-size:0.7rem; margin-top:4px;">{ok}/{total} archivos verificados</div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar(metadata: Optional[Dict[str, Any]] = None) -> None:
    """
    Renderiza el bloque premium del sidebar. Debe llamarse al inicio de cada
    página, antes de los filtros propios de esa página (segmento, fecha, etc.).
    """
    metadata = metadata or {}

    with st.sidebar:
        st.markdown("### Radar Cooperativo Ecuador")
        st.caption("CEO · DATAMETRICS")

        _estado_conexion()
        st.markdown("---")

        _buscador_cooperativas()
        st.markdown("---")

        _indicadores_rapidos()
        st.markdown("---")

        _favoritos()
        st.markdown("---")

        with st.expander("⚙️ Configuración"):
            st.caption("Tema institucional (oscuro) — fijo en esta versión.")
            st.checkbox("Modo compacto (próximamente)", value=False, disabled=True, key="sps_modo_compacto")

        with st.expander("📤 Exportaciones"):
            st.caption(
                "Cada gráfico incluye exportación a PNG desde su barra de herramientas "
                "(ícono de cámara, esquina superior derecha del gráfico)."
            )

        with st.expander("❓ Ayuda"):
            st.markdown(
                """
                - **Panorama**: KPIs, mapas de mercado y crecimiento anual.
                - **Balance General**: evolución de cuentas y heatmap YoY.
                - **Pérdidas y Ganancias**: resultados anualizados (12 meses).
                - **CAMEL**: 37 indicadores oficiales SEPS por categoría.
                - **Riesgo de Liquidez / Crédito / Solvencia**: indicadores oficiales especializados.
                - **Concentración / Sistémico**: HHI, Gini, Índice de Importancia Sistémica.
                - **CAMEL Score / Alertas Tempranas**: scoring compuesto y motor de reglas.

                Fuente de datos: Superintendencia de Economía Popular y Solidaria (SEPS).
                """
            )

        st.markdown("---")
        st.caption(f"COSEDE © {pd.Timestamp.now().year} · DATAMETRICS — Business Intelligence and Analytics")
