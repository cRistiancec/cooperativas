# Expediente de cierre — Radar Cooperativo (segmentos 1–3), corte 30/09/2026 · v2

Estado final: **CIERRE TÉCNICO COMPLETO, PRODUCCIÓN PENDIENTE** (PR #1 sin fusionar; despliegue remoto no verificado).
Cada afirmación se etiqueta: **[E]** evidencia comprobada · **[L]** limitación conocida · **[P]** pendiente.

## 1. Verificación del estado inicial (hipótesis del prompt)
| # | Hipótesis | Resultado |
|---|---|---|
| 1 | f4da720 en la rama del PR #1 | [E] Cierto; la rama avanzó con commits posteriores (este expediente). |
| 5 | Parquet base no modificados | [E] Cierto hasta f4da720. **Después** se modificaron de forma justificada (§3). |
| 12 | Workflow no validado en remoto | [E] Ahora validado en dos ejecuciones manuales sobre la rama, sin publicar (§6). |
| 18 | `main` sigue con el flujo anterior | [E] Cierto, y `main` había avanzado: la corrida programada del 18/10 (commit d8f05c1) dejó el **PR en conflicto** y **sobrescribió la historia de solvencia** (§3). Resuelto en la rama; PR `mergeable: clean`. |
Otras hipótesis (corte, 155 pruebas, 67 % arrastrado, patrimonio negativo, mojibake, alerta temprana) se re-verificaron y se corrigieron o precisaron abajo.

## 2. Defectos hallados y tratamiento
| Defecto | Causa raíz | Tratamiento | Evidencia |
|---|---|---|---|
| PR #1 en conflicto con `main` | La corrida programada de `main` (flujo antiguo) actualizó 14 archivos de datos al mismo corte | Merge de `main` en la rama conservando los datos de la rama; antes se comprobó que balance (conteo y suma por fecha), indicadores y PyG de `main` son idénticos en columnas comunes | commit de merge; API: `mergeable_state: clean` |
| `solvencia.parquet` perdió la historia (3.548 → 436 filas; 2020–2026 → solo 2026), tanto en `main` como en la rama | `procesar_solvencia.py` reconstruía desde los ZIP presentes y el workflow solo descarga el año reciente | `fusionar_con_previo` (lo nuevo manda en el solape, la historia se conserva); historia restaurada desde el commit 6c0ddae (3.646 filas, 2020-01→2026-09, 81 meses) | test `SolvenciaTests`; `metadata_solvencia.json` (nota de restauración) |
| 17 cooperativas con **dos identidades** (mojibake 2018–2021 / limpia 2022+, sin solape) | Los ZIP 2018–2021 se leyeron con otra codificación; `normalizar_nombre` no reparaba | `reparar_mojibake` en el normalizador; `scripts/corregir_nombres.py` renombra balance y dimensión; agregados y entidades regenerados; tabla `equivalencias_nombres.csv` | 259 → 242 entidades; panel 255 → 232 cooperativas; 0 mojibake en agg_catalogo |
| 331 observaciones 2020–21 «sin correspondencia» | El mismo mojibake (la dimensión tenía el nombre correcto) | Resueltas por reparación determinista (sin similitud textual): 331/331 → clasificación **exacta** | panel: 0 `balance_historico` |
| 6+1 entidades «X» / «X EN LIQUIDACION» contadas como salida y entrada falsas | La SEPS añade el sufijo al entrar en liquidación | Vínculo por sufijo exacto y fechas contiguas (`identidad.py`); se conserva `cooperativa_fuente` | 0 duplicados coop-mes; salidas 37 → 31 |
| Efecto segmento «significativo» (S2 vs 1, p=0,027) | Artefacto de las series partidas | Tras unificar: p=0,12 (S2), 0,37 (S3) | `resultados_vulnerabilidad.json` |
| Pruebas del workflow podían ocultar fallos (`… | tail`) | Pipe sin `pipefail` | Se quitó el pipe | log remoto: `Ran 164 tests … OK` |
| Workflow: faltaban dependencias del panel; sin entradas seguras | — | `pip install -r requirements.txt`; entradas `forzar_panel` / `publicar` (por defecto sin publicar); `concurrency`; validación estricta; artefacto de evidencia | §6 |

## 3. Reprocesamientos (registro)
- **No se re-descargó ni re-ejecutó** ETL de indicadores, PyG ni CAMEL (nombres limpios; sin cambios de insumo).
- **Parciales justificados:** (a) `solvencia.parquet`: restauración y fusión de historia; (b) `balance.parquet`: renombrado de 18 nombres por lotes (24.873.126 filas antes y después; esquema intacto) + dimensión de segmentos (94.404 → 94.113 filas; 291 colisiones tras renombrar, 1 con segmentos en conflicto resuelto por la regla exacto > arrastrado > corte más reciente); (c) regeneración de `agg_*` y `entidades_cooperativas` (derivados directos del balance); (d) panel derivado y `panel_vulnerabilidad.parquet`.
- Copias de seguridad previas fuera del repositorio; el cambio es reversible desde git.

## 4. Matriz de validación (corte 2026-09-30)
| Componente | Controles | Resultado |
|---|---|---|
| balance | 24.873.126 filas; 242 entidades; 0 nulos; 0 duplicados 2026; S1/S2/S3 = 44/66/91 (+4 mutualistas) | [E] OK |
| pyg / indicadores | 2.476.736 / 628.732 filas; 0 duplicados; corte presente; desde 2020 | [E] OK. PyG +4 filas agregadas `VT_TOTAL*` |
| dim_segmento_historico | 94.113 filas; 0 duplicados; sep-2026 solo con las 205 entidades del boletín | [E] OK / [L] cobertura de sep-2026 |
| solvencia (FS01) | 3.646 filas, 2020-01→2026-09; solo S1, mutualistas, FINANCOOP | [E] OK / [L] cobertura |
| panel S1–S3 | 18.686 filas, 232 cooperativas; identidad contable exacta (ene–nov: A=P+Pat+Res; dic: A=P+Pat) | [E] OK |
| Reconciliación SEPS | morosidad, cobertura, liquidez exactas; ROA 0,9997 / ROE 0,9985 | [E] OK |
| CAMEL | score = media de 5 letras (pesos iguales, percentiles); 205 entidades; Spearman con índice −0,88 (mediana, 81 fechas, n=151–201; último corte −0,87, n=191) | [E] asociación, no validación predictiva |

## 5. Clasificación de segmentos: procedencia y sensibilidad
- Panel: **47,0 % exacta del mes**, 52,5 % arrastrada, 0,5 % estimada, 0 % sin clasificación verificable. En 2020–2026: 34,4 % / 65,1 % / 0,5 %. Julio–agosto 2026: 403/403 arrastradas desde junio. [E]
- Cobertura por año, mes y segmento: `reports/vulnerabilidad/cobertura_segmentos.csv` (también en la página 19). Vistas en la página 17: principal, solo exacta, solo arrastrada, con la composición visible.
- Sensibilidad: el orden descriptivo del índice (S1 < S2 < S3) **se mantiene** con solo clasificación exacta; los efectos FE del segmento no son significativos en ninguna muestra. [E]
- [L] 6.604 observaciones exactas en la estimación FE; no se imputa ninguna clasificación. No se usa el segmento actual para reconstruir el pasado.

## 6. Pruebas
| Prueba | Resultado |
|---|---|
| `python -m unittest discover -s tests` (local, Py 3.13) | **164 pruebas, OK** (79 s) |
| Mismo comando en GitHub Actions (Py 3.11, run 39162548418) | **164 pruebas, OK** (61 s) |
| AppTest páginas 16–19 + interacciones (vistas, umbral, cooperativa, indicador) | sin excepciones |
| **Navegador real** (Chromium/Playwright, `tests/e2e/e2e_descargas.py`): descarga de 3 CSV y comparación de **contenido** con el cálculo independiente | Comparativo (3 filas), Resumen (3 filas), Alertas (40 filas): **OK** |
| Servidor `streamlit run Inicio.py` | `/_stcore/health` y `/` HTTP 200 |
| Workflow manual en la rama (forzar_panel=true, publicar=false), runs 39161974633 y 39162548418 | `success`: panel regenerado (18.686 filas, idéntico al local), validación estricta OK, pruebas OK, artefacto `evidencia-actualizacion`, commit **omitido** |
- [L] No se probó Excel (la app solo exporta CSV). No se midieron tiempos de carga en producción. El E2E cubre 3 de las descargas, no todas.
- [L] El workflow no se probó con un mes nuevo real (la SEPS no había publicado: «Nada que publicar»); la ruta de publicación (commit/push) no se ejecutó.

## 7. Alertas y modelo predictivo
Alertas = z robusto frente a pares del mismo segmento y fecha (umbral 1,5–3,0 seleccionable; detalle con indicador, valor, referencia, regla, período, procedencia y limitaciones; tabla de sensibilidad al umbral) + regla contable de patrimonio total negativo. **No son umbrales regulatorios ni probabilidad de insolvencia.** Modelo de alerta temprana: exploratorio, sin validar (13 entidades con evento y datos previos; AUC agrupa 2–5 entidades de prueba). Plan de investigación en `docs/VULNERABILIDAD_MODULO.md`.
Patrimonio negativo: **real** (20 observaciones, 7 entidades; pérdidas acumuladas > capital+reservas; identidad exacta; 0 duplicados); se conserva y se señala en la app.

## 8. Guía de ejecución y recuperación
- Dependencias: `pip install -r requirements.txt` (Py 3.12 en `runtime.txt`; probado en 3.11 remoto y 3.13 local). Arranque: `streamlit run Inicio.py`. Secreto opcional `ANTHROPIC_API_KEY` solo para el asistente; no se guarda en el repo.
- Regenerar derivados: `python analytics/construir_panel.py . <tmp>` → `python -m analytics.vulnerabilidad.run_all <tmp>/panel_cooperativas_S1S3.parquet reports/vulnerabilidad master_data/panel_vulnerabilidad.parquet` → `python scripts/validar_cierre.py --estricto`.
- Prueba segura del workflow: Actions → «Actualizar datos SEPS» → Run workflow en la rama con `forzar_panel=true`, `publicar=false`.
- Recuperación: los cambios de datos están en commits separados (`git revert` del merge o de los commits `fix(solvencia)` / `fix(nombres)`); la corrida mensual tiene `concurrency` y no hace commit si no hay cambios.

## 9. Estado de GitHub y despliegue
- Rama `feature/segmento-historico-ingesta`; PR #1 abierto, `mergeable_state: clean`; **no hay checks automáticos en el PR** (el workflow solo corre por calendario o manualmente) [L].
- Efecto de fusionar: desde la siguiente corrida programada, `main` ejecutará el flujo nuevo (segmento desde Entidades trimestral, solvencia sin pérdida de historia, panel + validación estricta + pruebas antes de publicar). Un fallo del panel o de las pruebas **bloqueará la publicación** del corte.
- Streamlit Cloud: el README apunta a `https://cooperativas-q73wpzj6f7.streamlit.app`, que responde 303 hacia la autenticación de Streamlit; `docs/CONTEXTO.md` indica que apunta a `main` de `jp1309/cooperativas` (el repo upstream, no este fork). **No se puede verificar desde aquí** qué repositorio/rama sirve, ni los logs. [P]

## 10. Limitaciones y riesgos residuales
1. [L] ~53 % del panel (65 % en 2020+) con segmento arrastrado; S4/S5 y mutualistas fuera del panel.
2. [L] `balance.parquet` pesa 88,9 MB; GitHub rechaza archivos >100 MB y ya emite advertencia (>50 MB). Crece ~1 MB/mes: **riesgo a ≈10 meses**; requiere Git LFS o particionado. Responsable: dueño del repositorio.
3. [L] Identidad por nombre (RUC solo para S1/mutualistas): cambios de razón social distintos del sufijo «EN LIQUIDACION» no se detectan.
4. [L] 30 salidas del panel sin registro posterior no se interpretan como quiebras (posibles fusiones).
5. [L] Capitalización = proxy (A−P)/A; la solvencia regulatoria solo existe para S1/mutualistas/FINANCOOP.
6. [P] Fusión del PR #1 (requiere autorización expresa) y verificación en Streamlit Cloud (requiere acceso del propietario de la app).
