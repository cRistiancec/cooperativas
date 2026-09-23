# -*- coding: utf-8 -*-
"""
Pipeline ETL — Solvencia oficial SEPS (Patrimonio Técnico / Formulario FS01).

Procesa el boletín "Patrimonio Técnico" que la SEPS publica en el mismo
portal que los Estados Financieros (`descargar_patrimonio_tecnico()` en
`descargar_datos_seps.py`), y que corresponde a las fichas 58-63 de
`Fichas-Metodologicas-de-Indicadores-Financieros_V3.0.pdf`:

  - Patrimonio Técnico Primario (PTP)
  - Patrimonio Técnico Secundario (PTS)
  - Patrimonio Técnico Constituido (PTC = PTP + PTS)
  - Activos y Contingentes Ponderados por Riesgo (APPR)
  - Solvencia = PTC / APPR  ← ratio de solvencia REGULATORIO (mínimo 9%)
  - Patrimonio Técnico Requerido (PTR) = APPR * 9%

LIMITACIÓN DE COBERTURA (verificada, no asumida): este boletín únicamente
cubre Segmento 1, Mutualistas y Caja Central FINANCOOP. La SEPS no publica
esta razón para Segmento 2 ni Segmento 3 — no es un defecto del pipeline,
es el alcance real de la regulación de solvencia ponderada por riesgo en
Ecuador. Ver docs/RIESGO_METODOLOGIA.md §3.2.

Este es un dataset INDEPENDIENTE de `indicadores.parquet` (identidad por
RUC, no solo por nombre; cobertura parcial del universo). No se fusiona
dentro de `indicadores.parquet` para no conflar un indicador de cobertura
parcial con el catálogo de indicadores oficiales de cobertura universal.

Salida: master_data/solvencia.parquet + master_data/metadata_solvencia.json
"""

from __future__ import annotations

import json
import re
import sys
import warnings
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

warnings.filterwarnings("ignore")

BASE_DIR = Path(__file__).parent.parent
PATRIMONIO_DIR = BASE_DIR / "patrimonio_tecnico"
OUTPUT_DIR = BASE_DIR / "master_data"
OUTPUT_PARQUET = OUTPUT_DIR / "solvencia.parquet"
OUTPUT_METADATA = OUTPUT_DIR / "metadata_solvencia.json"

sys.path.insert(0, str(Path(__file__).parent))
from procesar_balance_cooperativas import normalizar_nombre  # noqa: E402
from io_atomico import guardar_parquet_atomico  # noqa: E402

MESES_ES = {
    "ENE": 1, "FEB": 2, "MAR": 3, "ABR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AGO": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DIC": 12,
}
_PATRON_MES = re.compile(r"([A-Z]{3})_(\d{4})")

# Nombres de hoja que nunca son datos mensuales (portada, índice, metodología).
_HOJAS_IGNORAR = {"ÍNDICE", "INDICE", "NOTA MEDOLÓGICA", "NOTA METODOLÓGICA",
                   "CONTENIDO", "MENÚ", "MENU"}

COLUMNAS_DATO = [
    "ptp",       # A - Patrimonio Técnico Primario
    "pts",       # B - Patrimonio Técnico Secundario
    "ptc",       # C - Patrimonio Técnico Constituido (A+B)
    "appr",      # D - Activos y Contingentes Ponderados por Riesgo
    "solvencia", # E - Solvencia = C / D  (ratio, no %; 0.09 = 9%)
    "ptr_9pct",  # F - Patrimonio Técnico Requerido (9% de D)
]


def detectar_grupo_fuente(nombre_archivo: str) -> str:
    """
    Clasifica el archivo del boletín según su alcance regulatorio.

    Usa lookaround en vez de `\\b` porque varios nombres de archivo separan
    el token con guion bajo (p. ej. `..._S1_2020.xlsx`), y `_` cuenta como
    carácter de palabra en regex — `\\b` NO marca borde entre `_` y `s1`.
    """
    n = nombre_archivo.lower()
    if "financoop" in n:
        return "FINANCOOP"
    if "mutualista" in n or re.search(r"(?<![a-z0-9])mut(?![a-z0-9])", n):
        return "Mutualista"
    if "segmento 1" in n or re.search(r"(?<![a-z0-9])s1(?![a-z0-9])", n):
        return "Segmento 1"
    return "Sin clasificar"


def _extraer_mes_anio(nombre_hoja: str) -> Optional[tuple[int, int]]:
    """Busca un patrón MES_AAAA (p. ej. 'JUL_2026' o '3.7. JUL_2026') en el nombre de hoja."""
    m = _PATRON_MES.search(nombre_hoja.upper())
    if not m:
        return None
    mes_abr, anio_str = m.groups()
    mes = MESES_ES.get(mes_abr)
    if mes is None:
        return None
    return mes, int(anio_str)


def _es_hoja_de_datos(nombre_hoja: str) -> bool:
    if nombre_hoja.strip().upper() in _HOJAS_IGNORAR:
        return False
    return _extraer_mes_anio(nombre_hoja) is not None


def _localizar_fila_header(ws, max_filas_busqueda: int = 25) -> Optional[int]:
    """Devuelve el índice de fila (1-based) donde la celda contiene 'RUC'."""
    for i, row in enumerate(ws.iter_rows(min_row=1, max_row=max_filas_busqueda, values_only=True), start=1):
        for celda in row:
            if celda is not None and str(celda).strip().upper() == "RUC":
                return i
    return None


def leer_hoja_solvencia(ws, mes: int, anio: int, grupo_fuente: str, archivo_origen: str) -> pd.DataFrame:
    """Extrae la tabla No./RUC/RAZÓN SOCIAL/A-F de una hoja mensual."""
    fila_header = _localizar_fila_header(ws)
    if fila_header is None:
        return pd.DataFrame()

    fila_datos_inicio = fila_header + 2  # header + subheader de nombres largos
    registros = []
    for row in ws.iter_rows(min_row=fila_datos_inicio, values_only=True):
        ruc = row[1] if len(row) > 1 else None
        razon_social = row[2] if len(row) > 2 else None
        if ruc is None or razon_social is None:
            # Filas vacías intermedias son toleradas (algunas hojas tienen huecos);
            # dos filas vacías consecutivas cierran la tabla.
            continue
        ruc_str = str(ruc).strip()
        if not ruc_str or ruc_str.upper() in {"TOTAL", "TOTALES"}:
            continue
        valores = list(row[3:9]) + [None] * max(0, 6 - len(row[3:9]))
        registros.append({
            "ruc": ruc_str,
            "cooperativa_raw": str(razon_social).strip(),
            **dict(zip(COLUMNAS_DATO, [
                float(v) if isinstance(v, (int, float)) else None for v in valores
            ])),
        })

    if not registros:
        return pd.DataFrame()

    df = pd.DataFrame(registros)
    df["fecha"] = pd.Timestamp(year=anio, month=mes, day=1) + pd.offsets.MonthEnd(0)
    df["grupo_fuente"] = grupo_fuente
    df["archivo_origen"] = archivo_origen
    return df


def procesar_zip_anual(zip_path: Path) -> pd.DataFrame:
    """Procesa un ZIP anual del boletín de Patrimonio Técnico (todos sus archivos y hojas)."""
    import openpyxl

    frames = []
    with zipfile.ZipFile(zip_path) as zf:
        nombres_excel = [
            n for n in zf.namelist()
            if not n.startswith("__MACOSX") and n.lower().endswith((".xlsm", ".xlsx", ".xls"))
        ]
        for nombre in nombres_excel:
            grupo_fuente = detectar_grupo_fuente(Path(nombre).name)
            data = zf.read(nombre)
            import io
            try:
                wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True, read_only=True)
            except Exception as exc:  # noqa: BLE001
                print(f"    ADVERTENCIA: no se pudo abrir '{nombre}' dentro de {zip_path.name}: {exc}")
                continue

            for hoja_nombre in wb.sheetnames:
                if not _es_hoja_de_datos(hoja_nombre):
                    continue
                mes_anio = _extraer_mes_anio(hoja_nombre)
                if mes_anio is None:
                    continue
                mes, anio = mes_anio
                ws = wb[hoja_nombre]
                df_hoja = leer_hoja_solvencia(ws, mes, anio, grupo_fuente, Path(nombre).name)
                if not df_hoja.empty:
                    frames.append(df_hoja)
            wb.close()

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def generar_solvencia_parquet():
    """Genera/actualiza master_data/solvencia.parquet a partir de patrimonio_tecnico/*.zip."""
    print("=" * 60)
    print("PROCESANDO SOLVENCIA OFICIAL SEPS (Patrimonio Técnico / FS01)")
    print("=" * 60)

    if not PATRIMONIO_DIR.exists():
        print(f"  No existe {PATRIMONIO_DIR}. Nada que procesar (fuente opcional).")
        return

    zips = sorted(PATRIMONIO_DIR.glob("*-PAT.zip")) + sorted(PATRIMONIO_DIR.glob("*.zip"))
    zips = sorted(set(zips))
    if not zips:
        print(f"  No hay ZIPs en {PATRIMONIO_DIR}. Nada que procesar.")
        return

    frames = []
    archivos_procesados = []
    for zp in zips:
        print(f"\n[{zp.name}] Procesando...")
        try:
            df_anio = procesar_zip_anual(zp)
        except Exception as exc:  # noqa: BLE001 — fuente secundaria: un año corrupto no debe tumbar el resto
            print(f"  ADVERTENCIA: {zp.name} no se pudo procesar ({exc}). Se omite.")
            continue
        if df_anio.empty:
            print("  Sin registros extraídos.")
            continue
        print(f"  {len(df_anio)} registros, {df_anio['fecha'].nunique()} meses, "
              f"{df_anio['ruc'].nunique()} RUC únicos.")
        frames.append(df_anio)
        archivos_procesados.append(zp.name)

    if not frames:
        print("\nNingún ZIP produjo registros válidos. No se escribe salida.")
        return

    df = pd.concat(frames, ignore_index=True)

    # Normalización de nombre — reutiliza la MISMA función que balance/CAMEL
    # para que el nombre de cooperativa sea comparable entre datasets.
    df["cooperativa"] = df["cooperativa_raw"].apply(normalizar_nombre)

    # Regla de negocio verificada contra los datos (ficha 62): Solvencia = PTC/APPR.
    # Se recalcula como control de calidad; si difiere >0.5 pp del valor publicado
    # por la SEPS en la columna E, se conserva el valor oficial (E) pero se marca.
    with pd.option_context("mode.use_inf_as_na", True):
        solvencia_recalculada = df["ptc"] / df["appr"].replace(0, pd.NA)
    df["solvencia_recalculada_ptc_appr"] = solvencia_recalculada
    df["discrepancia_solvencia"] = (df["solvencia"] - df["solvencia_recalculada_ptc_appr"]).abs() > 0.005

    # Deduplicar por (ruc, fecha): si el mismo mes aparece en más de un ZIP
    # (años solapados por reprocesos), se conserva el último archivo procesado
    # (orden de `zips`, que ya es cronológico ascendente por nombre de archivo).
    columnas_finales = [
        "fecha", "ruc", "cooperativa", "cooperativa_raw", "grupo_fuente",
        "ptp", "pts", "ptc", "appr", "solvencia", "ptr_9pct",
        "solvencia_recalculada_ptc_appr", "discrepancia_solvencia", "archivo_origen",
    ]
    df = df[columnas_finales].drop_duplicates(subset=["ruc", "fecha"], keep="last")
    df = df.sort_values(["fecha", "ruc"]).reset_index(drop=True)

    # Dtypes compactos, coherentes con el resto del proyecto (category para texto repetido).
    for col in ["ruc", "cooperativa", "cooperativa_raw", "grupo_fuente", "archivo_origen"]:
        df[col] = df[col].astype("category")

    OUTPUT_DIR.mkdir(exist_ok=True)
    guardar_parquet_atomico(df, OUTPUT_PARQUET, engine="pyarrow", index=False)

    n_discrepancias = int(df["discrepancia_solvencia"].sum())
    metadata = {
        "fecha_procesamiento": datetime.now().isoformat(),
        "archivos_procesados": archivos_procesados,
        "registros_totales": int(len(df)),
        "ruc_unicos": int(df["ruc"].nunique()),
        "cooperativas_unicas": int(df["cooperativa"].nunique()),
        "grupos_fuente": sorted(df["grupo_fuente"].astype(str).unique().tolist()),
        "fecha_min": df["fecha"].min().isoformat(),
        "fecha_max": df["fecha"].max().isoformat(),
        "meses": int(df["fecha"].nunique()),
        "registros_con_discrepancia_solvencia_vs_ptc_appr": n_discrepancias,
        "cobertura": (
            "Segmento 1, Mutualistas y Caja Central FINANCOOP únicamente. "
            "La SEPS no publica este indicador para Segmento 2/3 "
            "(ver docs/RIESGO_METODOLOGIA.md §3.2)."
        ),
        "fuente": "Portal SEPS, panel 'Patrimonio técnico' (boletín Patrimonio Técnico por entidad)",
        "umbral_regulatorio": "Solvencia >= 9% (Patrimonio Técnico Requerido, ficha SEPS 63)",
    }
    with open(OUTPUT_METADATA, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print(f"COMPLETADO: {len(df)} registros -> {OUTPUT_PARQUET}")
    print(f"  Período: {metadata['fecha_min'][:10]} a {metadata['fecha_max'][:10]}")
    print(f"  RUC únicos: {metadata['ruc_unicos']}  ·  Grupos: {metadata['grupos_fuente']}")
    if n_discrepancias:
        print(f"  ADVERTENCIA: {n_discrepancias} registros con Solvencia publicada "
              f"!= PTC/APPR recalculado (>0.5pp) — se conservó el valor oficial (columna E).")
    print("=" * 60)


if __name__ == "__main__":
    generar_solvencia_parquet()
