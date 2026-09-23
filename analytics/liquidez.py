# -*- coding: utf-8 -*-
"""
Analítica de Riesgo de Liquidez.

La SEPS reporta un único indicador oficial de liquidez en el pivot cache
CAMEL: `LIQ` = Fondos Disponibles / Depósitos de Corto Plazo (indicadores.parquet).
Este módulo lo complementa con una métrica de **liquidez ampliada**, calculada
directamente de las cuentas de balance (Fondos Disponibles + Inversiones) /
Obligaciones con el Público, siguiendo la práctica supervisora estándar de
sumar activos líquidos de realización inmediata. Se etiqueta siempre como
"calculada" para distinguirla del indicador oficial `LIQ`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

CODIGO_FONDOS_DISPONIBLES = '11'
CODIGO_INVERSIONES = '13'
CODIGO_DEPOSITOS = '21'


def calcular_liquidez_ampliada(df_ranking: pd.DataFrame, fecha, segmento: str = "Todos") -> pd.DataFrame:
    """
    Calcula (Fondos Disponibles + Inversiones) / Depósitos del Público, por
    cooperativa, para una fecha dada.

    Args:
        df_ranking: salida de `cargar_ranking_cooperativas()`.
        fecha: fecha de corte.
        segmento: filtro de segmento ("Todos" = sin filtro).

    Returns:
        DataFrame con columnas: cooperativa, segmento, fondos_disponibles,
        inversiones, depositos, liquidez_ampliada (%).
    """
    mask = df_ranking['fecha'] == fecha
    if segmento != "Todos":
        mask &= df_ranking['segmento'] == segmento
    df_fecha = df_ranking[mask]

    pivote = df_fecha[df_fecha['codigo'].isin(
        [CODIGO_FONDOS_DISPONIBLES, CODIGO_INVERSIONES, CODIGO_DEPOSITOS]
    )].pivot_table(
        index=['cooperativa', 'segmento'], columns='codigo', values='valor', aggfunc='first', observed=True
    ).reset_index()

    columnas_valor = [CODIGO_FONDOS_DISPONIBLES, CODIGO_INVERSIONES, CODIGO_DEPOSITOS]
    for col in columnas_valor:
        if col not in pivote.columns:
            pivote[col] = 0.0
    pivote[columnas_valor] = pivote[columnas_valor].fillna(0.0)

    pivote = pivote.rename(columns={
        CODIGO_FONDOS_DISPONIBLES: 'fondos_disponibles',
        CODIGO_INVERSIONES: 'inversiones',
        CODIGO_DEPOSITOS: 'depositos',
    })

    activos_liquidos = pivote['fondos_disponibles'] + pivote['inversiones']
    pivote['liquidez_ampliada'] = np.where(
        pivote['depositos'] > 0, activos_liquidos / pivote['depositos'] * 100, np.nan
    )

    return pivote.dropna(subset=['liquidez_ampliada'])


def calcular_cobertura_retiro(fondos_disponibles_millones: float, salida_diaria_estimada_millones: float) -> float:
    """
    Días de cobertura ante una salida de depósitos estimada por el usuario
    (simulador de estrés simple, informativo). Evita división por cero.
    """
    if salida_diaria_estimada_millones <= 0:
        return float('inf')
    return fondos_disponibles_millones / salida_diaria_estimada_millones
