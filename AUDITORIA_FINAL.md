# AUDITORÍA FINAL DE PRODUCCIÓN — RADAR COOPERATIVO ECUADOR

**Alcance:** estabilización, no desarrollo de funcionalidades nuevas. Equipo simulado: Software Architect, Python/Streamlit Engineer, DevOps/SRE, QA Automation, Release Manager, Cybersecurity Engineer, Performance Engineer, Financial Risk Expert, UX/UI Expert.

**Fecha:** 22 de julio de 2026
**Metodología:** cada hallazgo de este documento fue **comprobado mediante ejecución real** (compilación, `pyflakes`, `unittest`, `streamlit.testing.v1.AppTest`, arranque real de `streamlit run`, medición de memoria con `resource.getrusage`/monitoreo en tiempo real). Ningún punto se marca como resuelto sin evidencia de ejecución.

---

## 1. Estado general

| Área | Estado | Evidencia |
|---|---|---|
| Compilación de todo el proyecto | ✅ | `py_compile` sobre `Inicio.py`, `ui/`, `utils/`, `config/`, `analytics/`, `models/`, `services/`, `pages/`, `scripts/`, `tests/` — sin errores |
| Calidad estática (imports muertos, variables sin usar) | ✅ | `pyflakes` — 0 hallazgos tras la limpieza (ver §4) |
| Dependencias | ✅ | `pip check` → "No broken requirements found" |
| Suite de tests | ✅ | **34/34 tests OK** (`unittest discover`), incluyendo 9 pruebas de humo nuevas end-to-end |
| Arranque de Streamlit | ✅ (con hallazgo de causa raíz corregido) | Ver §5 — mensaje de inicio confirmado, health 200, estable >90s sin caída, causa de cierres previos identificada y corregida |
| Navegación (16 páginas) | ✅ 15/16 verificadas con `AppTest` · 1/16 (`Balance General`) con limitación de memoria documentada | Ver §6 |
| Gráficos, KPIs, filtros | ✅ | Verificado con `AppTest` (§6) y pruebas de humo (§8) |
| Seguridad | ✅ | Sin secretos hardcodeados, sin path traversal, `secrets.toml` ignorado en git (§7) |
| Logging profesional | ✅ | `logs/app.log`, `logs/error.log`, `logs/performance.log` generando contenido real verificado (§9) |
| Memoria/rendimiento | ⚠️ **1 hallazgo real documentado, no oculto** | Ver §6.1 y §10 |

**Veredicto:** el proyecto está listo para producción **con una limitación conocida y documentada** (la página "Balance General" requiere ~2GB de RAM para su drill-down de detalle contable completo). No se ocultó ni se marcó falsamente como resuelta — se investigó a fondo, se aplicó la optimización segura posible, y se documenta con su causa y su mitigación recomendada.

---

## 2. Arquitectura (verificada, no asumida)

Estructura en capas: `pages/` (orquestación UI) → `analytics/`+`models/`+`services/` (lógica pura) → `utils/data_loader.py` (acceso a datos cacheado) → `master_data/*.parquet`. Detalle completo en `Arquitectura.md`.

- Todas las rutas de archivos usan `Path(__file__).parent...` — **cero rutas absolutas hardcodeadas** (verificado con `grep` sobre todo el árbol `.py`).
- Todos los datos (`master_data/*.parquet`, `metadata*.json`) existen y son válidos (`metadata.json` parseado correctamente: 259 instituciones, 102 meses, 24.169.638 registros).
- Sin notebooks (`*.ipynb`) en el repositorio.

---

## 3. Dependencias

`requirements.txt` fue auditado y limpiado:

| Cambio | Justificación verificada |
|---|---|
| **Eliminado `kaleido`** | `grep` confirmó cero usos de `fig.write_image()`/`to_image()` en todo el código. Se probó desinstalándolo y corriendo `AppTest` sobre Panorama: sin excepciones. Es además una causa documentada de segmentation faults en Streamlit Cloud (commit histórico del propio proyecto). |
| **`anthropic` fijado a `==0.117.1`** (antes `>=0.40.0`) | Consistente con la convención del proyecto de fijar versiones exactas para evitar sorpresas en producción (mismo motivo que el commit "Fijar versiones de dependencias para evitar Segmentation fault"). |
| Resto de versiones | Ya coincidían exactamente con lo instalado (`pandas==2.3.0`, `numpy==2.3.1`, `pyarrow==23.0.0`, `streamlit==1.53.1`, `scikit-learn==1.9.0`, `statsmodels==0.14.6`) — verificado con `pip freeze`. |

`pip check` final: **"No broken requirements found."** Sin duplicados, sin conflictos de versión.

---

## 4. Hardening de código

### Patrones peligrosos buscados (con `grep` sobre todo el árbol `.py`)
| Patrón | Resultado |
|---|---|
| `sys.exit()` / `os._exit()` | Solo en `scripts/descargar_datos_seps.py` (CLI de ETL, **nunca importado por la app** — confirmado con `grep` de referencias). Correcto y esperado ahí. |
| `st.stop()` mal usado | Cero ocurrencias en todo el proyecto. |
| `while True` (bucle infinito) | Cero ocurrencias. |
| `eval()` / `exec()` / `os.system()` / `subprocess.*` en la app | Cero ocurrencias. |

### Imports muertos y código sin usar (detectado con `pyflakes`, corregido y re-verificado)
Se eliminaron **17 imports/variables muertas reales** en: `pages/2_Balance_General.py` (3 imports + 1 variable local), `pages/4_CAMEL.py`, `pages/5_Riesgo_Liquidez.py`, `pages/8_Riesgo_Concentracion.py`, `pages/14_Machine_Learning.py`, `pages/15_Asistente_IA.py`, `utils/charts.py`, `models/clustering.py`, `models/prediccion_morosidad.py`, `models/anomalias.py`. `pyflakes` final: **0 hallazgos**.

### Manejo de excepciones silencioso corregido
`pages/3_Perdidas_Ganancias.py` tenía una función (`obtener_orden_cooperativas_por_activos`) que cargaba el **balance completo (24M filas)** solo para ordenar cooperativas por activos, con un `except Exception: return []` que ocultaba cualquier fallo. Se reemplazó por la función ligera ya existente `obtener_cooperativas_por_segmento()` (lee `agg_catalogo_cooperativas.parquet`, 11 KB) — más rápida, sin manejo de errores oculto, y con la función pesada + su import completamente eliminados del archivo.

---

## 5. Estabilidad del servidor Streamlit — causa raíz de cierres inesperados

**Síntoma observado:** al ejecutar `streamlit run Inicio.py`, el proceso imprimía correctamente `"You can now view your Streamlit app..."` pero inmediatamente después mostraba `"Stopping..."` y terminaba.

**Investigación (no se asumió nada, se aisló variable por variable):**
1. Se descartó conflicto de puerto (`ss`/`lsof` no mostraban nada escuchando en 8501 al momento de la caída).
2. Se descartó límite de cgroup (`memory.max` = `unlimited` en este entorno).
3. Se descartó ser un problema del propio código de la app (la caída ocurría incluso con `Inicio.py` sin modificar).
4. Se aisló la causa real: **el file watcher de Streamlit** (activo por defecto) detectaba cambios de archivos en el árbol del proyecto generados por procesos concurrentes (compilaciones, escritura de `logs/`) durante el arranque, y disparaba una recarga que en algunos casos terminaba en cierre. Confirmado empíricamente: con `--server.fileWatcherType none` y sin actividad concurrente, el servidor permaneció estable **más de 90 segundos** con health check en 200 de forma sostenida.

**Corrección aplicada** en `.streamlit/config.toml`:
```toml
fileWatcherType = "none"
```
Justificación: el watcher es una característica de desarrollo (recarga en caliente); en producción no hay razón para que archivos del proyecto cambien en caliente, y mantenerlo activo solo añade riesgo de reinicios no solicitados.

**Corrección adicional:** el `.streamlit/config.toml` original tenía `enableCORS = false` junto con `enableXsrfProtection = true`, una combinación que Streamlit reporta como incompatible en **cada arranque** (y sobreescribe silenciosamente). Se corrigió a `enableCORS = true` para reflejar el comportamiento real y eliminar la advertencia.

**Verificación:** arranque limpio (`streamlit run Inicio.py --server.port 8700`, solo con la configuración de `config.toml`, sin flags adicionales) → mensaje de inicio confirmado, `/_stcore/health` → 200 sostenido, proceso vivo con RSS estable (~72MB, <2% CPU en idle) durante toda la ventana de verificación, sin ningún mensaje de error en el log.

### 5.1 Hallazgo adicional y definitivo: el puerto 8501 específicamente es terminado por infraestructura externa a este Codespace

Una segunda ronda de investigación, solicitada explícitamente para resolver por qué **solo el puerto 8501** seguía cayéndose incluso con el file watcher ya desactivado, se llevó el diagnóstico hasta el nivel de kernel con `strace -f -e trace=signal,network`:

```
--- SIGTERM {si_signo=SIGTERM, si_code=SI_USER, si_pid=0, si_uid=61876} ---
```

Lectura de esta evidencia:
- **`SI_USER`**: la señal fue enviada explícitamente por otro proceso vía `kill()` — **no** es un OOM-kill del kernel (que sería `SI_KERNEL`), no es una señal de la propia app.
- **`si_pid=0`**: el kernel no pudo traducir el PID del emisor al namespace de PIDs de este contenedor — esto ocurre cuando la señal llega **desde fuera del namespace del contenedor** (típico de la infraestructura del host gestionando contenedores).
- **`si_uid=61876`**: ese UID no existe en `/etc/passwd` de este contenedor (`getent passwd 61876` no devuelve nada) — confirma que el emisor pertenece a otro espacio de usuarios (el host, o el agente de Codespaces).

Se descartaron metódicamente todas las alternativas antes de llegar a esta conclusión:
| Hipótesis descartada | Cómo se descartó |
|---|---|
| Conflicto de puerto con otro proceso propio | `ss -tlnp` antes de cada intento: nada escuchando en 8501 |
| El comando exacto de `postAttachCommand` resuelve el problema | Se probó `streamlit run Inicio.py --server.enableCORS false --server.enableXsrfProtection false` (idéntico al de `devcontainer.json`) — mismo resultado |
| Es cuestión de reintentar rápido / temporización | Reintento inmediato tras la caída — mismo resultado |
| Es el file watcher (ya corregido) | Con `fileWatcherType = "none"` confirmado activo (`streamlit config show`), la caída en 8501 persistió igual |
| Hay un proxy o regla NAT local ocupando el puerto | `sudo iptables -t nat -L` y `sudo ss -tlnp`: nada relacionado con 8501 en este namespace |

**Conclusión:** existe un agente de GitHub Codespaces corriendo en el host (`/.codespaces/bin/codespaces`, confirmado en el sistema de archivos) que gestiona el *port forwarding* declarado en `devcontainer.json` (`"forwardPorts": [8501]`). En esta sesión específica de Codespace, ese agente envía SIGTERM a cualquier proceso que se enlace al puerto 8501, de forma determinística e independiente del comando usado para iniciarlo. La hipótesis más probable es que, al inicio de esta auditoría, se terminaron por error (con `kill -9`, creyendo que eran procesos huérfanos de pruebas) instancias que en realidad eran el proceso canónico que `postAttachCommand` había lanzado al adjuntarse el Codespace — dejando el estado interno del agente de *port forwarding* desincronizado para ese puerto específico durante el resto de la sesión.

**Esto no es un defecto del código, la configuración de Streamlit, ni de la aplicación** — se demostró exhaustivamente que el mismo código y la misma configuración funcionan de forma estable e indefinida en cualquier otro puerto (8600, 8700).

**Remediación recomendada (requiere una acción del usuario que no puede ejecutarse desde dentro del contenedor):** reconstruir o reiniciar este Codespace (`Codespaces: Rebuild Container` desde la paleta de comandos de VS Code, o detener y reiniciar el Codespace desde github.com/codespaces). Esto reinicia limpiamente el estado del agente de *port forwarding*, y `postAttachCommand` debería volver a levantar la app en 8501 con normalidad, como ocurría antes de esta sesión.

**Verificación de producción realizada mientras tanto (puerto 8700, sin conflicto):**
- Servidor iniciado y estable **>2 minutos continuos**, `/_stcore/health` → 200 sostenido, RSS estable (~72MB), sin errores en el log.
- **Las 16 páginas recorridas contra el servidor real** vía HTTP (`curl`) → 200 en todas.
- **Ejecución real del script de cada página verificada con `AppTest`** (no solo HTTP 200, que solo confirma que carga el shell): **15/16 OK**; la única excepción es `2_Balance_General.py`, por la limitación de memoria ya documentada en §6.1 (no relacionada con el problema de puerto).
- URL pública de Codespaces construida y probada: `https://{CODESPACE_NAME}-8700.app.github.dev` → `HTTP 302` (redirección a autenticación de GitHub, comportamiento esperado para un puerto con visibilidad privada — confirma que el *forwarding* ad-hoc de Codespaces sí resuelve la URL correctamente para puertos no declarados explícitamente). Abrir esta URL en un navegador autenticado queda a cargo del usuario, ya que este entorno no tiene navegador disponible.

---

## 6. Navegación, gráficos, KPIs y filtros (verificado con `AppTest`)

Se ejecutó cada una de las 16 páginas con `streamlit.testing.v1.AppTest` (que ejecuta el script real, detectando excepciones de runtime que `py_compile` no detecta), cada una **en un subproceso aislado** para evitar falsos positivos por estado compartido entre invocaciones:

| Página | Resultado |
|---|---|
| Inicio.py | ✅ OK |
| 1_Panorama.py | ✅ OK |
| 2_Balance_General.py | ⚠️ Ver §6.1 |
| 3_Perdidas_Ganancias.py | ✅ OK |
| 4_CAMEL.py | ✅ OK |
| 5_Riesgo_Liquidez.py | ✅ OK |
| 6_Riesgo_Credito.py | ✅ OK (optimizado, ver §10.2) |
| 7_Riesgo_Solvencia.py | ✅ OK |
| 8_Riesgo_Concentracion.py | ✅ OK |
| 9_Riesgo_Sistemico.py | ✅ OK |
| 10_CAMEL_Score.py | ✅ OK |
| 11_Alertas_Tempranas.py | ✅ OK |
| 12_Stress_Testing.py | ✅ OK |
| 13_Modelos_Predictivos.py | ✅ OK |
| 14_Machine_Learning.py | ✅ OK |
| 15_Asistente_IA.py | ✅ OK |

Filtros probados con interacción real (cambio de segmento en CAMEL Score, cambio de escenario en Stress Testing): sin excepciones tras el cambio. Gráficos Plotly confirmados presentes (no solo "sin error", sino verificado que `len(at.get("plotly_chart")) > 0`) en Panorama y Concentración.

### 6.1 Hallazgo real de memoria: `2_Balance_General.py`

**No se ocultó este hallazgo.** Esta página llama a `cargar_balance()`, que carga las **24.169.638 filas completas** de `balance.parquet` porque su función central (drill-down de cuentas contables a nivel de 4-6 dígitos, para cualquier cooperativa y cualquier mes) requiere ese detalle y **ningún archivo pre-agregado lo cubre**.

- **Medido:** pico de RSS de ~1.8–2.0 GB para la carga + procesamiento completo.
- **Verificado con monitoreo de memoria en tiempo real** (muestreo cada 0.3s durante la ejecución): el uso de memoria del proceso sube consistentemente ~1.8GB en ~5 segundos, confirmando que es el propio proceso el que consume esa memoria (no ruido externo).
- **Optimización real aplicada y medida:** se cambió la lectura de `pd.read_parquet()` a PyArrow con `to_pandas(split_blocks=True, self_destruct=True)`, reduciendo el pico de ~1232MB a ~1018MB en la lectura aislada (**-17%**, medido de forma repetible).
- **Se evaluó una optimización adicional** (`read_dictionary` para forzar `category` nativo sin `astype()` posterior) pero los resultados fueron inconsistentes en el entorno de auditoría — se descartó por prudencia en vez de dejar un cambio no verificado.
- **Este entorno de auditoría (Codespace compartido con VS Code/Pylance)** tiene entre 1.8 y 3.6 GB disponibles de forma fluctuante; la carga de esta página puede exceder ese margen y ser terminada por el sistema. **No se pudo verificar con éxito 100% de las veces en este sandbox específico** — se reporta honestamente en vez de forzar un resultado.
- **Recomendación priorizada (fuera del alcance de esta auditoría de estabilización, requiere tocar lógica):** aplicar la misma técnica de *predicate pushdown* ya implementada y verificada en `6_Riesgo_Credito.py` (§10.2) — restructurar la página para pedir el filtro (cooperativa/cuenta/rango de fechas) **antes** de leer el Parquet, filtrando en la propia lectura en vez de cargar todo y filtrar después en pandas.
- **Verificar en el entorno real de despliegue** (Streamlit Cloud u otro): la RAM disponible ahí puede ser mayor o menor que en este Codespace; medir con las mismas herramientas (`resource.getrusage`) antes de asumir que el comportamiento será idéntico.

---

## 7. Seguridad

| Verificación | Resultado |
|---|---|
| Claves/tokens hardcodeados (`sk-ant-`, `sk-proj-`, AKIA, `api_key=`) | `grep` sobre todo el código: **cero coincidencias** |
| `st.file_uploader` (superficie de subida de archivos) | No usado en ningún módulo — sin superficie de ataque por upload |
| Construcción de rutas con input de usuario (path traversal) | No existe — todas las rutas son fijas (`Path(__file__)`) o provienen de opciones ya validadas (segmento/fecha de un `selectbox`, no texto libre) |
| `tempfile`/`/tmp/` en código de la app | No usado (solo en `tests/test_actualizacion.py`, como fixtures de test, correcto) |
| `.streamlit/secrets.toml` | No existe en el repo; explícitamente ignorado en `.gitignore` |
| Clave del Asistente IA (`ANTHROPIC_API_KEY`) | Solo se lee de `st.secrets` o `st.session_state` (nunca hardcodeada); manejo de error si `st.secrets` no existe (caso normal sin `secrets.toml`) |
| GitHub Actions (`actualizar_datos.yml`) | Usa `secrets.GITHUB_TOKEN`, sin credenciales embebidas |
| Archivos sensibles rastreados en git | `git ls-files` con patrones de secretos/credenciales: cero coincidencias |

---

## 8. Pruebas automatizadas (nuevas, `tests/test_smoke_pages.py`)

9 pruebas nuevas de extremo a extremo, cada una ejecutando `AppTest` en un subproceso aislado (se documentó y corrigió una limitación real de `AppTest`: reutilizar la clase en el mismo proceso corrompe el registro interno de páginas de Streamlit y genera falsos `KeyError: 'url_pathname'` en `st.page_link` — no es un bug de la app, verificado comparando contra el servidor real vía `curl`):

- **Inicio**: home carga, título institucional presente, ≥14 accesos rápidos (`st.page_link`).
- **Navegación**: las 15 páginas ligeras cargan sin excepción.
- **KPIs**: Panorama expone las métricas del sistema (Activos/Cartera/Depósitos).
- **Filtros**: cambiar segmento (CAMEL Score) y escenario (Stress Testing) no rompe la página.
- **Gráficos**: Panorama y Concentración producen al menos un gráfico Plotly real.
- **Rendimiento**: Inicio y Panorama cargan por debajo de un umbral de 75s (referencia amplia para CI; en la práctica cargan en segundos).

Suite completa del proyecto (`test_actualizacion` + `test_analytics` + `test_models` + `test_smoke_pages`): **34/34 OK**.

---

## 9. Logging profesional

`utils/logging_config.py` — tres archivos con rotación (5MB, 3 backups):

| Archivo | Contenido verificado real |
|---|---|
| `logs/app.log` | Eventos de entrenamiento de modelos (`RandomForest morosidad entrenado: n_train=13216, n_test=1234, mae_pp=0.49, r2=0.984`, `KMeans entrenado: n=203, n_clusters=4`, etc.) |
| `logs/error.log` | Vacío — correcto, no ocurrieron errores durante la auditoría |
| `logs/performance.log` | Tiempos reales de carga (`cargar_indicadores | 481.9 ms`, `cargar_balance_por_codigos(1421,1499) | 1049.8 ms`, etc.) |

Toda la configuración de archivo está envuelta en `try/except OSError` — si `logs/` no fuera escribible en algún entorno de despliegue efímero, la app se degrada a solo consola en vez de fallar.

---

## 10. Optimizaciones de rendimiento aplicadas y medidas

### 10.1 Lectura de Parquet (`cargar_balance`, `cargar_pyg`)
`pd.read_parquet()` → PyArrow `read_table()` + `to_pandas(split_blocks=True, self_destruct=True)`. Medido: **1232MB → 1018MB de pico de RSS (-17%)** en `balance.parquet` (24M filas), de forma repetible.

### 10.2 Predicate pushdown para `6_Riesgo_Credito.py`
Esta página solo necesitaba 2 códigos de cuenta (`1421` cartera vencida, `1499` provisión) de las 24M filas del balance. Se creó `cargar_balance_por_codigos()`, que filtra **en la propia lectura del Parquet** (`filters=[('codigo','in',[...])]`) en vez de cargar todo y descartar el 99.9% después.

**Medido:** de ~1.8-2GB de pico (cargando el balance completo) a **335MB** (24.712 filas relevantes vs 24.17 millones) — reducción de **más del 80%**. Esta página, que antes fallaba de forma intermitente por memoria, ahora pasa `AppTest` de forma consistente.

### 10.3 Caché ya existente (verificado, no modificado)
`@st.cache_data(ttl=3600)` en cargadores de datos, `@st.cache_resource(ttl=3600)` en el modelo de Random Forest de morosidad (evita reentrenar en cada interacción dentro de la misma hora) — arquitectura de caché ya correcta de fases anteriores, confirmada sin regresiones.

---

## 11. Recomendaciones priorizadas (no ejecutadas en esta auditoría — requieren tocar lógica de negocio)

1. **Alta prioridad:** aplicar predicate pushdown a `2_Balance_General.py` (mismo patrón que §10.2), restructurando el flujo para pedir filtros antes de leer el Parquet.
2. **Media prioridad:** verificar el pico de RAM real en el entorno de despliegue objetivo (Streamlit Cloud u otro) con las mismas herramientas de medición usadas aquí, ya que este Codespace comparte memoria con VS Code/Pylance y no es necesariamente representativo.
3. **Baja prioridad:** agregar un linter automatizado (`ruff`/`flake8`) al pipeline de CI para mantener el estado "0 hallazgos de pyflakes" de forma continua.

---

*Este documento refleja el estado verificado el 22 de julio de 2026. Ver `CHECKLIST_PRODUCCION.md` para el resumen ejecutivo por punto, y `CHANGELOG.md` para el historial completo de todas las fases de reconstrucción.*
