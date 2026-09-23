# -*- coding: utf-8 -*-
"""
Analítica de Riesgo de Solvencia.

Usa los indicadores oficiales de capital/vulnerabilidad patrimonial del
pivot cache SEPS (FK, FI, CAP_NETO, VULN_PAT, CART_IMPR_PAT, SUF_PAT) y el
ratio Patrimonio/Activos calculado directamente del balance (cuentas 3 y 1).

Ninguno de los anteriores es el ratio de Solvencia REGULATORIO (Patrimonio
Técnico Constituido / Activos Ponderados por Riesgo, mínimo 9% JPRF, ficha
SEPS 62-63). Ese ratio se calcula en `evaluar_solvencia_oficial()` a partir
de `cargar_solvencia()` (fuente `master_data/solvencia.parquet`, boletín
"Patrimonio Técnico" — cobertura Segmento 1 + Mutualistas + FINANCOOP
únicamente; ver docs/RIESGO_METODOLOGIA.md §3.2). Es el único umbral de esta
plataforma que es un límite regulatorio verificado, no un umbral analítico.
"""

from __future__ import annotations

import pandas as pd

CODIGO_PATRIMONIO = '3'
CODIGO_ACTIVOS = '1'

UMBRAL_SOLVENCIA_REGULATORIO = 0.09  # 9% — Patrimonio Técnico Requerido (ficha SEPS 63), JPRF

INDICADORES_SOLVENCIA = ['SUF_PAT', 'FK', 'FI', 'CAP_NETO', 'VULN_PAT', 'CART_IMPR_PAT']

ETIQUETAS_SOLVENCIA = {
    'SUF_PAT': 'Suficiencia Patrimonial (Patrim.+Result. / Act. Inmovilizados)',
    'FK': 'FK — Fondos de Capital',
    'FI': 'FI — Fondos de Inversión / Fondeo',
    'CAP_NETO': 'Índice de Capitalización Neto',
    'VULN_PAT': 'Vulnerabilidad Patrimonial (Cart. Improd. Descub. / Patrimonio)',
    'CART_IMPR_PAT': 'Cartera Improductiva / Patrimonio',
}


def calcular_patrimonio_sobre_activos(df_ranking: pd.DataFrame, fecha, segmento: str = "Todos") -> pd.DataFrame:
    """Ratio Patrimonio / Activos Totales por cooperativa, calculado del balance agregado."""
    mask = df_ranking['fecha'] == fecha
    if segmento != "Todos":
        mask &= df_ranking['segmento'] == segmento
    df_fecha = df_ranking[mask]

    pivote = df_fecha[df_fecha['codigo'].isin([CODIGO_PATRIMONIO, CODIGO_ACTIVOS])].pivot_table(
        index=['cooperativa', 'segmento'], columns='codigo', values='valor', aggfunc='first', observed=True
    ).reset_index()

    for col in [CODIGO_PATRIMONIO, CODIGO_ACTIVOS]:
        if col not in pivote.columns:
            pivote[col] = 0.0
    pivote = pivote.rename(columns={CODIGO_PATRIMONIO: 'patrimonio', CODIGO_ACTIVOS: 'activos'})
    pivote = pivote[pivote['activos'] > 0]
    pivote['patrimonio_sobre_activos'] = pivote['patrimonio'] / pivote['activos'] * 100
    return pivote


def evaluar_solvencia_oficial(df_solvencia: pd.DataFrame, fecha) -> pd.DataFrame:
    """
    Evalúa el ratio de Solvencia OFICIAL de la SEPS (PTC/APPR) contra su
    mínimo regulatorio (9%, `UMBRAL_SOLVENCIA_REGULATORIO`) para una fecha.

    A diferencia de `evaluar_alertas()` (analytics/alertas.py, umbrales
    percentílicos/analíticos), este es el único chequeo de la plataforma
    contra un límite regulatorio real y verificado (ficha SEPS 63).

    Cobertura: únicamente entidades presentes en `df_solvencia` (Segmento 1,
    Mutualistas, Caja Central FINANCOOP). No emite ningún juicio sobre
    Segmento 2/3 — para esos segmentos no existe fuente oficial de Solvencia.

    Devuelve columnas: fecha, ruc, cooperativa, grupo_fuente, solvencia,
    cumple_minimo_regulatorio, brecha_pp (puntos porcentuales por debajo del
    9%, 0 si cumple).
    """
    columnas = ['fecha', 'ruc', 'cooperativa', 'grupo_fuente', 'solvencia',
                'cumple_minimo_regulatorio', 'brecha_pp']
    if df_solvencia is None or df_solvencia.empty:
        return pd.DataFrame(columns=columnas)

    df_f = df_solvencia[df_solvencia['fecha'] == fecha].copy()
    if df_f.empty:
        return pd.DataFrame(columns=columnas)

    df_f['cumple_minimo_regulatorio'] = df_f['solvencia'] >= UMBRAL_SOLVENCIA_REGULATORIO
    df_f['brecha_pp'] = ((UMBRAL_SOLVENCIA_REGULATORIO - df_f['solvencia']) * 100).clip(lower=0)

    return df_f[columnas].sort_values('solvencia')
