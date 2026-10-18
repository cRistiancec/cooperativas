"""Cobertura de la clasificación de segmento por año, mes y segmento (procedencia), y sensibilidad exacto vs. todo."""
import numpy as np, pandas as pd
from . import panel_fe

CATEGORIAS = ["exacto_mes", "arrastrado", "estimado", "sin_clasificacion_verificable"]

def tabla_cobertura(P: pd.DataFrame) -> pd.DataFrame:
    """Una fila por fecha x segmento, con conteos y % por categoría de procedencia del segmento."""
    d = P.assign(proc=P.segmento_procedencia.where(P.segmento_procedencia.isin(CATEGORIAS), "sin_clasificacion_verificable"))
    t = d.groupby([d.fecha.dt.year.rename("anio"), d.fecha.dt.month.rename("mes"), "segmento_repo", "proc"]).size().unstack("proc", fill_value=0)
    for c in CATEGORIAS: t[c] = t.get(c, 0)
    t = t[CATEGORIAS]; t.insert(0, "observaciones", t.sum(axis=1))
    for c in CATEGORIAS: t["pct_" + c] = (t[c] / t["observaciones"] * 100).round(1)
    return t.reset_index().rename(columns={"segmento_repo": "segmento"})

def sensibilidad(P: pd.DataFrame, I: pd.DataFrame) -> dict:
    """¿Cambian las diferencias entre segmentos si solo se usa la clasificación exacta del mes?"""
    d = P.merge(I[["cooperativa", "fecha", "indice_eq"]], on=["cooperativa", "fecha"])
    ex = d[d.segmento_procedencia == "exacto_mes"]
    med = lambda x: x.groupby("segmento_repo").indice_eq.median().round(4).to_dict()
    out = {"n_todas": int(len(d)), "n_exactas": int(len(ex)), "pct_exactas": round(len(ex) / len(d) * 100, 1),
           "mediana_indice_todas": med(d), "mediana_indice_exactas": med(ex)}
    for nombre, x in [("todas", P), ("solo_exactas", P[P.segmento_procedencia == "exacto_mes"])]:
        r = panel_fe.estimar(x, I, rezago=False)
        out["FE_" + nombre] = {"n_obs": r["n_obs"], "coop_con_reclasificacion": r["coop_con_reclasificacion"],
                               "M2": {k: {"coef": round(v["coef"], 4), "p": round(v["p"], 4)} for k, v in r["M2_segmento_FE"].items() if k in ("s2", "s3")},
                               "wald_heterogeneidad_p": round(r["M3_wald_heterogeneidad"]["p"], 4)}
    return out
