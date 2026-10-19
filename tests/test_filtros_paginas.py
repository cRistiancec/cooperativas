# -*- coding: utf-8 -*-
"""
Filtros globales — pruebas sobre los DATOS REALES y sobre la APLICACIÓN (AppTest).

Complementa `tests/test_filtros_analisis.py` (capa pura, datos sintéticos). Cubre los casos obligatorios que requieren
la aplicación o las bases reales:

  11  la lista de entidades cambia dinámicamente al cambiar el segmento
  12  el botón «Restablecer filtros» devuelve todo a su valor por defecto
  13  coherencia entre indicadores, tablas, gráficos y alertas (misma población)
  14  la exportación CSV/Excel coincide con la tabla mostrada
  15  sin duplicados tras filtros y uniones (todas las bases, incluido el panel)
  +   combinación vacía → aviso, sin gráficos ni métricas
  +   las 20 páginas cargan sin excepción con una selección combinada (segmento + calidad) y con una sola entidad
"""
import io
import logging
import os
import subprocess
import sys
import unittest
import warnings
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)

from streamlit.testing.v1 import AppTest  # noqa: E402

from ui import filtros as uif  # noqa: E402
from utils import filtros_analisis as fa  # noqa: E402
from utils.data_loader import (  # noqa: E402
    acotar_entidades, cargar_dim_observaciones, datos_filtrados, datos_universo, obtener_metricas_kpi,
    obtener_ranking_rapido, obtener_serie_sistema,
)

PAGINA_LIGERA = "pages/8_Riesgo_Concentracion.py"
TODAS_LAS_PAGINAS = ["Inicio.py"] + [str(p.relative_to(REPO)) for p in sorted((REPO / "pages").glob("*.py"),
                                                                              key=lambda p: int(p.name.split("_")[0]))]


def _app(pagina: str, t: int = 400) -> AppTest:
    # Ruta relativa + cwd = raíz: `st.page_link` de Inicio.py necesita el registro de páginas del proyecto.
    os.chdir(REPO)
    return AppTest.from_file(pagina, default_timeout=t)


def _opciones(at: AppTest, key: str) -> list:
    return list(at.sidebar.multiselect(key=key).options)


def _total() -> fa.FiltroAnalisis:
    return fa.filtro_por_defecto(cargar_dim_observaciones())


# --------------------------------------------------------------------------------------------------
class TestComportamientoEnLaUI(unittest.TestCase):
    """Casos 11, 12 y combinación vacía, ejecutando la aplicación real."""

    @classmethod
    def setUpClass(cls):
        cls.dim = cargar_dim_observaciones()
        cls.segs = fa.segmentos_disponibles(cls.dim)

    def _esperadas(self, **kw) -> list:
        return fa.entidades_disponibles(self.dim, _total().con(**kw))

    def test_11_las_entidades_disponibles_cambian_con_el_segmento(self):
        at = _app(PAGINA_LIGERA); at.run()
        self.assertFalse(at.exception)
        todas = _opciones(at, "_w_entidades")
        self.assertEqual(todas, self._esperadas())
        s1, s3 = "SEGMENTO 1", "SEGMENTO 3"
        at.sidebar.multiselect(key="_w_segmentos").set_value([s1]).run()
        o1 = _opciones(at, "_w_entidades")
        self.assertEqual(o1, self._esperadas(segmentos=(s1,)))
        at.sidebar.multiselect(key="_w_segmentos").set_value([s1, s3]).run()
        o13 = _opciones(at, "_w_entidades")
        self.assertEqual(o13, self._esperadas(segmentos=(s1, s3)))
        self.assertTrue(set(o1) < set(o13) < set(todas) or set(o1) < set(o13) <= set(todas))
        at.sidebar.multiselect(key="_w_segmentos").set_value([s3]).run()
        o3 = _opciones(at, "_w_entidades")
        self.assertNotEqual(set(o1), set(o3), "Las entidades de S1 y S3 no pueden ser idénticas")

    def test_11b_seleccion_invalida_se_descarta_con_aviso(self):
        """Primero se elige la entidad y después un segmento incompatible: se descarta y se informa (no en silencio)."""
        at = _app(PAGINA_LIGERA); at.run()
        s1, s3 = "SEGMENTO 1", "SEGMENTO 3"
        solo_s1 = sorted(set(self._esperadas(segmentos=(s1,))) - set(self._esperadas(segmentos=(s3,))))
        self.assertTrue(solo_s1, "se necesita una entidad que nunca estuvo en el segmento 3")
        e = solo_s1[0]
        at.sidebar.multiselect(key="_w_entidades").set_value([e]).run()
        self.assertEqual(at.session_state[uif.K_ENT], [e])
        at.sidebar.multiselect(key="_w_segmentos").set_value([s3]).run()
        self.assertEqual(at.session_state[uif.K_ENT], [], "la entidad inválida debió quitarse")
        self.assertEqual(list(at.sidebar.multiselect(key="_w_entidades").value), [])
        avisos = " ".join(i.value for i in at.sidebar.info)
        self.assertIn("Se quitó de la selección", avisos)
        self.assertIn(e, avisos)

    def test_11c_entidad_valida_se_conserva_al_ampliar_segmentos(self):
        at = _app(PAGINA_LIGERA); at.run()
        s1, s2 = "SEGMENTO 1", "SEGMENTO 2"
        e = self._esperadas(segmentos=(s1,))[0]
        at.sidebar.multiselect(key="_w_entidades").set_value([e]).run()
        at.sidebar.multiselect(key="_w_segmentos").set_value([s1, s2]).run()
        self.assertEqual(at.session_state[uif.K_ENT], [e])

    def test_12_restablecer_filtros_devuelve_los_valores_por_defecto(self):
        at = _app(PAGINA_LIGERA); at.run()
        at.sidebar.multiselect(key="_w_segmentos").set_value(["SEGMENTO 2"]).run()
        at.sidebar.selectbox(key="_w_calidad").set_value("oficial").run()
        e = self._esperadas(segmentos=("SEGMENTO 2",), calidad="oficial")[0]
        at.sidebar.multiselect(key="_w_entidades").set_value([e]).run()
        self.assertEqual(at.session_state[uif.K_SEG], ["SEGMENTO 2"])
        self.assertEqual(at.session_state[uif.K_CAL], "oficial")
        self.assertEqual(at.session_state[uif.K_ENT], [e])
        at.sidebar.button(key="_btn_reset").click().run()
        inicial = uif.estado_inicial(self.dim)
        for k, v in inicial.items():
            self.assertEqual(at.session_state[k], v, f"{k} no volvió a su valor por defecto")
        self.assertEqual(list(at.sidebar.multiselect(key="_w_segmentos").value), [])
        self.assertEqual(list(at.sidebar.multiselect(key="_w_entidades").value), [])
        self.assertEqual(at.sidebar.selectbox(key="_w_calidad").value, "todas")
        self.assertFalse(at.exception)

    def test_8_combinacion_sin_observaciones_muestra_aviso_y_no_grafica(self):
        """Segmento 1 + «no verificable»: una observación sin clasificación nunca satisface una restricción de segmento."""
        at = _app(PAGINA_LIGERA); at.run()
        at.sidebar.multiselect(key="_w_segmentos").set_value(["SEGMENTO 1"]).run()
        at.sidebar.selectbox(key="_w_calidad").set_value("no_verificable").run()
        self.assertFalse(at.exception)
        self.assertTrue(any("no tiene observaciones" in w.value for w in at.warning), "debe avisar que no hay observaciones")
        self.assertEqual(len(at.metric), 0, "no debe presentar métricas de una selección vacía")
        self.assertEqual(len(at.get("plotly_chart")), 0, "no debe presentar gráficos vacíos como resultados")

    def test_8b_periodo_invertido_nunca_ocurre(self):
        at = _app(PAGINA_LIGERA); at.run()
        fechas = fa.fechas_disponibles(self.dim)
        at.sidebar.selectbox(key="_w_desde").set_value(pd.Timestamp(fechas[-1])).run()
        ini, fin = at.session_state[uif.K_INI], at.session_state[uif.K_FIN]
        self.assertLessEqual(pd.Timestamp(ini), pd.Timestamp(fin))


# --------------------------------------------------------------------------------------------------
class TestCoherenciaConDatosReales(unittest.TestCase):
    """Caso 13: todas las vistas de una página salen de la MISMA población filtrada."""

    @classmethod
    def setUpClass(cls):
        cls.dim = cargar_dim_observaciones()
        cls.todo = _total()
        cls.ultimo = pd.Timestamp(cls.dim["fecha"].max())
        cls.filtros = {
            "todo": cls.todo,
            "un_segmento": cls.todo.con(segmentos=("SEGMENTO 2",)),
            "dos_segmentos_oficial": cls.todo.con(segmentos=("SEGMENTO 1", "SEGMENTO 3"), calidad="oficial"),
            "periodo_corto": cls.todo.con(fecha_ini=cls.ultimo - pd.DateOffset(months=11)),
        }
        e = fa.entidades_disponibles(cls.dim, cls.todo.con(segmentos=("SEGMENTO 2",)))[:3]
        cls.filtros["tres_entidades"] = cls.todo.con(entidades=tuple(e))

    def test_toda_base_filtrada_solo_contiene_observaciones_visibles(self):
        for nombre, f in self.filtros.items():
            vis = fa.observaciones_visibles(self.dim, f)
            permitidos = set(zip(vis["cooperativa"].astype(str), pd.to_datetime(vis["fecha"])))
            for base in ("ranking", "indicadores", "pyg", "series"):
                with self.subTest(filtro=nombre, base=base):
                    d = datos_filtrados(base, f)
                    if d.empty:
                        continue
                    claves = set(zip(d["cooperativa"].astype(str), pd.to_datetime(d["fecha"])))
                    self.assertTrue(claves <= permitidos, f"{base}: filas fuera de la población filtrada")
                    self.assertTrue(d["fecha"].between(f.fecha_ini, f.fecha_fin).all())
                    if f.segmentos:
                        self.assertTrue(d["segmento"].astype(str).isin(f.segmentos).all())
                    if f.entidades:
                        self.assertTrue(d["entidad"].astype(str).isin(f.entidades).all())

    def test_kpi_ranking_serie_y_numero_de_entidades_coinciden(self):
        for nombre, f in self.filtros.items():
            with self.subTest(filtro=nombre):
                fecha = datos_filtrados("ranking", f)["fecha"].max()
                kpi = obtener_metricas_kpi(fecha, f)
                rk = obtener_ranking_rapido(fecha, "1", top_n=0, filtro=f)
                serie = obtener_serie_sistema("1", f)
                self.assertAlmostEqual(kpi["total_activos"], rk["valor"].sum() / 1e6, places=3)
                self.assertAlmostEqual(kpi["total_activos"], serie.loc[serie["fecha"] == fecha, "valor_total"].iloc[0] / 1e6, places=3)
                self.assertEqual(int(kpi["num_cooperativas"]), rk["cooperativa"].nunique())

    def test_segmentos_particionan_el_total_sin_duplicar(self):
        f, ultimo = self.todo, self.ultimo

        def en_corte(filtro):
            s = obtener_serie_sistema("1", filtro)
            return s.loc[s["fecha"] == ultimo, "valor_total"].sum()

        total = en_corte(f)
        partes = sum(en_corte(f.con(segmentos=(s,))) for s in fa.segmentos_disponibles(self.dim))
        partes += en_corte(f.con(calidad="no_verificable"))
        self.assertAlmostEqual(total / 1e6, partes / 1e6, places=3)

    def test_alertas_evaluan_exactamente_la_poblacion_filtrada(self):
        from analytics.financial_engine import evaluar_alertas
        for nombre, f in self.filtros.items():
            with self.subTest(filtro=nombre):
                ind = datos_filtrados("indicadores", f)
                if ind.empty:
                    continue
                fecha = ind["fecha"].max()
                alertas = evaluar_alertas(ind, fecha)
                esperadas = set(ind.loc[ind["fecha"] == fecha, "cooperativa"].astype(str))
                self.assertTrue(set(alertas["cooperativa"].astype(str)) <= esperadas)
                self.assertEqual(alertas["cooperativa"].nunique(), len(alertas), "una alerta por entidad")

    def test_universo_de_referencia_no_depende_de_la_seleccion_de_entidades(self):
        """Percentiles/IIS se calculan sobre el universo: elegir entidades solo decide cuáles se muestran."""
        f_ent = self.filtros["tres_entidades"]
        base = datos_universo("indicadores", f_ent)
        sin_ent = datos_filtrados("indicadores", f_ent.con(entidades=()))
        self.assertEqual(len(base), len(sin_ent))
        from analytics.financial_engine import calcular_score_camel
        fecha = base["fecha"].max()
        score = calcular_score_camel(base, fecha)
        meta = base[base["fecha"] == fecha][["cooperativa", "entidad"]].drop_duplicates("cooperativa")
        vista = acotar_entidades(score.merge(meta, on="cooperativa", how="left"), f_ent)
        self.assertLessEqual(vista["entidad"].nunique(), 3)
        self.assertGreater(len(score), len(vista), "el score se calcula con más entidades que las mostradas")
        # el score de una entidad no cambia por seleccionar solo esa entidad
        completo = calcular_score_camel(datos_filtrados("indicadores", f_ent.con(entidades=())), fecha)
        for _, fila in vista.iterrows():
            ref = completo.loc[completo["cooperativa"] == fila["cooperativa"], "score_total"].iloc[0]
            self.assertAlmostEqual(fila["score_total"], ref, places=9)

    def test_panel_vulnerabilidad_comparte_la_clasificacion_de_la_dimension(self):
        from utils.panel_vulnerabilidad import cargar_panel, panel_filtrado
        crudo = cargar_panel()
        if crudo.empty:
            self.skipTest("panel no disponible")
        for nombre, f in self.filtros.items():
            with self.subTest(filtro=nombre):
                p = panel_filtrado(f)
                if p.empty:
                    continue
                self.assertTrue((p["segmento_repo"].astype(str) == p["segmento_clasif"].astype(str)).all(),
                                "segmento_repo del panel difiere de la clasificación puntual de la dimensión")
                mapa = {"exacto_mes": "oficial_mes", "arrastrado": "arrastrado", "estimado": "estimado"}
                self.assertTrue((p["segmento_procedencia"].map(mapa) == p["procedencia_clasif"].astype(str)).all())
                self.assertFalse(p.duplicated(["cooperativa", "fecha"]).any())


# --------------------------------------------------------------------------------------------------
class TestExportacionesCoincidenConLaTabla(unittest.TestCase):
    """Caso 14 con datos reales: el archivo exportado reconstruye EXACTAMENTE la tabla mostrada."""

    @classmethod
    def setUpClass(cls):
        cls.dim = cargar_dim_observaciones()
        cls.todo = _total()

    def _tabla(self, f):
        rk = datos_filtrados("ranking", f)
        fecha = rk["fecha"].max()
        t = rk[(rk["fecha"] == fecha) & (rk["codigo"] == "1")][["fecha", "cooperativa", "entidad", "segmento", "procedencia_clasif", "codigo", "valor"]]
        t = t.astype({"cooperativa": str, "entidad": str, "segmento": str, "procedencia_clasif": str, "codigo": str})
        return t.sort_values("valor", ascending=False).reset_index(drop=True), fecha

    def test_csv_y_excel_reproducen_la_tabla_y_declaran_el_filtro(self):
        casos = {
            "todo": self.todo,
            "segmentos_1_2_oficial": self.todo.con(segmentos=("SEGMENTO 1", "SEGMENTO 2"), calidad="oficial"),
            "dos_entidades": self.todo.con(entidades=tuple(fa.entidades_disponibles(self.dim, self.todo)[:2])),
        }
        for nombre, f in casos.items():
            with self.subTest(filtro=nombre):
                t, fecha = self._tabla(f)
                self.assertGreater(len(t), 0)
                pob = {"entidades_usadas": int(t["entidad"].nunique()), "observaciones_usadas": len(t)}
                csv = fa.exportar_csv(t, f, fecha, "Ranking de prueba", pob)
                texto = csv.decode("utf-8-sig")
                lineas_meta = [ln for ln in texto.splitlines() if ln.startswith("#")]
                meta = "\n".join(lineas_meta)
                self.assertIn(f"corte_de_datos: {pd.Timestamp(fecha):%m/%Y}", meta)
                self.assertIn("calidad_clasificacion:", meta)
                self.assertIn("segmentos: " + (", ".join(f.segmentos) if f.segmentos else "todos"), meta)
                if f.entidades:
                    for e in f.entidades:
                        self.assertIn(e, meta)
                leido = pd.read_csv(io.StringIO(texto), comment="#", dtype={"codigo": str})
                leido["fecha"] = pd.to_datetime(leido["fecha"])
                pd.testing.assert_frame_equal(leido, t, check_dtype=False, check_exact=False, rtol=1e-12)
                # Excel
                xlsx = fa.exportar_excel(t, f, fecha, "Ranking de prueba", pob)
                hojas = pd.read_excel(io.BytesIO(xlsx), sheet_name=None, dtype={"codigo": str})
                self.assertEqual(set(hojas), {"datos", "filtros"})
                pd.testing.assert_frame_equal(hojas["datos"].assign(fecha=lambda x: pd.to_datetime(x["fecha"])), t,
                                              check_dtype=False, check_exact=False, rtol=1e-12)
                self.assertIn("calidad_clasificacion", set(hojas["filtros"]["parametro"]))
                # nada fuera de la selección
                if f.segmentos:
                    self.assertTrue(set(leido["segmento"]) <= set(f.segmentos))
                if f.entidades:
                    self.assertTrue(set(leido["entidad"]) <= set(f.entidades))
                if f.calidad == "oficial":
                    self.assertEqual(set(leido["procedencia_clasif"]), {"oficial_mes"})

    def test_la_exportacion_no_incluye_registros_excluidos_por_el_filtro(self):
        f = self.todo.con(segmentos=("SEGMENTO 1",))
        t, _ = self._tabla(f)
        fuera = datos_filtrados("ranking", self.todo.con(segmentos=("SEGMENTO 3",)))
        self.assertTrue(set(t["cooperativa"]).isdisjoint(set(fuera.loc[fuera["fecha"] == t["fecha"].iloc[0], "cooperativa"].astype(str))))


# --------------------------------------------------------------------------------------------------
class TestSinDuplicados(unittest.TestCase):
    """Caso 15 con datos reales: ni los filtros ni las uniones con la dimensión multiplican o repiten filas."""

    @classmethod
    def setUpClass(cls):
        cls.todo = _total()

    def test_dimension_con_clave_unica(self):
        d = cargar_dim_observaciones()
        self.assertFalse(d.duplicated(["cooperativa", "fecha"]).any())

    def test_las_bases_filtradas_no_tienen_duplicados_ni_filas_de_mas(self):
        from utils.data_loader import cargar_indicadores, cargar_pyg, cargar_ranking_cooperativas, cargar_series_temporales
        crudas = {"ranking": (cargar_ranking_cooperativas(), ["cooperativa", "fecha", "codigo"]),
                  "indicadores": (cargar_indicadores()[0], ["cooperativa", "fecha", "codigo"]),
                  "pyg": (cargar_pyg()[0], ["cooperativa", "fecha", "codigo"])}
        for base, (crudo, clave) in crudas.items():
            for nombre, f in {"todo": self.todo, "seg": self.todo.con(segmentos=("SEGMENTO 2",)),
                              "dos": self.todo.con(segmentos=("SEGMENTO 1", "SEGMENTO 3"), calidad="arrastrada")}.items():
                with self.subTest(base=base, filtro=nombre):
                    d = datos_filtrados(base, f)
                    self.assertFalse(d.duplicated(clave).any(), f"{base}: duplicados tras el filtro")
                    self.assertLessEqual(len(d), len(crudo))
            # sin restricciones el filtro no pierde ni gana filas (salvo el recorte de período, que aquí es total)
            self.assertEqual(len(datos_filtrados(base, self.todo)), len(crudo), f"{base}: el filtro «todo» alteró el número de filas")


# --------------------------------------------------------------------------------------------------
def _inicio_en_subproceso(segmentos=(), entidades=(), calidad="todas") -> str:
    """`Inicio.py` usa `st.page_link`, que necesita el registro de páginas de un proceso limpio (igual que test_smoke_pages)."""
    codigo = f"""
import warnings, logging; warnings.filterwarnings('ignore'); logging.disable(logging.CRITICAL)
from streamlit.testing.v1 import AppTest
at = AppTest.from_file("Inicio.py", default_timeout=400)
at.session_state["sps_f_segmentos"] = {list(segmentos)!r}
at.session_state["sps_f_entidades"] = {list(entidades)!r}
at.session_state["sps_f_calidad"] = {calidad!r}
at.run()
print("EXCEPTION:", at.exception[0].value) if at.exception else print("OK")
print("BANDA:", any("Selección activa" in m.value for m in at.markdown))
"""
    r = subprocess.run([sys.executable, "-c", codigo], cwd=REPO, capture_output=True, text=True, timeout=500)
    return r.stdout + r.stderr[-300:]


class TestTodasLasPaginas(unittest.TestCase):
    """Cada página (incluido Inicio) carga sin excepción con una selección combinada y con una sola entidad."""

    @classmethod
    def setUpClass(cls):
        cls.dim = cargar_dim_observaciones()

    def _ejecuta(self, pagina, **estado):
        at = _app(pagina); at.run()
        self.assertFalse(at.exception, f"{pagina} (sin filtros): {[str(e.value)[:200] for e in at.exception]}")
        return at

    def test_combinacion_segmentos_y_calidad(self):
        salida = _inicio_en_subproceso(("SEGMENTO 2", "SEGMENTO 3"), calidad="oficial")
        self.assertIn("OK", salida, salida)
        self.assertIn("BANDA: True", salida, salida)
        for pagina in TODAS_LAS_PAGINAS:
            if pagina == "Inicio.py":
                continue
            with self.subTest(pagina=pagina):
                at = self._ejecuta(pagina)
                at.sidebar.multiselect(key="_w_segmentos").set_value(["SEGMENTO 2", "SEGMENTO 3"]).run()
                self.assertFalse(at.exception, f"{pagina} con S2+S3: {[str(e.value)[:200] for e in at.exception]}")
                at.sidebar.selectbox(key="_w_calidad").set_value("oficial").run()
                self.assertFalse(at.exception, f"{pagina} con S2+S3 y calidad oficial: {[str(e.value)[:200] for e in at.exception]}")

    def test_una_sola_entidad(self):
        e = fa.entidades_disponibles(self.dim, _total().con(segmentos=("SEGMENTO 1",)))[0]
        salida = _inicio_en_subproceso(entidades=(e,))
        self.assertIn("OK", salida, salida)
        for pagina in TODAS_LAS_PAGINAS:
            if pagina == "Inicio.py":
                continue
            with self.subTest(pagina=pagina):
                at = self._ejecuta(pagina)
                at.sidebar.multiselect(key="_w_entidades").set_value([e]).run()
                self.assertFalse(at.exception, f"{pagina} con una entidad: {[str(x.value)[:200] for x in at.exception]}")

    def test_cada_pagina_muestra_el_resumen_de_la_seleccion(self):
        """Indicador visible de la población: período, segmentos, entidades, observaciones, corte y calidad."""
        for pagina in TODAS_LAS_PAGINAS:
            if pagina == "Inicio.py":
                continue   # su banda se verifica en test_combinacion_segmentos_y_calidad (subproceso)
            with self.subTest(pagina=pagina):
                at = self._ejecuta(pagina)
                at.sidebar.multiselect(key="_w_segmentos").set_value(["SEGMENTO 3"]).run()
                bandas = " ".join(m.value for m in at.markdown if "Selección activa" in m.value)
                for etiqueta in ("Período", "Segmentos", "Entidades", "Observaciones", "Corte de datos"):
                    self.assertIn(etiqueta, bandas, f"{pagina}: falta «{etiqueta}» en el resumen de la selección")
                self.assertIn("SEGMENTO 3", bandas)


if __name__ == "__main__":
    unittest.main()
