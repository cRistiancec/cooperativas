"""Pruebas de la ingesta del segmento histórico (point-in-time) desde los ZIP de la SEPS."""
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import pandas as pd

from scripts import procesar_balance_cooperativas as etl
from scripts import segmento_historico as sh

CSV_HDR_OLD = "FECHA_DE_CORTE;SEGMENTO;RUC;RAZON_SOCIAL;CUENTA;DESCRIPCION_CUENTA;SALDO_USD"
CSV_HDR_NEW = "FECHA DE CORTE\tSEGMENTO\tRUC\tRAZON SOCIAL\tCUENTA\tDESCRIPCION CUENTA\tSALDO (USD)"


def _fila(fecha, seg, coop, saldo, new):
    sep = "\t" if new else ";"
    return sep.join([fecha, seg, "1790000000001", coop, "1", "ACTIVO", str(saldo)])


def _zip(directorio, nombre, filas, nuevo):
    p = Path(directorio) / nombre
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("datos.csv", "\n".join([CSV_HDR_NEW if nuevo else CSV_HDR_OLD] + filas))
    return p


class NormalizarSegmentoTests(unittest.TestCase):
    def test_variantes_validas(self):
        self.assertEqual(sh.normalizar_segmento(" segmento  2 "), "SEGMENTO 2")
        self.assertEqual(sh.normalizar_segmento("SEGMENTO 1 MUTUALISTA"), "SEGMENTO 1 MUTUALISTA")

    def test_no_adivina(self):
        for malo in (None, float("nan"), "", "SEGMENTO 9", "Grande", "SEGMENTO 2 MUTUALISTA"):
            self.assertIsNone(sh.normalizar_segmento(malo))


class ExtraccionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)

    def test_csv_formato_antiguo_y_nuevo(self):
        z1 = _zip(self.tmp.name, "2021-EEFF-MEN.zip",
                  [_fila("2021-12-31", "SEGMENTO 3", "COOPERATIVA DE AHORRO Y CREDITO ALFA LTDA", 5, False)], False)
        z2 = _zip(self.tmp.name, "2022-EEFF-MEN.zip",
                  [_fila("2022-01-31", "SEGMENTO 2", "COOPERATIVA DE AHORRO Y CREDITO ALFA LTDA", 6, True)], True)
        d1, d2 = sh.extraer_dim_zip(z1), sh.extraer_dim_zip(z2)
        self.assertEqual(d1.segmento_historico.tolist(), ["SEGMENTO 3"])
        self.assertEqual(d2.segmento_historico.tolist(), ["SEGMENTO 2"])
        self.assertEqual(d1.cooperativa.iloc[0], d2.cooperativa.iloc[0])  # mismo nombre normalizado

    def test_segmento_ausente_falla(self):
        z = _zip(self.tmp.name, "2021-EEFF-MEN.zip", [_fila("2021-12-31", "", "ALFA LTDA", 1, False)], False)
        with self.assertRaises(sh.SegmentoInvalidoError):
            sh.extraer_dim_zip(z)

    def test_conflicto_mismo_mes_falla(self):
        z = _zip(self.tmp.name, "2021-EEFF-MEN.zip",
                 [_fila("2021-12-31", "SEGMENTO 1", "ALFA LTDA", 1, False),
                  _fila("2021-12-31", "SEGMENTO 2", "ALFA LTDA", 1, False)], False)
        with self.assertRaises(sh.SegmentoInvalidoError):
            sh.extraer_dim_zip(z)


class UpsertTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.ruta = Path(self.tmp.name) / "dim.parquet"; self.log = Path(self.tmp.name) / "log.json"

    def _dim(self, filas):
        return pd.DataFrame(filas, columns=["cooperativa", "fecha", "segmento_historico"]).assign(
            fecha=lambda d: pd.to_datetime(d.fecha), fuente="t")

    def test_idempotente_y_registra_revision_retroactiva(self):
        a = self._dim([("A", "2024-01-31", "SEGMENTO 3"), ("B", "2024-01-31", "SEGMENTO 2")])
        sh.upsert_dim(a, self.ruta, self.log); sh.upsert_dim(a, self.ruta, self.log)
        self.assertEqual(len(pd.read_parquet(self.ruta)), 2)
        self.assertFalse(self.log.exists())
        rev = self._dim([("A", "2024-01-31", "SEGMENTO 2")])      # la SEPS corrige A y retira B
        r = sh.upsert_dim(rev, self.ruta, self.log)
        self.assertEqual(r["filas_retiradas"], 1)
        self.assertEqual(r["revisiones_de_segmento"][0]["antes"], "SEGMENTO 3")
        self.assertEqual(pd.read_parquet(self.ruta).segmento_historico.tolist(), ["SEGMENTO 2"])
        self.assertTrue(self.log.exists())


class AplicarTests(unittest.TestCase):
    def test_marca_estimado_solo_donde_no_hay_cobertura(self):
        df = pd.DataFrame({"cooperativa": pd.Categorical(["A", "A", "B"]),
                           "fecha": pd.to_datetime(["2020-01-31", "2021-01-31", "2020-01-31"]),
                           "segmento": ["SEGMENTO 1"] * 3})
        dim = pd.DataFrame({"cooperativa": ["A"], "fecha": pd.to_datetime(["2020-01-31"]),
                            "segmento_historico": ["SEGMENTO 3"]})
        out = sh.aplicar_segmento_historico(df, dim)
        self.assertEqual(out.segmento_historico.astype(str).tolist(), ["SEGMENTO 3", "SEGMENTO 1", "SEGMENTO 1"])
        self.assertEqual(out.segmento_historico_estimado.tolist(), [False, True, True])


class EtlExtremoAExtremoTests(unittest.TestCase):
    def test_cooperativa_que_cambia_de_segmento_conserva_su_historia(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t); (t / "zips").mkdir(); (t / "out").mkdir()
            coop = "COOPERATIVA DE AHORRO Y CREDITO ALFA LTDA"
            _zip(t / "zips", "2021-EEFF-MEN.zip", [_fila("2021-12-31", "SEGMENTO 3", coop, 5, False)], False)
            _zip(t / "zips", "2022-EEFF-MEN.zip", [_fila("2022-01-31", "SEGMENTO 2", coop, 6, True)], True)
            with mock.patch.object(etl, "BALANCES_DIR", t / "zips"), mock.patch.object(etl, "OUTPUT_DIR", t / "out"), \
                    mock.patch.object(etl, "DIM_SEGMENTO_PATH", t / "out" / "dim.parquet"):
                df = etl.generar_balance_parquet()
            self.assertEqual(set(df.segmento.astype(str)), {"SEGMENTO 2"})            # compat: último segmento
            h = df.sort_values("fecha").segmento_historico.astype(str).tolist()
            self.assertEqual(h, ["SEGMENTO 3", "SEGMENTO 2"])                          # point-in-time
            self.assertFalse(df.segmento_historico_estimado.any())

    def test_incremental_rehidrata_parquet_historico_sin_columnas_de_segmento(self):
        """Caso real del repo: balance.parquet previo sin segmento_historico + ZIP nuevo."""
        with tempfile.TemporaryDirectory() as t:
            t = Path(t); (t / "zips").mkdir(); (t / "out").mkdir()
            coop = "COOPERATIVA DE AHORRO Y CREDITO ALFA LTDA"
            nombre = etl.normalizar_nombre(coop)
            previo = pd.DataFrame({"fecha": pd.to_datetime(["2021-12-31"]), "segmento": ["SEGMENTO 2"],
                                   "cooperativa": [nombre], "codigo": ["1"], "cuenta": ["ACTIVO"], "valor": [5.0]})
            previo.to_parquet(t / "out" / "balance.parquet")
            dim = pd.DataFrame({"cooperativa": [nombre], "fecha": pd.to_datetime(["2021-12-31"]),
                                "segmento_historico": ["SEGMENTO 3"], "fuente": "rehidratacion"})
            dim.to_parquet(t / "out" / "dim.parquet")
            _zip(t / "zips", "2022-EEFF-MEN.zip", [_fila("2022-01-31", "SEGMENTO 2", coop, 6, True)], True)
            with mock.patch.object(etl, "BALANCES_DIR", t / "zips"), mock.patch.object(etl, "OUTPUT_DIR", t / "out"), \
                    mock.patch.object(etl, "DIM_SEGMENTO_PATH", t / "out" / "dim.parquet"):
                df = etl.generar_balance_parquet()
            df = df.sort_values("fecha")
            self.assertEqual(df.segmento_historico.astype(str).tolist(), ["SEGMENTO 3", "SEGMENTO 2"])
            self.assertEqual(df.segmento_historico_estimado.tolist(), [False, False])


if __name__ == "__main__":
    unittest.main()
