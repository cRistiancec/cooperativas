# -*- coding: utf-8 -*-
"""
Predicción de Morosidad (Random Forest).

Modelo supervisado de panel: predice la Morosidad Total (MOR_TOT) del
**mes siguiente** de cada cooperativa a partir de sus indicadores oficiales
del mes actual (features de corte transversal + un paso de rezago temporal).

Validación: split **temporal** (no aleatorio) — se entrena con los meses más
antiguos y se evalúa contra los últimos `meses_holdout` meses, para simular
una situación realista de uso prospectivo y evitar fuga de información del
futuro hacia el pasado.
"""

from __future__ import annotations

from typing import Dict

import pandas as pd

from utils.logging_config import get_logger

logger = get_logger(__name__)

FEATURES = ["MOR_TOT", "COB_TOT", "ROE", "ROA", "LIQ", "CAP_NETO", "GO_ACT", "ACT_IMPR"]
TARGET_CODIGO = "MOR_TOT"


def _construir_panel_features(df_indicadores: pd.DataFrame) -> pd.DataFrame:
    """Pivota indicadores a formato ancho (cooperativa, fecha) x codigo, y arma el target (t+1)."""
    df_f = df_indicadores[df_indicadores["codigo"].isin(FEATURES)]

    panel = df_f.pivot_table(
        index=["cooperativa", "fecha"], columns="codigo", values="valor", aggfunc="first"
    ).reset_index()
    panel = panel.sort_values(["cooperativa", "fecha"])

    panel["target_mora_siguiente"] = panel.groupby("cooperativa", observed=True)[TARGET_CODIGO].shift(-1)
    return panel.dropna(subset=FEATURES + ["target_mora_siguiente"])


def entrenar_y_evaluar(df_indicadores: pd.DataFrame, meses_holdout: int = 6) -> Dict:
    """
    Entrena un RandomForestRegressor con split temporal y devuelve el modelo,
    las métricas de desempeño (MAE en puntos porcentuales, R²) y la
    importancia de variables.
    """
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.metrics import mean_absolute_error, r2_score

    panel = _construir_panel_features(df_indicadores)
    fechas_ordenadas = sorted(panel["fecha"].unique())

    if len(fechas_ordenadas) < meses_holdout + 12:
        raise ValueError("Historia insuficiente para entrenar con un holdout temporal confiable.")

    fecha_corte = fechas_ordenadas[-meses_holdout]
    train = panel[panel["fecha"] < fecha_corte]
    test = panel[panel["fecha"] >= fecha_corte]

    X_train, y_train = train[FEATURES], train["target_mora_siguiente"] * 100
    X_test, y_test = test[FEATURES], test["target_mora_siguiente"] * 100

    modelo = RandomForestRegressor(
        n_estimators=200, max_depth=8, min_samples_leaf=5, random_state=42, n_jobs=-1
    )
    modelo.fit(X_train, y_train)

    y_pred = modelo.predict(X_test)
    mae = float(mean_absolute_error(y_test, y_pred))
    r2 = float(r2_score(y_test, y_pred))
    logger.info(
        "RandomForest morosidad entrenado: n_train=%d, n_test=%d, mae_pp=%.2f, r2=%.3f",
        len(train), len(test), mae, r2,
    )

    importancias = pd.DataFrame({
        "feature": FEATURES, "importancia": modelo.feature_importances_,
    }).sort_values("importancia", ascending=False)

    return {
        "modelo": modelo,
        "mae_pp": mae,
        "r2": r2,
        "n_train": len(train),
        "n_test": len(test),
        "fecha_corte": fecha_corte,
        "importancias": importancias,
        "test_real": y_test.values,
        "test_predicho": y_pred,
        "test_cooperativas": test["cooperativa"].values,
    }


def proyectar_proximo_mes(modelo, df_indicadores: pd.DataFrame, segmento: str = "Todos") -> pd.DataFrame:
    """Usa el modelo entrenado para proyectar la morosidad del mes siguiente con los datos más recientes."""
    panel_completo = df_indicadores[df_indicadores["codigo"].isin(FEATURES)].pivot_table(
        index=["cooperativa", "segmento", "fecha"], columns="codigo", values="valor", aggfunc="first"
    ).reset_index()

    ultima_fecha = panel_completo["fecha"].max()
    df_ultima = panel_completo[panel_completo["fecha"] == ultima_fecha].dropna(subset=FEATURES)
    if segmento != "Todos":
        df_ultima = df_ultima[df_ultima["segmento"] == segmento]

    if df_ultima.empty:
        return pd.DataFrame()

    df_ultima = df_ultima.copy()
    df_ultima["mora_actual_pct"] = df_ultima["MOR_TOT"] * 100
    df_ultima["mora_proyectada_pct"] = modelo.predict(df_ultima[FEATURES])
    df_ultima["variacion_pp"] = df_ultima["mora_proyectada_pct"] - df_ultima["mora_actual_pct"]

    return df_ultima[["cooperativa", "segmento", "mora_actual_pct", "mora_proyectada_pct", "variacion_pp"]].sort_values(
        "variacion_pp", ascending=False
    )
