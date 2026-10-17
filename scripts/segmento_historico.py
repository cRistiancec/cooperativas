# -*- coding: utf-8 -*-
"""
Segmento histórico (point-in-time) de cada cooperativa — ingesta y tabla de dimensión.

PROBLEMA QUE RESUELVE
---------------------
Los archivos originales de la SEPS informan el SEGMENTO de cada entidad en cada
corte mensual (columna SEGMENTO en los CSV/TXT 2018-2025; nombre del XLSM por
segmento en 2026). El ETL lo leía, pero:
  1. en modo incremental solo reprocesa el ZIP del año corriente y los ZIP
     históricos no viven en el repositorio (.gitignore), de modo que el segmento
     de 2018-2025 nunca se recuperaba;
  2. `generar_balance_parquet` sobrescribe `segmento` con el último segmento de
     cada cooperativa (correcto para rankings "actuales", incorrecto para
     análisis histórico).

SOLUCIÓN
--------
Tabla pequeña y versionable `master_data/dim_segmento_historico.parquet`
(una fila por cooperativa-fecha de corte) que se alimenta en CADA ingesta:
  - `--rehidratar DIR`  : lee todos los ZIP históricos una sola vez y reconstruye
                          la tabla completa (operación de recuperación).
  - ingesta mensual     : `procesar_balance_cooperativas.py` hace upsert de los
                          meses que procesa (reemplaza el mes completo, de modo
                          que las revisiones retrospectivas de la SEPS quedan
                          registradas en `log_cambios`).
La tabla NUNCA infiere segmentos por tamaño ni por nombre: solo registra lo que
el archivo oficial dice para ese mes.

USO
---
    python scripts/segmento_historico.py --rehidratar balances_cooperativas/
    python scripts/segmento_historico.py --verificar
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from io_atomico import guardar_parquet_atomico
except ModuleNotFoundError:  # ejecución como paquete
    from scripts.io_atomico import guardar_parquet_atomico

BASE_DIR = Path(__file__).parent.parent
MASTER_DIR = BASE_DIR / "master_data"
DIM_PATH = MASTER_DIR / "dim_segmento_historico.parquet"
LOG_PATH = MASTER_DIR / "dim_segmento_historico_cambios.json"

SEGMENTOS_VALIDOS = {
    "SEGMENTO 1", "SEGMENTO 2", "SEGMENTO 3", "SEGMENTO 4", "SEGMENTO 5",
    "SEGMENTO 1 MUTUALISTA",
}
COLUMNAS = ["cooperativa", "fecha", "segmento_historico", "fuente"]


class SegmentoInvalidoError(ValueError):
    """El archivo fuente trae un segmento ausente, desconocido o contradictorio."""


def normalizar_segmento(valor) -> str | None:
    """'Segmento 2', 'SEGMENTO  2 ', 'segmento 1 mutualista' -> etiqueta canónica.

    Devuelve None si no se puede interpretar (NO se adivina)."""
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return None
    texto = re.sub(r"\s+", " ", str(valor).strip().upper())
    m = re.fullmatch(r"SEGMENTO ?([1-5])( MUTUALISTAS?)?", texto)
    if not m:
        if texto in ("MUTUALISTA", "MUTUALISTAS"):
            return "SEGMENTO 1 MUTUALISTA"
        return None
    if m.group(2):
        return "SEGMENTO 1 MUTUALISTA" if m.group(1) == "1" else None
    return f"SEGMENTO {m.group(1)}"


def construir_dim(df: pd.DataFrame, fuente: str) -> pd.DataFrame:
    """A partir de filas ya procesadas (columnas `cooperativa`, `fecha`,
    `segmento_historico`) devuelve la dimensión validada, una fila por
    cooperativa-fecha. Lanza SegmentoInvalidoError ante datos no confiables."""
    req = {"cooperativa", "fecha", "segmento_historico"}
    faltan = req - set(df.columns)
    if faltan:
        raise SegmentoInvalidoError(f"{fuente}: faltan columnas {sorted(faltan)}")
    base = df[["cooperativa", "fecha", "segmento_historico"]].drop_duplicates().copy()
    base["cooperativa"] = base["cooperativa"].astype(str)
    base["fecha"] = pd.to_datetime(base["fecha"])
    crudo = base["segmento_historico"].astype(object)
    base["segmento_historico"] = crudo.map(normalizar_segmento)

    nulos = base["segmento_historico"].isna()
    if nulos.any():
        ejemplos = crudo[nulos].astype(str).unique()[:5].tolist()
        raise SegmentoInvalidoError(
            f"{fuente}: {int(nulos.sum())} pares cooperativa-fecha con segmento ausente o "
            f"no reconocido (ejemplos: {ejemplos}). No se asigna por inferencia.")
    base = base.drop_duplicates()
    conflicto = base.duplicated(["cooperativa", "fecha"], keep=False)
    if conflicto.any():
        ej = base[conflicto].sort_values(["cooperativa", "fecha"]).head(6)
        raise SegmentoInvalidoError(
            f"{fuente}: {int(conflicto.sum())} filas con más de un segmento para la misma "
            f"cooperativa-fecha:\n{ej.to_string(index=False)}")
    base["fuente"] = fuente
    return base[COLUMNAS].sort_values(["fecha", "cooperativa"]).reset_index(drop=True)


def extraer_dim_zip(zip_path: Path) -> pd.DataFrame:
    """Lee un ZIP original de la SEPS y devuelve su dimensión de segmentos."""
    try:
        from procesar_balance_cooperativas import leer_archivo_desde_zip, procesar_dataframe
    except ModuleNotFoundError:
        from scripts.procesar_balance_cooperativas import leer_archivo_desde_zip, procesar_dataframe
    df = procesar_dataframe(leer_archivo_desde_zip(Path(zip_path)))
    return construir_dim(df, Path(zip_path).name)


def upsert_dim(nuevo: pd.DataFrame, ruta: Path = DIM_PATH, log_path: Path = LOG_PATH) -> dict:
    """Incorpora `nuevo` a la dimensión. Para cada fecha presente en `nuevo` se
    REEMPLAZA el mes completo (así una revisión retrospectiva de la SEPS no deja
    filas obsoletas). Registra altas, bajas y cambios de segmento detectados."""
    ruta = Path(ruta)
    previo = pd.read_parquet(ruta) if ruta.exists() else pd.DataFrame(columns=COLUMNAS)
    previo["fecha"] = pd.to_datetime(previo["fecha"])
    fechas = set(pd.to_datetime(nuevo["fecha"]).unique())
    viejo_mes = previo[previo["fecha"].isin(fechas)]
    comp = viejo_mes.merge(nuevo, on=["cooperativa", "fecha"], how="outer",
                           suffixes=("_antes", "_ahora"), indicator=True)
    cambios = comp[(comp["_merge"] == "both") &
                   (comp["segmento_historico_antes"] != comp["segmento_historico_ahora"])]
    resumen = {
        "fecha_proceso": datetime.now().isoformat(timespec="seconds"),
        "meses_reemplazados": sorted(str(pd.Timestamp(f).date()) for f in fechas),
        "filas_nuevas": int((comp["_merge"] == "right_only").sum()),
        "filas_retiradas": int((comp["_merge"] == "left_only").sum()),
        "revisiones_de_segmento": [
            {"cooperativa": r.cooperativa, "fecha": str(r.fecha.date()),
             "antes": r.segmento_historico_antes, "ahora": r.segmento_historico_ahora}
            for r in cambios.itertuples()],
    }
    resto = previo[~previo["fecha"].isin(fechas)]
    final = pd.concat([resto, nuevo[COLUMNAS]], ignore_index=True)
    assert not final.duplicated(["cooperativa", "fecha"]).any()
    final = final.sort_values(["fecha", "cooperativa"]).reset_index(drop=True)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    guardar_parquet_atomico(final, ruta, engine="pyarrow", compression="snappy")
    historial = json.loads(Path(log_path).read_text(encoding="utf-8")) if Path(log_path).exists() else []
    if resumen["revisiones_de_segmento"] or resumen["filas_retiradas"]:
        historial.append(resumen)
        Path(log_path).write_text(json.dumps(historial, indent=1, ensure_ascii=False), encoding="utf-8")
    return resumen


def rehidratar(directorio_zips: Path, ruta: Path = DIM_PATH) -> pd.DataFrame:
    """Reconstruye la dimensión desde TODOS los ZIP de balance de un directorio."""
    zips = sorted(Path(directorio_zips).glob("*.zip"))
    if not zips:
        raise FileNotFoundError(f"No hay ZIP en {directorio_zips}")
    partes = []
    for z in zips:
        print(f"  [segmento] {z.name} ...", flush=True)
        partes.append(extraer_dim_zip(z))
    dim = pd.concat(partes, ignore_index=True)
    dup = dim.duplicated(["cooperativa", "fecha"], keep=False)
    if dup.any():  # mismo mes en dos ZIP: debe coincidir; si no, no se resuelve en silencio
        c = dim[dup].drop_duplicates(["cooperativa", "fecha", "segmento_historico"])
        if c.duplicated(["cooperativa", "fecha"], keep=False).any():
            raise SegmentoInvalidoError("El mismo mes aparece en dos ZIP con segmentos distintos.")
        dim = dim.drop_duplicates(["cooperativa", "fecha"], keep="last")
    guardar_parquet_atomico(dim.sort_values(["fecha", "cooperativa"]).reset_index(drop=True),
                            Path(ruta), engine="pyarrow", compression="snappy")
    return dim


def _clave(cod: np.ndarray, fechas: pd.Series) -> np.ndarray:
    f = pd.to_datetime(fechas)
    return cod.astype(np.int64) * 100000 + ((f.dt.year - 1990) * 12 + f.dt.month).to_numpy(np.int64)


def aplicar_segmento_historico(df: pd.DataFrame, dim: pd.DataFrame) -> pd.DataFrame:
    """Asigna a `df` (formato largo del balance) `segmento_historico` desde la
    dimensión y marca `segmento_historico_estimado` = True SOLO donde la dimensión
    no cubre la cooperativa-fecha (ahí se conserva el valor previo, declarado estimado).
    Vectorizado por claves enteras para soportar ~25 M de filas."""
    if "cooperativa" not in df or not len(dim):
        return df
    cats = pd.Index(df["cooperativa"].astype(str).unique())
    cod_df = cats.get_indexer(df["cooperativa"].astype(str)) if len(cats) < 50_000 else None
    dim = dim.assign(cooperativa=dim["cooperativa"].astype(str))
    dim = dim[dim["cooperativa"].isin(cats)]
    clave_dim = _clave(cats.get_indexer(dim["cooperativa"]), dim["fecha"])
    orden = np.argsort(clave_dim)
    clave_dim, seg_dim = clave_dim[orden], dim["segmento_historico"].to_numpy(object)[orden]
    clave_df = _clave(cod_df, df["fecha"])
    pos = np.searchsorted(clave_dim, clave_df)
    pos[pos >= len(clave_dim)] = 0
    hallado = clave_dim[pos] == clave_df if len(clave_dim) else np.zeros(len(df), bool)
    previo = df["segmento_historico"].astype(object).to_numpy() if "segmento_historico" in df else df["segmento"].astype(object).to_numpy()
    df = df.copy()
    df["segmento_historico"] = np.where(hallado, seg_dim[pos], previo)
    df["segmento_historico"] = df["segmento_historico"].astype("category")
    df["segmento_historico_estimado"] = ~hallado
    return df


def acoplar_segmento(df: pd.DataFrame, nombre: str, ruta: Path | None = None) -> tuple[pd.DataFrame, dict]:
    """Punto único de acople del segmento point-in-time para CUALQUIER dataset
    largo (balance, PyG, CAMEL...). La dimensión es la única fuente de verdad:
    así los tres datasets nunca discrepan entre sí. Devuelve (df, reporte).

    reporte: filas, pct_cubierto (filas con segmento real), discrepancias_fuente
    (filas donde el dato propio del archivo —no estimado— difiere de la dimensión)."""
    ruta = Path(ruta or DIM_PATH)
    if not ruta.exists():
        print(f"  [segmento_historico:{nombre}] ADVERTENCIA: no existe la dimensión; "
              "el segmento queda ESTIMADO (retroactivo).")
        if "segmento_historico" not in df.columns:
            df = df.assign(segmento_historico=df["segmento"], segmento_historico_estimado=True)
        return df, {"dataset": nombre, "filas": len(df), "pct_cubierto": 0.0, "discrepancias_fuente": 0}
    propio_real = None
    if {"segmento_historico", "segmento_historico_estimado"} <= set(df.columns):
        propio_real = ~df["segmento_historico_estimado"].fillna(True).astype(bool)
        propio = df["segmento_historico"].astype(str)
    out = aplicar_segmento_historico(df, pd.read_parquet(ruta))
    disc = 0
    if propio_real is not None:
        disc = int((propio_real & ~out["segmento_historico_estimado"] &
                    (propio != out["segmento_historico"].astype(str))).sum())
    rep = {"dataset": nombre, "filas": len(out),
           "pct_cubierto": round(float((~out["segmento_historico_estimado"]).mean() * 100), 2),
           "discrepancias_fuente": disc}
    print(f"  [segmento_historico:{nombre}] cubierto={rep['pct_cubierto']}% "
          f"discrepancias_vs_dimension={disc}")
    return out, rep


def verificar(ruta: Path = DIM_PATH) -> int:
    """Informe de cobertura y de cambios de segmento. Código de salida 1 si falla."""
    if not Path(ruta).exists():
        print("FALLA: no existe la dimensión. Ejecutar --rehidratar con los ZIP históricos.")
        return 1
    d = pd.read_parquet(ruta)
    d["fecha"] = pd.to_datetime(d["fecha"])
    ok = True
    if d.duplicated(["cooperativa", "fecha"]).any():
        print("FALLA: duplicados cooperativa-fecha"); ok = False
    malos = set(d["segmento_historico"].unique()) - SEGMENTOS_VALIDOS
    if malos:
        print(f"FALLA: etiquetas inválidas {malos}"); ok = False
    huecos = [str(f.date()) for f in pd.date_range(d.fecha.min(), d.fecha.max(), freq="ME")
              if f not in set(d.fecha.unique())]
    if huecos:
        print(f"FALLA: meses sin segmento: {huecos}"); ok = False
    n_seg = d.groupby("cooperativa")["segmento_historico"].nunique()
    print(f"Filas={len(d):,} · cooperativas={d.cooperativa.nunique()} · {d.fecha.min().date()} → {d.fecha.max().date()}")
    print(f"Cooperativas con cambio de segmento: {(n_seg > 1).sum()}")
    print(d.groupby(["fecha", "segmento_historico"]).cooperativa.nunique().unstack(fill_value=0).tail(3).to_string())
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rehidratar", metavar="DIR_ZIPS")
    ap.add_argument("--verificar", action="store_true")
    a = ap.parse_args(argv)
    if a.rehidratar:
        dim = rehidratar(Path(a.rehidratar))
        print(f"Dimensión reconstruida: {len(dim):,} filas -> {DIM_PATH}")
    if a.verificar or a.rehidratar:
        return verificar()
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
