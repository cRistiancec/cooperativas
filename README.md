# DATA METRICS
[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://cooperativas-q73wpzj6f7.streamlit.app)
### Business Intelligence and Analytics

## Radar Cooperativo Ecuador

**Sistema Inteligente para el Monitoreo Integral del Sector Financiero Popular y Solidario**

git pull origin main

**Autor institucional**: Eco. Cristian Coronel Quezada, MBA — CEO - DATAMETRICS

## Descripcion del Proyecto

Plataforma de monitoreo y analisis de datos financieros del sector financiero popular y solidario ecuatoriano, basado en informacion publica de la Superintendencia de Economia Popular y Solidaria (SEPS). Permite analisis temporal, comparativo y de indicadores CAMEL de las cooperativas de ahorro y credito.

La plataforma cuenta actualmente con 4 modulos principales: panorama del sistema, estructura de balance, analisis de resultados (PyG) y evaluacion CAMEL con indicadores oficiales de la Superintendencia. Ver `PROYECTO/AUDITORIA_COMPLETA.md` y `CHANGELOG.md` para el plan y registro de la reconstruccion institucional en curso.

## Fuente de Datos

- **Origen**: Superintendencia de Economia Popular y Solidaria (SEPS) - Catalogo Unico de Cuentas
- **Periodo cubierto**: enero 2018-junio 2026 (102 meses para balance; 78 meses para PyG/CAMEL)
- **Instituciones**: 259 cooperativas unicas (Segmentos 1, 2, 3 y Mutualistas)
- **Registros**: 24.2 millones (balance) + 2.36 millones (PyG) + 603K (indicadores CAMEL)
- **Formato**: Archivos Parquet optimizados con dtypes category para memoria eficiente

### Estructura de Datos

Archivos en `master_data/`:

| Archivo | Tamano | Registros | Descripcion |
|---------|--------|-----------|-------------|
| `balance.parquet` | 82 MB | 24.17M | Balance General (Activos, Pasivos, Patrimonio) |
| `pyg.parquet` | 18 MB | 2.36M | Estado de Resultados con suma movil 12 meses |
| `indicadores.parquet` | 3.7 MB | 603K | Indicadores CAMEL oficiales |
| `agg_*.parquet` | 3.7 MB | - | Datos pre-agregados para consultas rapidas |
| `metadata.json` | <1 KB | - | Metadatos de procesamiento |

Columnas principales (balance):
- `cooperativa`: Nombre normalizado de la institucion
- `segmento`: SEGMENTO 1, SEGMENTO 2, SEGMENTO 3, SEGMENTO 1 MUTUALISTA
- `fecha`: Periodo (formato YYYY-MM-DD)
- `codigo`: Codigo contable (1-6 digitos segun nivel jerarquico)
- `cuenta`: Descripcion de la cuenta contable
- `valor`: Monto en USD

## Estructura del Proyecto

```
cooperativas/
├── Inicio.py                              # Pagina principal (multipage app)
├── pages/                                 # Modulos de analisis
│   ├── 1_Panorama.py                     # Vision general del sistema
│   ├── 2_Balance_General.py              # Analisis temporal de balance
│   ├── 3_Perdidas_Ganancias.py           # Estado de resultados (PyG)
│   └── 4_CAMEL.py                        # Indicadores CAMEL oficiales
├── ui/                                     # Capa de presentacion institucional
│   ├── theme.py                          # Inyector de tema (dark COSEDE)
│   ├── header.py                         # Header institucional
│   └── sidebar.py                        # Sidebar premium (buscador, favoritos, estado)
├── styles/                                 # Hojas de estilo modulares
│   ├── theme.css / styles.css / responsive.css / animations.css
├── utils/                                 # Utilidades compartidas
│   ├── data_loader.py                    # Carga y validacion de datos
│   └── charts.py                         # Componentes de visualizacion
├── config/
│   ├── indicator_mapping.py              # Mapeo de codigos, colores, CAMEL
│   └── constants.py                      # Constantes compartidas (meses, etc.)
├── scripts/                               # Scripts de procesamiento ETL
│   ├── procesar_balance_cooperativas.py  # ZIPs CSV → balance.parquet
│   ├── procesar_pyg.py                   # Desacumulacion + suma movil 12M
│   ├── procesar_camel.py                 # Extraccion de pivot cache XLSM
│   ├── procesar_indicadores.py           # ETL desde XLSM (legacy)
│   └── generar_agregados.py             # Genera datos pre-agregados
├── master_data/                           # Datos procesados (Parquet)
├── balances_cooperativas/                 # ZIPs fuente balance (no en repo)
├── indicadores/                           # ZIPs fuente indicadores (no en repo)
├── docs/
│   └── CONTEXTO.md                       # Documentacion tecnica detallada
├── PROYECTO/
│   └── AUDITORIA_COMPLETA.md             # Auditoria integral y hoja de ruta
├── CHANGELOG.md                           # Registro de la reconstruccion por fases
├── requirements.txt                       # Dependencias
└── .streamlit/config.toml                # Configuracion de tema (dark)
```

## Modulos Implementados

### 0. Inicio (Inicio.py)
**Estado**: Completado

Pagina principal con descripcion del sistema, KPIs generales y navegacion a los 4 modulos.

### 1. Panorama del Sistema (1_Panorama.py)
**Estado**: Completado

Vision consolidada del sistema cooperativo con indicadores de mercado y concentracion.

- **KPIs del Sistema**: Activos totales, cartera, depositos, patrimonio, numero de cooperativas
- **Treemaps**: Activos y pasivos con drill-down (Cooperativa → Componentes)
- **Rankings**: Top cooperativas por activos y pasivos
- **Crecimiento YoY**: Variacion anual de cartera y depositos
- Datos pre-agregados para carga rapida (~3.7 MB vs 78 MB)

### 2. Balance General (2_Balance_General.py)
**Estado**: Completado

Analisis profundo de la estructura patrimonial con selector de cuentas jerarquico de 4 niveles.

- **Evolucion Comparativa**: Series temporales de multiples cooperativas con modos Absoluto/Indexado/Participacion
- **Heatmap de Variacion YoY**: Matriz cooperativa x mes con escala de colores divergente
- **Ranking por Cuenta**: Comparacion de valores para cuenta y mes especificos

### 3. Perdidas y Ganancias (3_Perdidas_Ganancias.py)
**Estado**: Completado

Analisis de resultados basado en suma movil de 12 meses para comparabilidad interanual.

- **Evolucion Comparativa**: Series temporales con valores anualizados (valor_12m)
- **Ranking por Cuenta**: Comparacion de cooperativas por cuenta de ingresos/gastos
- Selector jerarquico: Nivel 1 (Gastos/Ingresos) → Nivel 2 (subcuentas)

### 4. Indicadores CAMEL (4_CAMEL.py)
**Estado**: Completado

Indicadores financieros **oficiales de la Superintendencia**, extraidos directamente del pivot cache de los archivos XLSM (37 indicadores en 7 categorias).

| Categoria | Indicadores | Ejemplos |
|-----------|-------------|----------|
| C - Capital | 5 | FK, FI, Capitalizacion Neto |
| A - Calidad de Activos | 3 | Act. Improductivos/Activos, AP/PC |
| A - Morosidad | 7 | Morosidad Total, Consumo, Micro, Inmobiliaria |
| A - Cobertura | 7 | Cobertura Total, Consumo, Micro, Inmobiliaria |
| M - Management | 3 | Gastos Op/Activo, Gastos Op/Margen |
| E - Earnings | 11 | ROE, ROA, Intermediacion, Rendimientos de Cartera |
| L - Liquidez | 1 | Fondos Disponibles / Depositos CP |

Tres pestanas: **Ranking**, **Evolucion Temporal**, **Heatmap Mensual**.

## Pipeline de Procesamiento

### Orden de ejecucion

```bash
cd cooperativas

# 1. Procesar balances desde ZIPs (genera balance.parquet)
python scripts/procesar_balance_cooperativas.py

# 2. Generar datos pre-agregados para Panorama
python scripts/generar_agregados.py

# 3. Extraer staging del ZIP reciente para PyG/CAMEL
python scripts/procesar_indicadores.py

# 4. Procesar PyG incremental (desacumulacion + suma movil 12M)
python scripts/procesar_pyg.py

# 5. Procesar indicadores CAMEL incremental desde pivot cache XLSM
python scripts/procesar_camel.py

# 6. Verificar fecha, consistencia entre salidas y preservacion historica
python scripts/validar_actualizacion.py
```

### Optimizacion de memoria

Los archivos Parquet usan dtypes optimizados para Streamlit Cloud (limite ~1 GB RAM):

| Metrica | Sin optimizar | Optimizado | Reduccion |
|---------|---------------|------------|-----------|
| Balance RAM | 4,736 MB | 500 MB | -89% |
| PyG RAM | 723 MB | 79 MB | -89% |
| **Total** | **5,459 MB** | **579 MB** | **-89%** |

Optimizaciones aplicadas:
- Columnas `ruc` y `nivel` eliminadas (no usadas por la UI)
- Columnas string (`codigo`, `cuenta`) almacenadas como `category` dtype
- Carga selectiva de columnas con `pd.read_parquet(columns=...)`
- `groupby(..., observed=True)` para evitar productos cartesianos de categorías
- PyG y CAMEL reemplazan solo los meses incluidos en el ZIP reciente

## Instalacion y Uso

### Requisitos
- Python 3.8+
- Streamlit 1.28+
- Pandas, NumPy, Plotly, PyArrow

### Instalacion

```bash
cd cooperativas
pip install -r requirements.txt
```

### Ejecucion

```bash
streamlit run Inicio.py --server.port 8502
```

Acceder en: http://localhost:8502

## Despliegue en Streamlit Cloud

La aplicacion esta desplegada en Streamlit Cloud y se actualiza automaticamente con cada push a `main`.

- **Archivo principal**: `Inicio.py`
- **Rama**: `main`

## Notas Tecnicas

### Normalizacion de nombres
- Prefijo "COOPERATIVA DE AHORRO Y CREDITO" removido
- LIMITADA → LTDA en todas las fuentes
- Mutualistas: nombres cortos expandidos a nombre completo
- 8 correcciones manuales para consistencia entre balance e indicadores

### Unificacion de segmentos
Cooperativas que cambiaron de segmento a lo largo del tiempo (70+) toman el segmento de su ultimo dato disponible, asegurando un unico segmento por cooperativa en todo el periodo.

### Indicadores CAMEL - Pivot Cache
- Los archivos XLSM son ZIPs con XML interno (pivot cache)
- El numero del cache varia entre anos (cache3 en 2021/2023, cache4 en otros)
- Valores almacenados como ratios (0-1), la UI multiplica por 100 para porcentajes
- Deteccion automatica del cache correcto via campos marcadores (I28_ROE, I29_ROA)

## Tecnologias Utilizadas

- **Python 3.8+**: Lenguaje principal
- **Streamlit 1.28+**: Framework de dashboard interactivo
- **Pandas**: Manipulacion y analisis de datos
- **Plotly**: Visualizaciones interactivas
- **PyArrow**: Lectura eficiente de archivos Parquet
- **NumPy**: Operaciones numericas

## Autor Institucional

**Eco. Cristian Coronel Quezada, MBA**
Coordinación Técnica de Riesgos y Estudios — COSEDE

---

**Nota**: Este proyecto utiliza datos publicos de la Superintendencia de Economia Popular y Solidaria del Ecuador.
