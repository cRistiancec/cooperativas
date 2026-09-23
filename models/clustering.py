# -*- coding: utf-8 -*-
"""
Segmentación de Riesgo (KMeans).

Agrupa a las cooperativas en clústeres de perfil de riesgo similar, usando
los mismos scores de categoría CAMEL (percentiles 0-100) calculados en
`analytics.camels_score`. El número de clústeres es configurable; se
etiqueta cada clúster de forma automática según su score promedio (no son
etiquetas fijas del negocio, se derivan de los datos en cada corrida).
"""

from __future__ import annotations

import pandas as pd

from utils.logging_config import get_logger

logger = get_logger(__name__)

COLUMNAS_CLUSTER = ["score_C", "score_A", "score_M", "score_E", "score_L"]


def segmentar_riesgo(df_score_camel: pd.DataFrame, n_clusters: int = 4) -> pd.DataFrame:
    """
    Ejecuta KMeans sobre los scores CAMEL por categoría (ya en escala 0-100,
    no requieren re-escalado) y etiqueta cada clúster según su score
    compuesto promedio: Sólido / Adecuado / Vigilancia / Crítico (o
    variantes numeradas si `n_clusters` no es 4).
    """
    from sklearn.cluster import KMeans

    df = df_score_camel.dropna(subset=COLUMNAS_CLUSTER).copy()
    if len(df) < n_clusters * 3:
        return pd.DataFrame()

    modelo = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    df["cluster"] = modelo.fit_predict(df[COLUMNAS_CLUSTER])

    orden_clusters = (
        df.groupby("cluster")["score_total"].mean().sort_values(ascending=False).index.tolist()
    )
    etiquetas_base = ["Sólido", "Adecuado", "Vigilancia", "Crítico"]
    mapa_etiquetas = {}
    for i, cluster_id in enumerate(orden_clusters):
        mapa_etiquetas[cluster_id] = etiquetas_base[i] if i < len(etiquetas_base) else f"Grupo {i + 1}"

    df["etiqueta_cluster"] = df["cluster"].map(mapa_etiquetas)
    df["centro_cluster"] = df["cluster"].map(
        {i: modelo.cluster_centers_[i].tolist() for i in range(n_clusters)}
    )
    logger.info("KMeans entrenado: n=%d, n_clusters=%d", len(df), n_clusters)

    return df


def resumen_clusters(df_segmentado: pd.DataFrame) -> pd.DataFrame:
    """Estadísticas descriptivas por clúster: tamaño y score promedio por categoría."""
    columnas = COLUMNAS_CLUSTER + ["score_total"]
    resumen = df_segmentado.groupby("etiqueta_cluster")[columnas].mean().round(1)
    resumen["n_instituciones"] = df_segmentado.groupby("etiqueta_cluster").size()
    return resumen.sort_values("score_total", ascending=False)
