# -*- coding: utf-8 -*-
"""
Tema institucional del RADAR COOPERATIVO ECUADOR (COSEDE).

Carga e inyecta la capa de estilos (dark institucional) desde `styles/`.
Un único punto de verdad para el aspecto visual de toda la plataforma.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import streamlit as st

# Directorio de hojas de estilo
_STYLES_DIR = Path(__file__).resolve().parent.parent / "styles"

# Orden de carga (las variables de theme.css deben ir primero)
_CSS_FILES = ["theme.css", "styles.css", "responsive.css", "animations.css"]

# Paleta expuesta a Python (para gráficos y componentes) — refleja theme.css
PALETA: Dict[str, str] = {
    "bg": "#0A1120",
    "bg_2": "#0E1526",
    "surface": "#131C2E",
    "surface_2": "#17223A",
    "border": "#24304A",
    "border_strong": "#33436B",
    "primary": "#2563EB",
    "petrol": "#0E4D64",
    "petrol_2": "#14657F",
    "navy": "#0B2545",
    "text": "#E7EEF9",
    "text_muted": "#9DB0CE",
    "text_dim": "#6C7C9C",
    "green": "#22C55E",
    "amber": "#F59E0B",
    "red": "#EF4444",
    "cyan": "#22D3EE",
}


@st.cache_data(show_spinner=False)
def _leer_css() -> str:
    """Lee y concatena las hojas de estilo. Cacheado (contenido estático)."""
    partes = []
    for nombre in _CSS_FILES:
        ruta = _STYLES_DIR / nombre
        if ruta.exists():
            partes.append(ruta.read_text(encoding="utf-8"))
    return "\n".join(partes)


def aplicar_tema() -> None:
    """
    Inyecta el tema institucional en la página actual.

    Debe invocarse una vez por página, inmediatamente después de
    `st.set_page_config`, porque Streamlit reejecuta cada página de forma
    independiente.
    """
    st.markdown(f"<style>{_leer_css()}</style>", unsafe_allow_html=True)
