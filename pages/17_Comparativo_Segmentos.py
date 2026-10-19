# -*- coding: utf-8 -*-
"""Módulo 17: Comparación de indicadores entre segmentos 1, 2 y 3 (point-in-time)."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from ui import aplicar_tema, botones_descarga, exigir_datos, render_filtros_globales, render_resumen_filtro, render_sidebar, selector_fecha_corte
from utils.data_loader import cargar_metadata
from utils.panel_vulnerabilidad import INDICADORES, SEGMENTOS, cargar_panel, composicion, descriptivos, panel_filtrado

st.set_page_config(page_title="Comparativo por segmento | Radar Cooperativo Ecuador", page_icon="📊", layout="wide")
aplicar_tema()
COL = {"SEGMENTO 1": "#2563EB", "SEGMENTO 2": "#F59E0B", "SEGMENTO 3": "#10B981"}

def main():
    metadata = cargar_metadata(); render_sidebar(metadata)
    st.title("📊 Comparación entre segmentos 1, 2 y 3")
    if cargar_panel().empty: st.error("Panel no disponible."); return
    filtro = render_filtros_globales(); fecha_corte = selector_fecha_corte(filtro)
    d = panel_filtrado(filtro)
    render_resumen_filtro(filtro, d[d.fecha == fecha_corte] if not d.empty else d, corte=pd.Timestamp(metadata["fecha_max"]), fecha_analisis=fecha_corte)
    exigir_datos(d)
    ind = st.sidebar.selectbox("Indicador", list(INDICADORES), format_func=lambda k: INDICADORES[k][0], key="cmp_ind")
    x = d                                           # ya filtrado: período ∩ segmentos ∩ entidades ∩ calidad de clasificación
    base_sel = x
    x = x.dropna(subset=[ind])
    if x.empty: st.warning("Sin datos para la selección."); return
    segs = [sg for sg in SEGMENTOS if sg in set(x.segmento_repo)]
    comp = composicion(base_sel); cA, cB, cC = st.columns(3)
    cA.metric("Clasificación oficial del mes", f"{comp.get('exacto_mes', 0)} %"); cB.metric("Arrastrada de otro corte", f"{comp.get('arrastrado', 0)} %"); cC.metric("Estimada", f"{comp.get('estimado', 0)} %")
    st.caption(f"Composición de las observaciones de la selección ({len(x):,} observaciones con valor del indicador). La calidad de clasificación se elige en el filtro global.")
    if (comp.get("arrastrado", 0) + comp.get("estimado", 0)) > 0:
        st.warning("La comparación mezcla clasificaciones de distinta calidad (arrastradas/estimadas junto a oficiales). "
                   "Para una comparación estricta, elija «oficial del período» en el filtro de calidad.")
    nom, un, formula, _ = INDICADORES[ind]
    st.caption(f"**Fórmula:** {formula}  ·  **Unidad:** {un}  ·  **Fuente:** balance SEPS (master_data) → panel cooperativa-mes. Valores faltantes: se excluyen (no se imputan).")
    s = x.groupby(["fecha", "segmento_repo"])[ind].agg(mediana="median", p25=lambda v: v.quantile(.25), p75=lambda v: v.quantile(.75)).reset_index()
    fig = go.Figure()
    for sg in segs:
        t = s[s.segmento_repo == sg]
        fig.add_trace(go.Scatter(x=t.fecha, y=t.p75, mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=t.fecha, y=t.p25, mode="lines", line=dict(width=0), fill="tonexty", fillcolor="rgba(120,120,120,.15)", showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=t.fecha, y=t["mediana"], mode="lines", name=sg, line=dict(color=COL[sg], width=2.5)))
    fig.update_layout(title=f"{nom}: mediana y rango intercuartílico por segmento", yaxis_title=f"{nom} ({un})", xaxis_title="Fecha de corte",
                      height=460, template="plotly_dark", legend=dict(orientation="h"))
    st.plotly_chart(fig, width='stretch')
    st.caption("Fuente: SEPS (EEFF mensuales), cálculo propio. Banda = percentiles 25–75. Diferencias descriptivas, no causales; entre cortes trimestrales el segmento puede ser arrastrado.")
    st.subheader(f"Estadísticos descriptivos al {pd.Timestamp(fecha_corte):%m/%Y}")
    t = descriptivos(x[x.fecha == pd.Timestamp(fecha_corte)], ind).rename(columns={"segmento_repo": "segmento"})
    st.dataframe(t, width='stretch', hide_index=True)
    botones_descarga(t, filtro, f"descriptivos_{ind}_{pd.Timestamp(fecha_corte):%Y%m}", f"Estadísticos descriptivos — {nom}", "dl_desc", corte=fecha_corte)
    with st.expander("Serie mostrada (exportable)"):
        st.dataframe(s, width='stretch', hide_index=True)
        botones_descarga(s, filtro, f"serie_{ind}", f"Serie por segmento — {nom}", "dl_serie", corte=fecha_corte)
main()
