# Metodología de Riesgo — Radar Cooperativo Ecuador

Este documento consolida la metodología de indicadores y de vigilancia de riesgo
de la plataforma, y dos auditorías independientes de fórmulas hechas contra
fuentes distintas:

1. `AUDITORIA_MOTOR_INDICADORES.md` (28-jul-2026): 150 fórmulas de un script R
   institucional (`INDICADORES BANCOS.R`) contra el código Python.
2. **Esta sesión** (14-sep-2026): las 63 fichas metodológicas oficiales de la
   SEPS (`Fichas-Metodologicas-de-Indicadores-Financieros_V3.0.pdf`, versión 3.0,
   31-jul-2026) contra `indicadores.parquet`, `config/indicator_mapping.py` y
   `analytics/`.

No reemplaza a `CATALOGO_INDICADORES.md` (catálogo generado automáticamente de
55 indicadores desde `config/indicator_mapping.py` + `analytics/catalogo_indicadores.py`).
Este documento es el nivel superior: fuentes, clasificación, umbrales, y el
estado real (implementado / no implementado / propuesto) de cada componente
que pide el objetivo de "sistema de vigilancia financiera" — no solo el
catálogo de fórmulas.

---

## 1. Fuentes, en orden de autoridad

1. Normativa SEPS / JPRF vigente.
2. `indicadores.parquet` — 41 indicadores oficiales, extraídos del pivot cache
   de la hoja "5. INDICADORES FINANCIEROS" de cada boletín XLSM (`procesar_camel.py`).
   Esta es la fuente de mayor autoridad disponible: es el número que la SEPS
   ya publicó, no una reconstrucción propia.
3. `Fichas-Metodologicas-de-Indicadores-Financieros_V3.0.pdf` (63 fichas,
   adjuntado en esta sesión) — fórmula, fuente, periodicidad y sintaxis SPSS
   oficial de cada uno de los 63 indicadores que la SEPS calcula.
4. `balance.parquet` / `pyg.parquet` — cuentas crudas del Catálogo Único de
   Cuentas, usadas solo cuando un indicador no está pre-calculado por la SEPS.
5. BIS/BCBS, IMF, FSB, ESRB, literatura académica — únicamente para
   indicadores complementarios sin equivalente oficial ecuatoriano (ver §6).

## 2. Clasificación de cada indicador

Todo indicador de la plataforma cae en una de cuatro categorías, ya usada de
forma consistente en `CATALOGO_INDICADORES.md`:

| Categoría | Significado | Ejemplo |
|---|---|---|
| `OFICIAL_SEPS` | Tomado literal de `indicadores.parquet`, calculado y publicado por la SEPS | `MOR_TOT`, `ROE`, `LIQ`, `CAP_NETO` |
| `DERIVADO` | Calculado en Python a partir de cuentas crudas oficiales (`balance.parquet`/`pyg.parquet`), con fórmula documentada y trazable a una cuenta contable real | `TASA_PI`, `TASA_AI`, `TASA_MF`, `CAPGA`, `COLGA` (`analytics/rentabilidad.py`, `analytics/crecimiento.py`) |
| `ANALÍTICO` | Construcción propia de la plataforma (índice, score, umbral, clasificación) sin fórmula oficial equivalente — debe declararse explícitamente como tal | Los 6 índices ejecutivos (`analytics/indices_ejecutivos.py`), HHI/CR-N/Gini (`analytics/concentracion.py`), IIS (`analytics/sistemico.py`), reglas de `config/umbrales_alerta.py` |
| `INTERNATIONAL_COMPLEMENT` | Metodología internacional (BIS/IMF/FSB) sin regulación ecuatoriana equivalente | Componente tamaño+sustituibilidad de la metodología D-SIB usado en el IIS |

Ningún indicador de la plataforma se presenta como "límite regulatorio" salvo
que la ficha SEPS lo defina como tal explícitamente (único caso verificado:
ficha 63, "Porcentaje Técnico Requerido" = 9%, ver §4).

## 3. Auditoría de esta sesión — 63 fichas SEPS vs. `indicadores.parquet`

Método: se extrajeron las 63 fichas (nombre, fórmula, fuente de datos B.11,
sintaxis SPSS D.10) y se cruzaron contra los 41 códigos únicos presentes hoy
en `indicadores.parquet`.

### 3.1 Indicadores 1–57 — cubiertos (con nota de segmentación)

Las fichas 5–30 (morosidad y cobertura por línea de negocio) definen hasta 3
variantes históricas de segmentación (prioritario/ordinario hasta abr-2021,
consolidado desde may-2021). `indicadores.parquet` únicamente contiene la
**segmentación vigente** (6 líneas: Consumo, Inmobiliaria, Microcrédito,
Productivo, Vivienda IP, Educativo + Total) porque el pivot cache de la SEPS
publica solo el esquema actual. Esto es correcto y ya estaba documentado en
`AUDITORIA_MOTOR_INDICADORES.md` (Categoría 2) para el cruce contra el script
R; esta auditoría lo confirma independientemente contra la fuente oficial.
**No se requiere ninguna acción**: no existe una fuente que permita reconstruir
las variantes prioritario/ordinario históricas sin recalcular desde cuentas
que la propia ficha 5 (D.10) marca como "hasta abril 2021" / "desde mayo 2021"
— es decir, la SEPS misma dejó de publicar esa granularidad.

Fichas 31–57 (eficiencia, rentabilidad, intermediación, FK, FI, capitalización
neta) mapean 1:1 a códigos ya presentes: `GO_ACT`, `GO_MNF`, `GP_ACT`, `ROE`,
`ROA`, `INTERM`, `MARG_PAT`, `MARG_ACT`, los 6 `REND_*`, `FK`, `FI`, `CAP_NETO`.
Verificado sin discrepancias en dirección del indicador (mayor/menor es mejor)
ni en unidad (ratio 0–1, se multiplica por 100 en la UI).

### 3.2 Indicadores 58–63 (Solvencia / Patrimonio Técnico) — **INTEGRADO (14-sep-2026, cobertura parcial)**

> **Actualización 14-sep-2026**: el hallazgo de "no disponible" descrito abajo
> (auditoría inicial) fue investigado y **resuelto para la parte pública de la
> fuente**. La SEPS publica en su portal de estadísticas un boletín separado
> ("Patrimonio Técnico") con exactamente los datos de la ficha FS01. Se
> implementó el pipeline completo: `descargar_patrimonio_tecnico()` en
> `scripts/descargar_datos_seps.py` (scraping del panel "Patrimonio técnico",
> best-effort, no afecta el código de salida del resto de la descarga) →
> `scripts/procesar_solvencia.py` (ETL: XLSM/XLSX → `master_data/solvencia.parquet`
> + `metadata_solvencia.json`) → `analytics/solvencia.py::evaluar_solvencia_oficial()`
> (compara contra el 9% mínimo regulatorio, ficha 63) → pestaña "🏦 Solvencia
> Oficial (FS01)" en `pages/7_Riesgo_Solvencia.py`.
>
> **Cobertura confirmada empíricamente (no asumida)**: el boletín de
> Patrimonio Técnico solo cubre **Segmento 1, Mutualistas y Caja Central
> FINANCOOP** — coincide con el propio texto descriptivo del panel SEPS.
> **Segmento 2 y 3 NO tienen Solvencia oficial calculable** por esta
> plataforma (ni por ninguna fuente pública conocida): para esos segmentos,
> `evaluar_solvencia_oficial()` simplemente no tiene filas — no se aproxima,
> no se estima, no se rellena.
>
> Verificado con datos reales: 3.548 registros, 2020-01 a 2026-07, 53 RUC
> únicos, 0 discrepancias entre la Solvencia reportada por la SEPS y su
> recálculo independiente `PTC / APPR` (columna `discrepancia_solvencia`,
> ver `procesar_solvencia.py` — es una verificación de calidad de dato, no
> una fórmula alternativa que reemplace el número oficial).
>
> **Separación estricta CAP_NETO vs. Solvencia oficial, mantenida en todo el
> sistema**: `CAP_NETO` (FK/FI, ficha 57, `config/umbrales_alerta.py`) sigue
> siendo un indicador analítico distinto — nunca se le aplica el 9% de
> Solvencia. Ver `UMBRAL_SOLVENCIA_REGULATORIO = 0.09` en `analytics/solvencia.py`,
> usado **únicamente** sobre la columna `solvencia` de `solvencia.parquet`
> (PTC/APPR real), nunca sobre `CAP_NETO`.
>
> **Estado**: `OPERATIVO` para Segmento 1/Mutualistas/FINANCOOP;
> `BLOQUEADO POR DATOS` para Segmento 2/3 (sin fuente pública).

**Hallazgo original de la auditoría (14-sep-2026, antes de la integración) — se conserva como registro:**

Las fichas 58 a 63 (Patrimonio Técnico Primario, Secundario, Constituido,
Activos y Contingentes Ponderados por Riesgo, **Solvencia**, Porcentaje
Técnico Requerido) declaran en su sección B.11 una fuente adicional a los
Estados Financieros:

> `2. Formulario de solvencia (FS01)`

Los indicadores 1–57 declaran únicamente `1. Estructura de Estados Financieros
(B11)`. El ETL actual (`procesar_camel.py`) solo descarga y procesa el boletín
de Estados Financieros (hoja "5. INDICADORES FINANCIEROS"); **no existe ningún
script que descargue o procese el Formulario de Solvencia (FS01)**, y se
verificó programáticamente que ninguno de los 41 códigos de `indicadores.parquet`
corresponde a Patrimonio Técnico, Activos Ponderados por Riesgo, Solvencia o
Porcentaje Técnico Requerido.

**Consecuencia**: la plataforma no puede hoy calcular ni mostrar el ratio de
Solvencia oficial de la SEPS (PTC / Activos y Contingentes Ponderados por
Riesgo) ni compararlo contra el mínimo regulatorio del 9% (ficha 63).

**Riesgo de interpretación ya presente en el código — documentado, no corregido
silenciosamente**: `config/umbrales_alerta.py` usa el indicador `CAP_NETO`
(= ficha 57, `FK/FI`, que en el código es `I50_Indi_capi_neto`) con umbrales
`alerta_amarilla=0.09` / `alerta_roja=0.06`. El valor `0.09` coincide
numéricamente con el mínimo regulatorio de **Solvencia** (ficha 63), pero
`CAP_NETO` (FK/FI) **no es el mismo indicador que Solvencia** (PTC/ACPR,
ficha 62): FK es patrimonio ajustado por resultados e ingresos extraordinarios
sobre activos totales, FI es un factor ≥ 1 que penaliza por activos
improductivos — una construcción de vulnerabilidad patrimonial distinta a la
razón de suficiencia de capital ponderada por riesgo de Basilea que usa
Solvencia. El código de `umbrales_alerta.py` ya declara correctamente que sus
umbrales son "referenciales" y no oficiales (ver cabecera del archivo), así
que no hay una afirmación falsa en el sistema hoy — pero el uso de 9% ahí,
sin esta nota, podía inducir a un lector a asumir que ese 9% es el mínimo
regulatorio de solvencia aplicado a CAP_NETO. **Corrección aplicada en esta
sesión**: se documentó explícitamente en `config/umbrales_alerta.py` (ver
diff) que el 9%/6% de `CAP_NETO` es un umbral percentílico propio y que **no
debe leerse como el 9% mínimo de Solvencia (ficha 63)**, indicador que la
plataforma no calcula por falta de la fuente FS01.

**Recomendación** (no ejecutada — requiere decisión de producto, no es una
corrección de código): si se requiere el ratio de Solvencia oficial, es
necesario ampliar `descargar_datos_seps.py` para localizar y descargar el
Formulario de Solvencia (FS01) del portal SEPS, y un nuevo
`procesar_solvencia.py` que lo procese. Sin esa fuente, cualquier intento de
reconstruir PTC/ACPR desde `balance.parquet` sería una aproximación no
verificable contra el número oficial (las ponderaciones de riesgo de la
ficha 61 dependen de detalle de cuentas — p. ej. distinguir inversiones "de
disponibilidad restringida" — que no siempre es identificable de forma
inequívoca solo con el Catálogo Único de Cuentas del balance).

### 3.3 Indicadores sin discrepancia y sin acción pendiente

Fichas 1–4 (Suficiencia Patrimonial, Activos Improductivos/Productivos,
Utilización Pasivo con Costo) → `SUF_PAT`, `ACT_IMPR`, `ACT_PROD`, `AP_PC`.
Sin discrepancias de fórmula, dirección o unidad.

## 4. Separación indicador / umbral (obligatoria, ya vigente)

| Tipo de umbral | Dónde vive | Estado |
|---|---|---|
| Regulatorio oficial | Ninguno implementado hoy (el único conocido, Solvencia 9%, no es calculable — ver §3.2) | Documentado como ausente |
| Analítico (percentiles propios) | `config/umbrales_alerta.py` (`REGLAS_ALERTA`) | Implementado, etiquetado "referencial" en la cabecera del módulo |
| Escala visual (heatmap) | `config/indicator_mapping.py::RANGOS_HEATMAP` | Implementado, calibrado con P5/P50/P95 reales — nunca presentado como umbral de alerta |

No se identificaron umbrales regulatorios hard-coded que se presenten como
tales sin serlo, aparte de la ambigüedad de `CAP_NETO` corregida en §3.2.

## 5. Estado real de los componentes del sistema de vigilancia

Esta sección es la más importante para no sobre-reportar: distingue lo que
**ya existe y está verificado** de lo que el objetivo de "sistema de
vigilancia" (EWI multifactorial, breadth, riesgo sistémico, IPSF,
backtesting) todavía **no tiene**, para no presentar una alerta o un índice
como más riguroso de lo que es.

| Componente | Estado | Archivo | Nota |
|---|---|---|---|
| Indicadores oficiales SEPS | OPERATIVO | `indicadores.parquet`, `financial_engine.py` | 41 códigos, fuente autoritativa |
| Solvencia oficial (PTC/APPR, fichas 58–63, FS01) | OPERATIVO (Seg. 1/Mutual/FINANCOOP) · BLOQUEADO POR DATOS (Seg. 2/3) | `analytics/solvencia.py`, `scripts/procesar_solvencia.py` | Ver §3.2 |
| Indicadores derivados (tasas, crecimiento) | OPERATIVO | `analytics/rentabilidad.py`, `crecimiento.py` | Categoría 3 de `AUDITORIA_MOTOR_INDICADORES.md` |
| Índices ejecutivos (Score, Vulnerabilidad, etc.) | OPERATIVO, con pruebas | `analytics/indices_ejecutivos.py` | Analítico, declarado como tal |
| Alertas por regla simple (nivel + semáforo) | OPERATIVO | `analytics/alertas.py`, `pages/11_Alertas_Tempranas.py` | Evalúa **nivel** de un mes |
| **Persistencia** de la señal | OPERATIVO | `analytics/persistencia.py` | Nueva/persistente/recurrente sobre ventana de N meses (ver §8) |
| **Breadth** (% activos/cartera/depósitos afectados) | OPERATIVO | `analytics/breadth.py` | RIESGO CONCENTRADO vs. GENERALIZADO (ver §9) |
| **Interacción entre riesgos** (reglas compuestas) | OPERATIVO (3 reglas) | `analytics/interaccion.py` | Cada regla con justificación económica explícita, no pesos arbitrarios (ver §10) |
| Riesgo sistémico — tamaño/sustituibilidad (IIS) | OPERATIVO, limitación declarada | `analytics/sistemico.py`, `pages/9_Riesgo_Sistemico.py` | Sin interconectividad (dato no publicado por SEPS) |
| Clasificación de contracción sistémica (Normal→Evento Extremo) | ANALÍTICO EXPERIMENTAL | `analytics/riesgo_sistemico_estado.py` | Árbol de decisión transparente, sin backtesting completo (ver §12) |
| Concentración de mercado (HHI/CR-N/Gini/Lorenz) | OPERATIVO | `analytics/concentracion.py`, `pages/8_Riesgo_Concentracion.py` | — |
| IPSF (Índice de Presión Financiera Sistémica) | EXPERIMENTAL | `analytics/ipsf.py` | Framework de prueba, NO indicador oficial (ver §13) |
| Backtesting de señales contra eventos reales | ANALÍTICO NO VALIDADO | `analytics/backtesting.py`, `analytics/eventos.py` | Eventos = proxy de cese de reporte, muestra pequeña (ver §14) |
| Identidad de entidades (RUC, estado, cambios de segmento) | PARCIAL | `master_data/entidades_cooperativas.parquet`, `scripts/generar_entidades.py` | RUC solo donde hay fuente FS01 (Seg. 1/Mutual/FINANCOOP); "salida" es proxy no causal (ver §15) |
| Calidad de datos (fechas, duplicados, denominadores, cambios de segmento) | OPERATIVO | `analytics/data_quality.py` | Separa anomalía de dato de señal financiera (ver §16) |
| Segmento histórico vs. actual | PARCIAL | `segmento_historico`/`segmento_actual` en `balance.parquet`/`indicadores.parquet` | Mecanismo correcto desde 14-sep-2026 en adelante; histórico previo sigue "estimado" (ver §17) |
| Modelos predictivos (RF morosidad, ARIMA) | ANALÍTICO NO VALIDADO / EXPERIMENTAL | `models/prediccion_morosidad.py`, `models/forecast.py` | Split temporal correcto, una sola ventana de holdout, sin backtesting contra eventos (ver §18) |
| Machine Learning no supervisado (Isolation Forest, KMeans) | ANALÍTICO, complementario | `models/anomalias.py`, `models/clustering.py` | No supervisado: no hay "verdad" contra la cual validar, por diseño |
| Asistente IA | OPERATIVO (modo local) / PARCIAL (modo Claude) | `services/asistente_ia.py` | Grounding reforzado 14-sep-2026: hecho vs. inferencia, fallback "Información insuficiente para determinarlo." (ver §19) |
| Indicadores macroprudenciales (Credit-to-GDP Gap, DSR) | BLOQUEADO POR DATOS | — | Sin fuente mensual de PIB/deuda de hogares en Ecuador accesible a este proyecto (ver §7) |

## 6. Historial — por qué IPSF y backtesting no se construyeron en la sesión del 14-sep-2026 (auditoría)

**Nota**: esta sección describe el razonamiento de la sesión de *auditoría*
(14-sep-2026, mañana). Los componentes que aquí se declaran como
prerrequisitos (persistencia, breadth) se construyeron esa misma tarde — ver
§8–§14 para el estado actual, ya implementado.

El objetivo pedía explícitamente no construir un índice compuesto "por
apariencia" sin antes validar que sus componentes tienen capacidad analítica,
y no afirmar capacidad predictiva de un backtest sin evidencia. En el momento
de la auditoría, ninguno de los dos componentes que el IPSF necesitaría como
insumo (persistencia de alertas, breadth ponderado por tamaño) existía todavía
de forma independiente y probada — construir el IPSF sin ellos habría sido el
antipatrón que el objetivo prohíbe. El backtesting, a su vez, requería una
lista de eventos de referencia que no existía como dataset estructurado.

La fase siguiente (persistencia → breadth → registro de eventos proxy →
interacción → estado sistémico → IPSF experimental → backtesting) se ejecutó
en su totalidad esa misma sesión — ver las secciones siguientes.

## 7. Limitaciones generales (declaración explícita, no implícita)

- No existe fuente pública en este repositorio para PIB mensual ecuatoriano ni
  Debt Service Ratio — Credit-to-GDP Gap y DSR **no se implementan** por falta
  de dato, no por omisión. La arquitectura queda preparada: si en el futuro
  aparece una fuente (p. ej. BCE publica PIB trimestral desagregable o un
  proxy mensual confiable), el punto de integración natural es un nuevo
  `analytics/macroprudencial.py` que consuma una serie externa — no se crea
  el archivo vacío hoy para no sugerir una implementación que no existe.
- El componente de interconectividad de riesgo sistémico (D-SIB) no es
  calculable: la SEPS no publica exposiciones intercooperativas.
- La granularidad histórica de morosidad/cobertura prioritario vs. ordinario
  (fichas 6,7,11,12,19,20,24,25) no es reconstruible después de may-2021
  porque la propia SEPS dejó de publicarla a ese nivel.
- El ratio de Solvencia oficial ya se calcula (§3.2) pero solo para
  Segmento 1/Mutualistas/FINANCOOP — Segmento 2/3 quedan sin este indicador
  por ausencia de fuente pública, no por una limitación del ETL.
- Todos los "eventos" usados en breadth/backtesting (§14) son un **proxy** de
  cese de reporte, no un registro confirmado de liquidaciones/fusiones por
  resolución SEPS — la SEPS no publica ese registro estructurado.

## 8. Persistencia temporal de alertas

`analytics/persistencia.py`. Reutiliza `evaluar_alertas()` sin reimplementar
reglas — la evalúa repetidamente sobre una ventana de fechas parametrizable
(3/6/12 meses, elegible en la UI) y agrega, por cooperativa:

- `meses_consecutivos_activa`: meses seguidos con ≥1 alerta activa, terminando
  en la fecha más reciente de la ventana.
- `alerta_nueva`: activa hoy, no lo estaba el mes anterior.
- `alerta_persistente`: activa hoy y `meses_consecutivos_activa >= UMBRAL_PERSISTENTE_MESES` (3, parametrizable).
- `alerta_recurrente`: ≥2 rachas de actividad separadas dentro de la ventana (patrón "aparece, desaparece, reaparece").

Integrado en `pages/11_Alertas_Tempranas.py` (pestaña "⏱️ Persistencia, Amplitud
e Interacción"). Estado: **OPERATIVO**. Prueba: `tests/test_riesgo_ampliado.py::PersistenciaTests`.

**Calibración del ~54% de alertas persistentes — investigado 14-sep-2026
(hardening), no es un defecto**: se auditó el hallazgo pendiente de la sesión
anterior con datos reales. Evidencia reunida:
- **Estable ante la ventana elegida**: 53.8% (12M) / 54.1% (6M) / 54.1% (3M) —
  no es un artefacto de qué ventana se usa.
- **No depende de una sola regla ruidosa**: en el corte jul-2026, las 103
  cooperativas "crónicas" (activas los 6 meses completos) tienen en promedio
  2.6 reglas activas simultáneas (ROE 64%, ROA 61%, CAP_NETO 58%, MOR_TOT 41%
  de esas 103) — solo 29/103 dependen de una única regla en el umbral mínimo.
- **Proporcional entre segmentos**: 45.7%-51.5% de cada segmento está en la
  cohorte crónica, sin concentrarse en uno.
- **Tendencia secular, no ruido de corte**: medido cada 6 meses desde 2020,
  el % de alertas persistentes subió de ~30-34% (2021-2022) a ~43-56%
  (2024-2026) — consistente con el hallazgo independiente de §12
  (`CONTRACCIÓN SIGNIFICATIVA` en la comparación interanual jul-2026).
- Conclusión: el umbral (`UMBRAL_PERSISTENTE_MESES = 3`) **se mantiene sin
  cambios** — no hay evidencia de que sea demasiado laxo, y bajarlo
  únicamente reduciría el conteo de alertas sin una justificación
  económica/estadística mejor que la actual. El objetivo pidió explícitamente
  no ajustar el umbral solo para producir menos alertas.

## 9. Breadth (amplitud)

`analytics/breadth.py`. Responde qué % de activos/cartera/depósitos/patrimonio
del universo comparado (sistema completo o un segmento) está en manos de un
conjunto de cooperativas afectadas (p. ej. las que tienen alerta roja hoy).
Clasifica `RIESGO CONCENTRADO` vs. `RIESGO GENERALIZADO` con un umbral
analítico (`UMBRAL_GENERALIZADO_PCT = 25.0`, no regulatorio, documentado en el
módulo). `breadth_por_segmento()` repite el cálculo por cada segmento para
comparar dónde pesa más un deterioro. Integrado en Alertas Tempranas y en el
estado sistémico (§12). Estado: **OPERATIVO**. Prueba: `BreadthTests`.

**Sensibilidad del umbral 25% — auditado 14-sep-2026**: se midió
`% de activos en entidades con alerta roja` cada 6 meses desde 2020. Rango
observado: 3.7% a 19.4% — **nunca cruzó el 25%** en 6.5 años de historia
usando la población "alerta roja". El umbral es estable en la región 20-40%
(ninguna reclasificación al mover el corte en ese rango) pero sensible en la
región 10-20% (varios períodos 2021-2026 cruzarían a "GENERALIZADO" con un
corte de 10-15%). Con la población más amplia "cualquier alerta" (roja +
amarilla), el mismo cálculo da 51% en jul-2026 — muy por encima del umbral,
"GENERALIZADO" con margen. Conclusión: **25% se mantiene** (es
deliberadamente conservador — pensado para la población de alerta roja, no
para cualquier alerta) y sigue etiquetado explícitamente como **UMBRAL
ANALÍTICO**, no regulatorio. No se implementó un umbral distinto por
indicador ni ponderación adicional por falta de evidencia que lo justifique
— el umbral ya pondera por activos (no por conteo de entidades), que era el
ajuste con mejor justificación disponible y ya estaba implementado.

## 10. Interacción entre indicadores

`analytics/interaccion.py`. Solo implementa combinaciones con justificación
económica explícita documentada en el propio código (no un score ponderado
sin narrativa):

1. `deterioro_cartera_compuesto`: morosidad + cobertura + ROA en alerta
   simultánea — cartera que se deteriora sin provisión suficiente, sin
   colchón de rentabilidad que lo absorba.
2. `deterioro_cartera_compuesto_critico`: morosidad Y cobertura en alerta
   **roja** a la vez (ROA en cualquier nivel de alerta) — variante más
   estricta de (1).
3. `presion_fondeo`: caída de depósitos + liquidez en alerta — menos fondeo
   entrando y menos colchón para responder retiros al mismo tiempo.

Cada regla opera sobre las columnas `sev_*` ya calculadas por `evaluar_alertas()`
(0/1/2), nunca sobre valores crudos — por construcción, una regla de
interacción es siempre al menos tan estricta como sus reglas individuales.
Reglas cuyas columnas necesarias no estén presentes se omiten silenciosamente
(no se inventa el dato faltante) — p. ej. `presion_fondeo` se omite si no se
pasó `df_crecimiento_depositos` a `evaluar_alertas()`. Estado: **OPERATIVO**
(3 reglas). Prueba: `InteraccionTests`.

**Auditoría de redundancia — 14-sep-2026 (hardening)**: se verificó que
`deterioro_cartera_compuesto_critico` es, por construcción y confirmado con
datos reales (jul-2026: 5 cooperativas críticas, subconjunto exacto de las
11 de `deterioro_cartera_compuesto`), un **subconjunto estricto** de
`deterioro_cartera_compuesto` — no doble-cuenta un riesgo distinto, es
intencionalmente una versión más severa de la misma señal (documentado en su
propia descripción). `n_interacciones_activas` suma ambas para una entidad
que cumple las dos, lo cual es correcto: refleja que esa entidad activó dos
niveles de severidad del mismo mecanismo, no dos mecanismos independientes.
No se agregaron reglas nuevas — el pedido de esta fase fue explícito en no
agregar reglas sin evidencia clara, y no se encontró ninguna combinación
adicional con justificación económica tan directa como las 3 existentes.

## 11. Identidad de entidades y eventos proxy

`scripts/generar_entidades.py` construye `master_data/entidades_cooperativas.parquet`
(tabla ligera, una fila por cooperativa) a partir de lo que ya existe — no
duplica RUC/segmento en los datasets grandes:

- `fecha_inicio`/`fecha_fin_datos`/`segmento_actual`: de `balance.parquet`
  (vía `segmento_historico`, §17).
- `ruc`: de `solvencia.parquet` — **solo para las entidades cubiertas por ese
  boletín** (Segmento 1/Mutualistas/FINANCOOP). Segmento 2/3: `ruc = NULL`,
  explícito, no inferido.
- `estado` (`activa` / `posible_salida` / `liquidacion_declarada`): de
  `analytics/eventos.detectar_eventos_salida()` — un **proxy** de cese de
  reporte (última fecha reportada muy anterior al máximo del dataset), no una
  clasificación causal. `liquidacion_declarada` es la única categoría con
  evidencia textual directa (el propio nombre de la entidad incluye "EN
  LIQUIDACION" en los datos de la SEPS).

Verificado con datos reales: 259 entidades, 51 con RUC, 207 activas, 45
`posible_salida`, 7 `liquidacion_declarada`. Integrado como sección expandible
en `pages/1_Panorama.py`. Estado: **PARCIAL** (identidad completa solo para el
subconjunto con RUC; el resto tiene nombre/segmento/estado pero no RUC).
Prueba: `EventosTests` (sintética) + `EntidadesIdentidadTests` (datos reales,
`tests/test_consistencia_datos.py`).

## 12. Estado sistémico y clasificación de contracción — ANALÍTICO EXPERIMENTAL

`analytics/riesgo_sistemico_estado.py`. Combina, en un árbol de decisión
transparente y documentado (no una caja negra ni pesos ocultos):

- Crecimiento YoY agregado en **3 dimensiones** (cartera, depósitos, activos)
  — nunca se define contracción por la caída de una sola.
- Breadth de alertas rojas (§9).
- Persistencia (§8): exige ≥3 meses consecutivos para que el deterioro cuente
  como señal "no es ruido de un mes" en el árbol.
- Concentración (HHI de activos, `analytics/concentracion.py`) como contexto,
  no como insumo del puntaje.

Clasifica en exactamente los 6 estados pedidos: `NORMAL`, `DESACELERACIÓN`,
`CONTRACCIÓN SECTORIAL`, `CONTRACCIÓN SIGNIFICATIVA`, `ESTRÉS SISTÉMICO
POTENCIAL`, `EVENTO EXTREMO` — **nunca** usa la palabra "CRISIS" (verificado
por test). Cada resultado incluye `drivers`, `evidencia_en_contra`,
`amplitud`, `persistencia`, `concentracion`, `confianza` (declarada, no una
probabilidad estadística) y `limitaciones` explícitas. Integrado en
`pages/9_Riesgo_Sistemico.py` (pestaña "🧭 Estado Sistémico (Experimental)"),
con advertencia visible de que es analítico experimental sin backtesting
histórico completo.

**Calibración del ~54% de "persistentes"**: investigada y cerrada en el
hardening del 14-sep-2026 — ver §8. Conclusión: es una tendencia secular real
(de ~30% en 2021-2022 a ~50-56% en 2024-2026), no ruido de calibración; el
umbral se mantiene sin cambios.

**Corrección de lógica — requisito de evidencia multidimensional (14-sep-2026,
hardening)**: se ejecutó una batería de 8 escenarios sintéticos (A-H:
crecimiento sano, desaceleración, contracción de cartera aislada, deterioro
generalizado de calidad, shock de liquidez, deterioro calidad+rentabilidad,
presión de depósitos aislada, shock combinado) para verificar coherencia
económica. Se encontró y corrigió un caso real: una caída YoY **aislada en
una sola dimensión** (p. ej. solo cartera -8%, con depósitos/activos sanos,
sin breadth ni persistencia) alcanzaba `CONTRACCIÓN SECTORIAL` únicamente por
el puntaje de crecimiento — exactamente el antipatrón que el objetivo prohíbe
("contracción no puede equivaler a caída aislada de cartera/depósitos").
**Corrección aplicada**: se exige que al menos 2 de las 3 señales de
evidencia (crecimiento negativo, breadth ≥15%, persistencia relevante)
concurran para que el estado pueda ser cualquiera de la familia
`CONTRACCIÓN`/`ESTRÉS`/`EVENTO EXTREMO`; con una sola señal, el resultado
queda acotado a `DESACELERACIÓN` (con el driver documentado igual, marcado
como evidencia insuficiente en `evidencia_en_contra`). Verificado: los 8
escenarios producen ahora resultados económicamente coherentes — en
particular, el deterioro generalizado de calidad con crecimiento sano
(escenario D) sigue alcanzando `CONTRACCIÓN SIGNIFICATIVA` correctamente
(breadth + persistencia sí concurren, sin necesitar caída de crédito),
mientras que la contracción de cartera aislada (C) y la presión de depósitos
aislada (G) ahora quedan en `DESACELERACIÓN`. Prueba de regresión:
`RiesgoSistemicoEstadoTests::test_contraccion_de_cartera_aislada_no_escala_sin_breadth_ni_persistencia`.

Estado: **ANALÍTICO EXPERIMENTAL** (sin cambio — la corrección mejora la
coherencia del árbol de decisión, no constituye backtesting histórico
completo). Prueba: `RiesgoSistemicoEstadoTests`.

## 13. IPSF — Índice de Presión Financiera Sistémica (EXPERIMENTAL)

`analytics/ipsf.py`. **NO es un indicador oficial, no está validado por
backtesting completo, no debe usarse para decisiones operativas.** A
diferencia de los 6 índices ejecutivos (que rankean cooperativas entre sí en
una fecha), el IPSF es una serie de tiempo agregada del sistema — un número
por período pensado para comparar a través del tiempo.

Tres componentes (0–100, 100 = máxima presión): `breadth_activos` (§9),
`severidad_promedio` (promedio de alertas activas normalizado), `desaceleracion`
(complemento del crecimiento YoY agregado de cartera+depósitos).

Dos esquemas de ponderación **implementados y comparados**: A (pesos iguales,
1/3 cada uno) y B (pesos "expertos": breadth 50%, severidad 20%,
desaceleración 30%). `diagnostico_esquemas()` calcula la correlación entre
ambos esquemas sobre la serie — verificado con datos reales: **correlación
A/B = 0.968** en los últimos 12 meses.

**¿Robustez o redundancia? — investigado 14-sep-2026 (hardening), pedido
explícito de no concluir superioridad solo por correlación**: se calculó la
correlación entre los 3 componentes CRUDOS (`analytics.ipsf.correlacion_componentes()`,
nueva función esta fase), no solo entre esquemas de pesos. Resultado con
datos reales (24 meses): `breadth_activos` vs. `severidad_promedio` = **0.75**
(ambos se derivan de `evaluar_alertas()` — comparten fuente por
construcción); `desaceleracion` vs. los otros dos = **0.07 y 0.20**
(componente genuinamente independiente, viene de crecimiento agregado de
balance). **Conclusión corregida**: la correlación A/B de 0.968 es, en buena
medida, un artefacto de que 2 de los 3 insumos del índice ya son redundantes
entre sí — no es evidencia de que el IPSF tenga capacidad analítica
validada, solo de que la elección específica entre A y B no domina el
resultado (una afirmación más débil que la de la versión anterior de este
documento). Esta corrección está reflejada en el docstring de
`diagnostico_esquemas()` y en una nueva sección expandible en la UI
("¿Robustez o redundancia?"). No cambia el estado EXPERIMENTAL del índice —
si acaso, refuerza por qué debe mantenerse así.

Tres esquemas **explícitamente NO implementados**, con razón documentada en
`ESQUEMAS_NO_IMPLEMENTADOS`:
- **C (PCA/factores)**: con solo 3 componentes, la primera componente
  principal colapsaría al de mayor varianza — no aporta sobre A/B.
- **D (ponderación por capacidad predictiva)**: con ~24 eventos proxy en todo
  el histórico, ajustar pesos por optimización memorizaría la muestra en vez
  de generalizar.
- **E (híbrido)**: depende de C y D.

Integrado en `pages/9_Riesgo_Sistemico.py` (pestaña "🌡️ IPSF (Experimental)"),
con la etiqueta "IPSF — ÍNDICE ANALÍTICO EXPERIMENTAL" visible en la UI.
Estado: **EXPERIMENTAL** (por instrucción explícita: no se promueve a
indicador oficial en esta sesión). Prueba: `IPSFTests`.

## 14. Backtesting — validación contra eventos observados

`analytics/backtesting.py` + `analytics/eventos.py`. **Limitación
metodológica principal, declarada en cada resultado**: los "eventos" son un
proxy de cese de reporte (`detectar_eventos_salida()`) — liquidación, fusión,
absorción o simple atraso, sin distinguir la causa salvo evidencia textual
directa ("EN LIQUIDACION" en el nombre). No es backtesting en el sentido
estricto de validar contra eventos confirmados por resolución SEPS.

`evaluar_alertas_previas_a_eventos()`: para cada evento proxy, revisa si la
entidad tuvo ≥1 alerta activa persistente en los `meses_anticipacion` meses
antes de su último reporte. Verificado con datos reales: 24 eventos proxy
detectados (2020–2026, incluye "COOP CATAR LTDA EN LIQUIDACION" confirmada
por nombre), `recall_proxy = 0.75` (18/24 tuvieron alerta previa),
`lead_time_promedio_meses = 5.8` (**censurado por la ventana de 6 meses**: un
valor igual a la ventana completa significa "al menos esos meses", no el lead
time real). No se reporta "falsos positivos" en sentido estricto — requeriría
saber qué entidades con alerta NO tuvieron problemas, cierto para la gran
mayoría por construcción.

**Muestra pequeña (~24 eventos)**: cualquier precision/recall aquí tiene un
intervalo de confianza amplio y no debe presentarse como tasa de acierto
operativa confiable. Estado: **ANALÍTICO NO VALIDADO** (no "EXPERIMENTAL":
tiene menos margen incluso que el IPSF, por el tamaño de muestra). Prueba:
`BacktestingTests`.

**Etiquetado reforzado — 14-sep-2026 (hardening)**: pedido explícito de no
tratar "cese de reporte" como sinónimo de liquidación/insolvencia/crisis. Se
adjuntaron etiquetas como **datos**, no solo en el docstring: la salida de
`detectar_eventos_salida()` ahora incluye una columna `tipo_evento` con el
valor literal `TIPO_EVENTO_PROXY` ("EVENTO PROXY NO CONFIRMADO — cese de
reporte, causa no verificada") o `TIPO_EVENTO_TEXTUAL` para el único caso con
evidencia directa (nombre con "LIQUIDACION"). La salida de
`evaluar_alertas_previas_a_eventos()` incluye ahora `tipo_resultado =
"BACKTESTING PROXY — no es validación definitiva"`. El objetivo de esto es
que cualquier consumidor futuro (una página nueva, un export, otro script)
vea la etiqueta aunque no lea este documento ni el docstring del módulo. No
se encontró ninguna fuente pública adicional que permita confirmar la causa
real de los 24 eventos — no se incorporó ninguna por falta de evidencia
verificable, consistente con "no inventar eventos".

## 15. Modelos predictivos y Machine Learning — auditoría crítica (14-sep-2026)

**`models/prediccion_morosidad.py`** (Random Forest, predicción de
`MOR_TOT` a un mes): split **temporal** correcto (entrena con meses
antiguos, valida contra los últimos `meses_holdout=6`) — no hay fuga de
información del futuro. Features: indicadores oficiales del mes actual
(incluyendo el propio `MOR_TOT` actual como predictor autoregresivo, lo cual
es válido — es un dato conocido al momento de predecir, no el target).
Métricas reales reportadas en la UI (MAE, R², no simuladas). **Limitación no
resuelta**: se evalúa sobre una única ventana de holdout, sin validación
cruzada temporal (múltiples cortes) ni contraste contra los eventos de §14 —
no hay evidencia de estabilidad del desempeño a través del tiempo. Etiquetado
en la UI (`pages/13_Modelos_Predictivos.py`) como "ANALÍTICO NO VALIDADO /
EXPERIMENTAL".

**`models/forecast.py`** (ARIMA, series del sistema): ya reportaba backtest
honesto (MAPE sobre 6 meses ocultos) antes de esta sesión — sin cambios,
mismo caveat de ventana única.

**`models/anomalias.py`** (Isolation Forest) y **`models/clustering.py`**
(KMeans): no supervisados — no tienen una variable objetivo, por lo que las
preocupaciones de fuga/split temporal no aplican de la misma forma. Ya
documentados en el propio código y en `pages/14_Machine_Learning.py` como
complementarios al motor de reglas, no un reemplazo. Sin cambios.

Estado: `models/prediccion_morosidad.py` y `models/forecast.py` →
**ANALÍTICO NO VALIDADO / EXPERIMENTAL**; `models/anomalias.py` y
`models/clustering.py` → **ANALÍTICO** (no supervisado, no aplica el mismo
estándar de validación).

**Re-auditoría 14-sep-2026 (hardening)**: se confirmó, sin encontrar cambios
necesarios, que ningún modelo usa datos del período de evaluación en el
entrenamiento (split estrictamente cronológico), que las features no
incluyen el target futuro, y que no hay clase objetivo desbalanceada que
requiera re-muestreo (regresión continua, no clasificación). Se reforzó
explícitamente en la UI (banner nuevo en `pages/13_Modelos_Predictivos.py`)
que "detección de anomalías ≠ predicción de crisis": ni el RF de morosidad
ni el Isolation Forest deben presentarse como capacidad de predecir un
evento sistémico — el primero predice un ratio continuo a un mes, el segundo
solo mide distancia estadística al resto del sistema en un corte.

## 16. Asistente IA — grounding reforzado (14-sep-2026)

`services/asistente_ia.py`. Dos modos: local determinístico (enrutador de
palabras clave a consultas ya calculadas, sin LLM, nunca inventa — sin
cambios) y Claude (Anthropic, requiere clave API). Se reforzó el prompt de
sistema de `construir_contexto_sistema()` para:

- Nunca inventar cifras, nombres, fechas ni eventos regulatorios
  (liquidaciones, fusiones, sanciones) sin respaldo en el resumen de datos
  inyectado o en la metodología documentada.
- Distinguir explícitamente **HECHO** (dato/cálculo directo de la plataforma)
  de **INFERENCIA** (lectura del asistente sobre ese dato) al ofrecer
  interpretación.
- Responder exactamente `"Información insuficiente para determinarlo."`
  cuando la pregunta requiere un dato/evento/clasificación regulatoria fuera
  del resumen inyectado — con sugerencia de en qué módulo verificarlo.

El fallback del modo local (pregunta no reconocida) se alineó al mismo
criterio ("Información insuficiente para determinarlo con el asistente local
determinístico..."). Estado: **OPERATIVO** el modo local (determinístico,
sin dependencia externa); **PARCIAL** el modo Claude (el grounding del
prompt es una instrucción al modelo, no una restricción técnica dura — no
hay forma de garantizar en código que el LLM la respete siempre).

## 17. Data quality — separación de anomalía de dato vs. señal financiera

`analytics/data_quality.py`. Funciones de solo lectura (no "arreglan" datos):
`validar_fechas` (huecos en la serie mensual), `validar_duplicados` (clave de
negocio repetida con valores distintos), `validar_faltantes` (% nulos por
columna), `detectar_denominadores_cero` (activos/cartera/depósitos ≤0 antes
de dividir), `detectar_entidades_nuevas_y_desaparecidas`,
`detectar_cambios_de_segmento` (usa `segmento_historico`, §18),
`detectar_cambios_abruptos` (variación mes a mes >50%, sin asumir causa).
`reporte_calidad_fecha()` combina fechas+duplicados+denominadores en un
veredicto simple (`confiable: bool`) — integrado en `pages/1_Panorama.py`
como sección expandible ejecutada antes de mostrar KPIs/rankings de la fecha
seleccionada. Estado: **OPERATIVO**. Prueba: `DataQualityTests`.

## 18. Segmento histórico vs. segmento actual — defecto corregido, con limitación remanente

**Defecto encontrado (14-sep-2026)**: `segmento` en `balance.parquet` e
`indicadores.parquet` estaba retroactivamente unificado al último segmento
conocido de cada cooperativa, aplicado a **toda su historia** — una
cooperativa que migró de Segmento 3 a Segmento 1 en 2024 aparecía como
Segmento 1 incluso en sus registros de 2018. Cualquier análisis histórico o
sistémico "por segmento a través del tiempo" (breadth por segmento,
concentración por segmento en el tiempo) heredaba ese sesgo silenciosamente.

**Corrección aplicada** (`scripts/procesar_balance_cooperativas.py`,
`scripts/procesar_camel.py`): se añadieron, de forma aditiva (sin tocar el
significado de la columna `segmento` que ya usan ~100+ referencias en el
código):

- `segmento_historico`: el segmento reportado por la propia entidad en ESE
  mes específico (point-in-time), cuando se puede determinar de la fuente
  procesada en esa corrida.
- `segmento_actual`: alias explícito del comportamiento legado (`segmento`
  duplicado con nombre honesto).
- `segmento_historico_estimado` (booleano): `True` cuando `segmento_historico`
  no es point-in-time real sino un backfill igual a `segmento_actual`.

**Limitación remanente, documentada explícitamente (no oculta)**: al momento
de escribir esto, `segmento_historico_estimado = True` para el **100%** de
los registros de `balance.parquet`/`indicadores.parquet`, **incluyendo el
corte más reciente**. Esto es correcto y esperado, no un error del mecanismo:
el ETL incremental de esta plataforma correctamente NO reprocesa meses que ya
están presentes en el parquet (evita recalcular 24M+ filas históricas en cada
corrida), así que la regeneración de esta sesión solo pudo *backfillear*
honestamente ("no sabemos el segmento point-in-time real de ningún registro
ya presente") — no reprocesó ningún ZIP fuente. El mecanismo queda bien
cableado **hacia adelante**: el próximo mes que la automatización (cron día
15/18/20/22) o un reproceso manual traten como genuinamente **nuevo** sí
obtendrá `segmento_historico_estimado = False`. Recuperar el dato real para
años 2018–2026 requeriría reprocesar los ZIPs fuente de cada año desde cero
(formatos distintos: 2018-2021 CSV/TXT con `;`, 2022-2025 tab-delimitado con
comas decimales) — evaluado como demasiado riesgoso/costoso para esta sesión,
diferido explícitamente.

**`procesar_pyg.py` — corregido y REGENERADO el 14-sep-2026 (hardening P0)**:
`procesar_pyg.py` tenía el mismo patrón de unificación retroactiva que
balance/indicadores. Se aplicó el mismo fix aditivo (`segmento_historico`,
`segmento_actual`, `segmento_historico_estimado`, con backfill defensivo
tanto para el histórico existente como para cualquier `df_fuente` que no
traiga las columnas — ver `combinar_historico_pyg()`).

En un primer intento (mismo día, sesión anterior de hardening), la
regeneración real de `pyg.parquet` no pudo ejecutarse porque
`scripts/procesar_indicadores.py` (que alimenta el PyG) no completaba el
parseo del Boletín Segmento 3 en un tiempo razonable. **Esa causa raíz fue
diagnosticada y corregida en esta sesión — ver §20.** Con la corrección, se
ejecutó el reproceso real y **`master_data/pyg.parquet` fue regenerado
exitosamente**: 2.399.251 registros (idéntico a antes — 0 filas, 0
diferencias numéricas en `valor_acumulado`/`valor_mes`/`valor_12m` frente al
archivo anterior, ver §20), 242 cooperativas, 2020-01 a 2026-07. El tramo
2026 (Ene-Jul, genuinamente reprocesado) quedó con
`segmento_historico_estimado = False`; el tramo 2020-2025 (histórico
heredado, no reprocesado) permanece `True` — exactamente el comportamiento
"hacia adelante" que se había documentado como objetivo.

**Verificación concreta de la corrección** (P0 del pedido de hardening, muestra real):
la cooperativa `CAÑAR LTDA` reportó genuinamente `SEGMENTO 3` de enero a mayo
de 2026 y migró a `SEGMENTO 2` desde junio de 2026 — dato point-in-time real,
visible en `segmento_historico` (con `segmento_historico_estimado=False`
para todo el tramo 2026). Las columnas legadas `segmento`/`segmento_actual`
muestran, correctamente según su definición, `SEGMENTO 2` para las 13 filas
completas (aplicación retroactiva del último segmento conocido) — la
diferencia entre ambas columnas para enero-mayo de 2026 es la prueba
funcional de que el mecanismo distingue correctamente ambos conceptos. 4
cooperativas en total mostraron un cambio de segmento detectable en el
tramo real de 2026 (`CAÑAR LTDA`, `GUARANDA LTDA`, `SAN MARTIN DE TISALEO
LTDA`, `SANTA ANITA LTDA`).

Uso recomendado: `utils.data_loader.cargar_segmento_historico()` para
análisis histórico/sistémico por segmento; `segmento`/`segmento_actual` para
rankings "a la fecha actual". Estado: **OPERATIVO** para el tramo genuinamente
reprocesado (2026 en balance/indicadores/pyg); **PARCIAL** para el histórico
2018-2025, que permanece backfilleado (`segmento_historico_estimado=True`) y
requeriría reprocesar los ZIPs fuente de cada año para recuperarse — evaluado
como fuera de alcance por formato heterogéneo entre años (2018-2021 CSV/TXT
con `;`, 2022-2025 tab-delimitado con comas decimales), no por falta de
capacidad técnica. Prueba: `SegmentoHistoricoTests`
(`tests/test_consistencia_datos.py`), `tests/test_actualizacion.py::IncrementalidadTests`.

## 19. Hardening 14-sep-2026 (tarde) — validación, calibración y robustez

Fase de auditoría y corrección sobre el sistema construido en la sesión
anterior del mismo día, sin reconstruir nada existente. Resumen de lo que
cambió realmente (detalle en cada sección arriba y en `docs/CHANGELOG_RIESGO.md`):

- **Arquitectura**: `analytics/financial_engine.py` ahora re-exporta también
  los 8 módulos nuevos de la sesión anterior (persistencia, breadth,
  interacción, estado sistémico, IPSF, eventos, backtesting, data quality) —
  las 3 páginas que los usaban (`9`, `11`, `1`) importaban directamente de los
  submódulos, violando el punto de entrada único que el propio proyecto ya
  exigía (`test_ninguna_pagina_importa_un_submodulo_de_dominio_directamente`,
  que no cubría estos módulos nuevos — ahora sí). Corregido en ambos lados:
  el motor y el test de guardia.
- **Corrección de lógica real** (no solo documentación): el árbol de decisión
  de `riesgo_sistemico_estado.py` permitía que una caída aislada de una sola
  dimensión de crecimiento (sin breadth ni persistencia) alcanzara
  "CONTRACCIÓN SECTORIAL" — corregido para exigir evidencia multidimensional
  (§12).
- **Calibración investigada, no cambiada arbitrariamente**: persistencia
  (~54%, §8) y breadth (25%, §9) se sometieron a análisis de sensibilidad con
  datos reales; ambos umbrales se mantienen, con la evidencia que los
  respalda documentada explícitamente (antes no existía este análisis).
- **Reinterpretación honesta de una métrica ya calculada**: la correlación
  A/B del IPSF (0.968) se había presentado como "evidencia débil de que el
  índice funciona" — se corrigió a la interpretación correcta (redundancia
  entre 2 de 3 componentes, no validación) tras calcular la correlación entre
  componentes crudos (§13).
- **Etiquetado explícito como dato, no solo como texto**: eventos proxy y
  resultados de backtesting ahora llevan columnas/campos con la etiqueta
  ("EVENTO PROXY NO CONFIRMADO", "BACKTESTING PROXY") adjunta al propio
  DataFrame (§14).
- **Control determinístico nuevo sobre el Asistente IA**: guardrail en código
  Python (no solo en el prompt) que detecta la palabra "crisis" en una
  respuesta del LLM y adjunta una advertencia visible — la primera vez que
  este proyecto implementa un control de este tipo sin depender de que el
  modelo "obedezca" (§16).
- **Workflow**: los pasos opcionales (Solvencia FS01, identidad de entidades)
  pasaron de `|| echo warning` (silencioso, sin marca visible en la UI de
  Actions) a `continue-on-error: true` (marca visible) + un paso de resumen
  final que categoriza el resultado en ERROR CRÍTICO / WARNING / NO HAY DATOS
  NUEVOS / OK, escrito a `$GITHUB_STEP_SUMMARY`.
- **`procesar_pyg.py` corregido a nivel de código** (mismo defecto de
  segmento que balance/indicadores) — `pyg.parquet` no se regeneró esta
  sesión por un hallazgo de performance no relacionado, descubierto al
  intentarlo (§18).
- **Hallazgo nuevo, no resuelto**: `procesar_indicadores.py` no completa el
  parseo del Boletín Financiero Segmento 3 en un tiempo razonable en este
  entorno — ver §18 y §21 (Riesgos residuales en el informe final).
- **Tests**: +6 nuevos (contracción aislada, guardrails del asistente ×2,
  contexto del asistente, respuesta local ×2) sobre los 110 ya existentes al
  cierre de la sesión anterior — **116 en total, 0 regresiones** (verificado
  con la suite completa, no solo los archivos tocados).
- Ningún componente pasó de EXPERIMENTAL/ANALÍTICO a OPERATIVO en esta fase
  — el objetivo de esta fase fue robustez y calibración, no ampliar cobertura
  funcional. Ningún commit se realizó.

## 20. Cierre técnico P0/P1 14-sep-2026 (noche) — pipeline, segmentación y producción

Segunda fase de hardening el mismo día, enfocada exclusivamente en
reproducibilidad del pipeline (no en el motor de riesgo, que no se tocó
salvo lo indicado explícitamente).

### P0 — Causa raíz del cuello de botella de Segmento 3 (diagnosticada, no solo mitigada)

La sesión anterior había documentado que `procesar_indicadores.py` no
completaba en >10 min al procesar el ZIP de indicadores 2026, atribuyéndolo
tentativamente a Segmento 3. **Diagnóstico correcto, instrumentado por
etapa** (lectura, apertura de workbook, identificación de cache, extracción
de lookup, `ET.fromstring`, bucle Python, construcción del DataFrame):

- Cada segmento, **medido en aislamiento**, procesa en tiempo lineal y
  razonable: Segmento 1 (55.6 MB) → 8.4s, Segmento 2 (81.7 MB) → 12.7s,
  Segmento 3 (119.2 MB) → 19.1s (~0.16s/MB, consistente entre los tres — sin
  ningún comportamiento no lineal en el algoritmo de parseo en sí).
- **La causa real es acumulación de memoria del PROCESO, no del archivo**:
  `procesar_todos_indicadores()` procesa los 4 archivos (Mutualistas +
  Segmento 1/2/3) secuencialmente en el mismo proceso Python. Cada
  `ET.fromstring()` construye un árbol XML completo en memoria (hasta ~1.3
  GB de objetos Python por archivo grande); Python libera esas referencias
  correctamente (`gc.collect()` las recolecta), pero **glibc no le devuelve
  esas páginas al sistema operativo** — el RSS del proceso queda "atascado"
  en el pico alcanzado. Medido: RSS subió 101→2050→2988→4325 MB (`ru_maxrss`)
  a lo largo de los 4 archivos. Con memoria limitada (~7-8 GB en este
  entorno, compartida con otros procesos), el proceso muere por OOM
  exactamente en el archivo más grande y más tardío en el orden de
  procesamiento (Segmento 3) — pareciendo "el problema de Segmento 3" cuando
  en realidad es "la cuarta acumulación consecutiva sin liberar memoria".
- Confirmado experimentalmente: `gc.collect()` + `ctypes` `malloc_trim(0)`
  después de cada archivo devuelve el RSS real (`/proc/self/status` VmRSS) a
  ~105 MB sin importar el archivo, en vez de acumularse — validado en los 3
  segmentos reales.

**Alternativa evaluada y descartada**: reescribir `parsear_cache_records()`
con `ET.iterparse()` (streaming) en vez de `ET.fromstring()` (árbol
completo). Se implementó y se demostró **equivalencia exacta** (mismas
filas, columnas, valores, en los 3 segmentos reales) contra la
implementación actual — pero no resultó más rápida (9.8s vs. 8.1s en
Segmento 1, 15.5s vs. 13.8s en Segmento 2, 20.2s vs. 21.8s en Segmento 3:
diferencias dentro del ruido de medición) y no se pudo demostrar de forma
aislada que reduce el pico de memoria más que la solución de `malloc_trim`.
Se descartó por mayor riesgo (cambia el algoritmo de parseo) sin beneficio
demostrado sobre la alternativa mucho más simple. **Principio aplicado**:
la corrección mínima que resuelve la causa diagnosticada, no la reescritura
más sofisticada disponible.

### Solución aplicada

`scripts/procesar_indicadores.py::_liberar_memoria_al_os()`: `gc.collect()`
+ `ctypes.CDLL("libc.so.6").malloc_trim(0)` (con fallback silencioso fuera de
Linux) después de procesar cada archivo XLSM del ZIP. 8 líneas de código,
cero cambios a la lógica de parseo/negocio.

### Performance antes/después (medido, no estimado)

| | Antes (sesión anterior) | Después (esta sesión) |
|---|---|---|
| `procesar_indicadores.py` (ZIP 2026 completo, 4 archivos) | No completa en >10 min (killed) | **Completa en <60s**, 1.756.691 registros consolidados |
| Segmento 3 aislado | 19.1s (ya era rápido aislado) | Sin cambio — no era el problema |
| RSS del proceso tras Segmento 3 | Sin datos (moría antes) | Confirmado que se mantiene ~105 MB tras cada archivo, en vez de acumular a 4.3+ GB |

### Datasets regenerados (P0 — regeneración real, no solo verificación de código)

Se ejecutó el pipeline completo real (no solo se validó el código):
`procesar_indicadores.py` → `procesar_camel.py` → `procesar_pyg.py`.

| Dataset | Filas antes | Filas después | Diferencias numéricas | Nuevas columnas |
|---|---|---|---|---|
| `indicadores_raw.parquet` | 1.756.691 | 1.756.691 | 0 (merge exacto por fecha+cooperativa+codigo) | — |
| `master_data/indicadores.parquet` | 611.881 | 611.881 | 0 | (ya las tenía, de la sesión anterior) |
| `master_data/pyg.parquet` | 2.399.251 | 2.399.251 | 0 en `valor_acumulado`/`valor_mes`/`valor_12m` | `segmento_historico`, `segmento_actual`, `segmento_historico_estimado` (nuevas) |

Todas las comparaciones se hicieron con un `merge` exterior por clave de
negocio (`fecha`, `cooperativa`, `codigo`) confirmando 0 filas `left_only`/
`right_only` y 0 diferencias numéricas (`abs(diff) > 1e-6` → 0 filas en los
3 datasets). Ninguna "diferencia esperada" quedó sin explicar — la única
diferencia real es la aparición de las 3 columnas nuevas en `pyg.parquet`
(intencional, ver §18).

### Consistencia entre datasets (matriz, vía PyArrow — sin cargar balance.parquet completo en pandas)

| Dataset | fecha_min | fecha_max | entidades | segmentos | filas | duplicados clave | nulos críticos |
|---|---|---|---|---|---|---|---|
| balance.parquet | 2018-01-31 | 2026-07-31 | 259 | 4 | 24.404.894 | 0 | 0 |
| pyg.parquet | 2020-01-31 | 2026-07-31 | 242 | 4 | 2.399.251 | 0 | 0 |
| indicadores.parquet | 2020-01-31 | 2026-07-31 | 231 | 4 | 611.881 | 0 | 0 |

Clasificación de las diferencias observadas:
- `fecha_min` distinto (2018 vs. 2020): **DIFERENCIA ESPERADA** — balance
  tiene 2 años más de historia que PyG/CAMEL porque la fuente XLSM de
  indicadores solo se procesa desde 2020 (documentado desde sesiones
  anteriores, no relacionado con el trabajo de hoy).
- `entidades` distinto (259/242/231): **DIFERENCIA ESPERADA** —
  verificado que estos conteos son IDÉNTICOS a los de antes de la
  regeneración de hoy (231 y 242 respectivamente, confirmado contra el
  backup pre-regeneración); refleja cobertura desigual de fuentes ya
  documentada en sesiones anteriores (`CATALOGO_INDICADORES.md`,
  `AUDITORIA_MOTOR_INDICADORES.md`), no un defecto introducido hoy.
- `segmentos`, duplicados, nulos: **CONSISTENTE** en los 3 datasets.
- **No se encontraron diferencias NO EXPLICADAS.**

### Segmentación histórica — validación con muestra real

Ver §18 (actualizado): `CAÑAR LTDA` sirve de caso de prueba real —
`segmento_historico` refleja correctamente `SEGMENTO 3` para ene-may 2026 y
`SEGMENTO 2` desde jun-2026, mientras `segmento`/`segmento_actual`
(comportamiento legado, intencional) muestran `SEGMENTO 2` para las 13
filas. 4 cooperativas con cambio de segmento detectable en el tramo
reprocesado de 2026.

### P1 — Workflow: distinción de 5 estados

`.github/workflows/actualizar_datos.yml` ya distinguía, desde la sesión
anterior, los 5 estados pedidos — verificado hoy simulando la lógica bash
exacta del paso "Resumen de estado del pipeline" con las 4 combinaciones
relevantes de variables (no fue posible ejecutar el runner de GitHub
Actions real en este entorno — no está instalado `act` ni equivalente):

- `NO_NEW_DATA` (datos_nuevos=false) → mensaje "NO HAY DATOS NUEVOS", sin
  tocar el pipeline ETL.
- `SUCCESS` (todo OK) → cada componente reportado "OK" individualmente.
- `OPTIONAL_COMPONENT_FAILURE` → WARNING visible para Solvencia/entidades,
  sin marcar el job como fallido, sin bloquear el commit del dataset
  principal.
- `CRITICAL_FAILURE` → mensaje "ERROR CRÍTICO", y por el comportamiento
  documentado y estándar de GitHub Actions (un `run:` sin `continue-on-error`
  que falla marca el job `failure` y salta automáticamente los pasos
  siguientes que no tengan `if: always()`), ni "Commit y push" ni
  "Verificar tamaño de archivos" se ejecutan — confirmado leyendo la
  definición de ambos pasos (`if: steps.descarga.outputs.datos_nuevos ==
  'true'`, sin `always()`).
- `WARNING` está cubierto por el mismo caso `OPTIONAL_COMPONENT_FAILURE`
  (mismo bloque del script de resumen).

### P1 — Integridad de actualización (escritura atómica)

**Hallazgo**: los 10 sitios donde el pipeline escribe `master_data/*.parquet`
usaban `df.to_parquet(destino, ...)` directo — si el proceso muriera a
mitad de la escritura (falta de memoria, corte del runner), el archivo
productivo quedaría truncado/corrupto, reemplazando silenciosamente una
versión anterior válida.

**Corrección**: nuevo módulo `scripts/io_atomico.py::guardar_parquet_atomico()`
— escribe a un archivo temporal en el mismo directorio y solo lo reemplaza
con `os.replace()` (atómico a nivel de sistema de archivos POSIX) si la
escritura terminó sin excepciones; si falla, borra el temporal huérfano y
dejar intacto lo que ya existía. Aplicado a los 10 sitios de escritura:
`procesar_balance_cooperativas.py`, `procesar_indicadores.py`,
`procesar_camel.py`, `procesar_pyg.py`, `procesar_solvencia.py`,
`generar_entidades.py`, `generar_agregados.py` (4 sitios). Cero cambios de
fórmula o de dato — es exclusivamente higiene de I/O. Verificado con 3 tests
nuevos (`tests/test_actualizacion.py::EscrituraAtomicaTests`): escritura
exitosa sin temporales huérfanos, fallo simulado preserva el archivo
productivo anterior byte a byte, fallo sin archivo previo no deja nada
a medio escribir.

### P1 — Crecimiento YoY centralizado

`pages/2_Balance_General.py::obtener_datos_heatmap_mensual()` reimplementaba
inline el crecimiento YoY mes a mes (hallazgo de la fase de hardening
anterior, documentado, no corregido en ese momento). Corregido ahora:
`analytics/crecimiento.py::calcular_crecimiento_yoy_mensual()` centraliza el
cálculo; la página solo agrega la conversión a millones y el pivotado para
el heatmap (presentación, no cálculo financiero). Mismo resultado
verificado con `tests/test_riesgo_ampliado.py::CrecimientoYoYMensualTests`
(equivalencia numérica exacta con la fórmula original, con y sin filtro de
segmento, y verificación de que el primer año de cada cooperativa queda sin
comparación — igual que antes).

### P1 — FutureWarning de `pivot_table()`

De los ~11 sitios restantes con `pivot_table()` sin `observed=True`, se
verificó CUÁL realmente dispara el warning en uso real (capturando
`FutureWarning` durante la ejecución de cada función pública con datos
reales) antes de tocar nada — **no se hizo un reemplazo masivo**:

- **Disparan el warning** (operan sobre `cargar_ranking_cooperativas()` /
  `balance.parquet`, con `cooperativa`/`segmento` en dtype `Categorical`):
  `analytics/liquidez.py:45`, `analytics/stress_testing.py:73`,
  `analytics/solvencia.py:46` (`calcular_patrimonio_sobre_activos`) — los 3
  corregidos con `observed=True`, equivalencia de filas verificada (206
  filas, idéntico antes/después) contra datos reales.
- **NO disparan el warning** (operan sobre `cargar_indicadores()`, con
  `cooperativa`/`segmento`/`codigo` en dtype `object`, no `Categorical` —
  `observed=` no tiene efecto): `analytics/camels_score.py:88`,
  `analytics/alertas.py:77`, `analytics/indices_ejecutivos.py` (5 sitios).
  **No se modificaron** — no hay warning que suprimir ni beneficio de
  tocarlos.

### Tests

6 tests nuevos sobre los 116 del cierre de la sesión anterior — **122 en
total**, 330 subpruebas, **0 regresiones**. Verificado con la suite completa
después de cada cambio material (regeneración de datasets, fix de
`pivot_table`, escritura atómica), no solo al final: 116→119 (tras
`CrecimientoYoYMensualTests`, 3 tests)→122 (tras `EscrituraAtomicaTests`, 3
tests más).

### Riesgos residuales de esta fase

- El histórico 2018/2020-2025 de `segmento_historico` sigue sin recuperarse
  (backfill honesto, no point-in-time real) — requiere reprocesar ZIPs
  fuente de cada año, evaluado como fuera de alcance.
- El fix de memoria (`malloc_trim`) es específico de glibc/Linux — tiene
  fallback silencioso en otras plataformas, pero en macOS/Windows (solo
  relevante para desarrollo local, no para producción en GitHub Actions
  `ubuntu-latest` ni Streamlit Cloud, ambos Linux) el problema de
  acumulación de memoria seguiría presente si alguna vez se ejecutara ahí
  con datos de este tamaño.
- No se ejecutó el runner real de GitHub Actions (`act` no disponible en
  este entorno) — la validación del workflow es por inspección + simulación
  de la lógica bash extraída, no una ejecución end-to-end del YAML real.
- `pages/2_Balance_General.py` (y potencialmente otras páginas no
  auditadas en detalle esta sesión) podrían tener otros cálculos inline no
  descubiertos — la auditoría de Prioridad 13 de la fase anterior fue
  dirigida (grep de patrones de división), no exhaustiva línea por línea.

## 21. Auditoría de segmentación como dimensión analítica (14-sep-2026, sesión posterior)

Auditoría solicitada explícitamente sobre TODOS los datasets de
`master_data/` para determinar si `segmento` es una dimensión confiable y
trazable, antes de tocar cualquier filtro. Metodología: primero auditar con
datos reales (no confiar en la documentación existente), después proponer,
implementar solo lo respaldado por evidencia. Hallazgo principal: la
plataforma **ya tenía** un filtro global centralizado
(`ui/filtros.py::render_filtro_segmento()`, usado por las 14 páginas
analíticas) y funciones de carga centralizadas que aceptan `segmento` como
parámetro (`utils/data_loader.py`) — el trabajo de esta sesión fue de
verificación y corrección puntual, no de construcción desde cero.

### Inventario real (vía PyArrow, esquema + perfil de columnas)

| Dataset | Filas | Tiene `segmento` | `segmento_historico`/`actual` | Filtrable |
|---|---|---|---|---|
| `balance.parquet` | 24.404.894 | Sí (0% nulos) | Sí, pero **100% estimado actualmente** (ver hallazgo A) | 🟢 |
| `pyg.parquet` | 2.399.251 (archivo); efectivas 2.344.930 tras excluir subtotales (ver hallazgo B) | Sí (0% nulos) | Sí, tramo real 2026-01 a 2026-07 (~12%) | 🟢 |
| `indicadores.parquet` | 611.881 | Sí (0% nulos) | Sí, tramo real 2026-01 a 2026-07 (~10%) | 🟢 |
| `agg_metricas_sistema.parquet` | 3.708 | Sí (0% nulos) | No (agregado desde `segmento`=actual) | 🟢 (KPIs "a la fecha actual") |
| `agg_ranking_cooperativas.parquet` | 168.363 | Sí (0% nulos) | No | 🟢 (rankings "a la fecha actual") |
| `agg_series_temporales.parquet` | 149.656 | Sí (0% nulos) | No | 🟡 (ver hallazgo A) |
| `agg_catalogo_cooperativas.parquet` | 259 | Sí (0% nulos) | No aplica (snapshot actual) | 🟢 |
| `entidades_cooperativas.parquet` | 259 | Sí, `segmento_actual` (0% nulos) | `cambio_segmento_detectado` presente pero **desactualizado** (ver hallazgo A) | 🟡 |
| `solvencia.parquet` | 3.548 | **No** — usa `grupo_fuente` (`Segmento 1`/`Mutualista`/`FINANCOOP`), vocabulario distinto, sin Segmento 2/3 | No aplica | 🔴 (no compatible con el selector estándar) |
| `indicadores_raw.parquet` | 1.756.691 | Sí | No | No aplica — intermedio, ningún consumo directo desde `pages/` |

Consistencia de codificación (perfil de valores único por archivo, vía
PyArrow sobre las 8 columnas `segmento*` que existen): **exactamente**
`{SEGMENTO 1, SEGMENTO 1 MUTUALISTA, SEGMENTO 2, SEGMENTO 3}` en los 9
datasets que tienen la columna, 0% nulos en todos. Sin variantes de
mayúsculas/espacios/códigos numéricos. Confirma (con datos, no por
inspección de código) lo que ya afirmaban `test_el_catalogo_de_segmentos_es_identico_en_todas_las_fuentes`
y `test_toda_cooperativa_tiene_segmento_asignado`.

### Hallazgo A — `balance.parquet` perdió el tramo real de `segmento_historico` (documentación desactualizada)

§18/§20 (arriba, misma fecha, sesión anterior) documentan una validación con
`CAÑAR LTDA` mostrando `segmento_historico_estimado=False` para el tramo
2026 de `balance.parquet`. **Esa validación ya no es reproducible sobre el
archivo actual**: verificado con PyArrow que `segmento_historico_estimado`
es `True` para el **100% de `balance.parquet`** (0 filas reales), mientras
que `indicadores.parquet` y `pyg.parquet` **sí** conservan el tramo real
(2026-01 a 2026-07, `segmento_historico_estimado=False`, 20 filas
divergentes cada uno, las mismas 4 cooperativas: `CAÑAR LTDA`, `GUARANDA
LTDA`, `SAN MARTIN DE TISALEO LTDA`, `SANTA ANITA LTDA`). Explicación más
probable (por timestamps de archivo): `balance.parquet` se regeneró a las
13:42 del 14-sep-2026, **antes** de que el fix de P0 (§20) permitiera
reprocesar `indicadores.parquet`/`pyg.parquet` a las 16:56-16:57 con el
tramo real — `balance.parquet` nunca se volvió a correr después.

**Consecuencia práctica**: `utils.data_loader.cargar_segmento_historico()`
(que lee de `balance.parquet`) hoy no aporta ninguna diferencia real frente
a `segmento`/`segmento_actual` — y por eso
`entidades_cooperativas.parquet::cambio_segmento_detectado` es `False` para
las 259 cooperativas (`scripts/generar_entidades.py` lee
`segmento_historico` de `balance.parquet`, que hoy no tiene divergencias que
detectar). **No es un bug de `generar_entidades.py`** — su lógica es
correcta; su insumo está desactualizado. Verificado también que esto NO
afecta a los agregados rápidos (`agg_*.parquet`): estos se construyen desde
`segmento` (=actual) directamente, nunca usaron `segmento_historico`.

**No corregido en esta sesión** (regla explícita del pedido: no modificar
ETL ni regenerar datasets). Recomendación registrada para una sesión de
mantenimiento de datos: reprocesar `balance.parquet` para alinear su tramo
2026 con `indicadores.parquet`/`pyg.parquet`, o hacer que
`generar_entidades.py` cruce también contra `segmento_historico` de esos dos
archivos como respaldo cuando `balance.parquet` esté 100% estimado.

### Hallazgo B — `pyg.parquet` contenía subtotales SEPS tratados como cooperativas (corregido)

El boletín SEPS de origen incluye, junto a cada cooperativa real, una fila
de subtotal por segmento (`VT_TOTAL SEGMENTO 1`, `VT_TOTAL SEGMENTO 2`,
`VT_TOTAL SEGMENTO 3`, `VT_TOTAL MUTUALISTAS`) con el mismo `codigo`/`cuenta`
que las cuentas normales, en la columna `cooperativa`. Verificado con datos
reales (jul-2026, cuenta `4` Gastos): la suma de `valor_acumulado` de las
cooperativas reales de cada segmento coincide **exactamente** (0.0000% de
diferencia) con el valor de su fila `VT_TOTAL` — confirma que son
subtotales oficiales, no una cooperativa más. `balance.parquet` e
`indicadores.parquet` ya excluyen estas filas en el ETL
(`scripts/procesar_balance_cooperativas.py`,
`scripts/procesar_camel.py`) — `pyg.parquet` nunca lo hizo a nivel de
archivo. `pages/3_Perdidas_Ganancias.py` ya las excluía manualmente en 5
puntos distintos (con comentarios `# excluir VT_`) — evidencia de que el
problema ya se había detectado, pero de forma dispersa y no centralizada.
`analytics/rentabilidad.py::_valor_12m_pyg()` (usado por
`calcular_tasas_implicitas`/`calcular_margen_financiero`, exportados por
`analytics/financial_engine.py` pero **sin ningún consumidor en `pages/`
actualmente**) no las excluía — sin impacto visible hoy porque nada en la UI
llama a esas funciones, pero habría heredado el defecto en cuanto se
conectaran.

**Corrección aplicada**: `utils.data_loader.cargar_pyg()` ahora excluye
`cooperativa.startswith('VT_')` inmediatamente después de leer el Parquet,
antes de cualquier otro procesamiento — un solo punto, beneficia a todo
consumidor presente y futuro (regla #11 del pedido: centralizar en vez de
repetir el filtro). Los 5 filtros manuales redundantes en
`pages/3_Perdidas_Ganancias.py` se simplificaron (ya no hacen falta). El
archivo `master_data/pyg.parquet` **no se modificó** — el fix vive en la
capa de carga, no en el ETL ni en el dataset. `calidad['cooperativas']` que
devuelve `cargar_pyg()` pasa de 242 (incluía 4 subtotales) a 238
(cooperativas reales); ningún test ni página hardcodeaba el valor anterior.
Verificado con 2 tests nuevos
(`tests/test_consistencia_datos.py::SegmentacionTests`): ausencia de filas
`VT_` en `cargar_pyg()`, y que la suma de cooperativas reales coincide con
el subtotal oficial (detecta una regresión de duplicación x2 si el filtro
se rompiera).

### Hallazgo C — `Riesgo_Sistémico`: el IIS cambia de significado al filtrar por segmento (documentado, no corregido — ya era correcto)

`analytics/sistemico.py::calcular_indice_importancia_sistemica()` normaliza
las participaciones de mercado **dentro del universo comparado** — cuando
se filtra por segmento, "Importancia Sistémica" pasa a significar
"importancia relativa dentro de ese segmento", no "importancia en el
sistema completo". Esto ya estaba documentado honestamente en el docstring
de la función ("100 = máxima importancia sistémica relativa dentro del
universo comparado") — no es un defecto, es la interpretación
metodológicamente correcta de permitir el filtro (regla #8 del pedido: si
el análisis puede desagregarse, permitirlo; aquí sí puede, con esa
semántica). Se deja registrado explícitamente en este documento para que
quede trazable, no solo en el código.

### Hallazgo D — `Riesgo_Solvencia`, pestaña "Solvencia Oficial (FS01)": el filtro global no aplica (corregido — UX)

`solvencia.parquet` no comparte la codificación de segmento del resto de la
plataforma (`grupo_fuente`: `Segmento 1`/`Mutualista`/`FINANCOOP`, sin
Segmento 2/3 — SEPS no publica ese boletín para esos segmentos). La pestaña
"Solvencia Oficial (FS01)" de `pages/7_Riesgo_Solvencia.py` ya mostraba
correctamente el universo completo sin intentar aplicarle el selector
global de segmento — pero no lo explicitaba: si un usuario seleccionaba
"SEGMENTO 2" en el selector global (visible en el sidebar de toda la
página), esa pestaña seguía mostrando Segmento 1/Mutualista/FINANCOOP sin
aviso, exactamente el escenario que la regla #18 del pedido pide evitar
("no debe existir una métrica que permanezca calculada sobre Todos mientras
el gráfico aparenta estar filtrado"). **Corrección aplicada**: aviso
explícito (`st.info`) en esa pestaña cuando el filtro global no es "Todos",
explicando por qué no se aplica ahí. No se tocó el cálculo ni los datos.

### Matriz de páginas — filtro por segmento

| Página | Usa `render_filtro_segmento()` | Propaga a KPIs/gráficos/rankings | Nota |
|---|---|---|---|
| Inicio | Sí | Sí (KPIs, sparklines, gauge) | — |
| Panorama | Sí | Sí (KPIs, treemaps, ranking, crecimiento YoY) | — |
| Balance General | Sí | Sí (serie, heatmap, ranking) | — |
| Pérdidas y Ganancias | Sí | Sí (evolución, participación, ranking) | Corregido: subtotales VT_TOTAL (hallazgo B) |
| CAMEL | Sí | Sí (ranking, evolución, heatmap) | — |
| Riesgo de Liquidez | Sí | Sí | — |
| Riesgo de Crédito | Sí | Sí | — |
| Riesgo de Solvencia | Sí | Sí, salvo pestaña FS01 (deliberado) | Corregido: aviso explícito (hallazgo D) |
| Riesgo de Concentración | Sí | Sí (HHI/CR5/CR10 se recalculan dentro del universo filtrado — mismo principio que hallazgo C) | — |
| Riesgo Sistémico | Sí | Sí, con cambio de semántica documentado | Hallazgo C |
| CAMEL Score | Sí | Sí | — |
| Alertas Tempranas | Sí | Sí | — |
| Stress Testing | Sí | Sí | — |
| Modelos Predictivos | Sí | Sí | — |
| Machine Learning | Sí | Sí | — |
| Asistente IA | No | No aplica — conversacional, sin KPIs/gráficos propios que filtrar | Sin cambios |

### Pruebas de equivalencia y consistencia (verificadas, no solo repetidas de sesiones anteriores)

- **"Todos" = sin filtrar**: sin cambios de comportamiento — el patrón
  `if segmento != "Todos": ...` en las ~20 funciones que aceptan `segmento`
  se dejó intacto; la única función cuyo cuerpo cambió (`cargar_pyg()`)
  ahora excluye subtotales **siempre** (con y sin filtro de segmento), así
  que "Todos" antes vs. después difiere exactamente en esas 54.321 filas
  espurias — una corrección, no una regresión (ver hallazgo B, prueba
  `test_suma_pyg_por_cooperativa_no_duplica_el_total_del_sistema`).
- **Suma de segmentos = Todos**: ya cubierto por
  `test_los_segmentos_suman_el_total_del_sistema` (existente,
  `obtener_serie_sistema`) — verificado que sigue pasando.
- **Catálogo de segmentos idéntico entre fuentes**: ya cubierto por
  `test_el_catalogo_de_segmentos_es_identico_en_todas_las_fuentes`
  (existente) — verificado que sigue pasando tras el fix de `cargar_pyg()`
  (lee el Parquet crudo directamente, no pasa por el loader).
- **Suite completa**: 124 tests (122 + 2 nuevos), 0 regresiones.

### Riesgos residuales de esta auditoría

- Hallazgo A (balance.parquet desalineado de indicadores/pyg en
  `segmento_historico`) requiere reprocesar `balance.parquet` — fuera de
  alcance de esta sesión (regla explícita: no tocar ETL/datasets). Mientras
  tanto, `cargar_segmento_historico()` y
  `entidades_cooperativas.parquet::cambio_segmento_detectado` deben leerse
  con esa limitación en mente.
- `analytics/rentabilidad.py` (tasas implícitas, margen financiero, ROE
  ajustado) y `analytics/indices_ejecutivos.py` (score financiero integral)
  no tienen ningún consumidor en `pages/` actualmente — quedan fuera del
  alcance de "qué análisis de la aplicación puede incorporar el filtro"
  porque no hay página que los muestre. Si se conectan en el futuro, ya
  heredan el fix de `cargar_pyg()` (hallazgo B) sin cambios adicionales.
- No se intentó unificar el `ruc` parcial (`solvencia.parquet`,
  cobertura Segmento 1/Mutualista/FINANCOOP) con `balance.parquet` para
  ampliar cobertura de RUC — no hay una fuente adicional confiable
  identificada para Segmento 2/3 en este pipeline (documentado ya en §3.2 y
  en `generar_entidades.py`).
