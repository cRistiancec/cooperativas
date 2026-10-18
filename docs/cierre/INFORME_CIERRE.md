# Expediente de cierre — Radar Cooperativo (segmentos 1–3), corte 30/09/2026

Rama `feature/segmento-historico-ingesta` · PR #1 abierto (no fusionado a `main`). Evidencia numérica: `docs/cierre/validacion_componentes.json` (generada por `scripts/validar_cierre.py`, solo lectura).

## 1. Informe de cierre
**Comprobado sin reprocesar:** todos los Parquet de `master_data/` llegan a 2026-09-30 sin duplicados de clave y sin infinitos; `git status` confirma que ningún Parquet base fue modificado en esta etapa. Reconciliación con indicadores SEPS (panel S1–S3): morosidad y cobertura exactas; liquidez exacta (n=14.590); ROA corr 0,9997 y ROE 0,9985 (mediana de diferencia 0).
**Corregido (solo artefactos derivados):** (a) `solvencia_proxy` pasa a (Activos−Pasivos)/Activos: la identidad contable es exacta (A = P + Pat + resultado YTD en ene–nov; en diciembre el resultado ya está cerrado dentro de Pat, A = P + Pat; 100 % de las 18.686 observaciones), por lo que patrimonio/activos tenía un diente de sierra anual (mediana sep 13,7 % → dic 14,3 %); (b) el panel incorpora `segmento_procedencia`.
**Hallazgo central que condiciona la interpretación:** en 2020–2026 el **~67 %** de las observaciones del panel usa un segmento **arrastrado** del último corte trimestral (≤2 meses), no el archivo del propio mes; jul–ago 2026 se arrastran desde junio (100 % de las 403 observaciones). El indicador previo `segmento_historico_estimado` (0,55 %) no captaba el arrastre y por sí solo daba una impresión artificialmente limpia.
**Pendiente:** ver §7.

## 2. Matriz de validación
| Componente | Corte | Controles | Resultado | Evidencia |
|---|---|---|---|---|
| balance | 2026-09-30 | filas 24.873.126; 259 entidades; nulos valor 0 %; dup. clave 2026 = 0; 44/66/91 coop. S1/S2/S3 + 4 mutualistas en el corte | OK | validacion_componentes.json |
| pyg | 2026-09-30 | 2.476.736 filas; dup. = 0; 209 entidades en el corte = 205 + 4 filas agregadas `VT_TOTAL*`; estimado 1,46 % | OK (desde 2020) | idem |
| indicadores | 2026-09-30 | 628.732 filas; dup. = 0; 205 entidades; estimado 0,67 % | OK (desde 2020) | idem |
| dim_segmento_historico | 2026-09-30 | 94.404 filas; dup. = 0; sep-2026 solo con 205 entidades del boletín mensual (meses previos ~917, incluye S4/S5) | Parcial | idem |
| agg_series_temporales | 2026-09-30 | dup. = 0; 205 entidades | OK | idem |
| solvencia (FS01) | 2026-09-30 | solo S1/mutualistas/FINANCOOP, 436 filas | OK (cobertura limitada, de origen) | metadata_solvencia.json |
| Panel S1–S3 | 2026-09-30 | 18.686 filas, 255 coop., dup. 0; identidad contable 100 %; reconciliación SEPS | OK | reports/vulnerabilidad/calidad_panel.json; tests |
| CAMEL existente | 2026-09-30 | 205 entidades, score en [12,7; 88,0], sin NaN; score_total = media de las 5 letras (chequeo puntual exacto); Spearman con índice de vulnerabilidad = −0,87 (coherente) | OK | ejecución del 18/10/2026 |
| Streamlit | — | Ver §5 | Funcional local | AppTest + arranque real |

## 3. Registro de cambios
| Archivo | Motivo / efecto |
|---|---|
| `analytics/construir_panel.py` | liquidez y ROA/ROE oficiales; `solvencia_proxy` = patrimonio total; `segmento_procedencia` |
| `analytics/vulnerabilidad/*` | módulo (índice, panel FE, alerta exploratoria); exporta `master_data/panel_vulnerabilidad.parquet` |
| `master_data/panel_vulnerabilidad.parquet` | artefacto compacto (6,7 MB) que consumen las páginas 16–19 |
| `pages/16–19_*.py`, `utils/panel_vulnerabilidad.py` | paneles A (resumen), B (comparativo), C+D (alertas y ficha), E (calidad) y exportaciones CSV (F) |
| `scripts/validar_cierre.py` | validación de solo lectura reproducible |
| `.github/workflows/actualizar_datos.yml` | paso best-effort que regenera el panel en cada actualización con datos nuevos (**no probado en remoto**) |
| `tests/test_paginas_cierre.py`, `tests/test_vulnerabilidad.py` | pruebas nuevas |
| `docs/VULNERABILIDAD_MODULO.md`, `docs/audit/*` | documentación |

## 4. Registro de reprocesamientos
- **Ninguno** de ingesta, descarga, ETL, indicadores o CAMEL en esta etapa (Parquet base intactos; hash/fecha sin cambios por `git status`).
- **Parcial justificado:** reconstrucción del *panel derivado* (2 veces) por (i) añadir `segmento_procedencia` y (ii) corregir `solvencia_proxy`. Dependencias directas: módulo de vulnerabilidad y `panel_vulnerabilidad.parquet`. Resultado: pruebas verdes tras cada reconstrucción.

## 5. Evidencia de pruebas
- `python -m unittest discover -s tests` → **155 pruebas, OK** (75,9 s).
- AppTest sobre `Inicio.py` y páginas 10, 16–19 → sin excepciones; interacciones (indicador, segmentos, "solo segmento exacto", mínimo de alertas, selección de cooperativa) sin excepciones.
- `streamlit run Inicio.py --server.headless true` → `/_stcore/health` y `/` responden HTTP 200.
- No se probó navegador real ni descarga efectiva de CSV (solo que el botón se construye).

## 6. Guía de ejecución
Python 3.12; `pip install -r requirements.txt` (sin dependencias nuevas). Arranque: `streamlit run Inicio.py`. Regenerar derivados tras actualizar `master_data/`:
```
python analytics/construir_panel.py . <dir_tmp>
python -m analytics.vulnerabilidad.run_all <dir_tmp>/panel_cooperativas_S1S3.parquet reports/vulnerabilidad master_data/panel_vulnerabilidad.parquet
python scripts/validar_cierre.py
```
Memoria: el constructor del panel lee el balance por lotes (≈7 GB suficientes).

## 7. Limitaciones y pendientes
- ~67 % de las observaciones 2020–2026 con segmento arrastrado; jul–ago 2026 desde junio; las comparaciones por segmento en meses intermedios son aproximadas (usar el filtro "solo segmento exacto").
- Panel excluye mutualistas y S4/S5; P&G, indicadores oficiales y CAMEL desde 2020; 2018–2019 sin P&G.
- Solvencia mostrada = proxy; la regulatoria solo existe para S1/mutualistas/FINANCOOP. 20 observaciones con patrimonio total negativo (7 entidades, varias "EN LIQUIDACIÓN"), no depuradas.
- Nombres con mojibake (p. ej. `BAÃ‘OS`) persisten en el balance; 331 observaciones 2020–21 sin fila en la dimensión (`balance_historico`).
- Alerta temprana **no estimable** (8 cooperativas con evento y observaciones previas); las alertas de la app son desviaciones estadísticas internas, no umbrales regulatorios ni probabilidad de insolvencia. El índice de vulnerabilidad es exploratorio y se superpone parcialmente con CAMEL (Spearman −0,87): no sustituye al modelo CAMEL existente.
- Despliegue remoto (Streamlit Cloud) y paso nuevo del workflow: **no verificados**. El PR #1 sigue sin fusionar; la corrida mensual usa `main`.
