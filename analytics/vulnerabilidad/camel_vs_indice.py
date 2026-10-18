"""Asociación (NO validación predictiva) entre el score CAMEL existente y el índice de vulnerabilidad.
Misma población y fecha: cooperativas S1-S3 presentes en ambos. CAMEL: 100 = mejor; índice: alto = más vulnerable => signo esperado negativo.
Uso: python -m analytics.vulnerabilidad.camel_vs_indice <salida.json>"""
import sys, json, numpy as np, pandas as pd
from analytics.financial_engine import calcular_score_camel

def main(salida):
    ind = pd.read_parquet("master_data/indicadores.parquet"); ind["fecha"] = pd.to_datetime(ind.fecha)
    P = pd.read_parquet("master_data/panel_vulnerabilidad.parquet")[["cooperativa_fuente", "cooperativa", "fecha", "indice_eq"]]
    filas = []
    for f in sorted(P.fecha.unique()):
        if f < ind.fecha.min(): continue
        s = calcular_score_camel(ind, pd.Timestamp(f), "Todos")
        if s.empty: continue
        m = s[["cooperativa", "score_total"]].merge(P[P.fecha == f], left_on="cooperativa", right_on="cooperativa_fuente", suffixes=("_camel", ""))
        m = m.dropna(subset=["score_total", "indice_eq"])
        if len(m) > 10: filas.append({"fecha": str(pd.Timestamp(f).date()), "n": int(len(m)), "spearman": float(m.score_total.corr(m.indice_eq, method="spearman"))})
    t = pd.DataFrame(filas)
    res = {"n_fechas": int(len(t)), "n_minimo": int(t.n.min()), "n_maximo": int(t.n.max()), "spearman_mediana": float(t.spearman.median()),
           "spearman_min": float(t.spearman.min()), "spearman_max": float(t.spearman.max()), "ultimo_corte": filas[-1],
           "interpretacion": "Asociación transversal por fecha. Ambos índices comparten insumos (morosidad, cobertura, ROA, liquidez), por lo que parte de la asociación es mecánica; "
                             "CAMEL usa percentiles dentro del universo y el índice usa z pooled winsorizado. No es validación predictiva ni de criterio externo."}
    json.dump(res, open(salida, "w"), indent=1, ensure_ascii=False); print(json.dumps(res, indent=1, ensure_ascii=False))

if __name__ == "__main__":
    main(sys.argv[1])
