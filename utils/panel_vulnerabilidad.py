# -*- coding: utf-8 -*-
"""Acceso cacheado al panel cooperativa-mes S1-S3 (master_data/panel_vulnerabilidad.parquet) y utilidades de las páginas 16-19."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st

RAIZ = Path(__file__).resolve().parent.parent
RUTA_PANEL = RAIZ / "master_data" / "panel_vulnerabilidad.parquet"
RUTA_VALIDACION = RAIZ / "docs" / "cierre" / "validacion_componentes.json"

# indicador -> (etiqueta, unidad, formula/fuente, mayor_es_peor)
INDICADORES = {
    "solvencia_proxy": ("Capitalización (proxy)", "%", "Patrimonio total (Activos − Pasivos, incluye resultado del ejercicio) / Activos. NO es la solvencia regulatoria (patrimonio técnico / APPR).", False),
    "liquidez": ("Liquidez", "%", "Fondos disponibles (11) / depósitos a corto plazo (2101+210305+210310). Coincide con indicador SEPS.", False),
    "morosidad": ("Morosidad", "%", "Cartera improductiva / cartera bruta (cód. 1401-1489). Coincide con indicador SEPS.", True),
    "cobertura": ("Cobertura de provisiones", "%", "Provisiones (1499) / cartera improductiva. Coincide con indicador SEPS.", False),
    "roa": ("ROA anualizado", "%", "Resultado YTD x12/m / promedio de activos (dic. previo..m). ≈92 % exacto vs SEPS.", False),
    "roe": ("ROE anualizado", "%", "Resultado YTD x12/m / promedio de patrimonio (dic. previo..m). ≈91 % exacto vs SEPS.", False),
    "eficiencia": ("Eficiencia operativa", "%", "Gastos de operación / ingresos operativos, 12 meses (no reconciliada con SEPS).", True),
    "crec_activos_12m": ("Crecimiento de activos 12m", "%", "Activos(t)/Activos(t-12) − 1.", False),
}
SEGMENTOS = ["SEGMENTO 1", "SEGMENTO 2", "SEGMENTO 3"]
PROCEDENCIA_TXT = {
    "exacto_mes": "Archivo SEPS del propio mes", "arrastrado": "Arrastrado del último corte trimestral (≤2 meses)",
    "estimado": "Estimado (backfill)", "balance_historico": "Acoplado en la ingesta (sin fila en la dimensión)",
}

@st.cache_data(ttl=3600, show_spinner=False)
def cargar_panel() -> pd.DataFrame:
    if not RUTA_PANEL.exists():
        return pd.DataFrame()
    d = pd.read_parquet(RUTA_PANEL)
    d["fecha"] = pd.to_datetime(d["fecha"])
    for c in INDICADORES:
        if c in d:
            d[c] = pd.to_numeric(d[c], errors="coerce").replace([np.inf, -np.inf], np.nan)
    return d

@st.cache_data(ttl=3600, show_spinner=False)
def cargar_validacion() -> dict:
    return json.loads(RUTA_VALIDACION.read_text(encoding="utf-8")) if RUTA_VALIDACION.exists() else {}

def fechas_panel(d: pd.DataFrame) -> list:
    return sorted(d["fecha"].dropna().unique(), reverse=True)

def descriptivos(d: pd.DataFrame, col: str, por: str = "segmento_repo") -> pd.DataFrame:
    g = d.groupby(por)[col]
    t = g.agg(n="count", media="mean", mediana="median", desv_est="std", p10=lambda x: x.quantile(.1), p25=lambda x: x.quantile(.25),
              p75=lambda x: x.quantile(.75), p90=lambda x: x.quantile(.9)).round(3)
    return t.reset_index()

def z_orientado(d: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """z-score robusto (mediana/MAD) DENTRO del mismo segmento y fecha, orientado: alto = peor."""
    out = pd.DataFrame(index=d.index)
    for c in cols:
        g = d.groupby(["fecha", "segmento_repo"])[c]
        med = g.transform("median"); mad = g.transform(lambda x: (x - x.median()).abs().median()) * 1.4826
        z = (d[c] - med) / mad.replace(0, np.nan)
        out[c] = z if INDICADORES[c][3] else -z
    return out

def boton_csv(df: pd.DataFrame, nombre: str, key: str):
    st.download_button("⬇️ Descargar tabla mostrada (CSV)", df.to_csv(index=False).encode("utf-8-sig"), file_name=nombre, mime="text/csv", key=key)
