"""Pruebas de las correcciones del cierre: nombres (mojibake), identidad, fusión de solvencia, cobertura y CSV."""
import io, sys, tempfile, unittest, re
from pathlib import Path
import pandas as pd
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / "scripts"))

class NombresTests(unittest.TestCase):
    def test_reparar_mojibake(self):
        from procesar_balance_cooperativas import reparar_mojibake, normalizar_nombre
        self.assertEqual(reparar_mojibake("CAÃ‘AR LTDA"), "CAÑAR LTDA")
        self.assertEqual(reparar_mojibake("RÃ\x8dOS"), "RÍOS")                    # byte C1 sin mapa en cp1252
        self.assertEqual(reparar_mojibake("CAÑAR LTDA"), "CAÑAR LTDA")            # nombres correctos no cambian
        self.assertEqual(reparar_mojibake("PILAHUIN"), "PILAHUIN")
        self.assertEqual(normalizar_nombre("COOPERATIVA DE AHORRO Y CRÃ‰DITO YUYAY LTDA"), "YUYAY LTDA")
    def test_sin_mojibake_en_datos(self):
        n = pd.read_parquet(RAIZ / "master_data" / "agg_catalogo_cooperativas.parquet", columns=["cooperativa"]).cooperativa.astype(str)
        self.assertFalse(n.str.contains("[ÃÂ]").any(), "quedan nombres con mojibake en agg_catalogo")
    def test_equivalencias_sin_solape(self):
        eq = RAIZ / "master_data" / "equivalencias_nombres.csv"
        if eq.exists():
            e = pd.read_csv(eq); self.assertTrue((e.nombre_fuente != e.nombre_corregido).all()); self.assertTrue(e.nombre_corregido.is_unique)

class IdentidadTests(unittest.TestCase):
    def test_sufijo_liquidacion(self):
        from analytics.vulnerabilidad.identidad import entidad_id, en_liquidacion_por_nombre
        self.assertEqual(entidad_id("CREA LTDA EN LIQUIDACION"), "CREA LTDA"); self.assertTrue(en_liquidacion_por_nombre("CREA LTDA EN LIQUIDACION"))
        self.assertEqual(entidad_id("CREA LTDA"), "CREA LTDA"); self.assertFalse(en_liquidacion_por_nombre("LIQUIDACION DEL SUR LTDA"))
    def test_panel_sin_duplicados_ni_sufijo(self):
        p = RAIZ / "master_data" / "panel_vulnerabilidad.parquet"
        if p.exists():
            d = pd.read_parquet(p, columns=["cooperativa", "fecha", "cooperativa_fuente"])
            self.assertFalse(d.duplicated(["cooperativa", "fecha"]).any()); self.assertFalse(d.cooperativa.str.contains("EN LIQUIDACION").any())

class SolvenciaTests(unittest.TestCase):
    def test_fusion_conserva_historia(self):
        from procesar_solvencia import fusionar_con_previo
        cols = ["fecha", "ruc", "cooperativa", "cooperativa_raw", "grupo_fuente", "solvencia", "archivo_origen"]
        previo = pd.DataFrame([[pd.Timestamp("2020-01-31"), "1", "A", "A", "g", 0.10, "x"], [pd.Timestamp("2026-01-31"), "1", "A", "A", "g", 0.11, "x"]], columns=cols)
        nuevo = pd.DataFrame([[pd.Timestamp("2026-01-31"), "1", "A", "A", "g", 0.12, "y"], [pd.Timestamp("2026-02-28"), "1", "A", "A", "g", 0.13, "y"]], columns=cols)
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "s.parquet"; previo.to_parquet(ruta, index=False)
            out = fusionar_con_previo(nuevo, ruta).sort_values("fecha")
        self.assertEqual(len(out), 3); self.assertEqual(out.fecha.min(), pd.Timestamp("2020-01-31"))        # la historia no se pierde
        self.assertAlmostEqual(out[out.fecha == "2026-01-31"].solvencia.iloc[0], 0.12)                      # lo nuevo manda en el solape
    def test_solvencia_tiene_historia(self):
        s = pd.read_parquet(RAIZ / "master_data" / "solvencia.parquet", columns=["fecha"])
        self.assertLessEqual(s.fecha.min(), pd.Timestamp("2020-12-31"))

class CoberturaTests(unittest.TestCase):
    def test_porcentajes_suman_100(self):
        from analytics.vulnerabilidad.cobertura import tabla_cobertura, CATEGORIAS
        P = pd.DataFrame({"fecha": pd.to_datetime(["2024-03-31"] * 4), "segmento_repo": ["SEGMENTO 1"] * 4,
                          "segmento_procedencia": ["exacto_mes", "arrastrado", "estimado", "otro"]})
        t = tabla_cobertura(P); self.assertEqual(int(t.observaciones.iloc[0]), 4)
        self.assertAlmostEqual(sum(t["pct_" + c].iloc[0] for c in CATEGORIAS), 100.0, places=0); self.assertEqual(int(t.sin_clasificacion_verificable.iloc[0]), 1)

class CsvTests(unittest.TestCase):
    def test_csv_bytes_idempotente(self):
        pytest_skip = False
        try:
            from utils.panel_vulnerabilidad import csv_bytes
        except Exception: pytest_skip = True
        if pytest_skip: self.skipTest("streamlit no disponible")
        df = pd.DataFrame({"cooperativa": ["PEQUEÑA ÑANDÚ"], "valor": [1.5], "n": [3]})
        back = pd.read_csv(io.BytesIO(csv_bytes(df)), encoding="utf-8-sig"); pd.testing.assert_frame_equal(back, df)
if __name__ == "__main__": unittest.main()
