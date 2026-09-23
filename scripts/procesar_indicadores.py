# -*- coding: utf-8 -*-
"""
Procesa los archivos Excel de indicadores financieros para extraer:
- Estado de Resultados (PyG) desde pivotCacheRecords
- Indicadores Financieros (CAMEL) desde pivotCacheRecords

Los archivos .xlsm contienen tablas dinámicas con todos los meses del año.
Los datos crudos están en xl/pivotCache/pivotCacheRecords*.xml
"""

import ctypes
import gc
import zipfile
import xml.etree.ElementTree as ET
import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple
import json
from datetime import datetime
import re
import io

try:
    from seps_zip import seleccionar_zips_procesamiento
except ModuleNotFoundError:
    from scripts.seps_zip import seleccionar_zips_procesamiento

try:
    from io_atomico import guardar_parquet_atomico
except ModuleNotFoundError:
    from scripts.io_atomico import guardar_parquet_atomico


# Rutas
INDICADORES_DIR = Path(__file__).parent.parent / "indicadores"
MASTER_DATA_DIR = Path(__file__).parent.parent / "master_data"

# Namespace XML
NS = {'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

# Archivos a ignorar
IGNORAR = ['CONAFIPS', 'FINANCOOP']

try:
    _LIBC = ctypes.CDLL("libc.so.6")
except OSError:
    _LIBC = None  # no-op fuera de Linux (p. ej. desarrollo local en macOS/Windows)


def _liberar_memoria_al_os():
    """
    Causa raíz diagnosticada 14-sep-2026 (hardening P0): parsear cada
    Boletín (XML de pivot cache de hasta ~120 MB, vía `ET.fromstring` — ver
    `parsear_cache_records`) genera decenas de miles de objetos Python
    (cadenas, dicts, el árbol XML completo) que se liberan correctamente a
    nivel de Python (`gc.collect()` los recolecta), pero CPython/glibc no le
    devuelve esas páginas al sistema operativo automáticamente — el RSS del
    proceso queda "atascado" en el pico alcanzado. Procesando los 4 archivos
    del ZIP mensual (Mutualistas, Segmento 1, 2, 3) uno tras otro en el
    mismo proceso, sin esta función, el RSS medido creció 101→2050→2988→
    4325 MB (`ru_maxrss`) — suficiente para que el proceso muriera por OOM
    en el paso de Segmento 3 en un entorno con ~7-8 GB de RAM disponible,
    aunque Segmento 3 por sí solo procesa en ~19s sin problema.

    `malloc_trim(0)` (glibc) fuerza la devolución de memoria libre al SO.
    Verificado: tras cada archivo, el RSS real (`/proc/self/status` VmRSS)
    vuelve a ~105 MB en los 3 segmentos reales, en vez de acumularse. No
    cambia ningún resultado — es limpieza de memoria, no lógica de negocio.
    """
    gc.collect()
    if _LIBC is not None:
        try:
            _LIBC.malloc_trim(0)
        except Exception:
            pass


def extraer_lookup_tables(zip_file: zipfile.ZipFile, cache_def_path: str) -> Dict[str, List]:
    """Extrae las tablas de lookup (valores compartidos) del pivotCacheDefinition."""
    with zip_file.open(cache_def_path) as f:
        content = f.read().decode('utf-8')
        root = ET.fromstring(content)

        cache_fields = root.findall('.//main:cacheField', NS)
        field_values = {}
        field_names = []

        for field in cache_fields:
            name = field.get('name')
            field_names.append(name)
            shared_items = field.find('.//main:sharedItems', NS)

            if shared_items is not None:
                values = []
                for item in shared_items:
                    tag = item.tag.split('}')[-1]  # Remover namespace
                    if tag == 's':  # string
                        values.append(item.attrib.get('v', ''))
                    elif tag == 'd':  # date
                        values.append(item.attrib.get('v', ''))
                    elif tag == 'n':  # number
                        values.append(float(item.attrib.get('v', 0)))
                    elif tag == 'm':  # missing/null
                        values.append(None)
                    elif tag == 'e':  # error
                        values.append(None)
                    else:
                        values.append(item.attrib.get('v', ''))
                field_values[name] = values
            else:
                field_values[name] = []

        return field_names, field_values


def parsear_cache_records(zip_file: zipfile.ZipFile, cache_records_path: str,
                          field_names: List[str], field_values: Dict[str, List]) -> pd.DataFrame:
    """Parsea los registros del pivotCacheRecords y resuelve referencias."""

    with zip_file.open(cache_records_path) as f:
        content = f.read().decode('utf-8')

    root = ET.fromstring(content)
    registros = []

    for record in root:
        if record.tag.endswith('r'):
            fila = {}
            for i, item in enumerate(record):
                if i >= len(field_names):
                    break

                field_name = field_names[i]
                tag = item.tag.split('}')[-1]

                if tag == 'x':  # referencia a valor compartido
                    idx = int(item.attrib.get('v', 0))
                    if field_name in field_values and idx < len(field_values[field_name]):
                        fila[field_name] = field_values[field_name][idx]
                    else:
                        fila[field_name] = None
                elif tag == 's':  # string directo
                    fila[field_name] = item.attrib.get('v', '')
                elif tag == 'n':  # número directo
                    fila[field_name] = float(item.attrib.get('v', 0))
                elif tag == 'm':  # missing
                    fila[field_name] = None
                elif tag == 'd':  # date directo
                    fila[field_name] = item.attrib.get('v', '')
                else:
                    fila[field_name] = item.attrib.get('v', '')

            registros.append(fila)

    return pd.DataFrame(registros)


def encontrar_cache_balance(zip_file: zipfile.ZipFile) -> Tuple[str, str]:
    """Encuentra el cache que contiene datos de balance/PyG (el más grande)."""
    caches = []
    for name in zip_file.namelist():
        if 'pivotCacheRecords' in name and name.endswith('.xml'):
            info = zip_file.getinfo(name)
            caches.append((name, info.file_size))

    if not caches:
        return None, None

    # El cache más grande generalmente contiene los datos de balance
    caches.sort(key=lambda x: x[1], reverse=True)
    records_path = caches[0][0]

    # Encontrar la definición correspondiente
    cache_num = re.search(r'pivotCacheRecords(\d+)\.xml', records_path)
    if cache_num:
        def_path = f'xl/pivotCache/pivotCacheDefinition{cache_num.group(1)}.xml'
        return def_path, records_path

    return None, None


def procesar_xlsm_desde_bytes(xlsm_data: bytes, segmento: str) -> pd.DataFrame:
    """Procesa un archivo XLSM desde bytes en memoria (sin extraer a disco)."""
    try:
        with zipfile.ZipFile(io.BytesIO(xlsm_data), 'r') as z:
            def_path, records_path = encontrar_cache_balance(z)

            if not def_path or not records_path:
                print(f"    [!] No se encontro cache de datos")
                return pd.DataFrame()

            field_names, field_values = extraer_lookup_tables(z, def_path)
            df = parsear_cache_records(z, records_path, field_names, field_values)

            if df.empty:
                print(f"    [!] Cache vacio")
                return pd.DataFrame()

            if 'SEGMENTO' not in df.columns or df['SEGMENTO'].isna().all():
                df['SEGMENTO'] = segmento

            print(f"    [OK] {len(df):,} registros")
            return df

    except Exception as e:
        print(f"    [ERROR] {e}")
        return pd.DataFrame()


def detectar_segmento(filename: str) -> str:
    """Detecta el segmento desde el nombre del archivo."""
    filename_lower = filename.lower()
    if 'segmento 1' in filename_lower or 'segmento_1' in filename_lower:
        return 'SEGMENTO 1'
    elif 'segmento 2' in filename_lower or 'segmento_2' in filename_lower:
        return 'SEGMENTO 2'
    elif 'segmento 3' in filename_lower or 'segmento_3' in filename_lower:
        return 'SEGMENTO 3'
    elif 'mutualista' in filename_lower:
        return 'SEGMENTO 1 MUTUALISTA'
    return 'DESCONOCIDO'


def es_archivo_ignorar(filename: str) -> bool:
    """Verifica si el archivo debe ser ignorado."""
    for ignorar in IGNORAR:
        if ignorar.lower() in filename.lower():
            return True
    return False


def procesar_todos_indicadores():
    """Procesa todos los archivos ZIP de indicadores."""
    print("=" * 70)
    print("PROCESAMIENTO DE INDICADORES FINANCIEROS")
    print("=" * 70)

    todos_los_datos = []
    archivos_zip = seleccionar_zips_procesamiento(
        INDICADORES_DIR.glob("*.zip"),
        incremental=(MASTER_DATA_DIR / "pyg.parquet").exists(),
    )

    print(f"\nArchivos ZIP encontrados: {len(archivos_zip)}")
    if (MASTER_DATA_DIR / "pyg.parquet").exists():
        print("  Modo incremental: procesando únicamente el año más reciente")

    for zip_path in archivos_zip:
        print(f"\n[{zip_path.name}]")

        # Extraer el año del nombre del archivo
        year_match = re.search(r'(\d{4})', zip_path.name)
        year = year_match.group(1) if year_match else 'UNKNOWN'

        try:
            with zipfile.ZipFile(zip_path, 'r') as main_zip:
                # Buscar archivos XLSM dentro del ZIP
                xlsm_files = [n for n in main_zip.namelist() if n.endswith('.xlsm')]
                print(f"  Archivos XLSM: {len(xlsm_files)}")

                for xlsm_name in xlsm_files:
                    filename = Path(xlsm_name).name

                    # Ignorar CONAFIPS y FINANCOOP
                    if es_archivo_ignorar(filename):
                        print(f"  Ignorando: {filename}")
                        continue

                    print(f"  Procesando: {filename}")

                    # Detectar segmento
                    segmento = detectar_segmento(xlsm_name)

                    # Leer XLSM en memoria y procesar
                    xlsm_data = main_zip.read(xlsm_name)
                    df = procesar_xlsm_desde_bytes(xlsm_data, segmento)
                    del xlsm_data

                    if not df.empty:
                        df['ARCHIVO_ORIGEN'] = filename
                        df['ANIO_ARCHIVO'] = year
                        todos_los_datos.append(df)

                    # Ver _liberar_memoria_al_os(): sin esto, el RSS del
                    # proceso se acumula archivo tras archivo hasta agotar
                    # la memoria disponible en el paso de Segmento 3.
                    _liberar_memoria_al_os()

        except Exception as e:
            print(f"  [ERROR] Error procesando ZIP: {e}")

    if not todos_los_datos:
        raise RuntimeError("No se extrajeron datos de los ZIP de indicadores")

    # Combinar todos los DataFrames
    print("\n" + "=" * 70)
    print("CONSOLIDANDO DATOS")
    print("=" * 70)

    df_completo = pd.concat(todos_los_datos, ignore_index=True)
    print(f"Total registros consolidados: {len(df_completo):,}")

    # Normalizar columnas
    column_mapping = {
        'SEGMENTO': 'segmento',
        'NUM_RUC': 'ruc',
        'NOM_RAZON_SOCIAL': 'cooperativa',
        'FECHA': 'fecha',
        'NOMBRE_CUENTA': 'cuenta',
        'CODIGO_CONTABLE': 'codigo',
        'VALOR': 'valor',
        'ESTRUCTURA': 'estructura',
        'TIPO': 'tipo',
        'GRUPO': 'grupo',
    }

    df_completo = df_completo.rename(columns={k: v for k, v in column_mapping.items() if k in df_completo.columns})

    # Convertir fecha
    if 'fecha' in df_completo.columns:
        df_completo['fecha'] = pd.to_datetime(df_completo['fecha'], errors='coerce')

    # Convertir valor a numérico
    if 'valor' in df_completo.columns:
        df_completo['valor'] = pd.to_numeric(df_completo['valor'], errors='coerce')

    # Filtrar solo cuentas de PyG (códigos 4, 5) e indicadores
    print("\nSeparando datos por tipo...")

    # PyG: cuentas que empiezan con 4 o 5
    if 'codigo' in df_completo.columns:
        df_completo['codigo_str'] = df_completo['codigo'].astype(str)
        mask_pyg = df_completo['codigo_str'].str.match(r'^[45]')
        df_pyg = df_completo[mask_pyg].copy()
        print(f"  Registros PyG (cuentas 4,5): {len(df_pyg):,}")
    else:
        df_pyg = pd.DataFrame()

    # Guardar datos
    print("\n" + "=" * 70)
    print("GUARDANDO ARCHIVOS")
    print("=" * 70)

    MASTER_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Guardar únicamente el staging raw. procesar_pyg.py lo fusiona con el
    # histórico publicado; nunca se debe sobrescribir pyg.parquet desde aquí.
    indicadores_path = MASTER_DATA_DIR / "indicadores_raw.parquet"
    guardar_parquet_atomico(df_completo, indicadores_path, index=False)
    size_mb = indicadores_path.stat().st_size / (1024 * 1024)
    print(f"  indicadores_raw.parquet: {len(df_completo):,} registros, {size_mb:.2f} MB")

    # Metadata
    metadata = {
        'fecha_procesamiento': datetime.now().isoformat(),
        'archivos_procesados': [z.name for z in archivos_zip],
        'registros_totales': len(df_completo),
        'registros_pyg': len(df_pyg) if not df_pyg.empty else 0,
        'fechas': {
            'min': str(df_completo['fecha'].min()) if 'fecha' in df_completo.columns else None,
            'max': str(df_completo['fecha'].max()) if 'fecha' in df_completo.columns else None,
        },
        'segmentos': df_completo['segmento'].unique().tolist() if 'segmento' in df_completo.columns else [],
        'cooperativas': df_completo['cooperativa'].nunique() if 'cooperativa' in df_completo.columns else 0,
    }

    with open(MASTER_DATA_DIR / "metadata_indicadores.json", 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False, default=str)

    print("\n[OK] Procesamiento completado")
    print(f"  Cooperativas: {metadata['cooperativas']}")
    print(f"  Período: {metadata['fechas']['min']} - {metadata['fechas']['max']}")


if __name__ == "__main__":
    procesar_todos_indicadores()
