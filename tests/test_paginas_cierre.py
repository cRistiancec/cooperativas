"""Pruebas de humo de las páginas 16-19 y del panel de vulnerabilidad (AppTest, sin servidor)."""
import unittest
from pathlib import Path
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
PANEL = RAIZ / "master_data" / "panel_vulnerabilidad.parquet"

@unittest.skipUnless(PANEL.exists(), "panel_vulnerabilidad.parquet no disponible")
class PanelTests(unittest.TestCase):
    def setUp(self): self.d = pd.read_parquet(PANEL)
    def test_clave_unica_y_segmentos(self):
        self.assertFalse(self.d.duplicated(["cooperativa", "fecha"]).any())
        self.assertTrue(set(self.d.segmento_repo) <= {"SEGMENTO 1", "SEGMENTO 2", "SEGMENTO 3"})
    def test_procedencia_valida_y_corte(self):
        self.assertTrue(set(self.d.segmento_procedencia) <= {"exacto_mes", "arrastrado", "estimado", "balance_historico"})
        self.assertEqual(pd.Timestamp(self.d.fecha.max()), pd.Timestamp("2026-09-30"))
    def test_identidad_contable(self):   # ene-nov: A = P + Pat + resultado YTD; dic: A = P + Pat (resultado ya cerrado en Pat)
        res = self.d.resultado_ytd.where(self.d.fecha.dt.month != 12, 0.0)
        r = ((self.d.activos - self.d.pasivos - self.d.patrimonio - res).abs() / self.d.activos).max()
        self.assertLess(r, 1e-6)
    def test_solvencia_proxy_es_patrimonio_total(self):
        r = (self.d.solvencia_proxy - (self.d.activos - self.d.pasivos) / self.d.activos * 100).abs().max()
        self.assertLess(r, 1e-9)
    def test_sin_infinitos(self):
        for c in ["liquidez", "morosidad", "roa", "eficiencia"]:
            self.assertFalse(self.d[c].isin([float("inf"), float("-inf")]).any())

@unittest.skipUnless(PANEL.exists(), "panel no disponible")
class PaginasTests(unittest.TestCase):
    def test_paginas_sin_excepciones(self):
        from streamlit.testing.v1 import AppTest
        for p in ["16_Resumen_Validado", "17_Comparativo_Segmentos", "18_Vulnerabilidad_Ficha", "19_Calidad_Trazabilidad"]:
            at = AppTest.from_file(str(RAIZ / "pages" / f"{p}.py"), default_timeout=180).run()
            self.assertEqual(len(at.exception), 0, p)
            self.assertGreaterEqual(len(at.dataframe), 1, p)
if __name__ == "__main__": unittest.main()
