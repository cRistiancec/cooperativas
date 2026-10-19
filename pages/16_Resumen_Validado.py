# -*- coding: utf-8 -*-
"""Módulo 16: Resumen ejecutivo validado (corte, entidades por segmento, indicadores y advertencias)."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
import pandas as pd
import streamlit as st
from ui import aplicar_tema, render_sidebar
from utils.data_loader import cargar_metadata
from utils.panel_vulnerabilidad import INDICADORES, PROCEDENCIA_TXT, SEGMENTOS, boton_csv, cargar_panel, cargar_validacion, descriptivos

st.set_page_config(page_title="Resumen validado | Radar Cooperativo Ecuador", page_icon="📌", layout="wide")
aplicar_tema()

def main():
    render_sidebar(cargar_metadata())
    st.title("📌 Resumen ejecutivo validado — Segmentos 1, 2 y 3")
    d = cargar_panel()
    if d.empty:
        st.error("No se encontró master_data/panel_vulnerabilidad.parquet. Ver docs/cierre/INFORME_CIERRE.md (§6)."); return
    corte = d["fecha"].max(); u = d[d["fecha"] == corte]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Corte validado", corte.strftime("%d/%m/%Y")); c2.metric("Cooperativas en el corte", f"{u['cooperativa'].nunique():,}")
    c3.metric("Observaciones coop-mes", f"{len(d):,}"); c4.metric("Período", f"{d['fecha'].min():%m/%Y} – {corte:%m/%Y}")
    st.subheader("Distribución por segmento (point-in-time al corte)")
    dist = u.groupby("segmento_repo").agg(entidades=("cooperativa", "nunique"), activos_usd=("activos", "sum")).reindex(SEGMENTOS).reset_index()
    dist["procedencia_segmento"] = dist["segmento_repo"].map(lambda s: ", ".join(sorted(u[u.segmento_repo == s].segmento_procedencia.map(PROCEDENCIA_TXT).unique())))
    st.dataframe(dist.rename(columns={"segmento_repo": "segmento"}), width='stretch', hide_index=True)
    st.subheader("Indicadores principales — mediana por segmento al corte")
    cols = ["liquidez", "morosidad", "cobertura", "roa", "eficiencia", "solvencia_proxy"]
    med = u.groupby("segmento_repo")[cols].median().round(2).reindex(SEGMENTOS).rename(columns={c: INDICADORES[c][0] for c in cols})
    st.dataframe(med, width='stretch'); boton_csv(med.reset_index(), f"resumen_{corte:%Y%m}.csv", "dl_resumen")
    st.subheader("Estado de actualización y advertencias")
    prop = d.segmento_procedencia.value_counts(normalize=True).mul(100).round(1)
    dd = d[d.fecha >= "2020-01-01"].segmento_procedencia.value_counts(normalize=True).mul(100).round(1)
    st.warning(f"**Procedencia del segmento (2020–2026):** {dd.get('exacto_mes', 0)} % archivo SEPS del propio mes; {dd.get('arrastrado', 0)} % arrastrado del último corte trimestral; "
               f"{dd.get('estimado', 0)} % estimado. Julio y agosto de 2026 usan el segmento de junio. Las comparaciones por segmento intermedias son aproximadas.")
    st.info("El corte de septiembre 2026 se toma del boletín mensual SEPS. El indicador de solvencia mostrado es un **proxy** (patrimonio/activos), no la solvencia regulatoria; "
            "las series de P&G e indicadores oficiales parten en 2020.")
    v = cargar_validacion()
    if v: st.caption(f"Validación de solo lectura: ver página «Calidad y trazabilidad». Panel: {len(d):,} filas, sin duplicados coop-mes: {not d.duplicated(['cooperativa','fecha']).any()}.")
main()
