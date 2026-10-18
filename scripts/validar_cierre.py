#!/usr/bin/env python3
"""Validación de SOLO LECTURA de master_data/ (no reprocesa nada). Salida: docs/cierre/validacion_componentes.json"""
import json, sys, numpy as np, pandas as pd, pyarrow.parquet as pq
from pathlib import Path
MD = Path("master_data"); OUT = Path("docs/cierre"); OUT.mkdir(parents=True, exist_ok=True)
SEG = "segmento_historico"
CORTE = pd.Timestamp(json.load(open(MD/"metadata.json"))["fecha_max"])
def cols(f): return pq.ParquetFile(MD/f).schema_arrow.names
def leer(f, c):
    c = [x for x in c if x in cols(f)]
    return pd.read_parquet(MD/f, columns=c)
res = {}
claves = {"pyg.parquet": ["cooperativa","fecha","codigo"], "indicadores.parquet": ["cooperativa","fecha","codigo"],
          "agg_series_temporales.parquet": ["cooperativa","fecha","codigo"], "dim_segmento_historico.parquet": ["cooperativa","fecha"],
          "solvencia.parquet": ["ruc","fecha"], "entidades_cooperativas.parquet": ["nombre"]}
for f, k in claves.items():
    cs = cols(f); d = leer(f, list(dict.fromkeys(k + [c for c in ["segmento","segmento_historico","segmento_historico_estimado","valor","valor_acumulado","es_arrastrado"] if c in cs])))
    r = {"filas": len(d), "duplicados_clave": int(d.duplicated(k).sum()), "clave": k}
    if "fecha" in d:
        fm = d.fecha.max(); r["fecha_max"] = str(pd.Timestamp(fm).date()); r["fecha_min"] = str(pd.Timestamp(d.fecha.min()).date())
        ent = "cooperativa" if "cooperativa" in d else None
        if ent:
            r["entidades"] = int(d[ent].nunique()); u = d[d.fecha == fm]; r["entidades_ultimo_corte"] = int(u[ent].nunique())
            sc = SEG if SEG in u else ("segmento" if "segmento" in u else None)
            if sc: r["entidades_por_segmento_ultimo_corte"] = u.groupby(sc, observed=True)[ent].nunique().to_dict()
    for v in ["valor","valor_acumulado"]:
        if v in d: r["nulos_"+v+"_pct"] = round(float(d[v].isna().mean()*100), 4); r["inf_"+v] = int(np.isinf(d[v].astype(float)).sum())
    if "segmento_historico_estimado" in d: r["estimado_pct"] = round(float(d.segmento_historico_estimado.astype(bool).mean()*100), 3)
    if "segmento_historico" in d: r["segmento_historico_nulo_pct"] = round(float(d.segmento_historico.isna().mean()*100), 3)
    res[f] = r
# balance por lotes
pf = pq.ParquetFile(MD/"balance.parquet"); n = 0; dup = 0; nul = 0; fmax = None; ents = set(); est = 0
ult = {}
for rb in pf.iter_batches(batch_size=2_000_000, columns=["fecha","cooperativa","codigo","valor","segmento_historico","segmento_historico_estimado"]):
    d = rb.to_pandas(); n += len(d); nul += int(d.valor.isna().sum()); est += int(d.segmento_historico_estimado.astype(bool).sum())
    fm = d.fecha.max(); fmax = fm if fmax is None else max(fmax, fm); ents |= set(d.cooperativa.astype(str).unique())
    u = d[d.fecha == CORTE]
    if len(u): ult.setdefault("filas", 0); ult["filas"] += len(u); ult.setdefault("segs", {}); [ult["segs"].setdefault(s, set()).update(g.cooperativa.astype(str)) for s, g in u.groupby("segmento_historico", observed=True)]
res["balance.parquet"] = {"filas": n, "fecha_max": str(pd.Timestamp(fmax).date()), "entidades": len(ents), "nulos_valor_pct": round(nul/n*100, 5),
    "estimado_pct": round(est/n*100, 3), "filas_corte": ult.get("filas", 0),
    "entidades_por_segmento_corte": {k: len(v) for k, v in ult.get("segs", {}).items()}}
# duplicados del balance (clave) en el corte más reciente y en una muestra de años
b = pd.read_parquet(MD/"balance.parquet", columns=["fecha","cooperativa","codigo"], filters=[("fecha", ">=", pd.Timestamp("2026-01-01"))])
res["balance.parquet"]["duplicados_clave_2026"] = int(b.duplicated().sum()); del b
# segmentación: arrastre por mes (dim)
D = pd.read_parquet(MD/"dim_segmento_historico.parquet")
m = D.groupby("fecha").agg(n=("cooperativa","size"), arrastrado=("es_arrastrado","mean")).reset_index()
res["segmentacion_meses_recientes"] = {str(r.fecha.date()): {"entidades": int(r.n), "pct_arrastrado": round(float(r.arrastrado*100),1)} for r in m.tail(8).itertuples()}
res["segmentacion_fuentes"] = D.fuente.value_counts().to_dict()
res["segmentacion_cortes_origen_ultimos_meses"] = {str(k.date()): str(pd.Timestamp(v).date()) for k, v in D[D.fecha >= "2026-05-01"].groupby("fecha").fecha_corte_origen.max().items()}
# consistencia de entidades entre componentes (último corte)
ult = CORTE
pyg = leer("pyg.parquet", ["cooperativa","fecha"]); ind = leer("indicadores.parquet", ["cooperativa","fecha"]); dm = D[D.fecha == ult]
bal_u = set(ult_ for ult_ in [])  # placeholder para claridad
res["consistencia_entidades_2026-09-30"] = {"pyg": int(pyg[pyg.fecha==ult].cooperativa.nunique()), "indicadores": int(ind[ind.fecha==ult].cooperativa.nunique()),
    "dim_segmento": int(dm.cooperativa.nunique()), "balance": res["balance.parquet"]["entidades_por_segmento_corte"]}
json.dump(res, open(OUT/"validacion_componentes.json", "w"), indent=1, ensure_ascii=False, default=str)
if "--estricto" in sys.argv:       # errores BLOQUEANTES (exit 1); las advertencias informativas no bloquean
    esperado = json.load(open(MD/"metadata.json"))["fecha_max"][:10]; err = []
    for k, r in res.items():
        if not (isinstance(r, dict) and "filas" in r): continue
        if r.get("fecha_max") and r["fecha_max"] != esperado and k not in ("entidades_cooperativas.parquet",): err.append(f"{k}: fecha_max {r['fecha_max']} != corte esperado {esperado}")
        for c in ("duplicados_clave", "duplicados_clave_2026"):
            if r.get(c): err.append(f"{k}: {r[c]} duplicados de clave")
    seg = res["balance.parquet"]["entidades_por_segmento_corte"] if False else res["balance.parquet"].get("entidades_por_segmento_corte", {})
    for s in ("SEGMENTO 1", "SEGMENTO 2", "SEGMENTO 3"):
        if not seg.get(s): err.append(f"balance: sin entidades de {s} en el corte {esperado}")
    if err: print("ERRORES BLOQUEANTES:\n  " + "\n  ".join(err)); sys.exit(1)
    print("Validación estricta OK (corte %s)" % esperado)
print(json.dumps(res, indent=1, ensure_ascii=False, default=str))
