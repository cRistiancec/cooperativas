# -*- coding: utf-8 -*-
"""
Score compuesto CAMEL por institución.

Metodología (transparente y documentada, no una caja negra):

1. Para cada indicador oficial relevante, se calcula el **percentil** de cada
   cooperativa dentro del universo comparado (sistema o segmento) en la
   fecha de corte. El percentil se orienta siempre para que **100 = mejor
   desempeño relativo, 0 = peor**, usando el sentido correcto según si un
   valor alto es deseable (p. ej. ROE, cobertura) o indeseable (p. ej.
   morosidad, gastos operativos).
2. Los percentiles de los indicadores de una misma categoría (C, A, M, E, L)
   se promedian con igual ponderación → **score de categoría (0-100)**.
3. El **score compuesto** es el promedio simple de las 5 categorías CAMEL
   (igual ponderación entre letras). Es una elección metodológica explícita,
   ajustable en fases posteriores si la institución define pesos oficiales.

Nota sobre "S": la SEPS no publica en estos archivos indicadores de
sensibilidad al riesgo de mercado (duración, brechas de tasa, VaR), por lo
que el score cubre las 5 letras clásicas **C-A-M-E-L**, no "CAMELS" completo.
La dimensión adicional "V - Vulnerabilidad Patrimonial" que sí reporta la
SEPS se muestra por separado, como métrica complementaria de capital.
"""

from __future__ import annotations

from typing import Dict, List

import pandas as pd

# Indicador -> True si "mayor valor = mejor desempeño"
DIRECCION_INDICADOR: Dict[str, bool] = {
    # C - Capital
    'SUF_PAT': True,
    # A - Calidad de Activos
    'ACT_PROD': True, 'AP_PC': True, 'ACT_IMPR': False,
    # A - Morosidad (menor es mejor)
    'MOR_TOT': False,
    # A - Cobertura (mayor es mejor)
    'COB_TOT': True,
    # M - Management (menor gasto relativo es mejor)
    'GO_ACT': False, 'GO_MNF': False, 'GP_ACT': False,
    # E - Earnings
    'ROE': True, 'ROA': True,
    # L - Liquidez
    'LIQ': True,
    # V - Vulnerabilidad (complementario, no entra al score CAMEL)
    'FK': True, 'FI': True, 'CAP_NETO': True,
    'VULN_PAT': False, 'CART_IMPR_PAT': False,
}

CATEGORIAS_CAMEL: Dict[str, List[str]] = {
    'C': ['SUF_PAT'],
    'A': ['ACT_PROD', 'AP_PC', 'ACT_IMPR', 'MOR_TOT', 'COB_TOT'],
    'M': ['GO_ACT', 'GO_MNF', 'GP_ACT'],
    'E': ['ROE', 'ROA'],
    'L': ['LIQ'],
}

INDICADORES_VULNERABILIDAD = ['FK', 'FI', 'CAP_NETO', 'VULN_PAT', 'CART_IMPR_PAT']


def _percentil_orientado(serie: pd.Series, mayor_es_mejor: bool) -> pd.Series:
    """Percentil 0-100 de una serie, orientado para que 100 = mejor desempeño."""
    rangos = serie.rank(pct=True, na_option='keep') * 100
    return rangos if mayor_es_mejor else (100 - rangos)


def calcular_score_camel(df_indicadores: pd.DataFrame, fecha, segmento: str = "Todos") -> pd.DataFrame:
    """
    Calcula el score CAMEL (0-100) por cooperativa para una fecha de corte.

    Returns:
        DataFrame con columnas: cooperativa, segmento, score_C, score_A,
        score_M, score_E, score_L, score_total, y las columnas de
        vulnerabilidad (V_*) como métricas complementarias en percentil.
    """
    todos_los_codigos = [c for lista in CATEGORIAS_CAMEL.values() for c in lista] + INDICADORES_VULNERABILIDAD

    df_f = df_indicadores[(df_indicadores['fecha'] == fecha) & (df_indicadores['codigo'].isin(todos_los_codigos))]
    if segmento != "Todos":
        df_f = df_f[df_f['segmento'] == segmento]

    if df_f.empty:
        return pd.DataFrame()

    pivote = df_f.pivot_table(
        index=['cooperativa', 'segmento'], columns='codigo', values='valor', aggfunc='first'
    ).reset_index()

    percentiles = pivote[['cooperativa', 'segmento']].copy()
    for codigo in todos_los_codigos:
        if codigo in pivote.columns:
            percentiles[f"pct_{codigo}"] = _percentil_orientado(
                pivote[codigo], DIRECCION_INDICADOR.get(codigo, True)
            )

    for letra, codigos in CATEGORIAS_CAMEL.items():
        columnas_pct = [f"pct_{c}" for c in codigos if f"pct_{c}" in percentiles.columns]
        percentiles[f"score_{letra}"] = percentiles[columnas_pct].mean(axis=1) if columnas_pct else pd.NA

    columnas_score = [f"score_{letra}" for letra in CATEGORIAS_CAMEL if f"score_{letra}" in percentiles.columns]
    percentiles['score_total'] = percentiles[columnas_score].mean(axis=1)

    columnas_vuln = [f"pct_{c}" for c in INDICADORES_VULNERABILIDAD if f"pct_{c}" in percentiles.columns]
    if columnas_vuln:
        percentiles['score_vulnerabilidad'] = percentiles[columnas_vuln].mean(axis=1)

    return percentiles.sort_values('score_total', ascending=False)


def clasificar_score(score: float) -> str:
    """Clasificación cualitativa del score compuesto (0-100)."""
    if pd.isna(score):
        return "Sin datos"
    if score >= 75:
        return "Sólido"
    if score >= 50:
        return "Adecuado"
    if score >= 25:
        return "Vigilancia"
    return "Crítico"
