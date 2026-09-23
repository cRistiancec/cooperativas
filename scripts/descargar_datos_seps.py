# -*- coding: utf-8 -*-
"""
Descarga automática de datos de cooperativas desde el portal SEPS.

Hace scraping de https://estadisticas.seps.gob.ec/index.php/estadisticas-sfps/
para encontrar el enlace del año corriente y descarga el ZIP de Estados
Financieros Mensuales (EEFF).

Exit codes:
  0 - Descargó datos nuevos correctamente
  1 - Error durante el proceso
  2 - No hay datos nuevos (el ZIP ya está descargado)
"""

import sys
import json
import re
import requests
import shutil
from pathlib import Path
from datetime import datetime

try:
    from seps_zip import inspeccionar_zip_seps
except ModuleNotFoundError:  # Importación como módulo desde tests/herramientas
    from scripts.seps_zip import inspeccionar_zip_seps

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: beautifulsoup4 no está instalado. Ejecuta: pip install beautifulsoup4")
    sys.exit(1)

# Rutas
BASE_DIR = Path(__file__).parent.parent
BALANCES_DIR = BASE_DIR / "balances_cooperativas"
INDICADORES_DIR = BASE_DIR / "indicadores"
PATRIMONIO_DIR = BASE_DIR / "patrimonio_tecnico"
MASTER_DATA_DIR = BASE_DIR / "master_data"
METADATA_PATH = MASTER_DATA_DIR / "metadata.json"

# Portal SEPS
URL_SEPS = "https://estadisticas.seps.gob.ec/index.php/estadisticas-sfps/"
BASE_DOWNLOAD_URL = "https://estadisticas.seps.gob.ec/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def obtener_fecha_actual_datos() -> datetime | None:
    """Lee metadata.json para saber hasta qué fecha están los datos actuales."""
    if not METADATA_PATH.exists():
        return None
    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        meta = json.load(f)
    fecha_max = meta.get("fecha_max")
    if not fecha_max:
        return None
    return datetime.fromisoformat(fecha_max.split("T")[0])


def extraer_download_id(html: str, anio: int, panel_texto: str = "estados financieros mensuales") -> str | None:
    """
    Extrae el enlace anual de un panel del portal SEPS, buscado por texto de
    su encabezado `<h5>` (insensible a mayúsculas). Por defecto busca el panel
    de "Estados Financieros Mensuales"; se reutiliza con otros textos (p. ej.
    "patrimonio técnico") para otras fuentes publicadas en el mismo portal.
    """
    soup = BeautifulSoup(html, "html.parser")
    seccion = None
    for h5 in soup.find_all("h5"):
        if panel_texto in h5.get_text(strip=True).lower():
            panel = h5.find_parent("div", class_="panel")
            seccion = panel if panel is not None else h5.parent
            break

    if seccion is None:
        return None

    # Buscar enlace con download_id cuyo texto sea el año
    anio_str = str(anio)
    for a in seccion.find_all("a", href=True):
        href = a["href"]
        texto = a.get_text(strip=True)
        if anio_str in texto and "download_id" in href:
            # Extraer el download_id
            match = re.search(r"download_id=(\d+)", href)
            if match:
                return match.group(1)

    return None


def scrape_download_id(anio: int, panel_texto: str = "estados financieros mensuales",
                        html: str | None = None) -> str | None:
    """
    Consulta el portal SEPS y obtiene el ID del ZIP de un panel dado.
    Si se pasa `html` ya descargado (p. ej. para reutilizar una misma
    respuesta del portal entre varias fuentes), evita un segundo fetch.
    """
    if html is None:
        print(f"  Accediendo a {URL_SEPS} ...")
        try:
            resp = requests.get(URL_SEPS, headers=HEADERS, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  ERROR al acceder al portal SEPS: {e}")
            return None
        html = resp.text

    download_id = extraer_download_id(html, anio, panel_texto)
    if download_id:
        print(f"  Encontrado: año {anio} -> download_id={download_id}")
        return download_id

    print(f"  No se encontró enlace de descarga ('{panel_texto}') para el año {anio}.")
    return None


def descargar_patrimonio_tecnico(anio: int) -> bool:
    """
    Descarga, de forma best-effort, el boletín de "Patrimonio Técnico" del
    portal SEPS (fuente FS01 — indicadores oficiales de Solvencia, PTC, PTS,
    APPR, PTR; cobertura: Segmento 1, Mutualistas y Caja Central FINANCOOP,
    no Segmentos 2/3 — ver docs/RIESGO_METODOLOGIA.md §3.2).

    Es una fuente **secundaria e independiente** del flujo principal de
    Estados Financieros: cualquier fallo aquí se registra como advertencia y
    NO afecta el código de salida del script (el pipeline de balance/CAMEL/PyG
    debe seguir funcionando aunque este boletín cambie de estructura o no
    esté disponible momentáneamente).

    Devuelve True si descargó (o ya tenía) el ZIP del año vigente.
    """
    try:
        PATRIMONIO_DIR.mkdir(exist_ok=True)
        print(f"\n[Patrimonio Técnico] Buscando boletín de solvencia oficial para {anio}...")
        download_id = scrape_download_id(anio, panel_texto="patrimonio técnico")
        if download_id is None:
            print("  [Patrimonio Técnico] No se encontró el panel en el portal. Se omite (no bloquea el pipeline).")
            return False

        destino = PATRIMONIO_DIR / f"{anio}-PAT.zip"
        destino_temporal = PATRIMONIO_DIR / f".{anio}-PAT.zip.tmp"
        destino_temporal.unlink(missing_ok=True)

        ok = descargar_zip(download_id, destino_temporal)
        if not ok:
            print("  [Patrimonio Técnico] Descarga falló. Se omite (no bloquea el pipeline).")
            destino_temporal.unlink(missing_ok=True)
            return False

        destino_temporal.replace(destino)
        print(f"  [Patrimonio Técnico] Guardado: {destino}")
        return True
    except Exception as exc:  # noqa: BLE001 — best-effort: nunca debe tumbar el flujo principal
        print(f"  [Patrimonio Técnico] ERROR inesperado (ignorado, no bloquea el pipeline): {exc}")
        return False


def descargar_zip(download_id: str, destino: Path) -> bool:
    """Descarga el ZIP del SEPS dado el download_id y lo guarda en destino."""
    url = f"{BASE_DOWNLOAD_URL}?sdm_process_download=1&download_id={download_id}"
    print(f"  Descargando desde: {url}")
    print(f"  Destino: {destino}")

    try:
        with requests.get(url, headers=HEADERS, stream=True, timeout=300) as resp:
            resp.raise_for_status()

            # Verificar que es un ZIP
            content_type = resp.headers.get("Content-Type", "")
            if "html" in content_type.lower():
                print(f"  ERROR: La respuesta es HTML, no un ZIP. "
                      f"Puede que el enlace haya cambiado o el ID sea incorrecto.")
                return False

            total = int(resp.headers.get("Content-Length", 0))
            descargado = 0
            with open(destino, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):  # 1 MB chunks
                    f.write(chunk)
                    descargado += len(chunk)
                    if total:
                        pct = descargado / total * 100
                        print(f"  {descargado / 1024 / 1024:.1f} MB / "
                              f"{total / 1024 / 1024:.1f} MB ({pct:.0f}%)", end="\r")

        print(f"\n  Descarga completa: {destino.stat().st_size / 1024 / 1024:.1f} MB")
        return True

    except requests.RequestException as e:
        print(f"  ERROR al descargar: {e}")
        if destino.exists():
            destino.unlink()  # Eliminar archivo parcial
        return False


def hay_datos_nuevos(anio: int, mes_actual: int) -> bool:
    """
    Verifica si los datos actuales ya incluyen el mes anterior al mes corriente.
    Si los datos llegan hasta el mes pasado, no hay nada nuevo que descargar.
    """
    fecha_max = obtener_fecha_actual_datos()
    if fecha_max is None:
        return True  # Sin metadata, asumir que hay datos nuevos
    mes_esperado = mes_actual - 1 if mes_actual > 1 else 12
    anio_esperado = anio if mes_actual > 1 else anio - 1

    print(f"  Datos actuales hasta: {fecha_max.strftime('%B %Y')}")
    print(f"  Mes esperado: {mes_esperado:02d}/{anio_esperado}")

    if fecha_max.year == anio_esperado and fecha_max.month >= mes_esperado:
        return False  # Ya tenemos los datos del mes pasado
    return True


def nombre_zip_balance(anio: int) -> str:
    """Genera el nombre estándar del ZIP de balance para un año dado."""
    # La SEPS usa patrones inconsistentes; usamos el más reciente como referencia
    if anio <= 2021:
        return f"{anio}-EEFF-MEN.zip"
    else:
        return f"{anio}_EEFF-Men.zip"


def nombre_zip_indicadores(anio: int) -> str:
    """Genera el nombre estándar del ZIP de indicadores para un año dado."""
    return f"{anio}-EEFF-MEN.zip"


def main():
    ahora = datetime.now()
    anio = ahora.year
    mes = ahora.month

    print("=" * 60)
    print("DESCARGA AUTOMÁTICA DE DATOS SEPS")
    print(f"Fecha de ejecución: {ahora.strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # Crear directorios si no existen
    BALANCES_DIR.mkdir(exist_ok=True)
    INDICADORES_DIR.mkdir(exist_ok=True)

    # Verificar si ya tenemos los datos actualizados
    print("\n[1/3] Verificando si hay datos nuevos...")
    if not hay_datos_nuevos(anio, mes):
        print("  Los datos ya están actualizados. No hay nada que descargar.")
        print("\nSaliendo con código 2 (sin datos nuevos).")
        sys.exit(2)
    print("  Hay datos nuevos disponibles. Procediendo con la descarga.")

    # Scraping para obtener el download_id del año corriente
    print(f"\n[2/3] Buscando enlace de descarga para el año {anio}...")
    download_id = scrape_download_id(anio)

    if download_id is None:
        # Si no encontramos el año corriente, puede que aún no esté publicado
        # Intentar con el año anterior si estamos en enero
        if mes == 1:
            print(f"  Intentando con el año {anio - 1} (estamos en enero)...")
            download_id = scrape_download_id(anio - 1)

    if download_id is None:
        print("\nERROR: No se pudo encontrar el enlace de descarga en el portal SEPS.")
        print("Puede que la SEPS haya cambiado la estructura de su web.")
        sys.exit(1)

    # Descargar primero a un temporal. La URL anual de la SEPS permanece
    # estable aunque su contenido todavía corresponda al mes anterior.
    print(f"\n[3/3] Descargando ZIP de Estados Financieros Mensuales {anio}...")
    nombre_zip = nombre_zip_balance(anio)
    destino_zip = BALANCES_DIR / nombre_zip
    destino_temporal = BALANCES_DIR / f".{nombre_zip}.tmp"
    destino_temporal.unlink(missing_ok=True)

    ok = descargar_zip(download_id, destino_temporal)

    if not ok:
        sys.exit(1)

    try:
        inspeccion = inspeccionar_zip_seps(destino_temporal)
    except (OSError, ValueError) as exc:
        print(f"  ERROR: El ZIP descargado no superó la validación: {exc}")
        destino_temporal.unlink(missing_ok=True)
        sys.exit(1)

    fecha_actual = obtener_fecha_actual_datos()
    print(f"  Fecha de corte dentro del ZIP: {inspeccion.fecha_corte:%Y-%m-%d}")
    print(f"  Segmentos validados: {len(inspeccion.segmentos)}")

    if fecha_actual is not None and inspeccion.fecha_corte <= fecha_actual:
        print(
            "  La SEPS aún sirve un ZIP sin un mes posterior a "
            f"{fecha_actual:%Y-%m-%d}."
        )
        destino_temporal.unlink(missing_ok=True)
        print("\nSaliendo con código 2 (la fuente aún no avanzó).")
        sys.exit(2)

    # Reemplazo atómico: la fuente anterior queda intacta ante cualquier fallo.
    destino_temporal.replace(destino_zip)

    # Copiar ZIP también a indicadores/ con nombre estándar.
    # El mismo ZIP contiene los XLSM usados por procesar_camel.py y procesar_pyg.py.
    nombre_zip_ind = nombre_zip_indicadores(anio)
    destino_ind = INDICADORES_DIR / nombre_zip_ind
    destino_ind_temporal = INDICADORES_DIR / f".{nombre_zip_ind}.tmp"
    print(f"\n  Copiando ZIP a indicadores/{nombre_zip_ind} ...")
    shutil.copy2(destino_zip, destino_ind_temporal)
    destino_ind_temporal.replace(destino_ind)
    print(f"  Copia completada: {destino_ind.stat().st_size / 1024 / 1024:.1f} MB")

    # Fuente secundaria best-effort: boletín de Patrimonio Técnico (Solvencia
    # oficial FS01). No afecta el código de salida de este script.
    descargar_patrimonio_tecnico(anio)

    print("\n" + "=" * 60)
    print(f"DESCARGA COMPLETADA: {nombre_zip}")
    print("Proceder con el pipeline ETL.")
    print("=" * 60)
    sys.exit(0)


if __name__ == "__main__":
    main()
