# Contexto Persistente - Cooperativas Ecuador

Este archivo es la fuente de verdad para recuperar contexto cuando el asistente pierda memoria.
Si estas leyendo esto, **DEBES actualizar este archivo** con cualquier cambio relevante antes de terminar la tarea.

## Instrucciones para el asistente
- Siempre leer `cooperativas/docs/CONTEXTO.md` al inicio de una nueva sesion.
- Actualizar este archivo al finalizar cambios.
- Todo el trabajo debe quedar dentro de `cooperativas/`.
- No modificar el proyecto de bancos (raiz del repo).

## Objetivo del proyecto
Replicar el dashboard de bancos para cooperativas ecuatorianas, con Streamlit, usando los datos en `cooperativas/`.

## Estado actual (PRODUCCION - Desplegado en Streamlit Cloud)

### Estructura de archivos
```
cooperativas/
├── Inicio.py                           # Página principal Streamlit
├── pages/
│   ├── 1_Panorama.py                   # Visión general del sistema (OPTIMIZADO)
│   ├── 2_Balance_General.py            # Análisis temporal de balances
│   ├── 3_Perdidas_Ganancias.py         # PyG con suma móvil 12 meses
│   └── 4_CAMEL.py                      # Indicadores CAMEL (usa pivot cache)
├── utils/
│   ├── __init__.py
│   ├── data_loader.py                  # Funciones de carga (optimizadas + legacy + PyG + indicadores)
│   └── charts.py                       # Componentes de visualización (obtener_color_cooperativa)
├── config/
│   ├── __init__.py
│   └── indicator_mapping.py            # Mapeo de cuentas, segmentos, COLORES y CAMEL
├── scripts/
│   ├── procesar_balance_cooperativas.py # Pipeline ETL balances (ZIPs/XLSM → balance.parquet)
│   ├── procesar_pyg.py                 # Pipeline PyG (desacumulación + suma móvil 12M)
│   ├── procesar_camel.py               # Pipeline ETL indicadores CAMEL desde pivot cache
│   ├── procesar_indicadores.py         # Pipeline ETL balance/PyG desde XLSM (legacy)
│   ├── generar_agregados.py            # Genera datos pre-agregados desde balance.parquet
│   ├── descargar_datos_seps.py         # Scraping y descarga automática del portal SEPS
│   ├── seps_zip.py                      # Inspección de fecha/segmentos del ZIP fuente
│   └── validar_actualizacion.py         # Puerta de calidad antes del commit automático
├── .github/
│   └── workflows/
│       └── actualizar_datos.yml        # GitHub Actions: actualización automática mensual
├── master_data/
│   ├── balance.parquet                 # 82 MB, 24.17M registros (sin ruc/nivel)
│   ├── pyg.parquet                     # 18 MB, PyG incremental con valor_12m
│   ├── indicadores.parquet             # 3.7 MB, indicadores CAMEL oficiales
│   ├── indicadores_raw.parquet         # Staging temporal ignorado por git
│   ├── agg_metricas_sistema.parquet    # 30 KB - KPIs rápidos
│   ├── agg_ranking_cooperativas.parquet # 1.4 MB - Rankings y treemaps
│   ├── agg_series_temporales.parquet   # 2.2 MB - Series temporales
│   ├── agg_catalogo_cooperativas.parquet # 5 KB - Catálogo (259 cooperativas)
│   ├── metadata.json                   # Metadatos de balance (incluye fecha_max)
│   ├── metadata_agregados.json         # Metadatos de agregados
│   └── metadata_indicadores.json       # Metadatos de indicadores CAMEL
├── balances_cooperativas/              # ZIPs fuente balance (2018-2026, no en repo)
├── indicadores/                        # ZIPs fuente indicadores XLSM (2020-2026, no en repo)
├── docs/
│   └── CONTEXTO.md
├── .streamlit/config.toml              # Tema y configuración de servidor
├── .gitignore                          # Excluye ZIPs fuente, archivos intermedios
├── requirements.txt                    # Dependencias para Streamlit Cloud
└── README.md                           # Documentación del proyecto
```

### Datos procesados

#### balance.parquet (82 MB disco → ~500 MB RAM)
- 24,169,638 registros (incluye junio 2026)
- 259 cooperativas únicas
- Columnas: fecha, segmento, cooperativa, codigo, cuenta, valor (todas category excepto fecha/valor)
- Segmentos: SEGMENTO 1, SEGMENTO 2, SEGMENTO 3, SEGMENTO 1 MUTUALISTA
- Período: Enero 2018 - Junio 2026 (102 meses)
- **Sin columnas ruc ni nivel** (eliminadas para reducir memoria, no usadas por UI)
- Nombres de mutualistas unificados retroactivamente a `Mutualista X` en toda la historia

#### pyg.parquet (18 MB disco)
- 2,359,861 registros
- 242 cooperativas únicas (normalizado LTDA)
- Columnas: fecha, segmento, cooperativa, codigo, cuenta, valor_acumulado, valor_mes, valor_12m (todas category excepto fecha/valores)
- Período: Enero 2020 - Junio 2026 (78 meses)
- 77.4% de registros con valor_12m válido
- **Sin columna ruc** (eliminada para reducir memoria, no usada por UI)

#### indicadores.parquet
- 603,312 registros
- 231 cooperativas únicas
- **37 indicadores CAMEL oficiales en 7 categorías**
- Período: Enero 2020 - Junio 2026
- Segmentos: SEGMENTO 1, SEGMENTO 2, SEGMENTO 3, SEGMENTO 1 MUTUALISTA
- **Valores como ratios (0-1)**, multiplicar por 100 para porcentaje
- Schema: cooperativa, segmento, fecha, codigo, indicador, valor, categoria
- Segmento unificado: cada cooperativa usa el segmento de su último dato disponible

#### Lógica de desacumulación PyG
Los datos de PyG son **acumulados** mes a mes dentro de cada año:
1. **valor_acumulado**: Valor original del archivo (acumulado YTD)
2. **valor_mes**: Valor desacumulado del mes = valor_acumulado - valor_mes_anterior (excepto enero)
3. **valor_12m**: Suma móvil de 12 meses para comparabilidad interanual

### Módulos funcionales

#### 1. Inicio.py
Página de bienvenida con descripción del sistema y los 4 módulos disponibles.

#### 2. 1_Panorama.py (OPTIMIZADO)
- KPIs del sistema (Activos, Cartera, Depósitos, Patrimonio, Número de cooperativas)
- Treemap de activos con drill-down (Cooperativa → Componentes)
- Treemap de pasivos y patrimonio
- Rankings por activos y pasivos
- Crecimiento YoY por cooperativa (Cartera y Depósitos)
- Usa datos pre-agregados para carga rápida

#### 3. 2_Balance_General.py
Tres secciones con **selector de cuentas jerárquico uniforme** (4 niveles):
1. **Evolución Comparativa**: Series temporales de múltiples cooperativas
2. **Heatmap de Variación YoY**: Matriz cooperativa × mes
3. **Ranking por Cuenta**: Comparación de valores para cuenta/mes específicos

#### 4. 3_Perdidas_Ganancias.py
- **Valores anualizados** usando suma móvil 12 meses (valor_12m)
- Selector de cuentas jerárquico (Nivel 1: 4-Gastos/5-Ingresos, Nivel 2: subcuentas)
- Sección 1: Evolución Comparativa con modos Absoluto/Indexado/Participación
- Sección 2: Ranking de cooperativas por cuenta y mes
- Excluye totales de segmento (VT_*) de visualizaciones
- Filtro por segmento en sidebar

#### 5. 4_CAMEL.py
Indicadores financieros **oficiales de la Superintendencia**, extraídos directamente del pivot cache
de los archivos XLSM (hoja "5. INDICADORES FINANCIEROS"). Ya no calcula desde códigos contables.

**37 indicadores en 7 categorías:**
- **C - Capital** (5): Cart. Improd. Descubierta/Patrimonio, Cartera Improductiva/Patrimonio, FK, FI, Capitalización Neto
- **A - Calidad de Activos** (3): Activos Improductivos/Activos, Activos Productivos/Activos, AP/PC
- **A - Morosidad por Cartera** (7): Total, Consumo, Inmobiliaria, Microcrédito, Productivo, Vivienda IP, Educativo
- **A - Cobertura por Cartera** (7): Total, Consumo, Inmobiliaria, Microcrédito, Productivo, Vivienda IP, Educativo
- **M - Management y Eficiencia** (3): Gastos Op/Activo, Gastos Op/Margen, Gastos Personal/Activo
- **E - Earnings (Rentabilidad)** (11): ROE, ROA, Intermediación, Margen/Patrimonio, Margen/Activo, 6 Rendimientos de Cartera
- **L - Liquidez** (1): Fondos Disponibles / Depósitos CP

Tres pestañas: Ranking, Evolución Temporal, Heatmap Mensual.
Filtros: Segmento y Fecha en sidebar. Selectores: Top 30, Top 50, Todas.

**Heatmap:**
- Cooperativas ordenadas por activos totales (más grande abajo, más pequeño arriba)
- Rangos de colores alineados con el módulo de bancos para consistencia financiera
- Nombres largos truncados con `truncar_nombre()`: mantiene inicio y final (ej: "ASOCIACION M...IENDA PICHINCHA")

### Normalización de nombres de cooperativas (IMPORTANTE)
Los nombres de cooperativas se normalizan para evitar duplicados:
- **LIMITADA → LTDA** (todas las ocurrencias)
- **LTDA. → LTDA** (elimina punto final)
- Espacios múltiples eliminados
- **Mutualistas**: Se unifican a nombres canónicos `Mutualista Ambato`, `Mutualista Azuay`, `Mutualista Imbabura`, `Mutualista Pichincha` (ver detalle abajo)
- **Correcciones manuales** en `procesar_camel.py`: 8 cooperativas con nombres distintos entre indicadores y balance (dict CORRECCIONES_NOMBRE)

Esta normalización se aplica en:
- `procesar_balance_cooperativas.py`: Función `normalizar_nombre()` + dict `MUTUALISTAS_NOMBRES`
- `procesar_camel.py`: Función `normalizar_nombre()` + CORRECCIONES_NOMBRE + expansión de mutualistas
- `procesar_pyg.py`: Función `normalizar_nombre_cooperativa()`
- `indicator_mapping.py`: COLORES_COOPERATIVAS usa nombres con LTDA

**Resultado**: Balance: 259 cooperativas únicas. Indicadores: 231 cooperativas (3 sin match en balance, cerradas/absorbidas 2020-2021).

#### Nombres canónicos de mutualistas
Las 4 mutualistas tienen nombres históricos distintos según el año de los datos:
- 2018-2025 (CSV/TXT): Nombre largo (ej: `ASOCIACION MUTUALISTA DE AHORRO Y CREDITO PARA LA VIVIENDA AMBATO`)
- 2026+ (XLSM): Nombre corto (ej: `AMBATO`)

El dict `MUTUALISTAS_NOMBRES` en `procesar_balance_cooperativas.py` mapea ambas formas al nombre canónico:
```python
MUTUALISTAS_NOMBRES = {
    'ASOCIACION MUTUALISTA DE AHORRO Y CREDITO PARA LA VIVIENDA AMBATO': 'Mutualista Ambato',
    'ASOCIACION MUTUALISTA DE AHORRO Y CREDITO PARA LA VIVIENDA AZUAY':  'Mutualista Azuay',
    'ASOCIACION MUTUALISTA DE AHORRO Y CREDITO PARA LA VIVIENDA IMBABURA': 'Mutualista Imbabura',
    'ASOCIACION MUTUALISTA DE AHORRO Y CREDITO PARA LA VIVIENDA PICHINCHA': 'Mutualista Pichincha',
    'AMBATO':    'Mutualista Ambato',
    'AZUAY':     'Mutualista Azuay',
    'IMBABURA':  'Mutualista Imbabura',
    'PICHINCHA': 'Mutualista Pichincha',
}
```
**Sin riesgo de colisión**: Existe `AMBATO LTDA` (cooperativa Segmento 1) que es diferente a `AMBATO` (mutualista Segmento 1 Mutualista). La función `normalizar_nombre()` verifica `MUTUALISTAS_NOMBRES` antes de aplicar otras transformaciones, por lo que `AMBATO LTDA` no se ve afectada.

### Unificación de segmentos
Cooperativas que cambiaron de segmento a lo largo del tiempo (51 cooperativas) toman el segmento de su **último dato disponible**. Esto se aplica en `procesar_camel.py` como post-procesamiento después de consolidar todos los años, asegurando que cada cooperativa tenga un único segmento en todo el período.

### Sistema de colores (indicator_mapping.py)
- **Top 10 cooperativas**: Colores brillantes y muy saturados
- **Top 11-30**: Colores medios (saturación media-alta)
- **Top 31-60**: Colores secundarios
- **Top 61-100**: Colores terciarios
- **Top 101-200+**: Colores quinarios (ciclo de paleta suave)
- Función `obtener_color_cooperativa(nombre)` retorna el color asignado
- **IMPORTANTE**: Los nombres en COLORES_COOPERATIVAS usan LTDA (no LIMITADA)

### Exclusión de totales VT_
Los datos de indicadores incluyen filas con nombres tipo `VT_TOTAL SEGMENTO X` que son totales pre-calculados.
Estos **deben excluirse** de:
- Listas de cooperativas en selectores
- Cálculos de ranking
- Cálculos de participación
- Total del sistema

Patrón para excluir: `~df['cooperativa'].str.startswith('VT_')`

### Unidades monetarias (IMPORTANTE)
- Los valores en parquet están en USD completos
- La división para mostrar es `/ 1_000_000` (millones)
- Las etiquetas usan sufijo "M" (Millones USD)
- PyG usa etiqueta "Millones USD (12M)" para indicar suma móvil

### Funciones de data_loader.py

**Funciones optimizadas (para Panorama - usan pre-agregados):**
- `obtener_fechas_disponibles_rapido()` → lista de fechas
- `obtener_segmentos_disponibles_rapido()` → lista de segmentos
- `obtener_metricas_kpi(fecha, segmento)` → dict de KPIs
- `obtener_ranking_rapido(fecha, codigo, top_n, segmento)` → DataFrame
- `obtener_datos_treemap_rapido(fecha, segmento, top_n)` → DataFrame
- `obtener_datos_treemap_pasivos_rapido(fecha, segmento, top_n)` → DataFrame
- `obtener_crecimiento_anual(fecha_actual, fecha_anterior, codigo, segmento, top_n)` → DataFrame
- `obtener_cooperativas_por_segmento(segmento)` → lista de cooperativas ordenadas por activos

**Funciones de carga completa:**
- `cargar_balance()` → (DataFrame, dict_calidad) - Para Balance General
- `cargar_pyg()` → (DataFrame, dict_calidad) - Para Pérdidas y Ganancias
- `cargar_indicadores()` → (DataFrame, dict_calidad) - Para CAMEL (valores como ratios 0-1)

**Funciones legacy (compatibilidad):**
- `obtener_fechas_disponibles(df)` → lista
- `obtener_segmentos_disponibles(df)` → lista
- `obtener_top_cooperativas(df, fecha, codigo, top_n, segmento)` → lista

### Ejecución
```bash
cd cooperativas

# 1. Procesar balances desde ZIPs (genera balance.parquet)
python scripts/procesar_balance_cooperativas.py

# 2. Generar datos pre-agregados (ejecutar cuando cambie balance.parquet)
python scripts/generar_agregados.py

# 3. Procesar PyG (desacumular y calcular suma móvil 12M)
python scripts/procesar_pyg.py

# 4. Procesar indicadores CAMEL desde pivot cache XLSM (genera indicadores.parquet)
python scripts/procesar_camel.py

# 5. Iniciar aplicación
streamlit run Inicio.py --server.port 8502
```

### Despliegue en producción

**Repositorio**: [jp1309/cooperativas](https://github.com/jp1309/cooperativas) (rama `main`)
**Plataforma**: Streamlit Cloud (free tier, ~1 GB RAM)
**Archivo principal**: `Inicio.py`

Archivos de despliegue:
- `requirements.txt`: streamlit, pandas, numpy, pyarrow, plotly, kaleido, requests, beautifulsoup4
- `.streamlit/config.toml`: Tema azul (#2c5282), servidor headless
- `.gitignore`: Excluye ZIPs fuente, archivos intermedios, __pycache__

### Optimización de memoria (CRÍTICO para Streamlit Cloud)

Los parquets se optimizaron para caber en el límite de ~1 GB RAM de Streamlit Cloud:

| Métrica | Sin optimizar | Optimizado | Reducción |
|---------|---------------|------------|-----------|
| Balance RAM | 4,736 MB | 500 MB | -89% |
| PyG RAM | 723 MB | 79 MB | -89% |
| **Total** | **5,459 MB** | **579 MB** | **-89%** |

Optimizaciones aplicadas:
1. **Columnas eliminadas**: `ruc` (1.4 GB, no usada) y `nivel` (no usada) del balance; `ruc` del PyG
2. **Category dtypes**: `codigo`, `cuenta`, `segmento`, `cooperativa` almacenados como category (no object)
3. **Carga selectiva**: `pd.read_parquet(columns=[...])` en `data_loader.py` carga solo columnas necesarias
4. **Dtypes en parquet**: Los scripts de procesamiento ya generan category dtypes, la conversión en carga es un safety net

**IMPORTANTE**: Si se regeneran los parquets, asegurar que los scripts de procesamiento mantengan la exclusión de `ruc`/`nivel` y el uso de category dtypes.

## Módulos de riesgo (ampliación — ver `AUDITORIA_MOTOR_INDICADORES.md`, `CATALOGO_INDICADORES.md`, `docs/RIESGO_METODOLOGIA.md`)

Además de los 4 módulos originales (Panorama, Balance, PyG, CAMEL), el proyecto
tiene 11 páginas adicionales y un motor de indicadores central. **Todo esto
está en el working tree pero sin commitear** (ver `git status` — 47 archivos
modificados/nuevos a la fecha de esta nota); antes de commitear, releer este
archivo y `docs/RIESGO_METODOLOGIA.md` completos.

```
pages/
├── 5_Riesgo_Liquidez.py
├── 6_Riesgo_Credito.py
├── 7_Riesgo_Solvencia.py          # FK/FI/CAP_NETO/VULN_PAT — NO es Solvencia oficial (ver nota abajo)
├── 8_Riesgo_Concentracion.py      # HHI, CR-N, Gini, Lorenz
├── 9_Riesgo_Sistemico.py          # Índice de Importancia Sistémica (tamaño+sustituibilidad, sin interconectividad)
├── 10_CAMEL_Score.py
├── 11_Alertas_Tempranas.py        # Semáforo por regla, SIN persistencia/velocidad/breadth todavía
├── 12_Stress_Testing.py
├── 13_Modelos_Predictivos.py
├── 14_Machine_Learning.py
└── 15_Asistente_IA.py

analytics/
├── financial_engine.py    # Fachada única — importar SOLO de aquí desde pages/
├── liquidez.py, credito.py, solvencia.py, concentracion.py, sistemico.py,
│   camels_score.py, alertas.py, stress_testing.py   (dominios originales)
├── rentabilidad.py, crecimiento.py                   # Fase 2.3: tasas implícitas, spread, crecimiento
├── indices_ejecutivos.py                             # Fase 2.4: 6 índices compuestos (Score, Vulnerabilidad,
│                                                        Fortaleza, Resiliencia, Estabilidad, Riesgo Integral)
└── catalogo_indicadores.py                            # Metadata para generar CATALOGO_INDICADORES.md

models/       anomalias.py, clustering.py, forecast.py, prediccion_morosidad.py
services/     asistente_ia.py
ui/           filtros.py (Filtro Global de Segmento, compartido entre TODAS las páginas), header.py, sidebar.py, theme.py
config/       umbrales_alerta.py (umbrales de alerta, declarados "referenciales", NO regulatorios), constants.py
```

**IMPORTANTE — no confundir CAP_NETO con Solvencia oficial**: `CAP_NETO`
(FK/FI, código SEPS `I50_Indi_capi_neto`) es un indicador de vulnerabilidad
patrimonial, no el ratio de Solvencia regulatorio (Patrimonio Técnico
Constituido / Activos Ponderados por Riesgo, mínimo 9% JPRF). Ese ratio
requiere el **Formulario de Solvencia (FS01)**, fuente que el ETL actual no
descarga ni procesa — solo procesa el boletín de Estados Financieros. Ver
`docs/RIESGO_METODOLOGIA.md` §3.2 para el detalle completo. `pages/7_Riesgo_Solvencia.py`
ya tiene una nota aclaratoria visible en la UI.

**Clasificación de indicadores** (usar siempre al agregar uno nuevo):
`OFICIAL_SEPS` (de `indicadores.parquet`) / `DERIVADO` (calculado desde cuentas
crudas oficiales) / `ANALÍTICO` (construcción propia, declarar como tal) /
`INTERNATIONAL_COMPLEMENT` (metodología BIS/IMF sin equivalente ecuatoriano).

**Lo que el motor de riesgo todavía NO tiene** (propuesto, no construido —
ver `docs/RIESGO_METODOLOGIA.md` §5-6 para el detalle y la razón de no haberlo
construido sin validación previa):
- Persistencia de alertas (cuántos meses consecutivos lleva activa una señal).
- Breadth ponderado (% de activos/cartera/depósitos del sistema afectados por
  un deterioro específico) — existe concentración de mercado (HHI/CR-N/Gini),
  pero no breadth de una alerta.
- Reglas de interacción entre indicadores documentadas (p. ej. morosidad↑ +
  cobertura↓ + ROA↓ como señal compuesta).
- Clasificación de contracción sistémica (Normal → Desaceleración → Estrés).
- IPSF (índice de presión financiera sistémica) — deliberadamente no construido
  hasta validar los insumos anteriores.
- Backtesting contra eventos reales (liquidaciones/fusiones) — no existe un
  registro estructurado de eventos de referencia.
- Tabla de identidad histórica de entidades con RUC
  (`master_data/entidades_cooperativas.parquet`) — el RUC se excluyó de
  `balance.parquet`/`pyg.parquet` por peso (ver optimización de memoria abajo);
  reintroducirlo solo en una tabla ligera aparte, no en los Parquet grandes.

## Próximo paso sugerido
- Agregar exportación de datos a Excel
- Agregar comparativo entre segmentos
- Agregar promedios del sistema como referencia en gráficos CAMEL
- Fases de riesgo propuestas en `docs/RIESGO_METODOLOGIA.md` §6 (persistencia →
  breadth → registro de eventos → recién entonces IPSF/backtesting)

## Notas técnicas importantes

### Formatos de archivos fuente por año
| Año | Formato | Delimitador | Notas |
|-----|---------|-------------|-------|
| 2018-2021 | CSV/TXT | `;` | Encoding `utf-8-sig` |
| 2022-2025 | CSV/TXT | `\t` (tab) | Coma decimal en valores, columnas diferentes |
| 2026+ | XLSM | N/A | ZIP con un XLSM por segmento, formato ancho (cooperativas como columnas) |

**Lectura de XLSM (2026+)**: Función `leer_xlsm_balance()` en `procesar_balance_cooperativas.py`:
- Un archivo XLSM por segmento (Segmento 1, Segmento 2, Segmento 3, Mutualistas)
- Ignora CONAFIPS y FINANCOOP (no son cooperativas de ahorro y crédito)
- Busca la hoja con "ESTADO" y "FINANCIERO" en el nombre
- Localiza fila header con "COD CONTABLE"
- Extrae fecha de celda datetime antes del header (fallback: parsea nombre de archivo `_ene_2026`)
- Aplica `melt()` para convertir formato ancho (cooperativas=columnas) a largo (una fila por cooperativa+cuenta)
- Requiere `openpyxl` instalado

### Extracción de indicadores CAMEL desde pivot cache
- Los archivos XLSM son ZIPs con XML interno
- La hoja "5. INDICADORES FINANCIEROS" usa un pivot table respaldado por un pivotCache
- El número del pivot cache **varía entre años**: cache3 en 2021/2023, cache4 en 2020/2022/2024/2025
- `procesar_camel.py` detecta el cache correcto buscando campos marcadores (`I28_ROE`, `I29_ROA`, `I1_suficiencia_patrimonial`)
- Los valores se almacenan como **ratios (0-1)**, no porcentajes. Ej: ROA=0.009 → 0.9%
- La UI multiplica por 100 para mostrar porcentajes
- Las funciones `extraer_lookup_tables()` y `parsear_cache_records()` parsean el XML de pivot cache
- Los campos de indicadores usan prefijo `I{número}_` (ej: `I28_ROE`, `I5_Moros_carte`)
- Las filas `VT_TOTAL` del cache son totales del sistema y se excluyen

### Constantes CAMEL en indicator_mapping.py
- `GRUPOS_INDICADORES`: 7 categorías CAMEL con 37 códigos para selectores de UI
- `ETIQUETAS_INDICADORES`: Nombres amigables por código
- `ESCALAS_COLORES_HEATMAP`: RdYlGn (mayor=mejor), RdYlGn_r (menor=mejor), Blues (neutral)
- `RANGOS_HEATMAP`: Rangos de valores en porcentaje, alineados con módulo de bancos

### Truncamiento de nombres largos
Función `truncar_nombre(n, max_len=30)` en `4_CAMEL.py` mantiene inicio y final del nombre para diferenciar cooperativas con prefijos similares (especialmente mutualistas). Se aplica en ranking y heatmap.

## Requisitos críticos para la automatización

Estos requisitos deben cumplirse para que GitHub Actions funcione. Si alguno falla, la actualización automática se detiene silenciosamente.

### 1. Branch default debe ser `main`
GitHub Actions **solo ejecuta cron schedules desde el branch default**. Si el default se cambia a otro branch, el workflow nunca se ejecutará automáticamente.

**Verificar:**
```bash
gh api repos/jp1309/cooperativas --jq .default_branch
# Debe devolver: main
```

**Corregir si es necesario:**
```bash
gh api repos/jp1309/cooperativas --method PATCH -f default_branch=main
```

### 2. Permisos del workflow
El workflow necesita `permissions: contents: write` en `actualizar_datos.yml`. Sin esto, la descarga y procesamiento funcionan pero `git push` falla con `Permission denied`.

### 3. URL del portal SEPS
La URL del portal es: `https://estadisticas.seps.gob.ec/index.php/estadisticas-sfps/`
El script busca enlaces con `download_id` en la sección "Estados Financieros Mensuales".

### 4. Streamlit Cloud debe apuntar a `main`
Verificar en https://share.streamlit.io que la app apunte al branch `main` del repo `jp1309/cooperativas`.

## Troubleshooting de automatización

### El workflow no se ejecuta automáticamente
1. Verificar que el branch default sea `main` (ver arriba)
2. Verificar que `.github/workflows/actualizar_datos.yml` exista en `main`
3. Revisar en https://github.com/jp1309/cooperativas/actions si el workflow aparece

### Error: "Permission denied" en git push
- Verificar que el workflow tenga `permissions: contents: write`

### Los datos no se actualizan al mes esperado
- La SEPS publica datos con retraso variable. El workflow reintenta los días 15, 18, 20, 22
- Verificar si el ZIP descargado contiene el mes nuevo revisando logs en GitHub Actions
- El script descarga el ZIP del año completo; si la SEPS no incluyó el mes nuevo, los datos no cambian

### Ejecutar manualmente desde CLI
```bash
# Disparar workflow
gh workflow run "Actualizar datos SEPS" --repo jp1309/cooperativas

# Ver estado
gh run list --repo jp1309/cooperativas --limit=3

# Ver logs del último run
gh run view $(gh run list --repo jp1309/cooperativas --limit=1 --json databaseId -q '.[0].databaseId') --log
```

### Incidente marzo 2026 en proyecto bancos (evitar aquí)
El workflow de bancos no se ejecutó durante 1 mes porque el branch default era `master` en lugar de `main`. Cooperativas no tuvo este problema porque se configuró correctamente desde el inicio, pero hay que verificar periódicamente que el default branch no cambie.

### Incidente mayo 2026 en bancos y variante detectada en cooperativas
**Síntoma:** La app mostraba marzo cuando debería mostrar abril.
**Causa raíz en bancos:** `actualizar_datos.py` guardaba en `update_status.json` el *período objetivo* sin verificar si el parquet realmente cambió. Cuando el portal no publicó el mes nuevo, procesaba sin cambios y marcaba el mes como "descargado". Los reintentos posteriores se saltaban todos.
**Variante hallada en cooperativas:** `fecha_max` sí provenía del Parquet real, pero cualquier ZIP descargado devolvía código 0 aunque todavía contuviera el mes anterior. Esto ejecutaba todo el ETL y generaba un commit de falso avance.
**Invariante a mantener:** comparar siempre `fecha_max` real contra la fecha interna validada del ZIP; si la fuente no avanzó, devolver código 2, omitir ETL/commit y conservar el ZIP anterior.

## Errores previos a evitar
- Trabajar fuera de `cooperativas/`.
- Modificar archivos del proyecto de bancos.
- No manejar el BOM (Byte Order Mark) en archivos UTF-8
- No convertir comas decimales a puntos en archivos 2022+
- **Dividir por 1000 en lugar de 1_000_000** - causa valores 1000x más grandes
- **No normalizar nombres** - causa cooperativas duplicadas (LIMITADA vs LTDA)
- **No excluir VT_** - incluye totales pre-calculados en rankings
- **Truncar nombres a longitud fija** - hace indistinguibles cooperativas con prefijo largo similar (mutualistas)
- **No optimizar dtypes para Streamlit Cloud** - balance.parquet con object dtypes usa 4.7 GB RAM, excede el límite de 1 GB. Siempre usar category dtypes y excluir columnas no usadas (ruc, nivel)

### Errores cometidos en sesión 2026-02-22 (aprendizajes)

#### 1. Normalización de nombres incompleta al renombrar mutualistas
**Error**: Al renombrar mutualistas a `Mutualista X` en `procesar_balance_cooperativas.py`, no se actualizaron simultáneamente los otros 3 lugares que también usaban los nombres antiguos:
- `config/indicator_mapping.py` → claves en `COLORES_COOPERATIVAS`
- `scripts/procesar_camel.py` → expansión a nombre largo
- `scripts/procesar_pyg.py` → sin ninguna normalización de mutualistas

**Consecuencia**: Los colores de las 4 mutualistas se volvieron negros (el dict no encontraba match), y los parquets de indicadores y PyG tenían nombres distintos al de balance, rompiendo la consistencia entre módulos.

**Regla**: Cuando se cambia el nombre canónico de una entidad, buscar con grep en TODO el proyecto antes de commitear: `grep -rn "MUTUALISTA\|nombre_anterior" .`

#### 2. Llamada a `generar_agregados.py` sin controlar el tamaño de salida
**Error**: Al llamar `generar_agregados.py` localmente (sin supervisión) durante la corrección de colores, el script generó `agg_ranking_cooperativas.parquet` de 212 MB (era 1.4 MB). El `groupby` con `observed=False` en category dtypes genera el producto cartesiano de todas las categorías (157M filas en lugar de 157K).

**Consecuencia**: El push fue rechazado por GitHub (límite 100 MB). Se tuvo que hacer `--amend` con los archivos restaurados del commit anterior.

**Regla**:
- Nunca agregar archivos `agg_*.parquet` al staging sin verificar su tamaño (`ls -lh master_data/agg_*.parquet`)
- Si un parquet creció más del doble inesperadamente, NO hacer push — investigar primero
- Al regenerar pre-agregados localmente, asegurarse de que `generar_agregados.py` use `observed=True` en todos los groupby con category dtypes

#### 3. `use_container_width` deprecado en Streamlit 1.54
**Error**: El proyecto usaba `use_container_width=True` (19 ocurrencias en 5 archivos), parámetro eliminado en Streamlit 1.54. Streamlit Cloud instaló 1.54 y generó warnings masivos en los logs.

**Solución**: Reemplazar `use_container_width=True` → `width='stretch'` y `use_container_width=False` → `width='content'`.

**Regla**: Al crear nuevos gráficos con `st.plotly_chart()` o `st.page_link()`, usar `width='stretch'` directamente.

#### 4. `observed=False` deprecado en pandas con category dtypes
**Error**: `groupby()` y `pivot_table()` en `2_Balance_General.py` sin `observed=True` generaban FutureWarning en producción porque las columnas son category dtype.

**Regla**: Siempre agregar `observed=True` en cualquier `groupby()` o `pivot_table()` que opere sobre columnas con category dtype. En este proyecto: `cooperativa`, `segmento`, `codigo`, `cuenta`.

## Historial de cambios

### 2026-09-14 (noche, cierre técnico) - Pipeline reproducible: memoria, regeneración real, integridad

Segunda fase de hardening la misma noche. Detalle completo en
`docs/RIESGO_METODOLOGIA.md` §20 y `docs/CHANGELOG_RIESGO.md`; resumen:

- **Causa raíz real del "cuello de botella de Segmento 3" diagnosticada**:
  no era el archivo (procesa en 19s aislado) sino acumulación de memoria del
  PROCESO al procesar los 4 archivos del ZIP secuencialmente (glibc no
  devuelve memoria liberada al SO) — RSS subía a 4.3+ GB, OOM en el último
  archivo. Fix de 8 líneas (`gc.collect()` + `malloc_trim(0)` tras cada
  archivo) en `scripts/procesar_indicadores.py`. Una reescritura alternativa
  con `ET.iterparse()` (streaming) se probó equivalente pero no más rápida
  ni con memoria menor demostrada — descartada por riesgo sin beneficio.
- **Regeneración real ejecutada** (no solo el código verificado):
  `indicadores_raw.parquet`, `master_data/indicadores.parquet` y
  `master_data/pyg.parquet` — equivalencia numérica exacta confirmada
  (0 diferencias) contra los archivos anteriores. `pyg.parquet` ahora tiene
  `segmento_historico` genuinamente point-in-time para 2026 (verificado con
  `CAÑAR LTDA`: reportó Segmento 3 ene-may 2026, migró a Segmento 2 desde
  jun-2026 — capturado correctamente).
- **Escritura atómica nueva**: `scripts/io_atomico.py` — ningún
  `master_data/*.parquet` puede quedar parcialmente escrito ante un fallo a
  mitad de proceso; aplicado a los 10 sitios de escritura del pipeline.
- **YoY centralizado**: `pages/2_Balance_General.py` ya no reimplementa el
  cálculo de crecimiento mensual — usa `analytics/crecimiento.py` (nueva
  función), equivalencia verificada.
- **3 `pivot_table()` corregidos** (de ~11 candidatos; los otros 8 no
  disparan el warning en uso real, no se tocaron).
- Workflow: verificado (sin cambios necesarios) que ya distingue los 5
  estados pedidos (NO_NEW_DATA/SUCCESS/WARNING/OPTIONAL_COMPONENT_FAILURE/
  CRITICAL_FAILURE).
- Tests: 116 → 122 (330 subpruebas), 0 regresiones.
- Ningún commit realizado.

### 2026-09-14 (noche) - Fase de hardening: validación, calibración y robustez

Continuación directa de la entrada "(tarde)" de este mismo día. Detalle
completo en `docs/CHANGELOG_RIESGO.md`; resumen aquí:

- **Bug real corregido**: `analytics/riesgo_sistemico_estado.py` permitía que
  una caída aislada en una sola dimensión de crecimiento (sin breadth ni
  persistencia) alcanzara `CONTRACCIÓN SECTORIAL` — encontrado con una
  batería de 8 escenarios sintéticos A-H, corregido exigiendo evidencia
  multidimensional. Los 8 escenarios producen ahora resultados coherentes.
- **`scripts/procesar_pyg.py` corregido** (mismo defecto de segmentación que
  balance/indicadores) a nivel de código; `master_data/pyg.parquet` no se
  regeneró por un hallazgo de performance no relacionado (ver abajo).
- **Calibraciones investigadas con datos reales, no cambiadas**: persistencia
  (~54%, estable y con tendencia secular real, no ruido) y breadth (25%,
  nunca cruzado por la población "alerta roja" en 6.5 años). Ambos umbrales
  se mantienen con la evidencia ahora documentada.
- **Reinterpretación corregida**: la correlación A/B del IPSF (0.968) se
  había leído como "evidencia de que el índice funciona" — es, en gran
  parte, redundancia entre 2 de sus 3 componentes (misma fuente por
  construcción). Corregido en el docstring y en la UI.
- **Etiquetado explícito como dato**: eventos proxy y resultados de
  backtesting ahora llevan columnas/campos con la etiqueta adjunta
  (`TIPO_EVENTO_PROXY`, `"BACKTESTING PROXY"`), no solo en el docstring.
- **Control determinístico nuevo**: `services/asistente_ia.py` ahora filtra
  la palabra "crisis" en las respuestas del modo Claude con código Python
  (no solo con el prompt) y adjunta una advertencia visible.
- **Arquitectura consolidada**: `analytics/financial_engine.py` ahora
  re-exporta los 8 módulos que la entrada anterior había creado sin
  conectar a la fachada; 3 páginas (`1`, `9`, `11`) actualizaron sus imports;
  el test de guardia que debía haber detectado esto se amplió para cubrirlos.
- **Workflow**: pasos opcionales pasaron de `|| echo warning` (silencioso) a
  `continue-on-error: true` + un resumen final categorizado en
  `$GITHUB_STEP_SUMMARY`.
- **Hallazgo nuevo, no resuelto**: el parseo del Boletín Financiero
  Segmento 3 en `procesar_indicadores.py` no completó en >10 minutos en este
  entorno (escala no lineal frente a Segmento 1/2) — código pre-existente,
  no tocado por los cambios de esta sesión, documentado como riesgo residual.
- **Tests**: 110 → 116 (330 subpruebas), 0 regresiones. Un test pre-existente
  (`test_actualizacion.py`) se rompió con el primer intento del fix de PyG y
  se corrigió haciendo la función más defensiva, sin tocar el test.
- Ningún cambio de esta fase fue commiteado.

### 2026-09-14 (tarde) - Cierre e implementación integral tras la auditoría de la mañana

Continuación directa de la entrada anterior (auditoría). Ver `docs/CHANGELOG_RIESGO.md`
para el detalle completo componente por componente; resumen aquí:

- **Solvencia oficial (FS01) integrada**: se encontró que la SEPS publica un
  boletín público separado ("Patrimonio Técnico") con los datos de la ficha
  FS01. Pipeline completo nuevo: `descargar_patrimonio_tecnico()` en
  `scripts/descargar_datos_seps.py` → `scripts/procesar_solvencia.py` (ETL) →
  `analytics/solvencia.py::evaluar_solvencia_oficial()` → pestaña nueva en
  `pages/7_Riesgo_Solvencia.py`. Cobertura confirmada: solo Segmento
  1/Mutualistas/FINANCOOP (Segmento 2/3 sin fuente pública). 3.548 registros,
  2020-01 a 2026-07, 0 discrepancias en la verificación PTC/APPR recalculado.
  `CAP_NETO` (FK/FI) se mantiene estrictamente separado del 9% regulatorio en
  todo el sistema (nunca se le aplica ese umbral).
- **Defecto corregido — `segmento` retroactivo**: `balance.parquet` e
  `indicadores.parquet` unificaban el segmento de cada cooperativa al último
  conocido, aplicado a toda su historia. Se añadieron (aditivo, sin tocar
  `segmento`) `segmento_historico`, `segmento_actual`,
  `segmento_historico_estimado`. Regenerados ambos parquets (balance: 24.404.894
  filas, sin cambio de conteo; indicadores: 611.881 filas). **Limitación
  documentada**: por diseño del ETL incremental (no reprocesa meses ya
  presentes), el 100% del histórico regenerado quedó `estimado=True`,
  incluyendo el corte más reciente — el mecanismo es correcto hacia adelante
  (próximos meses procesados como "nuevos" sí obtendrán el valor real).
  `procesar_pyg.py` tiene el mismo defecto y **no se corrigió** (gap
  documentado). Ver `docs/RIESGO_METODOLOGIA.md` §18.
- **9 módulos analíticos nuevos** en `analytics/`: `data_quality.py`,
  `persistencia.py`, `breadth.py`, `interaccion.py`, `eventos.py`,
  `backtesting.py`, `ipsf.py`, `riesgo_sistemico_estado.py`, más
  `scripts/generar_entidades.py` → `master_data/entidades_cooperativas.parquet`
  (tabla ligera de identidad, 259 entidades, 51 con RUC). Todos con datos
  reales verificados — detalle y cifras en `docs/RIESGO_METODOLOGIA.md` §8-§18.
- **Integrado en páginas existentes, sin crear páginas nuevas**: pestaña
  "⏱️ Persistencia, Amplitud e Interacción" en `pages/11_Alertas_Tempranas.py`;
  pestañas "🧭 Estado Sistémico (Experimental)" y "🌡️ IPSF (Experimental)" en
  `pages/9_Riesgo_Sistemico.py`; sección "Calidad de datos e identidad de
  entidades" en `pages/1_Panorama.py`.
- **Auditoría de ML/Modelos Predictivos y Asistente IA**: `models/prediccion_morosidad.py`
  y `models/forecast.py` etiquetados en la UI como "ANALÍTICO NO VALIDADO /
  EXPERIMENTAL" (split temporal correcto, pero una sola ventana de holdout, sin
  backtesting contra eventos). `models/anomalias.py`/`clustering.py` (no
  supervisados) sin cambios de fondo. `services/asistente_ia.py`: prompt de
  sistema reforzado para distinguir hecho/inferencia y responder
  "Información insuficiente para determinarlo." cuando corresponde.
- **Workflow** (`.github/workflows/actualizar_datos.yml`): pasos nuevos
  `procesar_solvencia.py` y `generar_entidades.py`, best-effort (`|| echo
  ::warning`, no bloquean el pipeline si fallan); `git add` de
  `solvencia.parquet`/`entidades_cooperativas.parquet` protegido con `|| true`
  (pueden no existir en una corrida donde esas fuentes no tuvieron datos
  nuevos).
- **Tests**: 29 pruebas nuevas — `tests/test_riesgo_ampliado.py` (21,
  sintéticas: persistencia, breadth, interacción, data quality, estado
  sistémico, eventos, backtesting, IPSF) + 8 nuevas en
  `tests/test_consistencia_datos.py` (datos reales: segmento histórico,
  cobertura FS01, identidad de entidades). Suite completa: **110 pruebas / 330
  subpruebas, sin regresiones** (antes: 81 pruebas).
- **No se hizo commit** de ningún cambio (instrucción explícita del pedido) —
  todo queda preparado en el working tree para revisión.

### 2026-09-14 - Auditoría de indicadores contra Fichas Metodológicas SEPS v3.0 (63 fichas oficiales)

- Insumo: `Fichas-Metodologicas-de-Indicadores-Financieros_V3.0.pdf` (31-jul-2026),
  adjuntado por el usuario. Auditoría de las 63 fichas oficiales contra los 41
  códigos de `indicadores.parquet`, siguiendo la misma metodología rigurosa que
  `AUDITORIA_MOTOR_INDICADORES.md` (28-jul-2026) usó contra el script R.
- **Hallazgo material**: los indicadores 58-63 de la ficha (Patrimonio Técnico
  Primario/Secundario/Constituido, Activos Ponderados por Riesgo, **Solvencia**,
  Porcentaje Técnico Requerido) requieren el **Formulario de Solvencia (FS01)**
  como fuente adicional — el ETL actual (`procesar_camel.py`) solo procesa el
  boletín de Estados Financieros. Verificado programáticamente: ninguno de los
  41 códigos de `indicadores.parquet` corresponde a estos 6 indicadores. La
  plataforma **no puede calcular el ratio de Solvencia oficial (mínimo
  regulatorio 9%)** con las fuentes que ingesta hoy.
- Consecuencia detectada: `config/umbrales_alerta.py` usaba `alerta_amarilla=0.09`
  para `CAP_NETO` (FK/FI, un indicador de vulnerabilidad patrimonial distinto),
  coincidiendo numéricamente con el 9% de Solvencia oficial sin aclarar que son
  indicadores diferentes. **Corregido**: comentario explícito en
  `config/umbrales_alerta.py` + nota visible en `pages/7_Riesgo_Solvencia.py`
  (`st.caption`) aclarando que la página usa vulnerabilidad patrimonial (FK,
  FI, CAP_NETO, VULN_PAT), no el ratio de Solvencia regulatorio. El valor del
  umbral (9%/6%) no se modificó — solo se documentó, siguiendo la regla de "no
  corregir silenciosamente" cuando hay ambigüedad metodológica.
- Resto de las 63 fichas (1-57): sin discrepancias de fórmula, dirección
  (mayor/menor es mejor) ni unidad frente al código actual. La granularidad
  histórica prioritario/ordinario de morosidad y cobertura (fichas 6,7,11,12,
  19,20,24,25) no es reconstruible después de may-2021 porque la propia SEPS
  dejó de publicarla a ese nivel — confirma, con fuente independiente, el mismo
  hallazgo que ya documentó `AUDITORIA_MOTOR_INDICADORES.md` (Categoría 2).
- **Creado** `docs/RIESGO_METODOLOGIA.md`: documento de metodología de riesgo
  que consolida fuentes, clasificación (`OFICIAL_SEPS`/`DERIVADO`/`ANALÍTICO`/
  `INTERNATIONAL_COMPLEMENT`), separación indicador/umbral, y un inventario
  honesto de qué componentes del "sistema de vigilancia" (persistencia de
  alertas, breadth, interacción entre riesgos, clasificación de contracción
  sistémica, IPSF, backtesting, identidad histórica con RUC) están
  implementados vs. propuestos-no-construidos, con la razón de no haberlos
  construido sin validar antes sus insumos.
- **Decisión de alcance**: no se construyeron IPSF, backtesting, breadth
  ponderado, persistencia de alertas ni clasificación de contracción sistémica
  en esta sesión. Son componentes grandes cuya construcción apresurada sin
  validar sus insumos (persistencia, breadth, registro de eventos de
  referencia) violaría el principio explícito del pedido de "calidad sobre
  cantidad" en señales de riesgo. Se documentaron como fases propuestas en
  `docs/RIESGO_METODOLOGIA.md` §6, siguiendo el mismo patrón de
  auditar-proponer-confirmar que ya usó `AUDITORIA_MOTOR_INDICADORES.md`.
- Verificación: suite completa de pruebas re-ejecutada tras los dos cambios
  (`config/umbrales_alerta.py`, `pages/7_Riesgo_Solvencia.py`) — 81 pruebas /
  330 subpruebas, sin regresiones.
- **Nota**: al iniciar esta sesión, `docs/CONTEXTO.md` no reflejaba el trabajo
  ya presente en el working tree (páginas 5-15, `analytics/` ampliado,
  `models/`, `services/`, `ui/`, `CATALOGO_INDICADORES.md`,
  `AUDITORIA_MOTOR_INDICADORES.md`, `SEGMENTACION_TRANSVERSAL.md`,
  `VALIDACION_FINAL_DATOS.md`) — 47 archivos nuevos/modificados sin commitear.
  Se actualizó la sección "Módulos de riesgo" de este archivo para no perder
  ese contexto en la próxima sesión. Ningún commit se creó en esta sesión (no
  fue solicitado explícitamente).

### 2026-07-17 - Pipeline mensual endurecido y datos junio 2026

- **Causa del retraso**: el cron del 15 de julio descargó la URL anual estable,
  pero la SEPS todavía servía el paquete de mayo. El workflow interpretó la
  descarga como actualización y publicó nuevamente `fecha_max=2026-05-31`.
- `descargar_datos_seps.py` ahora descarga a un temporal, exige los cuatro
  segmentos, obtiene la fecha desde los nombres XLSM y solo reemplaza la fuente
  local si `fecha_fuente > fecha_max_publicada`.
- El código `2` significa fuente sin avance y GitHub Actions lo convierte en
  `datos_nuevos=false`; los ETL y el commit quedan omitidos sin marcar fallo.
- `validar_actualizacion.py` bloquea el push si Balance, agregados, PyG, CAMEL o
  metadata no terminan exactamente en la fecha del ZIP, o si se perdió historia.
- PyG y CAMEL son incrementales: reemplazan los meses contenidos en el ZIP más
  reciente y conservan los años anteriores desde sus Parquet publicados.
- `procesar_indicadores.py` ya no sobrescribe `pyg.parquet`; solo crea el staging
  ignorado `indicadores_raw.parquet`. En modo incremental procesa únicamente el
  año más reciente; un rebuild sin Parquet histórico procesa todos los ZIP.
- `generar_agregados.py` usa `observed=True`; evita un producto cartesiano que
  intentó crear 165 millones de filas y reservar 265 GiB.
- Balance convierte categorías temporalmente a `object`, evitando una reserva
  de 6.69 GiB causada por `astype(str)` durante la concatenación incremental.
- Dependencias ETL fijadas y `openpyxl==3.1.5` declarado en `requirements.txt`.
- Estado verificado: Balance 24,169,638 filas (2018-01 a 2026-06), PyG
  2,359,861 (2020-01 a 2026-06) y CAMEL 603,312 (2020-01 a 2026-06).

### 2026-02-22 - Automatización mensual y datos enero 2026

#### Automatización con GitHub Actions
- **Creado** `.github/workflows/actualizar_datos.yml`: workflow que corre automáticamente los días 15, 18, 20 y 22 de cada mes a las 6 AM UTC (reintentos en caso de que la SEPS no publique el día 15)
- **Creado** `scripts/descargar_datos_seps.py`: scraping del portal SEPS para encontrar el `download_id` del ZIP del año corriente, descarga con streaming (no hace falta conocer el ID de antemano)
- **Actualizado** `requirements.txt`: agregados `requests>=2.31.0` y `beautifulsoup4>=4.12.0`
- El workflow usa `GITHUB_TOKEN` con `permissions: contents: write` para hacer commit+push automático de los parquets actualizados
- Streamlit Cloud detecta el push y se redespliega automáticamente

#### Soporte para formato XLSM 2026
- La SEPS cambió el formato del ZIP de balance: 2026 contiene 4 archivos XLSM (uno por segmento) en formato ancho (cooperativas como columnas), en lugar del CSV/TXT de años anteriores
- **Agregada** función `leer_xlsm_balance()` en `procesar_balance_cooperativas.py`
- `leer_archivo_desde_zip()` ahora auto-detecta si el ZIP contiene XLSM y delega a la función correcta
- `procesar_dataframe()` maneja ambos formatos (CSV con columna `FECHA_DE_CORTE`, y XLSM ya normalizado)
- Requiere `openpyxl` (agregado al pip install del workflow)

#### Modo incremental en ETL de balance
- `generar_balance_parquet()` ahora carga el `balance.parquet` existente como base histórica
- Solo procesa ZIPs del año de `fecha_max` en adelante
- Filtra registros nuevos (fecha > fecha_max existente) y concatena
- Esto permite que GitHub Actions procese solo el ZIP nuevo sin necesitar los 8 años de histórico

#### Datos enero 2026
- **234,116 nuevos registros** procesados desde 4 archivos XLSM
- **Total: 23,003,634 registros** (era 22,769,518)
- **Período: Enero 2018 - Enero 2026** (97 meses, era 96)
- `balance.parquet`: 82 MB (era 78 MB)

#### Normalización de nombres de mutualistas
- Detectado cambio en nomenclatura: en 2026 las mutualistas usan nombre corto (`AMBATO`, `AZUAY`, etc.) en lugar del nombre largo de años anteriores
- Verificado que no hay colisión con cooperativas: `AMBATO LTDA` (cooperativa Seg. 1) ≠ `AMBATO` (mutualista Seg. 1 Mutualista)
- **Agregado** dict `MUTUALISTAS_NOMBRES` en `procesar_balance_cooperativas.py` que mapea ambas formas al nombre canónico `Mutualista X`
- Nombres aplicados retroactivamente a los 490,208 registros de mutualistas en toda la historia del parquet

### 2026-02-08 - Despliegue en producción
- **Desplegado en Streamlit Cloud** desde GitHub repo jp1309/cooperativas
- **Optimización de memoria**: RAM reducida de 5.5 GB a 579 MB (-89%)
  - Eliminadas columnas `ruc` y `nivel` de balance.parquet (no usadas por UI)
  - Eliminada columna `ruc` de pyg.parquet (no usada por UI)
  - Columnas string convertidas a category dtype en scripts de procesamiento y data_loader
  - Carga selectiva con `pd.read_parquet(columns=[...])`
- **Archivos de despliegue creados**: requirements.txt, .streamlit/config.toml, .gitignore, README.md
- **CAMEL Evolución Temporal**: Agregados selectores Año inicio/Año fin (igual que Heatmap)
- **Rangos de heatmap ajustados**: ROE [-5, 15], ROA [-1, 3] (proporción ~5x leverage)

### 2026-02-06 - Refinamientos finales
- **Indicadores reducidos a 37**: Eliminados CART_REF, CART_REEST, CART_VENCER de A-Calidad de Activos
- **Rangos de heatmap alineados con bancos**: MOR [0,10], COB [0,300], ACT_IMPR [0,40], AP_PC [80,120], GO_ACT [0,10], GP_ACT [0,5]
- **Truncamiento inteligente de nombres**: `truncar_nombre()` mantiene inicio+final para diferenciar mutualistas y cooperativas similares
- **Corregido conteo**: 37 indicadores en 7 categorías (era 40 antes de eliminar 3 de cartera)

### 2026-02-06 - Ajustes post Fase 4
- **Normalización de nombres unificada**: LIMITADA→LTDA en `procesar_balance_cooperativas.py` y `procesar_camel.py`
- **Nombres de mutualistas expandidos** en `procesar_camel.py`: "AMBATO"→"ASOCIACION MUTUALISTA DE AHORRO Y CREDITO PARA LA VIVIENDA AMBATO"
- **Correcciones de nombre** en `procesar_camel.py` (CORRECCIONES_NOMBRE dict): 8 cooperativas con nombres distintos entre indicadores y balance
- **Catálogo mejorado** en `generar_agregados.py`: usa última fecha por cooperativa (no solo última global)
- `agg_catalogo_cooperativas.parquet`: 259 cooperativas (antes 203)
- `indicadores.parquet`: 231 cooperativas (antes 261, después de normalizar)
- Solo 3 cooperativas sin match en balance (cerradas/absorbidas 2020-2021)
- **Reorganización CAMEL**: Vulnerabilidad (VULN_PAT, FK, FI, CAP_NETO, CART_IMPR_PAT) movida a C-Capital, eliminada SUF_PAT
- **Selectores**: Top 30, Top 50, Todas (ranking y heatmap)
- **Heatmap**: siempre ordena por activos totales (más grande abajo, más pequeño arriba)
- **Segmento unificado**: cada cooperativa toma el segmento de su último dato disponible (51 cooperativas cambiaron de segmento histórico)

### 2026-02-06 - Fase 4 completada (Indicadores CAMEL desde pivot cache)
- Reescrito módulo 4_CAMEL.py: ya no calcula indicadores, los lee pre-extraídos
- Creado script `procesar_camel.py`: extrae indicadores del pivot cache de XLSM
- Generado `indicadores.parquet`: ~550K registros, 231 cooperativas, 2020-2025
- Agregadas constantes CAMEL a `indicator_mapping.py`: GRUPOS_INDICADORES, ETIQUETAS, ESCALAS, RANGOS
- Agregada función `cargar_indicadores()` a `data_loader.py`

### 2026-02-06 - Fase 3 completada
- Agregado módulo 3_Perdidas_Ganancias.py con suma móvil 12 meses
- Creado script procesar_pyg.py (desacumulación + suma móvil)
- Creado script procesar_indicadores.py (extrae datos de XLSM - legacy)
- Agregado pyg.parquet con columnas valor_acumulado, valor_mes, valor_12m
- Normalización de nombres: LIMITADA → LTDA
- Exclusión de totales VT_ en visualizaciones de PyG
- Agregada función cargar_pyg() en data_loader.py

### 2026-02-05 - Fase 2 completada
- Agregado sistema de colores para 200+ cooperativas (Top 10 brillantes, resto gradual)
- Optimización de rendimiento con datos pre-agregados (~3.6 MB vs 73 MB)
- Agregada sección de Pasivos y Patrimonio en Panorama
- Corregida inconsistencia de unidades (1000 → 1_000_000 para millones)
- Unificados selectores de cuentas jerárquicos en los 3 módulos de Balance General
- Agregado script `generar_agregados.py`

### 2026-02-04 - Fase 1 completada
- Implementación completa de ETL de balances
- Módulos Streamlit: Panorama y Balance General
