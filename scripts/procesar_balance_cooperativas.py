# -*- coding: utf-8 -*-
"""
Pipeline ETL para procesar balances de cooperativas ecuatorianas.
Lee archivos ZIP con datos CSV/TXT y genera balance.parquet consolidado.
"""

import pandas as pd
import zipfile
import json
import io
from pathlib import Path
from datetime import datetime
import warnings

try:
    from io_atomico import guardar_parquet_atomico
except ModuleNotFoundError:
    from scripts.io_atomico import guardar_parquet_atomico

warnings.filterwarnings('ignore')

# Rutas
BASE_DIR = Path(__file__).parent.parent
BALANCES_DIR = BASE_DIR / "balances_cooperativas"
OUTPUT_DIR = BASE_DIR / "master_data"


def calcular_nivel(codigo: str) -> int:
    """Calcula el nivel jerárquico según la longitud del código contable."""
    if pd.isna(codigo):
        return 0
    codigo_str = str(codigo).strip()
    longitud = len(codigo_str)
    if longitud == 1:
        return 1
    elif longitud == 2:
        return 2
    elif longitud <= 4:
        return 3
    elif longitud <= 6:
        return 4
    else:
        return 5


# Mapeo explícito de nombres de mutualistas:
# La SEPS usó el nombre largo hasta 2025 y lo abrevió a partir de 2026.
# Unificamos ambas formas al nombre canónico "Mutualista X".
MUTUALISTAS_NOMBRES = {
    'ASOCIACION MUTUALISTA DE AHORRO Y CREDITO PARA LA VIVIENDA AMBATO': 'Mutualista Ambato',
    'ASOCIACION MUTUALISTA DE AHORRO Y CREDITO PARA LA VIVIENDA AZUAY':  'Mutualista Azuay',
    'ASOCIACION MUTUALISTA DE AHORRO Y CREDITO PARA LA VIVIENDA IMBABURA': 'Mutualista Imbabura',
    'ASOCIACION MUTUALISTA DE AHORRO Y CREDITO PARA LA VIVIENDA PICHINCHA': 'Mutualista Pichincha',
    # Nombres cortos usados desde enero 2026
    'AMBATO':   'Mutualista Ambato',
    'AZUAY':    'Mutualista Azuay',
    'IMBABURA': 'Mutualista Imbabura',
    'PICHINCHA': 'Mutualista Pichincha',
}


def normalizar_nombre(nombre: str) -> str:
    """Normaliza el nombre de la cooperativa."""
    if pd.isna(nombre):
        return ""
    nombre = str(nombre).strip()

    # Aplicar mapeo explícito de mutualistas primero
    if nombre.upper() in MUTUALISTAS_NOMBRES:
        return MUTUALISTAS_NOMBRES[nombre.upper()]

    # Remover prefijos comunes para nombres más cortos
    prefijos = [
        "COOPERATIVA DE AHORRO Y CREDITO ",
        "COOPERATIVA DE AHORRO Y CRÉDITO ",
        "COOP. DE AHORRO Y CREDITO ",
    ]
    for prefijo in prefijos:
        if nombre.upper().startswith(prefijo):
            nombre = nombre[len(prefijo):]
            break
    nombre = nombre.strip()

    # Unificar LIMITADA a LTDA
    nombre = nombre.replace(' LIMITADA', ' LTDA')

    # Eliminar punto al final de LTDA.
    if nombre.endswith('LTDA.'):
        nombre = nombre[:-1]

    # Eliminar espacios múltiples
    nombre = ' '.join(nombre.split())

    return nombre


def leer_xlsm_balance(zip_path: Path, zf: zipfile.ZipFile) -> pd.DataFrame:
    """
    Lee archivos XLSM de balance (formato nuevo desde 2026).

    El ZIP contiene múltiples XLSM (uno por segmento). Cada XLSM tiene una
    hoja de Estado Financiero con formato ancho: COD CONTABLE, Nombre de Cuenta,
    TIPO*, GRUPO**, y luego una columna por cooperativa. La fecha de corte está
    en una fila anterior al header.
    Devuelve un DataFrame en formato largo (una fila por cooperativa+cuenta).
    """
    IGNORAR = {'CONAFIPS', 'FINANCOOP'}
    # Segmento inferido del nombre del archivo
    SEGMENTOS = {
        'Segmento 1': 'SEGMENTO 1',
        'Segmento 2': 'SEGMENTO 2',
        'Segmento 3': 'SEGMENTO 3',
        'Mutualistas': 'SEGMENTO 1 MUTUALISTA',
    }

    xlsms = [
        f for f in zf.namelist()
        if f.endswith('.xlsm')
        and not any(ign in f for ign in IGNORAR)
    ]
    print(f"    XLSM a procesar: {[f.split('/')[-1] for f in xlsms]}")

    dfs = []
    for xlsm_path in xlsms:
        # Detectar segmento desde nombre de archivo
        segmento = None
        for key, val in SEGMENTOS.items():
            if key in xlsm_path:
                segmento = val
                break
        if segmento is None:
            print(f"    Saltando (segmento desconocido): {xlsm_path}")
            continue

        with zf.open(xlsm_path) as f:
            content = f.read()

        xl = pd.ExcelFile(io.BytesIO(content))
        # Buscar hoja de Estado Financiero
        hoja = next(
            (s for s in xl.sheet_names if 'ESTADO' in s.upper() and 'FINANCIERO' in s.upper()),
            None
        )
        if hoja is None:
            print(f"    Sin hoja de Estado Financiero en {xlsm_path}")
            continue

        df_raw = xl.parse(hoja, header=None)

        # Encontrar fila del header (contiene 'COD CONTABLE')
        header_row = None
        for i, row in df_raw.iterrows():
            if any(str(v).strip().upper() == 'COD CONTABLE' for v in row if pd.notna(v)):
                header_row = i
                break
        if header_row is None:
            print(f"    No se encontró header en {xlsm_path}")
            continue

        # Encontrar fecha de corte (buscar celda con datetime o '2026-' antes del header)
        fecha = None
        for i in range(header_row):
            for v in df_raw.iloc[i]:
                if isinstance(v, datetime):
                    fecha = v
                    break
                if isinstance(v, str) and '2026-' in v:
                    try:
                        fecha = pd.to_datetime(v)
                    except Exception:
                        pass
                if fecha:
                    break
            if fecha:
                break
        # Fallback: extraer del nombre de archivo (ene_2026 → 2026-01-31)
        if fecha is None:
            import re
            meses = {'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6,
                     'jul': 7, 'ago': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dic': 12}
            m = re.search(r'_(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)_(\d{4})', xlsm_path)
            if m:
                mes_n = meses[m.group(1)]
                anio_n = int(m.group(2))
                ultimo_dia = pd.Timestamp(anio_n, mes_n, 1) + pd.offsets.MonthEnd(0)
                fecha = ultimo_dia
        if fecha is None:
            print(f"    No se encontró fecha en {xlsm_path}, saltando")
            continue

        print(f"    {xlsm_path.split('/')[-1]}: fecha={pd.Timestamp(fecha).strftime('%Y-%m-%d')}, segmento={segmento}")

        # Extraer datos usando el header encontrado
        df_raw.columns = df_raw.iloc[header_row]
        df_data = df_raw.iloc[header_row + 1:].copy()
        df_data = df_data.rename(columns={
            'COD CONTABLE': 'codigo',
            'Nombre de Cuenta': 'cuenta',
        })

        # Columnas de cooperativas = todo excepto las primeras 4 metadatos
        cols_meta = ['codigo', 'cuenta', 'TIPO*', 'GRUPO**']
        cols_coops = [c for c in df_data.columns if c not in cols_meta and pd.notna(c) and str(c).strip()]

        # Eliminar fila de totales VT_TOTAL si existe
        cols_coops = [c for c in cols_coops if 'VT_TOTAL' not in str(c).upper()]

        # Melt: formato ancho → largo
        df_long = df_data[['codigo', 'cuenta'] + cols_coops].melt(
            id_vars=['codigo', 'cuenta'],
            var_name='cooperativa',
            value_name='valor'
        )
        df_long['fecha'] = pd.Timestamp(fecha)
        df_long['segmento'] = segmento
        df_long['ruc'] = None

        # Limpiar
        df_long = df_long.dropna(subset=['codigo', 'valor'])
        df_long['codigo'] = df_long['codigo'].astype(str).str.strip()
        df_long = df_long[df_long['codigo'].str.match(r'^\d+$')]  # Solo códigos numéricos
        df_long['valor'] = pd.to_numeric(df_long['valor'], errors='coerce').fillna(0)

        dfs.append(df_long)

    if not dfs:
        raise ValueError("No se pudo leer ningún XLSM del ZIP")

    return pd.concat(dfs, ignore_index=True)


def leer_archivo_desde_zip(zip_path: Path) -> pd.DataFrame:
    """Lee el archivo de datos desde un ZIP (CSV/TXT o XLSM según año)."""
    print(f"  Procesando: {zip_path.name}")

    # Determinar año del archivo para decidir el formato
    año_archivo = int(zip_path.name.split('-')[0].split('_')[0])

    with zipfile.ZipFile(zip_path, 'r') as zf:
        archivos = zf.namelist()
        print(f"    Archivos internos: {[a.split('/')[-1] for a in archivos if not a.endswith('/')]}")

        # Detectar si el ZIP contiene XLSM (nuevo formato desde 2026)
        xlsms = [f for f in archivos if f.endswith('.xlsm')]
        if xlsms:
            print(f"    Formato XLSM detectado ({len(xlsms)} archivos)")
            return leer_xlsm_balance(zip_path, zf)

        # Formato CSV/TXT (2018-2025)
        candidatos = [f for f in archivos if f.endswith(('.csv', '.txt', '.CSV', '.TXT'))]
        if not candidatos:
            candidatos = [f for f in archivos if not f.endswith('/')]
        archivo_datos = candidatos[0]
        print(f"    Leyendo: {archivo_datos}")

        with zf.open(archivo_datos) as f:
            if año_archivo >= 2022:
                df = pd.read_csv(f, sep='\t', encoding='utf-8-sig', dtype=str)
                df.columns = df.columns.str.strip().str.replace('\ufeff', '')
                df = df.rename(columns={
                    'FECHA DE CORTE': 'FECHA_DE_CORTE',
                    'RAZON SOCIAL': 'RAZON_SOCIAL',
                    'DESCRIPCION CUENTA': 'DESCRIPCION_CUENTA',
                    'SALDO (USD)': 'SALDO_USD',
                })
            else:
                df = pd.read_csv(f, sep=';', encoding='utf-8-sig', dtype={'CUENTA': str, 'RUC': str})

    df.columns = df.columns.str.strip().str.replace('\ufeff', '')
    return df


def procesar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Procesa y normaliza el DataFrame.

    Acepta tanto el formato CSV histórico (columnas en mayúsculas con prefijos)
    como el formato largo ya normalizado que devuelve leer_xlsm_balance.
    """

    # Renombrar columnas del formato CSV (si vienen en ese formato)
    if 'FECHA_DE_CORTE' in df.columns:
        df = df.rename(columns={
            'FECHA_DE_CORTE': 'fecha',
            'SEGMENTO': 'segmento',
            'RUC': 'ruc',
            'RAZON_SOCIAL': 'cooperativa',
            'CUENTA': 'codigo',
            'DESCRIPCION_CUENTA': 'cuenta',
            'SALDO_USD': 'valor',
        })

    # Parsear fecha (si no es ya datetime)
    df['fecha'] = pd.to_datetime(df['fecha'], format='mixed')

    # segmento_historico: el segmento tal como lo reportó la propia entidad
    # en ESTE archivo/mes, antes de cualquier unificación posterior. Se
    # captura aquí (inmediatamente después de leer el archivo fuente) porque
    # es el único punto del pipeline donde el valor es genuinamente
    # point-in-time. `segmento` (más abajo, en generar_balance_parquet) se
    # sobrescribe con el último segmento conocido de cada cooperativa — eso
    # es correcto para rankings/filtros "actuales", pero NO debe usarse para
    # análisis histórico o sistémico por período (ver docs/RIESGO_METODOLOGIA.md §15).
    df['segmento_historico'] = df['segmento']
    df['segmento_historico_estimado'] = False

    # Normalizar nombres de cooperativas
    df['cooperativa'] = df['cooperativa'].apply(normalizar_nombre)

    # Calcular nivel jerárquico
    df['nivel'] = df['codigo'].apply(calcular_nivel)

    # Limpiar valores - manejar formato con coma decimal (CSV histórico)
    if df['valor'].dtype == object:
        df['valor'] = df['valor'].str.replace(',', '.', regex=False)
    df['valor'] = pd.to_numeric(df['valor'], errors='coerce').fillna(0)

    # Asegurar que código sea string
    df['codigo'] = df['codigo'].astype(str).str.strip()

    return df


def generar_balance_parquet():
    """Genera el archivo balance.parquet consolidado.

    Modo incremental: si ya existe balance.parquet, carga los datos históricos
    desde él y solo procesa los ZIPs que contengan meses nuevos. Esto permite
    correr el ETL en GitHub Actions sin necesidad de tener todos los ZIPs históricos.
    """

    print("=" * 60)
    print("PIPELINE ETL - BALANCES DE COOPERATIVAS")
    print("=" * 60)

    # Crear directorio de salida si no existe
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # --- Modo incremental: cargar parquet existente si está disponible ---
    output_path = OUTPUT_DIR / "balance.parquet"
    df_historico = None
    fecha_max_existente = None

    if output_path.exists():
        print("\n[INCREMENTAL] Cargando balance.parquet existente...")
        df_historico = pd.read_parquet(output_path)
        fecha_max_existente = df_historico['fecha'].max()
        print(f"  Datos existentes hasta: {fecha_max_existente.strftime('%Y-%m')}")
        print(f"  Registros existentes: {len(df_historico):,}")

        # Backfill de segmento_historico para parquets generados antes de esta
        # columna existir: lo único disponible en ese caso es el `segmento`
        # ya unificado (last-known), así que se marca explícitamente como
        # estimado (no point-in-time real) en vez de fingir precisión que no
        # existe. Corridas futuras de este script, sobre archivos fuente que sí
        # incluyen la columna, no vuelven a pisar este flag.
        if 'segmento_historico' not in df_historico.columns:
            print("  [segmento_historico] Columna ausente en el parquet existente — "
                  "backfill como ESTIMADO (= segmento last-known, no point-in-time real).")
            df_historico['segmento_historico'] = df_historico['segmento']
            df_historico['segmento_historico_estimado'] = True

    # Buscar todos los ZIPs disponibles
    zips = sorted(BALANCES_DIR.glob("*.zip"))
    print(f"\nArchivos ZIP encontrados: {len(zips)}")

    # En modo incremental, solo procesar ZIPs que puedan tener datos nuevos
    if fecha_max_existente is not None and len(zips) > 0:
        # Filtrar: solo ZIPs del año de fecha_max en adelante
        # (el ZIP del año corriente puede tener meses nuevos)
        año_min = fecha_max_existente.year
        zips_nuevos = [z for z in zips if int(z.name.split('-')[0].split('_')[0]) >= año_min]
        if len(zips_nuevos) < len(zips):
            print(f"  [INCREMENTAL] Procesando solo {len(zips_nuevos)} ZIP(s) con datos potencialmente nuevos")
        zips = zips_nuevos

    # Procesar cada ZIP seleccionado
    dataframes = []
    for zip_path in zips:
        try:
            df = leer_archivo_desde_zip(zip_path)
            df = procesar_dataframe(df)
            # En modo incremental, descartar fechas que ya están en el parquet existente
            if fecha_max_existente is not None:
                df_nuevo = df[df['fecha'] > fecha_max_existente]
                if len(df_nuevo) == 0:
                    print(f"    -> Sin datos nuevos (todo hasta {fecha_max_existente.strftime('%Y-%m')})")
                    continue
                print(f"    -> {len(df_nuevo):,} registros nuevos (de {len(df):,} totales en el ZIP)")
                df = df_nuevo
            else:
                print(f"    -> {len(df):,} registros")
            dataframes.append(df)
        except Exception as e:
            print(f"    ERROR: {e}")

    # Combinar datos históricos con los nuevos
    if df_historico is not None and len(dataframes) > 0:
        print("\nCombinando datos históricos con nuevos...")
        # Pasar categorías a object sin materializar arreglos Unicode gigantes.
        # astype(str) llegó a requerir >6 GB para 24 millones de filas.
        for col in ['segmento', 'cooperativa', 'codigo', 'cuenta', 'segmento_historico']:
            if col in df_historico.columns:
                df_historico[col] = df_historico[col].astype('object')
        df_nuevos = pd.concat(dataframes, ignore_index=True)
        df_final = pd.concat([df_historico, df_nuevos], ignore_index=True)
    elif df_historico is not None and len(dataframes) == 0:
        print("\nNo hay datos nuevos que agregar. El parquet ya está actualizado.")
        df_final = df_historico
    else:
        print("\nConsolidando datos...")
        df_final = pd.concat(dataframes, ignore_index=True)

    # Unificar segmento: cada cooperativa toma el segmento de su último dato
    print("Unificando segmentos...")
    ultimo_segmento = (
        df_final.sort_values('fecha')
        .drop_duplicates(subset=['cooperativa'], keep='last')[['cooperativa', 'segmento']]
        .set_index('cooperativa')['segmento']
    )
    coops_multi = df_final.groupby('cooperativa')['segmento'].nunique()
    coops_cambiaron = coops_multi[coops_multi > 1].index.tolist()
    if coops_cambiaron:
        print(f"  Cooperativas con cambio de segmento: {len(coops_cambiaron)} (unificando al último)")
    df_final['segmento'] = df_final['cooperativa'].map(ultimo_segmento)
    # Alias explícito: `segmento` (nombre histórico de la columna, usado por
    # ~100 referencias en pages/analytics/utils) y `segmento_actual` (nombre
    # claro para código nuevo) son el MISMO valor — el último segmento
    # conocido de cada cooperativa. Para análisis por período usar
    # `segmento_historico` en su lugar (ver nota en procesar_dataframe()).
    df_final['segmento_actual'] = df_final['segmento']
    if 'segmento_historico' not in df_final.columns:
        df_final['segmento_historico'] = df_final['segmento'].astype('object')
    if 'segmento_historico_estimado' not in df_final.columns:
        df_final['segmento_historico_estimado'] = True
    df_final['segmento_historico'] = df_final['segmento_historico'].astype('object')
    df_final['segmento_historico'] = df_final['segmento_historico'].where(
        df_final['segmento_historico'].notna(), df_final['segmento']
    )
    df_final['segmento_historico_estimado'] = df_final['segmento_historico_estimado'].fillna(True)

    # Eliminar columnas no usadas por la UI
    df_final = df_final.drop(columns=['ruc', 'nivel'], errors='ignore')

    # Optimizar tipos de datos
    print("Optimizando tipos de datos...")
    df_final['segmento'] = df_final['segmento'].astype('category')
    df_final['segmento_actual'] = df_final['segmento_actual'].astype('category')
    df_final['segmento_historico'] = df_final['segmento_historico'].astype('category')
    df_final['segmento_historico_estimado'] = df_final['segmento_historico_estimado'].astype('bool')
    df_final['cooperativa'] = df_final['cooperativa'].astype('category')
    df_final['codigo'] = df_final['codigo'].astype('category')
    df_final['cuenta'] = df_final['cuenta'].astype('category')

    # Ordenar
    df_final = df_final.sort_values(['fecha', 'segmento', 'cooperativa', 'codigo'])
    df_final = df_final.reset_index(drop=True)

    # Estadísticas
    print("\n" + "=" * 60)
    print("ESTADÍSTICAS")
    print("=" * 60)
    print(f"Total registros: {len(df_final):,}")
    print(f"Cooperativas únicas: {df_final['cooperativa'].nunique()}")
    print(f"Segmentos: {df_final['segmento'].unique().tolist()}")
    print(f"Fechas: {df_final['fecha'].min().strftime('%Y-%m')} a {df_final['fecha'].max().strftime('%Y-%m')}")
    print(f"Meses únicos: {df_final['fecha'].nunique()}")
    print(f"Cuentas únicas: {df_final['codigo'].nunique()}")
    pct_estimado = df_final['segmento_historico_estimado'].mean() * 100
    print(f"segmento_historico estimado (no point-in-time real): {pct_estimado:.1f}% de registros")

    # Guardar parquet
    guardar_parquet_atomico(df_final, output_path, engine='pyarrow', compression='snappy')

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"\nArchivo generado: {output_path}")
    print(f"Tamaño: {size_mb:.1f} MB")

    # Generar metadata
    metadata = {
        'fecha_procesamiento': datetime.now().isoformat(),
        'registros_totales': len(df_final),
        'cooperativas': df_final['cooperativa'].nunique(),
        'segmentos': df_final['segmento'].unique().tolist(),
        'fecha_min': df_final['fecha'].min().isoformat(),
        'fecha_max': df_final['fecha'].max().isoformat(),
        'meses': df_final['fecha'].nunique(),
        'cuentas': df_final['codigo'].nunique(),
        'archivos_procesados': [z.name for z in zips],
    }

    metadata_path = OUTPUT_DIR / "metadata.json"
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"Metadata guardada: {metadata_path}")
    print("\n" + "=" * 60)
    print("PROCESO COMPLETADO")
    print("=" * 60)

    return df_final


if __name__ == "__main__":
    generar_balance_parquet()
