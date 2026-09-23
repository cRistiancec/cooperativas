# -*- coding: utf-8 -*-
"""
Pruebas de humo (smoke tests) de extremo a extremo sobre las páginas reales
de Streamlit, usando `streamlit.testing.v1.AppTest` — ejecuta el script tal
como lo haría el servidor de Streamlit (a diferencia de `py_compile`, que
solo verifica sintaxis).

Cobertura: arranque de Inicio, navegación de todos los módulos, presencia de
KPIs, interacción con filtros (segmento/fecha), render de gráficos Plotly, y
un umbral de tiempo de carga básico.

NOTA DE AISLAMIENTO: cada verificación de `AppTest` se ejecuta en un
subproceso Python nuevo (`_ejecutar_apptest`), no en el proceso del test
runner. Se comprobó empíricamente que reutilizar `AppTest.from_file()`
varias veces dentro del mismo proceso corrompe el registro interno de
páginas de Streamlit (`PagesManager`): `st.page_link()` funciona
perfectamente en algo ejecutado en aislamiento o en el servidor real
(verificado con `streamlit run` + `curl` durante la auditoría), pero falla
con `KeyError: 'url_pathname'` si se ejecuta después de otras instancias de
`AppTest` en el mismo proceso. Aislar por subproceso evita ese falso
positivo y valida el comportamiento real de la aplicación.

NOTA sobre `2_Balance_General.py`: se excluye deliberadamente de este
archivo. Esa página carga `balance.parquet` completo (24.17M filas) vía
`cargar_balance()`, con un pico medido de ~1.8-2 GB de RAM (ver
`AUDITORIA_FINAL.md`). Incluirla aquí haría la suite de pruebas dependiente
de la memoria disponible en el entorno de CI, en vez de validar lógica. Se
verifica por separado, manualmente, con monitoreo de memoria (ver
`ManualTecnico.md`).
"""

import subprocess
import sys
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
UMBRAL_SEGUNDOS = 60

# Páginas ligeras (agregados/indicadores, no balance.parquet completo).
PAGINAS_LIGERAS = [
    "Inicio.py",
    "pages/1_Panorama.py",
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
    "pages/15_Asistente_IA.py",
]


def _ejecutar_apptest(codigo_python: str, timeout: int = UMBRAL_SEGUNDOS + 30) -> subprocess.CompletedProcess:
    """Ejecuta un fragmento de código en un subproceso Python limpio, en la raíz del repo."""
    return subprocess.run(
        [sys.executable, "-c", codigo_python],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=timeout,
    )


def _codigo_carga_pagina(ruta: str) -> str:
    return f"""
import warnings; warnings.filterwarnings('ignore')
from streamlit.testing.v1 import AppTest
at = AppTest.from_file({ruta!r}, default_timeout={UMBRAL_SEGUNDOS})
at.run()
if at.exception:
    print("EXCEPTION:", at.exception[0].value)
else:
    print("OK")
"""


class NavegacionTests(unittest.TestCase):
    """Cada página del menú debe cargar sin excepciones (requisito: Navegación)."""

    def test_todas_las_paginas_ligeras_cargan_sin_excepciones(self):
        for ruta in PAGINAS_LIGERAS:
            with self.subTest(pagina=ruta):
                resultado = _ejecutar_apptest(_codigo_carga_pagina(ruta))
                self.assertIn(
                    "OK", resultado.stdout,
                    msg=f"{ruta} no cargó correctamente. stdout={resultado.stdout!r} stderr={resultado.stderr[-500:]!r}",
                )


class InicioTests(unittest.TestCase):
    """Requisito: Inicio — home carga, header, KPIs y accesos rápidos presentes."""

    def test_sin_excepciones_y_contenido_institucional(self):
        codigo = """
import warnings; warnings.filterwarnings('ignore')
from streamlit.testing.v1 import AppTest
at = AppTest.from_file("Inicio.py", default_timeout=%d)
at.run()
if at.exception:
    print("EXCEPTION:", at.exception[0].value)
else:
    texto = " ".join(m.value for m in at.markdown)
    print("OK")
    print("TIENE_TITULO:", "RADAR COOPERATIVO ECUADOR" in texto)
    print("N_PAGE_LINKS:", len(at.get("page_link")))
""" % UMBRAL_SEGUNDOS
        resultado = _ejecutar_apptest(codigo)
        self.assertIn("OK", resultado.stdout, msg=f"stdout={resultado.stdout!r} stderr={resultado.stderr[-500:]!r}")
        self.assertIn("TIENE_TITULO: True", resultado.stdout)
        n_links = int(resultado.stdout.split("N_PAGE_LINKS:")[1].strip().splitlines()[0])
        self.assertGreaterEqual(n_links, 14, "El home debería tener accesos rápidos a los 15 módulos")


class KPITests(unittest.TestCase):
    """Requisito: KPIs — Panorama debe exponer métricas del sistema."""

    def test_panorama_muestra_kpis(self):
        codigo = """
import warnings; warnings.filterwarnings('ignore')
from streamlit.testing.v1 import AppTest
at = AppTest.from_file("pages/1_Panorama.py", default_timeout=%d)
at.run()
if at.exception:
    print("EXCEPTION:", at.exception[0].value)
else:
    texto = " ".join(m.value for m in at.markdown)
    print("OK")
    print("TIENE_KPI:", any(p in texto for p in ["Total Activos", "Cartera de Créditos", "Depósitos"]))
""" % UMBRAL_SEGUNDOS
        resultado = _ejecutar_apptest(codigo)
        self.assertIn("OK", resultado.stdout, msg=f"stdout={resultado.stdout!r} stderr={resultado.stderr[-500:]!r}")
        self.assertIn("TIENE_KPI: True", resultado.stdout)


class FiltrosTests(unittest.TestCase):
    """Requisito: Filtros — cambiar segmento/escenario no debe romper la página."""

    def test_cambiar_segmento_en_camel_score(self):
        codigo = """
import warnings; warnings.filterwarnings('ignore')
from streamlit.testing.v1 import AppTest
at = AppTest.from_file("pages/10_CAMEL_Score.py", default_timeout=%d)
at.run()
sb = next((s for s in at.sidebar.selectbox if s.label == "Segmento"), None)
if sb is None:
    print("EXCEPTION: selectbox del Filtro Global de Segmento no encontrado")
else:
    opciones = sb.options
    if len(opciones) > 1:
        sb.set_value(opciones[1]).run()
    print("EXCEPTION:", at.exception[0].value) if at.exception else print("OK")
""" % UMBRAL_SEGUNDOS
        resultado = _ejecutar_apptest(codigo)
        self.assertIn("OK", resultado.stdout, msg=f"stdout={resultado.stdout!r} stderr={resultado.stderr[-500:]!r}")

    def test_cambiar_escenario_en_stress_testing(self):
        codigo = """
import warnings; warnings.filterwarnings('ignore')
from streamlit.testing.v1 import AppTest
at = AppTest.from_file("pages/12_Stress_Testing.py", default_timeout=%d)
at.run()
sb = next((s for s in at.selectbox if s.key == "escenario_stress"), None)
if sb is None:
    print("EXCEPTION: selectbox escenario_stress no encontrado")
else:
    sb.set_value("Extremo").run()
    print("EXCEPTION:", at.exception[0].value) if at.exception else print("OK")
""" % UMBRAL_SEGUNDOS
        resultado = _ejecutar_apptest(codigo)
        self.assertIn("OK", resultado.stdout, msg=f"stdout={resultado.stdout!r} stderr={resultado.stderr[-500:]!r}")


class GraficosTests(unittest.TestCase):
    """Requisito: Gráficos — las páginas deben producir al menos un gráfico Plotly."""

    def test_panorama_produce_graficos_plotly(self):
        codigo = """
import warnings; warnings.filterwarnings('ignore')
from streamlit.testing.v1 import AppTest
at = AppTest.from_file("pages/1_Panorama.py", default_timeout=%d)
at.run()
if at.exception:
    print("EXCEPTION:", at.exception[0].value)
else:
    print("OK")
    print("N_GRAFICOS:", len(at.get("plotly_chart")))
""" % UMBRAL_SEGUNDOS
        resultado = _ejecutar_apptest(codigo)
        self.assertIn("OK", resultado.stdout, msg=f"stdout={resultado.stdout!r} stderr={resultado.stderr[-500:]!r}")
        n_graficos = int(resultado.stdout.split("N_GRAFICOS:")[1].strip().splitlines()[0])
        self.assertGreater(n_graficos, 0, "Panorama no produjo ningún gráfico Plotly")

    def test_concentracion_produce_graficos_plotly(self):
        codigo = """
import warnings; warnings.filterwarnings('ignore')
from streamlit.testing.v1 import AppTest
at = AppTest.from_file("pages/8_Riesgo_Concentracion.py", default_timeout=%d)
at.run()
if at.exception:
    print("EXCEPTION:", at.exception[0].value)
else:
    print("OK")
    print("N_GRAFICOS:", len(at.get("plotly_chart")))
""" % UMBRAL_SEGUNDOS
        resultado = _ejecutar_apptest(codigo)
        self.assertIn("OK", resultado.stdout, msg=f"stdout={resultado.stdout!r} stderr={resultado.stderr[-500:]!r}")
        n_graficos = int(resultado.stdout.split("N_GRAFICOS:")[1].strip().splitlines()[0])
        self.assertGreater(n_graficos, 0, "Concentración no produjo ningún gráfico Plotly")


class RendimientoTests(unittest.TestCase):
    """Requisito: Rendimiento — umbral básico de tiempo de carga por página."""

    def _medir(self, ruta: str) -> float:
        t0 = time.perf_counter()
        resultado = _ejecutar_apptest(_codigo_carga_pagina(ruta))
        duracion = time.perf_counter() - t0
        self.assertIn("OK", resultado.stdout, msg=f"{ruta}: stdout={resultado.stdout!r}")
        return duracion

    def test_inicio_carga_bajo_el_umbral(self):
        duracion = self._medir("Inicio.py")
        self.assertLess(duracion, UMBRAL_SEGUNDOS + 15, f"Inicio.py tardó {duracion:.1f}s")

    def test_panorama_carga_bajo_el_umbral(self):
        duracion = self._medir("pages/1_Panorama.py")
        self.assertLess(duracion, UMBRAL_SEGUNDOS + 15, f"Panorama tardó {duracion:.1f}s")


if __name__ == "__main__":
    unittest.main()
