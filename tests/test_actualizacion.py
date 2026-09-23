import tempfile
import unittest
import unittest.mock
import zipfile
from pathlib import Path

import pandas as pd

from scripts.procesar_camel import combinar_historico_camel
from scripts.procesar_pyg import combinar_historico_pyg
from scripts.descargar_datos_seps import extraer_download_id
from scripts.seps_zip import inspeccionar_zip_seps
from scripts.io_atomico import guardar_parquet_atomico


class InspeccionZipTests(unittest.TestCase):
    def crear_zip(self, nombres):
        temporal = tempfile.TemporaryDirectory()
        path = Path(temporal.name) / "2026_EEFF-Men.zip"
        with zipfile.ZipFile(path, "w") as zf:
            for nombre in nombres:
                zf.writestr(nombre, b"")
        self.addCleanup(temporal.cleanup)
        return path

    def test_reconoce_fecha_uniforme_y_cuatro_segmentos(self):
        path = self.crear_zip([
            "Boletin Financiero Segmento 1_jun_2026.xlsm",
            "Boletin Financiero Segmento 2_jun_2026.xlsm",
            "Boletin Financiero Segmento 3_jun_2026.xlsm",
            "Boletin Financiero Mutualistas_jun_2026.xlsm",
            "Boletin Financiero CONAFIPS_jun_2026.xlsm",
        ])
        resultado = inspeccionar_zip_seps(path)
        self.assertEqual(resultado.fecha_corte.date().isoformat(), "2026-06-30")
        self.assertEqual(len(resultado.segmentos), 4)

    def test_rechaza_segmento_faltante(self):
        path = self.crear_zip([
            "Boletin Financiero Segmento 1_jun_2026.xlsm",
            "Boletin Financiero Segmento 2_jun_2026.xlsm",
            "Boletin Financiero Mutualistas_jun_2026.xlsm",
        ])
        with self.assertRaisesRegex(ValueError, "SEGMENTO 3"):
            inspeccionar_zip_seps(path)

    def test_rechaza_fechas_mezcladas(self):
        path = self.crear_zip([
            "Boletin Financiero Segmento 1_jun_2026.xlsm",
            "Boletin Financiero Segmento 2_jun_2026.xlsm",
            "Boletin Financiero Segmento 3_may_2026.xlsm",
            "Boletin Financiero Mutualistas_jun_2026.xlsm",
        ])
        with self.assertRaisesRegex(ValueError, "mezcla fechas"):
            inspeccionar_zip_seps(path)

    def test_scraper_elige_el_panel_financiero_mensual(self):
        html = """
        <div class="panel"><h5>Otro reporte</h5>
          <a href="?download_id=9999">2026</a></div>
        <div class="panel">
          <div class="panel-heading"><h5><a>Estados Financieros Mensuales</a></h5></div>
          <div class="panel-body"><a href="?download_id=3255">2026</a></div>
        </div>
        """
        self.assertEqual(extraer_download_id(html, 2026), "3255")


class IncrementalidadTests(unittest.TestCase):
    def test_pyg_reemplaza_solapamiento_y_conserva_historia(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "pyg.parquet"
            historico = pd.DataFrame({
                "fecha": pd.to_datetime(["2020-01-31", "2026-01-31"]),
                "segmento": ["SEGMENTO 1", "SEGMENTO 1"],
                "cooperativa": ["A", "A"],
                "codigo": ["5", "5"],
                "cuenta": ["INGRESOS", "INGRESOS"],
                "valor_acumulado": [10.0, 20.0],
                "valor_mes": [10.0, 20.0],
                "valor_12m": [pd.NA, pd.NA],
            })
            historico.to_parquet(output, index=False)
            fuente = pd.DataFrame({
                "fecha": pd.to_datetime(["2026-01-31", "2026-02-28"]),
                "segmento": ["SEGMENTO 1", "SEGMENTO 1"],
                "ruc": ["1", "1"],
                "cooperativa": ["A", "A"],
                "codigo": ["5", "5"],
                "cuenta": ["INGRESOS", "INGRESOS"],
                "valor": [25.0, 40.0],
            })
            combinado = combinar_historico_pyg(fuente, output)
            self.assertEqual(len(combinado), 3)
            self.assertEqual(combinado["fecha"].min(), pd.Timestamp("2020-01-31"))
            enero = combinado[combinado["fecha"] == pd.Timestamp("2026-01-31")]
            self.assertEqual(enero["valor"].iloc[0], 25.0)

    def test_camel_reemplaza_solapamiento_y_conserva_historia(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "indicadores.parquet"
            columnas = {
                "cooperativa": ["A", "A"],
                "segmento": ["SEGMENTO 1", "SEGMENTO 1"],
                "fecha": pd.to_datetime(["2020-01-31", "2026-01-31"]),
                "codigo": ["ROE", "ROE"],
                "indicador": ["ROE", "ROE"],
                "valor": [0.1, 0.2],
                "categoria": ["E", "E"],
            }
            pd.DataFrame(columnas).to_parquet(output, index=False)
            fuente = pd.DataFrame({
                **columnas,
                "fecha": pd.to_datetime(["2026-01-31", "2026-02-28"]),
                "valor": [0.25, 0.3],
            })
            combinado = combinar_historico_camel(fuente, output)
            self.assertEqual(len(combinado), 3)
            self.assertEqual(combinado["fecha"].min(), pd.Timestamp("2020-01-31"))
            enero = combinado[combinado["fecha"] == pd.Timestamp("2026-01-31")]
            self.assertEqual(enero["valor"].iloc[0], 0.25)


class EscrituraAtomicaTests(unittest.TestCase):
    """
    Hardening 14-sep-2026 (P1, integridad de actualización): un dataset
    productivo nunca debe quedar parcialmente escrito. `guardar_parquet_atomico()`
    escribe a un temporal y reemplaza con `os.replace()` (atómico) solo si
    la escritura completa sin errores.
    """

    def test_escritura_exitosa_reemplaza_el_archivo_y_no_deja_temporales(self):
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "datos.parquet"
            df = pd.DataFrame({"a": [1, 2, 3]})
            guardar_parquet_atomico(df, destino, index=False)

            self.assertTrue(destino.exists())
            leido = pd.read_parquet(destino)
            pd.testing.assert_frame_equal(leido, df)
            # Sin archivos temporales huérfanos en el directorio.
            temporales = list(Path(tmp).glob(".*.tmp_atomico"))
            self.assertEqual(temporales, [])

    def test_fallo_durante_la_escritura_preserva_el_archivo_productivo_anterior(self):
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "datos.parquet"
            df_original = pd.DataFrame({"a": [1, 2, 3]})
            df_original.to_parquet(destino, index=False)
            contenido_original = destino.read_bytes()

            df_nuevo_invalido = pd.DataFrame({"a": [9, 9, 9]})
            with self.assertRaises(RuntimeError):
                with unittest.mock.patch.object(
                    pd.DataFrame, "to_parquet", side_effect=RuntimeError("fallo simulado durante la escritura")
                ):
                    guardar_parquet_atomico(df_nuevo_invalido, destino, index=False)

            # El archivo productivo debe seguir siendo EXACTAMENTE el original — byte a byte.
            self.assertEqual(destino.read_bytes(), contenido_original)
            leido = pd.read_parquet(destino)
            pd.testing.assert_frame_equal(leido, df_original)
            # El temporal huérfano se limpia, no queda basura en el directorio.
            temporales = list(Path(tmp).glob(".*.tmp_atomico"))
            self.assertEqual(temporales, [])

    def test_fallo_sin_archivo_previo_no_deja_nada_a_medio_escribir(self):
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / "nuevo.parquet"
            df = pd.DataFrame({"a": [1]})
            with self.assertRaises(RuntimeError):
                with unittest.mock.patch.object(
                    pd.DataFrame, "to_parquet", side_effect=RuntimeError("fallo simulado")
                ):
                    guardar_parquet_atomico(df, destino, index=False)
            self.assertFalse(destino.exists())


if __name__ == "__main__":
    unittest.main()
