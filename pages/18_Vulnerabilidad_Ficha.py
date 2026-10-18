# -*- coding: utf-8 -*-
"""Módulo 18: Perfil de vulnerabilidad, alertas estadísticas internas (con regla, valor y referencia) y ficha por cooperativa."""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from ui import aplicar_tema, render_sidebar
from utils.data_loader import cargar_metadata
from utils.panel_vulnerabilidad import INDICADORES, PROCEDENCIA_TXT, REGLA_Z, SEGMENTOS, boton_csv, cargar_panel, fechas_panel

st.set_page_config(page_title="Vulnerabilidad y ficha | Radar Cooperativo Ecuador", page_icon="🚨", layout="wide")
aplicar_tema()
ALERTA_COLS = ["solvencia_proxy", "liquidez", "morosidad", "cobertura", "roa", "eficiencia"]
UMBRALES = [1.5, 2.0, 2.5, 3.0]

@st.cache_data(ttl=3600, show_spinner=False)
def _z_largo(fecha) -> pd.DataFrame:
    """Tabla larga (cooperativa, indicador) con valor, mediana de pares, MAD, z robusto orientado y n de pares. Una sola vez por fecha."""
    d = cargar_panel(); d = d[d.fecha == pd.Timestamp(fecha)]
    filas = []
    for c in ALERTA_COLS:
        g = d.groupby("segmento_repo")[c]
        med = g.transform("median"); mad = g.transform(lambda x: (x - x.median()).abs().median()) * 1.4826; n = g.transform("count")
        z = (d[c] - med) / mad.replace(0, np.nan); z = z if INDICADORES[c][3] else -z
        filas.append(pd.DataFrame({"cooperativa": d.cooperativa, "segmento": d.segmento_repo, "procedencia_segmento": d.segmento_procedencia.map(PROCEDENCIA_TXT),
                                   "periodo": pd.Timestamp(fecha).strftime("%m/%Y"), "indicador_codigo": c, "indicador": INDICADORES[c][0], "valor_observado": d[c],
                                   "referencia_mediana_pares": med, "n_pares": n, "z_robusto_adverso": z}))
    return pd.concat(filas, ignore_index=True)

def _resumen(largo: pd.DataFrame, umbral: float, pan: pd.DataFrame) -> pd.DataFrame:
    a = largo[largo.z_robusto_adverso >= umbral]
    r = a.groupby("cooperativa").agg(n_alertas=("indicador", "size"), indicadores_en_alerta=("indicador", lambda s: ", ".join(s))).reset_index()
    r = pan[["cooperativa", "segmento_repo", "segmento_procedencia", "indice_eq", "patrimonio_negativo"]].merge(r, on="cooperativa", how="left")
    r["n_alertas"] = r.n_alertas.fillna(0).astype(int); r["indicadores_en_alerta"] = r.indicadores_en_alerta.fillna("")
    return r

def main():
    render_sidebar(cargar_metadata())
    st.title("🚨 Perfil de vulnerabilidad y ficha por cooperativa")
    d = cargar_panel()
    if d.empty: st.error("Panel no disponible."); return
    st.warning("**Alcance de las señales.** Las alertas son *desviaciones estadísticas internas* respecto de cooperativas del mismo segmento y fecha. "
               "**No son umbrales regulatorios** ni una probabilidad de insolvencia o quiebra: no existe un modelo predictivo validado "
               "(ver docs/VULNERABILIDAD_MODULO.md). La única regla no estadística es *patrimonio total negativo* (A − P < 0), una condición contable observable.")
    tab1, tab2 = st.tabs(["Alertas por fecha", "Ficha por cooperativa"])
    with tab1:
        f = st.selectbox("Fecha de corte", fechas_panel(d), format_func=lambda x: pd.Timestamp(x).strftime("%m/%Y"), key="v_fecha")
        segs = st.multiselect("Segmentos", SEGMENTOS, default=SEGMENTOS, key="v_segs")
        umbral = st.select_slider("Umbral interno de z robusto", options=UMBRALES, value=2.0, key="v_umbral")
        st.caption("Regla: " + REGLA_Z + f" ≥ {umbral:g}.")
        pan = d[d.fecha == pd.Timestamp(f)]; largo = _z_largo(f)
        res = _resumen(largo, umbral, pan); res = res[res.segmento_repo.isin(segs)]
        min_al = st.slider("Mínimo de indicadores en alerta", 0, 6, 1, key="v_min")
        t = res[(res.n_alertas >= min_al) | res.patrimonio_negativo].sort_values(["patrimonio_negativo", "n_alertas", "indice_eq"], ascending=False)
        vista = t.assign(segmento_procedencia=t.segmento_procedencia.map(PROCEDENCIA_TXT), patrimonio_negativo=t.patrimonio_negativo.map({True: "SÍ", False: ""})
                         ).rename(columns={"segmento_repo": "segmento", "indice_eq": "índice vulnerabilidad (exploratorio)"}).round(3)
        st.caption(f"{len(vista)} de {len(res)} cooperativas cumplen el filtro (incluye siempre las de patrimonio negativo). El índice compuesto es exploratorio (z pooled, pesos iguales; alto = más vulnerable).")
        st.dataframe(vista, width="stretch", hide_index=True); boton_csv(vista, f"alertas_resumen_{pd.Timestamp(f):%Y%m}.csv", "dl_alertas")
        with st.expander("Detalle de cada alerta: indicador, valor observado, referencia y regla"):
            det = largo[(largo.z_robusto_adverso >= umbral) & largo.segmento.isin(segs)].copy()
            det["regla_activada"] = f"z_robusto ≥ {umbral:g} (adverso)"; det["limitaciones"] = "Desviación vs. pares; no es umbral regulatorio ni probabilidad de insolvencia"
            det = det.sort_values("z_robusto_adverso", ascending=False).round(3)
            st.dataframe(det, width="stretch", hide_index=True); boton_csv(det, f"alertas_detalle_{pd.Timestamp(f):%Y%m}.csv", "dl_alertas_det")
        with st.expander("Sensibilidad del número de alertas al umbral"):
            sens = pd.DataFrame([{"umbral_z": u, "cooperativas_con_>=1_alerta": int((_resumen(largo, u, pan).query("segmento_repo in @segs").n_alertas >= 1).sum()),
                                  "alertas_totales": int(((largo.z_robusto_adverso >= u) & largo.segmento.isin(segs)).sum())} for u in UMBRALES])
            st.dataframe(sens, width="stretch", hide_index=True); boton_csv(sens, "sensibilidad_umbral.csv", "dl_sens")
            st.caption("El número de señales es muy sensible al umbral: cualquier lista de alertas depende de esa elección interna y no de un criterio regulatorio.")
    with tab2:
        nombres = sorted(d[d.fecha == d.fecha.max()].cooperativa.unique()) or sorted(d.cooperativa.unique())
        c = st.selectbox("Cooperativa", nombres, key="v_coop")
        x = d[d.cooperativa == c].sort_values("fecha"); ult = x.iloc[-1]
        k1, k2, k3 = st.columns(3)
        k1.metric("Segmento (último corte)", str(ult.segmento_repo).title()); k2.metric("Procedencia del segmento", PROCEDENCIA_TXT.get(ult.segmento_procedencia, "—"))
        k3.metric("Último corte", f"{ult.fecha:%m/%Y}")
        pct_no_ex = (x.segmento_procedencia != "exacto_mes").mean() * 100
        if pct_no_ex > 0: st.info(f"{pct_no_ex:.0f} % de los meses de esta cooperativa tienen segmento arrastrado o estimado.")
        if x.patrimonio_negativo.any(): st.error(f"Patrimonio total negativo en {int(x.patrimonio_negativo.sum())} mes(es) (A − P < 0).")
        if x.en_liquidacion_nombre.any(): st.warning(f"Aparece con el sufijo «EN LIQUIDACION» desde {x[x.en_liquidacion_nombre].fecha.min():%m/%Y} (nombre de la fuente SEPS).")
        ind = st.selectbox("Indicador", list(INDICADORES), format_func=lambda k: INDICADORES[k][0], key="v_ind")
        par = d[d.segmento_repo == ult.segmento_repo].groupby("fecha")[ind].median(); sis = d.groupby("fecha")[ind].median()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=x.fecha, y=x[ind], name=c[:40], line=dict(width=3)))
        fig.add_trace(go.Scatter(x=par.index, y=par.values, name=f"Mediana {ult.segmento_repo}", line=dict(dash="dash")))
        fig.add_trace(go.Scatter(x=sis.index, y=sis.values, name="Mediana S1–S3", line=dict(dash="dot")))
        fig.update_layout(title=INDICADORES[ind][0], yaxis_title=f"{INDICADORES[ind][0]} ({INDICADORES[ind][1]})", xaxis_title="Fecha de corte", height=430, template="plotly_dark", legend=dict(orientation="h"))
        st.plotly_chart(fig, width="stretch"); st.caption("Fuente: SEPS, cálculo propio. Fórmula: " + INDICADORES[ind][2])
        lf = _z_largo(x.fecha.max()); fila = lf[(lf.cooperativa == c) & (lf.z_robusto_adverso >= 2.0)]
        if len(fila): st.error("Alertas estadísticas al último corte (z ≥ 2,0): " + ", ".join(fila.indicador))
        else: st.success("Sin alertas estadísticas (z ≥ 2,0) al último corte frente a pares del segmento.")
        cols = ["fecha", "segmento_repo", "segmento_procedencia", "activos", "indice_eq", "patrimonio_negativo"] + list(INDICADORES)
        tabla = x[[c_ for c_ in cols if c_ in x]].round(3); st.dataframe(tabla, width="stretch", hide_index=True); boton_csv(tabla, "ficha_cooperativa.csv", "dl_ficha")
main()
