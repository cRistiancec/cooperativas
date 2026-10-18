"""Alerta temprana EXPLORATORIA: logit regularizado con partición temporal. ~15 eventos => no confirmatorio."""
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss
from . import config as C

def tabla_eventos(P, ruta_eventos):
    e = pd.read_csv(ruta_eventos, parse_dates=["fecha"])
    e = e[e.cooperativa.isin(P.cooperativa.unique())]
    return e.groupby("cooperativa").fecha.min().rename("fecha_evento").reset_index()

def construir_muestra(P, Z, E):
    d = pd.concat([P[["cooperativa", "fecha", "segmento_repo"]], Z.add_prefix("z_")], axis=1)
    d = d.merge(E, on="cooperativa", how="left")
    meses = (d.fecha_evento.dt.year - d.fecha.dt.year) * 12 + (d.fecha_evento.dt.month - d.fecha.dt.month)
    d["y"] = ((meses > 0) & (meses <= C.HORIZONTE_ALERTA_M)).astype(int)
    # tras el evento la entidad no es observación válida de riesgo
    d = d[~(meses <= 0)].dropna(subset=[c for c in d if c.startswith("z_")])
    return d

def evaluar(d, corte=None, ventana_test_m=24):
    zc = [c for c in d if c.startswith("z_")]
    corte = pd.Timestamp(corte or C.CORTE_TEMPORAL)
    tr = d[d.fecha <= corte]
    te = d[(d.fecha > corte) & (d.fecha <= corte + pd.DateOffset(months=ventana_test_m))]
    res = {"n_train": int(len(tr)), "n_test": int(len(te)), "eventos_train": int(tr.y.sum()),
           "eventos_test": int(te.y.sum()), "coop_evento_train": int(tr[tr.y == 1].cooperativa.nunique()),
           "coop_evento_test": int(te[te.y == 1].cooperativa.nunique()), "horizonte_m": C.HORIZONTE_ALERTA_M,
           "corte": str(corte.date()), "ventana_test_m": ventana_test_m, "advertencia": "Exploratorio: pocos eventos distintos; IC amplios; no usar para decisiones."}
    if res['coop_evento_train'] < 3 or res['coop_evento_test'] < 2:   # eventos = cooperativas distintas, no observaciones
        res["modelo"] = "no estimable (se exigen >=3 cooperativas con evento en entrenamiento y >=2 en prueba)"; return res, None
    mdl = LogisticRegression(C=0.5, class_weight="balanced", max_iter=2000).fit(tr[zc], tr.y)
    p = mdl.predict_proba(te[zc])[:, 1]
    res["coef_z"] = dict(zip(zc, map(float, mdl.coef_[0])))
    res["auc_test"] = float(roc_auc_score(te.y, p)); res["pr_auc_test"] = float(average_precision_score(te.y, p))
    res["prevalencia_test"] = float(te.y.mean())
    res["brier_test"] = float(brier_score_loss(te.y, p))
    # benchmark ingenuo: índice compuesto simple
    res["auc_test_indice_simple"] = float(roc_auc_score(te.y, te[zc].mean(1)))
    # IC bootstrap por cooperativa (clusters) del AUC
    rng = np.random.default_rng(C.SEMILLA); te = te.assign(p=p); coops = te.cooperativa.unique(); aucs = []
    for _ in range(300):
        s = rng.choice(coops, len(coops)); b = pd.concat([te[te.cooperativa == c] for c in s])
        if b.y.nunique() == 2: aucs.append(roc_auc_score(b.y, b.p))
    if aucs: res["auc_test_ic95_bootstrap"] = [float(np.percentile(aucs, 2.5)), float(np.percentile(aucs, 97.5))]
    return res, te

def origenes_rodantes(d, cortes=("2020-12-31", "2021-12-31", "2022-06-30", "2022-12-31", "2023-06-30")):
    """Evalúa varios orígenes temporales (entrena <= corte, prueba 24 m siguientes). Reporta honestamente los no estimables."""
    return {c: evaluar(d, c)[0] for c in cortes}
