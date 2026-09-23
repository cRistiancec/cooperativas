# -*- coding: utf-8 -*-
"""
Motor de Alertas Tempranas.

Evalúa, por cooperativa, un conjunto de reglas sobre indicadores oficiales
(`config/umbrales_alerta.py`) más la variación interanual de depósitos, y
produce un semáforo agregado y un ranking de deterioro. Las reglas son
transparentes y auditables (ver el módulo de configuración); esto no
reemplaza el juicio experto de un analista de riesgos, es una capa de
priorización para enfocar la revisión manual.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from config.umbrales_alerta import (
    REGLAS_ALERTA,
    UMBRAL_CAIDA_DEPOSITOS_AMARILLA,
    UMBRAL_CAIDA_DEPOSITOS_ROJA,
    UMBRAL_NUM_ALERTAS_AMARILLO,
    UMBRAL_NUM_ALERTAS_ROJO,
)


def _evaluar_regla(valor: float, regla: dict) -> int:
    """Devuelve 0 (sin alerta), 1 (amarilla) o 2 (roja) para un valor e indicador."""
    if pd.isna(valor):
        return 0

    if regla['direccion'] == 'mayor_es_peor':
        if valor >= regla['alerta_roja']:
            return 2
        if valor >= regla['alerta_amarilla']:
            return 1
        return 0

    # menor_es_peor
    if valor <= regla['alerta_roja']:
        return 2
    if valor <= regla['alerta_amarilla']:
        return 1
    return 0


def evaluar_alertas(
    df_indicadores: pd.DataFrame,
    fecha,
    segmento: str = "Todos",
    df_crecimiento_depositos: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """
    Evalúa las reglas de alerta para todas las cooperativas en una fecha.

    Args:
        df_indicadores: DataFrame de `cargar_indicadores()`.
        fecha: fecha de corte.
        segmento: filtro de segmento.
        df_crecimiento_depositos: salida opcional de
            `obtener_crecimiento_anual(..., codigo='21')`, con columnas
            cooperativa y crecimiento (%).

    Returns:
        DataFrame por cooperativa con una columna de severidad (0/1/2) por
        regla, el conteo de alertas activas, y el semáforo agregado.
    """
    codigos = list(REGLAS_ALERTA.keys())
    df_f = df_indicadores[(df_indicadores['fecha'] == fecha) & (df_indicadores['codigo'].isin(codigos))]
    if segmento != "Todos":
        df_f = df_f[df_f['segmento'] == segmento]

    if df_f.empty:
        return pd.DataFrame()

    pivote = df_f.pivot_table(
        index=['cooperativa', 'segmento'], columns='codigo', values='valor', aggfunc='first'
    ).reset_index()

    columnas_severidad = []
    for codigo, regla in REGLAS_ALERTA.items():
        if codigo not in pivote.columns:
            continue
        col_sev = f"sev_{codigo}"
        pivote[col_sev] = pivote[codigo].apply(lambda v: _evaluar_regla(v, regla))
        columnas_severidad.append(col_sev)

    if df_crecimiento_depositos is not None and not df_crecimiento_depositos.empty:
        crecim = df_crecimiento_depositos[['cooperativa', 'crecimiento']].rename(
            columns={'crecimiento': 'crecimiento_depositos'}
        )
        pivote = pivote.merge(crecim, on='cooperativa', how='left')

        def _severidad_depositos(v):
            if pd.isna(v):
                return 0
            if v <= UMBRAL_CAIDA_DEPOSITOS_ROJA:
                return 2
            if v <= UMBRAL_CAIDA_DEPOSITOS_AMARILLA:
                return 1
            return 0

        pivote['sev_DEPOSITOS'] = pivote['crecimiento_depositos'].apply(_severidad_depositos)
        columnas_severidad.append('sev_DEPOSITOS')

    pivote['alertas_rojas'] = (pivote[columnas_severidad] == 2).sum(axis=1)
    pivote['alertas_amarillas'] = (pivote[columnas_severidad] == 1).sum(axis=1)
    pivote['total_alertas_activas'] = (pivote[columnas_severidad] > 0).sum(axis=1)

    def _semaforo(fila) -> str:
        if fila['alertas_rojas'] > 0 or fila['total_alertas_activas'] >= UMBRAL_NUM_ALERTAS_ROJO:
            return 'crit'
        if fila['total_alertas_activas'] >= UMBRAL_NUM_ALERTAS_AMARILLO:
            return 'warn'
        return 'ok'

    pivote['semaforo'] = pivote.apply(_semaforo, axis=1)

    return pivote.sort_values(
        ['alertas_rojas', 'alertas_amarillas'], ascending=[False, False]
    )
