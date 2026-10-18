"""Uso: python -m analytics.vulnerabilidad.run_all <panel.parquet> <dir_salida>"""
import sys, json, pandas as pd
from . import config as C, indice, panel_fe, alerta

def main(panel, out):
    P = pd.read_parquet(panel); P = P[P.segmento_repo.isin(C.SEGMENTOS)].reset_index(drop=True)
    I, Z, sens = indice.construir(P)
    res = {"indice_sensibilidad": sens}
    d = P.merge(I[["cooperativa", "fecha", "indice_eq"]], on=["cooperativa", "fecha"])
    desc = d.groupby("segmento_repo").indice_eq.describe()[["count", "mean", "50%", "std"]]
    res["indice_por_segmento"] = desc.round(4).to_dict("index")
    res["panel_fe"] = panel_fe.estimar(P, I)
    E = alerta.tabla_eventos(P, C.EVENTOS_CSV)
    res["n_eventos_en_panel"] = int(len(E))
    S = alerta.construir_muestra(P, Z, E)
    m, te = alerta.evaluar(S); res["alerta"] = m
    res["alerta_origenes_rodantes"] = alerta.origenes_rodantes(S)
    res["eventos_fecha"] = {r.cooperativa: str(r.fecha_evento.date()) for r in E.itertuples()}
    res["eventos_con_obs_previas_12m"] = int(S[S.y == 1].cooperativa.nunique())
    I.to_parquet(out + "indice_vulnerabilidad.parquet", index=False)
    json.dump(res, open(out + "resultados_vulnerabilidad.json", "w"), indent=1, ensure_ascii=False)
    print(json.dumps(res, indent=1, ensure_ascii=False))

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2].rstrip("/") + "/")
