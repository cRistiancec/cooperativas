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
COLUMNAS = ["cooperativa", "fecha", "segmento_historico", "fuente",
            "fecha_corte_origen", "es_arrastrado"]
# es_arrastrado=False -> el segmento viene del corte de ESE mes (dato exacto).
# es_arrastrado=True  -> el mes no tiene corte propio (fuente trimestral): se usa el
#                        último corte anterior <= mes (point-in-time, sin mirar al futuro);
#                        fecha_corte_origen dice de qué corte proviene.
MAX_ARRASTRE_MESES = 2


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
    base["fecha_corte_origen"] = base["fecha"]
    base["es_arrastrado"] = False
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
    nuevo = nuevo.copy()
    nuevo["fecha"] = pd.to_datetime(nuevo["fecha"])
    if "fecha_corte_origen" not in nuevo:
        nuevo["fecha_corte_origen"] = nuevo["fecha"]
    if "es_arrastrado" not in nuevo:
        nuevo["es_arrastrado"] = False
    previo = pd.read_parquet(ruta) if ruta.exists() else pd.DataFrame(columns=COLUMNAS)
    previo["fecha"] = pd.to_datetime(previo["fecha"])
    if "fecha_corte_origen" not in previo:
        previo["fecha_corte_origen"] = previo["fecha"]
    if "es_arrastrado" not in previo:
        previo["es_arrastrado"] = False
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
    guardar_parquet_atomico(final, ruta, engine="pyarrow", compression="zstd")
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
                            Path(ruta), engine="pyarrow", compression="zstd")
    return dim


# ----------------------------------------------------------------------------
# Fuente oficial trimestral: "Entidades trimestral" (portal SEPS, 2018 -> hoy)
# ----------------------------------------------------------------------------
def _parsear_fecha_corte(col: pd.Series) -> pd.Series:
    """dd/mm/aaaa (TXT 2025+) o ISO/fecha de Excel (XLSX 2018-2024)."""
    col = col.astype(str).str.strip()
    iso = col.str.match(r"^\d{4}-\d{2}-\d{2}")
    out = pd.to_datetime(col.where(~iso), format="%d/%m/%Y", errors="coerce")
    out = out.fillna(pd.to_datetime(col.where(iso).str[:10], format="%Y-%m-%d", errors="coerce"))
    if out.isna().any():
        raise SegmentoInvalidoError(f"FECHA_CORTE no interpretable: {col[out.isna()].unique()[:5].tolist()}")
    return out


def leer_entidades_txt(contenido: bytes | str, fuente: str, df: pd.DataFrame | None = None) -> pd.DataFrame:
    """Parsea un TXT de 'Entidades trimestral' (tabulado; FECHA_CORTE dd/mm/aaaa,
    RUC, RAZON_SOCIAL, SEGMENTO, ESTADO_JURIDICO, ...). Devuelve una fila por
    entidad-corte con el nombre normalizado igual que el balance. Solo se conservan
    cooperativas y mutualistas; un segmento no interpretable lanza error."""
    import io
    try:
        from procesar_balance_cooperativas import normalizar_nombre
    except ModuleNotFoundError:
        from scripts.procesar_balance_cooperativas import normalizar_nombre
    if df is None and isinstance(contenido, bytes):
        if contenido[:2] in (b"\xff\xfe", b"\xfe\xff"):      # 2026: UTF-16 con BOM
            contenido = contenido.decode("utf-16")
        else:
            try:
                contenido = contenido.decode("utf-8-sig")
            except UnicodeDecodeError:
                contenido = contenido.decode("latin-1")
    if df is None:
        df = pd.read_csv(io.StringIO(contenido), sep="\t", dtype=str)
    df.columns = [c.strip().upper() for c in df.columns]
    req = {"FECHA_CORTE", "RUC", "RAZON_SOCIAL", "SEGMENTO"}
    if req - set(df.columns):
        raise SegmentoInvalidoError(f"{fuente}: faltan columnas {sorted(req - set(df.columns))}")
    if "TIPO_ORGANIZACION" in df:
        tipo = df["TIPO_ORGANIZACION"].fillna("").str.upper()
        df = df[tipo.str.contains("COOPERATIVA|MUTUALISTA")]
    out = pd.DataFrame({
        "ruc": df["RUC"].str.strip(),
        "cooperativa": df["RAZON_SOCIAL"].map(normalizar_nombre),
        "fecha": _parsear_fecha_corte(df["FECHA_CORTE"]),
        "segmento_historico": df["SEGMENTO"].map(normalizar_segmento),
        "estado_juridico": df.get("ESTADO_JURIDICO"),
        "provincia": df.get("PROVINCIA"),
    })
    # "SIN SEGMENTO" es una condición oficial (p. ej. entidades extintas o aún no
    # clasificadas): se conserva con segmento nulo y NO entra a la dimensión.
    sin_seg = df["SEGMENTO"].fillna("").str.upper().str.strip().isin(["SIN SEGMENTO", ""]).to_numpy()
    nulo = out["segmento_historico"].isna().to_numpy() & ~sin_seg
    if nulo.any():
        ej = df["SEGMENTO"][nulo].unique()[:5].tolist()
        raise SegmentoInvalidoError(
            f"{fuente}: {int(nulo.sum())} filas con SEGMENTO no reconocido (ej.: {ej})")
    dup = out.duplicated(["ruc", "fecha"], keep=False)
    if dup.any():
        out = out.drop_duplicates(["ruc", "fecha", "segmento_historico"])
        if out.duplicated(["ruc", "fecha"], keep=False).any():
            raise SegmentoInvalidoError(f"{fuente}: un mismo RUC con dos segmentos en un corte")
    out["fuente"] = f"entidades_trimestral:{fuente}"
    return out.reset_index(drop=True)


def expandir_cortes_a_mensual(cortes: pd.DataFrame, hasta: pd.Timestamp | None = None) -> pd.DataFrame:
    """Convierte cortes trimestrales (ruc/cooperativa, fecha, segmento) en filas
    MENSUALES point-in-time: para cada mes se toma el último corte <= mes (nunca uno
    futuro), a lo sumo MAX_ARRASTRE_MESES atrás. Los meses sin corte propio quedan
    con es_arrastrado=True y su fecha_corte_origen. Se excluyen estados jurídicos
    posteriores al corte porque no se mira hacia adelante."""
    c = cortes.dropna(subset=["segmento_historico"]).copy()
    if "fuente" not in c:
        c["fuente"] = "entidades_trimestral"
    c["fecha"] = pd.to_datetime(c["fecha"]) + pd.offsets.MonthEnd(0)
    c = c.drop_duplicates(["cooperativa", "fecha"], keep="last")
    hasta = pd.Timestamp(hasta) if hasta is not None else c["fecha"].max()
    meses = pd.date_range(c["fecha"].min(), hasta, freq="ME")
    partes = []
    for k in range(MAX_ARRASTRE_MESES + 1):
        t = c.copy()
        t["fecha_corte_origen"] = t["fecha"]
        t["fecha"] = t["fecha"] + pd.offsets.MonthEnd(k)
        t["es_arrastrado"] = k > 0
        t["_k"] = k
        partes.append(t)
    m = pd.concat(partes, ignore_index=True)
    m = m[m["fecha"].isin(meses) & (m["fecha"] <= hasta)]
    # para cada cooperativa-mes: el corte más reciente (k mínimo)
    m = m.sort_values(["cooperativa", "fecha", "_k"]).drop_duplicates(["cooperativa", "fecha"], keep="first")
    return m[COLUMNAS].reset_index(drop=True)


def combinar_exacto_y_trimestral(exacto: pd.DataFrame, trimestral_mensual: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Prioridad: dato exacto del mes (archivo mensual) > corte trimestral arrastrado.
    Devuelve (dim, diagnóstico). El diagnóstico cuenta discrepancias entre ambas
    fuentes en los pares cooperativa-mes que las dos cubren (control de calidad)."""
    claves = ["cooperativa", "fecha"]
    ambos = exacto.merge(trimestral_mensual, on=claves, suffixes=("_ex", "_tr"))
    disc = ambos[ambos["segmento_historico_ex"] != ambos["segmento_historico_tr"]]
    solo_tr = trimestral_mensual.merge(exacto[claves], on=claves, how="left", indicator=True)
    solo_tr = solo_tr[solo_tr["_merge"] == "left_only"].drop(columns="_merge")
    dim = pd.concat([exacto[COLUMNAS], solo_tr[COLUMNAS]], ignore_index=True)
    dim = dim.sort_values(claves).reset_index(drop=True)
    diag = {"pares_comparados": int(len(ambos)), "discrepancias_exacto_vs_trimestral": int(len(disc)),
            "ejemplos": disc[claves + ["segmento_historico_ex", "segmento_historico_tr"]].head(8).to_dict("records")}
    return dim, diag


def cargar_cortes_entidades(directorio: Path) -> pd.DataFrame:
    """Lee todos los ZIP/TXT de 'Entidades trimestral' de un directorio."""
    import zipfile
    partes = []
    for z in sorted(Path(directorio).glob("*.zip")):
        with zipfile.ZipFile(z) as zf:
            for n in zf.namelist():
                bajo = n.lower()
                if bajo.endswith(".txt"):
                    partes.append(leer_entidades_txt(zf.read(n), f"{z.name}/{n}"))
                elif bajo.endswith(".xlsx"):
                    import io
                    hoja = pd.read_excel(io.BytesIO(zf.read(n)), dtype=str)
                    partes.append(leer_entidades_txt(b"", f"{z.name}/{n}", df=hoja))
    if not partes:
        raise FileNotFoundError(f"No hay ZIP/TXT de entidades en {directorio}")
    c = pd.concat(partes, ignore_index=True)
    return c.drop_duplicates(["ruc", "fecha"], keep="last")


def rehidratar_desde_fuente(dir_mensuales: Path, dir_entidades: Path, ruta: Path = DIM_PATH) -> dict:
    """Reconstruye la dimensión SOLO con archivos descargados del portal SEPS:
    exacto (ZIP mensuales con SEGMENTO) + registro trimestral de entidades."""
    exacto = rehidratar(dir_mensuales, ruta=Path(ruta).with_suffix(".exacto.parquet"))
    exacto = exacto[exacto["fecha"] <= exacto["fecha"].max()]
    cortes = cargar_cortes_entidades(dir_entidades)
    cortes.to_parquet(Path(ruta).parent / "entidades_trimestral.parquet", index=False)
    tri = expandir_cortes_a_mensual(cortes, hasta=max(exacto['fecha'].max(), cortes['fecha'].max()))
    dim, diag = combinar_exacto_y_trimestral(exacto, tri)
    guardar_parquet_atomico(dim, Path(ruta), engine="pyarrow", compression="zstd")
    Path(ruta).with_suffix(".exacto.parquet").unlink(missing_ok=True)
    diag.update(filas=int(len(dim)), arrastradas=int(dim["es_arrastrado"].sum()),
                cortes_entidades=int(cortes["fecha"].nunique()))
    return diag


def actualizar_entidades(anios: list[int] | None = None, ruta: Path = DIM_PATH) -> dict:
    """Ingesta periódica desde la fuente: descarga 'Entidades trimestral' del año
    corriente y el anterior, fusiona los nuevos cortes con los ya guardados y
    recalcula las filas arrastradas de la dimensión. Los meses con dato exacto
    (archivo mensual/boletín) no se tocan."""
    try:
        from descargar_datos_seps import ENTIDADES_DIR, descargar_entidades_trimestral
    except ModuleNotFoundError:
        from scripts.descargar_datos_seps import ENTIDADES_DIR, descargar_entidades_trimestral
    hoy = datetime.now().year
    for a in (anios or [hoy - 1, hoy]):
        if descargar_entidades_trimestral(a) is None:
            print(f"  [entidades] {a}: no publicado todavía")
    nuevos = cargar_cortes_entidades(ENTIDADES_DIR)
    # Los ZIP descargados no viven en el repo: se fusionan con los cortes ya guardados
    # (los nuevos ganan ante una revisión del mismo RUC-corte).
    guardado = Path(ruta).parent / "entidades_trimestral.parquet"
    if guardado.exists():
        previos = pd.read_parquet(guardado)
        previos["fecha"] = pd.to_datetime(previos["fecha"])
        cortes = pd.concat([previos, nuevos], ignore_index=True).drop_duplicates(["ruc", "fecha"], keep="last")
    else:
        cortes = nuevos
    dim_prev = pd.read_parquet(ruta)
    dim_prev["fecha"] = pd.to_datetime(dim_prev["fecha"])
    exacto = dim_prev[~dim_prev["fuente"].str.startswith("entidades_trimestral")]
    cortes.to_parquet(Path(ruta).parent / "entidades_trimestral.parquet", index=False)
    tri = expandir_cortes_a_mensual(cortes, hasta=max(dim_prev["fecha"].max(), cortes["fecha"].max()))
    dim, diag = combinar_exacto_y_trimestral(exacto, tri)
    guardar_parquet_atomico(dim, Path(ruta), engine="pyarrow", compression="zstd")
    diag.update(filas=int(len(dim)), cortes_entidades=int(cortes["fecha"].nunique()))
    return diag


def reparar_mojibake(texto: str) -> str:
    """'CRÃ‰DITO' -> 'CRÉDITO' (UTF-8 leído como cp1252). Si no aplica, devuelve igual."""
    if "Ã" not in texto and "Â" not in texto:
        return texto
    try:
        return texto.encode("cp1252").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return texto


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
    nombres = df["cooperativa"].astype(str)
    try:
        from procesar_balance_cooperativas import normalizar_nombre as _norm
    except ModuleNotFoundError:
        from scripts.procesar_balance_cooperativas import normalizar_nombre as _norm
    reparados = {n: (_norm(reparar_mojibake(n)) if ("Ã" in n or "Â" in n) else n)
                 for n in nombres.unique()}
    nombres = nombres.map(reparados)       # solo para el cruce; df conserva su nombre
    cats = pd.Index(nombres.unique())
    cod_df = cats.get_indexer(nombres)
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
    seg_final = np.where(hallado, seg_dim[pos], previo)
    # Filas agregadas de la SEPS ("VT_TOTAL SEGMENTO 2", "VT_TOTAL MUTUALISTAS") no son
    # entidades: su segmento es el de la propia etiqueta oficial (no una estimación).
    vt = nombres.str.upper().str.startswith("VT_TOTAL").to_numpy()
    if vt.any():
        etiqueta = nombres[vt].str.upper().str.replace("VT_TOTAL", "", regex=False).str.strip().map(
            lambda t: normalizar_segmento("MUTUALISTA" if t.startswith("MUTUALISTA") else t))
        seg_final = seg_final.astype(object)
        seg_final[vt] = np.where(etiqueta.notna().to_numpy(), etiqueta.to_numpy(object), seg_final[vt])
        hallado = hallado.copy()
        hallado[vt] = etiqueta.notna().to_numpy()
    df = df.copy()
    df["segmento_historico"] = seg_final
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


def _acoplar_parquet_streaming(pq_path: Path, dim: pd.DataFrame, nombre: str,
                               lote: int = 1_500_000) -> dict:
    """Agrega `segmento_historico` y `segmento_historico_estimado` a un parquet grande
    por lotes (balance tiene ~25 M de filas: no cabe en memoria como DataFrame)."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    pf = pq.ParquetFile(pq_path)
    esquema = pf.schema_arrow
    for c in ("segmento_historico", "segmento_historico_estimado"):
        if c in esquema.names:
            esquema = esquema.remove(esquema.get_field_index(c))
    cat_tipo = pa.dictionary(pa.int32(), pa.string())
    esquema_out = esquema.append(pa.field("segmento_historico", cat_tipo)) \
                         .append(pa.field("segmento_historico_estimado", pa.bool_()))
    tmp = pq_path.with_suffix(".tmp.parquet")
    escritor = pq.ParquetWriter(tmp, esquema_out, compression="zstd")
    filas = cubiertas = 0
    try:
        for rb in pf.iter_batches(batch_size=lote):
            t = pa.Table.from_batches([rb])
            for c in ("segmento_historico", "segmento_historico_estimado"):
                if c in t.column_names:
                    t = t.drop_columns([c])
            base = pd.DataFrame({
                "cooperativa": t["cooperativa"].to_pandas().astype(str),
                "fecha": t["fecha"].to_pandas(),
                "segmento": (t["segmento"].to_pandas().astype(str) if "segmento" in t.column_names
                             else "SEGMENTO 3"),
            })
            r = aplicar_segmento_historico(base, dim)
            seg = pa.array(r["segmento_historico"].astype(str).to_numpy(object), pa.string()).dictionary_encode()
            est = pa.array(r["segmento_historico_estimado"].to_numpy(bool))
            t = t.append_column("segmento_historico", seg).append_column("segmento_historico_estimado", est)
            escritor.write_table(t.cast(esquema_out))
            filas += len(r)
            cubiertas += int((~r["segmento_historico_estimado"]).sum())
    finally:
        escritor.close()
    tmp.replace(pq_path)
    rep = {"dataset": nombre, "filas": filas, "pct_cubierto": round(cubiertas / max(filas, 1) * 100, 2)}
    print(f"  [acoplar_master:{nombre}] filas={filas:,} cubierto={rep['pct_cubierto']}%")
    return rep


def acoplar_master_data(ruta: Path = DIM_PATH) -> list[dict]:
    """Aplica la dimensión a los parquets ya existentes (balance, pyg, indicadores)
    sin reprocesar ZIP. Útil cuando la fuente actual del portal ya no publica los
    CSV mensuales históricos y solo se puede recuperar el segmento, no el balance."""
    dim = pd.read_parquet(ruta)
    reportes = []
    for nombre in ("indicadores", "pyg", "balance"):
        pq_path = MASTER_DIR / f"{nombre}.parquet"
        if pq_path.exists():
            reportes.append(_acoplar_parquet_streaming(pq_path, dim, nombre))
    return reportes


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
    ap.add_argument("--actualizar-entidades", action="store_true",
                    help="descarga Entidades trimestral del portal y refresca la dimensión")
    ap.add_argument("--acoplar-master", action="store_true",
                    help="aplica la dimensión a balance/pyg/indicadores existentes")
    a = ap.parse_args(argv)
    if a.actualizar_entidades:
        d = actualizar_entidades()
        d.pop("ejemplos", None)
        print("Entidades trimestral:", d)
    if a.acoplar_master:
        print(acoplar_master_data())
    if a.rehidratar:
        dim = rehidratar(Path(a.rehidratar))
        print(f"Dimensión reconstruida: {len(dim):,} filas -> {DIM_PATH}")
    if a.verificar or a.rehidratar or a.acoplar_master or a.actualizar_entidades:
        return verificar()
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
