# -*- coding: utf-8 -*-
"""
Genera archivos parquet pre-agregados para consultas rápidas.
Esto reduce los 22.7M de registros a datasets pequeños optimizados.
"""

import pandas as pd
from pathlib import Path
import json
from datetime import datetime

try:
    from io_atomico import guardar_parquet_atomico
except ModuleNotFoundError:
    from scripts.io_atomico import guardar_parquet_atomico

# Rutas
MASTER_DATA_DIR = Path(__file__).parent.parent / "master_data"
BALANCE_PATH = MASTER_DATA_DIR / "balance.parquet"

def main():
    print("=" * 60)
    print("GENERADOR DE DATOS PRE-AGREGADOS")
    print("=" * 60)

    # Cargar datos completos
    print("\n[1/5] Cargando balance.parquet...")
    df = pd.read_parquet(BALANCE_PATH)
    print(f"    Registros cargados: {len(df):,}")

    # Códigos importantes para pre-agregar
    codigos_principales = ['1', '11', '13', '14', '2', '21', '26', '3', '31']

    # =========================================================================
    # AGREGADO 1: Métricas por fecha/segmento (para KPIs)
    # =========================================================================
    print("\n[2/5] Generando métricas agregadas por fecha/segmento...")

    df_codigos = df[df['codigo'].isin(codigos_principales)]

    metricas_sistema = df_codigos.groupby(
        ['fecha', 'segmento', 'codigo'],
        observed=True,
    ).agg(
        valor_total=('valor', 'sum'),
        num_cooperativas=('cooperativa', 'nunique')
    ).reset_index()

    # Guardar
    guardar_parquet_atomico(metricas_sistema, MASTER_DATA_DIR / "agg_metricas_sistema.parquet", index=False)
    print(f"    agg_metricas_sistema.parquet: {len(metricas_sistema):,} registros")

    # =========================================================================
    # AGREGADO 2: Ranking por cooperativa/fecha (para treemaps y rankings)
    # =========================================================================
    print("\n[3/5] Generando rankings por cooperativa/fecha...")

    ranking_cooperativas = df_codigos.groupby(
        ['fecha', 'segmento', 'cooperativa', 'codigo'],
        observed=True,
    ).agg(
        valor=('valor', 'sum')
    ).reset_index()

    # Guardar
    guardar_parquet_atomico(ranking_cooperativas, MASTER_DATA_DIR / "agg_ranking_cooperativas.parquet", index=False)
    print(f"    agg_ranking_cooperativas.parquet: {len(ranking_cooperativas):,} registros")

    # =========================================================================
    # AGREGADO 3: Series temporales por cooperativa (para gráficos de evolución)
    # =========================================================================
    print("\n[4/5] Generando series temporales...")

    # Solo códigos nivel 1 y 2 para series temporales
    codigos_serie = ['1', '11', '13', '14', '2', '21', '26', '3']
    df_serie = df[df['codigo'].isin(codigos_serie)]

    series_temporales = df_serie.groupby(
        ['fecha', 'cooperativa', 'segmento', 'codigo', 'cuenta'],
        observed=True,
    ).agg(
        valor=('valor', 'sum')
    ).reset_index()

    guardar_parquet_atomico(series_temporales, MASTER_DATA_DIR / "agg_series_temporales.parquet", index=False)
    print(f"    agg_series_temporales.parquet: {len(series_temporales):,} registros")

    # =========================================================================
    # AGREGADO 4: Lista de cooperativas con metadatos
    # =========================================================================
    print("\n[5/5] Generando catálogo de cooperativas...")

    # Usar la fecha más reciente disponible para CADA cooperativa
    # (algunas cooperativas pueden no reportar en el último mes global)
    df_activos = df[df['codigo'] == '1'].copy()

    # Para cada cooperativa, tomar el registro con la fecha más reciente
    idx_ultimo = df_activos.groupby('cooperativa', observed=True)['fecha'].idxmax()
    df_ultima = df_activos.loc[idx_ultimo]

    catalogo = df_ultima[['cooperativa', 'segmento', 'valor']].copy()
    catalogo = catalogo.rename(columns={'valor': 'activos_ultimo'})
    catalogo = catalogo.sort_values('activos_ultimo', ascending=False).reset_index(drop=True)
    catalogo['ranking'] = range(1, len(catalogo) + 1)

    guardar_parquet_atomico(catalogo, MASTER_DATA_DIR / "agg_catalogo_cooperativas.parquet", index=False)
    print(f"    agg_catalogo_cooperativas.parquet: {len(catalogo):,} registros")

    # =========================================================================
    # METADATA
    # =========================================================================
    metadata = {
        'fecha_generacion': datetime.now().isoformat(),
        'archivos_generados': [
            'agg_metricas_sistema.parquet',
            'agg_ranking_cooperativas.parquet',
            'agg_series_temporales.parquet',
            'agg_catalogo_cooperativas.parquet'
        ],
        'registros_originales': len(df),
        'fechas': {
            'min': str(df['fecha'].min()),
            'max': str(df['fecha'].max())
        }
    }

    with open(MASTER_DATA_DIR / "metadata_agregados.json", 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    # Resumen de tamaños
    print("\n" + "=" * 60)
    print("RESUMEN DE ARCHIVOS GENERADOS")
    print("=" * 60)

    archivos = [
        ("balance.parquet (original)", BALANCE_PATH),
        ("agg_metricas_sistema.parquet", MASTER_DATA_DIR / "agg_metricas_sistema.parquet"),
        ("agg_ranking_cooperativas.parquet", MASTER_DATA_DIR / "agg_ranking_cooperativas.parquet"),
        ("agg_series_temporales.parquet", MASTER_DATA_DIR / "agg_series_temporales.parquet"),
        ("agg_catalogo_cooperativas.parquet", MASTER_DATA_DIR / "agg_catalogo_cooperativas.parquet"),
    ]

    for nombre, ruta in archivos:
        size_mb = ruta.stat().st_size / (1024 * 1024)
        print(f"  {nombre}: {size_mb:.2f} MB")

    print("\nAgregados generados exitosamente.")
    print("  Los archivos pre-agregados acelerarán las consultas de la app.")


if __name__ == "__main__":
    main()
