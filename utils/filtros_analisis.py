# -*- coding: utf-8 -*-
"""
Lógica ÚNICA de filtrado de la plataforma (sin dependencias de Streamlit: se prueba de forma aislada).

    Datos visibles = período ∩ segmentos ∩ entidades ∩ criterio de calidad de la clasificación

Convenciones
------------
* Vacío = sin restricción. `segmentos=()` incluye todos los segmentos; `entidades=()` incluye todas las
  entidades compatibles con los demás filtros (regla 1 y 2 del requisito).
* El segmento que filtra es la clasificación PUNTUAL del período (`segmento_clasif`, que viene de
  `segmento_historico`), NUNCA el segmento actual aplicado retroactivamente. Una observación sin
  clasificación verificable (`procedencia_clasif == "no_verificable"`, `segmento_clasif` nulo) no cumple
  ninguna restricción de segmento: no se le asigna un segmento sin evidencia.
* La entidad se identifica por `entidad` (nombre sin el sufijo «EN LIQUIDACION»). Cada base trae su propio
  nombre de fuente (`cooperativa`); la dimensión de observaciones los vincula.
* La unión con la dimensión es siempre muchos-a-uno y se verifica que no cambie el número de filas
  (no puede producir duplicados).
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field, replace
from typing import Iterable, Optional, Sequence

import pandas as pd

# calidad -> (etiqueta visible, valores de procedencia_clasif admitidos; None = sin restricción)
CALIDADES = {
    "todas": ("Todas las clasificaciones disponibles", None),
    "oficial": ("Solo oficial del período", ("oficial_mes",)),
    "arrastrada": ("Solo arrastrada de otro corte", ("arrastrado",)),
    "estimada": ("Solo estimada", ("estimado",)),
    "no_verificable": ("Solo no verificable", ("no_verificable",)),
}
PROCEDENCIA_ETIQUETA = {
    "oficial_mes": "Oficial del mes (archivo SEPS del propio período)",
    "arrastrado": "Arrastrada del último corte trimestral (≤2 meses)",
    "estimado": "Estimada (backfill, sin archivo del período)",
    "no_verificable": "No verificable (sin respaldo; sin segmento asignado)",
}
COLUMNAS_CLASIFICACION = ["entidad", "segmento_clasif", "procedencia_clasif"]


@dataclass(frozen=True)
class FiltroAnalisis:
    """Estado de filtros. Inmutable y hashable (sirve como clave de caché)."""
    fecha_ini: Optional[pd.Timestamp] = None
    fecha_fin: Optional[pd.Timestamp] = None
    segmentos: tuple = ()
    entidades: tuple = ()
    calidad: str = "todas"

    def __post_init__(self):
        if self.calidad not in CALIDADES:
            raise ValueError(f"calidad desconocida: {self.calidad!r}")
        object.__setattr__(self, "segmentos", tuple(sorted(set(map(str, self.segmentos)))))
        object.__setattr__(self, "entidades", tuple(sorted(set(map(str, self.entidades)))))
        for c in ("fecha_ini", "fecha_fin"):
            v = getattr(self, c)
            if v is not None:
                object.__setattr__(self, c, pd.Timestamp(v))

    def con(self, **cambios) -> "FiltroAnalisis":
        return replace(self, **cambios)

    def sin_entidades(self) -> "FiltroAnalisis":
        return replace(self, entidades=())

    def a_tupla(self) -> tuple:
        """Representación estable y hashable (argumento de funciones con st.cache_data)."""
        f = lambda t: None if t is None else pd.Timestamp(t).isoformat()
        return (f(self.fecha_ini), f(self.fecha_fin), self.segmentos, self.entidades, self.calidad)

    @classmethod
    def desde_tupla(cls, t: tuple) -> "FiltroAnalisis":
        return cls(t[0], t[1], t[2], t[3], t[4])

    def descripcion(self) -> str:
        p = f"{_mes(self.fecha_ini)} – {_mes(self.fecha_fin)}"
        s = ", ".join(_corto(x) for x in self.segmentos) if self.segmentos else "todos"
        e = f"{len(self.entidades)} seleccionada(s)" if self.entidades else "todas las compatibles"
        return f"Período {p} · Segmentos: {s} · Entidades: {e} · Clasificación: {CALIDADES[self.calidad][0]}"


def _mes(t) -> str:
    return "—" if t is None else pd.Timestamp(t).strftime("%m/%Y")


def _corto(seg: str) -> str:
    return str(seg).replace("SEGMENTO", "S").replace("MUTUALISTA", "Mut.")


def segmentos_disponibles(dim: pd.DataFrame) -> list:
    """Segmentos con clasificación verificable en los datos, ordenados."""
    return sorted(dim["segmento_clasif"].dropna().astype(str).unique())


def fechas_disponibles(dim: pd.DataFrame) -> list:
    return sorted(pd.to_datetime(dim["fecha"]).unique())


def filtro_por_defecto(dim: pd.DataFrame) -> FiltroAnalisis:
    f = fechas_disponibles(dim)
    return FiltroAnalisis(fecha_ini=f[0] if f else None, fecha_fin=f[-1] if f else None)


# --------------------------------------------------------------------------------------------------
# Núcleo: máscara sobre la dimensión de observaciones
# --------------------------------------------------------------------------------------------------
def _mascara(dim: pd.DataFrame, filtro: FiltroAnalisis, *, con_entidades: bool = True,
             con_calidad: bool = True, con_segmentos: bool = True, con_periodo: bool = True) -> pd.Series:
    m = pd.Series(True, index=dim.index)
    if con_periodo:
        if filtro.fecha_ini is not None:
            m &= dim["fecha"] >= filtro.fecha_ini
        if filtro.fecha_fin is not None:
            m &= dim["fecha"] <= filtro.fecha_fin
    if con_segmentos and filtro.segmentos:
        m &= dim["segmento_clasif"].astype(object).isin(filtro.segmentos)      # nulo -> False
    if con_entidades and filtro.entidades:
        m &= dim["entidad"].astype(object).isin(filtro.entidades)
    if con_calidad:
        admitidas = CALIDADES[filtro.calidad][1]
        if admitidas is not None:
            m &= dim["procedencia_clasif"].astype(object).isin(admitidas)
    return m


def observaciones_visibles(dim: pd.DataFrame, filtro: FiltroAnalisis) -> pd.DataFrame:
    """Pares (cooperativa, fecha) que cumplen TODOS los filtros, con su clasificación."""
    return dim.loc[_mascara(dim, filtro), ["cooperativa", "fecha", *COLUMNAS_CLASIFICACION]]


def entidades_disponibles(dim: pd.DataFrame, filtro: FiltroAnalisis) -> list:
    """Entidades con al menos una observación en período ∩ segmentos ∩ calidad (ignora la selección de entidades)."""
    sub = dim.loc[_mascara(dim, filtro, con_entidades=False), "entidad"]
    return sorted(sub.astype(str).unique())


def reconciliar_entidades(seleccionadas: Iterable[str], disponibles: Iterable[str]) -> tuple[list, list]:
    """(válidas, descartadas): conserva solo las selecciones que siguen siendo compatibles."""
    disp = set(map(str, disponibles))
    sel = list(dict.fromkeys(map(str, seleccionadas)))
    return [e for e in sel if e in disp], [e for e in sel if e not in disp]


def segmentos_de_entidad(dim: pd.DataFrame, entidad: str) -> list:
    """Historia de clasificación de una entidad (para mostrar cambios de segmento)."""
    d = dim[dim["entidad"].astype(str) == str(entidad)].sort_values("fecha")
    return d[["fecha", "segmento_clasif", "procedencia_clasif"]].assign(
        segmento_clasif=lambda x: x["segmento_clasif"].astype(object)).values.tolist()


# --------------------------------------------------------------------------------------------------
# Aplicación sobre cualquier base
# --------------------------------------------------------------------------------------------------
def aplicar_filtros_analisis(datos: pd.DataFrame, filtro: FiltroAnalisis, dim: pd.DataFrame, *,
                             col_fecha: str = "fecha", col_entidad: str = "cooperativa",
                             conservar_clasificacion: bool = True) -> pd.DataFrame:
    """
    Devuelve las filas de `datos` que cumplen período ∩ segmentos ∩ entidades ∩ calidad.

    * `col_entidad` es el nombre de fuente de la entidad en `datos` (se une con `dim.cooperativa`).
    * Añade `entidad`, `segmento_clasif` y `procedencia_clasif` (la clasificación puntual y su procedencia)
      salvo `conservar_clasificacion=False`. Si `datos` ya los trae, se reemplazan por los de la dimensión.
    * Filas cuya (entidad, fecha) no existe en la dimensión quedan fuera si hay CUALQUIER restricción de
      segmento, entidad o calidad (no tienen clasificación verificable); sin restricciones se conservan
      solo si el período las admite y se marcan `no_verificable`.
    """
    if datos is None or len(datos) == 0:
        return datos.copy() if datos is not None else pd.DataFrame()
    base = datos.drop(columns=[c for c in COLUMNAS_CLASIFICACION if c in datos.columns])
    # Recorte barato previo (período) antes de la unión.
    f = pd.to_datetime(base[col_fecha])
    pre = pd.Series(True, index=base.index)
    if filtro.fecha_ini is not None:
        pre &= f >= filtro.fecha_ini
    if filtro.fecha_fin is not None:
        pre &= f <= filtro.fecha_fin
    base = base.loc[pre]
    permitidos = observaciones_visibles(dim, filtro)
    restringe = bool(filtro.segmentos or filtro.entidades or CALIDADES[filtro.calidad][1] is not None)
    n0 = len(base)
    k = base[[col_entidad, col_fecha]].copy()
    k["_fila"] = range(len(k))
    k[col_entidad] = k[col_entidad].astype(str)
    k[col_fecha] = pd.to_datetime(k[col_fecha])
    p = permitidos.rename(columns={"cooperativa": col_entidad, "fecha": col_fecha}).copy()
    p[col_entidad] = p[col_entidad].astype(str)
    # `p` tiene clave única por construcción (dimensión sin duplicados) -> la unión no puede multiplicar filas.
    if p.duplicated([col_entidad, col_fecha]).any():
        raise ValueError("la dimensión de observaciones tiene claves duplicadas")
    j = k.merge(p, on=[col_entidad, col_fecha], how="left", validate="many_to_one")
    if len(j) != n0:
        raise AssertionError("la unión con la dimensión alteró el número de filas")
    if restringe:
        mantener = j["procedencia_clasif"].notna().to_numpy()
    else:
        # Sin restricciones: se conservan también las filas ausentes de la dimensión, marcadas no_verificable.
        mantener = pd.Series(True, index=j.index).to_numpy()
        j["procedencia_clasif"] = j["procedencia_clasif"].astype(object).where(j["procedencia_clasif"].notna(), "no_verificable")
    out = base.iloc[j.loc[mantener, "_fila"].to_numpy()].copy()
    if conservar_clasificacion:
        # Categóricas (no object): en bases de millones de filas los strings repetidos ocuparían cientos de MB.
        for c in COLUMNAS_CLASIFICACION:
            out[c] = pd.Categorical(j.loc[mantener, c].astype(object).to_numpy())
    return out.reset_index(drop=True)


# --------------------------------------------------------------------------------------------------
# Resumen y cobertura (lo que se muestra en cada página)
# --------------------------------------------------------------------------------------------------
def cobertura(dim: pd.DataFrame, filtro: FiltroAnalisis) -> dict:
    """Cobertura de la selección sobre la dimensión (observaciones entidad-mes)."""
    sin_calidad = dim.loc[_mascara(dim, filtro, con_calidad=False)]
    con_calidad = dim.loc[_mascara(dim, filtro)]
    comp = (sin_calidad["procedencia_clasif"].astype(str).value_counts()).to_dict()
    return {
        "obs": int(len(con_calidad)),
        "entidades": int(con_calidad["entidad"].nunique()),
        "obs_sin_filtro_calidad": int(len(sin_calidad)),
        "entidades_sin_filtro_calidad": int(sin_calidad["entidad"].nunique()),
        "obs_excluidas_por_calidad": int(len(sin_calidad) - len(con_calidad)),
        "entidades_excluidas_por_calidad": int(sin_calidad["entidad"].nunique() - con_calidad["entidad"].nunique()),
        "composicion": {k: int(comp.get(k, 0)) for k in PROCEDENCIA_ETIQUETA},
        "pct_oficial": float(100 * comp.get("oficial_mes", 0) / max(len(sin_calidad), 1)),
    }


def resumen_poblacion(df: Optional[pd.DataFrame], dim: pd.DataFrame, filtro: FiltroAnalisis, corte,
                      col_entidad: str = "entidad") -> dict:
    """Entidades y observaciones EFECTIVAMENTE usadas (sobre `df` ya filtrado) + datos del filtro activo."""
    cov = cobertura(dim, filtro)
    if df is not None and len(df):
        ent = df[col_entidad if col_entidad in df.columns else "cooperativa"].nunique()
        fcol = "fecha" if "fecha" in df.columns else None
        obs = int(df[[c for c in (col_entidad if col_entidad in df.columns else "cooperativa", fcol) if c]].drop_duplicates().shape[0]) if fcol else len(df)
    else:
        ent, obs = 0, 0
    return {"periodo": f"{_mes(filtro.fecha_ini)} – {_mes(filtro.fecha_fin)}", "corte": _mes(corte),
            "segmentos": ", ".join(filtro.segmentos) if filtro.segmentos else "Todos",
            "entidades_usadas": int(ent), "observaciones_usadas": int(obs),
            "calidad": CALIDADES[filtro.calidad][0], "cobertura": cov, "descripcion": filtro.descripcion()}


# --------------------------------------------------------------------------------------------------
# Exportaciones
# --------------------------------------------------------------------------------------------------
def metadatos_exportacion(filtro: FiltroAnalisis, corte, poblacion: Optional[dict] = None, titulo: str = "") -> list:
    m = [("tabla", titulo), ("corte_de_datos", _mes(corte)), ("periodo", f"{_mes(filtro.fecha_ini)} - {_mes(filtro.fecha_fin)}"),
         ("segmentos", ", ".join(filtro.segmentos) if filtro.segmentos else "todos"),
         ("entidades_seleccionadas", "; ".join(filtro.entidades) if filtro.entidades else "todas las compatibles"),
         ("calidad_clasificacion", CALIDADES[filtro.calidad][0]),
         ("campo_segmento", "segmento_clasif = clasificacion puntual del periodo (segmento_historico); procedencia en procedencia_clasif")]
    if poblacion:
        m += [("entidades_en_tabla", poblacion.get("entidades_usadas")), ("observaciones_en_tabla", poblacion.get("observaciones_usadas"))]
    return m


def exportar_csv(df: pd.DataFrame, filtro: FiltroAnalisis, corte, titulo: str = "", poblacion: Optional[dict] = None) -> bytes:
    """CSV UTF-8 (BOM). Las primeras líneas, con prefijo «# », identifican filtro y corte; el resto es EXACTAMENTE la
    tabla mostrada (`pd.read_csv(..., comment="#")` la reconstruye sin pérdida)."""
    cab = "".join(f"# {k}: {v}\n" for k, v in metadatos_exportacion(filtro, corte, poblacion, titulo))
    return (cab + df.to_csv(index=False)).encode("utf-8-sig")


def exportar_excel(df: pd.DataFrame, filtro: FiltroAnalisis, corte, titulo: str = "datos",
                   poblacion: Optional[dict] = None) -> bytes:
    """Excel con la hoja `datos` (la tabla mostrada) y la hoja `filtros` (filtro activo y corte)."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="datos", index=False)
        pd.DataFrame(metadatos_exportacion(filtro, corte, poblacion, titulo), columns=["parametro", "valor"]).to_excel(
            w, sheet_name="filtros", index=False)
    return buf.getvalue()
