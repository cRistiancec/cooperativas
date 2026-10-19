#!/usr/bin/env python3
"""Corrección trazable de nombres con mojibake (UTF-8 leído como cp1252) en master_data/.

Causa raíz: los ZIP mensuales 2018-2021 se leyeron con otra codificación y `normalizar_nombre` no lo reparaba, de modo que
17 cooperativas aparecían con DOS identidades (mojibake 2018-2021 / limpia 2022+) sin solape de fechas.
Esta rutina: (1) construye la tabla de equivalencias (nombre de la fuente -> nombre corregido), (2) renombra en balance
(por lotes) y en la dimensión de segmentos, verificando que NO se creen duplicados de clave, (3) deja la tabla en
master_data/equivalencias_nombres.csv. Los agregados y la tabla de entidades se regeneran después con sus scripts.
Idempotente: si no quedan nombres con mojibake, no hace nada.  Uso: python scripts/corregir_nombres.py [--dry-run]"""
import re, sys, json
from pathlib import Path
import pandas as pd, pyarrow as pa, pyarrow.parquet as pq
sys.path.insert(0, str(Path(__file__).parent))
from procesar_balance_cooperativas import normalizar_nombre   # incluye reparar_mojibake
MD = Path("master_data"); MARK = re.compile("[ÃÂ]")

def main(dry=False):
    pf = pq.ParquetFile(MD / "balance.parquet"); filas = {}
    for rb in pf.iter_batches(batch_size=3_000_000, columns=["cooperativa", "fecha"]):
        d = rb.to_pandas(); d["cooperativa"] = d.cooperativa.astype(str)
        for n, g in d.groupby("cooperativa"):
            a = filas.setdefault(n, [0, g.fecha.min(), g.fecha.max()]); a[0] += len(g); a[1] = min(a[1], g.fecha.min()); a[2] = max(a[2], g.fecha.max())
    malos = sorted(n for n in filas if MARK.search(n))
    if not malos:
        print("Sin nombres con mojibake. Nada que hacer."); return
    eq = pd.DataFrame([{"nombre_fuente": n, "nombre_corregido": normalizar_nombre(n), "regla": "reparar_mojibake(cp1252->utf8)+normalizar_nombre",
                        "filas_balance": filas[n][0], "fecha_min": filas[n][1].date(), "fecha_max": filas[n][2].date(),
                        "gemelo_existente_en_balance": normalizar_nombre(n) in filas and normalizar_nombre(n) != n} for n in malos])
    mapa = dict(zip(eq.nombre_fuente, eq.nombre_corregido))
    # verificación: ninguna fecha compartida entre la identidad mojibake y su gemela limpia (si no, habría duplicados de clave)
    for n, c in mapa.items():
        if c in filas and not (filas[n][2] < filas[c][1] or filas[c][2] < filas[n][1]):
            raise SystemExit(f"ABORTA: fechas solapadas entre '{n}' y '{c}'")
    print(eq[["nombre_fuente", "nombre_corregido", "filas_balance", "gemelo_existente_en_balance"]].to_string())
    if dry: return
    # balance por lotes (conserva esquema y orden)
    tmp = MD / "balance.parquet.tmp"; w = pq.ParquetWriter(tmp, pf.schema_arrow, compression="zstd"); n_in = n_out = 0
    for rb in pf.iter_batches(batch_size=2_000_000):
        t = pa.Table.from_batches([rb]); col = pd.Series(t["cooperativa"].to_pandas().astype(str)).replace(mapa)
        t = t.set_column(t.schema.get_field_index("cooperativa"), pf.schema_arrow.field("cooperativa"), pa.array(col.values).cast(pf.schema_arrow.field("cooperativa").type))
        w.write_table(t); n_in += rb.num_rows; n_out += t.num_rows
    w.close(); assert n_in == n_out; tmp.replace(MD / "balance.parquet")
    # dimensión de segmentos: renombrar y resolver colisiones (exacto > arrastrado; luego corte de origen más reciente)
    D = pd.read_parquet(MD / "dim_segmento_historico.parquet"); D["cooperativa"] = D.cooperativa.astype(str)
    D["cooperativa"] = D.cooperativa.map(lambda x: normalizar_nombre(x) if MARK.search(x) else x)
    ant = len(D); D = D.sort_values(["cooperativa", "fecha", "es_arrastrado", "fecha_corte_origen"], ascending=[True, True, True, False])
    disc = D.groupby(["cooperativa", "fecha"]).segmento_historico.nunique(); D = D.drop_duplicates(["cooperativa", "fecha"], keep="first")
    D.to_parquet(MD / "dim_segmento_historico.parquet", index=False)
    eq.to_csv(MD / "equivalencias_nombres.csv", index=False)
    json.dump({"balance_filas": n_in, "dim_filas_antes": ant, "dim_filas_despues": len(D), "dim_pares_con_segmentos_en_conflicto": int((disc > 1).sum())},
              open(MD / "equivalencias_nombres_resumen.json", "w"), indent=1)
    print("OK", n_in, ant, len(D), "conflictos de segmento en colisiones:", int((disc > 1).sum()))

if __name__ == "__main__":
    main("--dry-run" in sys.argv)
