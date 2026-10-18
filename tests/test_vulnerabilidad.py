import unittest, numpy as np, pandas as pd
from analytics.vulnerabilidad import indice, alerta, config as C

def _panel(n=40, T=24, seed=0):
    r = np.random.default_rng(seed); f = pd.date_range("2020-01-31", periods=T, freq="ME")
    d = pd.DataFrame([(f"C{i}", t) for i in range(n) for t in f], columns=["cooperativa", "fecha"])
    for k in C.INDICADORES: d[k] = r.normal(10, 3, len(d))
    d["segmento_repo"] = "SEGMENTO 3"; return d

class IndiceTests(unittest.TestCase):
    def test_orientacion_y_estandarizacion(self):
        P = _panel(); Z = indice.estandarizar(P)
        self.assertAlmostEqual(abs(Z.morosidad.mean()), 0, places=6)
        self.assertGreater(np.corrcoef(Z.morosidad, P.morosidad)[0, 1], 0.9)      # +1
        self.assertLess(np.corrcoef(Z.liquidez, P.liquidez)[0, 1], -0.9)          # -1
    def test_pesos_suman_uno_y_no_negativos(self):
        w, v = indice.pesos_pca(indice.estandarizar(_panel()))
        self.assertAlmostEqual(w.sum(), 1.0); self.assertTrue((w >= 0).all())
    def test_construir_sensibilidad(self):
        I, Z, s = indice.construir(_panel()); self.assertEqual(len(I), len(Z)); self.assertIn("spearman_min", s)

class AlertaTests(unittest.TestCase):
    def test_sin_eventos_no_estimable(self):
        P = _panel(); Z = indice.estandarizar(P)
        E = pd.DataFrame({"cooperativa": ["C1"], "fecha_evento": [pd.Timestamp("2021-06-30")]})
        d = alerta.construir_muestra(P, Z, E)
        self.assertEqual(d[d.cooperativa == "C1"].fecha.max() < pd.Timestamp("2021-06-30"), True)  # sin obs post-evento
        m, _ = alerta.evaluar(d, "2020-12-31"); self.assertIn("modelo", m)
if __name__ == "__main__": unittest.main()
