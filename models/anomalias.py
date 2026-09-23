# -*- coding: utf-8 -*-
"""
Detección de Anomalías (Isolation Forest).

Identifica cooperativas con perfiles financieros atípicos respecto al resto
del sistema en una fecha de corte, usando un conjunto de indicadores
oficiales de las 5 dimensiones CAMEL como espacio de características. Es un
modelo **no supervisado**: no dice si una institución es "buena" o "mala",
solo qué tan distinta es su combinación de indicadores frente al resto.
Complementa (no reemplaza) al motor de reglas de Alertas Tempranas.
"""

from __future__ import annotations

from typing import List

import pandas as pd

from utils.logging_config import get_logger

logger = get_logger(__name__)

FEATURES = ["MOR_TOT", "COB_TOT", "ROE", "ROA", "LIQ", "CAP_NETO", "GO_ACT", "ACT_PROD"]


def detectar_anomalias(df_indicadores: pd.DataFrame, fecha, segmento: str = "Todos", contaminacion: float = 0.10) -> pd.DataFrame:
    """
    Entrena un Isolation Forest sobre los indicadores de una fecha de corte
    y devuelve, por cooperativa, un score de anomalía (más negativo = más
    atípico) y una bandera booleana `es_anomalia`.

    `contaminacion` es la proporción esperada de instituciones atípicas
    (hiperparámetro estándar de Isolation Forest, no un umbral regulatorio).
    """
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler

    df_f = df_indicadores[(df_indicadores["fecha"] == fecha) & (df_indicadores["codigo"].isin(FEATURES))]
    if segmento != "Todos":
        df_f = df_f[df_f["segmento"] == segmento]

    panel = df_f.pivot_table(
        index=["cooperativa", "segmento"], columns="codigo", values="valor", aggfunc="first"
    ).dropna(subset=FEATURES).reset_index()

    if len(panel) < 15:
        return pd.DataFrame()

    X = StandardScaler().fit_transform(panel[FEATURES])

    modelo = IsolationForest(n_estimators=200, contamination=contaminacion, random_state=42)
    panel["score_anomalia"] = modelo.fit(X).score_samples(X)
    panel["es_anomalia"] = modelo.predict(X) == -1
    logger.info(
        "IsolationForest evaluado: n=%d, marcadas=%d, contaminacion=%.2f",
        len(panel), int(panel["es_anomalia"].sum()), contaminacion,
    )

    return panel.sort_values("score_anomalia")


def explicar_anomalia(fila: pd.Series, panel_completo: pd.DataFrame) -> List[str]:
    """
    Explicación simple (no SHAP, para mantener el modelo liviano): indica
    qué indicadores de la institución están más alejados (en desviaciones
    estándar) de la media del sistema, como pista de por qué fue marcada.
    """
    razones = []
    for codigo in FEATURES:
        media = panel_completo[codigo].mean()
        desviacion = panel_completo[codigo].std()
        if desviacion == 0 or pd.isna(desviacion):
            continue
        z = (fila[codigo] - media) / desviacion
        if abs(z) >= 1.5:
            direccion = "muy por encima" if z > 0 else "muy por debajo"
            razones.append(f"{codigo} {direccion} del promedio del sistema (z={z:+.1f})")
    return razones[:3]
