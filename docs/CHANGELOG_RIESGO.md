# Changelog — Módulos de Riesgo

Registro de cambios específicos a fuentes, indicadores, fórmulas, reglas de
alerta, umbrales, tests y limitaciones del sistema de vigilancia de riesgo.
No duplica `docs/CONTEXTO.md` (historial general del proyecto) — este archivo
es el nivel de detalle que un analista de Riesgos necesita para auditar qué
cambió en la metodología, no en la aplicación en general. Ver
`docs/RIESGO_METODOLOGIA.md` para el estado consolidado de cada componente.

---

## 2026-09-14 (tarde, hardening) — Validación, calibración y robustez

Fase de auditoría + corrección sobre lo construido en la entrada anterior del
mismo día. Ningún componente nuevo; el foco fue robustez, no cobertura.

### Corrección de lógica

- **`analytics/riesgo_sistemico_estado.py`**: el árbol de decisión permitía
  que una caída YoY aislada en una sola dimensión (p. ej. solo cartera, sin
  breadth ni persistencia) alcanzara `CONTRACCIÓN SECTORIAL`. Se agregó un
  requisito de evidencia multidimensional (≥2 de 3 señales: crecimiento,
  breadth, persistencia) antes de permitir cualquier estado de la familia
  `CONTRACCIÓN`/`ESTRÉS`/`EVENTO EXTREMO`. Encontrado con una batería de 8
  escenarios sintéticos (A-H); los 8 producen ahora resultados coherentes.

### Corrección de código (fix de segmentación pendiente)

- **`scripts/procesar_pyg.py`**: mismo fix de `segmento_historico`/
  `segmento_actual`/`segmento_historico_estimado` ya aplicado a
  balance/indicadores en la entrada anterior. `master_data/pyg.parquet` NO
  se regeneró esta sesión (ver hallazgo de performance abajo).

### Hallazgos (investigados, no necesariamente corregidos)

- **Persistencia ~54%**: investigada con datos reales — estable ante la
  ventana (3/6/12M), no depende de una regla única, proporcional entre
  segmentos, y es una tendencia secular real (de ~30% en 2021-2022 a
  ~50-56% en 2024-2026). Umbral (`UMBRAL_PERSISTENTE_MESES=3`) sin cambios.
- **Breadth 25%**: nunca cruzado por la población "alerta roja" en 6.5 años
  de historia (rango observado 3.7%-19.4%); estable en la región 20-40%,
  sensible en 10-20%. Umbral sin cambios, sigue etiquetado ANALÍTICO.
- **IPSF, correlación A/B=0.968**: se recalculó la correlación entre los 3
  componentes crudos, no solo entre esquemas de pesos. `breadth_activos` y
  `severidad_promedio` correlacionan 0.75 (misma fuente por construcción);
  `desaceleracion` es casi independiente (0.07-0.20). La correlación A/B alta
  es, en gran parte, un artefacto de esa redundancia — se corrigió la
  interpretación en el docstring de `diagnostico_esquemas()` y se agregó
  `analytics.ipsf.correlacion_componentes()` + una sección nueva en la UI.
- **Interacción**: confirmado que `deterioro_cartera_compuesto_critico` es
  subconjunto estricto de `deterioro_cartera_compuesto` (no doble-cuenta un
  riesgo distinto). No se agregaron reglas nuevas por falta de evidencia.
- **Performance — `procesar_indicadores.py`**: el parseo del Boletín
  Financiero Segmento 3 (`indicadores/2026-EEFF-MEN.zip`, 119 MB de pivot
  cache) no completó en >10 minutos en este entorno, pese a que Segmento 1
  (55.6 MB) y Segmento 2 (81.7 MB) procesan en 9.7s/14.6s — escala no lineal.
  No se investigó ni corrigió a fondo (fuera de alcance de esta fase, código
  pre-existente no tocado por los cambios de segmentación). Riesgo residual
  documentado, no resuelto.

### Etiquetado explícito (dato, no solo texto/docstring)

- `analytics/eventos.py`: nueva columna `tipo_evento` en la salida de
  `detectar_eventos_salida()` (`TIPO_EVENTO_PROXY` o `TIPO_EVENTO_TEXTUAL`).
- `analytics/backtesting.py`: nuevo campo `tipo_resultado` = "BACKTESTING
  PROXY — no es validación definitiva".
- `pages/14_Machine_Learning.py`: banner nuevo "detección de anomalías ≠
  predicción de crisis".
- `pages/13_Modelos_Predictivos.py`: banner "ANALÍTICO NO VALIDADO /
  EXPERIMENTAL" (ya reportado en la entrada anterior, sin cambios).

### Control determinístico nuevo

- `services/asistente_ia.py::_aplicar_guardrails_deterministicos()`: capa en
  código (no en el prompt) que detecta la palabra "crisis" en cualquier
  respuesta del modo Claude y adjunta una advertencia visible. Primer control
  de este tipo en el proyecto — explícitamente para no depender solo de que
  el LLM obedezca el prompt de sistema. Prompt de sistema también reforzado
  (hecho vs. inferencia, fallback "Información insuficiente para
  determinarlo.") — ya reportado en la entrada anterior, sin cambios ahí.

### Arquitectura — consolidación del punto de entrada único

- `analytics/financial_engine.py` ahora re-exporta también: `persistencia`,
  `breadth`, `interaccion`, `riesgo_sistemico_estado`, `ipsf`, `eventos`,
  `backtesting`, `data_quality` (8 módulos que la entrada anterior había
  creado pero no conectado a la fachada).
- `pages/9_Riesgo_Sistemico.py`, `pages/11_Alertas_Tempranas.py`,
  `pages/1_Panorama.py`: cambiaron sus imports de submódulos directos a
  `analytics.financial_engine`.
- `tests/test_consistencia_datos.py::MotorCentralIndicadoresTests._SUBMODULOS_DOMINIO`:
  ampliada para cubrir los 8 módulos nuevos — el test de guardia existente no
  los conocía y por eso no había detectado la violación.
- Hallazgo NO corregido (riesgo bajo, ya documentado): `pages/2_Balance_General.py`
  calcula un crecimiento YoY inline para el heatmap mensual, en vez de usar
  una función de `analytics/crecimiento.py` — no es un drop-in porque las
  funciones existentes no soportan un código arbitrario sobre una serie
  mensual completa (solo 2 fechas fijas). Generalizar esa función es trabajo
  de una fase futura, no de este hardening.

### Workflow

- `.github/workflows/actualizar_datos.yml`: los pasos opcionales (Solvencia
  FS01, identidad de entidades) cambiaron de `|| echo "::warning::..."`
  (silencioso en el resumen del run) a `continue-on-error: true` (marca
  visible en la UI de Actions) + un paso final "Resumen de estado del
  pipeline" que escribe a `$GITHUB_STEP_SUMMARY`, categorizando: ERROR
  CRÍTICO / WARNING / NO HAY DATOS NUEVOS / OK por componente.

### Optimización menor

- `analytics/breadth.py`, `analytics/sistemico.py`: `observed=True` en
  `pivot_table()` para eliminar un `FutureWarning` de pandas (comportamiento
  sin cambios, solo silencia la advertencia de una deprecación futura). Los
  otros ~11 call sites de `pivot_table()` en `analytics/` tienen el mismo
  warning pero no se tocaron esta sesión — no son código nuevo de esta fase
  y el riesgo/beneficio de tocar 11 archivos adicionales no se justificaba
  dentro del alcance de este hardening.

### Tests

- `tests/test_riesgo_ampliado.py`: +6 tests (contracción aislada sin
  corroboración, guardrail de "crisis" ×2, contexto del asistente distingue
  hecho/inferencia, respuesta local sin match / con match).
- Suite completa: **116 tests, 330 subtests, 0 regresiones** (110 → 116).
- Un test pre-existente (`tests/test_actualizacion.py::IncrementalidadTests::test_pyg_reemplaza_solapamiento_y_conserva_historia`)
  falló tras el primer intento del fix de `procesar_pyg.py` (`KeyError:
  'segmento_historico'` — el test ejercita `combinar_historico_pyg()` en
  aislamiento con un `df_fuente` sintético que no incluye las columnas
  nuevas). Corregido haciendo la función defensiva ante esa columna faltante
  en `df_fuente`, no solo en el histórico — sin modificar el test.

### Sin cambios de commit

Ningún cambio de esta fase fue commiteado (instrucción explícita).

## 2026-09-14 (tarde) — Cierre e implementación integral

### Fuentes nuevas

- **Boletín SEPS "Patrimonio Técnico"** (fichas 58-63, fuente FS01): scraping
  público vía `scripts/descargar_datos_seps.py::descargar_patrimonio_tecnico()`.
  Cobertura confirmada: Segmento 1, Mutualistas, Caja Central FINANCOOP
  únicamente. Descarga best-effort (no afecta el código de salida del resto
  del pipeline de descarga).

### Indicadores nuevos

- **Solvencia oficial** (`solvencia` = PTC/APPR, ficha 62) y
  `cumple_minimo_regulatorio` / `brecha_pp` (ficha 63, 9% mínimo) —
  `analytics/solvencia.py::evaluar_solvencia_oficial()`. Clasificación:
  `OFICIAL_SEPS`. **Nunca aplicado a `CAP_NETO`** (ficha 57, FK/FI) — son
  indicadores distintos, documentado en 3 lugares: `config/umbrales_alerta.py`,
  `pages/7_Riesgo_Solvencia.py`, `docs/RIESGO_METODOLOGIA.md` §3.2.
- **`solvencia_recalculada_ptc_appr`** y **`discrepancia_solvencia`**
  (columnas de QA en `solvencia.parquet`, no un indicador nuevo publicado en
  UI): recálculo independiente de PTC/APPR para verificar consistencia contra
  el valor reportado por la SEPS. 0% de discrepancia en la corrida de
  verificación (3.548 registros).

### Reglas de alerta

- **`COB_TOT`** añadida a `config/umbrales_alerta.py::REGLAS_ALERTA`
  (`menor_es_peor`, amarilla=0.80, roja=0.60, calibrado por percentiles) —
  requerida como insumo de la regla de interacción `deterioro_cartera_compuesto`
  (ver abajo). No existía como regla individual antes de esta sesión.
- **3 reglas de interacción** nuevas en `analytics/interaccion.py::REGLAS_INTERACCION`
  (`deterioro_cartera_compuesto`, `deterioro_cartera_compuesto_critico`,
  `presion_fondeo`) — cada una con justificación económica documentada en el
  código, ninguna con pesos arbitrarios. Ver `docs/RIESGO_METODOLOGIA.md` §10.

### Módulos analíticos nuevos

| Módulo | Función principal | Clasificación |
|---|---|---|
| `analytics/data_quality.py` | `reporte_calidad_fecha()` y funciones individuales | Validación, no indicador |
| `analytics/persistencia.py` | `calcular_persistencia_alertas()` | ANALÍTICO |
| `analytics/breadth.py` | `calcular_breadth()`, `breadth_por_segmento()` | ANALÍTICO |
| `analytics/interaccion.py` | `evaluar_interacciones()` | ANALÍTICO |
| `analytics/eventos.py` | `detectar_eventos_salida()` | Proxy, no confirmado |
| `analytics/backtesting.py` | `evaluar_alertas_previas_a_eventos()` | ANALÍTICO NO VALIDADO |
| `analytics/riesgo_sistemico_estado.py` | `evaluar_estado_sistemico()` | ANALÍTICO EXPERIMENTAL |
| `analytics/ipsf.py` | `calcular_ipsf_periodo()`, `calcular_serie_ipsf()`, `diagnostico_esquemas()` | EXPERIMENTAL |

### Datos maestros nuevos

- `master_data/solvencia.parquet` + `metadata_solvencia.json` (nuevo, vía
  `scripts/procesar_solvencia.py`).
- `master_data/entidades_cooperativas.parquet` + `metadata_entidades.json`
  (nuevo, vía `scripts/generar_entidades.py`) — tabla ligera de identidad
  (259 entidades, 51 con RUC), no duplica RUC/segmento en `balance.parquet`.

### Cambios de esquema en datos existentes

- `balance.parquet` e `indicadores.parquet`: 3 columnas aditivas
  (`segmento_historico`, `segmento_actual`, `segmento_historico_estimado`).
  `segmento` no se modificó — ningún código existente que lo lea cambia de
  comportamiento. Ver limitación en `docs/RIESGO_METODOLOGIA.md` §18 (100%
  del histórico regenerado quedó `estimado=True`, incluyendo el corte más
  reciente, por diseño del ETL incremental).

### Umbrales y parámetros analíticos (todos declarados como no-regulatorios)

- `UMBRAL_PERSISTENTE_MESES = 3` (`analytics/persistencia.py`).
- `UMBRAL_GENERALIZADO_PCT = 25.0` (`analytics/breadth.py`) — mismo orden de
  magnitud que el umbral de concentración moderada de HHI, por consistencia
  conceptual, no coincidencia.
- `UMBRAL_CRECIMIENTO_DESACELERACION_PCT = 5.0`,
  `UMBRAL_CRECIMIENTO_CONTRACCION_PCT = 0.0`,
  `UMBRAL_BREADTH_SECTORIAL_PCT = 15.0`,
  `UMBRAL_BREADTH_SIGNIFICATIVO_PCT = 25.0`,
  `UMBRAL_PERSISTENCIA_MESES = 3` (`analytics/riesgo_sistemico_estado.py`).
- `UMBRAL_SOLVENCIA_REGULATORIO = 0.09` (`analytics/solvencia.py`) — este sí
  es regulatorio (ficha 63), aplicado únicamente a la columna `solvencia` de
  `solvencia.parquet`.

### Páginas modificadas (ninguna página nueva creada)

- `pages/7_Riesgo_Solvencia.py`: pestaña "🏦 Solvencia Oficial (FS01)".
- `pages/11_Alertas_Tempranas.py`: pestaña "⏱️ Persistencia, Amplitud e
  Interacción".
- `pages/9_Riesgo_Sistemico.py`: pestañas "🧭 Estado Sistémico (Experimental)"
  y "🌡️ IPSF (Experimental)".
- `pages/1_Panorama.py`: sección expandible "🔍 Calidad de datos e identidad
  de entidades".
- `pages/13_Modelos_Predictivos.py`: banner "ANALÍTICO NO VALIDADO /
  EXPERIMENTAL" añadido (sin cambios al motor de los modelos).
- `services/asistente_ia.py`: prompt de sistema reforzado (hecho vs.
  inferencia, fallback "Información insuficiente para determinarlo.").

### Automatización

- `.github/workflows/actualizar_datos.yml`: pasos `procesar_solvencia.py` y
  `generar_entidades.py` añadidos (best-effort, no bloqueantes); `git add`
  de sus outputs protegido para no fallar si el archivo no se generó en esa
  corrida.

### Tests

- `tests/test_riesgo_ampliado.py` (nuevo, 21 tests sintéticos): persistencia,
  breadth, interacción, data quality, estado sistémico, eventos, backtesting,
  IPSF.
- `tests/test_consistencia_datos.py`: 8 tests nuevos sobre datos reales
  (`SegmentoHistoricoTests`, `SolvenciaFS01Tests`, `EntidadesIdentidadTests`).
- Suite completa: 81 → **110 pruebas**, 330 subpruebas, sin regresiones.

### Explícitamente NO implementado en esta sesión (ver razones en `docs/RIESGO_METODOLOGIA.md`)

- Corrección de `segmento` retroactivo en `procesar_pyg.py` (mismo defecto
  que balance/indicadores, no corregido por límite de tiempo).
- Recuperación de `segmento_historico` real para 2018-2026 (requiere
  reprocesar ZIPs fuente de cada año; diferido).
- Indicadores macroprudenciales (Credit-to-GDP Gap, DSR): sin fuente pública
  de PIB mensual ecuatoriano.
- Esquemas de ponderación C (PCA), D (predictivo) y E (híbrido) del IPSF:
  documentados como no implementados con razón explícita, no como pendientes
  silenciosos.
- Ningún commit de los cambios de esta sesión (instrucción explícita).

---

## 2026-09-14 (noche) — Cierre técnico P0/P1: pipeline, segmentación, producción

Segunda fase de hardening el mismo día. Foco exclusivo: reproducibilidad del
pipeline (ningún cambio al motor de riesgo salvo lo indicado).

### P0 — Causa raíz diagnosticada (no solo mitigada)

El cuello de botella de "Segmento 3" reportado en la fase anterior **no era
del archivo Segmento 3** (procesa en 19.1s aislado, escala lineal 8.4s→
12.7s→19.1s para Segmento 1/2/3). La causa real: `procesar_indicadores.py`
procesa los 4 archivos del ZIP mensual en un solo proceso Python; cada
`ET.fromstring()` deja memoria retenida por glibc (no devuelta al SO pese a
que Python ya la liberó) — RSS acumulado 101→2050→2988→4325 MB a lo largo
de los 4 archivos, terminando en OOM en el último (más grande) archivo.
Confirmado: `gc.collect()` + `malloc_trim(0)` tras cada archivo devuelve el
RSS real a ~105 MB consistentemente.

**Fix**: `scripts/procesar_indicadores.py::_liberar_memoria_al_os()` — 8
líneas, cero cambios al parseo/negocio.

**Alternativa evaluada y descartada**: reescribir el parseo XML con
`ET.iterparse()` (streaming). Equivalencia exacta demostrada contra la
implementación actual en los 3 segmentos reales, pero sin ganancia de
tiempo medible y sin mejora de memoria demostrada por separado — descartada
por mayor riesgo sin beneficio sobre `malloc_trim`.

### Datasets regenerados (ejecución real, no solo verificación de código)

`procesar_indicadores.py` → `procesar_camel.py` → `procesar_pyg.py`
ejecutados de punta a punta. Equivalencia exacta verificada (merge por
fecha+cooperativa+codigo, 0 filas huérfanas, 0 diferencias numéricas
>1e-6) contra los archivos previos a la regeneración:

| Dataset | Filas | Diferencia numérica |
|---|---|---|
| `indicadores_raw.parquet` | 1.756.691 | 0 |
| `master_data/indicadores.parquet` | 611.881 | 0 |
| `master_data/pyg.parquet` | 2.399.251 | 0 (+3 columnas nuevas: `segmento_historico`, `segmento_actual`, `segmento_historico_estimado`) |

Matriz de consistencia balance/pyg/indicadores: sin diferencias no
explicadas (diferencias de `fecha_min` y conteo de entidades entre datasets
son preexistentes y ya documentadas, confirmadas idénticas a antes de esta
regeneración).

### Segmentación histórica — validación con muestra real

`CAÑAR LTDA`: reportó `SEGMENTO 3` real en ene-may 2026 y migró a
`SEGMENTO 2` desde jun-2026 — capturado correctamente en
`segmento_historico` (estimado=False para todo 2026), mientras
`segmento`/`segmento_actual` (legado, intencional) muestran `SEGMENTO 2`
retroactivamente para las 13 filas. 4 cooperativas con cambio de segmento
detectable en el tramo reprocesado.

### P1 — Workflow: 5 estados

Verificado (simulación de la lógica bash exacta, `act` no disponible en
este entorno) que `.github/workflows/actualizar_datos.yml` ya distingue
correctamente NO_NEW_DATA / SUCCESS / WARNING / OPTIONAL_COMPONENT_FAILURE /
CRITICAL_FAILURE desde la fase de hardening anterior. Sin cambios
adicionales al workflow esta fase — ya cumplía.

### P1 — Integridad de escritura (nuevo)

`scripts/io_atomico.py::guardar_parquet_atomico()` — escribe a un temporal
y reemplaza con `os.replace()` (atómico POSIX) solo si la escritura
completa sin error; si falla, el archivo productivo anterior queda
byte-a-byte intacto. Aplicado a los 10 sitios `to_parquet()` del pipeline
(balance, indicadores, camel, pyg, solvencia, entidades, 4×agregados).
Tests: `tests/test_actualizacion.py::EscrituraAtomicaTests` (3 tests:
escritura exitosa, fallo preserva el archivo anterior, fallo sin archivo
previo no deja nada a medio escribir).

### P1 — Crecimiento YoY centralizado

`pages/2_Balance_General.py::obtener_datos_heatmap_mensual()` ya no
reimplementa el cálculo — usa `analytics/crecimiento.py::calcular_crecimiento_yoy_mensual()`
(nueva función, misma fórmula). Equivalencia numérica exacta verificada
(`tests/test_riesgo_ampliado.py::CrecimientoYoYMensualTests`, 3 tests).

### P1 — FutureWarning de `pivot_table()`, auditado uno por uno

De los ~11 sitios restantes, solo 3 disparaban el warning en uso real
(`liquidez.py:45`, `stress_testing.py:73`, `solvencia.py:46` — operan sobre
datos `Categorical`); corregidos con `observed=True`, equivalencia de filas
verificada. Los otros 8 (`camels_score.py`, `alertas.py`,
`indices_ejecutivos.py`×5) operan sobre datos no categóricos — no disparan
el warning, no se tocaron.

### Tests

6 nuevos (3 `CrecimientoYoYMensualTests` + 3 `EscrituraAtomicaTests`).
116 → **122 tests, 330 subpruebas, 0 regresiones**.

### Sin cambios de commit

Ningún cambio de esta fase fue commiteado (instrucción explícita).
