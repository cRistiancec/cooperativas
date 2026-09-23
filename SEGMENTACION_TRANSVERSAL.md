# AMPLIACIÓN — SEGMENTACIÓN TRANSVERSAL Y ESTABILIZACIÓN FUNCIONAL

**Sistema Popular y Solidario — COSEDE**
Coordinación Técnica de Riesgos y Estudios · Eco. Cristian Coronel Quezada, MBA

| | |
|---|---|
| **Fecha** | 28 de julio de 2026 |
| **Alcance** | Diagnóstico funcional de las 16 páginas + Filtro Global de Segmento en las 15 páginas de análisis |
| **Método** | Ejecución real de cada página (`streamlit.testing.AppTest`), servidor Streamlit vivo, y suite de pruebas automatizadas |
| **Estado final** | ✅ **Estable — 0 excepciones en las 16 páginas** |
| **Pruebas automatizadas** | 54 pruebas / 79 subpruebas — **todas en verde** |

---

## Fase 1 — Diagnóstico completo

Antes de tocar un solo archivo se auditó la plataforma completa:

- Las 16 páginas ejecutadas de extremo a extremo con `AppTest` (no solo compiladas: **corridas**, con el mismo motor que usa `streamlit run`).
- Cada selector de segmento existente (14 páginas) accionado al menos una vez.
- Cada comparativo llevado a su máximo de 8-10 cooperativas.
- Los selectores anidados en pestañas (heatmaps con Top-N, sliders de clusters, selector de variable de forecast) accionados individualmente.
- Un servidor Streamlit real, ya en ejecución en el entorno, consultado por HTTP para las 16 rutas y su log de aplicación (`logs/app.log`) revisado en busca de excepciones.

### Resultado del diagnóstico

**No se encontró ningún módulo roto.** Las 16 páginas cargaron sin excepción, todos los filtros probados respondieron correctamente y no hay ninguna traza de error en el log del servidor. La causa más probable de la percepción de "módulos que dejaron de funcionar" es la fragmentación del filtro de segmento en 14 componentes independientes (detallada abajo): cambiar el segmento en un módulo no se reflejaba en los demás, lo que en un recorrido rápido por la plataforma puede leerse como inconsistencia o mal funcionamiento aunque técnicamente cada página respondiera bien de forma aislada.

| Verificación | Resultado |
|---|---|
| Carga de las 16 páginas (`Inicio.py` + 15 módulos) | ✅ 0 excepciones |
| 14 selectores de segmento pre-existentes, accionados | ✅ 0 excepciones |
| Comparativos al máximo de cooperativas (Balance General, PyG, CAMEL) | ✅ 0 excepciones |
| Widgets anidados en pestañas (Crédito, CAMEL Score, Alertas, Stress, ML, Modelos Predictivos) | ✅ 0 excepciones |
| Suite de pruebas heredada (51 pruebas) | ✅ 51/51 |
| Servidor Streamlit real — 16 rutas HTTP | ✅ 200 en todas, log sin errores |

### Único hallazgo real: filtro de segmento fragmentado

| Módulo afectado | Causa raíz | Impacto | Prioridad | Estrategia |
|---|---|---|---|---|
| 14 páginas (todas excepto Inicio, Asistente IA) | Cada página declaraba su propio `st.sidebar.selectbox("Segmento", ...)` con una `key` distinta (`seg_liq`, `seg_credito`, `segmento_global`, `segmento_pyg`, `seg_forecast`, `seg_mora_proy`, ...) y, en 9 de ellas, derivaba la lista de segmentos de un DataFrame distinto por página en vez de una fuente única | El segmento elegido en un módulo se perdía al navegar a cualquier otro — filtro aislado, no dimensión global de análisis | Alta (pedido explícito de esta ampliación) | Componente único `ui/filtros.py` con una `key` de `session_state` compartida |
| `pages/13_Modelos_Predictivos.py` | Tenía **dos** selectores de segmento independientes en la misma página (uno por pestaña: `seg_forecast` y `seg_mora_proy`) | El forecast ARIMA y la proyección de morosidad podían mostrar segmentos distintos en la misma pantalla | Media | Un único filtro de página, aplicado a ambas pestañas |

No se encontraron errores de importación, de DataFrames, de gráficos ni de caché. No se comenzó ninguna implementación nueva hasta confirmar —con la ejecución real de las 16 páginas— que no quedaba ningún módulo roto.

---

## Fase 2 — Estabilización

Con el diagnóstico en cero, la "estabilización" se limitó a **no introducir ninguna regresión** durante el refactor de la Fase 3, verificado de dos formas:

1. **Antes/después de cada archivo tocado**: recompilación (`py_compile`) y ejecución (`AppTest`) inmediatamente después de cada edición.
2. **Al cierre**: los 16 módulos listados en el pedido —Dashboard Principal, Resumen Ejecutivo, Liquidez, Crédito, Solvencia, Concentración, Riesgo Sistémico, CAMEL, Rankings, Comparativos, Reportes, Exportaciones, Modelos Predictivos— vueltos a ejecutar de punta a punta.

| Módulo | Estado |
|---|---|
| Dashboard Principal / Resumen Ejecutivo (Inicio) | ✅ |
| Panorama (Rankings, mapas de mercado) | ✅ |
| Balance General (Comparativos, heatmap, ranking) | ✅ |
| Pérdidas y Ganancias (Comparativos, ranking) | ✅ |
| Indicadores CAMEL | ✅ |
| Riesgo de Liquidez | ✅ |
| Riesgo de Crédito | ✅ |
| Riesgo de Solvencia | ✅ |
| Riesgo de Concentración | ✅ |
| Riesgo Sistémico | ✅ |
| CAMEL Score (Reportes/exportación de tabla) | ✅ |
| Alertas Tempranas | ✅ |
| Stress Testing (Reportes/exportación de tabla) | ✅ |
| Modelos Predictivos | ✅ |
| Machine Learning | ✅ |
| Asistente Inteligente | ✅ |

**No debe quedar ninguna excepción**: verificado — 0 excepciones en las 16 páginas, en dos rondas independientes (antes y después de la Fase 3).

Un hallazgo colateral de este proceso: la prueba automatizada heredada `test_cambiar_segmento_en_camel_score` (en `tests/test_smoke_pages.py`) referenciaba la `key` local `seg_score`, que dejó de existir al centralizar el filtro. Se corrigió para apuntar a la nueva `key` compartida (`SPS_SEGMENTO_KEY`) — de no corregirse, esta prueba habría quedado permanentemente en rojo a partir de esta ampliación.

---

## Fase 3 — Segmentación transversal

### Variable de segmentación

La variable **`segmento`** ya estaba presente y es consistente en las 5 fuentes que la contienen (`balance.parquet`, `pyg.parquet`, `indicadores.parquet`, `agg_ranking_cooperativas.parquet`, `agg_catalogo_cooperativas.parquet`), con 4 valores oficiales: `SEGMENTO 1`, `SEGMENTO 1 MUTUALISTA`, `SEGMENTO 2`, `SEGMENTO 3`. No existen Segmento 4 ni Segmento 5 en la fuente oficial de la SEPS — no es un dato faltante, es el alcance real de la publicación (ya documentado en `VALIDACION_FINAL_DATOS.md`, sección 3).

### Componente único: `ui/filtros.py`

```python
def render_filtro_segmento() -> str:
    segmentos = ["Todos"] + obtener_segmentos_disponibles_rapido()
    return st.sidebar.selectbox(
        "Segmento", options=segmentos, index=0,
        key=SPS_SEGMENTO_KEY,  # key única compartida por toda la plataforma
        help="Filtra toda la página por segmento. La selección se mantiene al navegar entre módulos.",
    )
```

Reutiliza `obtener_segmentos_disponibles_rapido()`, la misma función ya cacheada (`st.cache_data`) que la plataforma usaba antes — no se agregó ninguna lectura de datos nueva. Se exporta desde `ui/__init__.py` junto al resto de componentes institucionales (`aplicar_tema`, `render_header`, `render_sidebar`).

### Cómo persiste entre páginas — y una corrección sobre la marcha

La primera versión de este componente asumía que bastaba con una `key` de `st.session_state` compartida (`st.selectbox(..., key="sps_segmento_global")`) para que el valor sobreviviera a la navegación entre páginas, apoyada en pruebas con `AppTest` que precargaban esa key antes de ejecutar cada página por separado.

**Al probar la aplicación real en un navegador** (Playwright, sirviendo `streamlit run Inicio.py` y navegando de verdad entre páginas — ver Fase 6) esa suposición resultó **incorrecta**: en las apps multipágina "clásicas" de carpeta `pages/` (el patrón que usa esta plataforma), Streamlit **no conserva el valor de un widget entre páginas** aunque la `key` sea idéntica — cada página resetea el estado de sus propios widgets al navegar, incluso dentro de la misma sesión de navegador y sin recarga completa (confirmado con un repro mínimo de dos páginas: el mismo `st.selectbox(key="x")` volvía a su valor por defecto al pasar de una página a otra). Las pruebas con `AppTest` no detectaban esto porque cada `AppTest.from_file()` ejecuta una página de forma aislada — nunca reproduce la navegación real del cliente.

Se corrigió aplicando el patrón que Streamlit documenta para este caso exacto ("widgets that persist across pages"): una key de `session_state` **plana** y persistente (`SPS_SEGMENTO_KEY`) separada de la key del widget en sí; antes de crear el widget se copia el valor persistente a su key interna (`_cargar_valor_persistente`), y un callback `on_change` copia el valor de vuelta cuando el usuario cambia la selección (`_guardar_valor_persistente`). `st.session_state` como variable plana sí persiste de forma nativa entre páginas — es solo el valor *atado a un widget* el que no lo hace.

**Verificado de punta a punta en la aplicación real** (no solo con `AppTest`): con el servidor Streamlit corriendo, se navegó en un navegador headless de Inicio → Panorama → Riesgo de Crédito, seleccionando "SEGMENTO 2" en Inicio. El segmento se mantuvo en las dos páginas siguientes, y los KPIs de Panorama cambiaron correctamente a los valores de ese segmento ($3,806M en Activos Totales, 64 cooperativas — la misma cifra ya verificada por otras vías en este documento). Capturas en el cierre de este documento.

### Migración — 14 filtros aislados → 1 componente

| Página | Antes | Después |
|---|---|---|
| Inicio | `segmento_home` (propio, agregado en la validación anterior) | `render_filtro_segmento()` |
| 1 · Panorama | `segmento_panorama` | `render_filtro_segmento()` |
| 2 · Balance General | `segmento_global` (derivaba la lista de `obtener_segmentos_disponibles_rapido()` igual) | `render_filtro_segmento()` |
| 3 · Pérdidas y Ganancias | `segmento_pyg` (derivaba la lista de `pyg.parquet` directamente) | `render_filtro_segmento()` |
| 4 · CAMEL | `segmento_camel` (derivaba la lista de `indicadores.parquet` directamente) | `render_filtro_segmento()` |
| 5-12, 14 (Liquidez, Crédito, Solvencia, Concentración, Sistémico, CAMEL Score, Alertas, Stress, ML) | `seg_liq`, `seg_credito`, `seg_solv`, `seg_conc`, `seg_sist`, `seg_score`, `seg_alertas`, `seg_stress`, `seg_ml` — cada una derivando la lista de un DataFrame de esa página | `render_filtro_segmento()` |
| 13 · Modelos Predictivos | `seg_forecast` + `seg_mora_proy` (**dos** selectores independientes en la misma página) | `render_filtro_segmento()` — **un solo selector, aplicado a ambas pestañas** |
| 15 · Asistente Inteligente | n/a (chat sin cortes propios) | n/a — sin cambio, coincide con el alcance del pedido |

Ningún DataFrame ni proceso de carga se duplicó: el componente solo reemplaza el *widget*; las funciones de filtrado (`df[df["segmento"] == segmento_sel]`, `obtener_serie_sistema(codigo, segmento)`, `obtener_metricas_kpi(fecha, segmento)`, etc.) son exactamente las mismas que ya existían.

### Alcance cubierto

Todos los puntos listados en el pedido:

Resumen Ejecutivo y Dashboard Principal (Inicio) · Riesgo de Liquidez · Riesgo de Crédito · Riesgo de Solvencia · Riesgo de Concentración · Riesgo Sistémico · Indicadores CAMEL · Rankings (Panorama, Balance General, PyG, CAMEL, Crédito) · Comparativos (Balance General, PyG, CAMEL) · Alertas Tempranas · Evolución Histórica (Balance General) · Stress Testing · Modelos Predictivos (forecast **y** proyección de morosidad) · Reportes (tablas exportables de CAMEL Score y Stress Testing).

### Comportamiento esperado — verificado con datos reales

| Módulo | "Todos" | Al filtrar | Verificado |
|---|---|---|---|
| CAMEL Score — tabla de clasificación | 203 filas, score promedio 50.1 | **SEGMENTO 3**: 91 filas, score promedio 50.2 | ✅ |
| Stress Testing — tabla de detalle exportable | 203 filas | **SEGMENTO 2**: 64 filas, **100 % de las filas pertenecen a SEGMENTO 2** | ✅ |
| Inicio — KPI Activos Totales | $31 530 M | Suma de los 4 segmentos = $31 530 M (partición exacta, sin duplicar ni perder) | ✅ (ya verificado en `VALIDACION_FINAL_DATOS.md`) |

### Optimización — sin reprocesos

- **No se vuelve a leer la base de datos al cambiar el segmento.** `cargar_balance()`, `cargar_pyg()`, `cargar_indicadores()` y los 4 `agg_*` siguen siendo `st.cache_data`: el cambio de segmento dispara un rerun de Streamlit (inevitable en su modelo de ejecución), pero el DataFrame en memoria no se vuelve a leer del disco — solo se re-filtra.
- **`st.session_state`**: es el mecanismo mismo por el que el filtro es global (ver arriba).
- **`st.cache_data`**: cada combinación (fecha, segmento) ya consultada queda cacheada; volver a un segmento visitado antes no recalcula nada.
- **`st.cache_resource`**: sin cambios — sigue usándose solo donde ya se usaba (el modelo de morosidad entrenado en Modelos Predictivos).
- El propio widget del filtro no agrega ninguna lectura: `obtener_segmentos_disponibles_rapido()` opera sobre `agg_metricas_sistema.parquet` (45 KB), el mismo agregado pequeño que el resto de la plataforma ya cacheaba.

---

## Fase 4 — Validación de los reportes

Verificado con datos reales, no solo por inspección de código (tabla de la Fase 3). Adicionalmente:

- **Totales**: el KPI "Activos Totales" del home cambia consistentemente al filtrar, y la suma de los 4 segmentos reproduce el total sin duplicar ni perder registros (partición exacta).
- **Gráficos**: los rankings y heatmaps de riesgo (Crédito, CAMEL Score, Stress Testing) se regeneran con el universo filtrado — mismo mecanismo de siempre (`df[df["segmento"]==...]` antes de graficar), ahora alimentado por un único valor de origen.
- **Tablas**: la tabla exportable de Stress Testing quedó reducida y homogénea (100 % SEGMENTO 2) al filtrar por ese segmento.
- **Exportaciones**: las exportaciones de la plataforma son (a) PNG de cada gráfico Plotly desde su propia barra de herramientas y (b) CSV desde el ícono de descarga de cada `st.dataframe`. Ambas operan sobre la figura/tabla ya construida con el segmento aplicado — no hay una ruta de exportación separada que pudiera quedar desincronizada.

**No se encontró ningún reporte utilizando información distinta al resto** de la página en la que vive.

---

## Fase 5 — Comparativo de Cooperativas

Este módulo ya había sido optimizado en la validación anterior (`VALIDACION_FINAL_DATOS.md`, sección 4): truncamiento de nombres sin colisiones (`truncar_nombres_unicos`), altura proporcional al número de instituciones (`altura_por_categorias`), leyenda que escala con el número de series (`layout_leyenda_series`), `automargin`, `cliponaxis=False` y nombre completo preservado en cada tooltip.

En esta ampliación se revalidó que el refactor del filtro de segmento no lo afectó — el cambio en cada página fue estrictamente el widget de segmento, en un punto del layout anterior a la sección de comparativo:

| Página | Comparativo | Máximo probado | Resultado |
|---|---|---|---|
| Balance General | `cooperativas_evol` (multiselect) | 10 | ✅ sin excepción |
| Pérdidas y Ganancias | `cooperativas_evol_pyg` (multiselect) | 10 | ✅ sin excepción |
| CAMEL | `cooperativas_evol` (multiselect) | 8 | ✅ sin excepción |

Sin sobreposición de textos, con la misma legibilidad medida en la validación anterior.

---

## Fase 6 — Validación final

| Verificación | Resultado |
|---|---|
| Las 16 páginas cargan | ✅ 0 excepciones (segunda ronda, tras el refactor completo) |
| Todos los filtros funcionan (segmento global + fecha + modo + escenario + cluster) | ✅ |
| Todos los gráficos renderizan | ✅ 49 gráficos Plotly en total, mismo conteo que antes del refactor |
| Todos los KPIs responden | ✅ |
| Todos los reportes usan el mismo período de información | ✅ (heredado de `VALIDACION_FINAL_DATOS.md`, sin cambios) |
| El filtro de segmento funciona en toda la plataforma | ✅ 15/15 páginas de análisis, un único componente |
| No existen errores de ejecución | ✅ |

### Prueba en la aplicación real (`streamlit run`), no solo en pruebas automatizadas

Se ejecutó `streamlit run Inicio.py` de verdad y se condujo un navegador headless (Playwright/Chromium) contra el servidor vivo — la única forma de probar lo que un usuario real experimenta, incluida la navegación entre páginas que `AppTest` no puede reproducir.

1. **Servidor real arrancado y saludable**: `curl http://localhost:8501/_stcore/health` → `ok`.
2. **Inicio renderiza con datos reales**: activos $31 530 M, cartera $18 598 M — coincide con las cifras verificadas en `VALIDACION_FINAL_DATOS.md`.
3. **El Filtro Global de Segmento se accionó con un clic real** sobre el `<select>` de BaseWeb en el sidebar, eligiendo "SEGMENTO 2": los 4 KPIs del home cambiaron a $3 806 M / $2 559 M / $3 025 M / $477 M, con la leyenda "Indicadores filtrados por SEGMENTO 2." — confirma la Fase 3 con datos reales, no solo con `AppTest`.
4. **Navegación real de Inicio → Panorama → Riesgo de Crédito** (clics sobre el menú de páginas del sidebar, sin recargar la pestaña): el segmento se mantuvo en "SEGMENTO 2" en ambas páginas siguientes, y el KPI "Total Activos" de Panorama mostró exactamente $3 806 M (64 cooperativas) — el mismo total que muestra CAMEL Score para ese segmento en las pruebas automatizadas.
5. **Sin errores de página** (`page.on("pageerror")`) durante toda la sesión.

Este recorrido con navegador real fue el que expuso el hallazgo de la sección anterior (la key compartida ingenua no persistía entre páginas) — una prueba que ninguna batería de `AppTest` podía detectar por construcción, y la razón concreta por la que vale la pena "correr" la aplicación, no solo probarla por partes.

### Rendimiento — antes/después del refactor

| Página | Antes | Después |
|---|---|---|
| Inicio | 0,90 s / 167 MB | 0,79 s / 169 MB |
| Panorama | 1,29 s / 186 MB | 0,96 s / 190 MB |
| Balance General | 17,16 s / 2 651 MB | 12,44 s / 2 474 MB |
| CAMEL | 2,23 s / 382 MB | 1,63 s / 402 MB |
| Modelos Predictivos | 12,04 s / 469 MB | 10,89 s / 470 MB |

Las variaciones están dentro del ruido normal de medición (entrenamiento de modelos en tiempo real, estado de caché del proceso); no hay ningún incremento significativo de tiempo, memoria ni CPU atribuible a la centralización del filtro — es, si acaso, menos código ejecutándose por página (una función en vez de una construcción de lista + selectbox repetida).

### Pruebas automatizadas

```
55 passed, 79 subtests passed
```

| Archivo | Qué agrega esta ampliación |
|---|---|
| `tests/test_consistencia_datos.py::FiltroGlobalSegmentoTests` | **Nuevo** (5 pruebas): ninguna página vuelve a declarar su propio selectbox de segmento, todas importan `render_filtro_segmento`, cada página se hidrata desde la key persistente, y cambiar el widget actualiza esa key vía `on_change` (round-trip completo del patrón de persistencia) |
| `tests/test_smoke_pages.py::FiltrosTests::test_cambiar_segmento_en_camel_score` | **Corregido dos veces**: primero para apuntar a la key compartida en vez de la `key` local `seg_score` (ya eliminada); luego, al introducir la key sombra del widget, para localizar el selector por su etiqueta ("Segmento") en vez de por key interna |

`FiltroGlobalSegmentoTests.test_ninguna_pagina_define_su_propio_selectbox_de_segmento` es la guardia permanente de esta ampliación: si una página futura vuelve a declarar un `st.sidebar.selectbox("Segmento", ...)` propio en lugar de reutilizar el componente, la suite falla.

---

## Cumplimiento de restricciones

| Restricción | Cumplimiento |
|---|---|
| No generar una nueva arquitectura | ✅ El componente vive en `ui/`, el paquete que ya alojaba `render_sidebar` y `render_header` |
| No duplicar procesos | ✅ Cero lecturas de datos nuevas; se **eliminaron** 9 derivaciones redundantes de la lista de segmentos (una por página) en favor de la única ya cacheada |
| No reconstruir módulos existentes | ✅ Cada página conserva su estructura, sus pestañas y su lógica de negocio intactas; el único cambio es de dónde viene el valor `segmento_sel` |
| Recuperar el 100 % de los módulos con errores | ✅ No había módulos rotos que recuperar (diagnóstico exhaustivo, Fase 1); se corrigió 1 prueba automatizada que habría quedado obsoleta |
| Filtro global único y reutilizable | ✅ `ui/filtros.py::render_filtro_segmento()`, usado por las 15 páginas de análisis |
| Evitar duplicidad de código y DataFrames | ✅ 14 bloques de selectbox → 1 función; 9 derivaciones de lista de segmentos → 1 función cacheada |
| Único proceso de carga de datos | ✅ Sin cambios en `utils/data_loader.py`; el filtro solo cambia el parámetro `segmento` que ya recibían las funciones existentes |
| Todas las visualizaciones responden al segmento | ✅ Verificado con datos reales en CAMEL Score y Stress Testing (Fase 3/4) |
| Rendimiento mantenido o mejorado | ✅ Sin incrementos significativos (tabla de la Fase 6) |
| Documentación antes de producción | ✅ Este documento |

### Archivos modificados en esta ampliación

**Nuevo:** `ui/filtros.py`

**Modificados:** `ui/__init__.py` · `Inicio.py` · `pages/1_Panorama.py` · `pages/2_Balance_General.py` ·
`pages/3_Perdidas_Ganancias.py` · `pages/4_CAMEL.py` · `pages/5_Riesgo_Liquidez.py` ·
`pages/6_Riesgo_Credito.py` · `pages/7_Riesgo_Solvencia.py` · `pages/8_Riesgo_Concentracion.py` ·
`pages/9_Riesgo_Sistemico.py` · `pages/10_CAMEL_Score.py` · `pages/11_Alertas_Tempranas.py` ·
`pages/12_Stress_Testing.py` · `pages/13_Modelos_Predictivos.py` · `pages/14_Machine_Learning.py` ·
`tests/test_smoke_pages.py` (corrección de key obsoleta) · `tests/test_consistencia_datos.py` (pruebas nuevas)

**Sin modificar:** `analytics/` · `models/` · `config/` · `services/` · `styles/` · `ui/theme.py` ·
`ui/header.py` · `scripts/` · `.streamlit/config.toml` · `master_data/` · `pages/15_Asistente_IA.py`

---

## Conclusión

El diagnóstico exhaustivo de la Fase 1 —ejecución real de las 16 páginas, servidor Streamlit vivo, y la suite de pruebas heredada— no encontró módulos rotos. Lo que sí existía era una segmentación **fragmentada**: 14 filtros de segmento independientes, con 9 de ellos derivando el catálogo de segmentos de un DataFrame distinto por página, y una página (Modelos Predictivos) con dos selectores de segmento simultáneos. Se reemplazaron por un único componente reutilizable (`ui/filtros.py`), con una sola `key` de `session_state`, de modo que el segmento es ahora una dimensión global de análisis: se elige una vez y se mantiene en cualquier módulo al que se navegue, sin releer datos y sin duplicar código.

**Estado: estable, con segmentación transversal, apto para producción.**

---

*Documento generado como parte de la ampliación del proyecto.
COSEDE — Coordinación Técnica de Riesgos y Estudios.*
