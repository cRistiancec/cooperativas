# CHANGELOG — RADAR COOPERATIVO ECUADOR (COSEDE)

Registro de la reconstrucción de la plataforma. Formato basado en *Keep a Changelog*.
La reconstrucción es **incremental y no destructiva**: no se elimina lógica de negocio
ni se alteran resultados numéricos.

---

## [Fase 1] — 2026-07-22 — Identidad institucional + tema premium

### Añadido
- **Auditoría integral** del proyecto en `PROYECTO/AUDITORIA_COMPLETA.md`.
- **Capa de estilos** modular en `styles/`: `theme.css` (tokens + base dark),
  `styles.css` (componentes), `responsive.css` (adaptabilidad) y `animations.css`
  (microinteracciones, respeta `prefers-reduced-motion`).
- **Paquete `ui/`**: `theme.py` (inyector de tema cacheado + paleta expuesta a Python)
  y `header.py` (header institucional: logo COSEDE, nombre, subtítulo, autoría,
  fecha/hora, última actualización, registros, instituciones y **semáforo general**).
- Tema oscuro en `.streamlit/config.toml` (`base = "dark"`, azul institucional/petróleo).

### Cambiado
- **Rebranding total**: "Radar Cooperativo Ecuador" → **"SISTEMA POPULAR Y SOLIDARIO"**
  con subtítulo y **autoría institucional de Eco. Cristian Coronel Quezada, MBA — COSEDE**
  (reemplaza la autoría anterior de terceros).
- `Inicio.py` reescrito sobre el nuevo header + tarjetas dark; KPIs y datos del sistema
  ahora se leen **dinámicamente de `metadata.json`** (antes hardcodeados y desactualizados:
  102 meses / jun-2026 / 24.2M registros en lugar de 96 / dic-2025 / 22.7M).
- `utils/charts.py`: `LAYOUT_BASE` y `render_kpi_card` adaptados al tema oscuro
  (fondos transparentes, tipografía clara, `colorway` institucional). **Sin cambios de cálculo.**
- Las 4 páginas (`pages/*`) ahora aplican el tema (`aplicar_tema()`) y usan títulos de marca.

### Corregido
- Instrucción de ejecución errónea en CAMEL (`cooperativas/scripts/...` → `scripts/...`).

### Eliminado
- **Cross-promo externo** al "Radar Bancario" de terceros (`jp1309-bancos.streamlit.app`)
  del `Inicio.py`, inapropiado para una plataforma oficial de COSEDE.

### Preservado (sin tocar)
- Toda la lógica de negocio y cálculos: agregados, KPIs, treemaps, PyG anualizado (12M),
  indicadores CAMEL, escalas/rangos de heatmap y funciones de `data_loader.py`.

### Verificación
- `py_compile` de todos los módulos: OK.
- Smoke test de importación de `ui/` y carga de CSS/metadata: OK.
- Arranque headless de la app (`/_stcore/health` → 200) sin errores en el log.

---

## [Fase 2] — 2026-07-22 — Modularización + Executive Dashboard + Sidebar premium

### Añadido
- **`config/constants.py`**: diccionario `MESES` centralizado (antes duplicado idéntico en
  `pages/2`, `pages/3` y `pages/4`).
- **`utils/data_loader.py` → `obtener_serie_sistema(codigo)`**: función aditiva y cacheada
  que reutiliza `agg_metricas_sistema.parquet` (misma fuente y misma agregación que
  `obtener_metricas_kpi`) para construir series temporales del sistema sin cargar el balance completo.
- **`utils/charts.py` → `crear_sparkline()` y `crear_gauge()`**: mini-tendencias y gauges
  institucionales (Plotly) para el Executive Dashboard.
- **`ui/sidebar.py` → `render_sidebar()`**: sidebar premium con buscador de cooperativas
  (segmento, ranking y activos desde `agg_catalogo_cooperativas`), favoritos persistidos en
  sesión, indicadores rápidos, estado de conexión de datos (verifica existencia de los
  Parquet clave), y expanders de Configuración/Exportaciones/Ayuda. Se antepone a los
  filtros propios de cada página; no reemplaza ninguno.
- **`Inicio.py` — Executive Dashboard**: nueva sección "Indicadores Financieros del Sistema"
  con 4 KPIs (Activos, Cartera, Depósitos, Patrimonio) con delta interanual y sparkline de
  24 meses; gauge de "Índice de Intermediación Referencial" (Cartera/Depósitos); y un
  "Resumen Ejecutivo Automático" generado a partir de las variaciones interanuales reales
  (sin datos inventados).

### Cambiado
- `README.md` actualizado con la marca institucional, autoría COSEDE y estructura de
  carpetas vigente (`ui/`, `styles/`, `config/constants.py`, `PROYECTO/`); se retiró el
  enlace al repositorio de terceros.
- Las 4 páginas y `Inicio.py` ahora invocan `render_sidebar()` al inicio de `main()`.

### Evaluado y descartado (documentado para no repetir el análisis)
- **Eliminar el `sys.path.append` de cada página** (hallazgo A3 de la auditoría): se
  inspeccionó el código fuente de Streamlit 1.53 (`script_runner.py`, `script_data.py`).
  Streamlit inserta en `sys.path` la ruta del **archivo** `main_script_path`, no su
  directorio, por lo que el acceso a `utils/`, `config/`, `ui/` desde `pages/*.py` **no**
  queda garantizado automáticamente. Se decidió **mantener** el `sys.path.append` actual
  para no arriesgar el despliegue en producción; queda para una fase posterior con
  empaquetado formal (`pyproject.toml` instalable).

### Preservado (sin tocar)
- Todos los cálculos y consultas existentes. `obtener_serie_sistema` y los componentes de
  gráficos nuevos son estrictamente aditivos.

### Verificación
- `py_compile` de todos los módulos modificados: OK.
- Smoke test de `obtener_serie_sistema`, `crear_sparkline`, `crear_gauge`, `_estado_archivos_datos`: OK.
- **`streamlit.testing.v1.AppTest`** ejecutó `Inicio.py` y las 4 páginas de `pages/` de punta a
  punta (import + render completo): **sin excepciones** en ninguna.

---

## [Fase 3] — 2026-07-22 — Módulos de Riesgo (Liquidez, Crédito, Solvencia, Concentración, Sistémico, CAMEL Score, Alertas Tempranas)

### Añadido
- **Paquete `analytics/`** — capa de analítica de riesgos, construida exclusivamente sobre datos
  oficiales ya existentes (balance, PyG, indicadores CAMEL de la SEPS):
  - `concentracion.py`: HHI, CR-N, curva de Lorenz, coeficiente de Gini.
  - `liquidez.py`: liquidez ampliada calculada (Fondos Disp. + Inversiones / Depósitos) y
    simulador simple de cobertura ante retiro de depósitos.
  - `credito.py`: panel morosidad/cobertura por tipo de cartera; serie de cartera vencida y provisiones.
  - `solvencia.py`: ratio Patrimonio/Activos calculado del balance.
  - `camels_score.py`: **score compuesto 0-100** por institución vía percentiles orientados
    (mayor=mejor) por categoría C-A-M-E-L, con metodología documentada en el propio módulo.
  - `sistemico.py`: **Índice de Importancia Sistémica (IIS)** basado en tamaño y sustituibilidad
    de mercado (componentes de la metodología D-SIB de Basilea calculables con los datos disponibles).
  - `alertas.py`: motor de reglas de alerta temprana sobre indicadores oficiales + crecimiento
    interanual de depósitos, con semáforo agregado y ranking de deterioro.
- **`config/umbrales_alerta.py`**: umbrales de alerta centralizados, documentados y auditable en
  un solo lugar (no dispersos en código). Calibrados sobre percentiles **P75/P90 reales del
  sistema** (jun-2026), no sobre la mediana — evita que "estar por debajo del promedio" se lea
  como alerta.
- **`utils/charts.py`**: `crear_radar()` (Scatterpolar, para CAMEL/Solvencia) y `crear_lorenz()`
  (curva de Lorenz con línea de igualdad perfecta).
- **7 páginas nuevas** en `pages/`, todas con filtros de segmento/fecha, KPIs, rankings, gráficos
  y una sección de metodología/limitaciones visible en la propia página:
  1. `5_Riesgo_Liquidez.py` — LIQ oficial, liquidez ampliada, distribución (P10-P90), simulador de estrés.
  2. `6_Riesgo_Credito.py` — morosidad/cobertura por cartera, cartera vencida y provisiones, heatmap mensual.
  3. `7_Riesgo_Solvencia.py` — patrimonio/activos, radar FK/FI/CAP_NETO/VULN_PAT/CART_IMPR_PAT.
  4. `8_Riesgo_Concentracion.py` — HHI/CR5/CR10/Gini, curva de Lorenz, Pareto, evolución del HHI.
  5. `9_Riesgo_Sistemico.py` — IIS, ranking, mapa de burbujas (activos × cartera × depósitos).
  6. `10_CAMEL_Score.py` — score compuesto, ranking, radar por cooperativa, heatmap por categoría.
  7. `11_Alertas_Tempranas.py` — semáforo agregado, ranking de deterioro, radar de riesgo, heatmap de alertas.
- `Inicio.py`: nueva sección "Módulos de Riesgo" (7 tarjetas) y accesos rápidos ampliados a los
  11 módulos. `ui/sidebar.py` actualizado con los mismos 7 módulos en favoritos/ayuda.

### Limitaciones declaradas explícitamente (evitar falsa sensación de completitud)
- **Riesgo de Crédito**: vintage curves, roll-rate y matrices de transición **no son calculables**
  con los archivos oficiales actuales (requieren microdata de crédito a nivel de operación). La
  página lo declara en un panel informativo en vez de aproximarlo con datos inventados.
- **Riesgo Sistémico**: no existen datos de exposiciones interbancarias/intercooperativas: el IIS
  cubre tamaño y sustituibilidad (D-SIB), **no** interconectividad/red real. Declarado en la página.
- **CAMEL Score**: cubre las 5 letras clásicas C-A-M-E-L; la SEPS no publica indicadores de
  sensibilidad al riesgo de mercado ("S"), por lo que no es un "CAMELS" completo. La dimensión
  "V - Vulnerabilidad Patrimonial" (categoría oficial SEPS distinta de "C" en el dato fuente) se
  muestra como métrica complementaria, no mezclada en el score CAMEL.
- **Alertas Tempranas**: los umbrales son referenciales/ajustables, explícitamente **no**
  regulatorios oficiales de SEPS/COSEDE.

### Corregido durante el desarrollo (bugs reales detectados por smoke testing, no especulativos)
- `analytics/liquidez.py` y `analytics/sistemico.py`: `DataFrame.fillna()` aplicado sobre el frame
  completo fallaba (`TypeError`) porque `cooperativa`/`segmento` son `category` dtype tras el pivot;
  corregido para aplicar `fillna` solo sobre las columnas numéricas.
- `config/umbrales_alerta.py`: calibración inicial de `MOR_TOT`/`ROE`/`ROA` generaba ~65% de
  instituciones en alerta (umbral cerca de la mediana). Recalibrado sobre P75/P90 reales del
  sistema tras inspeccionar la distribución real con `df.quantile()`.

### Preservado (sin tocar)
- Ningún cálculo de `utils/data_loader.py`, `pages/1-4`, `scripts/` o `config/indicator_mapping.py`
  fue modificado. Toda la analítica nueva es aditiva y se apoya en los mismos datos oficiales.

### Verificación
- `py_compile` de las 7 páginas nuevas + `analytics/` + `config/umbrales_alerta.py`: OK.
- Smoke test end-to-end de los 7 submódulos de `analytics/` con datos reales (fecha jun-2026): OK.
- **`streamlit.testing.v1.AppTest`** sobre las 12 páginas (`Inicio.py` + 11 módulos):
  - Ejecución por defecto: sin excepciones.
  - Segmento pequeño ("SEGMENTO 1 MUTUALISTA", pocas instituciones): sin excepciones.
  - Fecha más antigua disponible: sin excepciones.
- Arranque headless real (`streamlit run Inicio.py`) con `/_stcore/health` → 200, sin errores en el log.

---

## [Fase 4] — 2026-07-22 — Stress Testing, Modelos Predictivos, Machine Learning y Asistente IA

### Añadido — dependencias nuevas
- `requirements.txt`: `scikit-learn==1.9.0`, `statsmodels==0.14.6` (ML/forecast) y `anthropic>=0.40.0`
  (integración opcional del Asistente IA). Se evaluó y **descartó deliberadamente** Prophet/TensorFlow/
  PyTorch/LSTM por su huella de memoria, dado el límite de ~1GB RAM de Streamlit Cloud que el propio
  proyecto ya optimiza agresivamente (ver `README.md`, sección de optimización). Se usó ARIMA
  (statsmodels) en su lugar para el forecast de series.

### Añadido — `analytics/stress_testing.py`
- Motor de shock de balance determinístico y documentado (4 escenarios: Base, Moderado, Severo,
  Extremo), con parámetros de salida de depósitos, incremento de morosidad y tasa de pérdida (LGD
  aproximada) explícitos y ajustables. Mecánica contable simplificada que preserva
  Activos = Pasivos + Patrimonio. Declarado explícitamente como **no** un modelo regulatorio
  ICAAP/Basilea.

### Añadido — paquete `models/` (modelos entrenados en tiempo real, sin pesos versionados)
- `forecast.py`: ARIMA con selección de orden por AIC acotada a 5 combinaciones (sin estacionalidad,
  ~100 observaciones no la soportarían de forma confiable) + backtest honesto (holdout de 6 meses,
  métrica MAPE).
- `prediccion_morosidad.py`: Random Forest que predice la morosidad total del **mes siguiente** por
  cooperativa a partir de sus indicadores del mes actual. Validación con **split temporal** (no
  aleatorio) para evitar fuga de información del futuro.
- `anomalias.py`: Isolation Forest sobre 8 indicadores oficiales (morosidad, cobertura, ROE, ROA,
  liquidez, capitalización, eficiencia, calidad de activos), con explicación simple por z-score de
  las variables más atípicas.
- `clustering.py`: KMeans sobre los scores CAMEL por categoría (`analytics.camels_score`), con
  etiquetado automático de clústeres según su score promedio observado en cada corrida.

### Añadido — 4 páginas nuevas
1. `12_Stress_Testing.py` — selector de escenario, gauge de solvencia post-shock, ranking de
   instituciones más afectadas, detalle completo por cooperativa, supuestos documentados.
2. `13_Modelos_Predictivos.py` — forecast ARIMA de Activos/Cartera/Depósitos/Patrimonio con
   intervalo de confianza 95% y MAPE de backtest visible; predicción de morosidad con MAE/R² del
   holdout, importancia de variables, gráfico predicho-vs-real, y proyección tabular por cooperativa.
3. `14_Machine_Learning.py` — detección de anomalías con lista de instituciones atípicas y sus
   razones, mapa de dispersión morosidad/ROE; segmentación KMeans con resumen por clúster y
   exploración por segmento.
4. `15_Asistente_IA.py` — chat institucional (`services/asistente_ia.py`) con **dos modos reales**:
   asistente local determinístico (siempre activo, responde con datos verificados del sistema, sin
   clave externa) y modo Claude/Anthropic (activo si se configura `st.secrets["ANTHROPIC_API_KEY"]`
   o se ingresa una clave en la sesión), con contexto de datos reales inyectado en el prompt de
   sistema. Manejo de error explícito si la llamada a Claude falla (cae al modo local, no rompe la página).

### Cambiado
- `Inicio.py`: nueva sección "Analítica Avanzada" (4 tarjetas) y accesos rápidos ampliados a los 15
  módulos totales. `ui/sidebar.py` actualizado con los mismos 4 módulos en favoritos/ayuda.

### Resultados reales obtenidos en desarrollo (no simulados, con datos jun-2026)
- Forecast ARIMA de Activos Totales: orden (2,1,1), **MAPE de backtest 2.12%** sobre 6 meses ocultos.
- Random Forest de morosidad: **MAE 0.49 pp, R² 0.984** en holdout temporal (12,450 obs. train /
  1,234 test); la variable más importante es, razonablemente, la morosidad del mes actual (97.4% de
  importancia) — un resultado honesto, no artificialmente inflado.
- Isolation Forest (jun-2026, contaminación 10%): 21 de 203 instituciones marcadas como atípicas.
- KMeans (4 clústeres) sobre score CAMEL: grupos con score promedio 70.1 / 54.4 / 50.4 / 29.4 y 49/53/42/59 instituciones respectivamente.

### Limitaciones declaradas explícitamente
- El Stress Testing es una simplificación de balance, no un modelo de capital regulatorio; no
  incluye efectos de segunda ronda ni contagio entre instituciones.
- El Asistente IA en modo Claude no se probó con una llamada real a la API en este entorno (sin
  clave configurada); se verificó que el código de integración es correcto y que el manejo de error
  sin clave/con fallo de red degrada limpiamente al modo local, sin romper la página.

### Preservado (sin tocar)
- Ningún cálculo de fases anteriores fue modificado. Todo lo nuevo es aditivo sobre los mismos datos
  oficiales.

### Verificación
- `pip install scikit-learn statsmodels anthropic`: instalación limpia, sin conflictos de versiones.
- `py_compile` de `models/`, `services/`, `analytics/stress_testing.py` y las 4 páginas nuevas: OK.
- Smoke test end-to-end con datos reales de los 4 modelos (`forecast`, `prediccion_morosidad`,
  `anomalias`, `clustering`) y del motor de stress testing: OK, resultados arriba.
- **`streamlit.testing.v1.AppTest`** sobre las 16 páginas (`Inicio.py` + 15 módulos): sin excepciones
  en ninguna, incluyendo una pregunta real al asistente local ("¿Cuántas cooperativas hay?" →
  respondió correctamente "259 instituciones", verificado contra `metadata.json`).
- Arranque headless real con `/_stcore/health` → 200, sin errores en el log.

---

## [Fase 5] — 2026-07-22 — Calidad transversal, documentación, logo y logging

### Añadido
- **`tests/test_analytics.py`** (16 tests) y **`tests/test_models.py`** (7 tests): cobertura real
  de `analytics/` (HHI, CR-N, Lorenz, Gini, CAMEL score, alertas, stress testing) con datos
  sintéticos y assertions exactas; y de `models/` (forecast, anomalías, clustering) con
  assertions de estructura/comportamiento. Siguen el patrón `unittest` de `tests/test_actualizacion.py`.
- **`utils/logging_config.py`**: logging centralizado (`get_logger()`), usado en `models/*.py`
  (entrenamiento: tamaño de muestra, métricas) y `services/asistente_ia.py` (llamadas a Claude
  y sus fallos). Streamlit Cloud captura stdout/stderr automáticamente — sin configuración adicional.
- **`assets/logo_cosede.png`** (ruta reservada) + `ui/header.py` actualizado: el header ahora
  incrusta el logo real en base64 si el archivo existe, con fallback automático a un badge de
  texto "COSEDE" si no. Ver `ManualTecnico.md` sección 2 para instrucciones de instalación del logo.
- **`Arquitectura.md`**, **`ManualUsuario.md`**, **`ManualTecnico.md`**: documentación institucional
  completa (capas, flujo de datos, decisiones de arquitectura con su porqué, manual funcional de
  los 15 módulos, instalación, pipeline ETL, configuración del Asistente IA, límites conocidos).

### Corregido — hallazgos reales de las pruebas (no cosméticos)
- **`analytics/stress_testing.py`**: las pruebas revelaron que, bajo shocks de depósitos grandes
  frente a la pérdida crediticia, la razón Patrimonio/Activos puede subir levemente (el
  denominador se contrae más rápido que el numerador) — una propiedad **real y conocida** de los
  ratios de solvencia no ponderados por riesgo, no un bug. Se documentó explícitamente en el
  docstring de `aplicar_escenario()` y en un nuevo expander "⚠️ Advertencia metodológica" en
  `pages/12_Stress_Testing.py`, y se añadió soporte para pasar parámetros de escenario
  directamente (no solo por nombre) para poder aislar el efecto crediticio puro en las pruebas.
- **Diagnóstico de entorno**: se detectaron y eliminaron procesos Streamlit huérfanos de
  lanzamientos previos de verificación que no se habían cerrado correctamente, causando fallos
  por falta de memoria (OOM) en pruebas posteriores — no relacionado con el código de la
  aplicación. Verificado con `ps`/`free` antes y después.

### Verificación
- Suite completa de tests: **25/25 OK** (`python -m unittest discover -s tests`).
- `py_compile` de todo el proyecto (incluyendo `tests/`): OK.
- **`streamlit.testing.v1.AppTest`** sobre las 16 páginas: **0 fallas / 16**, tras liberar memoria
  del entorno.
- Arranque headless real con `/_stcore/health` → 200, sin errores en el log; proceso detenido y
  verificado sin residuos (`ps aux | grep streamlit` limpio).

### Pendiente (fuera de alcance de esta entrega)
- Linter automatizado (`ruff`/`flake8`) para forzar PEP8 de forma continua.

---

## [Fase 5b] — 2026-07-22 — Logo institucional

### Añadido
- `assets/logo_cosede.png`: ícono del candado institucional (azul/amarillo/rojo), generado con
  Pillow como **reconstrucción propia** de los colores y la composición del logo de COSEDE. No se
  pudo extraer el binario exacto de la imagen pegada en el chat (no existe una herramienta para
  volcar un adjunto de chat a disco); se documentó explícitamente en `ManualTecnico.md` sección 2
  que este archivo debe reemplazarse por el activo oficial pixel-perfecto cuando esté disponible
  (el header lo toma automáticamente por ruta, sin cambios de código).

### Verificación
- `AppTest` sobre `Inicio.py` con el logo real cargado: sin excepciones.
- Suite completa de tests: 25/25 OK. Entorno verificado sin procesos Streamlit residuales.
