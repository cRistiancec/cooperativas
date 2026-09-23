# -*- coding: utf-8 -*-
"""
Registro de eventos de referencia (proxy) para backtesting.

La SEPS no publica, en ninguna de las fuentes que este proyecto procesa, un
registro estructurado de liquidaciones/fusiones/absorciones con fecha. Este
módulo construye un **proxy**: cooperativas cuyo último reporte disponible
es anterior al último período del dataset por más de `meses_gracia` meses —
es decir, dejaron de reportar. Eso puede deberse a liquidación, fusión,
absorción, o simplemente un atraso de reporte no resuelto en los datos
disponibles. **No se afirma la causa** — se registra el hecho observable
(cese de reporte) con la fecha, y se deja la clasificación de causa como
"NO VERIFICADO" salvo evidencia textual directa (p. ej. el propio nombre de
la entidad contiene "EN LIQUIDACION", que sí se detecta y se marca aparte).

Cobertura: limitada al rango de fechas del dataset usado (`indicadores.parquet`
desde 2020, `balance.parquet` desde 2018) — salidas anteriores a ese rango no
son observables.
"""

from __future__ import annotations

import pandas as pd

MESES_GRACIA_DEFAULT = 3

# Etiqueta obligatoria para cualquier consumidor (UI, reportes, otros
# módulos) de la salida de este módulo — hardening 14-sep-2026, pedido
# explícito: "cese de reporte" NO equivale a liquidación/insolvencia/
# crisis/deterioro financiero. Se adjunta como COLUMNA de datos (no solo en
# el docstring) para que no se pierda si el DataFrame se filtra/exporta/
# muestra en otra parte sin pasar por este módulo.
TIPO_EVENTO_PROXY = "EVENTO PROXY NO CONFIRMADO — cese de reporte, causa no verificada"
TIPO_EVENTO_TEXTUAL = "EVIDENCIA TEXTUAL DIRECTA — el nombre reportado por la SEPS incluye 'LIQUIDACION'"


def detectar_eventos_salida(
    df: pd.DataFrame,
    columna_entidad: str = "cooperativa",
    columna_fecha: str = "fecha",
    meses_gracia: int = MESES_GRACIA_DEFAULT,
) -> pd.DataFrame:
    """
    Cooperativas cuyo último registro en `df` es anterior al máximo del
    dataset por más de `meses_gracia` meses.

    **"Cese de reporte" NO equivale a liquidación, insolvencia, crisis ni
    deterioro financiero** — puede deberse a cualquiera de esas causas, o
    simplemente a un atraso de reporte no resuelto en los datos disponibles.
    Este módulo NUNCA infiere la causa; solo el propio nombre de la entidad
    conteniendo "LIQUIDACION" (columna `liquidacion_declarada_en_nombre`) es
    evidencia textual directa, no inferida.

    Devuelve: cooperativa, ultima_fecha_reportada, meses_sin_reportar,
    liquidacion_declarada_en_nombre, `tipo_evento` (`TIPO_EVENTO_PROXY` o
    `TIPO_EVENTO_TEXTUAL` — adjunto como dato, no solo como docstring, para
    que cualquier consumidor de este DataFrame vea la etiqueta).
    """
    columnas_vacias = [
        "cooperativa", "ultima_fecha_reportada", "meses_sin_reportar",
        "liquidacion_declarada_en_nombre", "tipo_evento",
    ]
    if df.empty:
        return pd.DataFrame(columns=columnas_vacias)

    fecha_max_dataset = df[columna_fecha].max()
    ultima_fecha = df.groupby(columna_entidad, observed=True)[columna_fecha].max()

    umbral = fecha_max_dataset - pd.DateOffset(months=meses_gracia)
    candidatos = ultima_fecha[ultima_fecha < umbral].reset_index()
    candidatos.columns = ["cooperativa", "ultima_fecha_reportada"]

    candidatos["meses_sin_reportar"] = (
        (fecha_max_dataset.year - candidatos["ultima_fecha_reportada"].dt.year) * 12
        + (fecha_max_dataset.month - candidatos["ultima_fecha_reportada"].dt.month)
    )
    candidatos["liquidacion_declarada_en_nombre"] = (
        candidatos["cooperativa"].astype(str).str.upper().str.contains("LIQUIDACION")
    )
    candidatos["tipo_evento"] = candidatos["liquidacion_declarada_en_nombre"].map(
        {True: TIPO_EVENTO_TEXTUAL, False: TIPO_EVENTO_PROXY}
    )

    return candidatos.sort_values("ultima_fecha_reportada")
