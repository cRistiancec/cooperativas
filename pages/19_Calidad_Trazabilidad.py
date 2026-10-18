# -*- coding: utf-8 -*-
"""Módulo 19: Calidad, cobertura y trazabilidad por componente (lee docs/cierre/validacion_componentes.json)."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
import pandas as pd
import streamlit as st
from ui import aplicar_tema, render_sidebar
from utils.data_loader import cargar_metadata
from utils.panel_vulnerabilidad import boton_csv, cargar_panel, cargar_validacion

st.set_page_config(page_title="Calidad y trazabilidad | Radar Cooperativo Ecuador", page_icon="🧾", layout="wide")
aplicar_tema()

def main():
    render_sidebar(cargar_metadata())
    st.title("🧾 Calidad de datos y trazabilidad")
    v = cargar_validacion()
    if not v: st.error("Falta docs/cierre/validacion_componentes.json (ejecutar scripts/validar_cierre.py)."); return
    filas = []
    for k, r in v.items():
        if isinstance(r, dict) and "filas" in r:
            filas.append({"componente": k, "registros": r["filas"], "fecha_min": r.get("fecha_min", "—"), "fecha_max": r.get("fecha_max"), "entidades": r.get("entidades"),
                          "duplicados_clave": r.get("duplicados_clave", r.get("duplicados_clave_2026")), "% segmento estimado": r.get("estimado_pct"),
                          "% nulos valor": r.get("nulos_valor_pct", r.get("nulos_valor_acumulado_pct"))})
    t = pd.DataFrame(filas); st.dataframe(t, width='stretch', hide_index=True); boton_csv(t, "calidad_componentes.csv", "dl_cal")
    st.subheader("Segmentación: procedencia por mes (últimos meses)")
    m = pd.DataFrame(v.get("segmentacion_meses_recientes", {})).T.reset_index().rename(columns={"index": "mes"}); st.dataframe(m, width='stretch', hide_index=True)
    st.caption("`pct_arrastrado` = entidades cuyo segmento se toma del último corte trimestral (≤2 meses). Jul–ago 2026 vienen de junio. El corte 2026-09 solo incluye entidades del boletín mensual.")
    d = cargar_panel()
    if not d.empty:
        st.subheader("Procedencia del segmento en el panel S1–S3")
        p = d.assign(anio=d.fecha.dt.year).groupby(["anio", "segmento_procedencia"]).size().unstack(fill_value=0)
        st.dataframe(p, width='stretch')
    st.subheader("Reconciliación con indicadores oficiales SEPS")
    q = Path(__file__).parent.parent / "reports" / "vulnerabilidad" / "calidad_panel.json"
    if q.exists():
        import json
        cal = json.loads(q.read_text(encoding="utf-8"))
        r = pd.DataFrame([{"indicador": k.replace("recon_", ""), **val} for k, val in cal.items() if k.startswith("recon_")]); st.dataframe(r, width='stretch', hide_index=True)
    st.warning("Limitaciones: segmento arrastrado/estimado (ver arriba); P&G e indicadores oficiales desde 2020; solvencia mostrada = proxy; el panel excluye mutualistas y S4/S5.")
main()
