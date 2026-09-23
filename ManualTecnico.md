# Manual Técnico — RADAR COOPERATIVO ECUADOR

Guía operativa para desarrollo, despliegue y mantenimiento. Para el diseño de
arquitectura ver `Arquitectura.md`; para el uso funcional, `ManualUsuario.md`.

---

## 1. Instalación local

```bash
git clone <repositorio>
cd cooperativas
pip install -r requirements.txt
streamlit run Inicio.py
```

Requisitos: Python 3.9+ (ver `requirements.txt` para versiones exactas de
`streamlit`, `pandas`, `numpy`, `pyarrow`, `plotly`, `scikit-learn`,
`statsmodels`, `anthropic`).

## 2. Logo institucional — ruta requerida

El header (`ui/header.py`) busca el logo en:

```
assets/logo_cosede.png
```

**Coloque ahí el PNG del logo de COSEDE** (el candado con el texto
"COSEDE — Protegemos tu dinero"). Recomendaciones:
- Formato PNG con fondo transparente (o blanco, ya que el contenedor del
  logo en el header usa fondo blanco cuando detecta el archivo).
- Tamaño sugerido: al menos 200×200 px (se reescala automáticamente,
  `object-fit: contain`, dentro de un contenedor de 52×52 px en el header).
- **No requiere reiniciar código**: `ui/header.py` verifica la existencia del
  archivo en cada render (`LOGO_PATH.exists()`) y lo incrusta en base64
  automáticamente la primera vez que se ejecuta la página tras copiarlo.
  Si la app ya estaba corriendo con `st.cache_data`, use el menú de
  Streamlit → "Clear cache" (o reinicie el proceso) para forzar la relectura,
  ya que `_logo_html()` está cacheado con `@st.cache_data`.
- Si el archivo no existe, el header muestra automáticamente un badge de
  texto "COSEDE" como *fallback* — la plataforma nunca se rompe por la
  ausencia del logo.

**Nota sobre el archivo actual**: el logo oficial fue proporcionado como una
imagen pegada en el chat de esta sesión; no existe un mecanismo para extraer
el binario exacto de esa imagen a un archivo en disco. El archivo que hoy
vive en `assets/logo_cosede.png` es una **reconstrucción propia** del ícono
del candado (mismos colores institucionales: azul, amarillo, rojo),
generada con Pillow para que el header no dependa de un placeholder de
texto. **No es el activo oficial pixel-perfecto de COSEDE.** Cuando tenga a
mano el archivo original (p. ej. del manual de marca de COSEDE), reemplace
`assets/logo_cosede.png` con ese archivo — el header lo tomará
automáticamente sin cambios de código, ya que solo verifica que el nombre y
la ruta coincidan.

## 3. Pipeline de datos (ETL)

Orden de ejecución (ver también `README.md`):

```bash
python scripts/procesar_balance_cooperativas.py   # ZIPs SEPS -> balance.parquet
python scripts/generar_agregados.py               # balance.parquet -> agg_*.parquet
python scripts/procesar_indicadores.py            # staging para PyG/CAMEL
python scripts/procesar_pyg.py                    # -> pyg.parquet
python scripts/procesar_camel.py                  # -> indicadores.parquet
python scripts/validar_actualizacion.py           # valida consistencia
```

Automatizado mensualmente por `.github/workflows/actualizar_datos.yml`.
Los módulos nuevos de Fases 2-5 (`ui/`, `analytics/`, `models/`, `services/`)
**no requieren cambios en el pipeline ETL** — consumen los mismos Parquet.

## 4. Ejecutar la suite de pruebas

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

- `tests/test_actualizacion.py`: pipeline ETL (preexistente).
- `tests/test_analytics.py`: HHI/CR/Lorenz/Gini, CAMEL score, alertas, stress
  testing — con datos sintéticos, assertions exactas.
- `tests/test_models.py`: forecast, anomalías, clustering — con datos
  sintéticos, assertions de estructura/comportamiento (no valores exactos,
  porque scikit-learn/statsmodels pueden variar levemente entre versiones
  aun con `random_state` fijo).

**Verificación de páginas completas** (ejecuta cada página como lo haría
Streamlit, detecta excepciones de runtime que `py_compile` no detecta):

```python
from streamlit.testing.v1 import AppTest
at = AppTest.from_file("pages/11_Alertas_Tempranas.py", default_timeout=120)
at.run()
assert not at.exception
```

## 5. Logging

`utils/logging_config.get_logger(__name__)` configura logging una sola vez
por proceso (`logging.basicConfig`) y lo usan `models/*.py` y
`services/asistente_ia.py` para registrar eventos significativos:
entrenamiento de modelos (tamaño de muestra, métricas), llamadas a Claude y
sus fallos. Streamlit Cloud captura stdout/stderr automáticamente en los
logs de la aplicación — no se requiere configuración adicional en producción.

## 6. Asistente IA — configurar Claude (opcional)

En Streamlit Cloud: **Settings → Secrets**, agregar:

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
```

En local: crear `.streamlit/secrets.toml` (no versionado, ya excluido por
`.gitignore`) con la misma clave, o ingresarla manualmente en el sidebar del
módulo **Asistente Inteligente** (se guarda solo en la sesión del navegador).

Sin clave configurada, el asistente funciona en modo local determinístico
(ver `services/asistente_ia.py::responder_local`) — no requiere ninguna
configuración y nunca inventa cifras.

## 7. Reentrenamiento de modelos

Los modelos de `models/` **no tienen pesos versionados**: se entrenan en
cada ejecución de la página correspondiente, sobre los datos más recientes
de `master_data/`. Esto significa que:
- No hay un paso manual de "reentrenar" — ocurre automáticamente al abrir
  `pages/13_Modelos_Predictivos.py` o `pages/14_Machine_Learning.py`.
- El costo de entrenamiento (Random Forest de morosidad, ~14K filas) se
  mitiga con `@st.cache_resource(ttl=3600)` en `pages/13`, para no reentrenar
  en cada interacción del usuario dentro de la misma hora.
- Si se actualiza `master_data/indicadores.parquet` (nuevo mes de datos), el
  modelo se reentrena automáticamente la próxima vez que expire el caché.

## 8. Convenciones de código

- **Español** para nombres de funciones/variables de dominio (consistente
  con el proyecto original); **docstrings en español**.
- **Type hints** en `analytics/`, `models/`, `services/`, `ui/` (capas de
  lógica reutilizable). Las páginas (`pages/*.py`) son scripts de
  orquestación y no requieren type hints exhaustivos.
- **Sin comentarios explicativos de "qué hace" el código** (los nombres ya
  lo dicen); comentarios solo para supuestos no obvios (ver
  `analytics/stress_testing.py`, `config/umbrales_alerta.py`).
- **PEP8**: sin un linter automatizado configurado aún; se recomienda
  `ruff` o `flake8` como siguiente paso de calidad transversal.

## 9. Límites conocidos (para no reintroducir por error)

- `sys.path.append(...)` en cada página de `pages/`: necesario (ver
  `Arquitectura.md`, sección 6) — no eliminar sin empaquetar el proyecto
  formalmente primero.
- El Stress Testing puede mostrar una razón de solvencia post-shock **mayor**
  que la previa bajo shocks de depósitos grandes — no es un bug (ver
  `analytics/stress_testing.py` y `tests/test_analytics.py`).
- Vintage curves / roll-rate / matrices de transición de crédito: no
  calculables con los datos oficiales actuales (requieren microdata de
  operación). No implementar con datos aproximados o inventados.
- Riesgo Sistémico: no incluye red de interconexión real (no hay datos de
  exposiciones interbancarias/intercooperativas en las fuentes oficiales).
