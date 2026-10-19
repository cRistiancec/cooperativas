# -*- coding: utf-8 -*-
"""Módulo 19: Calidad, cobertura y trazabilidad por componente (lee docs/cierre/validacion_componentes.json)."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
import pandas as pd
import streamlit as st
from ui import aplicar_tema, botones_descarga, render_filtros_globales, render_resumen_filtro, render_sidebar, selector_fecha_corte
from utils.data_loader import cargar_metadata
from utils.panel_vulnerabilidad import cargar_panel, cargar_validacion, panel_filtrado

st.set_page_config(page_title="Calidad y trazabilidad | Radar Cooperativo Ecuador", page_icon="🧾", layout="wide")
aplicar_tema()

def main():
    metadata = cargar_metadata(); render_sidebar(metadata)
    st.title("🧾 Calidad de datos y trazabilidad")
    filtro = render_filtros_globales(); fecha_sel = selector_fecha_corte(filtro)
    d = panel_filtrado(filtro) if not cargar_panel().empty else cargar_panel()
    render_resumen_filtro(filtro, d[d.fecha == fecha_sel] if not d.empty else d, corte=pd.Timestamp(metadata["fecha_max"]), fecha_analisis=fecha_sel)
    st.caption("Las tablas de validación por componente y de reconciliación describen los archivos completos (no dependen de la selección). "
               "Las tablas de procedencia, cobertura y patrimonio negativo se restringen al filtro global.")
    v = cargar_validacion()
    if not v: st.error("Falta docs/cierre/validacion_componentes.json (ejecutar scripts/validar_cierre.py)."); return
    filas = []
    for k, r in v.items():
        if isinstance(r, dict) and "filas" in r:
            filas.append({"componente": k, "registros": r["filas"], "fecha_min": r.get("fecha_min", "—"), "fecha_max": r.get("fecha_max"), "entidades": r.get("entidades"),
                          "duplicados_clave": r.get("duplicados_clave", r.get("duplicados_clave_2026")), "% segmento estimado": r.get("estimado_pct"),
                          "% nulos valor": r.get("nulos_valor_pct", r.get("nulos_valor_acumulado_pct"))})
    t = pd.DataFrame(filas); st.dataframe(t, width='stretch', hide_index=True)
    botones_descarga(t, filtro, "calidad_componentes", "Validación por componente (archivos completos, sin filtrar)", "dl_cal", corte=metadata["fecha_max"])
    st.subheader("Segmentación: procedencia por mes (últimos meses)")
    m = pd.DataFrame(v.get("segmentacion_meses_recientes", {})).T.reset_index().rename(columns={"index": "mes"}); st.dataframe(m, width='stretch', hide_index=True)
    st.caption("`pct_arrastrado` = entidades cuyo segmento se toma del último corte trimestral (≤2 meses). Jul–ago 2026 vienen de junio. El corte 2026-09 solo incluye entidades del boletín mensual.")
    if not d.empty:
        st.subheader("Procedencia del segmento en el panel S1–S3 (selección)")
        p = d.assign(anio=d.fecha.dt.year).groupby(["anio", "segmento_procedencia"]).size().unstack(fill_value=0)
        st.dataframe(p, width='stretch')
    cov = Path(__file__).parent.parent / "reports" / "vulnerabilidad" / "cobertura_segmentos.csv"
    if cov.exists():
        st.subheader("Cobertura de la clasificación por año, mes y segmento")
        c = pd.read_csv(cov)
        per = pd.to_datetime(dict(year=c.anio, month=c.mes, day=1)) + pd.offsets.MonthEnd(0)
        cv = c[(per >= filtro.fecha_ini) & (per <= filtro.fecha_fin)]
        if filtro.segmentos:
            cv = cv[cv.segmento.isin(filtro.segmentos)]
        st.dataframe(cv, width="stretch", hide_index=True)
        botones_descarga(cv, filtro, "cobertura_segmentos_filtrada", "Cobertura de la clasificación (período y segmentos del filtro)", "dl_cov", corte=metadata["fecha_max"])
        st.caption("Informe agregado por segmento y mes: respeta período y segmentos del filtro global; no se subdivide por entidad ni por calidad.")
        st.caption("exacto_mes = asignación del archivo SEPS del propio mes; arrastrado = último corte trimestral ≤2 meses; estimado = backfill; "
                   "sin_clasificacion_verificable = sin procedencia conocida (0 en el panel actual).")
    eq = Path(__file__).parent.parent / "master_data" / "equivalencias_nombres.csv"
    if eq.exists():
        st.subheader("Equivalencias de nombres corregidas (trazabilidad)")
        e = pd.read_csv(eq); st.dataframe(e, width="stretch", hide_index=True)
        botones_descarga(e, filtro, "equivalencias_nombres", "Equivalencias de nombres (tabla de trazabilidad completa)", "dl_eq", corte=metadata["fecha_max"])
        st.caption("Corrección de codificación (UTF-8 leído como cp1252). Une identidades que aparecían duplicadas sin solape de fechas. El nombre de la fuente se conserva en esta tabla.")
    if not d.empty and "patrimonio_negativo" in d:
        neg = d[d.patrimonio_negativo][["cooperativa", "fecha", "segmento_repo", "activos", "pasivos", "patrimonio_total"]]
        st.subheader(f"Observaciones con patrimonio total negativo ({len(neg)})")
        st.dataframe(neg.round(0), width="stretch", hide_index=True)
        botones_descarga(neg, filtro, "patrimonio_negativo", "Observaciones con patrimonio negativo", "dl_neg", corte=metadata["fecha_max"])
        st.caption("Valores reales de la fuente (identidad A = P + Pat verificada; pérdidas acumuladas superan capital y reservas). Se conservan; no se imputan.")
    st.subheader("Reconciliación con indicadores oficiales SEPS")
    q = Path(__file__).parent.parent / "reports" / "vulnerabilidad" / "calidad_panel.json"
    if q.exists():
        import json
        cal = json.loads(q.read_text(encoding="utf-8"))
        r = pd.DataFrame([{"indicador": k.replace("recon_", ""), **val} for k, val in cal.items() if k.startswith("recon_")]); st.dataframe(r, width='stretch', hide_index=True)
    st.warning("Limitaciones: segmento arrastrado/estimado (ver arriba); P&G e indicadores oficiales desde 2020; solvencia mostrada = proxy; el panel excluye mutualistas y S4/S5.")
main()
