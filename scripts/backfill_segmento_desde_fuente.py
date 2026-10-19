# -*- coding: utf-8 -*-
"""
Backfill del segmento histórico DIRECTAMENTE desde el portal SEPS.

Descarga los ZIP anuales de Estados Financieros Mensuales (2018 -> año actual)
y reconstruye master_data/dim_segmento_historico.parquet con el segmento oficial
(columna SEGMENTO) de cada mes. No requiere archivos externos.

Uso:  python scripts/backfill_segmento_desde_fuente.py [--desde 2018] [--hasta AAAA]
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import requests  # noqa: E402
from descargar_datos_seps import (  # noqa: E402
    BALANCES_DIR, ENTIDADES_DIR, HEADERS, URL_SEPS, descargar_entidades_trimestral,
    descargar_zip, nombre_zip_balance, scrape_download_id,
)
from segmento_historico import DIM_PATH, rehidratar_desde_fuente  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", type=int, default=2018)
    ap.add_argument("--hasta", type=int, default=datetime.now().year)
    ap.add_argument("--refrescar", action="store_true", help="volver a descargar aunque exista")
    args = ap.parse_args()

    BALANCES_DIR.mkdir(exist_ok=True)
    html = requests.get(URL_SEPS, headers=HEADERS, timeout=30).text
    faltan = []
    for anio in range(args.desde, args.hasta + 1):
        # 1) ZIP mensual del año (exacto: trae SEGMENTO del mes)
        destino = BALANCES_DIR / nombre_zip_balance(anio)
        if not (destino.exists() and not args.refrescar):
            did = scrape_download_id(anio, html=html)
            tmp = destino.with_suffix(".tmp")
            if did is None or not descargar_zip(did, tmp):
                faltan.append(f"mensual {anio}")
            else:
                tmp.replace(destino)
        # 2) Registro oficial trimestral de entidades (segmento por corte)
        if not ((ENTIDADES_DIR / f"entidades_{anio}.zip").exists() and not args.refrescar):
            if descargar_entidades_trimestral(anio, html=html) is None:
                faltan.append(f"entidades {anio}")
    if faltan:
        print(f"ERROR: fuentes no descargables: {faltan}")
        return 1
    diag = rehidratar_desde_fuente(BALANCES_DIR, ENTIDADES_DIR, DIM_PATH)
    print("Diagnóstico:", diag)
    return 0


if __name__ == "__main__":
    sys.exit(main())
