# -*- coding: utf-8 -*-
"""
Dimensión de observaciones para el filtrado global: una fila por (cooperativa, fecha).

Contiene, por observación entidad-mes presente en `balance.parquet`, `pyg.parquet` o `indicadores.parquet` (excluye los subtotales VT_TOTAL*):
  - entidad            identidad estable (sin sufijo «EN LIQUIDACION»); clave del filtro de entidades.
  - cooperativa        nombre tal como figura en las bases (clave de unión).
  - segmento_clasif    clasificación PUNTUAL del período (`segmento_historico` del balance). Nunca se
                       reconstruye ni se completa con el segmento actual.
  - segmento_actual    segmento vigente hoy (informativo; NO se usa para filtrar el historial).
  - procedencia_clasif oficial_mes | arrastrado | estimado | no_verificable
  - fuente_clasif      archivo SEPS que sustenta la clasificación (trazabilidad).

Reglas de procedencia (en este orden):
  1. `segmento_historico_estimado` = True  -> estimado
  2. la dimensión histórica dice es_arrastrado = False -> oficial_mes
  3. la dimensión histórica dice es_arrastrado = True  -> arrastrado
  4. cualquier otro caso (sin respaldo en la dimensión) -> no_verificable y `segmento_clasif` = NaN:
     no se asigna un segmento sin evidencia.

Es un derivado PEQUEÑO (≈20 mil filas) de datos ya validados; no reprocesa el balance.
Idempotente y atómico. Uso: python scripts/generar_dim_observaciones.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from analytics.vulnerabilidad.identidad import entidad_id  # noqa: E402

MD = RAIZ / "master_data"
SALIDA = MD / "dim_observaciones.parquet"
PROCEDENCIAS = ["oficial_mes", "arrastrado", "estimado", "no_verificable"]


def construir(md: Path = MD) -> pd.DataFrame:
    cols = ["cooperativa", "fecha", "segmento_historico", "segmento_historico_estimado", "segmento_actual"]

    def leer(archivo: str) -> pd.DataFrame:
        x = pq.read_table(md / archivo, columns=cols).to_pandas()
        for c in ("cooperativa", "segmento_historico", "segmento_actual"):
            x[c] = x[c].astype("object")
        x = x[~x["cooperativa"].astype(str).str.startswith("VT_TOTAL")]          # subtotales del reporte, no entidades
        n_seg = x.groupby(["cooperativa", "fecha"])["segmento_historico"].nunique(dropna=False).max()
        if n_seg > 1:
            raise SystemExit(f"{archivo}: más de un segmento histórico por entidad-mes ({n_seg}); no se genera la dimensión")
        return x.drop_duplicates(["cooperativa", "fecha"])

    # Universo = observaciones entidad-mes presentes en balance, PyG o indicadores. Cuando una misma observación
    # está en varias bases manda la primera (balance > PyG > indicadores).
    b = leer("balance.parquet")
    for archivo in ("pyg.parquet", "indicadores.parquet"):
        x = leer(archivo)
        nuevo = x.merge(b[["cooperativa", "fecha"]], on=["cooperativa", "fecha"], how="left", indicator=True)
        b = pd.concat([b, nuevo[nuevo["_merge"] == "left_only"].drop(columns="_merge")], ignore_index=True)
    dim = pd.read_parquet(md / "dim_segmento_historico.parquet", columns=["cooperativa", "fecha", "es_arrastrado", "fuente"])
    dim["cooperativa"] = dim["cooperativa"].astype("object")
    n0 = len(b)
    b = b.merge(dim, on=["cooperativa", "fecha"], how="left", validate="many_to_one")
    assert len(b) == n0, "la unión con la dimensión duplicó observaciones"

    est = b["segmento_historico_estimado"].fillna(False).astype(bool)
    proc = np.select([est, b["es_arrastrado"].eq(False), b["es_arrastrado"].eq(True)],
                     ["estimado", "oficial_mes", "arrastrado"], "no_verificable")
    out = pd.DataFrame({
        "entidad": b["cooperativa"].map(entidad_id),
        "cooperativa": b["cooperativa"],
        "fecha": pd.to_datetime(b["fecha"]),
        "segmento_clasif": b["segmento_historico"].where(proc != "no_verificable"),
        "segmento_actual": b["segmento_actual"],
        "procedencia_clasif": proc,
        "fuente_clasif": b["fuente"].where(proc != "estimado", "estimado (backfill)").fillna("sin respaldo en la dimensión"),
    })
    out = out.sort_values(["entidad", "cooperativa", "fecha"]).reset_index(drop=True)
    for c in ("entidad", "cooperativa", "segmento_clasif", "segmento_actual", "procedencia_clasif", "fuente_clasif"):
        out[c] = out[c].astype("category")
    assert not out.duplicated(["cooperativa", "fecha"]).any()
    return out


def main() -> int:
    d = construir()
    tmp = SALIDA.with_name(f".{SALIDA.name}.tmp")
    try:
        d.to_parquet(tmp, index=False, compression="zstd", compression_level=19)
        os.replace(tmp, SALIDA)
    finally:
        tmp.unlink(missing_ok=True)
    print(f"{SALIDA.name}: {len(d)} observaciones, {d['entidad'].nunique()} entidades, "
          f"{d['fecha'].min():%Y-%m} a {d['fecha'].max():%Y-%m}")
    print(d["procedencia_clasif"].value_counts().to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
