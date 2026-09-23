# AUDITORÍA — MOTOR CENTRAL DE INDICADORES

**Sistema Popular y Solidario — COSEDE**
Fase 1 del pedido "Motor Central de Indicadores": auditoría completa, sin implementación.

| | |
|---|---|
| **Fecha** | 28 de julio de 2026 |
| **Insumo** | `INDICADORES BANCOS.R` (script institucional, 150 fórmulas) + todo el código Python del proyecto |
| **Método** | Extracción programática de las 150 asignaciones `mutate()` del R (parser de paréntesis balanceados, no lectura superficial) + cruce automático contra los códigos de cuenta reales de `balance.parquet` y `pyg.parquet` + lectura completa de `analytics/`, `models/`, `config/`, `scripts/procesar_*.py` |
| **Estado** | ✅ Auditoría completa — **sin cambios de código todavía**, según lo solicitado |

---

## Hallazgo central (condiciona todo lo demás)

**El script R fue escrito para BANCOS (Superintendencia de Bancos), no para cooperativas (SEPS).**

Evidencia, no interpretación:
- La ruta de trabajo del script es `.../RIESGO DE CREDITO/BOLETIN DE ECONOMIA Y BANCA/...`.
- La fuente es `BASES BALANCES BANCOS HISTORICO.txt`, con la variable `INST_ABRV` (abreviatura de banco).
- Los comentarios del propio script marcan explícitamente varios bloques como **"Refinanciado COVID"** y **"Reestructurado COVID"** — una estructura de cuentas transitoria 2020-2021 que la Superintendencia de Bancos exigió a la banca.

La plataforma actual, en cambio, consume boletines de la **SEPS** (cooperativas de ahorro y crédito, segmentos 1-3 y mutualistas). Ambos reguladores comparten familia de Catálogo Único de Cuentas ecuatoriano — por eso la mayoría de las cuentas SÍ coinciden — pero **no son el mismo catálogo**, y donde divergen, divergen exactamente en el bloque COVID.

**Verificación cuantitativa** (no una suposición): de los 236 códigos de cuenta (`CTA_XXXXX`) que referencia el script R, se buscó cada uno, literal, en `balance.parquet` y `pyg.parquet` (24,17M + 2,36M registros reales):

| | Cantidad | % |
|---|---|---|
| Códigos del R presentes en `balance.parquet` | 186 | 79% |
| Códigos del R presentes en `pyg.parquet` | 14 | 6% |
| **Códigos del R que NO existen en ningún archivo** | **50** | **21%** |

Los 50 códigos faltantes son, sin excepción, del rango `1491xx`–`1496xx` (el desglose COVID: refinanciado/reestructurado × por-vencer/no-devenga/vencida × línea de negocio) más dos códigos sueltos (`260505`, `260510`) que tampoco existen en el catálogo actual. El catálogo de cooperativas usa en su lugar una estructura **más simple y vigente**: `149905`–`149989` (provisión por línea de negocio + provisión genérica/anticíclica/voluntaria), sin el cruce COVID.

**Efecto en cascada:** de las 150 fórmulas del R, **49 dependen directamente de esas cuentas faltantes**, y otras que dependen de esas 49 (morosidad y participación por línea de negocio detallada: `MORACOM`, `PARTCOM`, `COBCOM`, `TCOMA`, `TCONA`, etc.) heredan la misma limitación. **No es un defecto del proyecto Python — es que la información que esas fórmulas piden no existe en lo que la SEPS publica para cooperativas.**

---

## Matriz de auditoría

### Categoría 1 — Ya existe en Python, con fuente MEJOR que el script R (13 dominios)

La plataforma no calcula estos indicadores en Python: los toma **pre-calculados y publicados oficialmente por la SEPS** (`indicadores.parquet`, extraído del pivot cache de la hoja "5. INDICADORES FINANCIEROS" de cada boletín — ver `scripts/procesar_camel.py`). Son cifras auditadas por el regulador, no una reconstrucción propia — una fuente **más autoritativa** que recalcular desde cuentas crudas.

| Indicador R | Código SEPS ya en `indicadores.parquet` | Dónde se usa en Python |
|---|---|---|
| `MORA`, `MORACOM`…`MORACONSORD` | `MOR_TOT`, `MOR_CONS`, `MOR_INMOB`, `MOR_MICRO`, `MOR_PROD`, `MOR_VIV_IP`, `MOR_EDU` | `analytics/credito.py`, `pages/6_Riesgo_Credito.py`, `pages/4_CAMEL.py` |
| `COBCOM`…`COBCARTOT` | `COB_TOT`, `COB_CONS`, `COB_INMOB`, `COB_MICRO`, `COB_PROD`, `COB_VIV_IP`, `COB_EDU` | ídem |
| `ROE`, `ROA` (versión R, manual) | `ROE`, `ROA` (oficial SEPS) | `analytics/camels_score.py`, `models/prediccion_morosidad.py`, `models/anomalias.py` |
| — (no existe en el R) | `SUF_PAT`, `FK`, `FI`, `CAP_NETO`, `VULN_PAT`, `CART_IMPR_PAT` | `analytics/solvencia.py`, `analytics/camels_score.py` |
| `GOP_AP` | `GO_ACT`, `GO_MNF`, `GP_ACT` | `analytics/camels_score.py`, `config/indicator_mapping.py` |
| `LIQ_INM` | `LIQ` (oficial SEPS, fórmula equivalente) | `analytics/liquidez.py` |
| `PARTCOM`…`PARTMICRO` | — (no publicado por SEPS a este nivel; ver Categoría 3) | — |

**Decisión metodológica que propone esta auditoría** (a confirmar con el usuario en la Fase 2): para la familia morosidad/cobertura/rentabilidad/capital, **no recalcular desde cero** — seguir consumiendo el dato oficial SEPS. Recalcularlo desde cuentas crudas cooperativas sería (a) redundante, (b) imposible de auditar contra el número que la SEPS realmente publicó, y (c) en el caso de varias líneas de cartera, **imposible por falta de cuentas** (Categoría 2).

### Categoría 2 — No computable con los datos de cooperativas (49 fórmulas)

Bloque "cartera bruta y cartera improductiva por línea de negocio detallada + refinanciada/reestructurada COVID". Lista completa (nombres del R):

```
CBCOM, CBCONS, CBINMVIV, CBMICRO, CBCOMPRI, CBPRODUCTIVO, CBCONSPRI, CBCOMORD,
CBCONSORD, CBINMOB, CIMPCOM, CIMPCONS, CIMPINMVIV, CIMPMICRO, CIMPCOMPRI,
CIMPCOMORD, CIMPPROD, CIMPCONSPRI, CIMPCONSORD, CIMPINM, CIMPTOT,
CONS_REF_PORVENCER, CONS_REF_NODEVENGA, CONS_REF_VENCIDA, CONS_RES_PORVENCER,
CONS_RES_NODEVENGA, CONS_RES_VENCIDA, CARTERA_RES_COM_PRI/PROD/ORD/TOT,
CARTERA_REF_COM_PRI/PROD/ORD/TOT, CONS_REF_RES_COVID, COM_REF_RES_COVID,
INM_REF_RES_COVID, MICRO_REF_RES_COVID, CTOT_REF_RES_COVID,
CIMP_*_REF_RES_COVID (5 variantes), MORA_*_REF_RES_COVID (5 variantes),
LIQ_1RA, LIQ_2DA
```

**Recomendación**: marcar explícitamente como **"No aplicable — la SEPS no reporta este desglose para cooperativas"**, siguiendo el mismo patrón de limitación declarada que ya usa `analytics/credito.py` para vintage curves. No inventar una aproximación. `LIQ_1RA`/`LIQ_2DA` son un caso aparte (ver Categoría 4).

### Categoría 3 — Computable, y NO existe todavía en Python (32 fórmulas nuevas)

Estas SÍ tienen todas sus cuentas presentes en `balance.parquet`/`pyg.parquet` y no están duplicadas en ningún módulo actual:

| Fórmula R | Qué mide | Prioridad propuesta | Nota |
|---|---|---|---|
| `TASA_PI` | Tasa pasiva implícita (interés causado / depósitos, anualizado) | Alta | Insumo directo para `TASA_MF` (spread) |
| `TASA_AI` | Tasa activa implícita (interés ganado / cartera, anualizado) | Alta | ídem |
| `TASA_MF` | Spread de tasas (activa − pasiva) | Alta | Indicador de rentabilidad estructural, no está en CAMEL SEPS |
| `MARGEN_FINANCIERO` | Ingresos financieros netos de gastos financieros | Media | Insumo de `GO_MNF` oficial, pero útil como cifra en dólares |
| `ROE_ADJ` | ROE ajustado por partidas no recurrentes (usa cuenta `3603`, utilidad del ejercicio) | Media | Complementa el ROE oficial |
| `CAPGA`, `TCAPGA`, `CAPGM`, `TCAPGM` | Crecimiento absoluto/% de captaciones (anual/mensual) | Alta | Ya existe crecimiento de depósitos ad-hoc en Panorama; formalizarlo |
| `COLGA`, `TCOLGA`, `COLGM`, `TCOLGM` | Crecimiento absoluto/% de colocaciones (cartera bruta total) | Alta | ídem, sobre cartera |
| `CER` | Variación anual de cartera en riesgo (Σ improductiva sin desglose COVID) | Media | Computable con las cuentas base (sin el aditivo COVID) |
| `Perc10*/Perc90*` (7 pares) | Bandas de percentil 10-90 por fecha, para benchmarking de pares | Alta | **Patrón transversal reutilizable** — ver Fase 4 |
| `PROVCOM`…`PROVTOT` (11 variantes) | Provisión por línea de negocio (desde cuentas de provisión + gasto de provisión) | Baja | La SEPS ya publica cobertura oficial; esto es el desglose en dólares |
| `GOP_AP`, `INTERM_FIN` | Gastos operativos/activo promedio (versión propia), intermediación financiera | Baja | Ya existen equivalentes oficiales (`GO_ACT`); valor marginal de recalcular |

### Categoría 4 — Requiere adaptación antes de migrar (no migración literal)

| Fórmula | Problema encontrado | Recomendación |
|---|---|---|
| `LIQ_1RA`, `LIQ_2DA` | Referencian `CTA_260505`/`CTA_260510`, que **no existen en ningún catálogo verificado** (ni banco ni cooperativa, en los datos disponibles) — posible resabio de una versión anterior del catálogo bancario. | Adaptar la fórmula usando el rango `2605` real vigente (`260505`→ojo, no existe; el rango real es `2606`, "Obligaciones con entidades financieras del sector público") **o** excluir esos dos sumandos con nota metodológica. Requiere validación de un analista de riesgos antes de publicar el número — no es una decisión que deba tomar unilateralmente el motor de cálculo. |
| `MORA`, `COBCARTOT`, `Percentil*COBCART` | Dependen de `CIMPTOT`, que a su vez depende del bloque COVID (Categoría 2) | Usar `MOR_TOT`/`COB_TOT` oficiales de la SEPS (Categoría 1) en su lugar; no intentar reconstruir el agregado desde cuentas incompletas. |

### Categoría 5 — Bug real encontrado en el script R institucional

**`COBINM` se define dos veces con fórmulas distintas, y la segunda pisa a la primera silenciosamente:**

```r
mutate(COBINM = PROVINMVIV / CIMPINMVIV) %>%   # Cobertura INMOBILIARIA
mutate(COBINM = PROVMICRO / CIMPMICRO) %>%     # Cobertura MICROCRÉDITO — sobrescribe la anterior
```

El comentario dice "Cobertura de cartera microcrédito" pero la variable de salida sigue llamándose `COBINM` (inmobiliaria). En el reporte final del R, la columna que debería contener cobertura inmobiliaria en realidad contiene cobertura de microcrédito, y **la cobertura inmobiliaria nunca se exporta**. Esto no se replicará al migrar — se documenta aquí para que Riesgos y Estudios lo sepa, y porque es evidencia de que la migración a Python (con nombres explícitos por línea de negocio, como ya hace `analytics/credito.py::CARTERAS_COBERTURA`) es una mejora real de calidad, no solo un cambio de lenguaje.

Adicionalmente: el bloque completo "CARTERA REFINANCIADA Y REESTRUCTURADA COVID" (`CONS_REF_RES_COVID`, `COM_REF_RES_COVID`, `INM_REF_RES_COVID`, `MICRO_REF_RES_COVID`, `CTOT_REF_RES_COVID`) y el bloque "CARTERA IMPRODUCTIVA REFINANCIADA Y REESTRUCTURADA COVID" **están copiados y pegados dos veces, de forma idéntica**, en el script (líneas ~250-290). No cambia el resultado (la segunda ejecución sobrescribe con el mismo valor), pero es trabajo duplicado en el propio R.

### Categoría 6 — Indicadores oficiales de la SEPS que YA están en los datos pero son invisibles en la UI

Se cruzaron los 41 códigos únicos realmente presentes en `indicadores.parquet` contra los 28 códigos que `config/indicator_mapping.py::GRUPOS_INDICADORES` expone en el selector de la página CAMEL. **13 códigos existen en los datos, tienen `codigo`/`indicador`/`categoria` completos, y no aparecen en ningún dropdown ni gráfico:**

| Código | Nombre oficial SEPS (`procesar_camel.py`) | Estado actual |
|---|---|---|
| `SUF_PAT` | Suficiencia Patrimonial | Usado en `analytics/solvencia.py` y `camels_score.py`, pero invisible en el dropdown de la página CAMEL (no está en `GRUPOS_INDICADORES`) |
| `CART_REF` | Carteras de Créditos Refinanciadas | Sin etiqueta, sin grupo — completamente invisible |
| `CART_REEST` | Carteras de Créditos Reestructuradas | ídem |
| `CART_VENCER` | Cartera por Vencer Total | ídem |
| `INTERM` | Intermediación Financiera | Tiene etiqueta (`ETIQUETAS_INDICADORES`) pero no está agrupado — invisible en el selector |
| `MARG_PAT`, `MARG_ACT` | Margen de Intermediación / Patrimonio, / Activo | ídem |
| `REND_CONS`, `REND_INMOB`, `REND_MICRO`, `REND_PROD`, `REND_VIV`, `REND_EDU` | Rendimiento de cartera por línea de negocio (6 indicadores) | ídem |

Esto es **trabajo cero de cálculo** (la SEPS ya lo publica, el ETL ya lo extrae) — solo falta agregarlos a `GRUPOS_INDICADORES` y, para los 3 sin etiqueta, a `ETIQUETAS_INDICADORES`. Es la mejora de mayor retorno por esfuerzo de toda esta auditoría.

---

## Arquitectura actual (para no reconstruir lo que ya funciona)

```
master_data/indicadores.parquet   ← SEPS ya calculó MOR_*, COB_*, ROE, ROA, FK, FI, CAP_NETO, etc.
master_data/balance.parquet       ← cuentas crudas (activos, pasivos, patrimonio, cartera por código)
master_data/pyg.parquet           ← cuentas de resultados, YA con valor_12m (rolling 12 meses)
        │
        ▼
analytics/liquidez.py, credito.py, solvencia.py, concentracion.py,
sistemico.py, camels_score.py, alertas.py, stress_testing.py
        │  (funciones puras: reciben DataFrame + fecha + segmento, devuelven DataFrame)
        ▼
pages/*.py  (leen, filtran por Filtro Global de Segmento, grafican)
        │
        ▼
models/*.py  (forecast.py, prediccion_morosidad.py, clustering.py, anomalias.py
              consumen directamente los códigos de indicadores.parquet — sin recalcular nada)
```

**Hallazgo de arquitectura, no de fórmulas**: `pyg.parquet` ya trae `valor_12m` (suma móvil de 12 meses) **pre-calculada en el ETL**, una sola vez por corrida. El script R recalcula esa misma ventana móvil manualmente (`UTILM` = delta mensual, `SUM_UTIL` = `rollapplyr(UTILM, 12, sum)`) para cada indicador de rentabilidad, en cada ejecución. **La plataforma Python ya resuelve esto de forma más eficiente** — no hay que reimplementar el rolling window del R; ROA/ROE/utilidad anualizada deben construirse sobre `valor_12m`, no reproducir la lógica de `lag()`+`rollapplyr()` cuenta por cuenta.

No hay cálculos financieros duplicados dentro de las páginas Streamlit: se verificó con una búsqueda dirigida (patrones de división `a / b` fuera de `utils/data_loader.py` y `analytics/`) y el único hallazgo fue una participación de mercado simple en Pérdidas y Ganancias (no una fórmula CAMEL). Los `pages/*.py` ya delegan correctamente en `analytics/` y `utils/data_loader.py` — **el problema no es duplicación de cálculos, es que el cálculo de "indicadores ejecutivos de segundo nivel" (score integral, vulnerabilidad, resiliencia, etc.) que pide esta ampliación simplemente no existe todavía**, más allá del CAMEL Score compuesto que ya hay en `analytics/camels_score.py`.

---

## Resumen cuantitativo de la matriz

| Categoría | Cantidad | Acción propuesta |
|---|---|---|
| 1 — Ya existe, fuente SEPS oficial (mejor que recalcular) | ~20 indicadores (mapean a 13 códigos SEPS + score CAMEL) | Ninguna — mantener como está |
| 2 — No computable (cuentas COVID inexistentes en cooperativas) | 49 fórmulas | Documentar limitación, no implementar |
| 3 — Computable y nuevo | 32 fórmulas | Candidatas a `financial_engine.py`, priorizadas arriba |
| 4 — Requiere adaptación/validación de un analista antes de migrar | 3 fórmulas (`LIQ_1RA`, `LIQ_2DA`, familia `MORA` cruda) | Migrar la variante oficial ya disponible; ajustar `LIQ_1RA/2DA` con un analista |
| 5 — Bug del script R (no se replica) | 1 colisión de nombre + 2 bloques duplicados | Documentado; se corrige al migrar (nombres explícitos por línea) |
| 6 — Ya calculado por SEPS, invisible en la UI | 13 códigos | **Mayor retorno/esfuerzo** — solo requiere edición de `config/indicator_mapping.py` |
| Derivados (percentiles, tasas de crecimiento, ratios compuestos sobre los anteriores) | 64 fórmulas | Heredan el estado de su(s) insumo(s); ver detalle por nombre en el análisis programático |

---

## Lo que esta auditoría NO hizo (por instrucción explícita)

- No se creó `analytics/financial_engine.py` ni ningún submódulo de dominio.
- No se modificó `config/indicator_mapping.py` (aunque la Categoría 6 es una edición de una tarde).
- No se tocó ningún modelo de Machine Learning.
- No se escribió ninguna prueba nueva.
- No se generaron los 6 índices ejecutivos de segundo nivel pedidos (Score Financiero Integral, Vulnerabilidad, Riesgo Integral, Fortaleza, Resiliencia, Estabilidad) — son indicadores **nuevos**, no una migración del R (el R no los define), y su diseño metodológico (qué pesos, qué normalización, qué variables) requiere una decisión de negocio antes de escribir código.

---

## Propuesta de alcance para la Fase 2 (a confirmar antes de implementar)

Dado el tamaño real del pedido completo — motor central, 7 submódulos de dominio, 6 índices ejecutivos nuevos, integración con ML, pruebas unitarias por indicador, documentación automática — construirlo todo de una sola vez no es prudente sin antes acordar prioridad y secuencia. Propuesta de fases incrementales, cada una entregable y verificable por separado:

1. **Quick win (Categoría 6)**: exponer los 13 indicadores SEPS ya calculados que hoy son invisibles. Cambio pequeño, cero riesgo, valor inmediato.
2. **`analytics/financial_engine.py` — capa de fachada**: no mover código todavía, sino crear el punto de entrada único que hoy no existe, re-exportando lo que ya vive en `liquidez.py`, `credito.py`, `solvencia.py`, etc. Deja el motor "existiendo" sin reescribir nada que funciona.
3. **Migrar la Categoría 3** (32 fórmulas nuevas y computables) al motor, organizadas por dominio como pide el pedido (Liquidez, Cartera, Morosidad, Cobertura, Rentabilidad, Eficiencia, Crecimiento).
4. **Índices ejecutivos nuevos**: definir metodología (pesos, normalización) para cada uno de los 6 antes de codificar — esto es una decisión de Riesgos y Estudios, no solo de ingeniería.
5. **Pruebas unitarias + documentación automática por indicador**, en paralelo a cada dominio migrado (no al final).

No voy a empezar a construir esto hasta que confirmes cómo priorizarlo.

---

## Fase 2 — Implementación (completada)

Confirmado el alcance: las 5 fases anteriores, en el orden propuesto, con metodología propia (transparente, ajustable) para los 6 índices ejecutivos. Estado final:

| Fase | Entregable | Estado |
|---|---|---|
| 2.1 — Quick win | 13 indicadores SEPS antes invisibles, expuestos en `config/indicator_mapping.py` (`GRUPOS_INDICADORES`, `ETIQUETAS_INDICADORES`, escalas y rangos de heatmap calibrados con percentiles P5/P50/P95 reales de `indicadores.parquet`) | ✅ |
| 2.2 — Fachada | `analytics/financial_engine.py`: punto de entrada único, re-exporta los 8 módulos de dominio existentes sin reescribir ninguna fórmula. Las 9 páginas que antes importaban de `analytics.liquidez`, `analytics.credito`, etc. directamente ahora importan solo de `financial_engine` | ✅ |
| 2.3 — Categoría 3 migrada | `analytics/rentabilidad.py` (tasas implícitas, spread, margen financiero, ROE ajustado) y `analytics/crecimiento.py` (captaciones, colocaciones, cartera en riesgo, bandas de percentil) — 9 de las fórmulas "Alta/Media prioridad" de la matriz; las de prioridad "Baja" (`PROVCOM`…`PROVTOT`, redundantes con `COB_*` oficial) quedaron fuera, según la propia priorización de esta auditoría | ✅ |
| 2.4 — Índices ejecutivos | `analytics/indices_ejecutivos.py`: los 6 índices, metodología de percentiles orientados (reutilizada de `camels_score.py`, no reimplementada) | ✅ |
| 2.5 — Pruebas unitarias | 18 pruebas nuevas (`tests/test_analytics.py`) + 3 de integración con datos reales (`tests/test_consistencia_datos.py`) — **encontraron y corrigieron 2 bugs reales antes de producción** (detalle abajo) | ✅ |
| 2.6 — Documentación automática | `CATALOGO_INDICADORES.md`, generado por `scripts/generar_documentacion_indicadores.py` a partir de `config/indicator_mapping.py` y `analytics/catalogo_indicadores.py` — 55 indicadores documentados (41 oficiales SEPS + 14 nuevos), con los 9 campos pedidos cada uno | ✅ |
| 2.7 — Validación final | Suite completa (81 pruebas / 330 subpruebas), barrido de las 16 páginas vía `AppTest`, y verificación en un servidor Streamlit real con navegador (Playwright) — sin excepciones ni errores de JavaScript | ✅ |

### Dos bugs reales que las pruebas atraparon antes de producción

**1 — Índice de Vulnerabilidad invertido.** La primera versión clasificaba como "más vulnerable" a la cooperativa con **mejores** indicadores. Causa: mal uso del parámetro `mayor_es_mejor` de `_percentil_orientado()` — ese parámetro gobierna "¿un valor crudo alto produce una salida alta?", no un juicio de valor financiero. Al querer que un z-score alto (más vulnerable) produjera un índice alto, correspondía `mayor_es_mejor=True`, no `False`. Detectado por una prueba sintética de 2 líneas (`FRAGIL` debía superar a `SANA`) y confirmado en datos reales: tras la corrección, las 5 cooperativas más "vulnerables" según el índice son, en efecto, las de mayor morosidad real (12%-21%), y la correlación entre el índice y el Índice de Riesgo Integral es -0.88 (fuertemente negativa, como corresponde).

**2 — `calcular_indice_vulnerabilidad` fallaba con `KeyError` si se le pasaban `df_pyg`/`df_ranking` vacíos** (los dos argumentos opcionales para la señal de brecha de ROE). El guard `if not roe_oficial.empty and not roe_adj.empty` llegaba demasiado tarde: el crash ocurría dentro de `calcular_roe_ajustado`, antes de que ese guard se evaluara. Corregido verificando `df_pyg.empty`/`df_ranking.empty` **antes** de invocar la función.

### Verificación en producción, no solo en pruebas

Todo el trabajo se validó contra datos reales de junio de 2026 (203-242 cooperativas según la fuente), no solo con datos sintéticos:

- **Tasas implícitas**: pasiva 7.8% promedio, activa 19.1% promedio, spread 11.3% — magnitudes plausibles para el sector cooperativo ecuatoriano.
- **ROE ajustado**: verificado a mano contra JARDIN AZUAYO LTDA — la diferencia frente al ROE oficial (1.85% vs. 5.69%) se explica exactamente por excluir "otros ingresos" ($7M) de una utilidad neta muy delgada ($11.46M), tal como pretende la fórmula.
- **Índice de Riesgo Integral**: distribución real jun-2026 — 103 "Bueno", 77 "Vigilancia", 15 "Riesgo Medio", 7 "Muy Bueno", 1 "Excelente"; ninguna institución en "Riesgo Alto" ni "Riesgo Crítico" en ese corte.
- **Servidor real**: reiniciado con el código de hoy, verificado con Playwright (no solo `AppTest`) — "Suficiencia Patrimonial" visible en el selector de la página CAMEL, las 15 páginas cargan con su título correcto y cero errores de JavaScript.

### Qué no se hizo (alcance explícitamente diferido)

- Las 49 fórmulas de la Categoría 2 (cuentas COVID inexistentes en cooperativas) — documentadas como no aplicables, no implementadas.
- `LIQ_1RA`/`LIQ_2DA` (Categoría 4) — requieren que un analista de riesgos valide la fórmula ajustada antes de publicar el número; no implementadas.
- Las fórmulas de prioridad "Baja" de la Categoría 3 (`PROVCOM`…`PROVTOT`, `GOP_AP`/`INTERM_FIN` propios) — redundantes con indicadores oficiales ya disponibles.
- Ninguna página nueva de UI para los indicadores de la Fase 2.3/2.4 — el pedido original los describe como una capa de **cálculo** ("el motor deberá dividir automáticamente los indicadores en módulos"); quedan disponibles en `financial_engine` para que cualquier página los consuma, pero no se creó una superficie visual nueva sin que el usuario la pida explícitamente.

### Archivos nuevos de esta fase

`analytics/financial_engine.py` · `analytics/rentabilidad.py` · `analytics/crecimiento.py` ·
`analytics/indices_ejecutivos.py` · `analytics/catalogo_indicadores.py` ·
`scripts/generar_documentacion_indicadores.py` · `CATALOGO_INDICADORES.md`

### Archivos modificados

`config/indicator_mapping.py` (Categoría 6) · 9 páginas (`pages/5_Riesgo_Liquidez.py` a `pages/15_Asistente_IA.py`, solo el import) · `tests/test_analytics.py` · `tests/test_consistencia_datos.py`

### Sin modificar (ninguna fórmula financiera existente tocada)

`analytics/liquidez.py` · `analytics/credito.py` · `analytics/solvencia.py` · `analytics/concentracion.py` ·
`analytics/sistemico.py` · `analytics/camels_score.py` · `analytics/alertas.py` · `analytics/stress_testing.py` ·
`models/` · `utils/data_loader.py` (solo se reutilizó `obtener_crecimiento_anual`, sin tocarla) · `master_data/`
