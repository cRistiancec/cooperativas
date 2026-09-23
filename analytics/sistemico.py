# -*- coding: utf-8 -*-
"""
Analítica de Riesgo Sistémico.

Limitación declarada: la SEPS no publica en estos archivos exposiciones
interbancarias/intercooperativas ni datos de red (quién le presta a quién),
por lo que **no es posible construir un mapa de conectividad o contagio
real**. En su lugar, este módulo construye un **Índice de Importancia
Sistémica (IIS)** basado en tamaño y sustituibilidad de mercado —los dos
componentes de la metodología D-SIB del Comité de Basilea que sí son
calculables con los datos disponibles (participación de activos, cartera y
depósitos). El componente de "interconectividad" de esa metodología queda
fuera por falta de datos, y así se declara en la página.
"""

from __future__ import annotations

import pandas as pd

CODIGO_ACTIVOS = '1'
CODIGO_CARTERA = '14'
CODIGO_DEPOSITOS = '21'

PESOS_IIS = {
    'participacion_activos': 0.4,
    'participacion_cartera': 0.3,
    'participacion_depositos': 0.3,
}


def calcular_indice_importancia_sistemica(df_ranking: pd.DataFrame, fecha, segmento: str = "Todos") -> pd.DataFrame:
    """
    Índice de Importancia Sistémica (IIS, 0-100) por cooperativa: promedio
    ponderado de las participaciones de mercado en activos, cartera y
    depósitos. 100 = máxima importancia sistémica relativa dentro del universo.
    """
    mask = df_ranking['fecha'] == fecha
    if segmento != "Todos":
        mask &= df_ranking['segmento'] == segmento
    df_fecha = df_ranking[mask]

    pivote = df_fecha[df_fecha['codigo'].isin([CODIGO_ACTIVOS, CODIGO_CARTERA, CODIGO_DEPOSITOS])].pivot_table(
        index=['cooperativa', 'segmento'], columns='codigo', values='valor', aggfunc='first', observed=True
    ).reset_index()

    columnas_valor = [CODIGO_ACTIVOS, CODIGO_CARTERA, CODIGO_DEPOSITOS]
    for col in columnas_valor:
        if col not in pivote.columns:
            pivote[col] = 0.0
    pivote[columnas_valor] = pivote[columnas_valor].fillna(0.0)
    pivote = pivote.rename(columns={
        CODIGO_ACTIVOS: 'activos', CODIGO_CARTERA: 'cartera', CODIGO_DEPOSITOS: 'depositos',
    })

    for base, col in [('activos', 'participacion_activos'), ('cartera', 'participacion_cartera'),
                       ('depositos', 'participacion_depositos')]:
        total = pivote[base].sum()
        pivote[col] = (pivote[base] / total * 100) if total > 0 else 0.0

    pivote['iis'] = (
        pivote['participacion_activos'] * PESOS_IIS['participacion_activos']
        + pivote['participacion_cartera'] * PESOS_IIS['participacion_cartera']
        + pivote['participacion_depositos'] * PESOS_IIS['participacion_depositos']
    )

    # Reescalar 0-100 dentro del universo comparado (el máximo posible del IIS crudo
    # depende del número de instituciones; se normaliza para lectura ejecutiva).
    max_iis = pivote['iis'].max()
    pivote['iis_normalizado'] = (pivote['iis'] / max_iis * 100) if max_iis > 0 else 0.0

    return pivote.sort_values('iis_normalizado', ascending=False)
