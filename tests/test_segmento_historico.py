"""Pruebas de la ingesta del segmento histórico (point-in-time) desde los ZIP de la SEPS."""
import json
import sys
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


class AcoplarYValidarTests(unittest.TestCase):
    """acoplar_segmento (PyG/CAMEL/entidades), validar_segmentos y agregado histórico."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def _dim(self, filas, nombre="dim.parquet"):
        d = pd.DataFrame(filas, columns=["cooperativa", "fecha", "segmento_historico"])
        d["fecha"] = pd.to_datetime(d["fecha"]); d["fuente"] = "t"
        d.to_parquet(self.dir / nombre); return self.dir / nombre

    def test_acoplar_reporta_cobertura_y_discrepancias(self):
        ruta = self._dim([("A", "2024-01-31", "SEGMENTO 2"), ("B", "2024-01-31", "SEGMENTO 3")])
        df = pd.DataFrame({"cooperativa": ["A", "B", "C"], "fecha": pd.to_datetime(["2024-01-31"] * 3),
                           "segmento": ["SEGMENTO 1"] * 3,
                           "segmento_historico": ["SEGMENTO 2", "SEGMENTO 1", "SEGMENTO 1"],
                           "segmento_historico_estimado": [False, False, True]})
        out, rep = sh.acoplar_segmento(df, "t", ruta)
        self.assertEqual(out.segmento_historico.astype(str).tolist(), ["SEGMENTO 2", "SEGMENTO 3", "SEGMENTO 1"])
        self.assertEqual(out.segmento_historico_estimado.tolist(), [False, False, True])
        self.assertEqual(rep["discrepancias_fuente"], 1)          # B: el archivo decía S1, la dimensión S3
        self.assertAlmostEqual(rep["pct_cubierto"], 66.67, places=1)

    def test_acoplar_sin_dimension_marca_estimado(self):
        df = pd.DataFrame({"cooperativa": ["A"], "fecha": pd.to_datetime(["2024-01-31"]), "segmento": ["SEGMENTO 1"]})
        out, rep = sh.acoplar_segmento(df, "t", self.dir / "no_existe.parquet")
        self.assertTrue(out.segmento_historico_estimado.all()); self.assertEqual(rep["pct_cubierto"], 0.0)

    def _datasets(self, estimado_ultimo=False, con_columnas=True):
        f = pd.to_datetime(["2024-01-31", "2024-02-29"])
        df = pd.DataFrame({"fecha": f, "cooperativa": ["A", "A"], "segmento": ["SEGMENTO 2"] * 2})
        if con_columnas:
            df["segmento_historico"] = ["SEGMENTO 3", "SEGMENTO 2"]
            df["segmento_historico_estimado"] = [False, estimado_ultimo]
        p = self.dir / "ds.parquet"; df.to_parquet(p)
        return {"balance": p}

    def test_validar_segmentos_ok(self):
        from scripts.validar_actualizacion import validar_segmentos
        dim = self._dim([("A", "2024-01-31", "SEGMENTO 3"), ("A", "2024-02-29", "SEGMENTO 2")])
        validar_segmentos(pd.Timestamp("2024-02-29"), dim, self._datasets())

    def test_validar_segmentos_falla_sin_dimension_con_hueco_o_estimado(self):
        from scripts.validar_actualizacion import validar_segmentos
        corte = pd.Timestamp("2024-02-29")
        with self.assertRaises(ValueError):
            validar_segmentos(corte, self.dir / "no.parquet", self._datasets())
        hueco = self._dim([("A", "2023-12-31", "SEGMENTO 3"), ("A", "2024-02-29", "SEGMENTO 2")], "h.parquet")
        with self.assertRaises(ValueError):
            validar_segmentos(corte, hueco, self._datasets())
        ok = self._dim([("A", "2024-01-31", "SEGMENTO 3"), ("A", "2024-02-29", "SEGMENTO 2")], "ok.parquet")
        with self.assertRaises(ValueError):
            validar_segmentos(corte, ok, self._datasets(estimado_ultimo=True))
        with self.assertRaises(ValueError):
            validar_segmentos(corte, ok, self._datasets(con_columnas=False))

    def test_agregado_historico_separa_por_segmento_de_cada_mes(self):
        from scripts import generar_agregados as ga
        bal = pd.DataFrame({"fecha": pd.to_datetime(["2024-01-31", "2024-02-29"]),
                            "segmento": ["SEGMENTO 2"] * 2, "cooperativa": ["A", "A"], "codigo": ["1", "1"],
                            "cuenta": ["ACTIVO"] * 2, "valor": [10.0, 20.0],
                            "segmento_historico": ["SEGMENTO 3", "SEGMENTO 2"],
                            "segmento_historico_estimado": [False, False]})
        bal.to_parquet(self.dir / "balance.parquet")
        with mock.patch.object(ga, "MASTER_DATA_DIR", self.dir), mock.patch.object(ga, "BALANCE_PATH", self.dir / "balance.parquet"):
            ga.main()
        h = pd.read_parquet(self.dir / "agg_metricas_sistema_historico.parquet").sort_values("fecha")
        self.assertEqual(h.segmento_historico.astype(str).tolist(), ["SEGMENTO 3", "SEGMENTO 2"])
        meta = json.loads((self.dir / "metadata_agregados.json").read_text())
        self.assertIn("agg_metricas_sistema_historico.parquet", meta["archivos_generados"])


if __name__ == "__main__":
    unittest.main()


class FuenteTrimestralTests(unittest.TestCase):
    """Registro oficial 'Entidades trimestral': arrastre point-in-time y sin mirar al futuro."""

    def _cortes(self):
        return pd.DataFrame({
            "cooperativa": ["A", "A", "B"],
            "fecha": pd.to_datetime(["2020-03-31", "2020-06-30", "2020-03-31"]),
            "segmento_historico": ["SEGMENTO 3", "SEGMENTO 2", "SEGMENTO 1"],
        })

    def test_arrastre_no_usa_cortes_futuros(self):
        m = sh.expandir_cortes_a_mensual(self._cortes(), hasta=pd.Timestamp("2020-08-31"))
        a = m[m.cooperativa == "A"].set_index("fecha")
        self.assertEqual(a.loc["2020-04-30", "segmento_historico"], "SEGMENTO 3")  # aún no cambia
        self.assertEqual(a.loc["2020-06-30", "segmento_historico"], "SEGMENTO 2")
        self.assertTrue(a.loc["2020-04-30", "es_arrastrado"])
        self.assertFalse(a.loc["2020-03-31", "es_arrastrado"])

    def test_arrastre_tiene_tope(self):
        m = sh.expandir_cortes_a_mensual(self._cortes(), hasta=pd.Timestamp("2020-12-31"))
        b = m[m.cooperativa == "B"]
        self.assertEqual(b.fecha.max(), pd.Timestamp("2020-05-31"))  # 2 meses tras el corte

    def test_dato_exacto_gana_y_se_reportan_discrepancias(self):
        exacto = sh.construir_dim(pd.DataFrame({
            "cooperativa": ["A"], "fecha": pd.to_datetime(["2020-04-30"]),
            "segmento_historico": ["SEGMENTO 2"]}), "x")
        tri = sh.expandir_cortes_a_mensual(self._cortes(), hasta=pd.Timestamp("2020-06-30"))
        dim, diag = sh.combinar_exacto_y_trimestral(exacto, tri)
        fila = dim[(dim.cooperativa == "A") & (dim.fecha == "2020-04-30")]
        self.assertEqual(fila.segmento_historico.iloc[0], "SEGMENTO 2")
        self.assertEqual(diag["discrepancias_exacto_vs_trimestral"], 1)

    def test_sin_segmento_no_entra_y_desconocido_falla(self):
        ok = "FECHA_CORTE\tRUC\tRAZON_SOCIAL\tSEGMENTO\tESTADO_JURIDICO\n31/03/2025\t1\tX LTDA\tSIN SEGMENTO\tEXTINTA\n"
        out = sh.leer_entidades_txt(ok, "t")
        self.assertTrue(out.segmento_historico.isna().all())
        mal = ok.replace("SIN SEGMENTO", "SEGMENTO 9")
        with self.assertRaises(sh.SegmentoInvalidoError):
            sh.leer_entidades_txt(mal, "t")

    def test_reparar_mojibake(self):
        self.assertEqual(sh.reparar_mojibake("CRÃ‰DITO"), "CRÉDITO")
        self.assertEqual(sh.reparar_mojibake("CREDITO"), "CREDITO")


class ActualizarEntidadesTests(unittest.TestCase):
    def test_fusiona_con_cortes_guardados_y_no_encoge_la_dimension(self):
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            previos = pd.DataFrame({"ruc": ["1", "1"], "cooperativa": ["A", "A"],
                "fecha": pd.to_datetime(["2020-03-31", "2020-06-30"]),
                "segmento_historico": ["SEGMENTO 3", "SEGMENTO 2"], "fuente": "entidades_trimestral:x"})
            previos.to_parquet(d / "entidades_trimestral.parquet", index=False)
            nuevo = pd.DataFrame({"ruc": ["1"], "cooperativa": ["A"],
                "fecha": pd.to_datetime(["2020-09-30"]), "segmento_historico": ["SEGMENTO 2"],
                "fuente": "entidades_trimestral:y"})
            ruta = d / "dim.parquet"
            sh.guardar_parquet_atomico(sh.expandir_cortes_a_mensual(previos), ruta, engine="pyarrow")
            with mock.patch.dict(sys.modules, {"descargar_datos_seps": mock.MagicMock(
                    ENTIDADES_DIR=d, descargar_entidades_trimestral=lambda a: d)}), \
                 mock.patch.object(sh, "cargar_cortes_entidades", return_value=nuevo):
                sh.actualizar_entidades([2020], ruta=ruta)
            dim = pd.read_parquet(ruta)
            self.assertEqual(pd.to_datetime(dim.fecha).min(), pd.Timestamp("2020-03-31"))
            self.assertIn(pd.Timestamp("2020-09-30"), set(pd.to_datetime(dim.fecha)))


class FilasAgregadasTests(unittest.TestCase):
    def test_vt_total_toma_segmento_de_su_etiqueta(self):
        df = pd.DataFrame({"cooperativa": ["VT_TOTAL SEGMENTO 2", "VT_TOTAL MUTUALISTAS", "X LTDA"],
                           "fecha": pd.to_datetime(["2026-09-30"] * 3),
                           "segmento": ["SEGMENTO 3"] * 3})
        dim = sh.construir_dim(pd.DataFrame({"cooperativa": ["X LTDA"],
            "fecha": pd.to_datetime(["2026-09-30"]), "segmento_historico": ["SEGMENTO 1"]}), "t")
        r = sh.aplicar_segmento_historico(df, dim).set_index("cooperativa")
        self.assertEqual(r.loc["VT_TOTAL SEGMENTO 2", "segmento_historico"], "SEGMENTO 2")
        self.assertEqual(r.loc["VT_TOTAL MUTUALISTAS", "segmento_historico"], "SEGMENTO 1 MUTUALISTA")
        self.assertFalse(r.loc["VT_TOTAL SEGMENTO 2", "segmento_historico_estimado"])
        self.assertEqual(r.loc["X LTDA", "segmento_historico"], "SEGMENTO 1")
