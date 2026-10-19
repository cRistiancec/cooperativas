# -*- coding: utf-8 -*-
"""Capa de presentación institucional (UI) del RADAR COOPERATIVO ECUADOR."""

from ui.theme import aplicar_tema, PALETA
from ui.header import render_header
from ui.sidebar import render_sidebar
from ui.filtros import (
    botones_descarga, exigir_datos, filtro_actual, render_filtros_globales, render_resumen_filtro,
    restablecer_filtros, selector_fecha_corte,
)

__all__ = [
    "aplicar_tema", "PALETA", "render_header", "render_sidebar",
    "render_filtros_globales", "selector_fecha_corte", "render_resumen_filtro", "exigir_datos",
    "botones_descarga", "filtro_actual", "restablecer_filtros",
]
