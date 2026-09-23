# -*- coding: utf-8 -*-
"""
Tests de la capa `models/` (ML y forecast) con datos sintéticos.

Para los modelos de scikit-learn/statsmodels se verifica **estructura y
comportamiento** (formas, tipos, invariantes) en vez de valores exactos,
porque los resultados numéricos pueden variar levemente entre versiones de
librería aun con `random_state` fijo.
"""

import unittest

import numpy as np
import pandas as pd

from models.anomalias import FEATURES as FEATURES_ANOMALIAS, detectar_anomalias
from models.clustering import COLUMNAS_CLUSTER, resumen_clusters, segmentar_riesgo
from models.forecast import forecast_serie


def _serie_tendencia_sintetica(n=48):
    """Serie mensual sintética con tendencia + ruido leve, determinística (semilla fija)."""
    rng = np.random.RandomState(42)
    fechas = pd.date_range("2022-01-31", periods=n, freq="ME")
    tendencia = np.linspace(1000, 1500, n)
    ruido = rng.normal(0, 5, n)
    return pd.Series(tendencia + ruido, index=fechas)


class ForecastTests(unittest.TestCase):
    def test_forecast_devuelve_los_pasos_solicitados(self):
        serie = _serie_tendencia_sintetica()
        resultado = forecast_serie(serie, pasos=6)
        self.assertEqual(len(resultado["valores"]), 6)
        self.assertEqual(len(resultado["fechas_futuras"]), 6)
        self.assertEqual(len(resultado["limite_inferior"]), 6)

    def test_forecast_rechaza_series_muy_cortas(self):
        serie = _serie_tendencia_sintetica(n=10)
        with self.assertRaises(ValueError):
            forecast_serie(serie, pasos=6)

    def test_forecast_sigue_la_tendencia_creciente(self):
        serie = _serie_tendencia_sintetica()
        resultado = forecast_serie(serie, pasos=3)
        # La serie sintética crece ~10.4/mes; el forecast no debería predecir una caída abrupta.
        self.assertGreater(resultado["valores"][-1], serie.iloc[-1] - 50)


class AnomaliasTests(unittest.TestCase):
    def _df_indicadores_con_un_atipico(self):
        fecha = pd.Timestamp("2026-06-30")
        rng = np.random.RandomState(7)
        filas = []
        for i in range(30):
            valores = {c: float(rng.normal(0.05, 0.01)) for c in FEATURES_ANOMALIAS}
            filas.append({"cooperativa": f"COOP_{i}", "segmento": "SEGMENTO 1", "fecha": fecha, **valores})
        # Institución claramente atípica: morosidad muy alta, ROE muy negativo.
        atipico = {c: float(rng.normal(0.05, 0.01)) for c in FEATURES_ANOMALIAS}
        atipico.update({"MOR_TOT": 0.9, "ROE": -2.0, "cooperativa": "ATIPICA", "segmento": "SEGMENTO 1", "fecha": fecha})
        filas.append(atipico)

        registros = []
        for fila in filas:
            for codigo in FEATURES_ANOMALIAS:
                registros.append({
                    "cooperativa": fila["cooperativa"], "segmento": fila["segmento"], "fecha": fila["fecha"],
                    "codigo": codigo, "valor": fila[codigo],
                })
        return pd.DataFrame(registros)

    def test_detecta_la_institucion_claramente_atipica(self):
        df = self._df_indicadores_con_un_atipico()
        resultado = detectar_anomalias(df, pd.Timestamp("2026-06-30"), contaminacion=0.1)
        self.assertFalse(resultado.empty)
        # La institución atípica debe estar entre las de menor (más negativo) score de anomalía.
        peor = resultado.iloc[0]
        self.assertEqual(peor["cooperativa"], "ATIPICA")
        self.assertTrue(bool(peor["es_anomalia"]))


class ClusteringTests(unittest.TestCase):
    def _df_score_sintetico(self):
        rng = np.random.RandomState(3)
        filas = []
        for i in range(20):
            base = 80 if i < 10 else 30  # dos grupos claramente separados
            fila = {c: base + rng.normal(0, 3) for c in COLUMNAS_CLUSTER}
            fila["cooperativa"] = f"COOP_{i}"
            fila["segmento"] = "SEGMENTO 1"
            fila["score_total"] = np.mean(list(fila[c] for c in COLUMNAS_CLUSTER))
            filas.append(fila)
        return pd.DataFrame(filas)

    def test_segmenta_en_el_numero_de_clusters_solicitado(self):
        df = self._df_score_sintetico()
        segmentado = segmentar_riesgo(df, n_clusters=2)
        self.assertFalse(segmentado.empty)
        self.assertEqual(segmentado["cluster"].nunique(), 2)

        resumen = resumen_clusters(segmentado)
        self.assertEqual(len(resumen), 2)
        # El grupo "Sólido" (mejor score) debe tener score_total mayor que "Adecuado"/"Crítico".
        self.assertGreater(resumen.iloc[0]["score_total"], resumen.iloc[-1]["score_total"])


if __name__ == "__main__":
    unittest.main()
