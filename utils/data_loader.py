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
# FILTRADO GLOBAL (ÚNICA vía de acceso a datos filtrados por la selección del usuario)
# =============================================================================
# La lógica vive en `utils/filtros_analisis.py` (pura, sin Streamlit). Aquí solo se cachean las lecturas y se
# aplica el filtro sobre cada base. Ninguna función de esta sección usa el segmento ACTUAL retroactivo para filtrar.

SEGMENTO_SIN_CLASIFICAR = "SIN CLASIFICACIÓN VERIFICABLE"
_COLS_DIM = ["entidad", "cooperativa", "segmento_clasif", "segmento_actual", "procedencia_clasif", "fuente_clasif"]


@st.cache_data(ttl=3600, show_spinner=False)
def cargar_dim_observaciones() -> pd.DataFrame:
    """Dimensión (cooperativa, fecha) -> entidad, segmento puntual y procedencia. Ver scripts/generar_dim_observaciones.py."""
    ruta = MASTER_DATA_DIR / "dim_observaciones.parquet"
    if not ruta.exists():
        return pd.DataFrame(columns=_COLS_DIM + ["fecha"])
    d = pd.read_parquet(ruta)
    for c in _COLS_DIM:
        d[c] = d[c].astype(object)
    d["fecha"] = pd.to_datetime(d["fecha"])
    return d


@st.cache_data(ttl=3600, show_spinner=False)
def cargar_identificadores() -> Dict[str, str]:
    """entidad -> RUC(s) conocidos (solo Segmento 1/Mutualista/FINANCOOP tienen RUC), para búsqueda por identificador."""
    ruta = MASTER_DATA_DIR / "entidades_cooperativas.parquet"
    if not ruta.exists():
        return {}
    e = pd.read_parquet(ruta, columns=["nombre", "ruc"])
    e = e[e["ruc"].notna() & (e["ruc"].astype(str).str.strip() != "")]
    from analytics.vulnerabilidad.identidad import entidad_id
    e["entidad"] = e["nombre"].map(entidad_id)
    return e.groupby("entidad")["ruc"].apply(lambda x: " ".join(sorted(set(map(str, x))))).to_dict()


def filtrar(df: pd.DataFrame, filtro, col_entidad: str = "cooperativa", col_fecha: str = "fecha") -> pd.DataFrame:
    """Aplica período ∩ segmentos ∩ entidades ∩ calidad a cualquier DataFrame con (entidad, fecha). Usa la lógica única."""
    from utils.filtros_analisis import aplicar_filtros_analisis
    return aplicar_filtros_analisis(df, filtro, cargar_dim_observaciones(), col_fecha=col_fecha, col_entidad=col_entidad)


def _presentar(df: pd.DataFrame) -> pd.DataFrame:
    """`segmento` pasa a ser la clasificación PUNTUAL del período; el segmento actual retroactivo se conserva aparte."""
    if df.empty:
        return df
    if "segmento" in df.columns and "segmento_actual" not in df.columns:
        df = df.rename(columns={"segmento": "segmento_actual"})
    seg = df["segmento_clasif"]
    if isinstance(seg.dtype, pd.CategoricalDtype):
        seg = seg.cat.add_categories([SEGMENTO_SIN_CLASIFICAR]) if SEGMENTO_SIN_CLASIFICAR not in seg.cat.categories else seg
    df["segmento"] = seg.fillna(SEGMENTO_SIN_CLASIFICAR)
    return df


@st.cache_data(ttl=3600, max_entries=10, show_spinner=False)
def datos_filtrados(nombre: str, filtro, codigos: Tuple[str, ...] = ()) -> pd.DataFrame:
    """
    Base `nombre` ('ranking' | 'series' | 'indicadores' | 'pyg' | 'balance' | 'solvencia') restringida al filtro.
    La clave de caché incluye el filtro completo (período, segmentos, entidades, calidad): una selección distinta
    nunca reutiliza el resultado de otra. Añade `entidad`, `segmento_clasif` y `procedencia_clasif`.
    """
    if filtro is None:
        from utils.filtros_analisis import filtro_por_defecto
        filtro = filtro_por_defecto(cargar_dim_observaciones())
    if nombre == "ranking":
        base = cargar_ranking_cooperativas()
    elif nombre == "series":
        base = cargar_series_temporales()
    elif nombre == "indicadores":
        base = cargar_indicadores()[0]
    elif nombre == "pyg":
        base = cargar_pyg()[0]
    elif nombre == "balance":
        base = cargar_balance_por_codigos(tuple(codigos))
    elif nombre == "solvencia":
        base = cargar_solvencia()[0]
    else:
        raise ValueError(f"base desconocida: {nombre}")
    if base is None or base.empty:
        return pd.DataFrame()
    return _presentar(filtrar(base, filtro, col_entidad="cooperativa"))


def datos_universo(nombre: str, filtro, codigos: Tuple[str, ...] = ()) -> pd.DataFrame:
    """
    Población de REFERENCIA de los análisis relativos (percentiles CAMEL, IIS, alertas): período ∩ segmentos ∩ calidad,
    SIN restringir entidades. La selección de entidades solo decide cuáles se muestran (`acotar_entidades`); así un score
    percentil no se degenera a «100» cuando se elige una sola cooperativa.
    """
    return datos_filtrados(nombre, filtro.sin_entidades(), codigos)


def acotar_entidades(df: pd.DataFrame, filtro) -> pd.DataFrame:
    """Muestra únicamente las entidades seleccionadas (si no hay selección, toda la población)."""
    if df is None or df.empty or not filtro.entidades:
        return df
    return df[df["entidad"].astype(str).isin(set(filtro.entidades))]


# =============================================================================
# FUNCIONES DE CONSULTA OPTIMIZADAS (todas reciben el FiltroAnalisis completo)
# =============================================================================

_CODIGOS_KPI = {
    'total_activos': '1', 'fondos_disponibles': '11', 'total_cartera': '14', 'total_depositos': '21', 'total_patrimonio': '3',
}


def obtener_metricas_kpi(fecha, filtro) -> dict:
    """
    KPIs de la población filtrada (en millones). Se calculan sumando el ranking filtrado, que reproduce exactamente
    el agregado del sistema (`agg_metricas_sistema`) cuando no hay restricciones.
    """
    rk = datos_filtrados("ranking", filtro)
    if rk.empty:
        return {}
    d = rk[rk['fecha'] == pd.Timestamp(fecha)]
    if d.empty:
        return {}
    metricas = {nombre: d.loc[d['codigo'] == cod, 'valor'].sum() / 1_000_000 for nombre, cod in _CODIGOS_KPI.items()}
    metricas['num_cooperativas'] = d.loc[d['codigo'] == '1', 'entidad'].nunique()
    return metricas


def obtener_ranking_rapido(fecha, codigo: str = '1', top_n: int = 20, filtro=None) -> pd.DataFrame:
    """Ranking de la población filtrada para una cuenta y un corte (top_n=0 → todas)."""
    rk = datos_filtrados("ranking", filtro)
    if rk.empty:
        return pd.DataFrame()
    d = rk[(rk['fecha'] == pd.Timestamp(fecha)) & (rk['codigo'] == codigo)].copy()
    if d.empty:
        return pd.DataFrame()
    d = d.sort_values('valor', ascending=False)
    if top_n > 0:
        d = d.head(top_n)
    d['valor_millones'] = d['valor'] / 1_000_000
    return d[['fecha', 'cooperativa', 'segmento', 'valor', 'valor_millones', 'procedencia_clasif']]


def obtener_datos_treemap_rapido(fecha, filtro, top_n: int = 20) -> pd.DataFrame:
    """Datos del treemap de activos de la población filtrada (vectorizado)."""
    df = datos_filtrados("ranking", filtro)
    if df.empty:
        return pd.DataFrame()
    df_fecha = df[df['fecha'] == pd.Timestamp(fecha)]

    # NIVEL 1: Top cooperativas por activos (código '1')
    activos = df_fecha[df_fecha['codigo'] == '1'].nlargest(top_n, 'valor')
    activos = activos[activos['valor'].notna() & (activos['valor'] > 0)]
    if activos.empty:
        return pd.DataFrame()

    activos_coop_str = activos['cooperativa'].astype(str).values
    df_n1 = pd.DataFrame({
        'labels': activos_coop_str, 'parents': '', 'values': activos['valor'].values / 1_000_000,
        'tipo': 'cooperativa', 'id': activos_coop_str,
    })

    # NIVEL 2: Subcuentas por cooperativa
    cooperativas_top = activos['cooperativa'].tolist()
    cuentas_nivel2 = {'11': 'Fondos Disponibles', '13': 'Inversiones', '14': 'Cartera de Créditos'}
    df_top = df_fecha[
        df_fecha['cooperativa'].isin(cooperativas_top) & df_fecha['codigo'].isin(cuentas_nivel2.keys()) &
        df_fecha['valor'].notna() & (df_fecha['valor'] > 0)
    ].copy()
    if not df_top.empty:
        df_top['nombre_cuenta'] = df_top['codigo'].map(cuentas_nivel2)
        coop_str = df_top['cooperativa'].astype(str).values
        df_n2 = pd.DataFrame({
            'labels': df_top['nombre_cuenta'].values, 'parents': coop_str, 'values': df_top['valor'].values / 1_000_000,
            'tipo': 'cuenta_nivel2', 'id': coop_str + '_' + df_top['nombre_cuenta'].values,
        })
        df_tree = pd.concat([df_n1, df_n2], ignore_index=True)
    else:
        df_tree = df_n1

    total_sistema = df_n1['values'].sum()
    df_tree['participacion'] = (df_tree['values'] / total_sistema * 100) if total_sistema > 0 else 0
    return df_tree


def obtener_datos_treemap_pasivos_rapido(fecha, filtro, top_n: int = 20) -> pd.DataFrame:
    """Datos del treemap de pasivos y patrimonio de la población filtrada (vectorizado)."""
    df = datos_filtrados("ranking", filtro)
    if df.empty:
        return pd.DataFrame()
    df_fecha = df[df['fecha'] == pd.Timestamp(fecha)]

    activos = df_fecha[df_fecha['codigo'] == '1'].nlargest(top_n, 'valor')
    cooperativas_top = activos['cooperativa'].tolist()

    df_pas_pat = df_fecha[df_fecha['cooperativa'].isin(cooperativas_top) & df_fecha['codigo'].isin(['2', '3'])]
    totales = df_pas_pat.groupby('cooperativa', observed=True)['valor'].sum().reset_index()
    totales = totales[totales['valor'] > 0]
    if totales.empty:
        return pd.DataFrame()

    totales_coop_str = totales['cooperativa'].astype(str).values
    df_n1 = pd.DataFrame({
        'labels': totales_coop_str, 'parents': '', 'values': totales['valor'].values / 1_000_000,
        'tipo': 'cooperativa', 'id': totales_coop_str,
    })

    cuentas_nivel2 = {'21': 'Obligaciones con el Público', '26': 'Obligaciones Financieras', '3': 'Patrimonio'}
    df_sub = df_fecha[
        df_fecha['cooperativa'].isin(cooperativas_top) & df_fecha['codigo'].isin(cuentas_nivel2.keys()) &
        df_fecha['valor'].notna() & (df_fecha['valor'] > 0)
    ].copy()
    if not df_sub.empty:
        df_sub['nombre_cuenta'] = df_sub['codigo'].map(cuentas_nivel2)
        coop_str = df_sub['cooperativa'].astype(str).values
        df_n2 = pd.DataFrame({
            'labels': df_sub['nombre_cuenta'].values, 'parents': coop_str, 'values': df_sub['valor'].values / 1_000_000,
            'tipo': 'cuenta_nivel2', 'id': coop_str + '_' + df_sub['nombre_cuenta'].values,
        })
        df_tree = pd.concat([df_n1, df_n2], ignore_index=True)
    else:
        df_tree = df_n1

    total_sistema = df_n1['values'].sum()
    df_tree['participacion'] = (df_tree['values'] / total_sistema * 100) if total_sistema > 0 else 0
    return df_tree


def obtener_crecimiento_anual(fecha_actual, fecha_anterior, codigo: str, filtro=None, top_n: int = 20) -> pd.DataFrame:
    """
    Crecimiento entre dos cortes de las entidades que cumplen el filtro EN `fecha_actual`.

    Excepción documentada: el valor base (`fecha_anterior`, normalmente 12 meses antes) se toma de la MISMA entidad
    aunque ese mes quede fuera del período elegido o la entidad tuviera otro segmento entonces; el crecimiento es
    inherentemente una comparación entre dos fechas y solo la observación del corte debe cumplir el filtro.
    """
    rk = datos_filtrados("ranking", filtro)
    if rk.empty:
        return pd.DataFrame()
    actual = rk[(rk['fecha'] == pd.Timestamp(fecha_actual)) & (rk['codigo'] == codigo)][['cooperativa', 'segmento', 'procedencia_clasif', 'valor']]
    actual = actual.rename(columns={'valor': 'valor_actual'})
    crudo = cargar_ranking_cooperativas()
    previo = crudo[(crudo['fecha'] == pd.Timestamp(fecha_anterior)) & (crudo['codigo'] == codigo)][['cooperativa', 'valor']]
    previo = previo.rename(columns={'valor': 'valor_anterior'})
    actual = actual.assign(cooperativa=actual['cooperativa'].astype(str))
    previo = previo.assign(cooperativa=previo['cooperativa'].astype(str))
    df_crec = actual.merge(previo, on='cooperativa', how='inner', validate='one_to_one')
    df_crec['fecha_actual'] = pd.Timestamp(fecha_actual)
    df_crec['fecha_anterior'] = pd.Timestamp(fecha_anterior)
    df_crec['crecimiento'] = (df_crec['valor_actual'] - df_crec['valor_anterior']) / df_crec['valor_anterior'] * 100
    df_crec = df_crec[df_crec['valor_anterior'] > 0].dropna(subset=['crecimiento'])
    if top_n > 0:
        df_crec = df_crec.nlargest(top_n, 'valor_actual')
    return df_crec.sort_values('crecimiento', ascending=True)


def obtener_serie_sistema(codigo: str, filtro=None) -> pd.DataFrame:
    """Serie temporal del total de la población filtrada para una cuenta (suma del ranking filtrado)."""
    rk = datos_filtrados("ranking", filtro)
    if rk.empty:
        return pd.DataFrame(columns=['fecha', 'valor_total'])
    return (rk[rk['codigo'] == codigo].groupby('fecha', observed=True)['valor']
            .sum().rename('valor_total').reset_index().sort_values('fecha'))


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


def obtener_segmentos_disponibles_rapido() -> list:
    """Segmentos con clasificación verificable en la dimensión de observaciones (clasificación puntual)."""
    d = cargar_dim_observaciones()
    return sorted(d['segmento_clasif'].dropna().unique()) if not d.empty else []


def obtener_cooperativas_filtro(filtro) -> list:
    """Cooperativas de la población filtrada, ordenadas por activos del último corte disponible dentro de la selección."""
    rk = datos_filtrados("ranking", filtro)
    if rk.empty:
        return []
    a = rk[rk['codigo'] == '1'].sort_values('fecha')
    ult = a.groupby('cooperativa', observed=True).tail(1).sort_values('valor', ascending=False)
    return ult['cooperativa'].astype(str).tolist()


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
    df = df.drop_duplicates(subset=['fecha', 'cooperativa'])

    # La dimensión oficial (una fila por cooperativa-mes, tomada del archivo
    # SEPS de ese corte) manda sobre cualquier backfill estimado del balance.
    dim_path = MASTER_DATA_DIR / "dim_segmento_historico.parquet"
    if dim_path.exists():
        dim = pd.read_parquet(dim_path, columns=['cooperativa', 'fecha', 'segmento_historico'])
        dim['fecha'] = pd.to_datetime(dim['fecha'])
        dim['cooperativa'] = dim['cooperativa'].astype(str)
        df['cooperativa'] = df['cooperativa'].astype(str)
        df = df.drop(columns=['segmento_historico', 'segmento_historico_estimado'], errors='ignore')
        df = df.merge(dim, on=['cooperativa', 'fecha'], how='left')
        df['segmento_historico_estimado'] = df['segmento_historico'].isna()
        df['segmento_historico'] = df['segmento_historico'].fillna(df['segmento_actual'])

    return df


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
