# -*- coding: utf-8 -*-
"""
Analítica de Riesgo de Crédito.

Se apoya en los indicadores oficiales de morosidad y cobertura por línea de
cartera (grupos "A - Morosidad" y "A - Cobertura" del pivot cache SEPS) y en
las cuentas de balance de cartera vencida y provisiones.

Limitación declarada: la SEPS no publica en estos archivos información de
crédito a nivel de operación (añadas de originación, días de mora por
operación), por lo que **no es posible construir vintage curves, roll-rate
ni matrices de transición reales** sin esa microdata. Las páginas que usan
este módulo deben declarar esta limitación en vez de aproximarla con datos
inventados.
"""

from __future__ import annotations

from typing import Dict

import pandas as pd

CARTERAS_MOROSIDAD: Dict[str, str] = {
    'MOR_TOT': 'Total',
    'MOR_CONS': 'Consumo',
    'MOR_INMOB': 'Inmobiliaria',
    'MOR_MICRO': 'Microcrédito',
    'MOR_PROD': 'Productivo',
    'MOR_VIV_IP': 'Vivienda Interés Público',
    'MOR_EDU': 'Educativo',
}

CARTERAS_COBERTURA: Dict[str, str] = {
    'COB_TOT': 'Total',
    'COB_CONS': 'Consumo',
    'COB_INMOB': 'Inmobiliaria',
    'COB_MICRO': 'Microcrédito',
    'COB_PROD': 'Productivo',
    'COB_VIV_IP': 'Vivienda Interés Público',
    'COB_EDU': 'Educativo',
}

CODIGO_CARTERA_VENCIDA = '1421'
CODIGO_PROVISION_CARTERA = '1499'
CODIGO_CARTERA_TOTAL = '14'


def construir_panel_morosidad_cobertura(
    df_indicadores: pd.DataFrame, fecha, segmento: str = "Todos"
) -> pd.DataFrame:
    """
    Panel morosidad/cobertura por tipo de cartera para una fecha, agregado a
    nivel de sistema (promedio simple entre cooperativas con dato disponible).
    """
    df_f = df_indicadores[df_indicadores['fecha'] == fecha]
    if segmento != "Todos":
        df_f = df_f[df_f['segmento'] == segmento]

    codigos = list(CARTERAS_MOROSIDAD) + list(CARTERAS_COBERTURA)
    df_f = df_f[df_f['codigo'].isin(codigos)]

    resumen = df_f.groupby('codigo', observed=True)['valor'].mean().reset_index()
    resumen['valor_pct'] = resumen['valor'] * 100
    return resumen


def construir_serie_cartera_vencida(df_balance: pd.DataFrame, segmento: str = "Todos") -> pd.DataFrame:
    """
    Serie temporal del sistema para cartera vencida (1421) y provisión de
    cartera (1499), en millones de USD. Espera un DataFrame de balance ya
    filtrado a estos dos códigos (ver `utils.data_loader.cargar_balance_por_codigos`)
    o el balance completo — el filtro por código es idempotente en ambos casos.
    """
    df_f = df_balance[df_balance['codigo'].isin([CODIGO_CARTERA_VENCIDA, CODIGO_PROVISION_CARTERA])]
    if segmento != "Todos":
        df_f = df_f[df_f['segmento'] == segmento]

    serie = df_f.groupby(['fecha', 'codigo'], observed=True)['valor'].sum().reset_index()
    serie['valor_millones'] = serie['valor'] / 1_000_000
    etiquetas = {CODIGO_CARTERA_VENCIDA: 'Cartera Vencida', CODIGO_PROVISION_CARTERA: 'Provisión de Cartera'}
    serie['cuenta'] = serie['codigo'].map(etiquetas)
    return serie.sort_values('fecha')
