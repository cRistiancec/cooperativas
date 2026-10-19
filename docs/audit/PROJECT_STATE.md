# PROJECT_STATE — Auditoría inicial (sesión 1, 2026-10-16)

Repositorio: cRistiancec/cooperativas · HEAD 6c0ddae (2026-09-23, "pin Python 3.12 para Streamlit Cloud"). Clon superficial (1 commit): historial NO verificable.
Alcance de esta sesión: lectura de código/docs, perfilado de `master_data/*.parquet`, pruebas de integridad. No se ejecutó la suite pytest ni el pipeline de descarga. No se modificó el repositorio (acceso de solo lectura).

## 1. Diagnóstico ejecutivo
| Tema | Veredicto | Tipo de evidencia |
|---|---|---|
| Código | Activo; último commit 2026-09-23 (cambio de entorno, no de datos) | Hecho verificado |
| Datos | balance.parquet: 2018-01-31 → 2026-08-31, 104 meses sin huecos, 24.639.010 registros, 259 entidades; procesado 2026-09-17 | Resultado calculado |
| Último corte SEPS oficial | NO verificado: `estadisticas.seps.gob.ec` no respondió a la descarga (error del servidor). Conciliación con la fuente pendiente | No verificable |
| Segmentos 1/2/3 | Campo existe, sin nulos ni valores inválidos, PERO es **retroactivo** (ver C-01) | Resultado calculado |
| Panel | Viable para balance (104 m, cuentas 1-6, A = P + Pat + Ingresos − Gastos con 7,7 % de excepciones, concentradas en cierres de diciembre) | Resultado calculado |
| Indicadores CAMEL | indicadores.parquet / pyg.parquet: 2020-01 → 2026-08 (80 meses), 231 entidades; son indicadores oficiales SEPS (no recalculados) | Resultado calculado |
| Evento de vulnerabilidad | No existe variable verificada. 45 entidades "posible salida" (causa NO verificada) y 7 con "EN LIQUIDACION" en el nombre | Hecho verificado |
| Modelo de alerta temprana | NO viable aún (sin evento definido ni segmentos válidos) | Interpretación |
| Panel econométrico continuo / índice | Condicionalmente viable tras corregir C-01 | Interpretación |

## 2. Incidencias (registro)
| ID | Sev. | Componente | Hallazgo | Evidencia | Acción |
|---|---|---|---|---|---|
| C-01 | CRÍTICA | `balance.parquet.segmento`, `entidades_cooperativas.parquet` | Segmento estático: 0 de 259 entidades cambian de segmento en 104 meses y `pct_segmento_historico_estimado` = 1,0 en las 259. El segmento actual está proyectado hacia atrás. Contradice la regla «segmento a la fecha de corte». Diagnóstico: coincidencia del segmento asignado con el umbral por activos del propio mes (S1>80 M, S2 20-80 M, S3 5-20 M; solo diagnóstico, NO para reasignar) = 75,3 % (dic-2018), 86,9 % (dic-2021), 93,0 % (dic-2024). En dic-2018, 23 entidades "S2" tenían activos de rango S3 y 12 "S1" de rango S2 | `docs/audit/DATA_COVERAGE.csv`; script de perfilado | Obtener el listado oficial de segmentación por año (SEPS/JPRF) y construir `dim_segmento(id, vigencia)`; hasta entonces suspender toda estimación por segmento |
| C-02 | ALTA | `master_data/balance.parquet` vs código/docs | El esquema versionado tiene 6 columnas (sin `segmento_historico`, `segmento_actual`, `segmento_historico_estimado`) aunque `procesar_balance_cooperativas.py` y CONTEXTO.md afirman que existen | schema Parquet | Regenerar o corregir documentación; añadir prueba de esquema |
| C-03 | ALTA | `entidades_cooperativas.parquet` | `ultima_fecha_reportada` máx = 2026-01-31 y las 259 tienen `fecha_fin_datos` < 2026-08-31, aunque el balance tiene 205 entidades en 2026-08. Estados (207/45/7) probablemente desactualizados | consulta directa | Regenerar tras C-01; corregir lógica |
| C-04 | ALTA | Fuente SEPS | Último corte oficial y revisiones retrospectivas no conciliados (sin acceso) | WebFetch fallido | Reintentar desde el equipo del usuario o adjuntar ZIPs originales |
| C-05 | MEDIA | `pyg`/`indicadores` | Cobertura 2020-2026 frente a 2018-2026 del balance; `metadata_indicadores.json` refleja solo la última ejecución incremental (fecha_min 2026-01) | metadata vs parquet | Decidir ventana común o recalcular desde balance 2018 |
| C-06 | MEDIA | Identidad contable | 1.447 de 18.912 pares entidad-mes no cumplen A = P + Pat + I − G (±1 USD), concentrados en cierres de diciembre | cálculo | Clasificar: error vs reclasificación de cierre |
| C-07 | MEDIA | README | Cifras desactualizadas (102/78 meses, 24,2 M registros) frente a metadata (104 meses, 24,6 M) | README vs metadata.json | Actualizar |
| C-08 | MEDIA | Universo | Mutualistas (4) incluidas en el campo `segmento`; el estudio es solo cooperativas S1-3 | valores distintos | Excluir en la base analítica |
| C-09 | MEDIA | Evento | `analytics/eventos.py` marca salidas como "causa NO VERIFICADA"; sin evento documentado | entidades parquet | Construir tabla de eventos (liquidación/fusión) con resoluciones SEPS |
| C-10 | BAJA | Trazabilidad | Historial git superficial (1 commit) | `git log` | Obtener historia completa antes de afirmar el estado de la actualización |

Duplicados entidad-fecha-cuenta: 0. Activos ≤ 0: 0. Meses faltantes en balance: 0. Saltos anómalos de entidades: máx. ±19 (jun-2023).

## 3. Cobertura por segmento (entidades únicas por fecha de corte, según el campo actual — NO histórico)
Ver `DATA_COVERAGE.csv`. S1 44-46, S2 57-67, S3 44-94 (el crecimiento de S3 por entradas de entidades es consistente con registro tardío, no con reclasificaciones).

## 4. Documento metodológico
«Diseño empírico del artículo científico» NO fue adjuntado (solo el prompt). La carpeta del usuario contiene normas y plantilla de la Revista Economía y Política (U. de Cuenca); pendiente de leer para ajustar extensión y formato.

## 5. Siguiente acción prioritaria
1. Adjuntar el documento metodológico y los ZIP originales SEPS (o confirmar acceso al portal desde tu equipo).
2. Resolver C-01 (segmentación histórica oficial).
3. Con C-01 cerrado: DATA_QUALITY.csv completo, base maestra 2018-2026, definición del evento y diseño econométrico.

---
# Sesión 2 (2026-10-17) — Ingesta con segmento desde el origen
**Hechos verificados:** la cabecera SEGMENTO existe en los CSV oficiales (2018-2025) y el segmento por XLSM en 2026; el ETL la leía pero no se conservaba (modo incremental sin ZIP históricos + sobrescritura con el último segmento). Los ETL de PyG y CAMEL repetían el patrón. `validar_actualizacion` comprobaba la columna retroactiva, por lo que no podía detectar el problema. `generar_agregados` agregaba por segmento retroactivo.
**Implementado y probado (rama local `feature/segmento-historico-ingesta`, 2 commits; push rechazado: la app de Claude no tiene acceso a la organización):**
- Dimensión `dim_segmento_historico` + upsert mensual + bitácora de revisiones + `--rehidratar/--verificar`.
- `acoplar_segmento` en balance, PyG, CAMEL y entidades; agregado `agg_metricas_sistema_historico`; puerta `validar_segmentos`; cargador de la app; workflow.
- Pruebas: 23 pasan (14 nuevas + 9 existentes de actualización); suite completa 138 pruebas, 2 fallan por baseline (parquets versionados sin columnas `segmento_historico`; fallaban antes del cambio).
**Abierto:** C-01 sigue CRÍTICA hasta ejecutar `--rehidratar` con los ZIP originales (no disponibles en la sesión). C-02 se cierra al regenerar los parquets. Normalizadores de nombre distintos entre balance/PyG/CAMEL: riesgo de pérdida de emparejamiento (se informa en `pct_cubierto`).
**Siguiente acción:** obtener los ZIP 2018-2026 → `--rehidratar` → regenerar datasets → reconstruir panel (`construir_panel.py`) → entonces habilitar comparación entre segmentos.

---

## SESIÓN 3 — 2026-10-18 (ingesta desde la fuente, segmento a la fecha, último corte)

### Estado de las incidencias tras la sesión 3
| ID | Antes | Ahora | Evidencia |
|---|---|---|---|
| C-01 Segmento retroactivo | CRÍTICA | **MITIGADA (parcial)** — 99,4 % de pares coop-mes con segmento a la fecha; 0,5-1,4 % aún estimado; 230 entidades con reclasificación registrada | `master_data/dim_segmento_historico.parquet`, `docs/audit/COBERTURA_SEGMENTOS_MENSUAL.csv`, `validar_actualizacion.py` |
| C-02 Esquema sin columnas de segmento | ALTA | **CERRADA** — balance/PyG/indicadores traen `segmento_historico` y `segmento_historico_estimado` | lectura del esquema Parquet |
| C-03 `entidades_cooperativas` desactualizada | ALTA | **CERRADA por regeneración en Actions** (pipeline completo ejecutado el 2026-10-18, run 39101509188) — pendiente revisar estados contra `entidades_trimestral.parquet` | Actions + validación OK |
| C-04 Último corte SEPS no conciliado | ALTA | **VERIFICADO**: portal accesible; ZIP 2026 contiene corte 2026-09-30; el repo quedó en 2026-09-30 | descarga directa, `metadata.json` |
| C-05 PyG/CAMEL desde 2020 | MEDIA | abierta (la fuente ya no publica PyG mensual 2018-2019 comparable) | `validar_actualizacion.py` |
| C-10 (nueva) | ALTA | Los ZIP mensuales 2020-2025 del portal ya son boletines de **un solo corte**; el balance mensual histórico del repo no es regenerable desde la fuente actual | inspección de los ZIP |
| C-11 (nueva) | MEDIA | Nombres con mojibake en balance 2020-2021 (`CRÃ‰DITO`) | cruce con la dimensión |
| C-12 (nueva) | MEDIA | jul-ago 2026 sin archivo propio: segmento arrastrado de jun-2026 | `es_arrastrado` |

### Dictamen (Fase III §11)
**¿Permite la base identificar de manera verificable y comparable a las cooperativas S1, S2 y S3?** → **PARCIAL (afirmativo con reservas).**
- Verificado: segmento oficial por entidad y corte (CSV mensual 2018-19; boletines 2020-26 en dic/sep; registro "Entidades trimestral" 2018-26).
- Reserva 1: 2020-2026 es trimestral arrastrado (53 de 105 meses sin corte propio); en 4 424 pares comparables hay 43 discrepancias (0,97 %), concentradas en recalificaciones anuales.
- Reserva 2: el registro trimestral solo cubre entidades; la serie mensual de balance 2020-25 proviene de archivos ya no publicados (se conserva la del repo, sin re-verificar contra la fuente).
- Prueba de robustez disponible: clasificación fija al inicio del período (2018) — implementable sin sesgo con `dim_segmento_historico`.

### Eventos de vulnerabilidad (Fase VI §17)
De 54 entidades que dejan de reportar en el panel antes de 2026-09: 15 con estado jurídico oficial EXTINTA/EN LIQUIDACIÓN (`SALIDAS_DEL_PANEL.csv`), 9 siguen ACTIVAS (5 pasan a Segmento 4: salen del universo, no quiebran), 30 sin registro posterior (fusión/absorción o discrepancia de nombre: **no puedo confirmar eso con la evidencia disponible**).
→ ~15 eventos en 9 años: el modelo logístico de alerta temprana (C) es **exploratorio, no confirmatorio**; XGBoost (D) **no se justifica**. Línea principal: A (descriptivo), B (panel con efectos fijos) e índice compuesto de vulnerabilidad.

### Panel analítico (reconstruido solo desde el repo, segmento a la fecha)
18 686 filas, 255 cooperativas, 2018-01 → 2026-09, sin duplicados. Reconciliación con indicadores SEPS: morosidad y cobertura exactas; ROA/ROE parciales (corr. 0,71/0,61); liquidez **no** reconcilia (corr. 0,38; definición distinta) → no usar como variable oficial. 11 observaciones con solvencia proxy negativa (revisar).

### Pendiente
Documento «Diseño empírico del artículo científico» (no adjunto); normas de la revista; revisión bibliográfica; estimación A/B; índice; manuscrito. Merge del PR #1 a `main` (la corrida mensual programada usa `main`).
