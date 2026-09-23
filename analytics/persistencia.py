# -*- coding: utf-8 -*-
"""
Persistencia temporal de alertas.

Extiende `analytics.alertas` (que evalúa un único corte transversal) con la
dimensión de tiempo: una alerta de un solo mes no debe pesar igual que una
que lleva activa varios meses consecutivos. Reutiliza `evaluar_alertas()`
tal cual — no reimplementa las reglas, solo las evalúa repetidamente en una
ventana de fechas y agrega el resultado.

Definiciones (parametrizables, no hardcodeadas en el análisis; ver
`VENTANA_PERSISTENCIA_MESES`):

  - `activa_hoy`: la cooperativa tiene al menos una alerta activa (amarilla
    o roja) en la fecha más reciente de la ventana evaluada.
  - `meses_consecutivos`: cuántos meses seguidos, terminando en la fecha más
    reciente, la cooperativa tuvo al menos una alerta activa. 0 si no está
    activa hoy.
  - `alerta_nueva`: activa hoy, pero NO estaba activa el mes inmediatamente
    anterior (meses_consecutivos == 1).
  - `alerta_persistente`: activa hoy y `meses_consecutivos >= UMBRAL_PERSISTENTE`
    (por defecto 3 — ver módulo).
  - `alerta_recurrente`: no necesariamente activa hoy, pero estuvo activa en
    al menos 2 sub-ventanas separadas (con al menos un mes de inactividad
    entre medio) dentro de la ventana completa evaluada — patrón de
    "aparece, desaparece, reaparece" que una sola foto no revela.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from analytics.alertas import evaluar_alertas

UMBRAL_PERSISTENTE_MESES = 3  # meses consecutivos para considerar la alerta "persistente"


def calcular_persistencia_alertas(
    df_indicadores: pd.DataFrame,
    fechas_ventana: list,
    segmento: str = "Todos",
    umbral_persistente_meses: int = UMBRAL_PERSISTENTE_MESES,
) -> pd.DataFrame:
    """
    Evalúa `evaluar_alertas()` en cada fecha de `fechas_ventana` (se ordenan
    ascendentemente internamente) y agrega persistencia por cooperativa,
    respecto de la última fecha de la ventana.

    Devuelve, por cooperativa: alertas_rojas_hoy, alertas_amarillas_hoy,
    meses_consecutivos_activa, alerta_nueva, alerta_persistente,
    alerta_recurrente, semaforo_hoy.
    """
    columnas_vacias = [
        "cooperativa", "segmento", "alertas_rojas_hoy", "alertas_amarillas_hoy",
        "meses_consecutivos_activa", "alerta_nueva", "alerta_persistente",
        "alerta_recurrente", "semaforo_hoy",
    ]
    fechas = sorted(pd.to_datetime(pd.Series(fechas_ventana)).unique())
    if not fechas:
        return pd.DataFrame(columns=columnas_vacias)

    # Matriz cooperativa x fecha: True si tuvo >=1 alerta activa (amarilla o roja) ese mes.
    activa_por_fecha = {}
    detalle_ultima_fecha = None
    for fecha in fechas:
        df_eval = evaluar_alertas(df_indicadores, fecha, segmento)
        if df_eval.empty:
            activa_por_fecha[fecha] = pd.Series(dtype=bool)
            continue
        activa_por_fecha[fecha] = (
            df_eval.set_index("cooperativa")["total_alertas_activas"] > 0
        )
        if fecha == fechas[-1]:
            detalle_ultima_fecha = df_eval.set_index("cooperativa")

    if detalle_ultima_fecha is None or detalle_ultima_fecha.empty:
        return pd.DataFrame(columns=columnas_vacias)

    todas_cooperativas = sorted(set().union(*[s.index for s in activa_por_fecha.values()]))
    matriz = pd.DataFrame(
        {fecha: activa_por_fecha[fecha].reindex(todas_cooperativas, fill_value=False) for fecha in fechas}
    )

    registros = []
    for coop in todas_cooperativas:
        fila = matriz.loc[coop]
        # Meses consecutivos activa, terminando en la última fecha.
        consecutivos = 0
        for fecha in reversed(fechas):
            if bool(fila[fecha]):
                consecutivos += 1
            else:
                break

        # Recurrencia: >= 2 rachas separadas de actividad dentro de la ventana completa.
        rachas = 0
        estado_previo = False
        for fecha in fechas:
            activo = bool(fila[fecha])
            if activo and not estado_previo:
                rachas += 1
            estado_previo = activo

        activa_hoy = consecutivos > 0
        registros.append({
            "cooperativa": coop,
            "segmento": (
                detalle_ultima_fecha.loc[coop, "segmento"] if coop in detalle_ultima_fecha.index else None
            ),
            "alertas_rojas_hoy": (
                int(detalle_ultima_fecha.loc[coop, "alertas_rojas"]) if coop in detalle_ultima_fecha.index else 0
            ),
            "alertas_amarillas_hoy": (
                int(detalle_ultima_fecha.loc[coop, "alertas_amarillas"]) if coop in detalle_ultima_fecha.index else 0
            ),
            "meses_consecutivos_activa": consecutivos,
            "alerta_nueva": activa_hoy and consecutivos == 1,
            "alerta_persistente": activa_hoy and consecutivos >= umbral_persistente_meses,
            "alerta_recurrente": rachas >= 2,
            "semaforo_hoy": (
                detalle_ultima_fecha.loc[coop, "semaforo"] if coop in detalle_ultima_fecha.index else "ok"
            ),
        })

    return pd.DataFrame(registros).sort_values(
        ["meses_consecutivos_activa", "alertas_rojas_hoy"], ascending=[False, False]
    )


def ventana_fechas(fechas_disponibles: list, fecha_referencia, meses: int) -> list:
    """
    Utilidad: de una lista de fechas disponibles (p. ej. `df['fecha'].unique()`),
    devuelve las últimas `meses` fechas hasta `fecha_referencia` inclusive.
    """
    fechas_ordenadas = sorted(pd.to_datetime(pd.Series(fechas_disponibles)).unique())
    fecha_referencia = pd.Timestamp(fecha_referencia)
    hasta_referencia = [f for f in fechas_ordenadas if f <= fecha_referencia]
    return hasta_referencia[-meses:] if meses > 0 else hasta_referencia
