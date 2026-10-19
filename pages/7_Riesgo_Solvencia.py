# -*- coding: utf-8 -*-
"""
Módulo 7: Riesgo de Solvencia
Capital, patrimonio e indicadores oficiales de vulnerabilidad patrimonial
(FK, FI, CAP_NETO, VULN_PAT, CART_IMPR_PAT) de la SEPS.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

import pandas as pd
import plotly.express as px
import streamlit as st

from analytics.financial_engine import (
    UMBRAL_SOLVENCIA_REGULATORIO,
    ETIQUETAS_SOLVENCIA,
    calcular_patrimonio_sobre_activos,
    evaluar_solvencia_oficial,
)
from ui import (
    aplicar_tema, botones_descarga, exigir_datos, render_filtros_globales, render_resumen_filtro, render_sidebar,
    selector_fecha_corte,
)
from utils.charts import COLORES, crear_radar, crear_ranking_barras
from utils.data_loader import (
    cargar_metadata,
    datos_filtrados,
    obtener_cooperativas_filtro,
)

st.set_page_config(
    page_title="Riesgo de Solvencia | Radar Cooperativo Ecuador",
    page_icon="🏛️",
    layout="wide",
)
aplicar_tema()

_INDICADORES_RADAR = ["FK", "FI", "CAP_NETO", "VULN_PAT", "CART_IMPR_PAT"]
_DIRECCION_RADAR = {"FK": True, "FI": True, "CAP_NETO": True, "VULN_PAT": False, "CART_IMPR_PAT": False}


@st.cache_data(ttl=3600)
def _serie_indicador(df_indicadores: pd.DataFrame, codigo: str) -> pd.DataFrame:
    """Promedio simple mensual del indicador sobre la población filtrada (df ya filtrado) y n.º de entidades."""
    df_f = df_indicadores[df_indicadores["codigo"] == codigo]
    serie = df_f.groupby("fecha", observed=True).agg(valor=("valor", "mean"), entidades=("entidad", "nunique")).reset_index()
    serie["valor_pct"] = serie["valor"] * 100
    return serie.sort_values("fecha")


def _calidad_solvencia(df: pd.DataFrame) -> dict:
    """Resumen de cobertura del boletín FS01 sobre la población filtrada."""
    if df is None or df.empty:
        return {'disponible': False, 'motivo': 'Sin entidades del boletín FS01 en la selección actual (o archivo no generado).'}
    return {
        'disponible': True, 'ruc_unicos': int(df['ruc'].nunique()), 'fecha_min': df['fecha'].min(), 'fecha_max': df['fecha'].max(),
        'discrepancias': int(df['discrepancia_solvencia'].fillna(False).astype(bool).sum()) if 'discrepancia_solvencia' in df.columns else 0,
    }


def main():
    metadata = cargar_metadata()
    render_sidebar(metadata)

    st.title("🏛️ Riesgo de Solvencia")
    st.markdown("Capitalización, patrimonio y vulnerabilidad patrimonial del sistema cooperativo, con indicadores oficiales SEPS.")
    st.caption(
        "Nota metodológica: esta página usa FK, FI, CAP_NETO (FK/FI) y VULN_PAT — indicadores "
        "oficiales de vulnerabilidad patrimonial de la SEPS. **No es el ratio de Solvencia "
        "regulatorio** (Patrimonio Técnico Constituido / Activos Ponderados por Riesgo, mínimo 9% "
        "según la Junta de Política y Regulación Financiera), que requiere el Formulario de "
        "Solvencia (FS01) — fuente que este pipeline no procesa. Detalle en `docs/RIESGO_METODOLOGIA.md`."
    )

    filtro = render_filtros_globales()
    fecha_sel = selector_fecha_corte(filtro)
    df_ind = datos_filtrados("indicadores", filtro)
    df_ranking = datos_filtrados("ranking", filtro)
    render_resumen_filtro(filtro, df_ind[df_ind["fecha"] == fecha_sel] if not df_ind.empty else df_ind,
                          corte=pd.Timestamp(metadata["fecha_max"]), fecha_analisis=fecha_sel)
    exigir_datos(df_ind)

    df_cap_neto = df_ind[(df_ind["codigo"] == "CAP_NETO") & (df_ind["fecha"] == fecha_sel)]

    patrim_activos = calcular_patrimonio_sobre_activos(df_ranking, fecha_sel)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Patrimonio / Activos (sistema)",
                   f"{patrim_activos['patrimonio_sobre_activos'].mean():,.1f}%" if not patrim_activos.empty else "—")
    with col2:
        st.metric("Índice de Capitalización Neto (promedio)",
                   f"{df_cap_neto['valor'].mean() * 100:,.1f}%" if not df_cap_neto.empty else "—")
    with col3:
        bajo_umbral = (df_cap_neto["valor"] < 0.06).sum() if not df_cap_neto.empty else 0
        st.metric("Instituciones con CAP_NETO < 6%", f"{bajo_umbral}")
    with col4:
        st.metric("Instituciones evaluadas", f"{len(patrim_activos)}")

    st.markdown("---")

    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Ranking", "🕸️ Radar por Cooperativa", "📈 Evolución", "🏦 Solvencia Oficial (FS01)",
    ])

    with tab1:
        st.markdown("**Ranking por Patrimonio / Activos**")
        if not patrim_activos.empty:
            df_r = patrim_activos.nlargest(20, "patrimonio_sobre_activos")
            fig = crear_ranking_barras(df_r, x_col="patrimonio_sobre_activos", y_col="cooperativa", formato_valor="{:.1f}%")
            st.plotly_chart(fig, width="stretch")
            with st.expander("Datos del ranking (descarga)"):
                _t = df_r.merge(df_ranking[["cooperativa", "entidad", "procedencia_clasif"]].drop_duplicates("cooperativa"),
                                on="cooperativa", how="left")
                _t.insert(0, "fecha", pd.Timestamp(fecha_sel))
                st.dataframe(_t, width="stretch", hide_index=True)
                botones_descarga(_t, filtro, f"solvencia_ranking_patrimonio_activos_{pd.Timestamp(fecha_sel):%Y%m}",
                                 "Ranking Patrimonio / Activos", "dl_solv_rank", corte=fecha_sel)
        else:
            st.info("Sin datos para esta selección.")

    with tab2:
        _con_ind = set(df_ind.loc[df_ind["fecha"] == fecha_sel, "cooperativa"].astype(str))
        cooperativas = [c for c in obtener_cooperativas_filtro(filtro) if c in _con_ind]
        if cooperativas:
            coop_sel = st.selectbox("Cooperativa", cooperativas, key="coop_radar_solv")

            df_fecha_ind = df_ind[df_ind["fecha"] == fecha_sel]

            valores_coop, valores_sistema = [], []
            for codigo in _INDICADORES_RADAR:
                serie_ind = df_fecha_ind[df_fecha_ind["codigo"] == codigo]
                fila_coop = serie_ind[serie_ind["cooperativa"] == coop_sel]
                if serie_ind.empty:
                    valores_coop.append(0)
                    valores_sistema.append(0)
                    continue
                percentil = serie_ind["valor"].rank(pct=True) * 100
                if not fila_coop.empty:
                    idx = fila_coop.index[0]
                    pct_coop = percentil.loc[idx] if idx in percentil.index else 50
                else:
                    pct_coop = 0
                pct_coop = pct_coop if _DIRECCION_RADAR[codigo] else (100 - pct_coop)
                valores_coop.append(round(float(pct_coop), 1))
                valores_sistema.append(50.0)

            fig = crear_radar(
                _INDICADORES_RADAR,
                {coop_sel: valores_coop, "Mediana del sistema (P50)": valores_sistema},
                titulo="Percentil relativo por indicador (100 = mejor desempeño)",
            )
            st.plotly_chart(fig, width="stretch")
            st.caption(
                "Percentiles calculados dentro de la población filtrada (período, segmentos, entidades y calidad) en la fecha de análisis. "
                "VULN_PAT y CART_IMPR_PAT se invierten (menor valor = mejor, mayor percentil)."
            )
        else:
            st.info("Sin cooperativas con indicadores para la selección.")

    with tab3:
        codigo_evol = st.selectbox(
            "Indicador", _INDICADORES_RADAR,
            format_func=lambda c: ETIQUETAS_SOLVENCIA.get(c, c), key="codigo_evol_solv",
        )
        serie = _serie_indicador(df_ind, codigo_evol)
        if not serie.empty:
            fig = px.line(serie, x="fecha", y="valor_pct", markers=True,
                          labels={"fecha": "Fecha", "valor_pct": f"{codigo_evol} (%)"})
            fig.update_traces(line_color=COLORES["petrol"] if "petrol" in COLORES else COLORES["secundario"])
            fig.update_layout(height=420, hovermode="x unified", paper_bgcolor="rgba(0,0,0,0)",
                               plot_bgcolor="rgba(0,0,0,0)", font_color=COLORES["texto"])
            fig.update_xaxes(gridcolor=COLORES["grid"])
            fig.update_yaxes(gridcolor=COLORES["grid"])
            st.plotly_chart(fig, width="stretch")
            st.caption("Promedio simple de las entidades de la selección en cada mes (la composición puede variar entre meses).")
            with st.expander("Datos de la serie (descarga)"):
                st.dataframe(serie, width="stretch", hide_index=True)
                botones_descarga(serie, filtro, f"solvencia_serie_{codigo_evol}",
                                 f"Serie {codigo_evol} (promedio)", "dl_solv_serie", corte=fecha_sel)
        else:
            st.info("Sin datos suficientes.")

    with tab4:
        df_solv = datos_filtrados("solvencia", filtro)
        calidad_solv = _calidad_solvencia(df_solv)
        if not calidad_solv.get('disponible'):
            st.warning(
                "**No disponible en este despliegue.** El ratio de Solvencia oficial "
                "(Patrimonio Técnico Constituido / Activos Ponderados por Riesgo, "
                "mínimo regulatorio 9%) requiere `master_data/solvencia.parquet`, "
                "generado por `scripts/procesar_solvencia.py` a partir del boletín "
                "SEPS de Patrimonio Técnico. " + calidad_solv.get('motivo', '')
            )
        else:
            st.markdown(
                "**Fuente**: boletín SEPS \"Patrimonio Técnico\" (fichas 58-63 de las "
                "Fichas Metodológicas SEPS v3.0). Es el **único indicador regulatorio "
                "verificado** de esta plataforma — a diferencia de CAP_NETO (FK/FI, "
                "pestañas anteriores), que es un indicador analítico de vulnerabilidad "
                "patrimonial, no el ratio de Solvencia oficial."
            )
            st.caption(
                f"**Cobertura**: Segmento 1, Mutualistas y Caja Central FINANCOOP "
                f"únicamente — la SEPS no publica este boletín para Segmento 2/3. "
                f"{calidad_solv['ruc_unicos']} RUC únicos, "
                f"{calidad_solv['fecha_min']:%b %Y} a {calidad_solv['fecha_max']:%b %Y}."
            )
            if filtro.segmentos:
                st.info(
                    "El boletín FS01 solo cubre Segmento 1, Mutualistas y FINANCOOP: con segmentos 2/3 seleccionados no habrá "
                    "entidades en esta pestaña. Se aplica el mismo filtro global (segmento puntual del período) que al resto."
                )
            if calidad_solv.get('discrepancias'):
                st.caption(
                    f"⚠️ {calidad_solv['discrepancias']} registros donde la Solvencia "
                    f"publicada por la SEPS difiere >0.5pp de PTC/APPR recalculado "
                    f"localmente como control de calidad (se muestra siempre el valor "
                    f"oficial publicado, nunca el recalculado)."
                )

            fechas_solv = sorted(df_solv['fecha'].unique(), reverse=True)
            fecha_solv_sel = st.selectbox(
                "Fecha (boletín Patrimonio Técnico)", fechas_solv,
                format_func=lambda x: pd.Timestamp(x).strftime("%B %Y").title(),
                index=0, key="fecha_solv_oficial",
            )

            df_eval = evaluar_solvencia_oficial(df_solv, fecha_solv_sel)
            if df_eval.empty:
                st.info("Sin datos para la fecha seleccionada.")
            else:
                n_incumple = int((~df_eval['cumple_minimo_regulatorio']).sum())
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Entidades evaluadas", len(df_eval))
                with col2:
                    st.metric("Solvencia promedio", f"{df_eval['solvencia'].mean()*100:.1f}%")
                with col3:
                    st.metric(
                        f"Bajo el mínimo regulatorio ({UMBRAL_SOLVENCIA_REGULATORIO*100:.0f}%)",
                        n_incumple,
                        delta=None if n_incumple == 0 else "requiere revisión",
                        delta_color="inverse",
                    )

                df_tabla = df_eval.copy()
                df_tabla['solvencia'] = (df_tabla['solvencia'] * 100).round(2)
                df_tabla['brecha_pp'] = df_tabla['brecha_pp'].round(2)
                df_tabla = df_tabla.rename(columns={
                    'cooperativa': 'Entidad', 'grupo_fuente': 'Grupo',
                    'solvencia': 'Solvencia (%)', 'cumple_minimo_regulatorio': 'Cumple 9%',
                    'brecha_pp': 'Brecha (pp)',
                })
                st.dataframe(
                    df_tabla[['Entidad', 'Grupo', 'Solvencia (%)', 'Cumple 9%', 'Brecha (pp)']],
                    width="stretch", hide_index=True,
                )
                _exp = df_eval.merge(df_solv[['cooperativa', 'fecha', 'entidad', 'segmento', 'procedencia_clasif']],
                                     on=['cooperativa', 'fecha'], how='left') if 'fecha' in df_eval.columns else df_eval
                botones_descarga(_exp, filtro, f"solvencia_fs01_{pd.Timestamp(fecha_solv_sel):%Y%m}", "Solvencia oficial FS01",
                                 "dl_solv_fs01", corte=fecha_solv_sel)

    st.markdown("---")
    with st.expander("ℹ️ Definiciones"):
        for codigo, etiqueta in ETIQUETAS_SOLVENCIA.items():
            st.markdown(f"- **{codigo}**: {etiqueta}")
        st.markdown(
            f"- **SOLVENCIA (oficial, pestaña FS01)**: Patrimonio Técnico Constituido "
            f"/ Activos Ponderados por Riesgo. Mínimo regulatorio "
            f"{UMBRAL_SOLVENCIA_REGULATORIO*100:.0f}% (JPRF). Cobertura parcial "
            f"(Segmento 1, Mutualistas, FINANCOOP)."
        )


if __name__ == "__main__":
    main()
