# -*- coding: utf-8 -*-
"""
Data Quality — validaciones previas a cualquier alerta o índice de riesgo.

Objetivo (pedido explícito del proyecto): "Una alerta financiera debe estar
separada de una anomalía de datos". Este módulo NO evalúa riesgo financiero;
evalúa si los datos de una fecha/indicador son confiables para que otro
módulo (alertas, breadth, riesgo sistémico) los use.

Todas las funciones son de solo lectura (no modifican ni "arreglan" datos):
devuelven un DataFrame o dict con el hallazgo, para que el llamador decida
qué hacer (excluir una fecha, mostrar una advertencia, etc.).
"""

from __future__ import annotations

from typing import Any, Dict

import pandas as pd


def validar_fechas(df: pd.DataFrame, columna_fecha: str = "fecha") -> Dict[str, Any]:
    """
    Detecta huecos en la serie mensual de fechas de un DataFrame.

    Devuelve: fecha_min, fecha_max, meses_esperados, meses_presentes,
    meses_faltantes (lista de fechas de fin de mes ausentes dentro del rango).
    """
    if df.empty or columna_fecha not in df.columns:
        return {"valido": False, "motivo": "DataFrame vacío o sin columna de fecha"}

    fechas = pd.to_datetime(df[columna_fecha]).dropna().unique()
    if len(fechas) == 0:
        return {"valido": False, "motivo": "Sin fechas válidas"}

    fecha_min, fecha_max = pd.Timestamp(min(fechas)), pd.Timestamp(max(fechas))
    rango_esperado = pd.date_range(fecha_min, fecha_max, freq="ME")
    presentes = set(pd.Timestamp(f) for f in fechas)
    faltantes = sorted(f for f in rango_esperado if f not in presentes)

    return {
        "valido": True,
        "fecha_min": fecha_min,
        "fecha_max": fecha_max,
        "meses_esperados": len(rango_esperado),
        "meses_presentes": len(presentes),
        "meses_faltantes": faltantes,
        "tiene_huecos": len(faltantes) > 0,
    }


def validar_duplicados(df: pd.DataFrame, columnas_clave: list[str]) -> Dict[str, Any]:
    """
    Cuenta filas duplicadas según una clave de negocio (p. ej. cooperativa+fecha+codigo).

    Un duplicado en la clave de negocio (a diferencia de un duplicado exacto
    de fila) es más grave: implica que hay dos valores distintos para lo que
    debería ser una sola observación, y cualquier `pivot`/`groupby` corriente
    arriba puede estar promediando o eligiendo el primero silenciosamente.
    """
    faltan = [c for c in columnas_clave if c not in df.columns]
    if faltan:
        return {"valido": False, "motivo": f"Faltan columnas: {faltan}"}

    n_total = len(df)
    n_duplicados_clave = int(df.duplicated(subset=columnas_clave, keep=False).sum())
    df_dup = df[df.duplicated(subset=columnas_clave, keep=False)]
    valores_distintos = 0
    if not df_dup.empty and "valor" in df.columns:
        valores_distintos = int(
            df_dup.groupby(columnas_clave, observed=True)["valor"].nunique().gt(1).sum()
        )

    return {
        "valido": True,
        "registros_totales": n_total,
        "registros_con_clave_duplicada": n_duplicados_clave,
        "pct_duplicados": round(n_duplicados_clave / n_total * 100, 3) if n_total else 0.0,
        "claves_con_valores_distintos": valores_distintos,
    }


def validar_faltantes(df: pd.DataFrame, columnas: list[str]) -> pd.DataFrame:
    """% de valores nulos/NaN por columna."""
    registros = []
    for col in columnas:
        if col not in df.columns:
            continue
        n_nulos = int(df[col].isna().sum())
        registros.append({
            "columna": col,
            "nulos": n_nulos,
            "pct_nulos": round(n_nulos / len(df) * 100, 3) if len(df) else 0.0,
        })
    return pd.DataFrame(registros)


def detectar_denominadores_cero(df_ranking: pd.DataFrame, fecha, codigo_denominador: str) -> pd.DataFrame:
    """
    Cooperativas donde el valor de una cuenta usada típicamente como
    denominador (activos, depósitos, cartera) es cero o negativo en una
    fecha — cualquier ratio que las use dividirá por cero/negativo. Se
    reporta para excluir explícitamente, no para que un ratio silencioso
    produzca inf/NaN/valor absurdo.
    """
    mask = (df_ranking["fecha"] == fecha) & (df_ranking["codigo"] == codigo_denominador)
    df_f = df_ranking[mask]
    problema = df_f[df_f["valor"] <= 0]
    return problema[["cooperativa", "segmento", "valor"]].rename(columns={"valor": "valor_denominador"})


def detectar_entidades_nuevas_y_desaparecidas(
    df: pd.DataFrame, fecha_actual, fecha_anterior, columna_entidad: str = "cooperativa"
) -> Dict[str, Any]:
    """
    Compara el catálogo de entidades presentes en dos fechas.

    "Desaparecida" es un hallazgo de DATOS (puede ser liquidación, fusión,
    absorción, o simplemente que ese mes no reportó a tiempo) — no un
    diagnóstico. Ver `analytics.eventos.detectar_eventos_entidad()` para una
    clasificación best-effort con más contexto.
    """
    entidades_actual = set(df.loc[df["fecha"] == fecha_actual, columna_entidad].astype(str).unique())
    entidades_anterior = set(df.loc[df["fecha"] == fecha_anterior, columna_entidad].astype(str).unique())

    return {
        "fecha_actual": fecha_actual,
        "fecha_anterior": fecha_anterior,
        "nuevas": sorted(entidades_actual - entidades_anterior),
        "desaparecidas": sorted(entidades_anterior - entidades_actual),
        "n_nuevas": len(entidades_actual - entidades_anterior),
        "n_desaparecidas": len(entidades_anterior - entidades_actual),
    }


def detectar_cambios_de_segmento(df_segmento_historico: pd.DataFrame) -> pd.DataFrame:
    """
    Lista cooperativas cuyo `segmento_historico` varía entre fechas (usa la
    salida de `utils.data_loader.cargar_segmento_historico()`).

    Sirve como advertencia para cualquier análisis "por segmento a través
    del tiempo": si no se usa `segmento_historico` (sino el `segmento_actual`
    aplicado retroactivamente), estas cooperativas contaminan silenciosamente
    la serie histórica del segmento al que NO pertenecían en ese momento.
    """
    if df_segmento_historico.empty:
        return pd.DataFrame(columns=["cooperativa", "n_segmentos_historicos", "segmentos"])

    g = df_segmento_historico.groupby("cooperativa", observed=True)["segmento_historico"]
    conteo = g.nunique()
    cambiaron = conteo[conteo > 1]
    if cambiaron.empty:
        return pd.DataFrame(columns=["cooperativa", "n_segmentos_historicos", "segmentos"])

    detalle = []
    for coop in cambiaron.index:
        segs = sorted(
            df_segmento_historico.loc[df_segmento_historico["cooperativa"] == coop, "segmento_historico"]
            .astype(str).unique()
        )
        detalle.append({"cooperativa": coop, "n_segmentos_historicos": len(segs), "segmentos": segs})
    return pd.DataFrame(detalle).sort_values("n_segmentos_historicos", ascending=False)


def detectar_cambios_abruptos(
    df_ranking: pd.DataFrame, codigo: str, umbral_pct: float = 50.0
) -> pd.DataFrame:
    """
    Variaciones mes a mes de una cuenta que superan `umbral_pct` en valor
    absoluto, por cooperativa. Una variación así de grande es tan
    probablemente un reclasificación contable o un error de captura como un
    evento financiero real — se reporta para revisión, no se asume ninguna
    de las dos causas.
    """
    df_f = df_ranking[df_ranking["codigo"] == codigo].copy()
    if df_f.empty:
        return pd.DataFrame(columns=["cooperativa", "fecha", "valor", "valor_anterior", "variacion_pct"])

    df_f = df_f.sort_values(["cooperativa", "fecha"])
    df_f["valor_anterior"] = df_f.groupby("cooperativa", observed=True)["valor"].shift(1)
    df_f["variacion_pct"] = (
        (df_f["valor"] - df_f["valor_anterior"]) / df_f["valor_anterior"].abs() * 100
    )
    resultado = df_f[df_f["variacion_pct"].abs() >= umbral_pct]
    return resultado[["cooperativa", "fecha", "valor", "valor_anterior", "variacion_pct"]].dropna(
        subset=["variacion_pct"]
    )


def reporte_calidad_fecha(
    df_indicadores: pd.DataFrame, df_ranking: pd.DataFrame, fecha,
) -> Dict[str, Any]:
    """
    Reporte consolidado de calidad de datos para una fecha específica —
    punto de entrada recomendado antes de calcular alertas/breadth para esa
    fecha. Combina los chequeos anteriores en un solo resultado con un
    veredicto simple (`confiable: bool`) y las razones si no lo es.
    """
    razones = []

    validacion_fechas = validar_fechas(df_indicadores)
    if validacion_fechas.get("tiene_huecos"):
        razones.append(
            f"{len(validacion_fechas['meses_faltantes'])} mes(es) faltantes en la serie de indicadores"
        )

    dup = validar_duplicados(df_indicadores[df_indicadores["fecha"] == fecha],
                              ["cooperativa", "codigo"])
    if dup.get("valido") and dup["registros_con_clave_duplicada"] > 0:
        razones.append(
            f"{dup['registros_con_clave_duplicada']} registros con clave "
            f"(cooperativa, codigo) duplicada en {fecha}"
        )

    denom_cero = detectar_denominadores_cero(df_ranking, fecha, codigo_denominador="1")
    if not denom_cero.empty:
        razones.append(f"{len(denom_cero)} entidades con Activos <= 0 en {fecha}")

    return {
        "fecha": fecha,
        "confiable": len(razones) == 0,
        "razones": razones,
        "detalle_fechas": validacion_fechas,
        "detalle_duplicados": dup,
        "detalle_denominadores_cero": denom_cero,
    }
