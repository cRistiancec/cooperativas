# -*- coding: utf-8 -*-
"""
Procesa datos de PyG (Pérdidas y Ganancias) de cooperativas.

Lógica especial:
- Los datos son acumulados mes a mes dentro de cada año
- Se desacumulan para obtener el valor de cada mes individual
- Se calcula suma móvil de 12 meses para comparabilidad

Basado en: scripts/procesar_pyg.py de bancos
"""

import pandas as pd
import numpy as np
from pathlib import Path
import warnings

try:
    from io_atomico import guardar_parquet_atomico
except ModuleNotFoundError:
    from scripts.io_atomico import guardar_parquet_atomico

warnings.filterwarnings('ignore')

# Rutas
BASE_DIR = Path(__file__).parent.parent
MASTER_DATA_DIR = BASE_DIR / "master_data"

# Códigos de cuentas principales de PyG para cooperativas
CUENTAS_RESUMEN = {
    # Ingresos (cuenta 5)
    '5': 'INGRESOS',
    '51': 'INTERESES Y DESCUENTOS GANADOS',
    '52': 'COMISIONES GANADAS',
    '53': 'UTILIDADES FINANCIERAS',
    '54': 'INGRESOS POR SERVICIOS',
    '55': 'OTROS INGRESOS OPERACIONALES',
    '56': 'OTROS INGRESOS',
    # Gastos (cuenta 4)
    '4': 'GASTOS',
    '41': 'INTERESES CAUSADOS',
    '42': 'COMISIONES CAUSADAS',
    '43': 'PERDIDAS FINANCIERAS',
    '44': 'PROVISIONES',
    '45': 'GASTOS DE OPERACION',
    '46': 'OTRAS PERDIDAS OPERACIONALES',
    '47': 'OTROS GASTOS Y PERDIDAS',
    '48': 'IMPUESTOS Y PARTICIPACION A EMPLEADOS',
}


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


def normalizar_nombre_cooperativa(nombre: str) -> str:
    """
    Normaliza el nombre de la cooperativa para evitar duplicados.
    - Unifica nombres de mutualistas al nombre canónico
    - Unifica LIMITADA -> LTDA
    - Elimina puntos al final
    - Normaliza espacios
    """
    if pd.isna(nombre):
        return nombre

    nombre = str(nombre).strip()

    # Normalizar mutualistas primero (antes de otras transformaciones)
    if nombre in MUTUALISTAS_NOMBRES:
        return MUTUALISTAS_NOMBRES[nombre]

    # Unificar LIMITADA a LTDA
    nombre = nombre.replace(' LIMITADA', ' LTDA')

    # Eliminar punto al final de LTDA.
    if nombre.endswith('LTDA.'):
        nombre = nombre[:-1]

    # Eliminar espacios múltiples
    nombre = ' '.join(nombre.split())

    return nombre


def combinar_historico_pyg(
    df_fuente: pd.DataFrame,
    output_path: Path,
) -> pd.DataFrame:
    """Reemplaza solo los meses presentes en la fuente y conserva el resto."""
    if not output_path.exists():
        return df_fuente.copy()

    df_historico_completo = pd.read_parquet(output_path)
    columnas = [
        'fecha', 'segmento', 'cooperativa', 'codigo', 'cuenta',
        'valor_acumulado',
    ]
    faltantes = [col for col in columnas if col not in df_historico_completo.columns]
    if faltantes:
        raise ValueError(
            "pyg.parquet histórico no tiene las columnas requeridas: "
            + ", ".join(faltantes)
        )

    # segmento_historico: igual patrón usado en procesar_balance_cooperativas.py
    # y procesar_camel.py (ver docs/RIESGO_METODOLOGIA.md §18). Si el parquet
    # existente todavía no tiene la columna, se backfillea como ESTIMADO
    # (= segmento last-known, no point-in-time real) en vez de fingir una
    # precisión que no existe. Corridas futuras, sobre un pyg.parquet que ya
    # incluye la columna, preservan el valor real que ya tenían.
    if 'segmento_historico' not in df_historico_completo.columns:
        print("  [segmento_historico] Columna ausente en el parquet existente — "
              "backfill como ESTIMADO (= segmento last-known, no point-in-time real).")
        df_historico_completo['segmento_historico'] = df_historico_completo['segmento']
        df_historico_completo['segmento_historico_estimado'] = True
    columnas = columnas + ['segmento_historico', 'segmento_historico_estimado']

    df_historico = df_historico_completo[columnas].rename(
        columns={'valor_acumulado': 'valor'}
    )
    df_historico['ruc'] = pd.NA
    df_historico['fecha'] = pd.to_datetime(df_historico['fecha'])

    df_fuente = df_fuente.copy()
    df_fuente['fecha'] = pd.to_datetime(df_fuente['fecha'])
    # Defensivo: si quien llama a esta función no adjuntó segmento_historico
    # (p. ej. una prueba unitaria que ejercita el merge en aislamiento, o un
    # futuro caller que no siga el flujo de procesar_pyg()), se backfillea
    # igual que se hace arriba para el histórico — nunca se asume que el
    # llamador cumplió el contrato sin verificarlo.
    if 'segmento_historico' not in df_fuente.columns:
        df_fuente['segmento_historico'] = df_fuente['segmento']
        df_fuente['segmento_historico_estimado'] = True
    fechas_reemplazo = df_fuente['fecha'].dropna().unique()
    df_historico = df_historico[
        ~df_historico['fecha'].isin(fechas_reemplazo)
    ]

    for col in ['segmento', 'cooperativa', 'codigo', 'cuenta', 'segmento_historico']:
        df_historico[col] = df_historico[col].astype('object')
        df_fuente[col] = df_fuente[col].astype('object')

    print(
        "  Histórico PyG conservado: "
        f"{len(df_historico):,} registros anteriores a los meses reemplazados"
    )
    return pd.concat([df_historico, df_fuente], ignore_index=True)


def desacumular_valores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Desacumula los valores para obtener el valor de cada mes individual.

    Lógica:
    - Enero: valor_mes = valor_acumulado (primer mes del año)
    - Feb-Dic: valor_mes = valor_acumulado - valor_acumulado_mes_anterior
    """
    if df.empty:
        return df

    df = df.sort_values(['cooperativa', 'codigo', 'fecha']).copy()
    df['ano'] = df['fecha'].dt.year
    df['mes'] = df['fecha'].dt.month

    # Renombrar 'valor' a 'valor_acumulado' para claridad
    df = df.rename(columns={'valor': 'valor_acumulado'})

    # Calcular valor del mes anterior (dentro del mismo cooperativa, código y año)
    df['valor_anterior'] = df.groupby(['cooperativa', 'codigo', 'ano'])['valor_acumulado'].shift(1)

    # Desacumular: para enero (mes=1) o si no hay anterior, usar valor acumulado directamente
    # Para otros meses, restar el valor anterior
    df['valor_mes'] = np.where(
        (df['mes'] == 1) | (df['valor_anterior'].isna()),
        df['valor_acumulado'],
        df['valor_acumulado'] - df['valor_anterior']
    )

    return df


def calcular_suma_movil_12m(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula la suma móvil de 12 meses para cada cooperativa/código.
    Esto permite comparar cualquier mes con cualquier otro.
    """
    if df.empty:
        return df

    df = df.sort_values(['cooperativa', 'codigo', 'fecha']).copy()

    # Calcular suma móvil de 12 meses
    df['valor_12m'] = df.groupby(['cooperativa', 'codigo'])['valor_mes'].transform(
        lambda x: x.rolling(window=12, min_periods=12).sum()
    )

    return df


def procesar_pyg():
    """Procesa el archivo pyg.parquet agregando desacumulación y suma móvil."""

    print("=" * 60)
    print("PROCESAMIENTO DE PYG (PÉRDIDAS Y GANANCIAS)")
    print("=" * 60)

    # Cargar datos originales desde indicadores_raw
    indicadores_path = MASTER_DATA_DIR / "indicadores_raw.parquet"
    if not indicadores_path.exists():
        raise FileNotFoundError(f"No se encontró {indicadores_path}")

    print(f"\nCargando: {indicadores_path}")
    df_ind = pd.read_parquet(indicadores_path)

    # Filtrar solo cuentas de PyG (4 y 5)
    df_ind['codigo'] = df_ind['codigo'].astype(str)
    df = df_ind[df_ind['codigo'].str.startswith(('4', '5'))].copy()
    if df.empty:
        raise RuntimeError("El staging de indicadores no contiene cuentas PyG 4 o 5")
    print(f"Registros PyG (cuentas 4 y 5): {len(df):,}")

    # Normalizar nombres de cooperativas
    print("\nNormalizando nombres de cooperativas...")
    coops_antes = df['cooperativa'].nunique()
    df['cooperativa'] = df['cooperativa'].apply(normalizar_nombre_cooperativa)
    coops_despues = df['cooperativa'].nunique()
    print(f"  Cooperativas antes: {coops_antes}")
    print(f"  Cooperativas después: {coops_despues}")
    print(f"  Duplicados unificados: {coops_antes - coops_despues}")

    # segmento_historico: el segmento tal como lo reportó la propia entidad en
    # ESTE mes (el archivo fuente que se está procesando ahora mismo), antes
    # de la unificación retroactiva de abajo. Mismo patrón que
    # procesar_balance_cooperativas.py / procesar_camel.py — ver
    # docs/RIESGO_METODOLOGIA.md §18.
    df['segmento_historico'] = df['segmento']
    df['segmento_historico_estimado'] = False

    # Seleccionar columnas necesarias antes de agrupar
    df = df[['fecha', 'segmento', 'ruc', 'cooperativa', 'codigo', 'cuenta', 'valor',
              'segmento_historico', 'segmento_historico_estimado']].copy()

    output_path = MASTER_DATA_DIR / "pyg.parquet"
    df = combinar_historico_pyg(df, output_path)

    # Agregar valores de cooperativas duplicadas (mismo fecha, codigo, cooperativa)
    # Usar reset_index para evitar problemas de memoria con categorías
    print("\nAgregando valores de cooperativas con nombres unificados...")
    df = df.groupby(['fecha', 'segmento', 'cooperativa', 'codigo', 'cuenta'], observed=True).agg({
        'valor': 'sum',
        'ruc': 'first',
        'segmento_historico': 'first',
        'segmento_historico_estimado': 'first',
    }).reset_index()
    print(f"Registros después de agregar: {len(df):,}")

    # segmento_actual: alias explícito del comportamiento legado de abajo
    # (segmento unificado retroactivamente al último conocido). La columna
    # `segmento` NO cambia de significado — se mantiene por compatibilidad
    # con el resto del código que ya la lee.
    print("\nUnificando segmentos...")
    ultimo_segmento = (
        df.sort_values('fecha')
        .drop_duplicates(subset=['cooperativa'], keep='last')[['cooperativa', 'segmento']]
        .set_index('cooperativa')['segmento']
    )
    coops_multi = df.groupby('cooperativa')['segmento'].nunique()
    coops_cambiaron = coops_multi[coops_multi > 1].index.tolist()
    if coops_cambiaron:
        print(f"  Cooperativas con cambio de segmento: {len(coops_cambiaron)} (unificando al último)")
    df['segmento'] = df['cooperativa'].map(ultimo_segmento)
    df['segmento_actual'] = df['segmento']

    pct_estimado = df['segmento_historico_estimado'].mean() * 100
    print(f"segmento_historico estimado (no point-in-time real): {pct_estimado:.1f}% de registros")

    # Estadísticas iniciales
    print(f"\nCooperativas: {df['cooperativa'].nunique()}")
    print(f"Fechas: {df['fecha'].min()} a {df['fecha'].max()}")
    print(f"Cuentas únicas: {df['codigo'].nunique()}")

    # Desacumular valores
    print("\n" + "-" * 40)
    print("Desacumulando valores mensuales...")
    df_desacumulado = desacumular_valores(df)
    print(f"Registros después de desacumular: {len(df_desacumulado):,}")

    # Calcular suma móvil de 12 meses
    print("\nCalculando suma móvil de 12 meses...")
    df_final = calcular_suma_movil_12m(df_desacumulado)

    # Seleccionar columnas finales (excluir ruc, no usado por la UI)
    columnas_finales = [
        'fecha', 'segmento', 'segmento_actual', 'segmento_historico', 'segmento_historico_estimado',
        'cooperativa', 'codigo', 'cuenta',
        'valor_acumulado', 'valor_mes', 'valor_12m'
    ]
    df_final = df_final[columnas_finales]

    # Optimizar tipos de datos para reducir memoria
    for col in ['segmento', 'segmento_actual', 'segmento_historico', 'cooperativa', 'codigo', 'cuenta']:
        df_final[col] = df_final[col].astype('category')
    df_final['segmento_historico_estimado'] = df_final['segmento_historico_estimado'].astype('bool')

    # Estadísticas finales
    print("\n" + "=" * 40)
    print("RESUMEN")
    print("=" * 40)
    print(f"Cooperativas: {df_final['cooperativa'].nunique()}")
    print(f"Fechas: {df_final['fecha'].nunique()}")
    print(f"Cuentas únicas: {df_final['codigo'].nunique()}")
    print(f"Registros totales: {len(df_final):,}")

    # Verificar suma móvil
    registros_con_12m = df_final['valor_12m'].notna().sum()
    print(f"\nRegistros con valor_12m: {registros_con_12m:,} ({registros_con_12m/len(df_final)*100:.1f}%)")

    # Mostrar muestra de una cooperativa
    print("\n" + "-" * 40)
    print("Muestra de valores (primera cooperativa, código 5):")
    coop_ejemplo = df_final['cooperativa'].iloc[0]
    muestra = df_final[
        (df_final['cooperativa'] == coop_ejemplo) &
        (df_final['codigo'] == '5')
    ][['fecha', 'cooperativa', 'valor_acumulado', 'valor_mes', 'valor_12m']].head(15)
    print(muestra.to_string())

    # Guardar
    guardar_parquet_atomico(df_final, output_path, index=False)

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"\n[OK] Guardado: {output_path}")
    print(f"    Tamaño: {size_mb:.1f} MB")

    # Mostrar cuentas principales
    print("\n" + "-" * 40)
    print("Códigos de cuentas principales:")
    for codigo in sorted(df_final['codigo'].unique()):
        if len(codigo) <= 2:
            cuenta_nombre = df_final[df_final['codigo'] == codigo]['cuenta'].iloc[0]
            print(f"  {codigo}: {cuenta_nombre}")


if __name__ == "__main__":
    procesar_pyg()
