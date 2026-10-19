# -*- coding: utf-8 -*-
"""Lógica única de filtrado: casos obligatorios 1-11, 14 y 15 sobre la capa pura (sin Streamlit)."""
import io
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from utils import filtros_analisis as fa  # noqa: E402
from utils.filtros_analisis import FiltroAnalisis, aplicar_filtros_analisis as ap  # noqa: E402

FECHAS = pd.date_range("2020-01-31", periods=24, freq="ME")


def _dim():
    filas = []
    def add(entidad, coop, fechas, seg, proc):
        for f in fechas:
            filas.append(dict(entidad=entidad, cooperativa=coop, fecha=f, segmento_clasif=seg, segmento_actual="SEGMENTO 3",
                              procedencia_clasif=proc, fuente_clasif="x"))
    add("A", "A", FECHAS, "SEGMENTO 1", "oficial_mes")
    add("B", "B", FECHAS, "SEGMENTO 2", "arrastrado")
    add("C", "C", FECHAS[:12], "SEGMENTO 2", "oficial_mes")        # cambia de segmento
    add("C", "C", FECHAS[12:], "SEGMENTO 3", "arrastrado")
    add("D", "D", FECHAS, "SEGMENTO 1", "estimado")
    add("E", "E", FECHAS, None, "no_verificable")                  # sin clasificación verificable
    add("F", "F", FECHAS[:10], "SEGMENTO 2", "oficial_mes")        # cambia de nombre de fuente
    add("F", "F EN LIQUIDACION", FECHAS[10:], "SEGMENTO 2", "oficial_mes")
    return pd.DataFrame(filas)


def _datos(dim):
    """Base de hechos: una fila por (cooperativa, fecha, codigo)."""
    r = np.random.default_rng(1)
    d = dim[["cooperativa", "fecha"]].merge(pd.DataFrame({"codigo": ["1", "14"]}), how="cross")
    d["valor"] = r.normal(100, 10, len(d)).round(2)
    d["segmento"] = "SEGMENTO 3"        # segmento actual retroactivo: NO debe usarse para filtrar
    return d


class TestFiltros(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dim = _dim(); cls.d = _datos(cls.dim)
        cls.todo = fa.filtro_por_defecto(cls.dim)

    def f(self, **kw):
        return self.todo.con(**kw)

    def test_01_todos_los_segmentos_y_entidades(self):
        r = ap(self.d, self.todo, self.dim)
        self.assertEqual(len(r), len(self.d))                       # nada se pierde, incluida la entidad sin clasificación
        self.assertEqual(set(r.entidad), set("ABCDEF"))

    def test_02_un_segmento_todas_sus_entidades(self):
        r = ap(self.d, self.f(segmentos=("SEGMENTO 1",)), self.dim)
        self.assertEqual(set(r.entidad), {"A", "D"})
        self.assertEqual(set(r.segmento_clasif), {"SEGMENTO 1"})

    def test_03_varios_segmentos(self):
        r = ap(self.d, self.f(segmentos=("SEGMENTO 1", "SEGMENTO 2")), self.dim)
        self.assertEqual(set(r.entidad), {"A", "B", "C", "D", "F"})
        self.assertTrue(set(r.segmento_clasif) <= {"SEGMENTO 1", "SEGMENTO 2"})

    def test_04_una_entidad(self):
        r = ap(self.d, self.f(entidades=("B",)), self.dim)
        self.assertEqual(set(r.entidad), {"B"}); self.assertEqual(len(r), 24 * 2)

    def test_05_varias_entidades_mismo_segmento(self):
        r = ap(self.d, self.f(entidades=("A", "D"), segmentos=("SEGMENTO 1",)), self.dim)
        self.assertEqual(set(r.entidad), {"A", "D"})

    def test_06_varias_entidades_segmentos_distintos(self):
        r = ap(self.d, self.f(entidades=("A", "B")), self.dim)
        self.assertEqual(set(r.segmento_clasif), {"SEGMENTO 1", "SEGMENTO 2"})

    def test_07_entidad_que_cambia_de_segmento(self):
        s2 = ap(self.d, self.f(entidades=("C",), segmentos=("SEGMENTO 2",)), self.dim)
        s3 = ap(self.d, self.f(entidades=("C",), segmentos=("SEGMENTO 3",)), self.dim)
        self.assertEqual(s2.fecha.max(), FECHAS[11]); self.assertEqual(s3.fecha.min(), FECHAS[12])
        self.assertEqual(len(s2) + len(s3), 24 * 2)                 # particiona exacto, sin solape ni pérdida
        # el segmento ACTUAL retroactivo (S3) jamás reemplaza al puntual
        self.assertEqual(set(s2.segmento_clasif), {"SEGMENTO 2"})

    def test_07b_entidad_con_dos_nombres_de_fuente(self):
        r = ap(self.d, self.f(entidades=("F",)), self.dim)
        self.assertEqual(set(r.cooperativa), {"F", "F EN LIQUIDACION"}); self.assertEqual(len(r), 24 * 2)

    def test_08_periodo_sin_datos(self):
        flt = self.f(fecha_ini="2030-01-31", fecha_fin="2030-12-31")
        r = ap(self.d, flt, self.dim)
        self.assertEqual(len(r), 0)
        self.assertEqual(fa.cobertura(self.dim, flt)["obs"], 0)
        self.assertEqual(fa.entidades_disponibles(self.dim, flt), [])

    def test_09_entidad_sin_clasificacion_verificable(self):
        # sin restricción de segmento se conserva y queda marcada; con cualquier segmento se excluye
        sin = ap(self.d, self.f(entidades=("E",)), self.dim)
        self.assertEqual(set(sin.procedencia_clasif), {"no_verificable"}); self.assertTrue(sin.segmento_clasif.isna().all())
        con = ap(self.d, self.f(entidades=("E",), segmentos=("SEGMENTO 1", "SEGMENTO 2", "SEGMENTO 3")), self.dim)
        self.assertEqual(len(con), 0)
        solo = ap(self.d, self.f(calidad="no_verificable"), self.dim)
        self.assertEqual(set(solo.entidad), {"E"})

    def test_10_oficial_frente_a_arrastrada(self):
        of = ap(self.d, self.f(calidad="oficial"), self.dim); ar = ap(self.d, self.f(calidad="arrastrada"), self.dim)
        es = ap(self.d, self.f(calidad="estimada"), self.dim)
        self.assertEqual(set(of.procedencia_clasif), {"oficial_mes"}); self.assertEqual(set(ar.procedencia_clasif), {"arrastrado"})
        self.assertEqual(set(es.entidad), {"D"})
        self.assertFalse(set(zip(of.cooperativa, of.fecha)) & set(zip(ar.cooperativa, ar.fecha)))
        cov = fa.cobertura(self.dim, self.f(calidad="oficial"))
        self.assertGreater(cov["obs_excluidas_por_calidad"], 0)
        self.assertEqual(cov["obs"] + cov["obs_excluidas_por_calidad"], cov["obs_sin_filtro_calidad"])

    def test_11_entidades_disponibles_cambian_con_el_segmento(self):
        s1 = fa.entidades_disponibles(self.dim, self.f(segmentos=("SEGMENTO 1",)))
        s12 = fa.entidades_disponibles(self.dim, self.f(segmentos=("SEGMENTO 1", "SEGMENTO 2")))
        self.assertEqual(s1, ["A", "D"]); self.assertEqual(s12, ["A", "B", "C", "D", "F"])
        # la selección previa se reconcilia: solo se conservan las válidas
        validas, descartadas = fa.reconciliar_entidades(["A", "B", "E"], s1)
        self.assertEqual(validas, ["A"]); self.assertEqual(descartadas, ["B", "E"])
        # la disponibilidad depende del período: C solo es S3 desde 2021
        s3_2020 = fa.entidades_disponibles(self.dim, self.f(segmentos=("SEGMENTO 3",), fecha_fin=FECHAS[11]))
        self.assertEqual(s3_2020, [])

    def test_11b_seleccionar_entidad_primero_y_luego_segmento(self):
        # entidad B (S2) elegida; al restringir a S1 la combinación es vacía (no se cuelan registros ajenos)
        self.assertEqual(len(ap(self.d, self.f(entidades=("B",), segmentos=("SEGMENTO 1",)), self.dim)), 0)
        self.assertEqual(len(ap(self.d, self.f(entidades=("B",), segmentos=("SEGMENTO 2",)), self.dim)), 24 * 2)

    def test_11c_periodo_acota_los_registros(self):
        r = ap(self.d, self.f(fecha_ini=FECHAS[5], fecha_fin=FECHAS[8], entidades=("A",)), self.dim)
        self.assertEqual(r.fecha.min(), FECHAS[5]); self.assertEqual(r.fecha.max(), FECHAS[8]); self.assertEqual(len(r), 4 * 2)

    def test_12_restablecer_devuelve_el_filtro_por_defecto(self):
        modificado = self.f(segmentos=("SEGMENTO 2",), entidades=("B",), calidad="oficial")
        self.assertNotEqual(modificado, self.todo)
        self.assertEqual(fa.filtro_por_defecto(self.dim), self.todo)
        self.assertEqual(len(ap(self.d, fa.filtro_por_defecto(self.dim), self.dim)), len(self.d))

    def test_14_exportacion_igual_a_la_tabla(self):
        flt = self.f(segmentos=("SEGMENTO 2",), entidades=("B", "C"))
        r = ap(self.d, flt, self.dim)
        csv = fa.exportar_csv(r, flt, FECHAS[-1], "prueba").decode("utf-8-sig")
        self.assertIn("# segmentos: SEGMENTO 2", csv); self.assertIn("# corte_de_datos: 12/2021", csv)
        back = pd.read_csv(io.StringIO(csv), comment="#")
        self.assertEqual(len(back), len(r)); self.assertEqual(list(back.columns), list(r.columns))
        self.assertTrue(np.allclose(back["valor"], r["valor"]))
        self.assertEqual(set(back["entidad"]), set(r["entidad"]))
        xl = pd.read_excel(io.BytesIO(fa.exportar_excel(r, flt, FECHAS[-1], "prueba")), sheet_name=None)
        self.assertEqual(len(xl["datos"]), len(r)); self.assertTrue(np.allclose(xl["datos"]["valor"], r["valor"]))
        self.assertIn("segmentos", set(xl["filtros"]["parametro"]))

    def test_15_sin_duplicados_tras_uniones(self):
        for flt in (self.todo, self.f(segmentos=("SEGMENTO 2",)), self.f(entidades=("C", "F")), self.f(calidad="arrastrada")):
            r = ap(self.d, flt, self.dim)
            self.assertFalse(r.duplicated(["cooperativa", "fecha", "codigo"]).any())
        dup = pd.concat([self.dim, self.dim.iloc[:1]])
        with self.assertRaises(ValueError):
            ap(self.d, self.todo, dup)

    def test_hashable_y_roundtrip(self):
        flt = self.f(segmentos=("SEGMENTO 2", "SEGMENTO 1"), entidades=("B", "A"))
        self.assertEqual(FiltroAnalisis.desde_tupla(flt.a_tupla()), flt)
        self.assertEqual(hash(flt), hash(self.f(segmentos=("SEGMENTO 1", "SEGMENTO 2"), entidades=("A", "B"))))
        with self.assertRaises(ValueError):
            FiltroAnalisis(calidad="inexistente")


class TestDatosReales(unittest.TestCase):
    """La dimensión generada es consistente con las bases productivas."""
    @classmethod
    def setUpClass(cls):
        md = Path(__file__).resolve().parents[1] / "master_data"
        cls.dim = pd.read_parquet(md / "dim_observaciones.parquet"); cls.md = md

    def test_clave_unica_y_cobertura_de_bases(self):
        self.assertFalse(self.dim.duplicated(["cooperativa", "fecha"]).any())
        for f in ("agg_ranking_cooperativas", "agg_series_temporales", "pyg", "indicadores"):
            k = pd.read_parquet(self.md / f"{f}.parquet", columns=["cooperativa", "fecha"]).drop_duplicates()
            k = k.assign(cooperativa=k.cooperativa.astype(str))
            k = k[~k.cooperativa.str.startswith("VT_TOTAL")]       # subtotales del reporte: el cargador los excluye
            m = k.merge(self.dim.assign(cooperativa=self.dim.cooperativa.astype(str))[["cooperativa", "fecha"]], how="left", indicator=True)
            self.assertEqual((m._merge == "left_only").sum(), 0, f)

    def test_segmento_filtrado_es_el_puntual_no_el_actual(self):
        rk = pd.read_parquet(self.md / "agg_ranking_cooperativas.parquet")
        flt = fa.filtro_por_defecto(self.dim).con(segmentos=("SEGMENTO 1",))
        r = fa.aplicar_filtros_analisis(rk, flt, self.dim)
        self.assertEqual(set(r.segmento_clasif), {"SEGMENTO 1"})
        antiguo = rk[rk.segmento == "SEGMENTO 1"]
        self.assertNotEqual(len(r), len(antiguo))      # el filtro puntual difiere del retroactivo (≈14 % de las filas)

    def test_procedencia_y_no_asignacion_silenciosa(self):
        nv = self.dim[self.dim.procedencia_clasif == "no_verificable"]
        self.assertTrue(nv.segmento_clasif.isna().all())
        self.assertTrue(self.dim[self.dim.procedencia_clasif != "no_verificable"].segmento_clasif.notna().all())


if __name__ == "__main__":
    unittest.main()
