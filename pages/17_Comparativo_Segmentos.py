# -*- coding: utf-8 -*-
"""Módulo 17: Comparación de indicadores entre segmentos 1, 2 y 3 (point-in-time)."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from ui import aplicar_tema, render_sidebar
from utils.data_loader import cargar_metadata
from utils.panel_vulnerabilidad import INDICADORES, SEGMENTOS, VISTAS, boton_csv, cargar_panel, composicion, descriptivos, fechas_panel, filtrar_vista

st.set_page_config(page_title="Comparativo por segmento | Radar Cooperativo Ecuador", page_icon="📊", layout="wide")
aplicar_tema()
COL = {"SEGMENTO 1": "#2563EB", "SEGMENTO 2": "#F59E0B", "SEGMENTO 3": "#10B981"}

def main():
    render_sidebar(cargar_metadata())
    st.title("📊 Comparación entre segmentos 1, 2 y 3")
    d = cargar_panel()
    if d.empty: st.error("Panel no disponible."); return
    st.sidebar.markdown("### Filtros")
    ind = st.sidebar.selectbox("Indicador", list(INDICADORES), format_func=lambda k: INDICADORES[k][0], key="cmp_ind")
    segs = st.sidebar.multiselect("Segmentos", SEGMENTOS, default=SEGMENTOS, key="cmp_seg")
    fmin, fmax = d.fecha.min().to_pydatetime(), d.fecha.max().to_pydatetime()
    rango = st.sidebar.slider("Período", fmin, fmax, (fmin, fmax), format="MM/YYYY", key="cmp_rango")
    fecha_corte = st.sidebar.selectbox("Fecha para estadísticos", fechas_panel(d), format_func=lambda x: pd.Timestamp(x).strftime("%m/%Y"), key="cmp_fecha")
    vista = st.sidebar.radio("Vista de clasificación", list(VISTAS), key="cmp_vista",
                             help="Principal: clasificación con procedencia y fecha conocidas. Exacta: la asignación corresponde al propio mes. Arrastrada: tomada de otro corte (≤2 meses).")
    x = d[d.segmento_repo.isin(segs) & d.fecha.between(*map(pd.Timestamp, rango))]
    base_sel = x                                    # composición ANTES de aplicar la vista (muestra lo que se excluye)
    x = filtrar_vista(x, vista).dropna(subset=[ind])
    if x.empty: st.warning("Sin datos para la selección."); return
    comp = composicion(base_sel); cA, cB, cC = st.columns(3)
    cA.metric("Clasificación exacta del mes", f"{comp.get('exacto_mes', 0)} %"); cB.metric("Arrastrada de otro corte", f"{comp.get('arrastrado', 0)} %"); cC.metric("Estimada (excluida de las vistas)", f"{comp.get('estimado', 0)} %")
    st.caption(f"Composición de las observaciones del período y segmentos seleccionados. Vista activa: **{vista}** ({len(x):,} observaciones).")
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
    st.dataframe(t, width='stretch', hide_index=True); boton_csv(t, f"descriptivos_{ind}_{pd.Timestamp(fecha_corte):%Y%m}.csv", "dl_desc")
    with st.expander("Serie mostrada (exportable)"):
        st.dataframe(s, width='stretch', hide_index=True); boton_csv(s, f"serie_{ind}.csv", "dl_serie")
main()
