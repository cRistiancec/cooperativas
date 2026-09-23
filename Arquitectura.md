# Arquitectura — RADAR COOPERATIVO ECUADOR

git pull origin main && python -c "import json; d=json.load(open('master_data/metadata.json')); print('fecha_max:', d['fecha_max'], '| registros:', d['registros_totales'])"
`ManualTecnico.md` (operación y mantenimiento). Generado tras la reconstrucción
por fases documentada en `CHANGELOG.md`.

---

## 1. Visión general

El sistema es una aplicación **Streamlit multipágina**. Cada archivo en
`pages/` es una página independiente ejecutada por el runtime de Streamlit;
`Inicio.py` es el punto de entrada (home / executive dashboard). La navegación
entre páginas es automática (Streamlit ordena `pages/` por el prefijo numérico
del nombre de archivo).

```
Usuario ──▶ Inicio.py / pages/N_*.py
                │
                ├─▶ ui/          (tema, header, sidebar — presentación institucional)
                ├─▶ analytics/   (cálculos de riesgo sobre datos ya cargados)
                ├─▶ models/      (ML/forecast, entrenados en tiempo real)
                ├─▶ services/    (integraciones externas: Claude/Anthropic)
                ├─▶ utils/       (carga de datos cacheada, componentes de gráficos)
                └─▶ config/      (dominio: códigos contables, colores, umbrales)
                        │
                        ▼
                master_data/*.parquet + metadata*.json
```

## 2. Capas y responsabilidades

| Capa | Responsabilidad | No debe contener |
|---|---|---|
| `pages/`, `Inicio.py` | Orquestación de UI: layout, filtros, llamadas a `analytics/`/`models/`/`utils/`, render de gráficos | Lógica de cálculo de riesgo ni acceso directo a Parquet |
| `ui/` | Tema visual, header institucional, sidebar premium | Cálculos de negocio |
| `analytics/` | Fórmulas de riesgo (concentración, solvencia, liquidez, crédito, CAMEL score, sistémico, alertas, stress testing) | Renderizado (`st.*`) — son funciones puras que reciben/devuelven DataFrames |
| `models/` | ML/forecast entrenados en tiempo real (sin pesos versionados) | Acceso a archivos — reciben DataFrames ya cargados |
| `services/` | Integraciones externas (Claude/Anthropic) | Cálculos de riesgo |
| `utils/` | Carga de datos cacheada (`data_loader.py`), componentes de gráficos Plotly (`charts.py`), logging | Reglas de negocio de riesgo |
| `config/` | Constantes de dominio: códigos contables SEPS, paletas de color, umbrales de alerta | Lógica ejecutable compleja |
| `styles/` | CSS modular (tema dark institucional) | — |
| `master_data/` | Datos procesados (Parquet + JSON), generados por `scripts/` | — nunca se edita a mano |
| `scripts/` | Pipelines ETL offline (descarga SEPS → Parquet) | Código de la app en vivo |

## 3. Estructura de archivos

```
cooperativas/
├── Inicio.py                       # Home / Executive Dashboard
├── pages/
│   ├── 1_Panorama.py               # KPIs, treemaps, rankings, crecimiento YoY
│   ├── 2_Balance_General.py        # Evolución de cuentas, heatmap YoY
│   ├── 3_Perdidas_Ganancias.py     # PyG anualizado (12M)
│   ├── 4_CAMEL.py                  # 37 indicadores oficiales SEPS
│   ├── 5_Riesgo_Liquidez.py
│   ├── 6_Riesgo_Credito.py
│   ├── 7_Riesgo_Solvencia.py
│   ├── 8_Riesgo_Concentracion.py
│   ├── 9_Riesgo_Sistemico.py
│   ├── 10_CAMEL_Score.py
│   ├── 11_Alertas_Tempranas.py
│   ├── 12_Stress_Testing.py
│   ├── 13_Modelos_Predictivos.py
│   ├── 14_Machine_Learning.py
│   └── 15_Asistente_IA.py
├── ui/
│   ├── theme.py                    # aplicar_tema() — inyecta styles/*.css
│   ├── header.py                   # render_header() — logo, KPIs, semáforo
│   └── sidebar.py                  # render_sidebar() — buscador, favoritos, estado
├── styles/
│   ├── theme.css                   # tokens de diseño (colores, radios, sombras)
│   ├── styles.css                  # componentes (header, cards, KPIs, semáforos)
│   ├── responsive.css              # adaptación a pantallas pequeñas
│   └── animations.css              # microinteracciones
├── analytics/
│   ├── concentracion.py            # HHI, CR-N, Lorenz, Gini
│   ├── liquidez.py                 # liquidez ampliada, simulador de cobertura
│   ├── credito.py                  # panel morosidad/cobertura, cartera vencida
│   ├── solvencia.py                # patrimonio/activos
│   ├── camels_score.py             # score compuesto 0-100 (percentiles C-A-M-E-L)
│   ├── sistemico.py                # Índice de Importancia Sistémica (IIS)
│   ├── alertas.py                  # motor de reglas de alerta temprana
│   └── stress_testing.py           # shock de balance por escenario
├── models/
│   ├── forecast.py                 # ARIMA + backtest
│   ├── prediccion_morosidad.py     # Random Forest, split temporal
│   ├── anomalias.py                # Isolation Forest
│   └── clustering.py               # KMeans sobre scores CAMEL
├── services/
│   └── asistente_ia.py             # Claude (Anthropic) + asistente local determinístico
├── utils/
│   ├── data_loader.py              # Carga cacheada (agregados + completos)
│   ├── charts.py                   # Fábricas de gráficos Plotly (tema oscuro)
│   └── logging_config.py           # get_logger() — logging centralizado
├── config/
│   ├── indicator_mapping.py        # Códigos contables, segmentos, colores, CAMEL
│   ├── constants.py                # MESES compartido
│   └── umbrales_alerta.py          # Umbrales de Alertas Tempranas (auditable, ajustable)
├── assets/
│   └── logo_cosede.png             # Logo institucional (ver ManualTecnico.md)
├── scripts/                        # ETL offline (SEPS → Parquet)
├── master_data/                    # Parquet + metadata (datos procesados)
├── tests/                          # Tests unitarios (unittest)
├── docs/                           # Notas de continuidad del proyecto
└── PROYECTO/
    └── AUDITORIA_COMPLETA.md       # Auditoría integral previa a la reconstrucción
```

## 4. Flujo de datos

1. **ETL offline** (`scripts/`, disparado por `.github/workflows/actualizar_datos.yml`):
   descarga los boletines de la SEPS, los normaliza y genera los Parquet de
   `master_data/` (`balance.parquet`, `pyg.parquet`, `indicadores.parquet`) más
   los agregados pre-calculados (`agg_*.parquet`) usados para KPIs rápidos.
2. **Carga en la app** (`utils/data_loader.py`): funciones `@st.cache_data`
   que leen los Parquet. Existen dos vías:
   - **Rápida**: sobre `agg_*.parquet` (KB/MB) — KPIs, rankings, treemaps.
   - **Completa**: `cargar_balance()`/`cargar_pyg()`/`cargar_indicadores()`
     sobre los Parquet grandes — solo cuando se necesita detalle contable.
3. **Analítica** (`analytics/`): funciones puras que reciben los DataFrames ya
   cargados y devuelven DataFrames con las métricas de riesgo calculadas.
4. **Modelos** (`models/`): igual que `analytics/`, pero con entrenamiento de
   ML en tiempo de ejecución (cacheado con `@st.cache_resource` donde el
   costo de entrenar lo justifica, ver `pages/13_Modelos_Predictivos.py`).
5. **Presentación** (`pages/*.py` + `ui/` + `utils/charts.py`): arma filtros,
   invoca las capas anteriores, renderiza gráficos y tablas.

## 5. Patrones de caché

| Decorador | Uso | Ejemplo |
|---|---|---|
| `@st.cache_data(ttl=3600)` | Datos (DataFrames, dicts) que se invalidan en 1 hora | `cargar_balance()`, `obtener_serie_sistema()` |
| `@st.cache_resource(ttl=3600)` | Objetos costosos de recrear (modelos entrenados) | `_modelo_morosidad_entrenado()` en `pages/13` |
| `@st.cache_data(show_spinner=False)` | Contenido estático (CSS, HTML del logo) | `ui/theme.py`, `ui/header.py` |

**Regla:** cachear los **datos**, no las figuras Plotly, salvo que el costo de
reconstrucción sea alto y se documente por qué (evita el problema descrito en
la auditoría de cachear `go.Figure` de forma extendida).

## 6. Decisiones de arquitectura relevantes (con su porqué)

- **`sys.path.append` en cada página**: se investigó eliminarlo (ver
  `CHANGELOG.md`, Fase 2). Streamlit inserta en `sys.path` la ruta del
  *archivo* principal, no su directorio, por lo que las páginas en `pages/`
  no obtienen automáticamente acceso a `utils/`/`config/`/`ui/`. Se mantiene
  el hack hasta que el proyecto se empaquete formalmente (`pyproject.toml`
  instalable).
- **ARIMA en vez de Prophet/LSTM** (`models/forecast.py`): Prophet y los
  frameworks de deep learning tienen una huella de memoria incompatible con
  el límite de ~1GB RAM de Streamlit Cloud que el proyecto ya optimiza
  agresivamente (ver `README.md`).
- **Percentiles (no rangos fijos) para el CAMEL Score** (`analytics/camels_score.py`):
  evita mantener a mano un rango "bueno/malo" por cada uno de los 12
  indicadores usados; el percentil se adapta automáticamente a la
  distribución real del sistema en cada fecha.
- **Stress Testing como simplificación declarada, no un modelo ICAAP/Basilea**
  (`analytics/stress_testing.py`): se documentó explícitamente una propiedad
  no obvia de los ratios de solvencia bajo shocks de depósitos grandes (ver
  `CHANGELOG.md`, Fase 5) para evitar una lectura errónea de los resultados.
- **Asistente IA con modo local + modo Claude** (`services/asistente_ia.py`):
  el modo local nunca inventa cifras (responde solo lo que puede verificar
  contra datos reales); Claude es opcional y requiere clave explícita.

## 7. Extender la plataforma

- **Nuevo módulo de riesgo**: crear `analytics/<nombre>.py` con funciones
  puras, luego `pages/N_<Nombre>.py` que las invoque (seguir el patrón de
  `pages/5-11`). Registrar la página en `ui/sidebar.py` (`_PAGINAS_DISPONIBLES`)
  y en los accesos rápidos de `Inicio.py`.
- **Nuevo modelo de ML**: agregar `models/<nombre>.py` con una función de
  entrenamiento que reciba un DataFrame y devuelva un dict con el modelo y
  sus métricas de validación (seguir el patrón de `prediccion_morosidad.py`:
  siempre incluir una métrica de validación honesta, nunca solo el resultado
  sin evaluar).
- **Nuevo proveedor de IA**: agregar `responder_con_<proveedor>()` en
  `services/asistente_ia.py` con la misma firma que `responder_con_claude()`.
