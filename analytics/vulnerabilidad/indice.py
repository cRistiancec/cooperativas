"""Índice compuesto de vulnerabilidad I = sum_k w_k Z_k con análisis de sensibilidad a pesos."""
import numpy as np, pandas as pd
from . import config as C

def estandarizar(P: pd.DataFrame) -> pd.DataFrame:
    """Z_k orientado (alto = más vulnerable): winsorización pooled + z-score pooled."""
    Z = pd.DataFrame(index=P.index)
    for k, signo in C.INDICADORES.items():
        x = P[k].astype(float)
        lo, hi = x.quantile(C.WINSOR[0]), x.quantile(C.WINSOR[1])
        x = x.clip(lo, hi)
        Z[k] = signo * (x - x.mean()) / x.std(ddof=0)
    return Z

def pesos_pca(Z: pd.DataFrame) -> np.ndarray:
    """Pesos = |cargas| normalizadas del 1er componente (matriz de correlación, casos completos)."""
    X = Z.dropna()
    ev, evec = np.linalg.eigh(np.corrcoef(X.values.T))
    v = evec[:, -1]
    v = v if v.sum() >= 0 else -v          # orientar para que el componente aumente con la vulnerabilidad
    v = np.clip(v, 0, None)                 # sin pesos negativos (coherencia con la orientación)
    return v / v.sum(), float(ev[-1] / ev.sum())

def construir(P: pd.DataFrame, min_componentes: int = 5):
    Z = estandarizar(P)
    k = Z.shape[1]
    w_eq = np.repeat(1 / k, k)
    w_pca, var1 = pesos_pca(Z)
    def comb(w):
        M = Z.values
        ok = (~np.isnan(M)).sum(1) >= min_componentes
        num = np.nansum(M * w, 1); den = np.nansum(~np.isnan(M) * w, 1)
        return pd.Series(np.where(ok, num / np.where(den > 0, den, np.nan), np.nan), index=Z.index)
    out = P[["cooperativa", "fecha", "segmento_repo"]].copy()
    out["indice_eq"], out["indice_pca"] = comb(w_eq), comb(w_pca)
    # sensibilidad: pesos Dirichlet(1) -> correlación de rangos con el índice base
    rng = np.random.default_rng(C.SEMILLA)
    base = out.indice_eq
    rhos = []
    for w in rng.dirichlet(np.ones(k), C.N_PESOS_ALEATORIOS):
        rhos.append(base.corr(comb(w), method="spearman"))
    sens = {"spearman_min": float(np.min(rhos)), "spearman_p05": float(np.percentile(rhos, 5)),
            "spearman_mediana": float(np.median(rhos)),
            "spearman_eq_vs_pca": float(base.corr(out.indice_pca, method="spearman")),
            "var_explicada_pc1": var1, "pesos_pca": dict(zip(Z.columns, map(float, w_pca)))}
    return out, Z, sens
