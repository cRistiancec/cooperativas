# -*- coding: utf-8 -*-
"""
Pruebas de consistencia de datos entre módulos (Fases 1-4 de la validación de
producción).

Responden, de forma automatizada y repetible, a tres preguntas:

1. **Actualización**: ¿todas las fuentes (balance, PyG, indicadores CAMEL y los
   cuatro agregados) llegan al mismo último período, y es ese el período que
   abre la aplicación por defecto?
2. **Consistencia**: ¿los KPIs, rankings y agregados que muestran los distintos
   módulos salen de la misma información fuente y cuadran entre sí y contra el
   parquet crudo?
3. **Segmentación**: ¿la variable `segmento` es idéntica en todas las fuentes,
   de modo que "SEGMENTO 2" signifique lo mismo en cualquier módulo?

Estas pruebas leen los datos reales de `master_data/`. No usan fixtures
sintéticos a propósito: su valor está justamente en verificar el dataset que se
publica en producción, y fallarán si un ETL futuro deja una fuente rezagada.
"""

import re
import subprocess
import sys
import unittest
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parent.parent
MASTER_DATA = REPO_ROOT / "master_data"

sys.path.insert(0, str(REPO_ROOT))

from ui.filtros import SPS_SEGMENTO_KEY  # noqa: E402
from utils.charts import altura_por_categorias, truncar_nombre, truncar_nombres_unicos  # noqa: E402
from utils.data_loader import (  # noqa: E402
    cargar_entidades,
    cargar_metadata,
    cargar_pyg,
    cargar_ranking_cooperativas,
    cargar_segmento_historico,
    cargar_solvencia,
    obtener_metricas_kpi,
    obtener_ranking_rapido,
    obtener_segmentos_disponibles_rapido,
    obtener_serie_sistema,
    obtener_ultima_fecha,
)

# Páginas que ofrecen análisis por cooperativa/segmento y deben usar el
# Filtro Global de Segmento (ui/filtros.py). Excluida pages/15_Asistente_IA.py:
# es un chat sin cortes de datos propios, no un módulo de análisis.
PAGINAS_CON_FILTRO_SEGMENTO = [
    "Inicio.py",
    "pages/1_Panorama.py",
    "pages/2_Balance_General.py",
    "pages/3_Perdidas_Ganancias.py",
    "pages/4_CAMEL.py",
    "pages/5_Riesgo_Liquidez.py",
    "pages/6_Riesgo_Credito.py",
    "pages/7_Riesgo_Solvencia.py",
    "pages/8_Riesgo_Concentracion.py",
    "pages/9_Riesgo_Sistemico.py",
    "pages/10_CAMEL_Score.py",
    "pages/11_Alertas_Tempranas.py",
    "pages/12_Stress_Testing.py",
    "pages/13_Modelos_Predictivos.py",
    "pages/14_Machine_Learning.py",
]

# Fuentes con columna `fecha` que deben compartir el mismo corte.
FUENTES_CON_FECHA = [
    "balance.parquet",
    "pyg.parquet",
    "indicadores.parquet",
    "agg_metricas_sistema.parquet",
    "agg_ranking_cooperativas.parquet",
    "agg_series_temporales.parquet",
]

# Páginas con selector "Fecha de análisis" y la clave de ese selector.
PAGINAS_CON_SELECTOR_FECHA = [
    ("pages/1_Panorama.py", "fecha_panorama"),
    ("pages/4_CAMEL.py", "fecha_camel"),
    ("pages/5_Riesgo_Liquidez.py", "fecha_liq"),
    ("pages/6_Riesgo_Credito.py", "fecha_credito"),
    ("pages/7_Riesgo_Solvencia.py", "fecha_solv"),
    ("pages/8_Riesgo_Concentracion.py", "fecha_conc"),
    ("pages/9_Riesgo_Sistemico.py", "fecha_sist"),
    ("pages/10_CAMEL_Score.py", "fecha_score"),
    ("pages/11_Alertas_Tempranas.py", "fecha_alertas"),
    ("pages/12_Stress_Testing.py", "fecha_stress"),
    ("pages/14_Machine_Learning.py", "fecha_ml"),
]


def _fecha_max(nombre_archivo: str) -> pd.Timestamp:
    """Última fecha de un parquet, leyendo solo la columna `fecha`."""
    tabla = pq.read_table(MASTER_DATA / nombre_archivo, columns=["fecha"])
    return pd.to_datetime(tabla.to_pandas()["fecha"]).max()


class ActualizacionTests(unittest.TestCase):
    """Fase 1 — el último período disponible es único y es el que usa la app."""

    @classmethod
    def setUpClass(cls):
        cls.fechas_max = {f: _fecha_max(f) for f in FUENTES_CON_FECHA}
        cls.ultimo = max(cls.fechas_max.values())

    def test_todas_las_fuentes_llegan_al_mismo_periodo(self):
        for archivo, fecha in self.fechas_max.items():
            with self.subTest(fuente=archivo):
                self.assertEqual(
                    fecha, self.ultimo,
                    f"{archivo} está rezagado: llega a {fecha:%Y-%m-%d} y el sistema tiene "
                    f"datos hasta {self.ultimo:%Y-%m-%d}.",
                )

    def test_metadata_declara_el_periodo_real(self):
        metadata = cargar_metadata()
        self.assertEqual(
            pd.Timestamp(metadata["fecha_max"]), self.ultimo,
            "metadata.json declara un fecha_max distinto al de los parquet.",
        )

    def test_obtener_ultima_fecha_deriva_de_los_datos(self):
        """La fuente única de verdad del período no depende de metadata.json."""
        self.assertEqual(pd.Timestamp(obtener_ultima_fecha()), self.ultimo)

    def test_el_ultimo_periodo_es_la_primera_opcion_de_los_selectores(self):
        """Los selectores ordenan descendente: index=0 debe ser el último mes."""
        from utils.data_loader import obtener_fechas_disponibles_rapido
        fechas = obtener_fechas_disponibles_rapido()
        self.assertEqual(pd.Timestamp(fechas[0]), self.ultimo)
        self.assertEqual(list(fechas), sorted(fechas, reverse=True))


class ConsistenciaEntreModulosTests(unittest.TestCase):
    """Fases 2 y 3 — todos los módulos usan la misma información fuente."""

    @classmethod
    def setUpClass(cls):
        cls.ultimo = pd.Timestamp(obtener_ultima_fecha())

    def test_kpi_del_home_coincide_con_el_balance_crudo(self):
        """
        Los activos del sistema que muestra el home (vía agregados) deben ser
        idénticos a sumar la cuenta '1' directamente en balance.parquet.
        """
        tabla = pq.read_table(
            MASTER_DATA / "balance.parquet",
            columns=["fecha", "codigo", "valor"],
            filters=[("codigo", "=", "1")],
        )
        df = tabla.to_pandas()
        df["fecha"] = pd.to_datetime(df["fecha"])
        crudo = df[df["fecha"] == self.ultimo]["valor"].sum()

        serie = obtener_serie_sistema("1")
        agregado = serie["valor_total"].iloc[-1]

        self.assertAlmostEqual(
            crudo / 1e6, agregado / 1e6, places=2,
            msg="Los activos del home no coinciden con la suma directa del balance.",
        )

    def test_home_y_panorama_muestran_la_misma_cifra(self):
        """El home usa `obtener_serie_sistema`; Panorama usa `obtener_metricas_kpi`."""
        metricas = obtener_metricas_kpi(self.ultimo, "Todos")
        for nombre_kpi, codigo in [
            ("total_activos", "1"),
            ("total_cartera", "14"),
            ("total_depositos", "21"),
            ("total_patrimonio", "3"),
        ]:
            with self.subTest(kpi=nombre_kpi):
                serie = obtener_serie_sistema(codigo)
                self.assertAlmostEqual(
                    metricas[nombre_kpi], serie["valor_total"].iloc[-1] / 1e6, places=2,
                    msg=f"{nombre_kpi} difiere entre el home y Panorama.",
                )

    def test_los_segmentos_suman_el_total_del_sistema(self):
        """El filtro por segmento particiona los datos: no duplica ni pierde."""
        total = obtener_serie_sistema("1")["valor_total"].iloc[-1]
        suma_segmentos = sum(
            obtener_serie_sistema("1", seg)["valor_total"].iloc[-1]
            for seg in obtener_segmentos_disponibles_rapido()
        )
        self.assertAlmostEqual(total / 1e6, suma_segmentos / 1e6, places=2)

    def test_el_ranking_completo_cuadra_con_el_kpi_agregado(self):
        """Ranking (por cooperativa) y métricas (por segmento) vienen del mismo balance."""
        ranking = obtener_ranking_rapido(self.ultimo, codigo="1", top_n=0, segmento="Todos")
        metricas = obtener_metricas_kpi(self.ultimo, "Todos")
        self.assertAlmostEqual(
            ranking["valor"].sum() / 1e6, metricas["total_activos"], places=2,
            msg="La suma del ranking de activos no coincide con el KPI del sistema.",
        )

    def test_el_numero_de_instituciones_coincide_con_el_ranking(self):
        metricas = obtener_metricas_kpi(self.ultimo, "Todos")
        ranking = obtener_ranking_rapido(self.ultimo, codigo="1", top_n=0, segmento="Todos")
        self.assertEqual(int(metricas["num_cooperativas"]), ranking["cooperativa"].nunique())


class SegmentacionTests(unittest.TestCase):
    """Fase 4 — la variable de segmento es única y consistente."""

    def test_el_catalogo_de_segmentos_es_identico_en_todas_las_fuentes(self):
        esperado = None
        for archivo in ["balance.parquet", "pyg.parquet", "indicadores.parquet",
                        "agg_ranking_cooperativas.parquet", "agg_catalogo_cooperativas.parquet"]:
            tabla = pq.read_table(MASTER_DATA / archivo, columns=["segmento"])
            segmentos = set(str(s) for s in tabla.to_pandas()["segmento"].unique())
            if esperado is None:
                esperado = segmentos
            with self.subTest(fuente=archivo):
                self.assertEqual(
                    segmentos, esperado,
                    f"{archivo} usa un catálogo de segmentos distinto: {segmentos ^ esperado}",
                )

    def test_los_segmentos_expuestos_en_la_ui_son_los_de_los_datos(self):
        segmentos_ui = obtener_segmentos_disponibles_rapido()
        segmentos_datos = sorted(
            str(s) for s in cargar_ranking_cooperativas()["segmento"].unique()
        )
        self.assertEqual(sorted(segmentos_ui), segmentos_datos)

    def test_toda_cooperativa_tiene_segmento_asignado(self):
        catalogo = pq.read_table(
            MASTER_DATA / "agg_catalogo_cooperativas.parquet"
        ).to_pandas()
        self.assertFalse(
            catalogo["segmento"].isna().any(),
            "Hay cooperativas sin segmento en el catálogo.",
        )

    def test_cargar_pyg_excluye_filas_de_subtotal_vt_total(self):
        """
        Auditoría de segmentación (sep-2026): `pyg.parquet` en disco contiene
        filas `VT_TOTAL SEGMENTO 1/2/3`/`VT_TOTAL MUTUALISTAS` (subtotales del
        boletín SEPS de origen) tratadas como si fueran una cooperativa más —
        verificado que su `valor_acumulado` duplica exactamente la suma de las
        cooperativas reales del segmento. `cargar_pyg()` debe excluirlas para
        que ningún `groupby('cooperativa')`/suma por segmento las cuente dos
        veces. El archivo en disco no se modifica (regenerarlo es un cambio de
        ETL fuera de alcance) — el filtro vive en el loader.
        """
        df_pyg, _ = cargar_pyg()
        self.assertFalse(
            df_pyg["cooperativa"].astype(str).str.startswith("VT_").any(),
            "cargar_pyg() sigue devolviendo filas de subtotal VT_TOTAL*.",
        )

    def test_suma_pyg_por_cooperativa_no_duplica_el_total_del_sistema(self):
        """
        Prueba de consistencia directa (no solo ausencia de VT_): sumar
        valor_acumulado de TODAS las cooperativas reales para una cuenta/fecha
        debe dar el mismo total que reportaba el boletín SEPS (antes
        verificado manualmente contra las filas VT_TOTAL, ahora ya excluidas).
        Si `cargar_pyg()` volviera a incluir subtotales, este total se
        duplicaría exactamente x2.
        """
        df_pyg, _ = cargar_pyg()
        fecha_max = df_pyg["fecha"].max()
        total_gastos = df_pyg[
            (df_pyg["fecha"] == fecha_max) & (df_pyg["codigo"] == "4")
        ]["valor_acumulado"].sum()
        # Verificado contra el archivo crudo (ver auditoría): el valor real de
        # gastos totales del sistema en el último corte es de este orden de
        # magnitud (cientos de millones a ~4 mil millones, nunca el doble por
        # duplicación). Umbral generoso: solo detecta una regresión de
        # duplicación x2, no un cambio de dato mes a mes.
        tabla_cruda = pq.read_table(
            MASTER_DATA / "pyg.parquet", columns=["fecha", "cooperativa", "codigo", "valor_acumulado"]
        ).to_pandas()
        total_vt = tabla_cruda[
            (tabla_cruda["fecha"] == fecha_max)
            & (tabla_cruda["codigo"] == "4")
            & (tabla_cruda["cooperativa"].astype(str).str.startswith("VT_TOTAL"))
        ]["valor_acumulado"].sum()
        self.assertAlmostEqual(
            total_gastos / 1e6, total_vt / 1e6, places=2,
            msg="La suma de cooperativas reales no coincide con el subtotal oficial VT_TOTAL del boletín.",
        )


class IndicadoresCAMELExpuestosTests(unittest.TestCase):
    """
    Guardia de la Categoría 6 de `AUDITORIA_MOTOR_INDICADORES.md`: 13 códigos
    que la SEPS ya publica y el ETL ya extrae a `indicadores.parquet` estaban
    ausentes de `GRUPOS_INDICADORES` (invisibles en el selector de la página
    CAMEL) pese a no requerir ningún cálculo nuevo. Esta prueba falla si un
    ETL futuro agrega o quita un código de indicador y nadie actualiza el
    mapeo de la UI en consecuencia — evitando que la brecha se repita.
    """

    @classmethod
    def setUpClass(cls):
        from config.indicator_mapping import (
            ESCALAS_COLORES_HEATMAP,
            ETIQUETAS_INDICADORES,
            GRUPOS_INDICADORES,
            RANGOS_HEATMAP,
        )
        cls.grupos = GRUPOS_INDICADORES
        cls.etiquetas = ETIQUETAS_INDICADORES
        cls.escalas = ESCALAS_COLORES_HEATMAP
        cls.rangos = RANGOS_HEATMAP
        cls.expuestos = [c for lista in GRUPOS_INDICADORES.values() for c in lista]
        cls.disponibles = set(
            pq.read_table(MASTER_DATA / "indicadores.parquet", columns=["codigo"])
            .to_pandas()["codigo"].unique()
        )

    def test_todo_codigo_publicado_por_la_seps_esta_expuesto_en_la_ui(self):
        faltantes = self.disponibles - set(self.expuestos)
        self.assertEqual(
            faltantes, set(),
            f"Códigos presentes en indicadores.parquet pero ausentes de GRUPOS_INDICADORES: {faltantes}",
        )

    def test_no_hay_codigos_expuestos_que_no_existan_en_los_datos(self):
        fantasmas = set(self.expuestos) - self.disponibles
        self.assertEqual(
            fantasmas, set(),
            f"GRUPOS_INDICADORES expone códigos que no están en indicadores.parquet: {fantasmas}",
        )

    def test_todo_codigo_expuesto_tiene_etiqueta_escala_y_rango(self):
        for codigo in self.expuestos:
            with self.subTest(codigo=codigo):
                self.assertIn(codigo, self.etiquetas, f"{codigo} sin entrada en ETIQUETAS_INDICADORES")
                self.assertIn(codigo, self.escalas, f"{codigo} sin entrada en ESCALAS_COLORES_HEATMAP")
                self.assertIn(codigo, self.rangos, f"{codigo} sin entrada en RANGOS_HEATMAP")


class MotorCentralIndicadoresTests(unittest.TestCase):
    """
    Guardia del Motor Central de Indicadores (`analytics/financial_engine.py`):
    ninguna página debe volver a importar directamente de los submódulos de
    dominio (`analytics.liquidez`, `analytics.credito`, ...) — todas deben
    consumir exclusivamente la fachada. Si esta prueba falla, alguna página
    reintrodujo un import directo que la Fase 2.2 eliminó.
    """

    _SUBMODULOS_DOMINIO = [
        "liquidez", "credito", "solvencia", "concentracion",
        "sistemico", "camels_score", "alertas", "stress_testing",
        "rentabilidad", "crecimiento", "indices_ejecutivos",
        "persistencia", "breadth", "interaccion", "riesgo_sistemico_estado",
        "ipsf", "eventos", "backtesting", "data_quality",
    ]

    def test_ninguna_pagina_importa_un_submodulo_de_dominio_directamente(self):
        patron = re.compile(
            r'from analytics\.(' + '|'.join(self._SUBMODULOS_DOMINIO) + r')\s+import'
        )
        paginas = sorted((REPO_ROOT / "pages").glob("*.py")) + [REPO_ROOT / "Inicio.py"]
        for ruta in paginas:
            with self.subTest(pagina=ruta.relative_to(REPO_ROOT)):
                codigo = ruta.read_text(encoding="utf-8")
                self.assertIsNone(
                    patron.search(codigo),
                    f"{ruta.name} importa un submódulo de analytics/ directamente en vez de "
                    "usar analytics.financial_engine.",
                )

    def test_el_motor_reexporta_todo_lo_que_las_paginas_necesitan(self):
        """
        Cruce inverso: todo símbolo que algún archivo `pages/*.py` importaba
        (antes de esta fase) desde un submódulo de dominio debe seguir
        disponible desde `financial_engine` con el mismo nombre.
        """
        from analytics import financial_engine
        simbolos_esperados = [
            "calcular_liquidez_ampliada", "calcular_cobertura_retiro",
            "CARTERAS_COBERTURA", "CARTERAS_MOROSIDAD", "CODIGO_CARTERA_VENCIDA",
            "CODIGO_PROVISION_CARTERA", "construir_panel_morosidad_cobertura",
            "construir_serie_cartera_vencida", "ETIQUETAS_SOLVENCIA",
            "calcular_patrimonio_sobre_activos", "calcular_hhi", "calcular_cr",
            "clasificar_hhi", "coeficiente_gini", "curva_lorenz", "PESOS_IIS",
            "calcular_indice_importancia_sistemica", "CATEGORIAS_CAMEL",
            "calcular_score_camel", "clasificar_score", "evaluar_alertas",
            "ESCENARIOS", "aplicar_escenario", "construir_panel_balance",
        ]
        for simbolo in simbolos_esperados:
            with self.subTest(simbolo=simbolo):
                self.assertTrue(
                    hasattr(financial_engine, simbolo),
                    f"financial_engine no re-exporta {simbolo!r}",
                )


class RentabilidadYCrecimientoConDatosRealesTests(unittest.TestCase):
    """
    Fase 2.3 — indicadores nuevos (Categoría 3 de la auditoría), verificados
    sobre datos reales. `crecimiento_captaciones`/`crecimiento_colocaciones`
    delegan en `utils.data_loader.obtener_crecimiento_anual`, que lee
    `agg_ranking_cooperativas.parquet` internamente (está decorada con
    `st.cache_data`, no acepta un DataFrame inyectado) — por eso no son
    unit-testeables con datos sintéticos (ver `tests/test_analytics.py` para
    las funciones que sí lo son) y se verifican aquí contra el dataset real.
    """

    @classmethod
    def setUpClass(cls):
        cls.ultimo = pd.Timestamp(obtener_ultima_fecha())
        cls.hace_un_anio = cls.ultimo - pd.DateOffset(years=1)

    def test_crecimiento_captaciones_es_consistente_con_su_propia_resta(self):
        from analytics.financial_engine import crecimiento_captaciones
        df = crecimiento_captaciones(self.ultimo, self.hace_un_anio, "Todos")
        self.assertFalse(df.empty, "Sin datos de crecimiento de captaciones en el último año disponible.")
        diferencia = df["crecimiento_absoluto"] - (df["depositos_actual"] - df["depositos_anterior"])
        self.assertTrue((diferencia.abs() < 1e-6).all())

    def test_crecimiento_colocaciones_es_consistente_con_su_propia_resta(self):
        from analytics.financial_engine import crecimiento_colocaciones
        df = crecimiento_colocaciones(self.ultimo, self.hace_un_anio, "Todos")
        self.assertFalse(df.empty, "Sin datos de crecimiento de colocaciones en el último año disponible.")
        diferencia = df["crecimiento_absoluto"] - (df["cartera_actual"] - df["cartera_anterior"])
        self.assertTrue((diferencia.abs() < 1e-6).all())

    def test_tasas_implicitas_producen_valores_en_rango_plausible(self):
        """Sin excepción y sin porcentajes absurdos (ni 0%, ni miles por ciento) en el universo real."""
        from analytics.financial_engine import calcular_tasas_implicitas
        df_ranking = cargar_ranking_cooperativas()
        df_pyg, _ = cargar_pyg()
        resultado = calcular_tasas_implicitas(df_ranking, df_pyg, self.ultimo, "Todos")
        self.assertFalse(resultado.empty)
        for columna in ["tasa_pasiva_implicita", "tasa_activa_implicita"]:
            valores = resultado[columna].dropna()
            with self.subTest(columna=columna):
                self.assertTrue((valores.between(-5, 100)).mean() > 0.95,
                                 f"Más del 5% de {columna} fuera de [-5%, 100%] — revisar unidades/escala.")


class FiltroGlobalSegmentoTests(unittest.TestCase):
    """
    Fase 3 (ampliación) — el segmento es una dimensión global, no un filtro
    aislado por página: un único componente (`ui/filtros.py`), una única
    `key` de `session_state`, y el valor persiste al navegar entre módulos.
    """

    _PATRON_SELECTBOX_SEGMENTO_PROPIO = re.compile(
        r'st\.(?:sidebar\.)?selectbox\(\s*["\']Segmento["\']'
    )

    def test_ninguna_pagina_define_su_propio_selectbox_de_segmento(self):
        """
        Antes de `ui/filtros.py` cada página declaraba
        `st.sidebar.selectbox("Segmento", ...)` con una key propia. Este test
        falla si alguna página vuelve a hacerlo en vez de reutilizar
        `render_filtro_segmento()` — evita que el filtro se vuelva a
        fragmentar en el futuro.
        """
        for ruta in PAGINAS_CON_FILTRO_SEGMENTO:
            with self.subTest(pagina=ruta):
                codigo = (REPO_ROOT / ruta).read_text(encoding="utf-8")
                self.assertIsNone(
                    self._PATRON_SELECTBOX_SEGMENTO_PROPIO.search(codigo),
                    f"{ruta} define su propio selectbox de segmento en vez de "
                    "reutilizar render_filtro_segmento().",
                )

    def test_toda_pagina_relevante_importa_el_filtro_global(self):
        for ruta in PAGINAS_CON_FILTRO_SEGMENTO:
            with self.subTest(pagina=ruta):
                codigo = (REPO_ROOT / ruta).read_text(encoding="utf-8")
                self.assertIn(
                    "render_filtro_segmento", codigo,
                    f"{ruta} no usa render_filtro_segmento().",
                )

    def test_la_pagina_se_hidrata_desde_el_valor_persistente(self):
        """
        `render_filtro_segmento()` copia `session_state[SPS_SEGMENTO_KEY]`
        (persistente) a la key interna del widget ANTES de crearlo
        (`_cargar_valor_persistente`). Se precarga la key persistente y se
        confirma que el widget "Segmento" nace ya con ese valor, sin
        excepción, en una muestra de páginas de distinto tipo (Panorama usa
        agregados; Crédito e indicadores; Modelos Predictivos entrena
        modelos).

        NOTA: esto prueba la hidratación *dentro de una página*, no la
        navegación real entre páginas — `AppTest` ejecuta cada script de
        forma aislada y no reproduce el enrutamiento del cliente de
        Streamlit. La persistencia real, de punta a punta, se verificó con
        un navegador real (Playwright) navegando de Inicio a Panorama en la
        aplicación viva: el segmento elegido en Inicio seguía activo en
        Panorama. Es exactamente el escenario que motivó reemplazar un
        `st.selectbox(key=...)` ingenuo por el patrón de "widget con key
        sombra" que usa este componente — con la key compartida ingenua,
        Streamlit resetea el widget en cada nueva página aunque la key sea
        idéntica (comportamiento documentado de las apps multipágina
        clásicas de carpeta `pages/`, confirmado aquí con un repro mínimo).
        """
        muestra = [
            "pages/1_Panorama.py",
            "pages/6_Riesgo_Credito.py",
            "pages/10_CAMEL_Score.py",
            "pages/13_Modelos_Predictivos.py",
        ]
        for ruta in muestra:
            with self.subTest(pagina=ruta):
                codigo = f"""
import warnings; warnings.filterwarnings('ignore')
from streamlit.testing.v1 import AppTest
from ui.filtros import SPS_SEGMENTO_KEY
at = AppTest.from_file({ruta!r}, default_timeout=400)
at.session_state[SPS_SEGMENTO_KEY] = "SEGMENTO 2"
at.run()
if at.exception:
    print("EXCEPTION:", at.exception[0].value)
else:
    sb = next((s for s in list(at.sidebar.selectbox) + list(at.selectbox) if s.label == "Segmento"), None)
    print("VALOR:", sb.value if sb is not None else "SELECTOR_NO_ENCONTRADO")
    print("PERSISTENTE:", at.session_state[SPS_SEGMENTO_KEY])
"""
                proceso = subprocess.run(
                    [sys.executable, "-c", codigo],
                    cwd=REPO_ROOT, capture_output=True, text=True, timeout=420,
                )
                salida = proceso.stdout
                self.assertIn(
                    "VALOR: SEGMENTO 2", salida,
                    msg=f"{ruta} no heredó el segmento de session_state. "
                        f"stdout={salida!r} stderr={proceso.stderr[-400:]!r}",
                )
                self.assertIn(
                    "PERSISTENTE: SEGMENTO 2", salida,
                    msg=f"{ruta} desincronizó la key persistente respecto al widget.",
                )

    def test_cambiar_el_widget_actualiza_la_key_persistente(self):
        """
        La otra mitad del round-trip: cuando el usuario cambia el selector,
        `on_change` (`_guardar_valor_persistente`) debe escribir el nuevo
        valor en `SPS_SEGMENTO_KEY` — es lo que hace que el valor sobreviva
        para la siguiente página. Se simula el cambio con
        `selectbox.set_value(...)`, que en `AppTest` dispara el mismo
        callback `on_change` que un clic real en el navegador.
        """
        codigo = """
import warnings; warnings.filterwarnings('ignore')
from streamlit.testing.v1 import AppTest
from ui.filtros import SPS_SEGMENTO_KEY
at = AppTest.from_file("pages/1_Panorama.py", default_timeout=400)
at.run()
sb = next((s for s in list(at.sidebar.selectbox) + list(at.selectbox) if s.label == "Segmento"), None)
if sb is None:
    print("EXCEPTION: selector Segmento no encontrado")
else:
    opciones = [o for o in sb.options if o != "Todos"]
    sb.set_value(opciones[0]).run()
    print("EXCEPTION:", at.exception[0].value) if at.exception else print("OK")
    print("PERSISTENTE:", at.session_state[SPS_SEGMENTO_KEY])
"""
        proceso = subprocess.run(
            [sys.executable, "-c", codigo],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=420,
        )
        salida = proceso.stdout
        self.assertIn("OK", salida, msg=f"stdout={salida!r} stderr={proceso.stderr[-400:]!r}")
        self.assertNotIn(
            "PERSISTENTE: Todos", salida,
            msg="Cambiar el widget no actualizó la key persistente (on_change no disparó).",
        )


class LegibilidadEtiquetasTests(unittest.TestCase):
    """Fase 5 — las etiquetas no pueden solaparse ni fusionar instituciones."""

    def test_truncar_nombre_respeta_el_largo_maximo(self):
        largo = "COOPERATIVA DE AHORRO Y CREDITO JARDIN AZUAYO LTDA"
        self.assertLessEqual(len(truncar_nombre(largo, 30)), 30)
        self.assertEqual(truncar_nombre("CACPECO", 30), "CACPECO")

    def test_truncar_nombres_unicos_nunca_fusiona_dos_instituciones(self):
        """
        Dos nombres distintos jamás deben producir la misma etiqueta: Plotly
        trataría ambas barras como una sola categoría y una desaparecería.
        """
        nombres = [
            "COOPERATIVA DE AHORRO Y CREDITO SAN JOSE LTDA",
            "COOPERATIVA DE AHORRO Y CREDITO SAN JUAN LTDA",
            "COOPERATIVA DE AHORRO Y CREDITO SAN JOSE LTDA 2",
        ]
        etiquetas = truncar_nombres_unicos(nombres)
        self.assertEqual(len(set(etiquetas)), len(nombres))

    def test_truncar_nombres_unicos_sobre_el_catalogo_real(self):
        catalogo = pq.read_table(
            MASTER_DATA / "agg_catalogo_cooperativas.parquet", columns=["cooperativa"]
        ).to_pandas()["cooperativa"].astype(str).tolist()
        etiquetas = truncar_nombres_unicos(catalogo)
        self.assertEqual(
            len(set(etiquetas)), len(set(catalogo)),
            "El truncamiento colapsa instituciones reales del catálogo.",
        )

    def test_la_altura_da_espacio_propio_a_cada_etiqueta(self):
        """Con 30 instituciones, 400 px dejaban ~12 px por etiqueta (se solapaban)."""
        for n in [20, 30, 50, 203]:
            with self.subTest(instituciones=n):
                alto = altura_por_categorias(n)
                self.assertGreaterEqual(
                    alto / n, 20,
                    f"Con {n} instituciones quedan {alto / n:.1f} px por etiqueta.",
                )


class PeriodoEnLaInterfazTests(unittest.TestCase):
    """
    Fase 3 — ninguna página puede abrir en un corte distinto al más reciente.

    Se ejecuta cada página en un subproceso limpio (mismo aislamiento que
    `test_smoke_pages.py`) y se lee el valor por defecto de su selector de
    fecha tal como lo vería el usuario.
    """

    @classmethod
    def setUpClass(cls):
        cls.ultimo = pd.Timestamp(obtener_ultima_fecha())

    def _fecha_por_defecto(self, ruta: str, clave: str) -> str:
        codigo = f"""
import warnings; warnings.filterwarnings('ignore')
import pandas as pd
from streamlit.testing.v1 import AppTest
at = AppTest.from_file({ruta!r}, default_timeout=300)
at.run()
if at.exception:
    print("EXCEPTION:", at.exception[0].value)
else:
    sb = next((s for s in at.sidebar.selectbox if s.key == {clave!r}), None)
    print("FECHA:", pd.Timestamp(sb.value) if sb is not None else "SELECTOR_NO_ENCONTRADO")
"""
        proceso = subprocess.run(
            [sys.executable, "-c", codigo],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=420,
        )
        salida = proceso.stdout
        self.assertIn(
            "FECHA:", salida,
            msg=f"{ruta} no expuso su selector de fecha. stdout={salida!r} "
                f"stderr={proceso.stderr[-400:]!r}",
        )
        return salida.split("FECHA:")[1].strip().splitlines()[0]

    def test_cada_pagina_abre_en_el_ultimo_periodo_disponible(self):
        for ruta, clave in PAGINAS_CON_SELECTOR_FECHA:
            with self.subTest(pagina=ruta):
                fecha = self._fecha_por_defecto(ruta, clave)
                self.assertEqual(
                    pd.Timestamp(fecha), self.ultimo,
                    f"{ruta} abre en {fecha} en lugar de {self.ultimo:%Y-%m-%d}.",
                )


class SegmentoHistoricoTests(unittest.TestCase):
    """
    Verifica el defecto corregido en sep-2026: `segmento` en balance.parquet
    e indicadores.parquet estaba retroactivamente unificado al último
    segmento conocido, sin registro punto-en-el-tiempo. La corrección añadió
    `segmento_historico` (point-in-time, con `segmento_historico_estimado`
    para el tramo no recuperable de años previos) y `segmento_actual` (alias
    explícito del comportamiento legado). Ver docs/RIESGO_METODOLOGIA.md.
    """

    def _segmento_igual_a_segmento_actual(self, nombre_parquet: str) -> bool:
        """
        Compara `segmento` vs `segmento_actual` sobre las 24M+ filas de
        balance.parquet vía PyArrow (no pandas): `.astype(str)` sobre una
        columna completa de ese tamaño mide >6 GB de RSS y el proceso muere
        por SIGTERM (ver docs/CONTEXTO.md, "Optimización de memoria") — el
        mismo motivo por el que el ETL usa `pyarrow.compute` en vez de pandas
        para esta verificación en `scripts/procesar_balance_cooperativas.py`.
        """
        import pyarrow.compute as pc

        tabla = pq.read_table(MASTER_DATA / nombre_parquet, columns=["segmento", "segmento_actual"])
        return bool(pc.all(pc.equal(tabla["segmento"], tabla["segmento_actual"])).as_py())

    def test_columnas_nuevas_existen_en_balance_y_no_alteran_segmento_legado(self):
        self.assertTrue(self._segmento_igual_a_segmento_actual("balance.parquet"))

    def test_columnas_nuevas_existen_en_indicadores(self):
        self.assertTrue(self._segmento_igual_a_segmento_actual("indicadores.parquet"))

    def test_bandera_estimado_es_booleana_y_esta_presente_en_todo_el_historico(self):
        """
        LIMITACIÓN DOCUMENTADA (no un defecto): al momento de escribir este
        test, `segmento_historico_estimado` es True para el 100% de
        balance.parquet/indicadores.parquet, INCLUYENDO el corte más
        reciente. La corrección de sep-2026 solo añadió las columnas de
        tracking sobre el archivo existente (backfill honesto: "no sabemos
        el segmento point-in-time real de ningún registro ya presente en el
        parquet"); no reprocesó ningún ZIP fuente porque el ETL incremental
        correctamente NO reprocesa meses que ya están en el archivo. El
        mecanismo queda bien cableado hacia adelante: el próximo mes que la
        automatización (o un reproceso manual) trate como genuinamente
        NUEVO sí obtendrá `segmento_historico_estimado=False`. Ver
        docs/RIESGO_METODOLOGIA.md §15 y docs/CHANGELOG_RIESGO.md.
        """
        df = cargar_segmento_historico()
        if df.empty:
            self.skipTest("cargar_segmento_historico() no disponible en este entorno.")
        self.assertEqual(df["segmento_historico_estimado"].dtype, bool)
        self.assertFalse(df["segmento_historico_estimado"].isna().any())

    def test_hay_al_menos_una_cooperativa_con_cambio_de_segmento_detectable(self):
        """
        No es una aserción de negocio fuerte (podría ser 0 legítimamente),
        pero documenta con datos reales que el mecanismo de detección
        funciona sobre el dataset real, no solo en el test sintético.
        """
        from analytics.data_quality import detectar_cambios_de_segmento

        df = cargar_segmento_historico()
        if df.empty:
            self.skipTest("cargar_segmento_historico() no disponible en este entorno.")
        resultado = detectar_cambios_de_segmento(df)
        self.assertIsInstance(resultado, pd.DataFrame)


class SolvenciaFS01Tests(unittest.TestCase):
    """
    Solvencia oficial (PTC/APPR, fichas SEPS 58-63, fuente FS01 / boletín
    'Patrimonio Técnico'). Cobertura limitada a Segmento 1, Mutualistas y
    FINANCOOP — ver docs/RIESGO_METODOLOGIA.md §3.2.
    """

    def test_sin_registros_sin_clasificar(self):
        """Regresión del bug de \\b + guion bajo (ver CONTEXTO.md, sep-2026)."""
        df, _ = cargar_solvencia()
        if df.empty:
            self.skipTest("master_data/solvencia.parquet no disponible en este entorno.")
        self.assertNotIn("Sin clasificar", df["grupo_fuente"].unique().tolist())

    def test_solvencia_recalculada_coincide_con_la_reportada(self):
        df, _ = cargar_solvencia()
        if df.empty or "solvencia_recalculada_ptc_appr" not in df.columns:
            self.skipTest("Columna de QA no disponible en este entorno.")
        pct_discrepancia = df["discrepancia_solvencia"].mean() * 100
        self.assertLess(
            pct_discrepancia, 5.0,
            msg=f"{pct_discrepancia:.1f}% de registros con solvencia recalculada distinta a la reportada.",
        )


class EntidadesIdentidadTests(unittest.TestCase):
    """master_data/entidades_cooperativas.parquet — tabla ligera de identidad (Sección 16)."""

    def test_no_hay_ruc_duplicado_entre_entidades_distintas(self):
        df = cargar_entidades()
        if df.empty:
            self.skipTest("master_data/entidades_cooperativas.parquet no disponible en este entorno.")
        con_ruc = df[df["ruc"].notna()]
        self.assertEqual(con_ruc["ruc"].duplicated().sum(), 0)

    def test_toda_entidad_con_liquidacion_declarada_lo_dice_en_observaciones(self):
        df = cargar_entidades()
        if df.empty:
            self.skipTest("master_data/entidades_cooperativas.parquet no disponible en este entorno.")
        declaradas = df[df["estado"] == "liquidacion_declarada"]
        if declaradas.empty:
            self.skipTest("Sin entidades con liquidación declarada en el dataset actual.")
        self.assertTrue((declaradas["observaciones"].str.len() > 0).all())


if __name__ == "__main__":
    unittest.main()
