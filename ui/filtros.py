# -*- coding: utf-8 -*-
"""
Filtros globales de la plataforma — UN solo bloque en la barra lateral, común a TODAS las páginas.

    Datos visibles = período ∩ segmentos ∩ entidades ∩ calidad de la clasificación

Cada página llama una vez a `render_filtros_globales()` (devuelve un `FiltroAnalisis` inmutable) y obtiene sus
datos con `utils.data_loader.datos_filtrados(...)`/`aplicar_filtros_analisis(...)`. No existen selectores de
segmento propios por página.

Persistencia entre páginas
--------------------------
En apps multipágina «clásicas» (`pages/`), Streamlit descarta el estado de un widget al cambiar de página aunque
comparta `key`. Solo las claves PLANAS de `st.session_state` (no atadas a un widget) sobreviven. Por eso el estado
canónico vive en claves planas `sps_f_*` y cada widget usa una clave «sombra» `_w_*` que se hidrata desde la plana al
inicio de cada render y se copia de vuelta en `on_change`.

Consistencia
------------
Si un cambio de segmento/período/calidad invalida entidades ya seleccionadas, se conservan solo las válidas y se
informa cuáles se descartaron (nunca se descartan en silencio).
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from utils import filtros_analisis as fa
from utils.data_loader import cargar_dim_observaciones, cargar_identificadores

K_INI, K_FIN = "sps_f_fecha_ini", "sps_f_fecha_fin"
K_SEG, K_ENT, K_CAL = "sps_f_segmentos", "sps_f_entidades", "sps_f_calidad"
K_FECHA = "sps_f_fecha_corte"
K_AVISO = "_sps_f_aviso"
SPS_SEGMENTO_KEY = K_SEG   # compatibilidad de nombre con la API anterior

W_INI, W_FIN, W_SEG, W_CAL, W_ENT, W_BUSCA = "_w_desde", "_w_hasta", "_w_segmentos", "_w_calidad", "_w_entidades", "_w_busca"
W_FECHA = "_w_fecha_corte"


def _fmt_mes(t) -> str:
    return pd.Timestamp(t).strftime("%m/%Y")


def estado_inicial(dim: pd.DataFrame) -> dict:
    d = fa.filtro_por_defecto(dim)
    return {K_INI: d.fecha_ini, K_FIN: d.fecha_fin, K_SEG: [], K_ENT: [], K_CAL: "todas"}


def _asegurar_estado(dim: pd.DataFrame) -> None:
    for k, v in estado_inicial(dim).items():
        st.session_state.setdefault(k, v)


def filtro_actual(dim: pd.DataFrame | None = None) -> fa.FiltroAnalisis:
    """Filtro vigente según el estado de sesión (sin dibujar widgets)."""
    dim = cargar_dim_observaciones() if dim is None else dim
    _asegurar_estado(dim)
    return fa.FiltroAnalisis(st.session_state[K_INI], st.session_state[K_FIN], tuple(st.session_state[K_SEG]),
                             tuple(st.session_state[K_ENT]), st.session_state[K_CAL])


# ----------------------------------------------------------------------------- callbacks
def _guardar_ini():
    ini = pd.Timestamp(st.session_state[W_INI])
    st.session_state[K_INI] = ini
    if ini > pd.Timestamp(st.session_state[K_FIN]):
        st.session_state[K_FIN] = ini            # el rango nunca queda invertido


def _guardar_fin():
    fin = pd.Timestamp(st.session_state[W_FIN])
    st.session_state[K_FIN] = fin
    if fin < pd.Timestamp(st.session_state[K_INI]):
        st.session_state[K_INI] = fin


def _guardar_seg():
    st.session_state[K_SEG] = list(st.session_state[W_SEG])


def _guardar_cal():
    st.session_state[K_CAL] = st.session_state[W_CAL]


def _guardar_ent():
    # Conserva las seleccionadas que el buscador oculta: el multiselect solo muestra las coincidencias.
    visibles = set(st.session_state.get("_ent_visibles", []))
    previas = [e for e in st.session_state.get(K_ENT, []) if e not in visibles]
    st.session_state[K_ENT] = previas + list(st.session_state[W_ENT])


def restablecer_filtros() -> None:
    """Devuelve TODOS los filtros a sus valores predeterminados (callback del botón)."""
    dim = cargar_dim_observaciones()
    for k, v in estado_inicial(dim).items():
        st.session_state[k] = v
    for k in (W_INI, W_FIN, W_SEG, W_CAL, W_ENT, W_BUSCA, W_FECHA, K_FECHA):
        st.session_state.pop(k, None)
    st.session_state.pop(K_AVISO, None)


def _todas_visibles():
    st.session_state[K_ENT] = list(st.session_state.get("_ent_visibles", []))
    st.session_state.pop(W_ENT, None)


def _limpiar_entidades():
    st.session_state[K_ENT] = []
    st.session_state.pop(W_ENT, None)


# ----------------------------------------------------------------------------- render
def render_filtros_globales(*, mostrar_calidad: bool = True) -> fa.FiltroAnalisis:
    """Dibuja el bloque de filtros en la barra lateral y devuelve el filtro vigente (validado)."""
    dim = cargar_dim_observaciones()
    sb = st.sidebar
    sb.markdown("### Filtros globales")
    if dim is None or dim.empty:
        sb.error("No hay dimensión de observaciones (master_data/dim_observaciones.parquet).")
        return fa.FiltroAnalisis()
    _asegurar_estado(dim)

    fechas = [pd.Timestamp(x) for x in fa.fechas_disponibles(dim)]
    ini = min(max(pd.Timestamp(st.session_state[K_INI]), fechas[0]), fechas[-1])
    fin = min(max(pd.Timestamp(st.session_state[K_FIN]), fechas[0]), fechas[-1])
    if ini > fin:
        ini, fin = fechas[0], fechas[-1]
    # snap a las fechas disponibles
    ini = next((f for f in fechas if f >= ini), fechas[0]); fin = max((f for f in fechas if f <= fin), default=fechas[-1])
    st.session_state[K_INI], st.session_state[K_FIN] = ini, fin

    # ---- período (solo meses con datos)
    st.session_state[W_INI], st.session_state[W_FIN] = ini, fin
    c_ini, c_fin = sb.columns(2)
    c_ini.selectbox("Desde", fechas, key=W_INI, format_func=_fmt_mes, on_change=_guardar_ini,
                    help="Primer mes del período de análisis. Solo se ofrecen meses con datos.")
    c_fin.selectbox("Hasta", fechas, key=W_FIN, format_func=_fmt_mes, on_change=_guardar_fin,
                    help="Último mes del período. Todos los resultados se calculan dentro de este rango.")
    ini, fin = pd.Timestamp(st.session_state[K_INI]), pd.Timestamp(st.session_state[K_FIN])
    sb.caption(f"Corte máximo de información: **{_fmt_mes(fechas[-1])}**")

    # ---- segmentos (clasificación puntual del período)
    segs = fa.segmentos_disponibles(dim)
    st.session_state[K_SEG] = [s for s in st.session_state[K_SEG] if s in segs]
    st.session_state[W_SEG] = list(st.session_state[K_SEG])
    sb.multiselect("Segmentos", options=segs, key=W_SEG, on_change=_guardar_seg, placeholder="Todos los segmentos",
                   help="Clasificación vigente EN CADA PERÍODO (no el segmento actual). Sin selección = todos.")

    # ---- calidad de la clasificación
    if mostrar_calidad:
        cal_keys = list(fa.CALIDADES)
        if st.session_state[K_CAL] not in cal_keys:
            st.session_state[K_CAL] = "todas"
        st.session_state[W_CAL] = st.session_state[K_CAL]
        sb.selectbox("Calidad de la clasificación", cal_keys, key=W_CAL, on_change=_guardar_cal,
                     format_func=lambda k: fa.CALIDADES[k][0],
                     help="Oficial: segmento publicado por la SEPS para ese mes. Arrastrada: del último corte trimestral "
                          "(≤2 meses). Estimada: backfill sin archivo del período.")

    # ---- entidades (dependen de período ∩ segmentos ∩ calidad)
    base = fa.FiltroAnalisis(ini, fin, tuple(st.session_state[K_SEG]), (), st.session_state[K_CAL])
    disponibles = fa.entidades_disponibles(dim, base)
    validas, descartadas = fa.reconciliar_entidades(st.session_state[K_ENT], disponibles)
    if descartadas:
        st.session_state[K_AVISO] = descartadas
    st.session_state[K_ENT] = validas

    busca = sb.text_input("Buscar entidad (nombre o RUC)", key=W_BUSCA, placeholder="Ej. JARDIN o 0190…")
    ruc = cargar_identificadores()
    if busca:
        q = busca.strip().upper()
        opciones = [e for e in disponibles if q in e.upper() or q in ruc.get(e, "")]
    else:
        opciones = list(disponibles)
    st.session_state["_ent_visibles"] = list(opciones)
    mostrar = [e for e in validas if e in opciones]
    st.session_state[W_ENT] = mostrar
    sb.multiselect(f"Entidades ({len(disponibles)} compatibles)", options=opciones, key=W_ENT, on_change=_guardar_ent,
                   placeholder="Todas las compatibles",
                   help="Sin selección = todas las entidades compatibles con el resto de filtros.")
    c1, c2 = sb.columns(2)
    c1.button("Todas las visibles", key="_btn_todas", on_click=_todas_visibles, width="stretch")
    c2.button("Limpiar", key="_btn_limpiar", on_click=_limpiar_entidades, width="stretch")
    aviso = st.session_state.pop(K_AVISO, None)
    if aviso:
        sb.info("Se quitó de la selección por no cumplir los filtros vigentes: " + "; ".join(aviso))
    sb.button("↺ Restablecer filtros", key="_btn_reset", on_click=restablecer_filtros, width="stretch")

    return fa.FiltroAnalisis(ini, fin, tuple(st.session_state[K_SEG]), tuple(st.session_state[K_ENT]), st.session_state[K_CAL])


def selector_fecha_corte(filtro: fa.FiltroAnalisis, etiqueta: str = "Fecha de análisis (corte)") -> pd.Timestamp:
    """Una sola fecha para las vistas de «foto». Restringida al período y a meses con datos para la selección."""
    dim = cargar_dim_observaciones()
    vis = fa.observaciones_visibles(dim, filtro)
    fechas = sorted(pd.to_datetime(vis["fecha"]).unique(), reverse=True)
    if not fechas:
        st.sidebar.warning("La combinación de filtros no tiene observaciones.")
        return pd.Timestamp(filtro.fecha_fin) if filtro.fecha_fin is not None else pd.Timestamp.today()
    actual = st.session_state.get(K_FECHA)
    if actual is None or pd.Timestamp(actual) not in set(map(pd.Timestamp, fechas)):
        actual = fechas[0]          # por defecto, el último mes con datos dentro de la selección
    st.session_state[K_FECHA] = pd.Timestamp(actual)
    st.session_state[W_FECHA] = pd.Timestamp(actual)
    sel = st.sidebar.selectbox(etiqueta, fechas, key=W_FECHA, format_func=_fmt_mes,
                               on_change=lambda: st.session_state.__setitem__(K_FECHA, pd.Timestamp(st.session_state[W_FECHA])))
    return pd.Timestamp(sel)


# ----------------------------------------------------------------------------- resumen visible en cada página
def render_resumen_filtro(filtro: fa.FiltroAnalisis, df: pd.DataFrame | None = None, *, corte=None,
                          col_entidad: str = "entidad", fecha_analisis=None) -> dict:
    """Banda discreta con la población sobre la que se calcula la página. Devuelve el resumen (para pruebas/exportación)."""
    dim = cargar_dim_observaciones()
    corte = corte if corte is not None else dim["fecha"].max()
    r = fa.resumen_poblacion(df, dim, filtro, corte, col_entidad=col_entidad)
    cov = r["cobertura"]
    extra = f" · Fecha de análisis <b>{fa._mes(fecha_analisis)}</b>" if fecha_analisis is not None else ""
    st.markdown(
        f"<div style='font-size:0.78rem;padding:6px 10px;border:1px solid var(--sps-border,#ddd);border-radius:6px;"
        f"margin-bottom:8px'>🔎 <b>Selección activa</b> — Período <b>{r['periodo']}</b>{extra} · Segmentos <b>{r['segmentos']}</b> · "
        f"Entidades <b>{r['entidades_usadas']}</b> · Observaciones entidad-mes <b>{r['observaciones_usadas']:,}</b> · "
        f"Corte de datos <b>{r['corte']}</b> · Clasificación: <b>{r['calidad']}</b></div>", unsafe_allow_html=True)
    with st.expander("Cobertura de la clasificación histórica de la selección", expanded=False):
        comp = pd.DataFrame({"Procedencia del segmento": [fa.PROCEDENCIA_ETIQUETA[k] for k in cov["composicion"]],
                             "Observaciones": list(cov["composicion"].values())})
        tot = max(comp["Observaciones"].sum(), 1)
        comp["% de la selección"] = (comp["Observaciones"] / tot * 100).round(1)
        st.dataframe(comp, hide_index=True, width="stretch")
        st.caption(f"Oficial del período: {cov['pct_oficial']:.1f} % de las observaciones. "
                   "Las clasificaciones arrastradas, estimadas o no verificables se identifican como tales; ninguna se reconstruye con el segmento actual.")
        if filtro.calidad != "todas":
            st.warning(f"El criterio «{fa.CALIDADES[filtro.calidad][0]}» excluye {cov['obs_excluidas_por_calidad']:,} observaciones "
                       f"({cov['entidades_excluidas_por_calidad']} entidades quedan sin datos) respecto de la selección sin ese criterio.")
    return r


def exigir_datos(df: pd.DataFrame | None, mensaje: str | None = None) -> None:
    """Si la combinación elegida no tiene observaciones, informa con claridad y detiene la página (sin gráficos vacíos)."""
    if df is None or len(df) == 0:
        st.warning(mensaje or "La combinación de filtros elegida no tiene observaciones. Amplíe el período, los segmentos "
                              "o la calidad de la clasificación, o use «Restablecer filtros».")
        st.stop()


def botones_descarga(df: pd.DataFrame, filtro: fa.FiltroAnalisis, nombre: str, titulo: str, key: str, corte=None) -> None:
    """CSV y Excel de EXACTAMENTE la tabla mostrada, con el filtro activo y el corte como metadatos."""
    dim = cargar_dim_observaciones()
    corte = corte if corte is not None else dim["fecha"].max()
    pob = {"entidades_usadas": int(df["entidad"].nunique()) if "entidad" in df.columns and df["entidad"].notna().any() else None,
           "observaciones_usadas": len(df)}
    c1, c2 = st.columns(2)
    c1.download_button("⬇️ CSV (filtros aplicados)", fa.exportar_csv(df, filtro, corte, titulo, pob), file_name=f"{nombre}.csv",
                       mime="text/csv", key=f"{key}_csv")
    c2.download_button("⬇️ Excel (filtros aplicados)", fa.exportar_excel(df, filtro, corte, titulo, pob), file_name=f"{nombre}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"{key}_xlsx")


def multiselect_validado(label: str, options, default=None, key: str = None, **kw):
    """`st.multiselect` que nunca falla ni conserva valores inválidos: si un cambio de filtros dejó fuera alguna opción
    seleccionada, la quita del estado e informa cuáles se descartaron."""
    options = [str(o) for o in options]
    if key is not None and key in st.session_state:
        previas = list(st.session_state[key])
        validas = [v for v in previas if v in options]
        if validas != previas:
            st.info(f"«{label}»: se quitaron por no cumplir los filtros vigentes: " + "; ".join(v for v in previas if v not in options))
            st.session_state[key] = validas
        return st.multiselect(label, options=options, key=key, **kw)
    return st.multiselect(label, options=options, default=[d for d in (default or []) if d in options], key=key, **kw)
