# -*- coding: utf-8 -*-
"""
Reglas de interacción entre indicadores.

Una combinación de señales moderadas en distintos indicadores puede ser más
relevante que cualquiera de ellas por separado. Este módulo implementa
ÚNICAMENTE combinaciones con una justificación económica explícita (no
"pesos" arbitrarios ni un score combinado sin narrativa) — cada regla
documenta qué mecanismo financiero representa.

Opera sobre la salida de `analytics.alertas.evaluar_alertas()` (columnas
`sev_<CODIGO>`: 0 = sin alerta, 1 = amarilla, 2 = roja), no sobre valores
crudos — así una regla de interacción es, por construcción, siempre al
menos tan estricta como sus reglas individuales ya vigentes en
`config/umbrales_alerta.py`.
"""

from __future__ import annotations

import pandas as pd

REGLAS_INTERACCION = {
    "deterioro_cartera_compuesto": {
        "descripcion": (
            "Morosidad en alerta (severidad>=1) + Cobertura en alerta "
            "(severidad>=1) + ROA en alerta (severidad>=1). Mecanismo: cartera "
            "que se deteriora sin provisiones suficientes para absorber la "
            "pérdida esperada, mientras la rentabilidad ya no genera "
            "colchón adicional — la combinación es la secuencia clásica "
            "hacia una insolvencia por calidad de activos, más grave que "
            "cualquiera de los tres síntomas aislados."
        ),
        "condiciones": ["sev_MOR_TOT", "sev_COB_TOT", "sev_ROA"],
        "umbral_severidad_minima": 1,
    },
    "deterioro_cartera_compuesto_critico": {
        "descripcion": (
            "Igual que 'deterioro_cartera_compuesto' pero exigiendo severidad "
            "roja (>=2) en morosidad Y cobertura simultáneamente (ROA en "
            "cualquier nivel de alerta) — el par morosidad/cobertura en rojo "
            "a la vez es la condición más directa de deterioro patrimonial "
            "no cubierto: cartera muy vencida y provisiones muy por debajo "
            "de esa cartera vencida, al mismo tiempo."
        ),
        "condiciones_roja": ["sev_MOR_TOT", "sev_COB_TOT"],
        "condiciones_alerta": ["sev_ROA"],
    },
    "presion_fondeo": {
        "descripcion": (
            "Caída de depósitos en alerta (severidad>=1, ver sev_DEPOSITOS "
            "en evaluar_alertas cuando se provee df_crecimiento_depositos) + "
            "Liquidez en alerta (severidad>=1). Mecanismo: una entidad que "
            "pierde depósitos Y tiene poco colchón líquido tiene, "
            "simultáneamente, menos fondeo entrando y menos capacidad de "
            "responder retiros con lo que ya tiene — la combinación es la "
            "antesala típica de un problema de liquidez agudo, distinto de "
            "cualquiera de los dos factores por separado."
        ),
        "condiciones": ["sev_DEPOSITOS", "sev_LIQ"],
        "umbral_severidad_minima": 1,
    },
}


def evaluar_interacciones(df_alertas: pd.DataFrame) -> pd.DataFrame:
    """
    Evalúa las reglas de `REGLAS_INTERACCION` sobre la salida de
    `evaluar_alertas()`. Devuelve una columna booleana por regla más un
    conteo `n_interacciones_activas`.

    Reglas cuyas columnas de severidad necesarias no estén presentes en
    `df_alertas` (p. ej. no se pasó `df_crecimiento_depositos` a
    `evaluar_alertas()`, así que no hay `sev_DEPOSITOS`) se omiten
    silenciosamente para esa corrida — no se inventa el dato faltante.
    """
    if df_alertas.empty:
        return df_alertas

    resultado = df_alertas.copy()
    columnas_regla = []

    for nombre, regla in REGLAS_INTERACCION.items():
        if "condiciones" in regla:
            cols = regla["condiciones"]
            if not all(c in resultado.columns for c in cols):
                continue
            umbral = regla["umbral_severidad_minima"]
            resultado[nombre] = (resultado[cols] >= umbral).all(axis=1)
            columnas_regla.append(nombre)
        else:
            cols_roja = regla["condiciones_roja"]
            cols_alerta = regla["condiciones_alerta"]
            if not all(c in resultado.columns for c in cols_roja + cols_alerta):
                continue
            cond_roja = (resultado[cols_roja] >= 2).all(axis=1)
            cond_alerta = (resultado[cols_alerta] >= 1).all(axis=1)
            resultado[nombre] = cond_roja & cond_alerta
            columnas_regla.append(nombre)

    if columnas_regla:
        resultado["n_interacciones_activas"] = resultado[columnas_regla].sum(axis=1)
    else:
        resultado["n_interacciones_activas"] = 0

    return resultado
