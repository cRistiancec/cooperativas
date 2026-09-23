# -*- coding: utf-8 -*-
"""Capa de presentación institucional (UI) del RADAR COOPERATIVO ECUADOR."""

from ui.theme import aplicar_tema, PALETA
from ui.header import render_header
from ui.sidebar import render_sidebar
from ui.filtros import render_filtro_segmento, SPS_SEGMENTO_KEY

__all__ = [
    "aplicar_tema", "PALETA", "render_header", "render_sidebar",
    "render_filtro_segmento", "SPS_SEGMENTO_KEY",
]
