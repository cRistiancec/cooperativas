# -*- coding: utf-8 -*-
"""
Header institucional de RADAR COOPERATIVO ECUADOR (COSEDE).

Renderiza la cabecera premium con logo, nombre y subtítulo del producto,
autoría institucional, fecha/hora, última actualización de datos, número de
registros e instituciones procesadas, y el semáforo general del sistema.
"""

from __future__ import annotations

import base64
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import streamlit as st

from utils.data_loader import obtener_ultima_fecha

# Ruta donde debe colocarse el logo institucional del producto (PNG con fondo
# transparente recomendado). Si el archivo no existe, el header cae a un
# badge de texto. Logo oficial DATAMETRICS (Business Intelligence and
# Analytics) — el archivo ya contiene la identidad completa de la marca.
LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "branding" / "logo.png"

NOMBRE_SISTEMA = "RADAR COOPERATIVO ECUADOR"
SUBTITULO = "Sistema Inteligente para el Monitoreo Integral del Sector Financiero Popular y Solidario"
AUTOR = "Eco. Cristian Coronel Quezada MBA · CEO · DATAMETRICS"

_MESES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]

_SEMAFORO = {
    "ok": ("sps-light--ok", "Sistema operativo"),
    "warn": ("sps-light--warn", "Vigilancia elevada"),
    "crit": ("sps-light--crit", "Alertas críticas"),
}


def _fmt_fecha(valor: Any, corto: bool = False) -> str:
    """Formatea una fecha ISO o datetime a texto en español."""
    if valor is None:
        return "—"
    try:
        fecha = datetime.fromisoformat(str(valor)) if not isinstance(valor, datetime) else valor
    except (ValueError, TypeError):
        return str(valor)
    mes = _MESES[fecha.month]
    if corto:
        return f"{mes[:3]} {fecha.year}"
    return f"{fecha.day:02d} {mes} {fecha.year}"


def _fmt_registros(n: Optional[int]) -> str:
    """Formatea un conteo grande de registros de forma compacta."""
    if not n:
        return "—"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(int(n))


@st.cache_data(show_spinner=False)
def _logo_html() -> str:
    """
    Devuelve el HTML del logo: la imagen real de `assets/branding/logo.png`
    incrustada en base64 si existe, o un badge de texto "DATAMETRICS" como
    fallback mientras no se coloque el archivo.
    """
    if LOGO_PATH.exists():
        datos = base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
        return (
            f'<img src="data:image/png;base64,{datos}" '
            'alt="DATAMETRICS" style="width:100%;height:100%;object-fit:contain;padding:4px;" />'
        )
    return "DATAMETRICS"


def render_header(
    metadata: Optional[Dict[str, Any]] = None,
    estado: str = "ok",
    estado_label: Optional[str] = None,
    ahora: Optional[datetime] = None,
) -> None:
    """
    Dibuja el header institucional.

    Args:
        metadata: contenido de ``master_data/metadata.json``.
        estado: ``"ok" | "warn" | "crit"`` — color del semáforo general.
        estado_label: texto del semáforo (usa el predeterminado si es None).
        ahora: fecha/hora a mostrar (por defecto, la actual).
    """
    metadata = metadata or {}
    ahora = ahora or datetime.now()

    registros = _fmt_registros(metadata.get("registros_totales"))
    instituciones = metadata.get("cooperativas", "—")
    # "Datos al" se toma del último período presente en los agregados
    # (`obtener_ultima_fecha`, cacheado) y solo cae a `metadata["fecha_max"]`
    # si no hay agregados disponibles. Así la cabecera nunca puede quedar
    # anclada a un período anterior al que realmente contienen los datos.
    ultima_fecha = obtener_ultima_fecha()
    datos_al = _fmt_fecha(
        ultima_fecha if ultima_fecha is not None else metadata.get("fecha_max"),
        corto=True,
    )
    actualizado = _fmt_fecha(metadata.get("fecha_procesamiento"))
    fecha_hoy = f"{ahora.day:02d} {_MESES[ahora.month]} {ahora.year}"
    hora = ahora.strftime("%H:%M")

    clase_sem, label_def = _SEMAFORO.get(estado, _SEMAFORO["ok"])
    label_sem = estado_label or label_def

    logo_contenido = _logo_html()
    estilo_logo_extra = "background:#ffffff;" if LOGO_PATH.exists() else ""

    st.markdown(
        f"""
        <div class="sps-header">
            <div class="sps-header__brand">
                <div class="sps-header__logo" style="{estilo_logo_extra}">{logo_contenido}</div>
                <div class="sps-header__titles">
                    <h1>{NOMBRE_SISTEMA}</h1>
                    <p>{SUBTITULO}</p>
                    <p class="sps-header__author">{AUTOR}</p>
                </div>
            </div>
            <div class="sps-header__status">
                <div class="sps-stat">
                    <div class="sps-stat__value">{fecha_hoy}</div>
                    <div class="sps-stat__label">Fecha · {hora}</div>
                </div>
                <div class="sps-stat">
                    <div class="sps-stat__value">{datos_al}</div>
                    <div class="sps-stat__label">Datos al</div>
                </div>
                <div class="sps-stat">
                    <div class="sps-stat__value">{actualizado}</div>
                    <div class="sps-stat__label">Últ. actualización</div>
                </div>
                <div class="sps-stat">
                    <div class="sps-stat__value">{registros}</div>
                    <div class="sps-stat__label">Registros</div>
                </div>
                <div class="sps-stat">
                    <div class="sps-stat__value">{instituciones}</div>
                    <div class="sps-stat__label">Instituciones</div>
                </div>
                <div class="sps-stat">
                    <span class="sps-light {clase_sem}">
                        <span class="sps-light__dot"></span>{label_sem}
                    </span>
                    <div class="sps-stat__label" style="margin-top:6px;">Semáforo general</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
