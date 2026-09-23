# -*- coding: utf-8 -*-
"""
Carga centralizada de datos con validación y limpieza para cooperativas.
Usa archivos pre-agregados para consultas rápidas.

El período cubierto NO se documenta aquí como valor fijo: se deriva siempre de
los propios datos (`obtener_ultima_fecha`, `obtener_fechas_disponibles_rapido`,
`calidad['fecha_max']`), de modo que incorporar un mes nuevo al ETL no requiere
tocar código ni documentación en línea.
"""

import pandas as pd
import pyarrow.parquet as pq
import streamlit as st
from pathlib import Path
from typing import Tuple, Dict, Any, List, Optional
import json

from utils.logging_config import medir_rendimiento


def _leer_parquet_eficiente(filepath: Path, columnas: List[str]) -> pd.DataFrame:
    """
    Lee un Parquet vía PyArrow y lo convierte a pandas con
    `to_pandas(split_blocks=True, self_destruct=True)`: libera cada columna
    de la tabla de Arrow a medida que construye el DataFrame de pandas, en
    vez de mantener ambas copias completas en memoria simultáneamente.

    Medido en la auditoría de producción sobre `balance.parquet` (24M filas,
    6 columnas): reduce el pico de RSS de ~1232 MB (`pd.read_parquet()`
    directo) a ~1018 MB (-17%), de forma consistente y repetible.

    NOTA: se evaluó además `read_dictionary=[...]` para que las columnas de
    baja cardinalidad (codigo/cuenta/cooperativa) lleguen ya como `category`
    sin pasar por `astype()` después. Los resultados fueron inconsistentes
    en el entorno de auditoría (a veces peor que sin `read_dictionary`), así
    que se descartó esa parte — cada llamador sigue convirtiendo a
    `category` explícitamente después de leer, como antes.
    """
    tabla = pq.read_table(filepath, columns=columnas)
    df = tabla.to_pandas(split_blocks=True, self_destruct=True)
    del tabla
    return df

# Ruta base de datos
MASTER_DATA_DIR = Path(__file__).parent.parent / "master_data"


# =============================================================================
# CARGA DE DATOS PRE-AGREGADOS (RÁPIDO)
# =============================================================================

@st.cache_data(ttl=3600)
def cargar_metricas_sistema() -> pd.DataFrame:
    """
    Carga métricas pre-agregadas por fecha/segmento/código.
    Archivo pequeño (~30KB) para KPIs rápidos.
    """
    filepath = MASTER_DATA_DIR / "agg_metricas_sistema.parquet"
    if not filepath.exists():
        return pd.DataFrame()
    return pd.read_parquet(filepath)


@st.cache_data(ttl=3600)
def cargar_ranking_cooperativas() -> pd.DataFrame:
    """
    Carga ranking pre-agregado de cooperativas.
    Archivo mediano (~1.4MB) para rankings y treemaps.
    """
    filepath = MASTER_DATA_DIR / "agg_ranking_cooperativas.parquet"
    if not filepath.exists():
        return pd.DataFrame()
    return pd.read_parquet(filepath)


@st.cache_data(ttl=3600)
def cargar_series_temporales() -> pd.DataFrame:
    """
    Carga series temporales pre-agregadas.
    Archivo mediano (~2MB) para gráficos de evolución.
    """
    filepath = MASTER_DATA_DIR / "agg_series_temporales.parquet"
    if not filepath.exists():
        return pd.DataFrame()
    return pd.read_parquet(filepath)


@st.cache_data(ttl=3600)
def cargar_catalogo_cooperativas() -> pd.DataFrame:
    """
    Carga catálogo de cooperativas con ranking por activos.
    Archivo muy pequeño (~5KB).
    """
    filepath = MASTER_DATA_DIR / "agg_catalogo_cooperativas.parquet"
    if not filepath.exists():
        return pd.DataFrame()
    return pd.read_parquet(filepath)


# =============================================================================
# FUNCIONES DE CONSULTA OPTIMIZADAS
# =============================================================================

@st.cache_data(ttl=3600)
def obtener_metricas_kpi(fecha, segmento: str = "Todos") -> dict:
    """
    Obtiene métricas del sistema para KPIs de forma optimizada.
    Usa datos pre-agregados en lugar de filtrar 22M registros.
    """
    df = cargar_metricas_sistema()
    if df.empty:
        return {}

    # Filtrar por fecha
    df_fecha = df[df['fecha'] == fecha]

    # Filtrar por segmento
    if segmento != "Todos":
        df_fecha = df_fecha[df_fecha['segmento'] == segmento]

    metricas = {}

    # Mapeo de códigos a nombres
    codigos = {
        'total_activos': '1',
        'fondos_disponibles': '11',
        'total_cartera': '14',
        'total_depositos': '21',
        'total_patrimonio': '3',
    }

    for nombre, codigo in codigos.items():
        valor = df_fecha[df_fecha['codigo'] == codigo]['valor_total'].sum()
        metricas[nombre] = valor / 1_000_000  # Convertir a millones

    # Número de cooperativas (del código 1 = activos)
    df_activos = df_fecha[df_fecha['codigo'] == '1']
    metricas['num_cooperativas'] = df_activos['num_cooperativas'].sum()

    return metricas


@st.cache_data(ttl=3600)
def obtener_ranking_rapido(fecha, codigo: str = '1', top_n: int = 20, segmento: str = "Todos") -> pd.DataFrame:
    """
    Obtiene ranking de cooperativas de forma optimizada.
    """
    df = cargar_ranking_cooperativas()
    if df.empty:
        return pd.DataFrame()

    # Filtrar
    mask = (df['fecha'] == fecha) & (df['codigo'] == codigo)
    if segmento != "Todos":
        mask &= (df['segmento'] == segmento)

    df_filtrado = df[mask].copy()

    if df_filtrado.empty:
        return pd.DataFrame()

    # Ordenar y tomar top N (0 = todas)
    df_filtrado = df_filtrado.sort_values('valor', ascending=False)
    if top_n > 0:
        df_filtrado = df_filtrado.head(top_n)
    df_filtrado['valor_millones'] = df_filtrado['valor'] / 1_000_000

    return df_filtrado[['cooperativa', 'segmento', 'valor', 'valor_millones']]


@st.cache_data(ttl=3600)
def obtener_datos_treemap_rapido(fecha, segmento: str = "Todos", top_n: int = 20) -> pd.DataFrame:
    """
    Prepara datos para treemap de forma optimizada (vectorizado).
    """
    df = cargar_ranking_cooperativas()
    if df.empty:
        return pd.DataFrame()

    # Filtrar por fecha y segmento
    mask = df['fecha'] == fecha
    if segmento != "Todos":
        mask &= df['segmento'] == segmento
    df_fecha = df[mask]

    # NIVEL 1: Top cooperativas por activos (código '1')
    activos = df_fecha[df_fecha['codigo'] == '1'].nlargest(top_n, 'valor')
    activos = activos[activos['valor'].notna() & (activos['valor'] > 0)]

    if activos.empty:
        return pd.DataFrame()

    # Construir nivel 1 vectorizado
    activos_coop_str = activos['cooperativa'].astype(str).values
    df_n1 = pd.DataFrame({
        'labels': activos_coop_str,
        'parents': '',
        'values': activos['valor'].values / 1_000_000,
        'tipo': 'cooperativa',
        'id': activos_coop_str,
    })

    # NIVEL 2: Subcuentas por cooperativa (vectorizado)
    cooperativas_top = activos['cooperativa'].tolist()
    cuentas_nivel2 = {'11': 'Fondos Disponibles', '13': 'Inversiones', '14': 'Cartera de Créditos'}

    df_top = df_fecha[
        df_fecha['cooperativa'].isin(cooperativas_top) &
        df_fecha['codigo'].isin(cuentas_nivel2.keys()) &
        df_fecha['valor'].notna() &
        (df_fecha['valor'] > 0)
    ].copy()

    if not df_top.empty:
        df_top['nombre_cuenta'] = df_top['codigo'].map(cuentas_nivel2)
        coop_str = df_top['cooperativa'].astype(str).values
        df_n2 = pd.DataFrame({
            'labels': df_top['nombre_cuenta'].values,
            'parents': coop_str,
            'values': df_top['valor'].values / 1_000_000,
            'tipo': 'cuenta_nivel2',
            'id': coop_str + '_' + df_top['nombre_cuenta'].values,
        })
        df_tree = pd.concat([df_n1, df_n2], ignore_index=True)
    else:
        df_tree = df_n1

    # Participación
    total_sistema = df_n1['values'].sum()
    df_tree['participacion'] = (df_tree['values'] / total_sistema * 100) if total_sistema > 0 else 0

    return df_tree


@st.cache_data(ttl=3600)
def obtener_datos_treemap_pasivos_rapido(fecha, segmento: str = "Todos", top_n: int = 20) -> pd.DataFrame:
    """
    Prepara datos para treemap de pasivos y patrimonio (vectorizado).
    """
    df = cargar_ranking_cooperativas()
    if df.empty:
        return pd.DataFrame()

    # Filtrar por fecha y segmento
    mask = df['fecha'] == fecha
    if segmento != "Todos":
        mask &= df['segmento'] == segmento
    df_fecha = df[mask]

    # Top cooperativas por activos
    activos = df_fecha[df_fecha['codigo'] == '1'].nlargest(top_n, 'valor')
    cooperativas_top = activos['cooperativa'].tolist()

    # NIVEL 1: Pasivo + Patrimonio por cooperativa (vectorizado)
    df_pas_pat = df_fecha[
        df_fecha['cooperativa'].isin(cooperativas_top) &
        df_fecha['codigo'].isin(['2', '3'])
    ]
    totales = df_pas_pat.groupby('cooperativa', observed=True)['valor'].sum().reset_index()
    totales = totales[totales['valor'] > 0]

    if totales.empty:
        return pd.DataFrame()

    totales_coop_str = totales['cooperativa'].astype(str).values
    df_n1 = pd.DataFrame({
        'labels': totales_coop_str,
        'parents': '',
        'values': totales['valor'].values / 1_000_000,
        'tipo': 'cooperativa',
        'id': totales_coop_str,
    })

    # NIVEL 2: Subcuentas por cooperativa (vectorizado)
    cuentas_nivel2 = {'21': 'Obligaciones con el Público', '26': 'Obligaciones Financieras', '3': 'Patrimonio'}

    df_sub = df_fecha[
        df_fecha['cooperativa'].isin(cooperativas_top) &
        df_fecha['codigo'].isin(cuentas_nivel2.keys()) &
        df_fecha['valor'].notna() &
        (df_fecha['valor'] > 0)
    ].copy()

    if not df_sub.empty:
        df_sub['nombre_cuenta'] = df_sub['codigo'].map(cuentas_nivel2)
        coop_str = df_sub['cooperativa'].astype(str).values
        df_n2 = pd.DataFrame({
            'labels': df_sub['nombre_cuenta'].values,
            'parents': coop_str,
            'values': df_sub['valor'].values / 1_000_000,
            'tipo': 'cuenta_nivel2',
            'id': coop_str + '_' + df_sub['nombre_cuenta'].values,
        })
        df_tree = pd.concat([df_n1, df_n2], ignore_index=True)
    else:
        df_tree = df_n1

    # Participación
    total_sistema = df_n1['values'].sum()
    df_tree['participacion'] = (df_tree['values'] / total_sistema * 100) if total_sistema > 0 else 0

    return df_tree


@st.cache_data(ttl=3600)
def obtener_crecimiento_anual(fecha_actual, fecha_anterior, codigo: str, segmento: str = "Todos", top_n: int = 20) -> pd.DataFrame:
    """
    Calcula crecimiento anual por cooperativa de forma optimizada.
    """
    df = cargar_ranking_cooperativas()
    if df.empty:
        return pd.DataFrame()

    # Datos actuales
    mask_actual = (df['fecha'] == fecha_actual) & (df['codigo'] == codigo)
    if segmento != "Todos":
        mask_actual &= (df['segmento'] == segmento)
    df_actual = df[mask_actual][['cooperativa', 'segmento', 'valor']].copy()
    df_actual = df_actual.rename(columns={'valor': 'valor_actual'})

    # Datos anteriores
    mask_anterior = (df['fecha'] == fecha_anterior) & (df['codigo'] == codigo)
    df_anterior = df[mask_anterior][['cooperativa', 'valor']].copy()
    df_anterior = df_anterior.rename(columns={'valor': 'valor_anterior'})

    # Merge
    df_crec = df_actual.merge(df_anterior, on='cooperativa', how='inner')

    # Calcular crecimiento
    df_crec['crecimiento'] = (
        (df_crec['valor_actual'] - df_crec['valor_anterior']) /
        df_crec['valor_anterior'] * 100
    )

    # Filtrar y ordenar (top_n=0 = todas)
    df_crec = df_crec[df_crec['valor_anterior'] > 0].dropna(subset=['crecimiento'])
    if top_n > 0:
        df_crec = df_crec.nlargest(top_n, 'valor_actual')
    df_crec = df_crec.sort_values('crecimiento', ascending=True)

    return df_crec


@st.cache_data(ttl=3600)
def obtener_serie_sistema(codigo: str, segmento: str = "Todos") -> pd.DataFrame:
    """
    Serie temporal del total del sistema para una cuenta de balance dada. Usa
    el mismo agregado y la misma lógica de suma que `obtener_metricas_kpi`,
    pero devuelve todas las fechas de una vez para construir mini-tendencias
    (sparklines) en el home ejecutivo.

    `segmento="Todos"` (por defecto) suma todos los segmentos y reproduce
    exactamente el comportamiento anterior; cualquier otro valor restringe la
    suma a ese segmento, lo que permite filtrar el dashboard principal por
    segmento sin duplicar la lógica de agregación.
    """
    df = cargar_metricas_sistema()
    if df.empty:
        return pd.DataFrame(columns=['fecha', 'valor_total'])

    df_f = df[df['codigo'] == codigo]
    if segmento != "Todos":
        df_f = df_f[df_f['segmento'] == segmento]

    serie = (
        df_f
        .groupby('fecha', observed=True)['valor_total']
        .sum()
        .reset_index()
        .sort_values('fecha')
    )
    return serie


# =============================================================================
# FUNCIONES DE UTILIDAD
# =============================================================================

@st.cache_data(ttl=3600)
def obtener_fechas_disponibles_rapido() -> list:
    """Obtiene lista de fechas únicas desde datos pre-agregados."""
    df = cargar_metricas_sistema()
    if df.empty:
        return []
    fechas = df['fecha'].unique()
    return sorted(fechas, reverse=True)


@st.cache_data(ttl=3600)
def obtener_ultima_fecha():
    """
    Último período disponible, derivado **de los datos** (no de metadata.json
    ni de ninguna fecha escrita a mano).

    Fuente única de verdad para "los datos están al mes X" en cabeceras y
    tarjetas informativas: si el ETL incorpora un mes nuevo, este valor cambia
    solo, sin tocar código. Devuelve `None` si no hay agregados.
    """
    fechas = obtener_fechas_disponibles_rapido()
    return fechas[0] if fechas else None


@st.cache_data(ttl=3600)
def obtener_segmentos_disponibles_rapido() -> list:
    """Obtiene lista de segmentos únicos desde datos pre-agregados."""
    df = cargar_metricas_sistema()
    if df.empty:
        return []
    return sorted(df['segmento'].unique())


@st.cache_data(ttl=3600)
def obtener_cooperativas_por_segmento(segmento: str = "Todos") -> list:
    """Obtiene lista de cooperativas ordenadas por activos."""
    df = cargar_catalogo_cooperativas()
    if df.empty:
        return []

    if segmento != "Todos":
        df = df[df['segmento'] == segmento]

    return df['cooperativa'].tolist()


# =============================================================================
# CARGA DE DATOS COMPLETOS (SOLO CUANDO ES NECESARIO)
# =============================================================================

@st.cache_data(ttl=3600)
def cargar_catalogo_cuentas_balance() -> pd.DataFrame:
    """
    Catálogo único código/nombre de las 1,563 cuentas contables del balance,
    sin la dimensión temporal ni institucional (fecha, cooperativa, valor).

    Uso previsto: poblar selectores jerárquicos de cuenta (p. ej. Balance
    General) sin instanciar el DataFrame completo de 24M filas solo para
    resolver nombres de cuenta.

    Procesa por row group (`ParquetFile.read_row_group`) en vez de leer la
    columna `cuenta` completa de una sola vez: `codigo`/`cuenta` están
    dictionary-encoded en el Parquet, pero un `pq.read_table(columns=...)`
    de las 24M filas seguido de `drop_duplicates()` fuerza a pandas a
    expandir cada fila a su string completo antes de deduplicar, llevando el
    pico de RSS a >1 GB — tanto como `cargar_balance()` completo. Deduplicar
    dentro de cada row group (~1M filas) y solo después concatenar los
    resultados ya reducidos evita esa expansión masiva: pico de RSS medido
    ~230 MB (~1s) frente a >1 GB.
    """
    filepath = MASTER_DATA_DIR / "balance.parquet"
    if not filepath.exists():
        raise FileNotFoundError(f"No se encontró {filepath}")

    with medir_rendimiento("cargar_catalogo_cuentas_balance"):
        pf = pq.ParquetFile(filepath)
        partes = []
        for i in range(pf.num_row_groups):
            tabla = pf.read_row_group(i, columns=['codigo', 'cuenta'])
            partes.append(tabla.to_pandas().drop_duplicates())

        df = pd.concat(partes, ignore_index=True).drop_duplicates(subset='codigo', keep='last')
        df = df.sort_values('codigo').reset_index(drop=True)
        for col in ['codigo', 'cuenta']:
            if df[col].dtype == 'object':
                df[col] = df[col].astype('category')

    return df


@st.cache_data(ttl=3600)
def cargar_balance_por_codigos(codigos: Tuple[str, ...]) -> pd.DataFrame:
    """
    Carga balance.parquet filtrando por código de cuenta **en la propia
    lectura del Parquet** (predicate pushdown de PyArrow), en vez de cargar
    los 24M de registros completos y filtrar después en pandas.

    Uso previsto: análisis que solo necesitan 1-2 cuentas específicas (p. ej.
    cartera vencida/provisión en Riesgo de Crédito) — evita instanciar el
    DataFrame completo de `cargar_balance()` para descartar el 99%+ de las
    filas inmediatamente después. `codigos` es una tupla (no lista) para que
    `st.cache_data` pueda hashear el argumento.
    """
    filepath = MASTER_DATA_DIR / "balance.parquet"
    if not filepath.exists():
        raise FileNotFoundError(f"No se encontró {filepath}")

    with medir_rendimiento(f"cargar_balance_por_codigos({','.join(codigos)})"):
        columnas = ['fecha', 'segmento', 'cooperativa', 'codigo', 'cuenta', 'valor']
        tabla = pq.read_table(filepath, columns=columnas, filters=[('codigo', 'in', list(codigos))])
        df = tabla.to_pandas(split_blocks=True, self_destruct=True)
        del tabla

        if not pd.api.types.is_datetime64_any_dtype(df['fecha']):
            df['fecha'] = pd.to_datetime(df['fecha'])
        for col in ['codigo', 'cuenta']:
            if col in df.columns and df[col].dtype == 'object':
                df[col] = df[col].astype('category')

    return df


@st.cache_data(ttl=3600)
def cargar_balance() -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Carga balance.parquet completo.
    NOTA: Solo usar cuando se necesiten datos detallados (nivel 4-6 dígitos).
    Para la mayoría de consultas, usar las funciones optimizadas.
    """
    filepath = MASTER_DATA_DIR / "balance.parquet"

    if not filepath.exists():
        raise FileNotFoundError(f"No se encontró {filepath}")

    with medir_rendimiento("cargar_balance"):
        # Cargar solo columnas necesarias (excluir ruc y nivel que no se usan en la UI)
        columnas_necesarias = ['fecha', 'segmento', 'cooperativa', 'codigo', 'cuenta', 'valor']
        df = _leer_parquet_eficiente(filepath, columnas_necesarias)

        # Convertir fecha si es necesario
        if not pd.api.types.is_datetime64_any_dtype(df['fecha']):
            df['fecha'] = pd.to_datetime(df['fecha'])

        # Optimizar memoria: convertir strings a category
        for col in ['codigo', 'cuenta']:
            if col in df.columns and df[col].dtype == 'object':
                df[col] = df[col].astype('category')

        calidad = {
            'registros': len(df),
            'cooperativas': df['cooperativa'].nunique(),
            'segmentos': df['segmento'].nunique(),
            'fecha_min': df['fecha'].min(),
            'fecha_max': df['fecha'].max(),
        }

    return df, calidad


@st.cache_data(ttl=3600)
def cargar_metadata() -> Dict[str, Any]:
    """Carga metadata.json."""
    filepath = MASTER_DATA_DIR / "metadata.json"
    if not filepath.exists():
        return {}
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


@st.cache_data(ttl=3600)
def cargar_indicadores() -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Carga indicadores.parquet (Indicadores CAMEL extraídos del pivot cache).

    Columnas: cooperativa, segmento, fecha, codigo, indicador, valor, categoria
    Valores almacenados como ratios (0-1), no porcentajes.
    """
    filepath = MASTER_DATA_DIR / "indicadores.parquet"

    if not filepath.exists():
        raise FileNotFoundError(f"No se encontró {filepath}")

    with medir_rendimiento("cargar_indicadores"):
        df_original = pd.read_parquet(filepath)
        registros_originales = len(df_original)

        df = df_original.copy()

        # Filtrar indicadores vacíos
        mask_indicador_valido = df['indicador'].fillna('').str.strip() != ''
        df = df[mask_indicador_valido]

        # Filtrar valores nulos en columnas clave
        df = df.dropna(subset=['cooperativa', 'fecha'])

        # Convertir fecha a datetime si no lo es
        if not pd.api.types.is_datetime64_any_dtype(df['fecha']):
            df['fecha'] = pd.to_datetime(df['fecha'])

        calidad = {
            'registros_originales': registros_originales,
            'registros_limpios': len(df),
            'registros_eliminados': registros_originales - len(df),
            'cooperativas': df['cooperativa'].nunique(),
            'fechas': df['fecha'].nunique(),
            'fecha_min': df['fecha'].min(),
            'fecha_max': df['fecha'].max(),
            'indicadores_unicos': df['codigo'].nunique(),
            'categorias': df['categoria'].unique().tolist(),
        }

    return df, calidad


@st.cache_data(ttl=3600)
def cargar_segmento_historico() -> pd.DataFrame:
    """
    Carga SOLO las columnas de segmentación de balance.parquet (liviano: 4
    columnas en vez de las 6 de `cargar_balance()`, sin `codigo`/`cuenta`/`valor`).

    `segmento` (=`segmento_actual`): último segmento conocido de cada
    cooperativa, aplicado retroactivamente a toda su historia. Correcto para
    rankings/filtros "a la fecha actual".

    `segmento_historico`: segmento reportado por la propia entidad en ESE
    mes específico. Es el que debe usarse para análisis histórico o
    sistémico por período (breadth, concentración por segmento en el
    tiempo, etc.) — ver docs/RIESGO_METODOLOGIA.md §15.

    `segmento_historico_estimado`: True cuando el valor de
    `segmento_historico` no es point-in-time real sino un backfill igual a
    `segmento_actual` (parquets generados antes de que esta columna
    existiera, o corridas sin ZIP fuente nuevo que reprocesar). Filtrar por
    `segmento_historico_estimado == False` para quedarse solo con períodos
    donde el dato es genuinamente confiable.
    """
    filepath = MASTER_DATA_DIR / "balance.parquet"
    if not filepath.exists():
        raise FileNotFoundError(f"No se encontró {filepath}")

    columnas = ['fecha', 'cooperativa', 'segmento_actual', 'segmento_historico',
                'segmento_historico_estimado']
    try:
        df = _leer_parquet_eficiente(filepath, columnas)
    except Exception:  # noqa: BLE001 — PyArrow lanza ArrowInvalid, no KeyError, si falta una columna
        # Compatibilidad: parquet generado antes de que estas columnas existieran.
        df = _leer_parquet_eficiente(filepath, ['fecha', 'cooperativa', 'segmento'])
        df['segmento_actual'] = df['segmento']
        df['segmento_historico'] = df['segmento']
        df['segmento_historico_estimado'] = True
        df = df.drop(columns=['segmento'])

    if not pd.api.types.is_datetime64_any_dtype(df['fecha']):
        df['fecha'] = pd.to_datetime(df['fecha'])

    return df.drop_duplicates(subset=['fecha', 'cooperativa'])


@st.cache_data(ttl=3600)
def cargar_entidades() -> pd.DataFrame:
    """
    Carga master_data/entidades_cooperativas.parquet (tabla ligera de
    identidad — generada por `scripts/generar_entidades.py`).

    Una fila por cooperativa: ruc (parcial — solo Segmento 1/Mutualista/
    FINANCOOP, ver docs/RIESGO_METODOLOGIA.md §16), segmento_actual,
    fecha_inicio/fin de datos, estado ('activa'/'posible_salida'/
    'liquidacion_declarada') y observaciones. Devuelve DataFrame vacío si el
    archivo no existe todavía (fuente opcional, no bloquea el resto de la app).
    """
    filepath = MASTER_DATA_DIR / "entidades_cooperativas.parquet"
    if not filepath.exists():
        return pd.DataFrame(columns=[
            "nombre", "ruc", "ruc_fuente", "segmento_actual", "fecha_inicio", "fecha_fin_datos",
            "estado", "cambio_segmento_detectado", "n_segmentos_historicos",
            "pct_segmento_historico_estimado", "ultima_fecha_reportada", "observaciones",
        ])
    return pd.read_parquet(filepath)


@st.cache_data(ttl=3600)
def cargar_solvencia() -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Carga solvencia.parquet — Solvencia oficial SEPS (Patrimonio Técnico,
    fichas 58-63, fuente "Formulario de Solvencia"/boletín Patrimonio Técnico).

    Fuente INDEPENDIENTE de indicadores.parquet: identidad por RUC, cobertura
    parcial del universo (Segmento 1, Mutualistas, Caja Central FINANCOOP —
    la SEPS no publica esta razón para Segmento 2/3). Ver
    docs/RIESGO_METODOLOGIA.md §3.2.

    Es una fuente opcional/best-effort: si el archivo no existe todavía
    (p. ej. un despliegue que no corrió `procesar_solvencia.py`), devuelve un
    DataFrame vacío con las columnas esperadas en vez de fallar, para que las
    páginas que la consumen puedan mostrar "No disponible" sin romperse.

    Columnas: fecha, ruc, cooperativa, cooperativa_raw, grupo_fuente,
    ptp, pts, ptc, appr, solvencia, ptr_9pct,
    solvencia_recalculada_ptc_appr, discrepancia_solvencia, archivo_origen.
    `solvencia` es un ratio (0.09 = 9%), igual convención que indicadores.parquet.
    """
    filepath = MASTER_DATA_DIR / "solvencia.parquet"
    columnas_vacias = [
        'fecha', 'ruc', 'cooperativa', 'cooperativa_raw', 'grupo_fuente',
        'ptp', 'pts', 'ptc', 'appr', 'solvencia', 'ptr_9pct',
        'solvencia_recalculada_ptc_appr', 'discrepancia_solvencia', 'archivo_origen',
    ]

    if not filepath.exists():
        return pd.DataFrame(columns=columnas_vacias), {
            'disponible': False,
            'motivo': 'master_data/solvencia.parquet no existe (fuente FS01 no procesada en este despliegue)',
        }

    with medir_rendimiento("cargar_solvencia"):
        df = pd.read_parquet(filepath)
        if not pd.api.types.is_datetime64_any_dtype(df['fecha']):
            df['fecha'] = pd.to_datetime(df['fecha'])

        calidad = {
            'disponible': True,
            'registros': len(df),
            'ruc_unicos': df['ruc'].nunique(),
            'cooperativas': df['cooperativa'].nunique(),
            'grupos_fuente': sorted(df['grupo_fuente'].astype(str).unique().tolist()),
            'fecha_min': df['fecha'].min(),
            'fecha_max': df['fecha'].max(),
            'discrepancias': int(df['discrepancia_solvencia'].sum()),
        }

    return df, calidad


@st.cache_data(ttl=3600)
def cargar_pyg() -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Carga pyg.parquet (Estado de Pérdidas y Ganancias).
    Contiene cuentas 4 (Gastos) y 5 (Ingresos).

    Excluye las filas `VT_TOTAL SEGMENTO 1/2/3` y `VT_TOTAL MUTUALISTAS`
    (auditoría de segmentación, sep-2026): el boletín SEPS de origen incluye,
    además de cada cooperativa real, una fila de subtotal por segmento con el
    mismo `codigo`/`cuenta` que las cuentas normales — verificado que su
    `valor_acumulado` coincide, cuenta a cuenta, con la suma exacta de las
    cooperativas reales de ese segmento (diferencia 0.0000%). `balance.parquet`
    e `indicadores.parquet` ya excluyen estas filas en el ETL
    (`procesar_balance_cooperativas.py`, `procesar_camel.py`); `pyg.parquet`
    no lo hacía a nivel de archivo, así que cualquier `groupby('cooperativa')`
    o suma por segmento/sistema sobre el DataFrame crudo duplicaba el total
    real. `pages/3_Perdidas_Ganancias.py` ya lo filtraba de forma manual en
    varios puntos; se centraliza aquí para que TODO consumidor de
    `cargar_pyg()` reciba datos limpios sin tener que saberlo.
    """
    filepath = MASTER_DATA_DIR / "pyg.parquet"

    if not filepath.exists():
        raise FileNotFoundError(f"No se encontró {filepath}")

    with medir_rendimiento("cargar_pyg"):
        # Cargar solo columnas necesarias (excluir ruc que no se usa en la UI)
        columnas_necesarias = ['fecha', 'segmento', 'cooperativa', 'codigo', 'cuenta',
                               'valor_acumulado', 'valor_mes', 'valor_12m']
        df = _leer_parquet_eficiente(filepath, columnas_necesarias)

        # Excluir filas de subtotal VT_TOTAL* (ver docstring) antes de cualquier
        # otro procesamiento, para que ningún consumidor las vea.
        df = df[~df['cooperativa'].astype(str).str.startswith('VT_')].copy()

        # Convertir fecha si es necesario
        if not pd.api.types.is_datetime64_any_dtype(df['fecha']):
            df['fecha'] = pd.to_datetime(df['fecha'])

        # Optimizar memoria: convertir strings a category
        for col in ['segmento', 'cooperativa', 'codigo', 'cuenta']:
            if col in df.columns and df[col].dtype == 'object':
                df[col] = df[col].astype('category')

        calidad = {
            'registros': len(df),
            'cooperativas': df['cooperativa'].nunique(),
            'segmentos': df['segmento'].nunique(),
            'fecha_min': df['fecha'].min(),
            'fecha_max': df['fecha'].max(),
        }

    return df, calidad


# =============================================================================
# FUNCIONES LEGACY (compatibilidad con código existente)
# =============================================================================

def obtener_fechas_disponibles(df: pd.DataFrame) -> list:
    """Obtiene lista de fechas únicas ordenadas (más reciente primero)."""
    fechas = df['fecha'].dropna().unique()
    return sorted(fechas, reverse=True)


def obtener_segmentos_disponibles(df: pd.DataFrame) -> list:
    """Obtiene lista de segmentos únicos."""
    return sorted(df['segmento'].unique())


def filtrar_por_segmento(df: pd.DataFrame, segmento: str) -> pd.DataFrame:
    """Filtra DataFrame por segmento."""
    if segmento == "Todos":
        return df.copy()
    return df[df['segmento'] == segmento].copy()


def obtener_top_cooperativas(
    df: pd.DataFrame,
    fecha,
    codigo: str = '1',
    top_n: int = 20,
    segmento: Optional[str] = None
) -> List[str]:
    """Obtiene top N cooperativas por valor."""
    df_filtrado = df[(df['fecha'] == fecha) & (df['codigo'] == codigo)]
    if segmento and segmento != "Todos":
        df_filtrado = df_filtrado[df_filtrado['segmento'] == segmento]
    return df_filtrado.nlargest(top_n, 'valor')['cooperativa'].tolist()
