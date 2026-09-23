# -*- coding: utf-8 -*-
"""
Procesa los archivos XLSM de cooperativas para extraer indicadores financieros
(CAMEL) desde los pivotCacheRecords de la hoja "5. INDICADORES FINANCIEROS".

Los indicadores vienen pre-calculados por la Superintendencia en tablas dinámicas.
Este script extrae los datos crudos del pivot cache y los normaliza en formato long.

Salida: master_data/indicadores.parquet
Schema: cooperativa, segmento, fecha, codigo, indicador, valor, categoria
"""

import zipfile
import xml.etree.ElementTree as ET
import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple, Optional
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

# Campos marcadores para identificar el cache de indicadores
MARKER_FIELDS = {'I28_ROE', 'I29_ROA', 'I1_suficiencia_patrimonial'}

# =============================================================================
# MAPEO DE INDICADORES
# Campo del pivot cache -> (codigo, nombre_display, categoria_CAMEL)
# =============================================================================

INDICADORES_MAP = {
    # C - Capital (Suficiencia Patrimonial)
    'I1_suficiencia_patrimonial': ('SUF_PAT', '(Patrimonio + Resultados) / Activos Inmovilizados', 'C - Capital'),

    # A - Calidad de Activos
    'I2_prop_act_impr_net': ('ACT_IMPR', 'Activos Improductivos Netos / Total Activos', 'A - Calidad de Activos'),
    'I3_prop_act_prod_net': ('ACT_PROD', 'Activos Productivos / Total Activos', 'A - Calidad de Activos'),
    'I4_uti_pas_cost_prod_gene': ('AP_PC', 'Activos Productivos / Pasivos con Costo', 'A - Calidad de Activos'),

    # A - Morosidad
    'I5_Moros_carte': ('MOR_TOT', 'Morosidad Total', 'A - Morosidad'),
    'Moros_carte_consu': ('MOR_CONS', 'Morosidad Consumo', 'A - Morosidad'),
    'I8_Moros_carte_inmob': ('MOR_INMOB', 'Morosidad Inmobiliaria', 'A - Morosidad'),
    'I9_Moros_carte_micro': ('MOR_MICRO', 'Morosidad Microcrédito', 'A - Morosidad'),
    'I10_Moros_carte_produ': ('MOR_PROD', 'Morosidad Productivo', 'A - Morosidad'),
    'I13_Moros_carte_vivi_ip': ('MOR_VIV_IP', 'Morosidad Vivienda Interés Público', 'A - Morosidad'),
    'I14_Moros_carte_educ': ('MOR_EDU', 'Morosidad Educativo', 'A - Morosidad'),

    # A - Cobertura
    'I15_Cober_carte': ('COB_TOT', 'Cobertura Total', 'A - Cobertura'),
    'Cober_carte_consu': ('COB_CONS', 'Cobertura Consumo', 'A - Cobertura'),
    'I18_Cober_carte_inmob': ('COB_INMOB', 'Cobertura Inmobiliaria', 'A - Cobertura'),
    'I19_Cober_carte_micro': ('COB_MICRO', 'Cobertura Microcrédito', 'A - Cobertura'),
    'I20_Cober_carte_produ': ('COB_PROD', 'Cobertura Productivo', 'A - Cobertura'),
    'I23_Cober_carte_vivi_ip': ('COB_VIV_IP', 'Cobertura Vivienda Interés Público', 'A - Cobertura'),
    'I24_Cober_carte_educ': ('COB_EDU', 'Cobertura Educativo', 'A - Cobertura'),

    # M - Management (Eficiencia)
    'I25_Efici_opera': ('GO_ACT', 'Gastos Operación / Activo Promedio', 'M - Management'),
    'I26_Grad_abso': ('GO_MNF', 'Gastos Operación / Margen Financiero', 'M - Management'),
    'I27_Efic_adm_pers': ('GP_ACT', 'Gastos Personal / Activo Promedio', 'M - Management'),

    # E - Earnings (Rentabilidad)
    'I28_ROE': ('ROE', 'ROE', 'E - Earnings'),
    'I29_ROA': ('ROA', 'ROA', 'E - Earnings'),

    # Intermediación / Eficiencia Financiera
    'I30_Interm_fin': ('INTERM', 'Intermediación Financiera', 'E - Earnings'),
    'I31_Marg_inter_est_patri': ('MARG_PAT', 'Margen Intermediación / Patrimonio', 'E - Earnings'),
    'I32_Marg_inter_est_activ': ('MARG_ACT', 'Margen Intermediación / Activo', 'E - Earnings'),

    # Rendimiento de Cartera
    'I34_Rend_cart_consu_x_venc': ('REND_CONS', 'Rendimiento Cartera Consumo', 'E - Earnings'),
    'I35_Rend_cart_inmob_x_venc': ('REND_INMOB', 'Rendimiento Cartera Inmobiliaria', 'E - Earnings'),
    'I36_Rend_cart_micro_x_venc': ('REND_MICRO', 'Rendimiento Cartera Microcrédito', 'E - Earnings'),
    'I37_Rend_cart_prod_x_venc': ('REND_PROD', 'Rendimiento Cartera Productivo', 'E - Earnings'),
    'I40_Rend_cart_vivie_x_venc': ('REND_VIV', 'Rendimiento Cartera Vivienda IP', 'E - Earnings'),
    'I41_Rend_cart_educ_x_venc': ('REND_EDU', 'Rendimiento Cartera Educativo', 'E - Earnings'),

    # Cartera (Refinanciada, Reestructurada, Por Vencer)
    'I42_Cart_cred_ref_xven': ('CART_REF', 'Carteras de Créditos Refinanciadas', 'A - Calidad de Activos'),
    'I43_Cart_cred_reest': ('CART_REEST', 'Carteras de Créditos Reestructuradas', 'A - Calidad de Activos'),
    'I44_cartera_x_vencer': ('CART_VENCER', 'Cartera por Vencer Total', 'A - Calidad de Activos'),

    # L - Liquidez
    'I45_Fond_dis_sob_total_depo_cort_plz': ('LIQ', 'Fondos Disponibles / Depósitos CP', 'L - Liquidez'),

    # V - Vulnerabilidad del Patrimonio
    'I46_Carte_impro_descu_rela_patri_resul': ('VULN_PAT', 'Cart. Improd. Descubierta / Patrimonio', 'V - Vulnerabilidad'),
    'I47_Carte_impr_patri_dic': ('CART_IMPR_PAT', 'Cartera Improductiva / Patrimonio', 'V - Vulnerabilidad'),
    'I48_FK': ('FK', 'FK', 'V - Vulnerabilidad'),
    'I49_FI': ('FI', 'FI', 'V - Vulnerabilidad'),
    'I50_Indi_capi_neto': ('CAP_NETO', 'Índice Capitalización Neto', 'V - Vulnerabilidad'),
}


# =============================================================================
# FUNCIONES DE PARSEO XML (reutilizadas de procesar_indicadores.py)
# =============================================================================

def extraer_lookup_tables(zip_file: zipfile.ZipFile, cache_def_path: str) -> Tuple[List[str], Dict[str, List]]:
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
                    tag = item.tag.split('}')[-1]
                    if tag == 's':
                        values.append(item.attrib.get('v', ''))
                    elif tag == 'd':
                        values.append(item.attrib.get('v', ''))
                    elif tag == 'n':
                        values.append(float(item.attrib.get('v', 0)))
                    elif tag == 'm':
                        values.append(None)
                    elif tag == 'e':
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
                elif tag == 's':
                    fila[field_name] = item.attrib.get('v', '')
                elif tag == 'n':
                    fila[field_name] = float(item.attrib.get('v', 0))
                elif tag == 'm':
                    fila[field_name] = None
                elif tag == 'd':
                    fila[field_name] = item.attrib.get('v', '')
                else:
                    fila[field_name] = item.attrib.get('v', '')

            registros.append(fila)

    return pd.DataFrame(registros)


# =============================================================================
# FUNCIONES ESPECIFICAS PARA INDICADORES
# =============================================================================

def encontrar_cache_indicadores(zip_file: zipfile.ZipFile) -> Tuple[Optional[str], Optional[str]]:
    """
    Encuentra el pivot cache que contiene indicadores financieros.

    El número de cache varía entre años (cache4 en 2020/2022/2024/2025,
    cache3 en 2021/2023), así que inspeccionamos los nombres de campos
    en cada cache buscando marcadores como I28_ROE.
    """
    cache_defs = sorted([
        n for n in zip_file.namelist()
        if 'pivotCacheDefinition' in n and n.endswith('.xml') and '_rels' not in n
    ])

    for def_path in cache_defs:
        try:
            with zip_file.open(def_path) as f:
                content = f.read().decode('utf-8')
                root = ET.fromstring(content)

            field_names_in_cache = set()
            for field in root.findall('.//main:cacheField', NS):
                field_names_in_cache.add(field.get('name'))

            # Si al menos 2 campos marcadores están presentes, es el cache correcto
            if len(MARKER_FIELDS & field_names_in_cache) >= 2:
                cache_num = re.search(r'pivotCacheDefinition(\d+)\.xml', def_path)
                if cache_num:
                    records_path = f'xl/pivotCache/pivotCacheRecords{cache_num.group(1)}.xml'
                    if records_path in zip_file.namelist():
                        return def_path, records_path
        except Exception:
            continue

    return None, None


# Correcciones de nombres para alinear indicadores con balance
CORRECCIONES_NOMBRE = {
    'ALFONSO JARAMILLO LEON CCC': 'ALFONSO JARAMILLO LEON CAJA',
    'FERNANDO DAQUILEMA': 'FERNANDO DAQUILEMA LTDA',
    'VISION DE LOS ANDES VISANDES': 'VISION DE LOS ANDES VIS ANDES',
    'EDUCADORES DE LOJA LTDA': 'EDUCADORES DE LOJA - CACEL LTDA',
    'SUMAK SISA': 'SISA',
    'DE LA PEQUENA EMPRESA CACPE ZAMORA LTDA': 'DE LA PEQUEÑA EMPRESA CACPE ZAMORA CHINCHIPE LTDA',
    'CAMARA DE COMERCIO DE SANTO DOMINGO EN LIQUIDACION': 'CAMARA DE COMERCIO DE SANTO DOMINGO',
    'PARA LA VIVIENDA ORDEN Y SEGURIDAD': 'ORDEN Y SEGURIDAD "OYS"',
}

# Nombres canónicos de mutualistas (nombre corto en pivot cache → nombre canónico)
MUTUALISTAS_NOMBRES = {
    'AMBATO':    'Mutualista Ambato',
    'AZUAY':     'Mutualista Azuay',
    'IMBABURA':  'Mutualista Imbabura',
    'PICHINCHA': 'Mutualista Pichincha',
}
MUTUALISTAS = set(MUTUALISTAS_NOMBRES.keys())


def normalizar_nombre(nombre: str) -> str:
    """Normaliza el nombre de la cooperativa para alinear con balance.parquet."""
    if pd.isna(nombre):
        return ""
    nombre = str(nombre).strip()
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

    # Aplicar correcciones de nombre conocidas
    if nombre in CORRECCIONES_NOMBRE:
        nombre = CORRECCIONES_NOMBRE[nombre]

    return nombre


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


def procesar_xlsm_indicadores(xlsm_data: bytes, segmento: str) -> pd.DataFrame:
    """Extrae indicadores financieros de un XLSM desde su pivotCache."""
    try:
        with zipfile.ZipFile(io.BytesIO(xlsm_data), 'r') as z:
            def_path, records_path = encontrar_cache_indicadores(z)

            if not def_path or not records_path:
                print(f"    [!] No se encontró cache de indicadores")
                return pd.DataFrame()

            field_names, field_values = extraer_lookup_tables(z, def_path)
            df = parsear_cache_records(z, records_path, field_names, field_values)

            if df.empty:
                print(f"    [!] Cache vacío")
                return pd.DataFrame()

            # Identificar qué columnas de indicadores existen en este cache
            indicator_cols = [col for col in df.columns if col in INDICADORES_MAP]

            if not indicator_cols:
                print(f"    [!] No se encontraron columnas de indicadores")
                return pd.DataFrame()

            # Filtrar filas VT_TOTAL (totales del sistema)
            if 'NOM_RAZON_SOCIAL' in df.columns:
                df = df[~df['NOM_RAZON_SOCIAL'].astype(str).str.contains('VT_TOTAL', na=False)]

            # Normalizar nombre de cooperativa
            if 'NOM_RAZON_SOCIAL' in df.columns:
                df['cooperativa'] = df['NOM_RAZON_SOCIAL'].apply(normalizar_nombre)
            else:
                print(f"    [!] No se encontró columna NOM_RAZON_SOCIAL")
                return pd.DataFrame()

            # Parsear fecha
            if 'FEC_CORTE' in df.columns:
                df['fecha'] = pd.to_datetime(df['FEC_CORTE'], errors='coerce')
            else:
                print(f"    [!] No se encontró columna FEC_CORTE")
                return pd.DataFrame()

            # Segmento desde los datos o fallback
            if 'SEGMENTO' in df.columns and not df['SEGMENTO'].isna().all():
                df['segmento'] = df['SEGMENTO']
            else:
                df['segmento'] = segmento

            # Normalizar nombres de mutualistas al nombre canónico
            mask_mutualista = (
                df['cooperativa'].isin(MUTUALISTAS) &
                (df['segmento'].str.contains('MUTUALISTA', na=False))
            )
            df.loc[mask_mutualista, 'cooperativa'] = (
                df.loc[mask_mutualista, 'cooperativa'].map(MUTUALISTAS_NOMBRES)
            )

            # Melt de wide a long
            id_vars = ['cooperativa', 'segmento', 'fecha']
            df_melted = df.melt(
                id_vars=id_vars,
                value_vars=indicator_cols,
                var_name='campo_original',
                value_name='valor'
            )

            # Mapear a códigos normalizados
            df_melted['codigo'] = df_melted['campo_original'].map(
                lambda x: INDICADORES_MAP[x][0]
            )
            df_melted['indicador'] = df_melted['campo_original'].map(
                lambda x: INDICADORES_MAP[x][1]
            )
            df_melted['categoria'] = df_melted['campo_original'].map(
                lambda x: INDICADORES_MAP[x][2]
            )

            # Convertir valor a numérico
            df_melted['valor'] = pd.to_numeric(df_melted['valor'], errors='coerce')

            # Eliminar nulos
            df_melted = df_melted.dropna(subset=['valor', 'fecha'])

            # segmento_historico: valor point-in-time tal como lo reportó la
            # entidad en este boletín, antes de la unificación posterior
            # (ver combinar_historico_camel/procesar_todos_indicadores).
            df_melted['segmento_historico'] = df_melted['segmento']
            df_melted['segmento_historico_estimado'] = False

            # Seleccionar columnas finales
            df_final = df_melted[[
                'cooperativa', 'segmento', 'fecha', 'codigo', 'indicador', 'valor', 'categoria',
                'segmento_historico', 'segmento_historico_estimado',
            ]]

            print(f"    [OK] {len(df_final):,} registros de indicadores")
            return df_final

    except Exception as e:
        print(f"    [ERROR] {e}")
        return pd.DataFrame()


# =============================================================================
# PROCESAMIENTO PRINCIPAL
# =============================================================================


def combinar_historico_camel(
    df_fuente: pd.DataFrame,
    output_path: Path,
) -> pd.DataFrame:
    """Reemplaza los meses del ZIP actual sin perder años anteriores."""
    if not output_path.exists():
        return df_fuente.copy()

    df_historico = pd.read_parquet(output_path)
    columnas = [
        'cooperativa', 'segmento', 'fecha', 'codigo',
        'indicador', 'valor', 'categoria',
    ]
    faltantes = [col for col in columnas if col not in df_historico.columns]
    if faltantes:
        raise ValueError(
            "indicadores.parquet histórico no tiene las columnas requeridas: "
            + ", ".join(faltantes)
        )

    # segmento_historico: backfill para parquets generados antes de que esta
    # columna existiera. Igual criterio que balance.parquet — se marca como
    # ESTIMADO (no point-in-time real) en vez de fingir precisión histórica
    # que no se puede reconstruir sin reprocesar los ZIP originales.
    if 'segmento_historico' not in df_historico.columns:
        df_historico['segmento_historico'] = df_historico['segmento']
        df_historico['segmento_historico_estimado'] = True
    columnas = columnas + ['segmento_historico', 'segmento_historico_estimado']

    df_historico = df_historico[columnas].copy()
    df_historico['fecha'] = pd.to_datetime(df_historico['fecha'])
    df_fuente = df_fuente.copy()
    df_fuente['fecha'] = pd.to_datetime(df_fuente['fecha'])

    fechas_reemplazo = df_fuente['fecha'].dropna().unique()
    df_historico = df_historico[
        ~df_historico['fecha'].isin(fechas_reemplazo)
    ]
    print(
        "Histórico CAMEL conservado: "
        f"{len(df_historico):,} registros anteriores a los meses reemplazados"
    )
    return pd.concat([df_historico, df_fuente], ignore_index=True)

def procesar_todos_indicadores():
    """Procesa todos los archivos ZIP para extraer indicadores CAMEL."""
    print("=" * 70)
    print("PROCESAMIENTO DE INDICADORES CAMEL (COOPERATIVAS)")
    print("=" * 70)

    todos_los_datos = []
    output_path = MASTER_DATA_DIR / "indicadores.parquet"
    archivos_zip = seleccionar_zips_procesamiento(
        INDICADORES_DIR.glob("*.zip"),
        incremental=output_path.exists(),
    )

    print(f"\nArchivos ZIP encontrados: {len(archivos_zip)}")
    if output_path.exists():
        print("  Modo incremental: procesando únicamente el año más reciente")

    for zip_path in archivos_zip:
        print(f"\n[{zip_path.name}]")

        try:
            with zipfile.ZipFile(zip_path, 'r') as main_zip:
                xlsm_files = [n for n in main_zip.namelist() if n.endswith('.xlsm')]
                print(f"  Archivos XLSM: {len(xlsm_files)}")

                for xlsm_name in xlsm_files:
                    filename = Path(xlsm_name).name

                    if es_archivo_ignorar(filename):
                        print(f"  Ignorando: {filename}")
                        continue

                    print(f"  Procesando: {filename}")

                    segmento = detectar_segmento(xlsm_name)
                    xlsm_data = main_zip.read(xlsm_name)
                    df = procesar_xlsm_indicadores(xlsm_data, segmento)

                    if not df.empty:
                        todos_los_datos.append(df)

        except Exception as e:
            print(f"  [ERROR] Error procesando ZIP: {e}")

    if not todos_los_datos:
        raise RuntimeError("No se extrajeron indicadores CAMEL de los ZIP")

    # Consolidar
    print("\n" + "=" * 70)
    print("CONSOLIDANDO DATOS")
    print("=" * 70)

    df_nuevo = pd.concat(todos_los_datos, ignore_index=True)
    MASTER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    df_completo = combinar_historico_camel(df_nuevo, output_path)
    print(f"Total registros consolidados: {len(df_completo):,}")

    # Unificar segmento: cada cooperativa toma el segmento de su último dato
    ultimo_segmento = (
        df_completo.sort_values('fecha')
        .drop_duplicates(subset=['cooperativa'], keep='last')[['cooperativa', 'segmento']]
        .set_index('cooperativa')['segmento']
    )
    coops_multi = df_completo.groupby('cooperativa')['segmento'].nunique()
    coops_cambiaron = coops_multi[coops_multi > 1].index.tolist()
    if coops_cambiaron:
        print(f"Cooperativas con cambio de segmento: {len(coops_cambiaron)} (unificando al ultimo)")
    df_completo['segmento'] = df_completo['cooperativa'].map(ultimo_segmento)
    df_completo['segmento_actual'] = df_completo['segmento']
    if 'segmento_historico' not in df_completo.columns:
        df_completo['segmento_historico'] = df_completo['segmento']
        df_completo['segmento_historico_estimado'] = True
    df_completo['segmento_historico'] = df_completo['segmento_historico'].where(
        df_completo['segmento_historico'].notna(), df_completo['segmento']
    )
    df_completo['segmento_historico_estimado'] = df_completo['segmento_historico_estimado'].fillna(True)

    # Deduplicar
    df_completo = df_completo.drop_duplicates(
        subset=['cooperativa', 'fecha', 'codigo'],
        keep='last'
    )
    print(f"Registros tras deduplicar: {len(df_completo):,}")

    # Guardar
    guardar_parquet_atomico(df_completo, output_path, index=False)
    size_mb = output_path.stat().st_size / (1024 * 1024)

    print(f"\n[OK] Guardado: {output_path}")
    print(f"  Tamaño: {size_mb:.2f} MB")
    print(f"  Registros: {len(df_completo):,}")
    print(f"  Cooperativas: {df_completo['cooperativa'].nunique()}")
    print(f"  Indicadores: {df_completo['codigo'].nunique()}")
    print(f"  Categorías: {df_completo['categoria'].unique().tolist()}")
    print(f"  Segmentos: {df_completo['segmento'].unique().tolist()}")
    print(f"  Período: {df_completo['fecha'].min()} - {df_completo['fecha'].max()}")


if __name__ == "__main__":
    procesar_todos_indicadores()
