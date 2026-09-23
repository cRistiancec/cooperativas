# -*- coding: utf-8 -*-
"""
Analítica de Rentabilidad — tasas implícitas, spread financiero y ROE ajustado.

Migra la sección "INDICADORES DE RENTABILIDAD" del script R institucional de
referencia (`AUDITORIA_MOTOR_INDICADORES.md`, Categoría 3: fórmulas nuevas y
computables con datos de cooperativas). El ROE y el ROA oficiales YA están
publicados por la SEPS (`indicadores.parquet`, códigos `ROE`/`ROA`) y la
plataforma los sigue usando tal cual — este módulo agrega lo que el R calcula
y la SEPS **no** publica: tasas activa/pasiva implícitas, el spread entre
ambas, el margen financiero en dólares, y una versión ajustada del ROE.

Adaptación deliberada respecto al R (no una migración literal línea por
línea): el script R anualiza manualmente cada cuenta de PyG con
`lag()` + `rollapplyr(sum, 12)` sobre el saldo acumulado del año — una cuenta
por vez, en cada ejecución. `pyg.parquet` ya trae `valor_12m` (la misma suma
móvil de 12 meses) **pre-calculada una sola vez en el ETL**
(`scripts/procesar_pyg.py`), así que estas funciones parten de esa columna en
vez de reimplementar el rolling. Esto también evita la rama especial que el R
necesita para diciembre (`ROE_ADJ`, `ifelse(MES != 12, ...)`): al ya venir
anualizado el numerador, no hay meses especiales.
"""

from __future__ import annotations

import pandas as pd

CODIGO_DEPOSITOS = '21'
CODIGO_CARTERA = '14'
CODIGO_PATRIMONIO = '3'

# Cuentas de PyG (todas de 2 dígitos salvo las notadas), niveles del Catálogo Único
CODIGO_INTERES_CAUSADO_DEPOSITOS = '4101'  # Intereses causados / Obligaciones con el público
CODIGO_INTERES_GANADO_CARTERA = '5104'     # Intereses y descuentos de cartera de créditos
CODIGO_INGRESOS_TOTAL = '5'
CODIGO_GASTOS_TOTAL = '4'
CODIGO_OTROS_INGRESOS = '56'

CODIGOS_MARGEN_FINANCIERO_INGRESO = ['51', '52', '53', '54']
CODIGOS_MARGEN_FINANCIERO_GASTO = ['41', '42', '43', '44']

MESES_PROMEDIO_MOVIL = 3  # misma ventana que usa el R (`rollapplyr(..., 3, mean)`)


def _promedio_movil_balance(df_ranking: pd.DataFrame, codigo: str, fecha, segmento: str = "Todos") -> pd.Series:
    """
    Promedio de los últimos `MESES_PROMEDIO_MOVIL` cortes disponibles (≤ fecha)
    de una cuenta de balance, por cooperativa — el denominador que el R
    calcula con `rollapplyr(CTA_X, 3, mean, partial=T)`.

    Devuelve una Serie indexada por `cooperativa`.
    """
    df_f = df_ranking[df_ranking['codigo'] == codigo]
    if segmento != "Todos":
        df_f = df_f[df_f['segmento'] == segmento]

    fechas_disponibles = sorted(f for f in df_f['fecha'].unique() if f <= fecha)
    ventana = fechas_disponibles[-MESES_PROMEDIO_MOVIL:]
    if not ventana:
        return pd.Series(dtype=float)

    return df_f[df_f['fecha'].isin(ventana)].groupby('cooperativa', observed=True)['valor'].mean()


def _valor_12m_pyg(df_pyg: pd.DataFrame, codigo: str, fecha, segmento: str = "Todos") -> pd.Series:
    """Serie `valor_12m` de una cuenta de PyG en una fecha, indexada por cooperativa."""
    mask = (df_pyg['codigo'] == codigo) & (df_pyg['fecha'] == fecha)
    if segmento != "Todos":
        mask &= (df_pyg['segmento'] == segmento)
    df_f = df_pyg[mask]
    return df_f.groupby('cooperativa', observed=True)['valor_12m'].sum()


def calcular_tasas_implicitas(
    df_ranking: pd.DataFrame, df_pyg: pd.DataFrame, fecha, segmento: str = "Todos"
) -> pd.DataFrame:
    """
    Tasa pasiva implícita, tasa activa implícita y spread financiero, por
    cooperativa, en una fecha de corte.

        tasa_pasiva_implicita (%) = intereses causados en depósitos (12m) /
                                     promedio móvil 3m de depósitos del público
        tasa_activa_implicita (%) = intereses ganados en cartera (12m) /
                                     promedio móvil 3m de cartera bruta
        spread_financiero (pp)    = tasa_activa_implicita − tasa_pasiva_implicita

    Equivalente a `TASA_PI`, `TASA_AI`, `TASA_MF` del script R de referencia.
    """
    interes_pasivo = _valor_12m_pyg(df_pyg, CODIGO_INTERES_CAUSADO_DEPOSITOS, fecha, segmento)
    interes_activo = _valor_12m_pyg(df_pyg, CODIGO_INTERES_GANADO_CARTERA, fecha, segmento)
    depositos_prom = _promedio_movil_balance(df_ranking, CODIGO_DEPOSITOS, fecha, segmento)
    cartera_prom = _promedio_movil_balance(df_ranking, CODIGO_CARTERA, fecha, segmento)

    resultado = pd.DataFrame({
        'interes_pasivo_12m': interes_pasivo,
        'depositos_promedio_3m': depositos_prom,
        'interes_activo_12m': interes_activo,
        'cartera_promedio_3m': cartera_prom,
    }).dropna(how='all')

    resultado['tasa_pasiva_implicita'] = (
        resultado['interes_pasivo_12m'] / resultado['depositos_promedio_3m'] * 100
    ).where(resultado['depositos_promedio_3m'] > 0)
    resultado['tasa_activa_implicita'] = (
        resultado['interes_activo_12m'] / resultado['cartera_promedio_3m'] * 100
    ).where(resultado['cartera_promedio_3m'] > 0)
    resultado['spread_financiero'] = resultado['tasa_activa_implicita'] - resultado['tasa_pasiva_implicita']

    return resultado.reset_index().rename(columns={'index': 'cooperativa'})


def calcular_margen_financiero(df_pyg: pd.DataFrame, fecha, segmento: str = "Todos") -> pd.DataFrame:
    """
    Margen financiero en dólares (12 meses), por cooperativa:

        margen_financiero = (ingresos financieros: intereses, comisiones,
                              utilidades financieras, servicios) −
                             (gastos financieros: intereses, comisiones,
                              pérdidas financieras, provisiones)

    Equivalente a `MARGEN_FINANCIERO` del R (`CTA_51-CTA_41+CTA_52+CTA_53+CTA_54-CTA_42-CTA_43-CTA_44`),
    sobre `valor_12m` en vez del saldo acumulado del año — ver nota del módulo.
    """
    codigos = CODIGOS_MARGEN_FINANCIERO_INGRESO + CODIGOS_MARGEN_FINANCIERO_GASTO
    mask = (df_pyg['codigo'].isin(codigos)) & (df_pyg['fecha'] == fecha)
    if segmento != "Todos":
        mask &= (df_pyg['segmento'] == segmento)

    pivote = df_pyg[mask].pivot_table(
        index='cooperativa', columns='codigo', values='valor_12m', aggfunc='sum'
    )
    for c in codigos:
        if c not in pivote.columns:
            pivote[c] = 0.0
    pivote = pivote.fillna(0.0)

    ingresos = pivote[CODIGOS_MARGEN_FINANCIERO_INGRESO].sum(axis=1)
    gastos = pivote[CODIGOS_MARGEN_FINANCIERO_GASTO].sum(axis=1)

    return pd.DataFrame({
        'cooperativa': pivote.index,
        'margen_financiero': (ingresos - gastos).values,
    })


def calcular_roe_ajustado(
    df_ranking: pd.DataFrame, df_pyg: pd.DataFrame, fecha, segmento: str = "Todos"
) -> pd.DataFrame:
    """
    ROE ajustado (%), por cooperativa: utilidad de 12 meses, excluyendo otros
    ingresos no operativos (`CTA_56`), sobre el patrimonio promedio de los
    últimos 3 meses.

        roe_ajustado = (ingresos_12m − gastos_12m − otros_ingresos_12m) /
                        patrimonio_promedio_3m

    Equivalente a `ROE_ADJ` del R. El R distingue diciembre (usa el saldo
    acumulado del año completo) de los demás meses (anualiza multiplicando
    por 12/MES) porque parte de saldos acumulados sin anualizar; al partir
    aquí de `valor_12m` (ya anualizado por construcción, para cualquier mes)
    esa distinción de diciembre no aplica — mismo resultado, una sola fórmula.
    """
    ingresos = _valor_12m_pyg(df_pyg, CODIGO_INGRESOS_TOTAL, fecha, segmento)
    gastos = _valor_12m_pyg(df_pyg, CODIGO_GASTOS_TOTAL, fecha, segmento)
    otros_ingresos = _valor_12m_pyg(df_pyg, CODIGO_OTROS_INGRESOS, fecha, segmento)
    patrimonio_prom = _promedio_movil_balance(df_ranking, CODIGO_PATRIMONIO, fecha, segmento)

    resultado = pd.DataFrame({
        'ingresos_12m': ingresos,
        'gastos_12m': gastos,
        'otros_ingresos_12m': otros_ingresos,
        'patrimonio_promedio_3m': patrimonio_prom,
    }).dropna(how='all')

    utilidad_ajustada = (
        resultado['ingresos_12m'] - resultado['gastos_12m'] - resultado['otros_ingresos_12m'].fillna(0.0)
    )
    resultado['roe_ajustado'] = (
        utilidad_ajustada / resultado['patrimonio_promedio_3m'] * 100
    ).where(resultado['patrimonio_promedio_3m'] > 0)

    return resultado.reset_index().rename(columns={'index': 'cooperativa'})[['cooperativa', 'roe_ajustado']]
