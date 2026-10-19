"""Prueba de extremo a extremo con navegador real (Chromium/Playwright): arranca Streamlit, descarga los CSV y compara su
CONTENIDO con lo calculado de forma independiente desde master_data/panel_vulnerabilidad.parquet.
Uso: python tests/e2e/e2e_descargas.py     (no forma parte de `unittest discover`; requiere playwright + chromium)"""
import io, subprocess, sys, time, os, tempfile, urllib.request
from pathlib import Path
import pandas as pd
from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parents[2]; PUERTO = 8611; BASE = f"http://localhost:{PUERTO}"
sys.path.insert(0, str(RAIZ))
from utils.panel_vulnerabilidad import INDICADORES, descriptivos, VISTAS   # noqa: E402

def esperar_servidor():
    for _ in range(60):
        try:
            if urllib.request.urlopen(BASE + "/_stcore/health", timeout=2).status == 200: return
        except Exception: time.sleep(1)
    raise SystemExit("El servidor no arrancó")

def descargar(page, url, indice, esperar_texto):
    page.goto(url); page.wait_for_selector(f"text={esperar_texto}", timeout=120000)
    page.wait_for_selector('[data-testid="stDownloadButton"] button', timeout=60000)
    with page.expect_download(timeout=60000) as dl:
        page.locator('[data-testid="stDownloadButton"] button').nth(indice).click()
    return pd.read_csv(dl.value.path(), encoding="utf-8-sig"), dl.value.suggested_filename

def main():
    srv = subprocess.Popen([sys.executable, "-m", "streamlit", "run", "Inicio.py", "--server.port", str(PUERTO), "--server.headless", "true"],
                           cwd=RAIZ, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    resultados = []
    try:
        esperar_servidor(); P = pd.read_parquet(RAIZ / "master_data" / "panel_vulnerabilidad.parquet")
        with sync_playwright() as pw:
            nav = pw.chromium.launch(); ctx = nav.new_context(accept_downloads=True); pg = ctx.new_page()
            # 1) Comparativo: descriptivos de la fecha más reciente, vista principal, indicador por defecto (el 1.º)
            got, nombre = descargar(pg, BASE + "/Comparativo_Segmentos", 0, "Estadísticos descriptivos")
            ind = list(INDICADORES)[0]; corte = P.fecha.max()
            x = P[P.segmento_procedencia.isin(VISTAS[list(VISTAS)[0]]) & (P.fecha == corte)].dropna(subset=[ind])
            exp = descriptivos(x, ind).rename(columns={"segmento_repo": "segmento"})
            ok = list(got.columns) == list(exp.columns) and len(got) == len(exp) and (got.round(3).values == exp.round(3).values).all()
            resultados.append(("Comparativo: descriptivos", nombre, len(got), ok))
            # 2) Resumen ejecutivo: medianas por segmento al corte
            got2, n2 = descargar(pg, BASE + "/Resumen_Validado", 0, "Resumen ejecutivo validado")
            cols = ["liquidez", "morosidad", "cobertura", "roa", "eficiencia", "solvencia_proxy"]
            exp2 = P[P.fecha == corte].groupby("segmento_repo")[cols].median().round(2)
            ok2 = len(got2) == 3 and all(abs(got2.set_index(got2.columns[0]).iloc[i, j] - exp2.iloc[i, j]) < 0.011 for i in range(3) for j in range(len(cols)))
            resultados.append(("Resumen: medianas por segmento", n2, len(got2), ok2))
            # 3) Alertas: el resumen debe incluir todas las cooperativas con patrimonio negativo del corte y respetar el filtro
            got3, n3 = descargar(pg, BASE + "/Vulnerabilidad_Ficha", 0, "Alertas por fecha")
            neg = set(P[(P.fecha == corte) & P.patrimonio_negativo].cooperativa)
            ok3 = neg.issubset(set(got3.cooperativa)) and (got3.n_alertas.fillna(0) >= 0).all() and got3.cooperativa.is_unique
            resultados.append(("Alertas: resumen", n3, len(got3), ok3))
            nav.close()
    finally:
        srv.terminate()
    for r in resultados: print("OK  " if r[3] else "FALLA", *r[:3])
    sys.exit(0 if all(r[3] for r in resultados) else 1)

if __name__ == "__main__": main()
