# -*- coding: utf-8 -*-
"""Módulo 18: Perfil de vulnerabilidad, alertas estadísticas internas y ficha por cooperativa."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from ui import aplicar_tema, render_sidebar
from utils.data_loader import cargar_metadata
from utils.panel_vulnerabilidad import INDICADORES, PROCEDENCIA_TXT, SEGMENTOS, boton_csv, cargar_panel, fechas_panel, z_orientado

st.set_page_config(page_title="Vulnerabilidad y ficha | Radar Cooperativo Ecuador", page_icon="🚨", layout="wide")
aplicar_tema()
ALERTA_COLS = ["solvencia_proxy", "liquidez", "morosidad", "cobertura", "roa", "eficiencia"]
UMBRAL_Z = 2.0

@st.cache_data(ttl=3600, show_spinner=False)
def _alertas(fecha) -> pd.DataFrame:
    d = cargar_panel(); d = d[d.fecha == pd.Timestamp(fecha)].reset_index(drop=True)
    # z robusto contra pares del mismo segmento y fecha (umbral ESTADÍSTICO interno, no regulatorio)
    z = z_orientado(d, ALERTA_COLS).add_prefix("z_")
    d = pd.concat([d, z], axis=1)
    d["n_alertas"] = (z >= UMBRAL_Z).sum(axis=1)
    d["indicadores_en_alerta"] = z.apply(lambda r: ", ".join(INDICADORES[c.replace("z_", "")][0] for c in z.columns if r[c] >= UMBRAL_Z), axis=1)
    return d

def main():
    render_sidebar(cargar_metadata())
    st.title("🚨 Perfil de vulnerabilidad y ficha por cooperativa")
    d = cargar_panel()
    if d.empty: st.error("Panel no disponible."); return
    st.warning("**Alcance de las señales.** Las alertas son *desviaciones estadísticas internas* respecto de cooperativas del mismo segmento y fecha "
               f"(z robusto mediana/MAD ≥ {UMBRAL_Z:g} en la dirección adversa). **No son umbrales regulatorios** ni una probabilidad de insolvencia: el modelo de alerta temprana "
               "no es estimable con los eventos disponibles (ver docs/VULNERABILIDAD_MODULO.md).")
    tab1, tab2 = st.tabs(["Alertas por fecha", "Ficha por cooperativa"])
    with tab1:
        f = st.selectbox("Fecha de corte", fechas_panel(d), format_func=lambda x: pd.Timestamp(x).strftime("%m/%Y"), key="v_fecha")
        segs = st.multiselect("Segmentos", SEGMENTOS, default=SEGMENTOS, key="v_segs")
        a = _alertas(f); a = a[a.segmento_repo.isin(segs)]
        min_al = st.slider("Mínimo de indicadores en alerta", 0, 6, 2, key="v_min")
        t = a[a.n_alertas >= min_al].sort_values(["n_alertas", "indice_eq"], ascending=False)
        cols = ["cooperativa", "segmento_repo", "segmento_procedencia", "n_alertas", "indicadores_en_alerta", "indice_eq"] + ALERTA_COLS
        vista = t[cols].round(3).rename(columns={"segmento_repo": "segmento", "indice_eq": "índice vulnerabilidad (pesos iguales)"})
        st.caption(f"{len(vista)} de {len(a)} cooperativas cumplen el filtro. El índice compuesto es **exploratorio** (z pooled, pesos iguales; alto = más vulnerable).")
        st.dataframe(vista, width='stretch', hide_index=True); boton_csv(vista, f"alertas_{pd.Timestamp(f):%Y%m}.csv", "dl_alertas")
    with tab2:
        nombres = sorted(d[d.fecha == d.fecha.max()].cooperativa.unique()) or sorted(d.cooperativa.unique())
        c = st.selectbox("Cooperativa", nombres, key="v_coop")
        x = d[d.cooperativa == c].sort_values("fecha"); ult = x.iloc[-1]
        k1, k2, k3 = st.columns(3)
        k1.metric("Segmento (último corte)", str(ult.segmento_repo).title()); k2.metric("Procedencia del segmento", PROCEDENCIA_TXT.get(ult.segmento_procedencia, "—"))
        k3.metric("Último corte", f"{ult.fecha:%m/%Y}")
        pct_no_ex = (x.segmento_procedencia != "exacto_mes").mean() * 100
        if pct_no_ex > 0: st.info(f"{pct_no_ex:.0f} % de los meses de esta cooperativa tienen segmento arrastrado, estimado o acoplado sin fila propia.")
        ind = st.selectbox("Indicador", list(INDICADORES), format_func=lambda k: INDICADORES[k][0], key="v_ind")
        par = d[d.segmento_repo == ult.segmento_repo].groupby("fecha")[ind].median()
        sis = d.groupby("fecha")[ind].median()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=x.fecha, y=x[ind], name=c[:40], line=dict(width=3)))
        fig.add_trace(go.Scatter(x=par.index, y=par.values, name=f"Mediana {ult.segmento_repo}", line=dict(dash="dash")))
        fig.add_trace(go.Scatter(x=sis.index, y=sis.values, name="Mediana S1–S3", line=dict(dash="dot")))
        fig.update_layout(title=INDICADORES[ind][0], yaxis_title=f"{INDICADORES[ind][0]} ({INDICADORES[ind][1]})", xaxis_title="Fecha de corte", height=430, template="plotly_dark", legend=dict(orientation="h"))
        st.plotly_chart(fig, width='stretch'); st.caption("Fuente: SEPS, cálculo propio. Fórmula: " + INDICADORES[ind][2])
        aa = _alertas(x.fecha.max()); fila = aa[aa.cooperativa == c]
        if not fila.empty and fila.iloc[0].n_alertas > 0: st.error(f"Alertas estadísticas al último corte: {fila.iloc[0].indicadores_en_alerta}")
        else: st.success("Sin alertas estadísticas al último corte (frente a pares del segmento).")
        cols = ["fecha", "segmento_repo", "segmento_procedencia", "activos", "indice_eq"] + list(INDICADORES)
        tabla = x[[c_ for c_ in cols if c_ in x]].round(3); st.dataframe(tabla, width='stretch', hide_index=True); boton_csv(tabla, "ficha_cooperativa.csv", "dl_ficha")
main()
