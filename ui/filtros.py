# -*- coding: utf-8 -*-
"""
Filtro Global de Segmento — componente único de la plataforma para filtrar
por segmento de cooperativa (Segmento 1, Segmento 1 Mutualista, Segmento 2,
Segmento 3, o la clasificación oficial que exista en los datos).

Antes de este componente, catorce páginas definían su propio
`st.sidebar.selectbox("Segmento", ...)`, cada una con una `key` distinta
(`seg_liq`, `seg_credito`, `segmento_global`, `segmento_pyg`, ...) y algunas
derivando la lista de segmentos de un DataFrame distinto por página
(`df_ind["segmento"].unique()`, `df_ranking["segmento"].unique()`, ...). Eran
filtros aislados: elegir "Segmento 2" en Liquidez no afectaba a Crédito.

IMPORTANTE — por qué esto NO es un simple `st.selectbox(..., key=SPS_SEGMENTO_KEY)`:
en las apps multipágina "clásicas" (carpeta `pages/`, como esta plataforma),
Streamlit **no** conserva el valor de un widget entre páginas aunque compartan
`key` — cada página resetea el estado de sus propios widgets al navegar.
Verificado en vivo con un navegador real contra un repro mínimo: un
`st.selectbox` con `key` idéntica en dos páginas vuelve a su `index` por
defecto al pasar de una a otra. Solo `st.session_state` como variable *plana*
(no atada como key de un widget) persiste entre páginas de forma nativa. Por
eso este componente usa el patrón documentado por Streamlit para este caso
("Widgets that persist across pages"): una key plana persistente
(`SPS_SEGMENTO_KEY`) que se copia a una key de widget "sombra" al inicio de
cada render (`_cargar_valor`), y se copia de vuelta cuando el usuario cambia
la selección (`_guardar_valor`, vía `on_change`).
"""
from __future__ import annotations

import streamlit as st

from utils.data_loader import obtener_segmentos_disponibles_rapido

# Key de session_state persistente entre páginas — es la que deben leer otras
# páginas/funciones si alguna vez necesitaran el segmento sin volver a
# renderizar el widget. Todas las páginas deben obtener el segmento a través
# de `render_filtro_segmento()` (nunca declarar su propio selectbox de
# segmento) para seguir compartiendo esta key.
SPS_SEGMENTO_KEY = "sps_segmento_global"

# Key del widget en sí (nunca leída directamente fuera de este módulo): se
# resetea en cada página por a la limitación de Streamlit descrita arriba, y
# por eso se re-hidrata desde SPS_SEGMENTO_KEY antes de cada render.
_SPS_SEGMENTO_WIDGET_KEY = "_sps_segmento_widget"


def _cargar_valor_persistente() -> None:
    """Copia el valor persistente a la key del widget, antes de crearlo."""
    st.session_state[_SPS_SEGMENTO_WIDGET_KEY] = st.session_state.get(SPS_SEGMENTO_KEY, "Todos")


def _guardar_valor_persistente() -> None:
    """Callback `on_change`: copia el valor elegido de vuelta a la key persistente."""
    st.session_state[SPS_SEGMENTO_KEY] = st.session_state[_SPS_SEGMENTO_WIDGET_KEY]


def render_filtro_segmento() -> str:
    """
    Renderiza el selector global de segmento en el sidebar y devuelve el
    valor seleccionado ("Todos" o el nombre del segmento).

    Debe llamarse **una sola vez por página**, en el punto donde esa página
    ya mostraba su filtro de segmento (normalmente bajo su propio
    encabezado "### Filtros"). No dispara ninguna lectura de datos:
    `obtener_segmentos_disponibles_rapido()` ya está cacheada
    (`st.cache_data`) sobre `agg_metricas_sistema.parquet` (45 KB), el mismo
    agregado pequeño que ya usa el resto de la plataforma — cambiar de
    segmento nunca vuelve a leer los parquet de balance, PyG o indicadores.
    """
    segmentos = ["Todos"] + obtener_segmentos_disponibles_rapido()
    _cargar_valor_persistente()
    return st.sidebar.selectbox(
        "Segmento",
        options=segmentos,
        key=_SPS_SEGMENTO_WIDGET_KEY,
        on_change=_guardar_valor_persistente,
        help="Filtra toda la página por segmento. La selección se mantiene al navegar entre módulos.",
    )
