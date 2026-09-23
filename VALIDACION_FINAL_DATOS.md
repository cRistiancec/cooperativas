# VALIDACIÓN FINAL DE DATOS

**Sistema Popular y Solidario — COSEDE**
Coordinación Técnica de Riesgos y Estudios · Eco. Cristian Coronel Quezada, MBA

| | |
|---|---|
| **Fecha de la validación** | 28 de julio de 2026 |
| **Alcance** | 16 páginas (Inicio + 15 módulos), 6 fuentes de datos, 4 segmentos |
| **Método** | Auditoría de código + ejecución real de todas las páginas (`streamlit.testing.AppTest`) + verificación numérica contra los parquet crudos |
| **Estado final** | ✅ **Apta para producción** |
| **Pruebas automatizadas** | 51 pruebas / 45 subpruebas — **todas en verde** |

> Las mejoras fueron **incrementales**: no se reconstruyó ningún módulo, no se
> alteró ninguna fórmula financiera ni prudencial, no se creó ninguna estructura
> paralela y no se modificó el diseño institucional. Todo lo añadido se apoyó en
> componentes que ya existían.

---

## 1. Estado de actualización

### 1.1 Inventario completo de fuentes

Se rastreó automáticamente todo el repositorio en busca de fuentes de datos.
**No existen archivos CSV, Feather, bases SQLite, DuckDB ni consultas SQL** en la
plataforma: la totalidad de la información se sirve desde Parquet, alimentados
por un ETL que consume archivos Excel (`.xlsm`) publicados por la SEPS.

| Fuente | Tipo | Modificado | Registros | Último período | Variables |
|---|---|---|---|---|---|
| `master_data/balance.parquet` | Parquet | 2026-07-21 | 24 169 638 | **2026-06-30** (102 meses desde 2018-01) | fecha, segmento, cooperativa, codigo, cuenta, valor |
| `master_data/pyg.parquet` | Parquet | 2026-07-21 | 2 359 861 | **2026-06-30** (78 meses desde 2020-01) | fecha, segmento, cooperativa, codigo, cuenta, valor_acumulado, valor_mes, valor_12m |
| `master_data/indicadores.parquet` | Parquet | 2026-07-21 | 603 312 | **2026-06-30** (78 meses desde 2020-01) | cooperativa, segmento, fecha, codigo, indicador, valor, categoria |
| `master_data/agg_metricas_sistema.parquet` | Parquet (agregado) | 2026-07-21 | 3 672 | **2026-06-30** (102 meses) | fecha, segmento, codigo, valor_total, num_cooperativas |
| `master_data/agg_ranking_cooperativas.parquet` | Parquet (agregado) | 2026-07-21 | 166 509 | **2026-06-30** (102 meses) | fecha, segmento, cooperativa, codigo, valor |
| `master_data/agg_series_temporales.parquet` | Parquet (agregado) | 2026-07-21 | 148 008 | **2026-06-30** (102 meses) | fecha, cooperativa, segmento, codigo, cuenta, valor |
| `master_data/agg_catalogo_cooperativas.parquet` | Parquet (agregado) | 2026-07-21 | 259 | corte único (último dato de cada institución) | cooperativa, segmento, activos_ultimo, ranking |
| `master_data/metadata*.json` | JSON (3 archivos) | 2026-07-21 | — | declaran 2026-06-30 | estadísticas de la corrida del ETL |

**Fuentes externas y procesos ETL:**

| Proceso | Archivo | Naturaleza |
|---|---|---|
| Descarga automática | `scripts/descargar_datos_seps.py` | Scraping del portal SEPS → ZIP anual de EEFF mensuales |
| Validación del ZIP | `scripts/seps_zip.py` | Verifica los 4 segmentos y una fecha de corte uniforme |
| ETL Balance | `scripts/procesar_balance_cooperativas.py` | `.xlsm` → `balance.parquet` |
| ETL Agregados | `scripts/generar_agregados.py` | `balance.parquet` → los 4 `agg_*.parquet` |
| ETL Indicadores / PyG / CAMEL | `scripts/procesar_indicadores.py`, `procesar_pyg.py`, `procesar_camel.py` | Pivot caches de la SEPS → `pyg.parquet`, `indicadores.parquet` |
| Guardia de regresión | `scripts/validar_actualizacion.py` | Aborta la publicación si el período no avanza o si se pierde historia |
| Orquestación | `.github/workflows/actualizar_datos.yml` | Programado los días 15, 18, 20 y 22 de cada mes |

No se detectaron APIs de terceros consumidas en tiempo de ejecución. La única
integración externa opcional es Claude (Anthropic) en el Asistente Inteligente,
que **no es fuente de datos**: no alimenta ningún indicador.

### 1.2 Último período disponible vs. período mostrado

| Concepto | Valor |
|---|---|
| **Último período disponible en las fuentes** | **Junio 2026 (2026-06-30)** |
| **Último período mostrado por la aplicación** | **Junio 2026 (2026-06-30)** |
| **Estado** | ✅ **SINCRONIZADO** — sin desfase |

Verificación página por página del valor por defecto del selector de período,
ejecutando cada módulo tal como lo vería el usuario:

| Módulo | Período por defecto | Estado |
|---|---|---|
| Inicio (KPIs ejecutivos) | Junio 2026 | ✅ |
| 1 · Panorama | 2026-06-30 | ✅ |
| 2 · Balance General | Junio 2026 (mes/año derivados de `fecha_max`) | ✅ |
| 3 · Pérdidas y Ganancias | Junio 2026 (mes/año derivados de `fecha_max`) | ✅ |
| 4 · Indicadores CAMEL | 2026-06-30 | ✅ |
| 5 · Riesgo de Liquidez | 2026-06-30 | ✅ |
| 6 · Riesgo de Crédito | 2026-06-30 | ✅ |
| 7 · Riesgo de Solvencia | 2026-06-30 | ✅ |
| 8 · Riesgo de Concentración | 2026-06-30 | ✅ |
| 9 · Riesgo Sistémico | 2026-06-30 | ✅ |
| 10 · CAMEL Score | 2026-06-30 | ✅ |
| 11 · Alertas Tempranas | 2026-06-30 | ✅ |
| 12 · Stress Testing | 2026-06-30 | ✅ |
| 13 · Modelos Predictivos | Serie completa hasta 2026-06-30 | ✅ |
| 14 · Machine Learning | 2026-06-30 | ✅ |
| 15 · Asistente Inteligente | `df["fecha"].max()` (dinámico) | ✅ |

**No se encontró ningún desfase tipo "el panel muestra diciembre 2025".** Se
revisaron específicamente rutas de archivo, archivos históricos, filtros fijos,
fechas hardcodeadas, caché, DataFrames antiguos, merges y funciones de carga: los
selectores derivan sus opciones de `sorted(fechas, reverse=True)` sobre los datos
y abren en `index=0`, de modo que el mes más reciente es siempre el primero.

### 1.3 Endurecimiento aplicado (para que nunca pueda desfasarse)

Aunque no había desfase, la fecha mostrada en la cabecera y en el home **provenía
de `metadata.json`**, un archivo estático. Si una corrida del ETL actualizara los
parquet sin regenerar ese JSON, la interfaz habría anunciado un mes anterior al
real. Se corrigió el origen del dato, sin tocar la lógica de negocio:

| Cambio | Archivo | Efecto |
|---|---|---|
| Nueva función `obtener_ultima_fecha()` — fuente única de verdad, derivada de los agregados | `utils/data_loader.py` | El período nunca se lee de un valor escrito a mano |
| Cabecera institucional "Datos al" pasa a usarla (con `metadata.json` solo como respaldo) | `ui/header.py` | La cabecera no puede quedar anclada a un mes anterior |
| KPI "Datos al" y "Período cubierto" del home pasan a usarla | `Inicio.py` | Ídem en el dashboard principal |
| Texto "histórico real (102 meses)" reemplazado por el largo real de la serie | `pages/13_Modelos_Predictivos.py` | Se actualiza solo al incorporar un mes nuevo |
| Docstring "Datos: ene 2018 - ene 2026 (97 meses)" (obsoleto) reemplazado por la regla de derivación | `utils/data_loader.py` | Documentación que no caduca |

**Resultado: en toda la plataforma no queda ninguna fecha de corte codificada
manualmente.**

---

## 2. Consistencia

### 2.1 ¿Todos los reportes usan la misma información?

**Sí.** La arquitectura ya era correcta: existe una única capa de acceso a datos
(`utils/data_loader.py`) y todos los módulos entran por ella. Se verificó
numéricamente, no solo por inspección:

| Verificación | Resultado |
|---|---|
| Activos del sistema en el home (vía agregados) **vs.** suma directa de la cuenta `1` en `balance.parquet` | **$31 530 M = $31 530 M** ✅ |
| KPIs del home (`obtener_serie_sistema`) **vs.** KPIs de Panorama (`obtener_metricas_kpi`) — activos, cartera, depósitos, patrimonio | Idénticos en los 4 ✅ |
| Suma del ranking completo de activos **vs.** KPI agregado del sistema | Idénticos ✅ |
| Nº de instituciones del KPI **vs.** instituciones distintas del ranking | Idénticos ✅ |
| Suma de los 4 segmentos **vs.** total "Todos" | $24 736 M + $1 457 M + $3 806 M + $1 530 M = **$31 530 M** ✅ |
| Catálogo de segmentos en las 5 fuentes que lo contienen | Idéntico en todas ✅ |

Estas comprobaciones quedaron **automatizadas** en
`tests/test_consistencia_datos.py`: si una corrida futura del ETL dejara una
fuente rezagada o un módulo empezara a leer de otro lado, las pruebas fallan.

### 2.2 Diferencias detectadas

| # | Hallazgo | Severidad | Estado |
|---|---|---|---|
| **D-1** | **Heatmap de Balance General ignoraba el filtro "Top 20".** El top-N se pedía a `agg_ranking_cooperativas.parquet`, que solo contiene **9 códigos** de nivel 1-2. Para cualquier cuenta de nivel 3 o 4 (de las 1 563 disponibles) la consulta devolvía vacío, la lista de instituciones quedaba en `[]` y el heatmap **dejaba de filtrar**: mostraba las ~203 instituciones aunque el selector dijera "Top 20". | Media — inconsistencia visible entre el filtro y lo mostrado, y 10× de trabajo de render | ✅ **Corregido** |
| **D-2** | **Cabecera y home dependían de `metadata.json`** para el período mostrado, en vez de los datos. | Baja — no producía error hoy, pero es la vía por la que aparecería un desfase | ✅ **Corregido** |
| **D-3** | **`Inicio.py` definía su propio `obtener_metadata()`**, duplicando `cargar_metadata()` de `utils/data_loader.py` y releyendo el JSON sin caché en cada rerun. | Baja — función duplicada | ✅ **Corregido** |
| **D-4** | **Cuatro criterios distintos de truncamiento de nombres** conviviendo (`[:25]+'...'`, `[:30]+'...'`, cabeza+cola en CAMEL, sin truncar en las páginas de riesgo): la misma institución aparecía etiquetada distinto según el módulo. | Baja — inconsistencia de presentación | ✅ **Corregido** |
| **D-5** | `metadata_indicadores.json` declara `cooperativas: 212` y `registros_totales: 1 503 183`, mientras `indicadores.parquet` tiene 231 instituciones históricas y 603 312 filas. Son **estadísticas de la corrida del ETL** (conteos previos al filtrado), no del dataset publicado. **Ningún módulo de la aplicación lee ese archivo** — solo lo escriben los scripts. | Nula — sin impacto en la interfaz | ⚠️ **Documentado**, sin cambio |
| **D-6** | `pyg.parquet` contiene 4 filas `VT_TOTAL *` (totales por segmento provistos por la SEPS). Auditado: el módulo de PyG **ya las excluye** correctamente en el ranking, en el total del sistema y en el listado de instituciones. `balance.parquet` e `indicadores.parquet` no las contienen. | Nula — ya estaba bien resuelto | ✅ **Verificado, sin cambio** |

### 2.3 Correcciones realizadas

**D-1 — Heatmap de Balance General**
El respaldo reutiliza `obtener_valores_cooperativas_mes()`, la misma función que
ya emplea la sección de ranking de esa página, sobre el balance que **ya está
cargado en memoria**. No se creó ninguna consulta ni estructura nueva.

Efecto medido sobre la cuenta `1401` con el selector en "Top 20":

| | Antes | Después |
|---|---|---|
| Instituciones mostradas | 203 (el filtro no se aplicaba) | **20** (lo que pide el selector) |
| Celdas renderizadas | 6 090 | **600** (−90 %) |
| Altura del gráfico | 4 466 px | **520 px** |

**D-2 / D-3 / D-4** — descritas en 1.3 y en la sección 5.

---

## 3. Segmentación

### 3.1 Variable encontrada

✅ **Sí existe.** La columna **`segmento`** está presente en las 5 fuentes que la
requieren (`balance`, `pyg`, `indicadores`, `agg_ranking`, `agg_catalogo`), con
un catálogo **idéntico** en todas ellas y **sin valores nulos**.

### 3.2 Segmentos identificados

| Segmento | Instituciones (jun-2026) | Activos (jun-2026) | Criterio SEPS |
|---|---|---|---|
| SEGMENTO 1 | 44 | $24 736 M | Activos > $80 millones |
| SEGMENTO 2 | 64 | $3 806 M | Activos $20 – $80 millones |
| SEGMENTO 3 | 91 | $1 530 M | Activos $5 – $20 millones |
| SEGMENTO 1 MUTUALISTA | 4 | $1 457 M | Mutualistas de ahorro y crédito |
| **Total** | **203** | **$31 530 M** | |

> **Limitación documentada — no existen Segmentos 4 y 5.** El universo cubierto
> por esta plataforma es el de las entidades cuyos depósitos están cubiertos por
> el seguro que administra COSEDE y cuyos estados financieros mensuales publica
> la SEPS: segmentos 1, 2, 3 y mutualistas. Los segmentos 4 y 5 **no aparecen en
> la fuente oficial** y por tanto no pueden incorporarse ni derivarse. No se trata
> de un dato faltante en el ETL, sino del alcance real de la publicación de la
> SEPS.

### 3.3 Mejoras implementadas

Cobertura del filtro por segmento **antes** y **después** de esta validación:

| Módulo | Antes | Después |
|---|---|---|
| **Inicio — dashboard principal / KPIs** | ❌ sin filtro | ✅ **añadido** |
| 1 · Panorama (KPIs, rankings, treemaps, crecimiento) | ✅ | ✅ |
| 2 · Balance General (comparativos, heatmap, ranking) | ✅ | ✅ |
| 3 · Pérdidas y Ganancias | ✅ | ✅ |
| 4 · Indicadores CAMEL | ✅ | ✅ |
| 5–9 · Riesgos (Liquidez, Crédito, Solvencia, Concentración, Sistémico) | ✅ | ✅ |
| 10 · CAMEL Score · 11 · Alertas · 12 · Stress Testing | ✅ | ✅ |
| **13 · Modelos Predictivos — forecast ARIMA** | ❌ sin filtro (solo lo tenía la proyección de morosidad) | ✅ **añadido** |
| 14 · Machine Learning | ✅ | ✅ |
| 15 · Asistente Inteligente | n/a (chat, sin cortes) | n/a |

Ambas incorporaciones **reutilizan la infraestructura existente**: el catálogo
viene de `obtener_segmentos_disponibles_rapido()` y la agregación de
`obtener_serie_sistema(codigo, segmento)` — a la que solo se le añadió un
parámetro opcional con valor por defecto `"Todos"`, que reproduce exactamente el
comportamiento anterior. No se duplicó ninguna función ni DataFrame.

**Validado funcionalmente:** al filtrar el home por cada segmento, los activos
son $24 736 M / $1 457 M / $3 806 M / $1 530 M, que **suman el total del sistema**
($31 530 M) — el filtro particiona los datos sin duplicar ni perder registros.
En Modelos Predictivos, el forecast se ejecutó sin excepción para los 4 segmentos.

---

## 4. Comparativos ("Cooperativas a Comparar")

### 4.1 Problemas encontrados

| # | Problema | Dónde |
|---|---|---|
| **C-1** | **Leyenda superpuesta.** Con leyenda horizontal, nombres largos y un margen inferior **fijo de 80 px**, al seleccionar varias instituciones las entradas se envolvían en 3-4 filas que invadían el título del eje X y quedaban recortadas. | Balance General, Pérdidas y Ganancias, CAMEL |
| **C-2** | **Etiquetas del eje Y superpuestas.** Cinco páginas de riesgo llamaban a `crear_ranking_barras()` con **30 instituciones y la altura por defecto de 400 px**: ~13 px por etiqueta con fuente de 12 px — solape garantizado. | Liquidez, Crédito, Solvencia, Sistémico, CAMEL Score |
| **C-3** | **Nombres completos sin truncar** (hasta 46 caracteres) comiéndose el área de trazado en rankings y heatmaps. | Panorama, Balance General, Concentración, Crédito, CAMEL Score, Alertas, Stress |
| **C-4** | **Etiquetas de valor recortadas**: `textposition='outside'` con margen derecho de 10 px. | Todos los rankings horizontales |
| **C-5** | **Riesgo de fusión silenciosa de instituciones**: dos cooperativas cuyo nombre truncado coincidiera se habrían colapsado en una sola categoría de Plotly, y una de las dos barras habría desaparecido. | Cualquier gráfico con etiquetas truncadas |

### 4.2 Ajustes realizados

Se añadieron **tres componentes compartidos** en `utils/charts.py` — no una
capa nueva, sino la consolidación de la lógica que ya estaba dispersa:

| Componente | Qué resuelve |
|---|---|
| `truncar_nombre()` | Truncamiento **único** para toda la plataforma (promovido desde CAMEL, que ya tenía la mejor versión: conserva inicio **y** final, lo que permite distinguir instituciones con prefijos comunes). Sustituye los 4 criterios que convivían. |
| `truncar_nombres_unicos()` | Garantiza que dos instituciones **jamás** produzcan la misma etiqueta (C-5). Ante una colisión conserva el nombre completo. |
| `altura_por_categorias()` | Altura que da espacio propio a cada etiqueta. Sustituye los `max(400, n*22)` repetidos en 8 páginas. |
| `layout_leyenda_series()` | Leyenda y margen inferior que **escalan** con el número de series comparadas. |

Aplicado con: **rotación inteligente** (`tickangle` + `automargin` en heatmaps),
**truncamiento** consistente, **ajuste dinámico** de altura y margen,
**tooltips completos** (el nombre íntegro viaja en `customdata`, nunca se pierde
información) y **escalamiento automático** (`cliponaxis=False`, `automargin`,
fuente de ejes a 10 px).

### 4.3 Estado final — medido

**Ranking con 30 instituciones** (caso que se solapaba):

| Métrica | Antes | Después |
|---|---|---|
| Altura del gráfico | 400 px | **740 px** |
| Espacio vertical por etiqueta | **13,3 px** (fuente 12 px → solape) | **24,7 px** (fuente 10 px) |
| Largo máximo de etiqueta | 46 caracteres | **30 caracteres** |
| Margen derecho | 10 px (valores recortados) | **70 px** |
| Etiquetas únicas | — | **30/30** (sin fusión) |
| Nombre completo | se perdía al truncar | **preservado en el tooltip** |

**Comparativo de series:**

| Series | Filas de leyenda | Margen inferior (antes → después) |
|---|---|---|
| 4 | 2 | 80 px → **104 px** |
| 8 | 3 | 80 px → **126 px** |
| 10 (máximo) | 4 | 80 px → **148 px** |

Largo máximo de etiqueta en la leyenda: 37 → **30 caracteres**.

✅ **Ningún texto se superpone**, incluso con las 10 cooperativas que permite el
selector, y la visualización mantiene el aspecto institucional (paleta, tema
oscuro y tipografía intactos). Verificado además sobre el **catálogo real
completo** (259 instituciones): el truncamiento no colapsa ninguna.

---

## 5. Rendimiento

### 5.1 Tiempos de carga y consumo (medidos tras las mejoras)

Ejecución real de cada página con `AppTest`, midiendo tiempo de extremo a extremo
y pico de memoria residente del proceso:

| Módulo | Tiempo | Pico RSS | Gráficos | Excepciones |
|---|---|---|---|---|
| Inicio | 0,90 s | 167 MB | 5 | — |
| 1 · Panorama | 1,29 s | 186 MB | 6 | — |
| 2 · Balance General | 17,16 s | 2 651 MB | 3 | — |
| 3 · Pérdidas y Ganancias | 2,03 s | 663 MB | 2 | — |
| 4 · Indicadores CAMEL | 2,23 s | 382 MB | 3 | — |
| 5 · Riesgo de Liquidez | 2,09 s | 432 MB | 4 | — |
| 6 · Riesgo de Crédito | 3,13 s | 468 MB | 5 | — |
| 7 · Riesgo de Solvencia | 1,91 s | 438 MB | 3 | — |
| 8 · Riesgo de Concentración | 1,02 s | 185 MB | 3 | — |
| 9 · Riesgo Sistémico | 1,25 s | 247 MB | 2 | — |
| 10 · CAMEL Score | 1,73 s | 384 MB | 3 | — |
| 11 · Alertas Tempranas | 1,76 s | 384 MB | 2 | — |
| 12 · Stress Testing | 1,22 s | 247 MB | 3 | — |
| 13 · Modelos Predictivos | 12,04 s | 469 MB | 3 | — |
| 14 · Machine Learning | 3,63 s | 437 MB | 2 | — |
| 15 · Asistente Inteligente | 1,62 s | 377 MB | 0 | — |

**14 de 16 páginas cargan en menos de 4 segundos.** Las dos excepciones son
estructurales y están justificadas, no son regresiones:

- **Balance General (17 s / 2,6 GB)** — es la única página que necesita
  `balance.parquet` completo (24,17 M filas), porque permite navegar las 1 563
  cuentas contables en 4 niveles; los agregados solo contienen 9 códigos. Ya usa
  lectura por columnas y `self_destruct=True`.
- **Modelos Predictivos (12 s)** — entrena ARIMA y Random Forest **en tiempo
  real** sobre datos reales, con backtest honesto. El costo es el entrenamiento,
  no la carga de datos.

**Nota de honestidad metodológica:** no se dispone de una medición equivalente
"antes" tomada en el mismo entorno y en la misma sesión, por lo que **no se
reportan porcentajes de mejora globales**. Las cifras anteriores son el estado
final absoluto; lo que sí se midió de forma controlada, con el mismo dato y el
mismo proceso, es el efecto puntual de D-1 (tabla de la sección 2.3).

### 5.2 Mejoras implementadas

| Mejora | Efecto |
|---|---|
| **Heatmap de Balance General filtra realmente al Top-N** (D-1) | −90 % de celdas renderizadas y gráfico de 4 466 px → 520 px en cuentas de nivel 3-4 |
| **Eliminada la lectura de JSON sin caché** en cada rerun del home (D-3) | `cargar_metadata()` (cacheada) reemplaza a la función duplicada |
| **Eliminadas 2 de 6 llamadas** a `obtener_serie_sistema` en el home | Las series de cartera (`14`) y depósitos (`21`) ya obtenidas para los KPIs se **reutilizan** en el gauge de intermediación en vez de volver a pedirse |
| **Consolidación de 4 criterios de truncamiento y 8 cálculos de altura** en componentes compartidos | Menos código repetido; un solo lugar donde ajustar la legibilidad |

### 5.3 Optimización evaluada y **descartada** con evidencia

Se evaluó convertir `segmento` y `cooperativa` a `category` en `cargar_balance()`
(como ya hace `cargar_pyg()`), esperando un ahorro de memoria sobre 24 M de filas.
**Medición:** ambas columnas **ya llegan codificadas como `category`** desde
PyArrow (vienen dictionary-encoded en el Parquet). Memoria del DataFrame: 556,3 MB
antes y 556,3 MB después — **ganancia nula**. El cambio se descartó en lugar de
aplicarlo por analogía: habría añadido código sin ningún beneficio.

### 5.4 Verificación de que las mejoras no encarecieron el sistema

- **Caché:** no se eliminó ni se invalidó ninguna caché existente. La única firma
  modificada (`obtener_serie_sistema`) recibió un parámetro **opcional**, de modo
  que la clave de caché del uso previo (`"Todos"`) no cambia.
- **Sin nuevas cargas de datos:** los dos filtros por segmento añadidos consultan
  agregados **ya cargados** (`agg_metricas_sistema`, 45 KB); no abren ningún
  archivo adicional.
- **Sin DataFrames duplicados:** el respaldo del heatmap opera sobre el
  `df_balance` que la página ya tiene en memoria.
- **Coste de los gráficos más altos:** los rankings pasan de 400 a 740 px con 30
  instituciones. Es más DOM, pero **menos** trabajo total que antes en el caso
  D-1 (−90 % de celdas). El balance neto de render es favorable.

---

## 6. Validación funcional

Se recorrieron **las 16 páginas** ejecutándolas realmente, no solo compilándolas.

| Verificación | Resultado |
|---|---|
| **Navegación** — las 16 páginas cargan | ✅ **0 excepciones** |
| **Gráficos** — cada página produce sus visualizaciones | ✅ 49 gráficos Plotly en total |
| **KPIs** — presentes y cuadrados contra la fuente | ✅ |
| **Tablas** — `st.dataframe` en Stress Testing, Modelos Predictivos, ML | ✅ |
| **Filtros de segmento** — los 4 segmentos en cada página que lo ofrece | ✅ sin excepción |
| **Filtros de fecha** — los 102 / 78 períodos disponibles | ✅ |
| **Comparativos** — 10 cooperativas (máximo) en Balance General y PyG | ✅ sin excepción |
| **Modos de visualización** — Absoluto / Indexado / Participación en PyG | ✅ los 3 |
| **Jerarquía de cuentas** — niveles 1→4 en Balance General, incluida la ruta que fallaba (`1101 - Caja`) | ✅ sin excepción ni advertencia |
| **Escenarios de estrés** — Base / Moderado / Severo / Extremo | ✅ |
| **Exportaciones** — PNG desde la barra de herramientas de cada gráfico | ✅ disponible |
| **Mapas** — treemaps jerárquicos de activos y de pasivos/patrimonio | ✅ |
| **Asistente IA** — modo local determinístico sin clave configurada | ✅ |

> **Mapas geográficos:** la plataforma no incluye cartografía. Los "mapas" son
> **mapas de mercado** (treemaps), que sí están presentes y operativos. Los
> archivos de la SEPS no incluyen la ubicación geográfica de las oficinas, por lo
> que un mapa territorial no es construible con la fuente actual.

### 6.1 Pruebas automatizadas

```
51 passed, 45 subtests passed
```

| Archivo | Pruebas | Cubre |
|---|---|---|
| `tests/test_consistencia_datos.py` | **17 (nuevo)** | Fases 1-5: período único entre fuentes, cuadre de KPIs contra el parquet crudo, partición por segmento, catálogo de segmentos, no-fusión de etiquetas, período por defecto de cada página |
| `tests/test_smoke_pages.py` | 9 | Carga de las 15 páginas ligeras, KPIs, filtros, gráficos, umbrales de tiempo |
| `tests/test_analytics.py` | 14 | Indicadores de riesgo y concentración |
| `tests/test_models.py` | 5 | Forecast ARIMA y predicción de morosidad |
| `tests/test_actualizacion.py` | 6 | Inspección del ZIP de la SEPS e incrementalidad del ETL |

`tests/test_consistencia_datos.py` es la **guardia permanente** de esta
validación: se ejecuta contra los datos reales de producción y falla si una
corrida futura del ETL deja una fuente rezagada, si un módulo empieza a leer de
otra fuente o si un gráfico vuelve a colapsar dos instituciones en una etiqueta.

---

## 7. Checklist

| Criterio | Estado |
|---|---|
| Datos actualizados automáticamente | ✅ |
| Último período disponible utilizado | ✅ |
| KPIs consistentes | ✅ |
| Gráficos consistentes | ✅ |
| Tablas consistentes | ✅ |
| Reportes consistentes | ✅ |
| Segmentación incorporada | ✅ |
| Filtro por segmento | ✅ |
| Comparativo optimizado | ✅ |
| Sin sobreposición de textos | ✅ |
| Sin reprocesos | ✅ |
| Consumo optimizado | ✅ |
| Aplicación lista para producción | ✅ |

---

## 8. Cumplimiento de restricciones

| Restricción | Cumplimiento |
|---|---|
| No modificar la lógica de negocio | ✅ Ninguna regla de negocio alterada |
| No cambiar cálculos financieros | ✅ Ni una sola fórmula tocada: `analytics/` y `models/` quedaron **sin modificar** |
| No eliminar funcionalidades existentes | ✅ Solo se añadieron dos filtros; nada se retiró |
| No generar estructuras paralelas | ✅ Los componentes nuevos viven en `utils/charts.py` y `utils/data_loader.py`, los módulos que ya existían |
| No crear procesos nuevos si los actuales sirven | ✅ El respaldo del heatmap reutiliza `obtener_valores_cooperativas_mes()`; el filtro por segmento reutiliza `obtener_serie_sistema()` |
| No afectar el diseño institucional | ✅ `styles/`, `ui/theme.py`, `.streamlit/config.toml`, paleta y tipografía **sin cambios** |
| Priorizar reutilización y eficiencia | ✅ Se **eliminó** una función duplicada, se **unificaron** 4 criterios de truncamiento y 8 cálculos de altura, y se **descartó** una optimización que la medición demostró inútil |

### Archivos modificados

**Datos y componentes compartidos**
`utils/data_loader.py` · `utils/charts.py` · `ui/header.py`

**Páginas**
`Inicio.py` · `pages/1_Panorama.py` · `pages/2_Balance_General.py` ·
`pages/3_Perdidas_Ganancias.py` · `pages/4_CAMEL.py` · `pages/6_Riesgo_Credito.py` ·
`pages/8_Riesgo_Concentracion.py` · `pages/10_CAMEL_Score.py` ·
`pages/11_Alertas_Tempranas.py` · `pages/12_Stress_Testing.py` ·
`pages/13_Modelos_Predictivos.py`

**Pruebas**
`tests/test_consistencia_datos.py` *(nuevo)*

**Sin modificar:** `analytics/` · `models/` · `config/` · `services/` · `styles/` ·
`ui/theme.py` · `ui/sidebar.py` · `scripts/` · `.streamlit/config.toml` ·
`master_data/`

---

## 9. Conclusión

La plataforma **ya estaba correctamente sincronizada** con la fuente más
reciente: no existía el desfase de período que motivó la revisión. Los datos de
las seis fuentes llegan a **junio de 2026** y las dieciséis páginas abren en ese
período.

El trabajo consistió, por tanto, en **verificar exhaustivamente esa afirmación con
evidencia numérica**, **eliminar las vías por las que un desfase podría aparecer
en el futuro** (ninguna fecha de corte queda ya codificada manualmente),
**corregir una inconsistencia real** entre el filtro "Top 20" y lo que mostraba el
heatmap de Balance General, **completar la segmentación** en los dos módulos que
no la ofrecían, **resolver la superposición de etiquetas** con componentes
compartidos, y **dejar instalada una guardia automatizada** que hará fallar la
suite si cualquiera de estas propiedades se rompe.

**Estado: apto para producción.**

---

*Documento generado como parte de la validación final de datos.
COSEDE — Coordinación Técnica de Riesgos y Estudios.*
