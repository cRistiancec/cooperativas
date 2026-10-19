# -*- coding: utf-8 -*-
"""Módulo 16: Resumen ejecutivo validado (corte, entidades por segmento, indicadores y advertencias)."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
import pandas as pd
import streamlit as st
from ui import aplicar_tema, botones_descarga, exigir_datos, render_filtros_globales, render_resumen_filtro, render_sidebar, selector_fecha_corte
from utils.data_loader import cargar_metadata
from utils.panel_vulnerabilidad import INDICADORES, PROCEDENCIA_TXT, SEGMENTOS, cargar_panel, cargar_validacion, panel_filtrado

st.set_page_config(page_title="Resumen validado | Radar Cooperativo Ecuador", page_icon="📌", layout="wide")
aplicar_tema()

def main():
    metadata = cargar_metadata(); render_sidebar(metadata)
    st.title("📌 Resumen ejecutivo validado — Segmentos 1, 2 y 3")
    if cargar_panel().empty:
        st.error("No se encontró master_data/panel_vulnerabilidad.parquet. Ver docs/cierre/INFORME_CIERRE.md (§6)."); return
    filtro = render_filtros_globales(); corte = selector_fecha_corte(filtro)
    d = panel_filtrado(filtro); u = d[d["fecha"] == corte] if not d.empty else d
    render_resumen_filtro(filtro, u, corte=pd.Timestamp(metadata["fecha_max"]), fecha_analisis=corte)
    exigir_datos(d)
    exigir_datos(u, "No hay observaciones del panel S1–S3 en la fecha de análisis para esta selección.")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Fecha de análisis", corte.strftime("%d/%m/%Y")); c2.metric("Cooperativas en la fecha", f"{u['cooperativa'].nunique():,}")
    c3.metric("Observaciones coop-mes", f"{len(d):,}"); c4.metric("Período", f"{d['fecha'].min():%m/%Y} – {corte:%m/%Y}")
    st.subheader("Distribución por segmento (point-in-time al corte)")
    dist = u.groupby("segmento_repo").agg(entidades=("cooperativa", "nunique"), activos_usd=("activos", "sum")).reindex(SEGMENTOS).dropna(how="all").reset_index()
    dist["procedencia_segmento"] = dist["segmento_repo"].map(lambda s: ", ".join(sorted(u[u.segmento_repo == s].segmento_procedencia.map(PROCEDENCIA_TXT).unique())))
    dist = dist.rename(columns={"segmento_repo": "segmento"})
    st.dataframe(dist, width='stretch', hide_index=True)
    botones_descarga(dist, filtro, f"resumen_distribucion_{corte:%Y%m}", "Distribución por segmento", "dl_resumen_dist", corte=corte)
    st.subheader("Indicadores principales — mediana por segmento al corte")
    cols = ["liquidez", "morosidad", "cobertura", "roa", "eficiencia", "solvencia_proxy"]
    med = u.groupby("segmento_repo")[cols].median().round(2).reindex(SEGMENTOS).dropna(how="all").rename(columns={c: INDICADORES[c][0] for c in cols})
    st.dataframe(med, width='stretch'); botones_descarga(med.reset_index(), filtro, f"resumen_{corte:%Y%m}", "Indicadores principales — mediana por segmento", "dl_resumen", corte=corte)
    st.subheader("Estado de actualización y advertencias")
    prop = d.segmento_procedencia.value_counts(normalize=True).mul(100).round(1)
    dd = d[d.fecha >= "2020-01-01"].segmento_procedencia.value_counts(normalize=True).mul(100).round(1)
    st.warning(f"**Procedencia del segmento en la selección (desde 2020):** {dd.get('exacto_mes', 0)} % archivo SEPS del propio mes; {dd.get('arrastrado', 0)} % arrastrado del último corte trimestral; "
               f"{dd.get('estimado', 0)} % estimado. Julio y agosto de 2026 usan el segmento de junio. Las comparaciones por segmento intermedias son aproximadas.")
    st.info("El corte de septiembre 2026 se toma del boletín mensual SEPS. El indicador de solvencia mostrado es un **proxy** (patrimonio/activos), no la solvencia regulatoria; "
            "las series de P&G e indicadores oficiales parten en 2020.")
    v = cargar_validacion()
    if v: st.caption(f"Validación de solo lectura: ver página «Calidad y trazabilidad». Panel: {len(d):,} filas, sin duplicados coop-mes: {not d.duplicated(['cooperativa','fecha']).any()}.")
main()
