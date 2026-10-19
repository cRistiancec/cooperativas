# -*- coding: utf-8 -*-
"""El optimizador de Parquet no pierde ni altera datos y es idempotente."""
import sys, tempfile, unittest
from pathlib import Path
import numpy as np, pandas as pd, pyarrow as pa, pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import optimizar_parquet as op  # noqa: E402


def _tabla(n=20000, semilla=0):
    r = np.random.default_rng(semilla)
    df = pd.DataFrame({
        "fecha": pd.to_datetime("2020-01-31") + pd.to_timedelta(r.integers(0, 60, n) * 30, unit="D"),
        "cooperativa": pd.Categorical(r.choice([f"COOP {i}" for i in range(50)], n)),
        "codigo": pd.Categorical(r.choice(["1", "11", "2101", "3"], n)),
        "valor": r.normal(1e6, 5e5, n).round(2),
    })
    df.loc[::97, "valor"] = np.nan
    df.loc[5, "valor"] = -0.0
    return df


class TestOptimizar(unittest.TestCase):
    def test_lossless_idempotente_y_no_mayor(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "balance.parquet"
            df = _tabla(); df.to_parquet(ruta, compression="snappy")
            antes = ruta.stat().st_size
            r1 = op.optimizar(ruta)
            self.assertLessEqual(ruta.stat().st_size, antes)
            claves = ["cooperativa", "codigo", "fecha", "valor"]
            a = df[claves].astype({"cooperativa": str, "codigo": str}).sort_values(claves).reset_index(drop=True)
            b = pd.read_parquet(ruta)[claves].astype({"cooperativa": str, "codigo": str}).sort_values(claves).reset_index(drop=True)
            pd.testing.assert_frame_equal(a, b, check_exact=True)
            self.assertEqual(pq.read_metadata(ruta).row_group(0).column(0).compression, "ZSTD")
            tam = ruta.stat().st_size
            op.optimizar(ruta)                      # segunda pasada: sin cambio
            self.assertEqual(ruta.stat().st_size, tam)
            self.assertFalse([p for p in Path(d).iterdir() if "tmp" in p.name])

    def test_verificacion_detecta_diferencias(self):
        t = pa.table({"v": [1.0, 2.0, float("nan")]})
        self.assertTrue(op.iguales(t, t))
        self.assertFalse(op.iguales(t, pa.table({"v": [1.0, 2.0, 3.0]})))
        self.assertFalse(op.iguales(pa.table({"v": [0.0]}), pa.table({"v": [-0.0]})))

    def test_pesos_reales_bajo_limite_github(self):
        for f in (Path(__file__).resolve().parents[1] / "master_data").glob("*.parquet"):
            self.assertLess(f.stat().st_size, 95e6, f.name)


if __name__ == "__main__":
    unittest.main()
