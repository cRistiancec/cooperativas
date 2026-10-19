# -*- coding: utf-8 -*-
"""
Optimización de peso de los Parquet de `master_data/` SIN pérdida de datos.

El formato ya es Parquet (columnar); el peso se reduce con tres palancas:
  1. Orden físico de filas por (cooperativa, código, fecha): agrupa series
     parecidas y hace que la codificación delta/diccionario y el compresor
     trabajen sobre valores contiguos.
  2. Compresión zstd (nivel 9; 19 para archivos pequeños) en lugar de snappy.
  3. Grupos de filas grandes (1 M) con estadísticas min/max por columna.

Garantías:
  - Lossless: tras escribir se relee el archivo temporal y se compara contra
    la tabla ordenada en memoria, bit a bit (los float se comparan por su
    representación int64, así que NaN y -0.0 cuentan). Mismo número de filas
    y mismo esquema (incluidos los metadatos de pandas).
  - Atómico: escribe a un temporal y usa os.replace().
  - Idempotente: si el resultado no es menor que el actual, no reemplaza.
  - El orden de filas es lo único que cambia. Ningún consumidor del
    repositorio depende de él (las pruebas lo verifican).

Uso:
    python scripts/optimizar_parquet.py              # optimiza master_data/*.parquet
    python scripts/optimizar_parquet.py --dry-run    # solo informa
    python scripts/optimizar_parquet.py archivo.parquet [...]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

RAIZ = Path(__file__).resolve().parents[1]
MD = RAIZ / "master_data"

# Claves de ordenamiento por archivo (las que existan en el esquema).
CLAVES = {
    "balance": ["cooperativa", "codigo", "fecha"],
    "pyg": ["cooperativa", "codigo", "fecha"],
    "indicadores": ["cooperativa", "fecha"],
    "panel_vulnerabilidad": ["cooperativa", "fecha"],
    "solvencia": ["ruc", "fecha"],
}
UMBRAL_PEQUENO = 10 * 1024 * 1024  # bytes: por debajo se usa zstd 19
FILAS_POR_GRUPO = 1_000_000


def _claves_enteras(t: pa.Table, claves: list[str]) -> pa.Table:
    """Tabla auxiliar de claves ordenables (los diccionarios pasan a índices)."""
    cols = {}
    for k in claves:
        c = t[k]
        if pa.types.is_dictionary(c.type):
            c = c.combine_chunks().indices
        cols[k] = c
    return pa.table(cols)


def ordenar(t: pa.Table, claves: list[str]) -> pa.Table:
    claves = [k for k in claves if k in t.schema.names]
    if not claves:
        return t
    t = t.unify_dictionaries()
    idx = pc.sort_indices(_claves_enteras(t, claves), sort_keys=[(k, "ascending") for k in claves])
    return t.take(idx)


def _bits(col: pa.ChunkedArray) -> pa.ChunkedArray:
    """Vista exacta para comparar: floats por bits; diccionarios decodificados."""
    if pa.types.is_dictionary(col.type):
        col = col.cast(col.type.value_type)
    if pa.types.is_floating(col.type):
        col = col.cast(pa.float64()).combine_chunks().view(pa.int64())
        return pa.chunked_array([col])
    return col


def iguales(a: pa.Table, b: pa.Table) -> bool:
    if a.num_rows != b.num_rows or a.schema.names != b.schema.names:
        return False
    paso = 2_000_000
    for i in range(0, a.num_rows, paso):
        sa, sb = a.slice(i, paso), b.slice(i, paso)
        for n in a.schema.names:
            if not _bits(sa[n]).equals(_bits(sb[n])):
                return False
    return True


def optimizar(ruta: Path, dry_run: bool = False) -> dict:
    ruta = Path(ruta)
    antes = ruta.stat().st_size
    original = pq.read_table(ruta)
    ordenada = ordenar(original, CLAVES.get(ruta.stem, []))
    nivel = 19 if antes < UMBRAL_PEQUENO else 9
    tmp = ruta.with_name(f".{ruta.name}.tmp_opt")
    info = {"archivo": ruta.name, "antes": antes, "filas": original.num_rows}
    try:
        pq.write_table(
            ordenada, tmp, compression="zstd", compression_level=nivel,
            row_group_size=FILAS_POR_GRUPO, write_statistics=True,
        )
        despues = tmp.stat().st_size
        info["despues"] = despues
        if not iguales(ordenada, pq.read_table(tmp)):
            raise RuntimeError(f"{ruta.name}: la verificación bit a bit falló; no se reemplaza")
        if pq.read_metadata(tmp).num_rows != original.num_rows:
            raise RuntimeError(f"{ruta.name}: número de filas distinto")
        if dry_run or despues >= antes:
            info["reemplazado"] = False
            tmp.unlink(missing_ok=True)
        else:
            os.replace(tmp, ruta)
            info["reemplazado"] = True
    finally:
        tmp.unlink(missing_ok=True)
    return info


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("archivos", nargs="*")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    archivos = [Path(x) for x in a.archivos] or sorted(MD.glob("*.parquet"))
    tot_a = tot_d = 0
    for f in archivos:
        r = optimizar(f, a.dry_run)
        d = r.get("despues", r["antes"]) if r.get("reemplazado") or a.dry_run else r["antes"]
        tot_a += r["antes"]; tot_d += d
        print(f"{r['archivo']:42s} {r['antes']/1e6:8.2f} -> {r.get('despues', r['antes'])/1e6:8.2f} MB"
              f"  {'(reemplazado)' if r.get('reemplazado') else '(sin cambio)'}", flush=True)
    print(f"TOTAL {tot_a/1e6:.1f} -> {tot_d/1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
