"""Panel con efectos fijos de entidad y tiempo; errores agrupados por cooperativa.
El efecto del segmento se identifica SOLO por reclasificaciones dentro de la entidad."""
import numpy as np, pandas as pd
import statsmodels.formula.api as smf

def _fit(df, formula):
    return smf.ols(formula, data=df).fit(cov_type="cluster", cov_kwds={"groups": df["g"]})

def _tabla(res, claves):
    ci = res.conf_int()
    return {c: {"coef": float(res.params[c]), "ee": float(res.bse[c]), "p": float(res.pvalues[c]),
                "ic95": [float(ci.loc[c, 0]), float(ci.loc[c, 1])]} for c in claves if c in res.params}

def estimar(P: pd.DataFrame, I: pd.DataFrame) -> dict:
    d = P.merge(I[["cooperativa", "fecha", "indice_eq"]], on=["cooperativa", "fecha"])
    d = d.sort_values(["cooperativa", "fecha"])
    d["crec"] = d.crec_activos_12m.clip(*d.crec_activos_12m.quantile([.01, .99]))
    d["s2"] = (d.segmento_repo == "SEGMENTO 2").astype(int)
    d["s3"] = (d.segmento_repo == "SEGMENTO 3").astype(int)
    d["f"] = d.fecha.dt.strftime("%Y%m"); d["g"] = d.cooperativa
    d = d.dropna(subset=["indice_eq", "ln_activos", "crec"]).copy()
    # reclasificaciones dentro de la entidad (identificación del efecto segmento)
    nseg = d.groupby("cooperativa").segmento_repo.nunique()
    out = {"n_obs": int(len(d)), "n_coop": int(d.cooperativa.nunique()),
           "coop_con_reclasificacion": int((nseg > 1).sum())}
    base = "indice_eq ~ {} + C(cooperativa) + C(f)"
    m1 = _fit(d, base.format("ln_activos + crec"))
    out["M1_tamano_crecimiento"] = _tabla(m1, ["ln_activos", "crec"])
    m2 = _fit(d, base.format("s2 + s3 + ln_activos + crec"))
    out["M2_segmento_FE"] = _tabla(m2, ["s2", "s3", "ln_activos", "crec"])
    # heterogeneidad por segmento de la sensibilidad al crecimiento
    m3 = _fit(d, base.format("s2 + s3 + ln_activos + crec + crec:s2 + crec:s3"))
    out["M3_interacciones"] = _tabla(m3, ["crec", "crec:s2", "crec:s3"])
    wald = m3.wald_test("crec:s2 = 0, crec:s3 = 0", scalar=True)
    out["M3_wald_heterogeneidad"] = {"estadistico": float(wald.statistic), "p": float(wald.pvalue)}
    # Rezago: ¿el crecimiento pasado predice vulnerabilidad futura (t+12)? sin FE de tiempo cuestionable -> con FE
    d["I_f12"] = d.groupby("cooperativa").indice_eq.shift(-12)
    d2 = d.dropna(subset=["I_f12"])
    m4 = _fit(d2, "I_f12 ~ indice_eq + crec + ln_activos + C(cooperativa) + C(f)")
    out["M4_I_t+12"] = _tabla(m4, ["indice_eq", "crec", "ln_activos"]); out["M4_n"] = int(len(d2))
    out["nota"] = ("Errores agrupados por cooperativa. Con efectos fijos de entidad, el coeficiente de segmento "
                   "proviene solo de reclasificaciones; no es una comparación entre entidades.")
    return out
