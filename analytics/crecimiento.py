# -*- coding: utf-8 -*-
"""
Analítica de Crecimiento — captaciones, colocaciones, cartera en riesgo y
bandas de percentil para benchmarking de pares.

Migra la sección "TASAS DE CRECIMIENTO" del script R institucional de
referencia (`AUDITORIA_MOTOR_INDICADORES.md`, Categoría 3).

Las funciones de crecimiento de captaciones/colocaciones **no reimplementan**
el cálculo: delegan en `utils.data_loader.obtener_crecimiento_anual`, la
misma función ya usada por Panorama para el gráfico de crecimiento anual por
cooperativa (comparación de dos cortes vía merge). El R define 8 nombres
distintos (`CAPGA`, `TCAPGA`, `CAPGM`, `TCAPGM`, `COLGA`, `TCOLGA`, `COLGM`,
`TCOLGM`) para lo que en realidad son la misma operación —diferencia entre
dos fechas de una cuenta— aplicada a dos cuentas (depósitos/cartera) en dos
horizontes (mensual/anual, según qué `fecha_anterior` se pase). Aquí se
expresa como dos funciones con nombre financiero claro, parametrizadas por
fecha, en vez de ocho.
"""

from __future__ import annotations

from typing import Tuple

import pandas as pd

from utils.data_loader import obtener_crecimiento_anual

CODIGO_ACTIVOS = '1'
CODIGO_DEPOSITOS = '21'
CODIGO_CARTERA_BRUTA = '14'

# Cartera en riesgo (CER, R): cuentas "vencida" y "que no devenga intereses"
# por línea de negocio × modalidad (prioritario/productivo/ordinario), a
# nivel de 4 dígitos del Catálogo Único de Cuentas. Confirmadas presentes en
# balance.parquet (ver AUDITORIA_MOTOR_INDICADORES.md, Categoría 3).
CODIGOS_CARTERA_EN_RIESGO: Tuple[str, ...] = (
    '1425', '1426', '1427', '1428', '1429', '1430',
    '1433', '1434', '1435', '1436', '1437', '1438',
    '1441', '1442', '1443', '1444', '1445', '1446',
    '1449', '1450', '1451', '1452', '1453', '1454',
    '1457', '1458', '1459', '1460', '1461', '1462',
    '1465', '1466', '1467', '1468', '1469', '1470',
)


def crecimiento_captaciones(fecha_actual, fecha_anterior, segmento: str = "Todos", top_n: int = 0) -> pd.DataFrame:
    """
    Crecimiento de depósitos del público (captaciones) entre dos fechas, por
    cooperativa: valor absoluto y porcentual.

    Pasar `fecha_anterior` = mismo mes del año previo → equivalente a
    `CAPGA`/`TCAPGA` del R. Pasar `fecha_anterior` = mes calendario previo →
    equivalente a `CAPGM`/`TCAPGM`. `top_n=0` devuelve todas las cooperativas
    (ver `obtener_crecimiento_anual`).
    """
    df = obtener_crecimiento_anual(fecha_actual, fecha_anterior, codigo=CODIGO_DEPOSITOS, segmento=segmento, top_n=top_n)
    if df.empty:
        return df
    return df.rename(columns={
        'valor_actual': 'depositos_actual', 'valor_anterior': 'depositos_anterior',
        'crecimiento': 'crecimiento_pct',
    }).assign(crecimiento_absoluto=lambda d: d['depositos_actual'] - d['depositos_anterior'])


def crecimiento_colocaciones(fecha_actual, fecha_anterior, segmento: str = "Todos", top_n: int = 0) -> pd.DataFrame:
    """
    Crecimiento de cartera bruta (colocaciones) entre dos fechas, por
    cooperativa: valor absoluto y porcentual.

    Mismo uso que `crecimiento_captaciones` — equivalente a
    `COLGA`/`TCOLGA` (horizonte anual) o `COLGM`/`TCOLGM` (horizonte mensual)
    del R, según la `fecha_anterior` que se pase.
    """
    df = obtener_crecimiento_anual(fecha_actual, fecha_anterior, codigo=CODIGO_CARTERA_BRUTA, segmento=segmento, top_n=top_n)
    if df.empty:
        return df
    return df.rename(columns={
        'valor_actual': 'cartera_actual', 'valor_anterior': 'cartera_anterior',
        'crecimiento': 'crecimiento_pct',
    }).assign(crecimiento_absoluto=lambda d: d['cartera_actual'] - d['cartera_anterior'])


def crecimiento_activos(fecha_actual, fecha_anterior, segmento: str = "Todos", top_n: int = 0) -> pd.DataFrame:
    """
    Crecimiento de activos totales entre dos fechas, por cooperativa: valor
    absoluto y porcentual. Mismo uso que `crecimiento_captaciones` — no
    tiene un nombre propio en el R (que no calcula crecimiento de activos),
    pero es el mismo patrón aplicado a la cuenta de activos (código `1`);
    se usa como insumo del Índice de Fortaleza.
    """
    df = obtener_crecimiento_anual(fecha_actual, fecha_anterior, codigo=CODIGO_ACTIVOS, segmento=segmento, top_n=top_n)
    if df.empty:
        return df
    return df.rename(columns={
        'valor_actual': 'activos_actual', 'valor_anterior': 'activos_anterior',
        'crecimiento': 'crecimiento_pct',
    }).assign(crecimiento_absoluto=lambda d: d['activos_actual'] - d['activos_anterior'])


def calcular_cartera_en_riesgo(df_balance: pd.DataFrame, fecha, segmento: str = "Todos") -> pd.DataFrame:
    """
    Cartera en riesgo (CER, R) por cooperativa: suma de las cuentas vencidas
    y que no devengan intereses en todas las líneas de negocio, en una fecha.

    `df_balance` debe venir ya filtrado a `CODIGOS_CARTERA_EN_RIESGO` — usar
    `utils.data_loader.cargar_balance_por_codigos(CODIGOS_CARTERA_EN_RIESGO)`,
    que aplica predicate pushdown de PyArrow en vez de cargar el balance
    completo (24M filas) para quedarse con 36 códigos.
    """
    mask = df_balance['fecha'] == fecha
    if segmento != "Todos":
        mask &= df_balance['segmento'] == segmento
    return (
        df_balance[mask]
        .groupby('cooperativa', observed=True)['valor']
        .sum()
        .reset_index(name='cartera_en_riesgo')
    )


def variacion_anual_cartera_en_riesgo(
    df_balance: pd.DataFrame, fecha_actual, fecha_anterior, segmento: str = "Todos"
) -> pd.DataFrame:
    """Variación interanual (en dólares) de la cartera en riesgo — equivalente a `MORAGR`-sobre-`CER` del R."""
    actual = calcular_cartera_en_riesgo(df_balance, fecha_actual, segmento)
    anterior = calcular_cartera_en_riesgo(df_balance, fecha_anterior, segmento).rename(
        columns={'cartera_en_riesgo': 'cartera_en_riesgo_anterior'}
    )
    resultado = actual.merge(anterior, on='cooperativa', how='inner')
    resultado['variacion_cartera_en_riesgo'] = (
        resultado['cartera_en_riesgo'] - resultado['cartera_en_riesgo_anterior']
    )
    return resultado


def calcular_crecimiento_yoy_mensual(
    df_balance: pd.DataFrame, codigo: str, segmento: str = "Todos", cooperativas: list = None,
) -> pd.DataFrame:
    """
    Crecimiento YoY mes a mes (vs. el mismo mes del año anterior) de una
    cuenta arbitraria, para TODA la serie temporal disponible — a
    diferencia de `crecimiento_captaciones`/`crecimiento_colocaciones`
    (que comparan solo 2 fechas puntuales vía `obtener_crecimiento_anual`),
    esta función sirve para construir una serie/heatmap mensual completo.

    Centralizado aquí 14-sep-2026 (hardening): antes vivía duplicado dentro
    de `pages/2_Balance_General.py::obtener_datos_heatmap_mensual()`. Misma
    fórmula, mismo resultado — verificado por
    `tests/test_riesgo_ampliado.py::CrecimientoYoYMensualTests` (equivalencia
    numérica exacta contra la implementación original conservada en el
    propio test como referencia).

    Devuelve una fila por (cooperativa, fecha) con `año`, `mes`, `valor`,
    `valor_ano_anterior`, `crecimiento_yoy` (%). El primer año de cada
    cooperativa queda con `crecimiento_yoy = NaN` (no hay año anterior para
    comparar) — igual que la implementación original.
    """
    df_f = df_balance[df_balance['codigo'] == codigo].copy()
    if segmento != "Todos":
        df_f = df_f[df_f['segmento'] == segmento]
    if cooperativas:
        df_f = df_f[df_f['cooperativa'].isin(cooperativas)]
    if df_f.empty:
        return df_f

    df_f['año'] = df_f['fecha'].dt.year
    df_f['mes'] = df_f['fecha'].dt.month
    df_f = df_f.sort_values(['cooperativa', 'año', 'mes'])
    df_f['valor_ano_anterior'] = df_f.groupby(['cooperativa', 'mes'], observed=True)['valor'].shift(1)
    df_f['crecimiento_yoy'] = ((df_f['valor'] / df_f['valor_ano_anterior']) - 1) * 100
    return df_f


def bandas_percentil(valores: pd.Series, p_bajo: float = 10, p_alto: float = 90) -> Tuple[float, float]:
    """
    Banda de percentiles [p_bajo, p_alto] de una serie transversal (todas las
    cooperativas en una misma fecha), para benchmarking de pares.

    Equivalente al patrón `group_by(FECHA) %>% mutate(quantile(...))` que el
    R repite 7 veces (una por indicador) — aquí es una sola función que
    cualquier página puede aplicar a la serie que necesite comparar.
    """
    v = valores.dropna()
    if v.empty:
        return (float('nan'), float('nan'))
    return (float(v.quantile(p_bajo / 100)), float(v.quantile(p_alto / 100)))
