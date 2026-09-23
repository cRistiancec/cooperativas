# -*- coding: utf-8 -*-
"""
Analítica de Riesgo de Concentración.

Métricas estándar de concentración de mercado (HHI, CR-N, curva de Lorenz y
coeficiente de Gini) calculadas sobre participaciones de mercado reales,
derivadas de `agg_ranking_cooperativas.parquet`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def calcular_hhi(valores: pd.Series) -> float:
    """
    Índice de Herfindahl-Hirschman (HHI) sobre una serie de valores absolutos.

    Escala 0-10.000 (convención estándar de agencias de competencia).
    HHI < 1.500: mercado no concentrado. 1.500-2.500: concentración moderada.
    > 2.500: alta concentración.
    """
    valores = valores.dropna()
    total = valores.sum()
    if total <= 0:
        return 0.0
    participaciones_pct = (valores / total) * 100
    return float((participaciones_pct ** 2).sum())


def calcular_cr(valores: pd.Series, n: int) -> float:
    """Ratio de concentración CR-N: participación conjunta de las N mayores instituciones (%)."""
    valores = valores.dropna().sort_values(ascending=False)
    total = valores.sum()
    if total <= 0:
        return 0.0
    return float(valores.head(n).sum() / total * 100)


def curva_lorenz(valores: pd.Series) -> pd.DataFrame:
    """
    Curva de Lorenz: % acumulado de instituciones (eje x) vs. % acumulado del
    valor total (eje y), ordenado de menor a mayor. Incluye el punto (0,0).
    """
    valores = valores.dropna().sort_values(ascending=True).reset_index(drop=True)
    n = len(valores)
    if n == 0 or valores.sum() <= 0:
        return pd.DataFrame({'pct_instituciones': [0, 1], 'pct_valor_acumulado': [0, 1]})

    pct_instituciones = np.arange(1, n + 1) / n
    pct_valor_acumulado = valores.cumsum() / valores.sum()

    return pd.DataFrame({
        'pct_instituciones': np.concatenate([[0], pct_instituciones]),
        'pct_valor_acumulado': np.concatenate([[0], pct_valor_acumulado]),
    })


def coeficiente_gini(valores: pd.Series) -> float:
    """Coeficiente de Gini (0 = igualdad perfecta, 1 = concentración máxima)."""
    valores = valores.dropna().sort_values(ascending=True).values
    n = len(valores)
    if n == 0 or valores.sum() <= 0:
        return 0.0
    indices = np.arange(1, n + 1)
    return float((2 * (indices * valores).sum() / (n * valores.sum())) - (n + 1) / n)


def clasificar_hhi(hhi: float) -> str:
    """Clasifica el HHI según los umbrales estándar de agencias de competencia."""
    if hhi < 1500:
        return "No concentrado"
    if hhi < 2500:
        return "Concentración moderada"
    return "Alta concentración"
