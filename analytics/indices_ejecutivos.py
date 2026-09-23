# -*- coding: utf-8 -*-
"""
Índices ejecutivos de segundo nivel.

No son una migración del script R de referencia (el R no los define — son
indicadores nuevos, pedidos explícitamente en la ampliación del proyecto).
Metodología: percentiles orientados y promedio simple por dimensión, el
mismo enfoque transparente y ya documentado que usa
`analytics.camels_score.calcular_score_camel` — reutilizado aquí, no
reimplementado, precisamente para no tener dos convenciones de "qué
significa un score 0-100" conviviendo en la plataforma. Cada índice
combina indicadores que **ya existen** (oficiales SEPS o migrados en la
Fase 2.3): no se inventa ningún dato, solo se combinan los ya calculados.

Los 6 índices pedidos, y de qué se componen:

    Score Financiero Integral  → liquidez + solvencia + rentabilidad +
                                  cobertura + morosidad + crecimiento
    Índice de Vulnerabilidad   → z-score de morosidad, vulnerabilidad
                                  patrimonial y dependencia de ingresos no
                                  recurrentes (ver `analytics.rentabilidad`)
    Índice de Fortaleza        → patrimonio, liquidez, cobertura, ROA, ROE,
                                  crecimiento
    Índice de Resiliencia      → reutiliza `analytics.stress_testing`: percentil
                                  de la solvencia post-shock en el escenario
                                  "Severo"
    Índice de Estabilidad      → nivel + consistencia temporal (coeficiente de
                                  variación en los últimos 12 meses) de
                                  liquidez, morosidad y rentabilidad
    Índice de Riesgo Integral  → combina Score Financiero, Vulnerabilidad y el
                                  conteo de alertas activas (`analytics.alertas`)
                                  en una escala 0-100 con 7 bandas de
                                  clasificación

Todas las funciones son deterministas y auditables — ninguna usa modelos de
caja negra. Las ponderaciones están explícitas en el código, documentadas
como una elección metodológica inicial (no un límite regulatorio), ajustable
por Riesgos y Estudios sin tocar la estructura del módulo.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from analytics.camels_score import _percentil_orientado  # reutilizado, no reimplementado
from analytics.rentabilidad import calcular_roe_ajustado
from analytics.stress_testing import aplicar_escenario, construir_panel_balance

# =============================================================================
# SCORE FINANCIERO INTEGRAL
# =============================================================================

# codigo de indicadores.parquet -> (dimension, mayor_es_mejor)
_DIMENSIONES_SCORE_INTEGRAL = {
    'LIQ': ('liquidez', True),
    'SUF_PAT': ('solvencia', True),
    'ROE': ('rentabilidad', True),
    'COB_TOT': ('cobertura', True),
    'MOR_TOT': ('morosidad', False),
}


def calcular_score_financiero_integral(
    df_indicadores: pd.DataFrame, df_crecimiento: pd.DataFrame, fecha, segmento: str = "Todos"
) -> pd.DataFrame:
    """
    Score Financiero Integral (0-100), por cooperativa: percentil orientado
    (100 = mejor desempeño relativo) de liquidez, solvencia, rentabilidad,
    cobertura y morosidad —de `indicadores.parquet`— más crecimiento de
    cartera interanual —de `analytics.crecimiento.crecimiento_colocaciones`—,
    promediados con igual ponderación.

    Args:
        df_indicadores: salida de `cargar_indicadores()`.
        df_crecimiento: salida de `crecimiento_colocaciones(fecha, fecha - 1 año, segmento)`,
            con columnas `cooperativa` y `crecimiento_pct`.
        fecha, segmento: corte de análisis.
    """
    codigos = list(_DIMENSIONES_SCORE_INTEGRAL.keys())
    df_f = df_indicadores[(df_indicadores['fecha'] == fecha) & (df_indicadores['codigo'].isin(codigos))]
    if segmento != "Todos":
        df_f = df_f[df_f['segmento'] == segmento]
    if df_f.empty:
        return pd.DataFrame()

    pivote = df_f.pivot_table(
        index=['cooperativa', 'segmento'], columns='codigo', values='valor', aggfunc='first'
    ).reset_index()

    percentiles = pivote[['cooperativa', 'segmento']].copy()
    columnas_pct = []
    for codigo, (dimension, mayor_es_mejor) in _DIMENSIONES_SCORE_INTEGRAL.items():
        if codigo in pivote.columns:
            col = f"pct_{dimension}"
            percentiles[col] = _percentil_orientado(pivote[codigo], mayor_es_mejor)
            columnas_pct.append(col)

    if not df_crecimiento.empty:
        crecim = df_crecimiento[['cooperativa', 'crecimiento_pct']].copy()
        crecim['pct_crecimiento'] = _percentil_orientado(crecim['crecimiento_pct'], mayor_es_mejor=True)
        percentiles = percentiles.merge(crecim[['cooperativa', 'pct_crecimiento']], on='cooperativa', how='left')
        columnas_pct.append('pct_crecimiento')

    percentiles['score_financiero_integral'] = percentiles[columnas_pct].mean(axis=1, skipna=True)
    return percentiles.sort_values('score_financiero_integral', ascending=False)


# =============================================================================
# ÍNDICE DE VULNERABILIDAD
# =============================================================================

_INDICADORES_VULNERABILIDAD_Z = ['MOR_TOT', 'VULN_PAT', 'CART_IMPR_PAT']


def _z_score(serie: pd.Series) -> pd.Series:
    """z-score cross-seccional: cuántas desviaciones estándar por encima/debajo de la media del universo."""
    media, desvio = serie.mean(), serie.std(ddof=0)
    if not desvio or pd.isna(desvio) or desvio == 0:
        return pd.Series(0.0, index=serie.index)
    return (serie - media) / desvio


def calcular_indice_vulnerabilidad(
    df_indicadores: pd.DataFrame, df_pyg: pd.DataFrame, df_ranking: pd.DataFrame, fecha, segmento: str = "Todos"
) -> pd.DataFrame:
    """
    Índice de Vulnerabilidad (0-100, 100 = más vulnerable), por cooperativa.

    Combina, en z-score, tres señales de fragilidad —todas "mayor valor =
    más vulnerable":

    - `MOR_TOT` (morosidad total, oficial SEPS)
    - `VULN_PAT` (cartera improductiva descubierta / patrimonio, oficial SEPS)
    - **brecha de dependencia de ingresos no recurrentes**: `ROE oficial −
      ROE ajustado` (ver `analytics.rentabilidad.calcular_roe_ajustado`) — una
      brecha grande indica que la rentabilidad reportada depende de partidas
      no recurrentes ("otros ingresos"), no de la operación central. Esta
      señal es nueva (no está en el script R ni la publica la SEPS por
      separado): es exactamente el tipo de indicador de segundo nivel que
      esta ampliación pidió construir "a partir de los indicadores existentes".

    El promedio de los tres z-scores se reescala a percentil 0-100 dentro
    del universo comparado, para que sea directamente comparable con los
    demás índices (todos en la misma escala 0-100).
    """
    codigos = _INDICADORES_VULNERABILIDAD_Z
    df_f = df_indicadores[(df_indicadores['fecha'] == fecha) & (df_indicadores['codigo'].isin(codigos))]
    if segmento != "Todos":
        df_f = df_f[df_f['segmento'] == segmento]
    if df_f.empty:
        return pd.DataFrame()

    pivote = df_f.pivot_table(
        index=['cooperativa', 'segmento'], columns='codigo', values='valor', aggfunc='first'
    ).reset_index()

    z = pivote[['cooperativa', 'segmento']].copy()
    columnas_z = []
    for codigo in codigos:
        if codigo in pivote.columns:
            col = f"z_{codigo}"
            z[col] = _z_score(pivote[codigo])
            columnas_z.append(col)

    roe_oficial = df_indicadores[
        (df_indicadores['fecha'] == fecha) & (df_indicadores['codigo'] == 'ROE')
    ][['cooperativa', 'valor']].rename(columns={'valor': 'roe_oficial'})
    # df_pyg/df_ranking son opcionales: si no se pasan (o vienen vacíos), el
    # índice se calcula solo con MOR_TOT/VULN_PAT/CART_IMPR_PAT, sin la señal
    # de brecha de ROE — evita el KeyError de indexar 'codigo' en un
    # DataFrame vacío sin columnas.
    roe_adj = (
        calcular_roe_ajustado(df_ranking, df_pyg, fecha, segmento)
        if not df_pyg.empty and not df_ranking.empty
        else pd.DataFrame()
    )
    if not roe_oficial.empty and not roe_adj.empty:
        brecha = roe_oficial.merge(roe_adj, on='cooperativa', how='inner')
        brecha['brecha_roe'] = brecha['roe_oficial'] * 100 - brecha['roe_ajustado']
        brecha['z_brecha_roe'] = _z_score(brecha['brecha_roe'])
        z = z.merge(brecha[['cooperativa', 'z_brecha_roe']], on='cooperativa', how='left')
        columnas_z.append('z_brecha_roe')

    z['z_promedio'] = z[columnas_z].mean(axis=1, skipna=True)
    # `_percentil_orientado(serie, mayor_es_mejor)` traduce "un valor crudo alto
    # produce una salida alta" cuando mayor_es_mejor=True — no es un juicio de
    # valor. Las tres señales en `z_promedio` ya están definidas como "mayor =
    # más vulnerable", y ese es exactamente el sentido que debe tener la salida
    # (100 = más vulnerable) — por eso mayor_es_mejor=True aquí, no False.
    z['indice_vulnerabilidad'] = _percentil_orientado(z['z_promedio'], mayor_es_mejor=True)
    return z.sort_values('indice_vulnerabilidad', ascending=False)


# =============================================================================
# ÍNDICE DE FORTALEZA
# =============================================================================

_DIMENSIONES_FORTALEZA = {
    'SUF_PAT': True, 'LIQ': True, 'COB_TOT': True, 'ROA': True, 'ROE': True,
}


def calcular_indice_fortaleza(
    df_indicadores: pd.DataFrame, df_crecimiento_activos: pd.DataFrame, fecha, segmento: str = "Todos"
) -> pd.DataFrame:
    """
    Índice de Fortaleza (0-100, 100 = más fuerte), por cooperativa: percentil
    orientado de patrimonio (`SUF_PAT`), liquidez (`LIQ`), cobertura
    (`COB_TOT`), `ROA`, `ROE` y crecimiento de activos interanual.

    `df_crecimiento_activos`: salida de `analytics.crecimiento.crecimiento_activos(fecha, fecha - 1 año, segmento)`.
    """
    codigos = list(_DIMENSIONES_FORTALEZA.keys())
    df_f = df_indicadores[(df_indicadores['fecha'] == fecha) & (df_indicadores['codigo'].isin(codigos))]
    if segmento != "Todos":
        df_f = df_f[df_f['segmento'] == segmento]
    if df_f.empty:
        return pd.DataFrame()

    pivote = df_f.pivot_table(
        index=['cooperativa', 'segmento'], columns='codigo', values='valor', aggfunc='first'
    ).reset_index()

    percentiles = pivote[['cooperativa', 'segmento']].copy()
    columnas_pct = []
    for codigo, mayor_es_mejor in _DIMENSIONES_FORTALEZA.items():
        if codigo in pivote.columns:
            col = f"pct_{codigo}"
            percentiles[col] = _percentil_orientado(pivote[codigo], mayor_es_mejor)
            columnas_pct.append(col)

    if df_crecimiento_activos is not None and not df_crecimiento_activos.empty:
        crecim = df_crecimiento_activos[['cooperativa', 'crecimiento_pct']].copy()
        crecim['pct_crecimiento_activos'] = _percentil_orientado(crecim['crecimiento_pct'], mayor_es_mejor=True)
        percentiles = percentiles.merge(
            crecim[['cooperativa', 'pct_crecimiento_activos']], on='cooperativa', how='left'
        )
        columnas_pct.append('pct_crecimiento_activos')

    percentiles['indice_fortaleza'] = percentiles[columnas_pct].mean(axis=1, skipna=True)
    return percentiles.sort_values('indice_fortaleza', ascending=False)


# =============================================================================
# ÍNDICE DE RESILIENCIA
# =============================================================================

def calcular_indice_resiliencia(
    df_ranking: pd.DataFrame, fecha, segmento: str = "Todos", escenario: str = "Severo"
) -> pd.DataFrame:
    """
    Índice de Resiliencia (0-100, 100 = más resiliente), por cooperativa:
    percentil de la solvencia post-shock bajo el escenario de stress testing
    indicado (por defecto "Severo" — ver `analytics.stress_testing.ESCENARIOS`),
    con una penalización si el shock deja capital insuficiente o brecha de
    liquidez.

    Reutiliza el motor de stress testing existente
    (`construir_panel_balance` + `aplicar_escenario`) en vez de duplicar la
    mecánica de shock — es, literalmente, "capacidad para soportar escenarios
    adversos" aplicando el módulo que la plataforma ya tiene para eso.
    """
    panel = construir_panel_balance(df_ranking, fecha, segmento)
    if panel.empty:
        return pd.DataFrame()

    resultado = aplicar_escenario(panel, escenario)
    resultado['pct_solvencia_post'] = _percentil_orientado(resultado['solvencia_post'], mayor_es_mejor=True)

    penalizacion = pd.Series(0.0, index=resultado.index)
    penalizacion += resultado['capital_insuficiente'].astype(float) * 20.0
    penalizacion += resultado['brecha_liquidez'].astype(float) * 10.0
    resultado['indice_resiliencia'] = (resultado['pct_solvencia_post'] - penalizacion).clip(lower=0, upper=100)

    columnas = ['cooperativa', 'segmento', 'solvencia_pre', 'solvencia_post',
                'capital_insuficiente', 'brecha_liquidez', 'indice_resiliencia']
    return resultado[columnas].sort_values('indice_resiliencia', ascending=False)


# =============================================================================
# ÍNDICE DE ESTABILIDAD
# =============================================================================

_INDICADORES_ESTABILIDAD = {'LIQ': True, 'MOR_TOT': False, 'ROE': True}
MESES_VENTANA_ESTABILIDAD = 12


def calcular_indice_estabilidad(
    df_indicadores: pd.DataFrame, fecha, segmento: str = "Todos", meses_ventana: int = MESES_VENTANA_ESTABILIDAD
) -> pd.DataFrame:
    """
    Índice de Estabilidad (0-100, 100 = más estable), por cooperativa:
    promedio de dos componentes con igual ponderación —

    - **Nivel**: percentil orientado de liquidez, morosidad y rentabilidad
      en la fecha de corte (igual que los demás índices).
    - **Consistencia**: percentil orientado (100 = menos volátil) del
      coeficiente de variación de esos mismos indicadores en los últimos
      `meses_ventana` meses — una cooperativa cuya morosidad oscila mucho
      mes a mes es menos "estable" que una con el mismo nivel promedio pero
      consistente, aunque el Score Financiero Integral (que solo mira el
      corte actual) no distinga entre ambas. Esta es la diferencia
      metodológica deliberada entre Estabilidad y Fortaleza/Score Integral.
    """
    codigos = list(_INDICADORES_ESTABILIDAD.keys())
    fecha_inicio_ventana = fecha - pd.DateOffset(months=meses_ventana - 1)

    df_ventana = df_indicadores[
        (df_indicadores['fecha'] >= fecha_inicio_ventana) & (df_indicadores['fecha'] <= fecha)
        & (df_indicadores['codigo'].isin(codigos))
    ]
    if segmento != "Todos":
        df_ventana = df_ventana[df_ventana['segmento'] == segmento]
    if df_ventana.empty:
        return pd.DataFrame()

    # --- Nivel (en la fecha de corte) ---
    df_corte = df_ventana[df_ventana['fecha'] == fecha]
    pivote_nivel = df_corte.pivot_table(
        index=['cooperativa', 'segmento'], columns='codigo', values='valor', aggfunc='first'
    ).reset_index()

    resultado = pivote_nivel[['cooperativa', 'segmento']].copy()
    columnas_nivel = []
    for codigo, mayor_es_mejor in _INDICADORES_ESTABILIDAD.items():
        if codigo in pivote_nivel.columns:
            col = f"pct_nivel_{codigo}"
            resultado[col] = _percentil_orientado(pivote_nivel[codigo], mayor_es_mejor)
            columnas_nivel.append(col)
    resultado['nivel'] = resultado[columnas_nivel].mean(axis=1, skipna=True) if columnas_nivel else np.nan

    # --- Consistencia (coeficiente de variación en la ventana) ---
    stats = df_ventana.groupby(['cooperativa', 'codigo'], observed=True)['valor'].agg(['mean', 'std']).reset_index()
    stats['cv'] = (stats['std'] / stats['mean'].abs()).where(stats['mean'].abs() > 1e-9)
    cv_pivote = stats.pivot_table(index='cooperativa', columns='codigo', values='cv', aggfunc='first')

    columnas_cv = []
    cv_percentiles = pd.DataFrame(index=cv_pivote.index)
    for codigo in codigos:
        if codigo in cv_pivote.columns:
            col = f"pct_consistencia_{codigo}"
            # menor coeficiente de variación = más consistente = mejor
            cv_percentiles[col] = _percentil_orientado(cv_pivote[codigo], mayor_es_mejor=False)
            columnas_cv.append(col)
    cv_percentiles['consistencia'] = (
        cv_percentiles[columnas_cv].mean(axis=1, skipna=True) if columnas_cv else np.nan
    )

    resultado = resultado.merge(
        cv_percentiles[['consistencia']], left_on='cooperativa', right_index=True, how='left'
    )
    resultado['indice_estabilidad'] = resultado[['nivel', 'consistencia']].mean(axis=1, skipna=True)
    return resultado.sort_values('indice_estabilidad', ascending=False)


# =============================================================================
# ÍNDICE DE RIESGO INTEGRAL
# =============================================================================

_BANDAS_RIESGO_INTEGRAL = [
    (85, "Excelente"), (70, "Muy Bueno"), (55, "Bueno"), (40, "Vigilancia"),
    (25, "Riesgo Medio"), (10, "Riesgo Alto"), (0, "Riesgo Crítico"),
]

PESOS_RIESGO_INTEGRAL = {
    'score_financiero': 0.5,
    'vulnerabilidad': 0.3,
    'alertas': 0.2,
}


def calcular_indice_riesgo_integral(
    df_score_financiero: pd.DataFrame, df_vulnerabilidad: pd.DataFrame, df_alertas: pd.DataFrame,
) -> pd.DataFrame:
    """
    Índice de Riesgo Integral (0-100, 100 = mejor / menor riesgo), por
    cooperativa: combina el Score Financiero Integral, el (complemento del)
    Índice de Vulnerabilidad, y el número de alertas activas del motor de
    Alertas Tempranas (`analytics.alertas.evaluar_alertas`) — tres señales ya
    calculadas por otros componentes de esta misma plataforma, ponderadas
    (ver `PESOS_RIESGO_INTEGRAL`, ajustable).

        riesgo_integral = 0.5·score_financiero_integral
                         + 0.3·(100 − indice_vulnerabilidad)
                         + 0.2·(100 − alertas_normalizado)

    donde `alertas_normalizado` reescala el conteo de alertas activas
    (0 a N reglas evaluadas) a 0-100.
    """
    base = df_score_financiero[['cooperativa', 'segmento', 'score_financiero_integral']].copy()

    if not df_vulnerabilidad.empty:
        base = base.merge(
            df_vulnerabilidad[['cooperativa', 'indice_vulnerabilidad']], on='cooperativa', how='left'
        )
    else:
        base['indice_vulnerabilidad'] = np.nan

    if not df_alertas.empty and 'total_alertas_activas' in df_alertas.columns:
        max_alertas = df_alertas['total_alertas_activas'].max()
        alertas = df_alertas[['cooperativa', 'total_alertas_activas']].copy()
        alertas['alertas_normalizado'] = (
            alertas['total_alertas_activas'] / max_alertas * 100 if max_alertas > 0 else 0.0
        )
        base = base.merge(alertas[['cooperativa', 'alertas_normalizado']], on='cooperativa', how='left')
    else:
        base['alertas_normalizado'] = np.nan

    base['riesgo_integral'] = (
        PESOS_RIESGO_INTEGRAL['score_financiero'] * base['score_financiero_integral'].fillna(50)
        + PESOS_RIESGO_INTEGRAL['vulnerabilidad'] * (100 - base['indice_vulnerabilidad'].fillna(50))
        + PESOS_RIESGO_INTEGRAL['alertas'] * (100 - base['alertas_normalizado'].fillna(0))
    )
    base['clasificacion_riesgo'] = base['riesgo_integral'].apply(clasificar_riesgo_integral)

    return base.sort_values('riesgo_integral', ascending=False)


def clasificar_riesgo_integral(valor: float) -> str:
    """Clasifica el Índice de Riesgo Integral (0-100) en las 7 bandas pedidas."""
    if pd.isna(valor):
        return "Sin datos"
    for umbral, etiqueta in _BANDAS_RIESGO_INTEGRAL:
        if valor >= umbral:
            return etiqueta
    return "Riesgo Crítico"
