# -*- coding: utf-8 -*-
"""
Backtesting — validación de señales de alerta contra eventos observados.

LIMITACIÓN METODOLÓGICA PRINCIPAL (léase antes de usar el resultado): los
"eventos" vienen de `analytics.eventos.detectar_eventos_salida()`, un PROXY
de cese de reporte (liquidación, fusión, absorción o simplemente atraso —
no se distingue la causa salvo evidencia textual directa). El resultado de
este módulo, por lo tanto, NO es un backtest en el sentido estricto de
validar contra eventos confirmados por resolución de la SEPS. Se reporta
igual, con esta limitación explícita en cada resultado, porque es la única
evidencia histórica disponible en los datos que este proyecto procesa — la
alternativa sería no medir nada, lo cual el objetivo del proyecto desestima
explícitamente ("si no existe un conjunto histórico suficiente, documentarlo",
no "no hacer nada").

Además: la muestra es pequeña (~24 eventos proxy en todo el histórico
disponible, 2020-2026) — cualquier precision/recall calculado aquí tiene un
intervalo de confianza amplio y NO debe presentarse como una tasa de acierto
confiable para decisiones operativas.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from analytics.eventos import detectar_eventos_salida
from analytics.persistencia import calcular_persistencia_alertas, ventana_fechas


def evaluar_alertas_previas_a_eventos(
    df_indicadores: pd.DataFrame,
    meses_anticipacion: int = 6,
    meses_gracia_evento: int = 3,
    umbral_persistente_meses: int = 2,
) -> dict:
    """
    Para cada evento de salida detectado (`analytics.eventos`), revisa si la
    entidad tuvo al menos una alerta activa persistente en la ventana de
    `meses_anticipacion` meses ANTES de su último reporte.

    "Verdadero positivo" (a efectos de este proxy): el sistema de alertas
    señaló la entidad antes de que dejara de reportar. "Falso negativo":
    dejó de reportar sin alertas previas relevantes. No se puede calcular
    "falsos positivos" en sentido estricto (requeriría saber qué entidades
    con alerta NO tuvieron problemas, lo cual es cierto para la gran mayoría
    por construcción — se reporta aparte como tasa de alerta activa en el
    universo general, para contexto, no como "falso positivo" acusatorio).
    """
    eventos = detectar_eventos_salida(df_indicadores, meses_gracia=meses_gracia_evento)
    resultado_base = {
        "tipo_resultado": "BACKTESTING PROXY — no es validación definitiva (ver `limitaciones`)",
        "n_eventos_proxy": int(len(eventos)),
        "eventos": eventos,
        "n_con_alerta_previa": 0,
        "n_sin_alerta_previa": 0,
        "recall_proxy": None,
        "lead_time_promedio_meses": None,
        "detalle": pd.DataFrame(),
        "limitaciones": [
            "Eventos = proxy de cese de reporte, no liquidaciones confirmadas por resolución SEPS.",
            f"Muestra pequeña (n={len(eventos)}) — no interpretar el recall como tasa de acierto operativa.",
            "Solo cubre el rango de fechas de indicadores.parquet (desde 2020).",
            f"'meses_de_anticipacion' está censurado por la ventana ({meses_anticipacion} meses): un "
            "valor igual a la ventana completa significa 'al menos esos meses', no el lead time real "
            "(pudo empezar antes; la ventana no se extiende más atrás para medirlo).",
        ],
    }

    if eventos.empty:
        return resultado_base

    fechas_disponibles = sorted(df_indicadores["fecha"].unique())
    filas = []
    for _, evento in eventos.iterrows():
        coop = evento["cooperativa"]
        ultima_fecha = evento["ultima_fecha_reportada"]

        ventana = ventana_fechas(fechas_disponibles, ultima_fecha, meses_anticipacion)
        if not ventana:
            continue

        df_persist = calcular_persistencia_alertas(df_indicadores, ventana, "Todos",
                                                     umbral_persistente_meses=umbral_persistente_meses)
        fila_coop = df_persist[df_persist["cooperativa"] == coop]

        tuvo_alerta = False
        meses_antes_primera_alerta = None
        if not fila_coop.empty:
            tuvo_alerta = bool(fila_coop.iloc[0]["meses_consecutivos_activa"] > 0)
            if tuvo_alerta:
                meses_antes_primera_alerta = int(fila_coop.iloc[0]["meses_consecutivos_activa"])

        filas.append({
            "cooperativa": coop,
            "ultima_fecha_reportada": ultima_fecha,
            "liquidacion_declarada_en_nombre": evento["liquidacion_declarada_en_nombre"],
            "tuvo_alerta_previa": tuvo_alerta,
            "meses_de_anticipacion": meses_antes_primera_alerta,
        })

    detalle = pd.DataFrame(filas)
    if detalle.empty:
        return resultado_base

    n_con_alerta = int(detalle["tuvo_alerta_previa"].sum())
    n_total = len(detalle)

    resultado_base.update({
        "n_con_alerta_previa": n_con_alerta,
        "n_sin_alerta_previa": n_total - n_con_alerta,
        "recall_proxy": round(n_con_alerta / n_total, 3) if n_total else None,
        "lead_time_promedio_meses": (
            round(detalle.loc[detalle["tuvo_alerta_previa"], "meses_de_anticipacion"].mean(), 1)
            if n_con_alerta else None
        ),
        "detalle": detalle,
    })
    return resultado_base
