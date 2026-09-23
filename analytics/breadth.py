# -*- coding: utf-8 -*-
"""
Breadth (amplitud) de un deterioro o señal de alerta.

Responde una pregunta que el semáforo de `analytics.alertas` NO responde:
de las cooperativas con una alerta activa, ¿cuánto pesan realmente en el
sistema? 20 cooperativas pequeñas con alerta roja no es lo mismo que 3
cooperativas grandes con alerta roja, aunque el conteo de "cuántas
entidades" sea menor en el segundo caso.

Fuente: `agg_ranking_cooperativas.parquet` (vía `cargar_ranking_cooperativas()`),
que ya trae activos/cartera/depósitos/patrimonio por cooperativa y fecha.

Clasificación RIESGO CONCENTRADO / RIESGO GENERALIZADO: umbral ANALÍTICO
(no regulatorio) fijado en 25% de una dimensión del sistema — ver
`UMBRAL_GENERALIZADO_PCT`. Documentado explícitamente como tal para que no
se confunda con un límite oficial.
"""

from __future__ import annotations

from typing import Iterable

import pandas as pd

CODIGOS_DIMENSION = {
    "activos": "1",
    "cartera": "14",
    "depositos": "21",
    "patrimonio": "3",
}

# Umbral analítico (no regulatorio): a partir de qué % de una dimensión del
# sistema en manos de entidades afectadas se considera "generalizado" en vez
# de "concentrado". Elegido de forma simétrica y documentada, no arbitraria:
# es el mismo orden de magnitud que el umbral de "concentración moderada"
# de HHI (analytics.concentracion) traducido a participación de un solo
# grupo de entidades, para mantener consistencia conceptual entre ambos
# módulos de concentración/amplitud.
UMBRAL_GENERALIZADO_PCT = 25.0


def calcular_breadth(
    cooperativas_afectadas: Iterable[str],
    df_ranking: pd.DataFrame,
    fecha,
    segmento: str = "Todos",
) -> dict:
    """
    % de activos/cartera/depósitos/patrimonio del universo comparado que
    está en manos de `cooperativas_afectadas` en `fecha`.

    El "universo comparado" es el sistema completo si `segmento == "Todos"`,
    o solo ese segmento si se filtra — la amplitud dentro de un segmento
    pequeño no debe compararse contra el sistema completo sin decirlo.
    """
    afectadas = set(str(c) for c in cooperativas_afectadas)

    mask = df_ranking["fecha"] == fecha
    if segmento != "Todos":
        mask &= df_ranking["segmento"] == segmento
    df_f = df_ranking[mask & df_ranking["codigo"].isin(CODIGOS_DIMENSION.values())]

    if df_f.empty:
        return {
            "fecha": fecha, "segmento": segmento, "n_entidades_universo": 0,
            "n_entidades_afectadas": 0, "pct_entidades": 0.0,
            "dimensiones": {}, "clasificacion": "SIN DATOS",
        }

    pivote = df_f.pivot_table(
        index="cooperativa", columns="codigo", values="valor", aggfunc="first", observed=True
    ).fillna(0.0)

    resultado_dims = {}
    for nombre, codigo in CODIGOS_DIMENSION.items():
        if codigo not in pivote.columns:
            resultado_dims[nombre] = None
            continue
        total = pivote[codigo].sum()
        if total <= 0:
            resultado_dims[nombre] = None
            continue
        afectado = pivote.loc[pivote.index.astype(str).isin(afectadas), codigo].sum()
        resultado_dims[nombre] = round(float(afectado / total * 100), 2)

    n_universo = pivote.shape[0]
    n_afectadas = len(afectadas & set(pivote.index.astype(str)))
    pct_activos = resultado_dims.get("activos")

    if pct_activos is None:
        clasificacion = "SIN DATOS SUFICIENTES (activos)"
    elif pct_activos >= UMBRAL_GENERALIZADO_PCT:
        clasificacion = "RIESGO GENERALIZADO"
    else:
        clasificacion = "RIESGO CONCENTRADO"

    return {
        "fecha": fecha,
        "segmento": segmento,
        "n_entidades_universo": int(n_universo),
        "n_entidades_afectadas": int(n_afectadas),
        "pct_entidades": round(n_afectadas / n_universo * 100, 2) if n_universo else 0.0,
        "dimensiones": resultado_dims,
        "clasificacion": clasificacion,
        "umbral_generalizado_pct": UMBRAL_GENERALIZADO_PCT,
    }


def breadth_por_segmento(
    cooperativas_afectadas: Iterable[str], df_ranking: pd.DataFrame, fecha,
) -> pd.DataFrame:
    """Repite `calcular_breadth()` para cada segmento presente en `fecha` (para comparar dónde pesa más el deterioro)."""
    segmentos = sorted(df_ranking.loc[df_ranking["fecha"] == fecha, "segmento"].astype(str).unique())
    filas = []
    for seg in segmentos:
        r = calcular_breadth(cooperativas_afectadas, df_ranking, fecha, segmento=seg)
        filas.append({
            "segmento": seg,
            "n_entidades_universo": r["n_entidades_universo"],
            "n_entidades_afectadas": r["n_entidades_afectadas"],
            "pct_entidades": r["pct_entidades"],
            "pct_activos": r["dimensiones"].get("activos"),
            "pct_cartera": r["dimensiones"].get("cartera"),
            "pct_depositos": r["dimensiones"].get("depositos"),
            "pct_patrimonio": r["dimensiones"].get("patrimonio"),
            "clasificacion": r["clasificacion"],
        })
    return pd.DataFrame(filas)
