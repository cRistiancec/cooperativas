# Filtros globales y combinables (período ∩ segmentos ∩ entidades ∩ calidad de clasificación)

Un único filtro, definido en la barra lateral (`ui/filtros.py`) y evaluado por `utils/filtros_analisis.py`, gobierna **todas** las páginas
(Inicio y 1–19): gráficos, tablas, KPI, alertas, fichas y exportaciones CSV/Excel. No hay filtros de segmento duplicados por página.

## Módulo reutilizable
- `utils/filtros_analisis.py` (puro, sin Streamlit): `FiltroAnalisis` (inmutable y *hashable* → clave de caché), `aplicar_filtros_analisis`,
  `entidades_disponibles`, `reconciliar_entidades`, `cobertura`, `resumen_poblacion`, `exportar_csv`, `exportar_excel`.
- `ui/filtros.py`: `render_filtros_globales`, `filtro_actual`, `selector_fecha_corte`, `render_resumen_filtro`, `exigir_datos`, `botones_descarga`.
- `utils/data_loader.py`: `datos_filtrados(nombre, filtro)`, `datos_universo(nombre, filtro)`, `acotar_entidades`.
- Estado: claves planas `sps_f_*` en `st.session_state` (persisten entre páginas); los widgets usan claves sombra `_w_*`.

## Semántica de la combinación
- Intersección de los cuatro criterios; **selección vacía = sin restricción** de esa dimensión.
- Las entidades ofrecidas dependen del período, los segmentos y la calidad elegidos; al cambiar éstos, las entidades que dejan de cumplir
  se **descartan con aviso** (nunca se conservan en silencio). Botón «Restablecer». Combinación vacía → mensaje, sin gráficos vacíos.
- Cada página muestra el resumen de la selección y su cobertura (entidades, observaciones, procedencia de la clasificación).

## Segmento «en el momento» (point-in-time)
- Fuente: `master_data/dim_observaciones.parquet` (una fila por cooperativa-fecha; generada por `scripts/generar_dim_observaciones.py`).
- `segmento_clasif` es el segmento vigente **en esa fecha**; `segmento_actual` (el actual) se conserva solo como referencia y **nunca** se usa
  retroactivamente para filtrar. La columna legada `segmento` en las páginas equivale al segmento puntual.
- `procedencia_clasif`: `oficial_mes` (publicado para ese mes), `arrastrado` (de otro corte), `estimado`, `no_verificable`.
  Las observaciones no verificables **nunca** satisfacen una restricción de segmento (no se asignan en silencio).
- Filtro de calidad: todas / oficial del período / arrastrada / estimada / no verificable.
- Efecto de los cambios de segmento: una entidad que cambia de segmento sale de las ventanas (variación interanual, persistencia, composición
  de series) donde no cumple el filtro en ambas fechas; por eso un promedio por segmento puede variar de composición entre meses (se indica en pantalla).

## Universo vs. selección
Los análisis **relativos** (score CAMEL, IIS, percentiles del radar de alertas, anomalías/KMeans, z-scores del panel, amplitud) se calculan sobre
el *universo* (período + segmentos + calidad, sin entidades) y luego se acota la visualización a las entidades elegidas: un percentil sobre 1–2
entidades carecería de sentido. Excepción documentada: la base de la variación interanual.

## Exportaciones
`botones_descarga` exporta exactamente la tabla mostrada. CSV: UTF-8 con BOM y cabecera `# clave: valor` (filtros, corte, cobertura; leer con
`comment="#"`). Excel: hojas `datos` y `filtros`.

## Limitaciones
- Solvencia oficial FS01 solo cubre Segmento 1, Mutualistas y FINANCOOP; identidad por nombre (RUC solo S1).
- Clasificación estimada/arrastrada ≈ 53 % de las observaciones: usar el filtro de calidad para análisis estrictos.
- Las columnas de clasificación son `Categorical` (memoria PyG 700 → 107 MB); no usar `st.cache_data` sobre DataFrames enormes.
- Verificado localmente (pruebas, AppTest y navegador real). **No** verificado en el despliegue de producción.
