# Manual de Usuario — RADAR COOPERATIVO ECUADOR

**Sistema Inteligente para el Monitoreo Integral del Sector Financiero Popular y Solidario**
COSEDE — Coordinación Técnica de Riesgos y Estudios

---

## 1. Acceso y navegación

Al abrir la plataforma se muestra el **Home** (`Inicio.py`), con:

- **Header institucional**: logo, nombre del sistema, fecha/hora, última
  actualización de datos, registros procesados, instituciones y el
  **semáforo general** del sistema.
- **Sidebar** (menú lateral, siempre visible): estado de conexión de datos,
  buscador de cooperativas, indicadores rápidos, favoritos, configuración,
  exportaciones y ayuda — además del menú de navegación entre módulos.
- **KPIs financieros** con mini-tendencias (sparklines) y variación interanual.
- **Resumen Ejecutivo Automático**: texto generado a partir de las
  variaciones reales del sistema (no es un resumen editorial).
- Tarjetas de acceso a los 15 módulos, agrupadas en "Módulos de Análisis",
  "Módulos de Riesgo" y "Analítica Avanzada".

Todos los módulos comparten filtros de **Segmento** (Todos / Segmento 1 / 2 /
3 / Mutualistas) y **Fecha de análisis** en el sidebar.

## 2. Buscador de cooperativas (sidebar)

Escriba parte del nombre de una cooperativa en el campo **"🔎 Buscar
cooperativa"**. Se muestran hasta 5 coincidencias con su ranking por activos,
segmento y valor de activos — sin necesidad de entrar a un módulo específico.

## 3. Módulos de Análisis (base)

| Módulo | Para qué sirve |
|---|---|
| **📊 Panorama** | Vista consolidada: KPIs de mercado, mapas de activos/pasivos (treemap), rankings y crecimiento interanual. |
| **⚖️ Balance General** | Evolución temporal de cualquier cuenta contable, con navegación jerárquica y heatmap de variación interanual. |
| **💰 Pérdidas y Ganancias** | Resultados anualizados (suma móvil 12 meses) en modo absoluto, indexado o de participación. |
| **📈 Indicadores CAMEL** | Los 37 indicadores oficiales de la SEPS, en 7 categorías, con ranking, evolución y heatmap mensual. |

## 4. Módulos de Riesgo

| Módulo | Qué responde |
|---|---|
| **💧 Riesgo de Liquidez** | ¿Qué tan líquida está cada institución? Indicador oficial LIQ + liquidez ampliada calculada + simulador de estrés de retiro. |
| **🧾 Riesgo de Crédito** | ¿Dónde está concentrada la morosidad? Por tipo de cartera, con cobertura, cartera vencida y provisiones. |
| **🏛️ Riesgo de Solvencia** | ¿Cuánto capital respalda a cada institución? Patrimonio/Activos, FK, FI, CAP_NETO. |
| **🧩 Riesgo de Concentración** | ¿Qué tan concentrado está el mercado? HHI, CR5/CR10, curva de Lorenz, Gini. |
| **🕸️ Riesgo Sistémico** | ¿Qué instituciones son más relevantes para la estabilidad del sistema? Índice de Importancia Sistémica. |
| **🧮 CAMEL Score** | Score compuesto 0-100 por institución, con radar comparativo y heatmap. |
| **🚨 Alertas Tempranas** | Ranking de instituciones con más señales de deterioro (semáforo agregado). |

**Cómo leer el semáforo** en Alertas Tempranas y CAMEL Score:
🟢 verde = sin alertas relevantes · 🟡 amarillo = vigilancia · 🔴 rojo = crítico.
Los umbrales exactos están documentados y son ajustables (ver
`config/umbrales_alerta.py`) — **no son límites regulatorios oficiales**.

## 5. Analítica Avanzada

| Módulo | Qué hace |
|---|---|
| **🧪 Stress Testing** | Simula el impacto de shocks de liquidez y deterioro crediticio (escenarios Base/Moderado/Severo/Extremo) sobre el balance real. |
| **📉 Modelos Predictivos** | Proyecta series del sistema a futuro (ARIMA) y predice la morosidad del próximo mes por institución (Random Forest). |
| **🤖 Machine Learning** | Detecta instituciones con perfiles atípicos (Isolation Forest) y las agrupa en segmentos de riesgo (KMeans). |
| **🧠 Asistente Inteligente** | Chat institucional: responde preguntas frecuentes con datos reales; si se configura una clave de Claude, responde preguntas abiertas. |

### 5.1 Cómo usar el Stress Testing
1. Elija el **escenario** (Base, Moderado, Severo, Extremo).
2. Revise los KPIs de impacto agregado (solvencia del sistema antes/después,
   instituciones con brecha de liquidez o capital insuficiente).
3. **Importante**: si la razón de solvencia sube levemente en un escenario
   severo, revise siempre la columna de **Patrimonio en dólares** — puede
   tratarse del efecto mecánico de contracción del balance explicado en el
   expander "Advertencia metodológica" de la página, no de una mejora real.

### 5.2 Cómo usar Modelos Predictivos
- La pestaña de **Forecast** siempre muestra el **MAPE de backtest** (error
  de validación sobre 6 meses ocultos) junto a la proyección — revíselo antes
  de confiar en la proyección.
- La pestaña de **Predicción de Morosidad** muestra el **MAE y R²** de un
  período de prueba no visto durante el entrenamiento, más la importancia de
  cada variable.

### 5.3 Cómo usar el Asistente Inteligente
- Sin configuración adicional, puede preguntar: *"¿Cuántas cooperativas
  hay?"*, *"¿Cuál es el score CAMEL promedio?"*, *"¿Cuáles instituciones
  están en alerta crítica?"* — respuestas ancladas a datos reales.
- Para preguntas abiertas, configure una clave de Claude en el expander
  **"Configurar clave de Claude"** del sidebar (solo se guarda en la sesión
  del navegador).

## 6. Exportar resultados

Cada gráfico Plotly incluye un ícono de cámara en su barra de herramientas
(esquina superior derecha al pasar el mouse) para exportar a PNG. Las tablas
(`st.dataframe`) permiten copiar/ordenar directamente desde la interfaz.

## 7. Preguntas frecuentes

**¿Por qué un módulo dice "Sin datos suficientes para esta selección"?**
Algunos segmentos (p. ej. Mutualistas) tienen pocas instituciones; ciertos
cálculos (percentiles, clustering) requieren un mínimo de observaciones.

**¿Los umbrales de alerta son oficiales de la SEPS/COSEDE?**
No. Son referenciales, calibrados sobre la distribución real del sistema, y
están documentados y centralizados en `config/umbrales_alerta.py` para que
Riesgos y Estudios los audite y ajuste.

**¿Por qué el módulo CAMEL Score no incluye la "S" de sensibilidad a mercado?**
Porque la SEPS no publica esos indicadores en los archivos oficiales que
alimentan la plataforma. Esto se declara explícitamente en la página.
