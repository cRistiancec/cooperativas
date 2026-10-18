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
