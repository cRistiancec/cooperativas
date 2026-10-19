# -*- coding: utf-8 -*-
"""Puerta de calidad del pipeline mensual antes de commit y despliegue."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

try:
    from seps_zip import SEGMENTOS_ESPERADOS, inspeccionar_zip_seps
except ModuleNotFoundError:
    from scripts.seps_zip import SEGMENTOS_ESPERADOS, inspeccionar_zip_seps


BASE_DIR = Path(__file__).parent.parent
MASTER_DATA_DIR = BASE_DIR / "master_data"
BALANCES_DIR = BASE_DIR / "balances_cooperativas"

DATASETS_CON_FECHA = {
    "balance": MASTER_DATA_DIR / "balance.parquet",
    "agregados_metricas": MASTER_DATA_DIR / "agg_metricas_sistema.parquet",
    "agregados_ranking": MASTER_DATA_DIR / "agg_ranking_cooperativas.parquet",
    "agregados_series": MASTER_DATA_DIR / "agg_series_temporales.parquet",
    "pyg": MASTER_DATA_DIR / "pyg.parquet",
    "camel": MASTER_DATA_DIR / "indicadores.parquet",
}


def _rango_fechas(path: Path) -> tuple[pd.Timestamp, pd.Timestamp, int]:
    if not path.exists():
        raise FileNotFoundError(f"Falta dataset requerido: {path}")
    fechas = pd.read_parquet(path, columns=["fecha"])["fecha"]
    if fechas.empty:
        raise ValueError(f"Dataset vacío: {path}")
    fechas = pd.to_datetime(fechas)
    return fechas.min(), fechas.max(), len(fechas)


SEGMENTOS_VALIDOS_DIM = SEGMENTOS_ESPERADOS | {"SEGMENTO 4", "SEGMENTO 5"}
COLUMNAS_SEGMENTO = ["segmento_historico", "segmento_historico_estimado"]


def validar_segmentos(fecha_fuente: pd.Timestamp,
                      dim_path: Path | None = None,
                      datasets: dict[str, Path] | None = None) -> None:
    """Puerta del segmento point-in-time. ERROR si el corte nuevo no trae segmento
    oficial acoplado; ADVERTENCIA (impresa) si el historial aún está estimado."""
    import pyarrow.parquet as pq
    dim_path = Path(dim_path or MASTER_DATA_DIR / "dim_segmento_historico.parquet")
    datasets = datasets or {k: DATASETS_CON_FECHA[k] for k in ("balance", "pyg", "camel")}
    if not dim_path.exists():
        raise ValueError(
            "Falta master_data/dim_segmento_historico.parquet. Reconstruirla una vez con "
            "`python scripts/segmento_historico.py --rehidratar <ZIPs históricos>`.")
    dim = pd.read_parquet(dim_path)
    dim["fecha"] = pd.to_datetime(dim["fecha"])
    malos = set(dim["segmento_historico"].unique()) - SEGMENTOS_VALIDOS_DIM
    if malos:
        raise ValueError(f"dim_segmento_historico con etiquetas inválidas: {sorted(malos)}")
    if dim.duplicated(["cooperativa", "fecha"]).any():
        raise ValueError("dim_segmento_historico con duplicados cooperativa-fecha")
    if fecha_fuente not in set(dim["fecha"]):
        raise ValueError(f"dim_segmento_historico no contiene el corte {fecha_fuente.date()}")
    meses_dim = set(dim["fecha"].unique())
    huecos = [str(f.date()) for f in pd.date_range(dim["fecha"].min(), fecha_fuente, freq="ME")
              if f not in meses_dim]
    if huecos:
        raise ValueError(f"dim_segmento_historico con meses sin segmento: {huecos[:6]}")

    ultimo = dim[dim["fecha"] == fecha_fuente]
    for nombre, path in datasets.items():
        faltan = [c for c in COLUMNAS_SEGMENTO if c not in pq.ParquetFile(path).schema_arrow.names]
        if faltan:
            raise ValueError(f"{nombre} no tiene las columnas {faltan}: el segmento histórico "
                             "no se acopló en la ingesta")
        cols = pd.read_parquet(path, columns=["fecha", "cooperativa"] + COLUMNAS_SEGMENTO)
        cols["fecha"] = pd.to_datetime(cols["fecha"])
        mes = cols[cols["fecha"] == fecha_fuente]
        if mes["segmento_historico_estimado"].astype(bool).any():
            raise ValueError(f"{nombre}: hay registros de {fecha_fuente.date()} con segmento "
                             "ESTIMADO; el corte nuevo debe traer segmento oficial")
        sin_dim = set(mes["cooperativa"].astype(str)) - set(ultimo["cooperativa"].astype(str))
        if nombre == "balance" and sin_dim:
            raise ValueError(f"balance: {len(sin_dim)} cooperativas del corte sin fila en la "
                             f"dimensión (ej.: {sorted(sin_dim)[:3]})")
        pct = float(cols.drop_duplicates(["cooperativa", "fecha"])["segmento_historico_estimado"]
                    .astype(bool).mean() * 100)
        print(f"  segmento {nombre}: {pct:.1f}% de pares cooperativa-mes aún ESTIMADOS"
              + ("  <-- ADVERTENCIA: rehidratar historial" if pct > 0 else ""))
    n_seg = dim.groupby("cooperativa")["segmento_historico"].nunique()
    print(f"  segmento: {int((n_seg > 1).sum())} cooperativas con reclasificación registrada")


def validar(fecha_anterior: datetime | None = None) -> None:
    zips = sorted(BALANCES_DIR.glob("*.zip"))
    if not zips:
        raise FileNotFoundError("No hay ZIP fuente en balances_cooperativas/")
    inspeccion = inspeccionar_zip_seps(zips[-1])
    fecha_fuente = pd.Timestamp(inspeccion.fecha_corte)

    if fecha_anterior is not None and fecha_fuente <= pd.Timestamp(fecha_anterior):
        raise ValueError(
            f"La fuente no avanzó: anterior={fecha_anterior:%Y-%m-%d}, "
            f"fuente={fecha_fuente:%Y-%m-%d}"
        )

    rangos = {}
    for nombre, path in DATASETS_CON_FECHA.items():
        fecha_min, fecha_max, registros = _rango_fechas(path)
        rangos[nombre] = (fecha_min, fecha_max, registros)
        if fecha_max != fecha_fuente:
            raise ValueError(
                f"{nombre} termina en {fecha_max.date()}, "
                f"pero la fuente termina en {fecha_fuente.date()}"
            )

    for nombre in ("balance", "pyg", "camel"):
        path = DATASETS_CON_FECHA[nombre]
        columnas = pd.read_parquet(path, columns=["fecha", "segmento"])
        columnas["fecha"] = pd.to_datetime(columnas["fecha"])
        segmentos_ultimo_mes = set(
            columnas.loc[
                columnas["fecha"] == fecha_fuente,
                "segmento",
            ].astype(str)
        )
        faltantes = SEGMENTOS_ESPERADOS - segmentos_ultimo_mes
        if faltantes:
            raise ValueError(
                f"{nombre} no contiene todos los segmentos en "
                f"{fecha_fuente.date()}: {', '.join(sorted(faltantes))}"
            )

    validar_segmentos(fecha_fuente)

    if rangos["balance"][0] > pd.Timestamp("2018-01-31"):
        raise ValueError("El balance perdió historia anterior a 2018-01-31")
    if rangos["pyg"][0] > pd.Timestamp("2020-01-31"):
        raise ValueError("PyG perdió historia anterior a 2020-01-31")
    if rangos["camel"][0] > pd.Timestamp("2020-01-31"):
        raise ValueError("CAMEL perdió historia anterior a 2020-01-31")

    metadata_path = MASTER_DATA_DIR / "metadata.json"
    with open(metadata_path, "r", encoding="utf-8") as fh:
        metadata = json.load(fh)
    fecha_metadata = pd.Timestamp(metadata["fecha_max"])
    if fecha_metadata != fecha_fuente:
        raise ValueError(
            f"metadata.json termina en {fecha_metadata.date()}, "
            f"pero la fuente termina en {fecha_fuente.date()}"
        )

    metadata_agregados_path = MASTER_DATA_DIR / "metadata_agregados.json"
    with open(metadata_agregados_path, "r", encoding="utf-8") as fh:
        metadata_agregados = json.load(fh)
    fecha_agregados = pd.Timestamp(metadata_agregados["fechas"]["max"])
    if fecha_agregados != fecha_fuente:
        raise ValueError("metadata_agregados.json no coincide con la fuente")

    print("VALIDACIÓN MENSUAL OK")
    print(f"  Fuente: {fecha_fuente.date()}")
    for nombre, (fecha_min, fecha_max, registros) in rangos.items():
        print(
            f"  {nombre}: {registros:,} registros, "
            f"{fecha_min.date()} a {fecha_max.date()}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fecha-anterior",
        help="Fecha máxima publicada antes del ETL (ISO-8601)",
    )
    args = parser.parse_args()
    fecha_anterior = (
        datetime.fromisoformat(args.fecha_anterior.split("T")[0])
        if args.fecha_anterior
        else None
    )
    validar(fecha_anterior)


if __name__ == "__main__":
    main()
