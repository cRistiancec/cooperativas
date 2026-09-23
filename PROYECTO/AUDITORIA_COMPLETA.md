# AUDITORÍA COMPLETA DEL PROYECTO

## SISTEMA POPULAR Y SOLIDARIO
### Sistema Inteligente para el Monitoreo Integral del Sector Financiero Popular y Solidario

**Autor institucional:** Eco. Cristian Coronel Quezada, MBA — Coordinación Técnica de Riesgos y Estudios, COSEDE
**Estado del proyecto auditado:** `Radar Cooperativo Ecuador` (Streamlit multipágina en producción, Streamlit Cloud)
**Fecha de auditoría:** 22 de julio de 2026
**Alcance:** Análisis técnico integral previo a la reconstrucción. Este documento **no modifica código**; describe el estado real, los hallazgos y la hoja de ruta.

---

## 0. Resumen ejecutivo

El proyecto es una aplicación **Streamlit multipágina** funcional y ya desplegada en producción que analiza el sistema de cooperativas de ahorro y crédito del Ecuador con datos oficiales de la **SEPS**. La arquitectura de datos es sólida (capa de agregados pre-calculados en Parquet + caché de Streamlit), lo que le da un rendimiento razonable pese a manejar ~24 millones de registros de balance.

Sin embargo, evaluado contra el objetivo institucional (plataforma tipo Bloomberg / Moody's / Power BI Premium), presenta brechas importantes:

| Dimensión | Estado actual | Brecha |
|---|---|---|
| **Lógica de negocio / cálculos** | Correcta y funcional | Ninguna — **se debe preservar íntegra** |
| **Arquitectura de datos** | Buena (agregados + caché) | Menor (afinamiento) |
| **Arquitectura de código** | Monolítica por página, con duplicación | Alta |
| **Identidad / marca** | "Radar Cooperativo" + autoría de terceros | Total (rebranding a COSEDE) |
| **Diseño / UI** | Tema claro básico de Streamlit | Total (front premium, dark institucional) |
| **Cobertura analítica de riesgos** | 4 módulos descriptivos | Alta (faltan liquidez, crédito, solvencia, sistémico, CAMELS, stress, alertas, ML/IA) |
| **Calidad (tests, logging, typing)** | Mínima | Alta |
| **Consistencia de metadatos** | Valores hardcodeados desactualizados | Media |

**Veredicto:** el núcleo analítico y de datos es reutilizable y de calidad; la reconstrucción debe ser **incremental y no destructiva**, enfocándose en (1) rebranding, (2) capa de presentación premium, (3) modularización, (4) expansión de módulos de riesgo, y (5) calidad de ingeniería.

---

## 1. Estructura y arquitectura actual

### 1.1 Árbol de archivos

```
cooperativas/
├── Inicio.py                       # Landing / home (554 líneas)
├── requirements.txt                # Dependencias con versiones fijadas
├── README.md
├── .streamlit/config.toml          # Tema claro + config server
├── .devcontainer/devcontainer.json
├── .github/workflows/actualizar_datos.yml   # Automatización mensual de datos
├── pages/                          # Páginas Streamlit (navegación automática)
│   ├── 1_Panorama.py               # 321 líneas
│   ├── 2_Balance_General.py        # 963 líneas  ← la más grande
│   ├── 3_Perdidas_Ganancias.py     # 492 líneas
│   └── 4_CAMEL.py                  # 463 líneas
├── utils/
│   ├── __init__.py
│   ├── data_loader.py              # 513 líneas — carga + consultas cacheadas
│   └── charts.py                   # 361 líneas — componentes Plotly + KPI cards
├── config/
│   ├── __init__.py
│   └── indicator_mapping.py        # 505 líneas — códigos, colores, CAMEL
├── scripts/                        # Pipelines ETL (offline)
│   ├── descargar_datos_seps.py     # 276 — scraping portal SEPS
│   ├── seps_zip.py                 # 124 — inspección de ZIP fuente
│   ├── procesar_balance_cooperativas.py  # 456 — ETL balances
│   ├── procesar_pyg.py             # 308 — ETL PyG (desacumulación + 12M)
│   ├── procesar_camel.py           # 536 — ETL indicadores CAMEL
│   ├── procesar_indicadores.py     # 330 — ETL legacy
│   ├── generar_agregados.py        # 147 — genera agregados desde balance
│   └── validar_actualizacion.py    # 132 — validación post-actualización
├── tests/
│   └── test_actualizacion.py       # 123 — único archivo de test
├── docs/
│   └── CONTEXTO.md                 # Notas de continuidad del proyecto
└── master_data/                    # Capa de datos (Parquet + JSON)
    ├── balance.parquet             # 82 MB  ← dato pesado
    ├── pyg.parquet                 # 19 MB
    ├── indicadores.parquet         # 3.8 MB
    ├── agg_ranking_cooperativas.parquet   # 1.4 MB
    ├── agg_series_temporales.parquet      # 1.3 MB
    ├── agg_metricas_sistema.parquet       # 45 KB
    ├── agg_catalogo_cooperativas.parquet  # 11 KB
    ├── metadata.json
    ├── metadata_agregados.json
    └── metadata_indicadores.json
```

### 1.2 Patrón arquitectónico

- **Presentación:** Streamlit multipágina nativa (`pages/` con prefijo numérico para ordenar el menú).
- **Acceso a datos:** módulo `utils/data_loader.py` con dos estrategias:
  1. **Rápida** — funciones sobre agregados pre-calculados (`agg_*.parquet`), cacheadas con `@st.cache_data(ttl=3600)`. Es la vía correcta para KPIs, rankings y treemaps.
  2. **Completa** — `cargar_balance()`, `cargar_pyg()`, `cargar_indicadores()` que leen los Parquet grandes; se usan solo cuando se requiere detalle contable (4–6 dígitos).
- **Configuración/dominio:** `config/indicator_mapping.py` centraliza códigos contables, segmentos, paletas de color y taxonomía CAMEL.
- **Componentes visuales:** `utils/charts.py` con funciones Plotly reutilizables (`crear_treemap`, `crear_linea_temporal`, `crear_heatmap`, `crear_ranking_barras`, `render_kpi_card`).
- **ETL:** `scripts/` desacoplado de la app; alimentado por un **workflow de GitHub Actions** (`actualizar_datos.yml`) que descarga datos SEPS y regenera los Parquet mensualmente.

**Fortaleza clave:** la separación datos-crudos → agregados → app está bien concebida. La app **no** filtra 24M de registros en caliente para lo común; usa agregados de KB/MB. Esto es lo que se debe conservar y potenciar.

---

## 2. Modelo de datos

### 2.1 Volumen y cobertura (según `metadata.json`)

- **Registros de balance:** 24.169.638
- **Cooperativas:** 259 (Segmentos 1, 2, 3 y Mutualistas — "SEGMENTO 1 MUTUALISTA")
- **Período:** ene-2018 → **jun-2026** (102 meses)
- **Cuentas contables:** 1.563

### 2.2 Esquemas

- `balance.parquet`: `fecha, segmento, cooperativa, codigo, cuenta, valor` (+ `ruc`, `nivel` no usados en UI).
- `pyg.parquet`: `fecha, segmento, cooperativa, codigo, cuenta, valor_acumulado, valor_mes, valor_12m` (desacumulación de PyG + suma móvil 12 meses — cálculo correcto y valioso).
- `indicadores.parquet`: `cooperativa, segmento, fecha, codigo, indicador, valor, categoria`. **Valores en ratio (0–1), no en porcentaje** (la UI multiplica ×100).
- `agg_metricas_sistema.parquet`: métricas por `fecha/segmento/codigo` con `valor_total` y `num_cooperativas`.
- `agg_ranking_cooperativas.parquet`: `fecha, segmento, cooperativa, codigo, valor` (base de rankings y treemaps).
- `agg_series_temporales.parquet`: series por cooperativa/cuenta para gráficos de evolución.
- `agg_catalogo_cooperativas.parquet`: catálogo ordenado por activos.

### 2.3 Observaciones de datos

- La estrategia de tipos `category` en `codigo/cuenta/segmento/cooperativa` reduce memoria correctamente.
- Los indicadores CAMEL provienen del **pivot cache** de las tablas dinámicas oficiales de la SEPS (37 indicadores en 7 categorías), lo que da confiabilidad regulatoria.
- **No hay** definiciones prudenciales de umbrales/semáforos institucionalizadas en datos; solo `RANGOS_HEATMAP` para colorear. Para el objetivo (semáforos, alertas tempranas) se requerirá una **capa de reglas/umbrales**.

---

## 3. Hallazgos por severidad

### 3.1 🔴 Críticos (bloquean el objetivo institucional / afectan identidad)

| # | Hallazgo | Ubicación | Impacto |
|---|---|---|---|
| C1 | **Marca y autoría incorrectas.** La app se llama "Radar Cooperativo Ecuador" y el footer atribuye la autoría a "Juan Pablo Erráez T.". El objetivo exige "SISTEMA POPULAR Y SOLIDARIO" con autoría de **Eco. Cristian Coronel Quezada, MBA — COSEDE**. | `Inicio.py:18,201,545`; `menu_items`; `page_title` de las 4 páginas | Institucional/legal |
| C2 | **Cross-promo a un producto externo de terceros** ("Radar Bancario", enlace a `jp1309-bancos.streamlit.app`). Inapropiado para una plataforma oficial de COSEDE. | `Inicio.py:465-505` | Institucional |
| C3 | **Tema visual básico de Streamlit** (fondo blanco, CSS improvisado inline). Contradice el requisito de "front premium, dark institucional, no aspecto por defecto". | `.streamlit/config.toml`; CSS inline en `Inicio.py:38-177` y en cada página | Producto |
| C4 | **Cobertura analítica insuficiente** frente a lo requerido: no existen módulos dedicados de Riesgo de Liquidez, Crédito, Solvencia, Concentración, Sistémico, Operacional, Alertas Tempranas, CAMELS con score, Stress Testing, ML ni Asistente IA. | Toda la app (solo 4 páginas) | Producto |

### 3.2 🟠 Altos (arquitectura, mantenibilidad, consistencia)

| # | Hallazgo | Ubicación | Impacto |
|---|---|---|---|
| A1 | **Metadatos hardcodeados y desactualizados.** El home muestra "8 años", "96 meses", "Dic 2025", "22.7 millones de registros", "259 cooperativas + 4 mutualistas", cuando `metadata.json` dice 102 meses, jun-2026, 24.2M registros. El docstring de `data_loader.py` dice "97 meses". | `Inicio.py:211-253,517-519`; `menu_items:29`; `data_loader.py:5` | Confiabilidad del dato mostrado |
| A2 | **Duplicación de código transversal.** `MESES` (dict es→) repetido en 3 páginas; `_crear_ranking_cached` reimplementado en varias páginas; `st.set_page_config` + bloque CSS repetidos; `obtener_color_cooperativa` importado desde dos orígenes distintos (`utils.charts` vs `config.indicator_mapping`). | `pages/*`, `utils/charts.py` | Mantenibilidad |
| A3 | **Inyección de `sys.path` en cada archivo** (`sys.path.append(...parent...)`). Es un anti-patrón; debería resolverse con paquete instalable / imports relativos / `PYTHONPATH`. | Todas las páginas y `utils/charts.py` | Portabilidad |
| A4 | **Instrucciones de ejecución erróneas en la UI.** CAMEL sugiere `python cooperativas/scripts/procesar_camel.py` y Panorama `python scripts/generar_agregados.py`: rutas inconsistentes (el prefijo `cooperativas/` ya no aplica en este repo). | `pages/4_CAMEL.py:143`; `pages/1_Panorama.py:103` | UX/soporte |
| A5 | **Página monolítica de 963 líneas** (`2_Balance_General.py`) mezcla consultas, transformaciones y render. Difícil de mantener y testear. | `pages/2_Balance_General.py` | Mantenibilidad |
| A6 | **Sin capa de estilos.** No existen `styles.css`, `theme.css`, `responsive.css`, `animations.css`; todo el CSS vive inline en Python con `unsafe_allow_html`. | Proyecto | Producto/mantenibilidad |
| A7 | **Sin logging ni manejo de excepciones estandarizado.** Errores se tragan con `except Exception: return []` (p.ej. `3_Perdidas_Ganancias.py:74`), ocultando fallos de datos. | `pages/3`, varios | Observabilidad |

### 3.3 🟡 Medios (rendimiento, buenas prácticas)

| # | Hallazgo | Ubicación | Impacto |
|---|---|---|---|
| M1 | **Caché de figuras Plotly con `@st.cache_data`.** Se cachean objetos `go.Figure` (mutables/serializables) — funciona pero es frágil y consume memoria; conviene cachear los *datos* y construir la figura fuera de caché, o usar `st.cache_resource` con criterio. | `pages/1:37-78`, `pages/2:40-114` | Memoria/robustez |
| M2 | **Carga del balance completo (82 MB) para tareas evitables.** `obtener_orden_cooperativas_por_activos` en PyG llama a `cargar_balance()` solo para ordenar por activos, cuando existe `agg_catalogo_cooperativas.parquet` (11 KB) con ese orden. | `pages/3:57-75` | CPU/memoria/tiempo |
| M3 | **`@st.cache_data` sin `ttl` en varias funciones** (CAMEL) vs `ttl=3600` en otras: política de caché inconsistente. | `pages/4:52,65,81` | Consistencia |
| M4 | **`PALETA_COOPERATIVAS` y ~200 colores hardcodeados por nombre de cooperativa.** Frágil ante altas/bajas/renombres de entidades; romperá silenciosamente el color al cambiar el universo. | `config/indicator_mapping.py:103-330` | Mantenibilidad |
| M5 | **Sin `.streamlit/secrets` ni configuración para claves** (necesario para el futuro Asistente IA / LLM). | Proyecto | Preparación |
| M6 | **`kaleido` en requirements** (export estático) sin uso evidente en la app; validar si es necesario. | `requirements.txt` | Peso de entorno |

### 3.4 🟢 Bajos / cosméticos

- Comentarios y docstrings mezclan español con y sin tildes; inconsistencia menor de estilo.
- `menu_items['About']` con texto desactualizado.
- Ausencia de `CHANGELOG.md`, `Arquitectura.md`, `ManualUsuario.md`, `ManualTecnico.md` (solicitados).
- No hay `pyproject.toml`/linting (PEP8 no forzado), ni `type checking`.

---

## 4. Seguridad

| Ítem | Estado | Nota |
|---|---|---|
| `unsafe_allow_html=True` | Uso extensivo | Aceptable porque el HTML es **estático y propio** (no interpola input de usuario). Debe mantenerse esa invariante al centralizar CSS. |
| XSRF / CORS | `enableXsrfProtection = true`, `enableCORS = false` | Correcto. |
| Secretos | No hay manejo | A introducir con `st.secrets` para el módulo IA. **Nunca** hardcodear claves. |
| Datos | Públicos (SEPS) | Sin PII sensible; el riesgo de exposición es bajo. |
| Dependencias | Versiones fijadas (`==`) | Bien para reproducibilidad; conviene revisión periódica de CVEs. |

**No se detectaron vulnerabilidades de inyección** dado que no hay interpolación de entrada de usuario dentro del HTML ni ejecución dinámica.

---

## 5. Rendimiento y consumo de recursos

**Fortalezas**
- Agregados pre-calculados evitan escanear 24M de filas en la mayoría de vistas.
- Lectura selectiva de columnas en Parquet (`columns=[...]`).
- Conversión a `category` para reducir memoria.
- `@st.cache_data(ttl=3600)` en las consultas calientes.

**Oportunidades** (ordenadas por impacto)
1. Sustituir `cargar_balance()` por agregados donde solo se necesita orden/catálogo (M2).
2. Cachear **datos**, no figuras (M1); reduce huella de memoria del caché.
3. Cargar `balance.parquet`/`pyg.parquet` **de forma diferida** y solo en las páginas que lo requieren (lazy import + `st.cache_resource` para el DataFrame base).
4. Unificar `ttl` y política de invalidación por versión de datos (usar `metadata.json['fecha_procesamiento']` como clave de caché).
5. Considerar **DuckDB** sobre los Parquet para consultas ad-hoc del detalle contable sin cargar todo en memoria (mejora escalabilidad hacia los nuevos módulos de riesgo).

---

## 6. Inventario funcional (lo que NO se debe romper)

Estos cálculos y vistas están **correctos** y deben preservarse bit a bit durante la reconstrucción:

- **Panorama:** KPIs del sistema (activos, cartera, depósitos, patrimonio, # cooperativas), treemaps jerárquicos de activos y de pasivos/patrimonio, rankings, crecimiento YoY (cartera y depósitos).
- **Balance General:** evolución comparativa multi-cooperativa, filtros jerárquicos por cuenta, heatmap YoY, ranking por cuenta.
- **Pérdidas y Ganancias:** valores anualizados (suma móvil 12M), modos absoluto/indexado/participación, ranking por cuenta, jerarquía 4-Gastos / 5-Ingresos.
- **CAMEL:** 37 indicadores en 7 categorías (C/A/M/E/L), ranking por indicador, evolución temporal, heatmap mensual con escalas y rangos calibrados por percentiles.
- **Reglas de negocio a preservar:** indicadores en ratio→%×100; desacumulación PyG; orden por activos; mapeo de códigos contables SEPS; escalas de color "mayor/menor es mejor".

> **Regla de oro de la reconstrucción:** ningún resultado numérico puede cambiar sin justificación documentada. Se recomienda una prueba de regresión (golden tests) que fije los valores actuales de KPIs por fecha/segmento antes de refactorizar.

---

## 7. Mapa de brechas vs. objetivo institucional

| Requisito del objetivo | ¿Existe hoy? | Acción |
|---|---|---|
| Nombre "SISTEMA POPULAR Y SOLIDARIO" + autoría COSEDE | ❌ | Rebranding (Fase 1) |
| Header institucional (logo, fecha/hora, última actualización, estado, # registros, semáforo) | ❌ (header simple) | Componente header (Fase 1) |
| Sidebar premium (menú, buscador, favoritos, config, ayuda, exportaciones, estado) | ❌ (filtros básicos) | Rediseño sidebar (Fase 2) |
| Dark mode institucional + CSS modular | ❌ | `theme/` CSS (Fase 1) |
| Home tipo Executive Dashboard (KPIs animados, sparklines, gauges, heatmaps, alertas, resumen automático) | Parcial | Home nuevo (Fase 2) |
| Módulos: Liquidez, Crédito, Solvencia, Concentración, Sistémico, Operacional | ❌ | Nuevos módulos (Fase 3) |
| Alertas Tempranas (semáforos, radar, ranking de deterioro) | ❌ | Nuevo módulo + capa de reglas (Fase 3) |
| CAMELS con score/radar/semáforo/ranking | Parcial (CAMEL descriptivo) | Ampliar (Fase 3) |
| Concentración (HHI, CR5/CR10, Lorenz, Pareto) | ❌ | Nuevo módulo (Fase 3) |
| Stress Testing / Escenarios | ❌ | Nuevo módulo (Fase 4) |
| ML (XGBoost, RF, LightGBM, Isolation Forest, clustering, forecast, LSTM/ARIMA/Prophet) | ❌ | Módulo ML (Fase 4) |
| Asistente IA (OpenAI/Claude/Gemini/local) con chat institucional | ❌ | Módulo IA (Fase 4) |
| Visualizaciones avanzadas (ECharts, AgGrid, PyDeck, Sankey, radar, gauge, sunburst…) | Parcial (Plotly) | Ampliar librería (Fase 2-3) |
| Documentación (README, CHANGELOG, Arquitectura, Manuales) | Parcial (README) | Docs (transversal) |
| Calidad (PEP8, typing, docstrings, logging, tests) | Mínima | Transversal |

---

## 8. Arquitectura objetivo propuesta

Reorganización **no destructiva** (se mueve/renombra, no se elimina lógica):

```
SISTEMA_POPULAR_Y_SOLIDARIO/
├── app.py                     # Entry point (reemplaza Inicio.py, mantiene lógica)
├── pages/                     # Páginas (módulos de riesgo)
├── ui/                        # Header, sidebar, layout, componentes de página
├── components/                # KPI cards, semáforos, gauges, alert badges (reutilizables)
├── charts/                    # Fábricas de gráficos (Plotly/ECharts/AgGrid/PyDeck)
├── services/                  # Acceso a datos, caché, exportación, (IA/LLM)
├── analytics/                 # Cálculos de riesgo: liquidez, crédito, solvencia, HHI, CAMELS, stress
├── models/                    # ML/forecast (preparado; entrenamiento offline)
├── config/                    # Dominio: códigos, umbrales prudenciales, temas
├── styles/                    # styles.css, theme.css, responsive.css, animations.css
├── assets/                    # Logo COSEDE, íconos, fuentes
├── utils/                     # Helpers (fechas, formato, logging)
├── data/ (master_data)        # Parquet + metadata (sin cambios de datos)
├── tests/                     # Golden tests + unitarios
├── docs/                      # Arquitectura, manuales, changelog
└── PROYECTO/                  # Auditoría y registro de cambios
```

---

## 9. Hoja de ruta de reconstrucción (incremental y segura)

**Fase 0 — Blindaje (antes de tocar lógica)**
- Golden tests que fijan KPIs/rankings actuales por fecha/segmento.
- `CHANGELOG.md` y registro de cambios en `PROYECTO/`.

**Fase 1 — Identidad + tema premium (bajo riesgo, alto impacto)**
- Rebranding total → "SISTEMA POPULAR Y SOLIDARIO" + autoría COSEDE; retirar cross-promo externo.
- Capa `styles/` (dark institucional) + `config.toml`; header institucional; corrección de metadatos hardcodeados (leer de `metadata.json`).

**Fase 2 — Modularización + Home ejecutivo + Sidebar**
- Extraer duplicación (`MESES`, rankings, colores, config) a `ui/`, `components/`, `charts/`.
- Home tipo Executive Dashboard; sidebar premium; eliminar `sys.path` hacks.

**Fase 3 — Módulos de riesgo (reusando datos existentes)**
- Liquidez, Crédito, Solvencia, Concentración (HHI/CR/Lorenz), Sistémico, CAMELS con score, Alertas Tempranas (capa de umbrales/semáforos en `config/`).

**Fase 4 — Analítica avanzada**
- Stress Testing / Escenarios; módulo ML (entrenamiento offline, inferencia en app); Asistente IA con `st.secrets`.

**Transversal:** logging, typing, docstrings, PEP8, tests, y documentación (Arquitectura/Manuales) actualizados por fase.

---

## 10. Riesgos de la reconstrucción y mitigación

| Riesgo | Mitigación |
|---|---|
| Romper cálculos al modularizar | Golden tests (Fase 0) + refactor por extracción, no reescritura |
| Regresión de rendimiento | Medir antes/después; conservar estrategia de agregados + caché |
| Ruptura de despliegue en Streamlit Cloud | Mantener compatibilidad de versiones (`requirements.txt` fijado); cambios por PR incremental |
| Alcance excesivo en un solo paso | Entrega por fases; cada fase deja la app funcional y desplegable |
| Datos desactualizados en UI | Fuente única de verdad = `metadata.json` (sin hardcodear) |

---

*Fin de la auditoría. Este documento es la línea base para el registro de cambios que se mantendrá en `PROYECTO/` durante la reconstrucción.*
