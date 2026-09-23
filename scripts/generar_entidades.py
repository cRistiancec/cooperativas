# -*- coding: utf-8 -*-
"""
Genera master_data/entidades_cooperativas.parquet — tabla LIGERA de
identidad de entidades (Sección 16 del pedido de ampliación).

No duplica ruc/segmento en los datasets grandes (balance.parquet,
indicadores.parquet, pyg.parquet): esta tabla es pequeña (una fila por
cooperativa, no por cooperativa×fecha×cuenta) y se genera por separado a
partir de lo que ya existe:

  - `balance.parquet` (vía segmento_historico) → fecha_inicio, fecha_fin,
    segmento_actual, si tuvo más de un segmento histórico.
  - `master_data/solvencia.parquet` (si existe) → RUC, pero SOLO para las
    entidades cubiertas por ese boletín (Segmento 1, Mutualistas, FINANCOOP —
    ver docs/RIESGO_METODOLOGIA.md §3.2). Para Segmento 2/3 el campo `ruc`
    queda NULL: no hay ninguna fuente pública que este proyecto procese con
    RUC para esos segmentos (se descartó de balance.parquet por peso, ver
    CONTEXTO.md "Optimización de memoria", y los archivos fuente XLSM no
    siempre lo incluyen para todos los años).
  - `analytics.eventos.detectar_eventos_salida()` → estado ('activa' /
    'posible_salida') y la fecha de último reporte cuando aplica.

Ejecutar después de procesar balance/indicadores/solvencia:
    python scripts/generar_entidades.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).parent.parent
MASTER_DATA_DIR = BASE_DIR / "master_data"
sys.path.insert(0, str(BASE_DIR))

from analytics.eventos import detectar_eventos_salida  # noqa: E402
from procesar_balance_cooperativas import normalizar_nombre  # noqa: E402 (mismo dir, scripts/)
from io_atomico import guardar_parquet_atomico  # noqa: E402 (mismo dir, scripts/)


def generar_entidades():
    print("=" * 60)
    print("GENERANDO TABLA DE IDENTIDAD DE ENTIDADES")
    print("=" * 60)

    balance_path = MASTER_DATA_DIR / "balance.parquet"
    if not balance_path.exists():
        print(f"  No existe {balance_path}. Abortando.")
        return

    columnas = ["fecha", "cooperativa", "segmento_actual", "segmento_historico",
                "segmento_historico_estimado"]
    try:
        import pyarrow.parquet as pq
        df_bal = pq.read_table(balance_path, columns=columnas).to_pandas()
    except Exception:
        df_bal = pd.read_parquet(balance_path, columns=["fecha", "cooperativa", "segmento"])
        df_bal["segmento_actual"] = df_bal["segmento"]
        df_bal["segmento_historico"] = df_bal["segmento"]
        df_bal["segmento_historico_estimado"] = True

    df_bal = df_bal.drop_duplicates(subset=["fecha", "cooperativa"])

    # --- Rango de fechas y segmento actual por entidad ---
    resumen = df_bal.groupby("cooperativa", observed=True).agg(
        fecha_inicio=("fecha", "min"),
        fecha_fin_datos=("fecha", "max"),
        segmento_actual=("segmento_actual", "last"),
    ).reset_index()
    resumen = resumen.rename(columns={"cooperativa": "nombre"})

    # --- Cambios de segmento histórico ---
    n_segmentos = (
        df_bal.groupby("cooperativa", observed=True)["segmento_historico"].nunique()
        .rename("n_segmentos_historicos").reset_index().rename(columns={"cooperativa": "nombre"})
    )
    resumen = resumen.merge(n_segmentos, on="nombre", how="left")
    resumen["cambio_segmento_detectado"] = resumen["n_segmentos_historicos"] > 1

    pct_estimado = (
        df_bal.groupby("cooperativa", observed=True)["segmento_historico_estimado"].mean()
        .rename("pct_segmento_historico_estimado").reset_index().rename(columns={"cooperativa": "nombre"})
    )
    resumen = resumen.merge(pct_estimado, on="nombre", how="left")

    # --- RUC desde solvencia.parquet (cobertura parcial) ---
    solvencia_path = MASTER_DATA_DIR / "solvencia.parquet"
    resumen["ruc"] = None
    resumen["ruc_fuente"] = "No disponible (sin fuente con RUC para este segmento)"
    if solvencia_path.exists():
        df_solv = pd.read_parquet(solvencia_path, columns=["ruc", "cooperativa"])
        df_solv = df_solv.drop_duplicates(subset=["cooperativa"], keep="last")
        mapa_ruc = df_solv.set_index("cooperativa")["ruc"].astype(str)
        resumen["ruc"] = resumen["nombre"].map(mapa_ruc)
        resumen.loc[resumen["ruc"].notna(), "ruc_fuente"] = (
            "Boletín SEPS Patrimonio Técnico (Segmento 1/Mutualista/FINANCOOP)"
        )

    # --- Estado (activa / posible_salida) ---
    eventos = detectar_eventos_salida(
        df_bal.rename(columns={"cooperativa": "cooperativa"}), columna_entidad="cooperativa"
    )
    eventos = eventos.rename(columns={"cooperativa": "nombre"})
    resumen = resumen.merge(
        eventos[["nombre", "ultima_fecha_reportada", "meses_sin_reportar", "liquidacion_declarada_en_nombre"]],
        on="nombre", how="left",
    )
    resumen["estado"] = "activa"
    resumen.loc[resumen["meses_sin_reportar"].notna(), "estado"] = "posible_salida"
    resumen.loc[resumen["liquidacion_declarada_en_nombre"].fillna(False), "estado"] = "liquidacion_declarada"

    resumen["observaciones"] = ""
    resumen.loc[resumen["estado"] == "posible_salida", "observaciones"] = (
        "Dejó de reportar; causa NO VERIFICADA (puede ser liquidación, fusión, absorción o atraso). "
        "Ver analytics/eventos.py."
    )
    resumen.loc[resumen["estado"] == "liquidacion_declarada", "observaciones"] = (
        "El propio nombre reportado por la SEPS incluye 'EN LIQUIDACION' — evidencia textual directa."
    )
    resumen.loc[resumen["cambio_segmento_detectado"], "observaciones"] += (
        " Cambió de segmento_historico al menos una vez — no usar segmento_actual para análisis histórico."
    )

    columnas_finales = [
        "nombre", "ruc", "ruc_fuente", "segmento_actual", "fecha_inicio", "fecha_fin_datos",
        "estado", "cambio_segmento_detectado", "n_segmentos_historicos",
        "pct_segmento_historico_estimado", "ultima_fecha_reportada", "observaciones",
    ]
    resumen = resumen[columnas_finales].sort_values("nombre").reset_index(drop=True)

    output_path = MASTER_DATA_DIR / "entidades_cooperativas.parquet"
    guardar_parquet_atomico(resumen, output_path, engine="pyarrow", index=False)

    metadata = {
        "fecha_procesamiento": datetime.now().isoformat(),
        "entidades_totales": int(len(resumen)),
        "con_ruc": int(resumen["ruc"].notna().sum()),
        "activas": int((resumen["estado"] == "activa").sum()),
        "posible_salida": int((resumen["estado"] == "posible_salida").sum()),
        "liquidacion_declarada": int((resumen["estado"] == "liquidacion_declarada").sum()),
        "con_cambio_de_segmento_detectado": int(resumen["cambio_segmento_detectado"].sum()),
        "cobertura_ruc": (
            "RUC disponible solo para entidades en master_data/solvencia.parquet "
            "(Segmento 1, Mutualistas, FINANCOOP). Segmento 2/3: ruc=NULL."
        ),
    }
    with open(MASTER_DATA_DIR / "metadata_entidades.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"\n{len(resumen)} entidades -> {output_path}")
    print(f"  Con RUC: {metadata['con_ruc']}  ·  Activas: {metadata['activas']}  ·  "
          f"Posible salida: {metadata['posible_salida']}  ·  Liquidación declarada: {metadata['liquidacion_declarada']}")
    print(f"  Con cambio de segmento detectado: {metadata['con_cambio_de_segmento_detectado']}")


if __name__ == "__main__":
    generar_entidades()
