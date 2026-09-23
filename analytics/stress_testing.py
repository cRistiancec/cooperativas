# -*- coding: utf-8 -*-
"""
Motor de Stress Testing (pruebas de resistencia).

Metodología determinística y transparente de shock de balance, aplicada por
institución a partir del balance real (activos, cartera, depósitos,
patrimonio, fondos disponibles) y de la morosidad oficial vigente (MOR_TOT).

Cada escenario define tres parámetros:
    - `shock_depositos_pct`: % de salida (fuga) de depósitos del público.
    - `shock_mora_pp`: incremento en puntos porcentuales de la morosidad
      total sobre la cartera vigente.
    - `tasa_perdida_incremental` (LGD aproximada): fracción de la cartera
      que migra a mora adicional que se estima como pérdida neta (después
      de garantías), y que se carga contra patrimonio y activos.

Mecánica contable simplificada (para mantener el balance cuadrado):
    salida_efectivo   = depósitos × shock_depositos_pct
    pérdida_crédito   = cartera × shock_mora_pp × tasa_perdida_incremental
    depósitos_post    = depósitos − salida_efectivo
    fondos_disp_post  = fondos_disponibles − salida_efectivo
    patrimonio_post   = patrimonio − pérdida_crédito
    activos_post      = activos − salida_efectivo − pérdida_crédito

Esto es una **simplificación deliberada** para fines de priorización de
revisión, no un modelo regulatorio de capital (tipo Basilea/ICAAP). Se
declara así en la página que consume este módulo.
"""

from __future__ import annotations

from typing import Dict, TypedDict

import pandas as pd


class ParametrosEscenario(TypedDict):
    shock_depositos_pct: float
    shock_mora_pp: float
    tasa_perdida_incremental: float


ESCENARIOS: Dict[str, ParametrosEscenario] = {
    'Base': {
        'shock_depositos_pct': 0.0, 'shock_mora_pp': 0.0, 'tasa_perdida_incremental': 0.0,
    },
    'Moderado': {
        'shock_depositos_pct': 5.0, 'shock_mora_pp': 2.0, 'tasa_perdida_incremental': 0.40,
    },
    'Severo': {
        'shock_depositos_pct': 15.0, 'shock_mora_pp': 5.0, 'tasa_perdida_incremental': 0.50,
    },
    'Extremo': {
        'shock_depositos_pct': 30.0, 'shock_mora_pp': 10.0, 'tasa_perdida_incremental': 0.60,
    },
}

CODIGO_ACTIVOS = '1'
CODIGO_CARTERA = '14'
CODIGO_DEPOSITOS = '21'
CODIGO_PATRIMONIO = '3'
CODIGO_FONDOS_DISPONIBLES = '11'


def construir_panel_balance(df_ranking: pd.DataFrame, fecha, segmento: str = "Todos") -> pd.DataFrame:
    """Pivota el balance agregado a nivel de cooperativa para una fecha dada."""
    mask = df_ranking['fecha'] == fecha
    if segmento != "Todos":
        mask &= df_ranking['segmento'] == segmento
    df_fecha = df_ranking[mask]

    codigos = [CODIGO_ACTIVOS, CODIGO_CARTERA, CODIGO_DEPOSITOS, CODIGO_PATRIMONIO, CODIGO_FONDOS_DISPONIBLES]
    pivote = df_fecha[df_fecha['codigo'].isin(codigos)].pivot_table(
        index=['cooperativa', 'segmento'], columns='codigo', values='valor', aggfunc='first', observed=True
    ).reset_index()

    for col in codigos:
        if col not in pivote.columns:
            pivote[col] = 0.0
    pivote[codigos] = pivote[codigos].fillna(0.0)

    return pivote.rename(columns={
        CODIGO_ACTIVOS: 'activos', CODIGO_CARTERA: 'cartera', CODIGO_DEPOSITOS: 'depositos',
        CODIGO_PATRIMONIO: 'patrimonio', CODIGO_FONDOS_DISPONIBLES: 'fondos_disponibles',
    })


def aplicar_escenario(panel_balance: pd.DataFrame, escenario) -> pd.DataFrame:
    """
    Aplica un escenario de shock al panel de balance y devuelve las columnas
    post-shock junto con los ratios de solvencia y liquidez resultantes.

    `escenario` puede ser el nombre de un escenario predefinido (str, ver
    `ESCENARIOS`) o un dict con los tres parámetros directamente (usado en
    pruebas y para escenarios personalizados).

    ADVERTENCIA METODOLÓGICA (propiedad conocida de los ratios de solvencia):
    cuando el shock de salida de depósitos es grande en relación con la
    pérdida crediticia, la **razón** Patrimonio/Activos puede aumentar
    ligeramente incluso con pérdidas, porque el denominador (Activos) se
    contrae más rápido que el numerador (Patrimonio) al pagar la salida de
    depósitos con caja. Esto **no** significa que la institución esté mejor:
    el Patrimonio en dólares absolutos siempre cae con la pérdida crediticia.
    Es una limitación conocida de los ratios de solvencia no ponderados por
    riesgo (crítica clásica a los ratios de apalancamiento simples). Ver la
    página de Stress Testing para el detalle en dólares junto al ratio.
    """
    parametros = ESCENARIOS[escenario] if isinstance(escenario, str) else escenario
    df = panel_balance.copy()

    salida_efectivo = df['depositos'] * (parametros['shock_depositos_pct'] / 100)
    perdida_credito = df['cartera'] * (parametros['shock_mora_pp'] / 100) * parametros['tasa_perdida_incremental']

    df['salida_efectivo'] = salida_efectivo
    df['perdida_credito'] = perdida_credito
    df['depositos_post'] = df['depositos'] - salida_efectivo
    df['fondos_disponibles_post'] = df['fondos_disponibles'] - salida_efectivo
    df['patrimonio_post'] = df['patrimonio'] - perdida_credito
    df['activos_post'] = df['activos'] - salida_efectivo - perdida_credito

    df['solvencia_pre'] = (df['patrimonio'] / df['activos'] * 100).where(df['activos'] > 0)
    df['solvencia_post'] = (df['patrimonio_post'] / df['activos_post'] * 100).where(df['activos_post'] > 0)

    df['liquidez_pre'] = (df['fondos_disponibles'] / df['depositos'] * 100).where(df['depositos'] > 0)
    df['liquidez_post'] = (df['fondos_disponibles_post'] / df['depositos_post'] * 100).where(df['depositos_post'] > 0)

    df['brecha_liquidez'] = df['fondos_disponibles_post'] < 0
    df['capital_insuficiente'] = df['patrimonio_post'] <= 0

    return df
