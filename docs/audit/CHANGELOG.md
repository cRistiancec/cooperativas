# CHANGELOG (auditoría)
- 2026-10-16: Sesión 1. Solo lectura del repo; creados PROJECT_STATE.md y DATA_COVERAGE.csv. Sin cambios al código ni a los datos.
- 2026-10-17: Sesión 2. Parche de ingesta con segmento histórico (rama local, 2 commits). Ver PROJECT_STATE.md.
- 2026-10-18 (S3): dimensión de segmento desde la fuente, panel reconstruido, COBERTURA_SEGMENTOS_MENSUAL.csv, SALIDAS_DEL_PANEL.csv, EVENTOS_ESTADO_JURIDICO_CANDIDATOS.csv; estados C-01..C-04 actualizados.

## Sesión 4
- Panel: liquidez (11/(2101+210305+210310)) y ROA/ROE (YTD anualizado, promedio desde dic. previo) reconcilian con SEPS; 12m/solo-vista quedan como alternas.
- Nuevo módulo `analytics/vulnerabilidad/` (índice, panel FE, alerta exploratoria), tests y `docs/VULNERABILIDAD_MODULO.md`.
- Alerta temprana declarada no estimable (8 cooperativas con evento y observaciones previas).

## Sesión 5 (cierre)
- C-06 resuelto: identidad A = P + Pat + resultado YTD (ene–nov) y A = P + Pat (dic) exacta; `solvencia_proxy` = patrimonio total.
- Nuevo `segmento_procedencia`; ~67 % del panel 2020–2026 usa segmento arrastrado.
- Páginas 16–19 en Streamlit; `master_data/panel_vulnerabilidad.parquet`; expediente en `docs/cierre/`.

## Sesión 6 (producción)
- Merge de `main` (conflicto de datos) y restauración de la historia de solvencia; unificación de identidades (mojibake, sufijo EN LIQUIDACION); workflow seguro con validación estricta y pruebas; pruebas E2E con navegador. Ver `docs/cierre/INFORME_CIERRE.md`.

## Sesión 7 (peso de datos)
- `scripts/optimizar_parquet.py`: reordenamiento físico + zstd, lossless y verificado; `master_data/` 123,7 → 60,6 MB. Escritores migrados de snappy a zstd; paso en el workflow; control de 95 MB en `validar_cierre.py`; `tests/test_optimizar_parquet.py` (167 pruebas OK).

## Sesión 8 (filtros globales)
- Filtro global combinable (período ∩ segmentos ∩ entidades ∩ calidad de clasificación) con segmento puntual en las 20 páginas; `utils/filtros_analisis.py`, `ui/filtros.py`, `master_data/dim_observaciones.parquet` (+ paso en el workflow, validación estricta y optimizador). Exportaciones CSV/Excel con metadatos de filtros. Ver `docs/FILTROS_GLOBALES.md`. 206 pruebas OK; E2E con Chromium OK; producción NO verificada.
