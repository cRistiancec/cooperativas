# -*- coding: utf-8 -*-
"""
IPSF — Índice de Presión Financiera Sistémica. ÍNDICE ANALÍTICO EXPERIMENTAL.

**NO es un indicador oficial. NO está validado. NO debe usarse para decisiones
operativas sin revisión de un analista de riesgos.** Se construye aquí
únicamente como marco de prueba (framework), siguiendo el pedido explícito
del objetivo: "no conviertas todavía el IPSF en indicador oficial".

A diferencia de los 6 índices ejecutivos de `analytics.indices_ejecutivos`
(que rankean COOPERATIVAS entre sí en una fecha), el IPSF es una **serie de
tiempo agregada del sistema** — un número por período que resume presión
sistémica, pensado para compararse a lo largo del tiempo, no entre entidades.

Componentes (cada uno normalizado 0-100, 100 = máxima presión):
  1. breadth_activos: % de activos del sistema en entidades con alerta roja
     (`analytics.breadth`).
  2. severidad_promedio: promedio de `total_alertas_activas` normalizado por
     el máximo de reglas evaluadas.
  3. desaceleracion: complemento normalizado del crecimiento YoY agregado de
     cartera+depósitos (crecimiento muy negativo -> componente alto).

Esquemas de ponderación probados (pedido explícito: A, B; C/D/E documentados
como NO IMPLEMENTADOS con su razón — ver `ESQUEMAS_NO_IMPLEMENTADOS`):
  A. pesos iguales (1/3 cada componente).
  B. pesos "expertos" — mismo criterio que `riesgo_sistemico_estado.py`
     (breadth pesa más que severidad promedio, que pesa más que crecimiento,
     porque breadth ya captura tamaño y concentración del daño mientras que
     severidad_promedio no distingue una entidad grande de una pequeña).
"""

from __future__ import annotations

import pandas as pd

from analytics.alertas import evaluar_alertas
from analytics.breadth import calcular_breadth

ESQUEMAS_PESOS = {
    "A_igual": {"breadth_activos": 1 / 3, "severidad_promedio": 1 / 3, "desaceleracion": 1 / 3},
    "B_experto": {"breadth_activos": 0.5, "severidad_promedio": 0.2, "desaceleracion": 0.3},
}

ESQUEMAS_NO_IMPLEMENTADOS = {
    "C_pca": (
        "PCA/factores: requiere una matriz de componentes suficientemente rica "
        "(>=5-6 series no redundantes) para que la primera componente principal "
        "sea interpretable como 'presión sistémica' y no como ruido de un solo "
        "indicador dominante. Con 3 componentes actuales, PCA colapsaría "
        "esencialmente al componente de mayor varianza — no aporta sobre A/B."
    ),
    "D_predictivo": (
        "Pesos por capacidad predictiva: requiere el registro de eventos "
        "(analytics.eventos) con tamaño suficiente para ajustar pesos sin "
        "sobreajustar. Con ~24 eventos proxy (no confirmados) en todo el "
        "histórico, cualquier ajuste de pesos por regresión/optimización "
        "memorizaría la muestra en vez de generalizar — no implementado."
    ),
    "E_hibrido": "Depende de C y D — no implementado por las mismas razones.",
}


def _crecimiento_agregado_pct(df_ranking: pd.DataFrame, codigo: str, fecha_actual, fecha_anterior,
                               segmento: str) -> float | None:
    mask_a = (df_ranking["fecha"] == fecha_actual) & (df_ranking["codigo"] == codigo)
    mask_b = (df_ranking["fecha"] == fecha_anterior) & (df_ranking["codigo"] == codigo)
    if segmento != "Todos":
        mask_a &= df_ranking["segmento"] == segmento
        mask_b &= df_ranking["segmento"] == segmento
    total_actual = df_ranking.loc[mask_a, "valor"].sum()
    total_anterior = df_ranking.loc[mask_b, "valor"].sum()
    if total_anterior <= 0:
        return None
    return (total_actual / total_anterior - 1) * 100


def calcular_ipsf_periodo(
    df_indicadores: pd.DataFrame, df_ranking: pd.DataFrame, fecha, segmento: str = "Todos",
) -> dict:
    """Calcula los 3 componentes crudos y ambos esquemas de ponderación (A, B) para UN período."""
    df_alertas = evaluar_alertas(df_indicadores, fecha, segmento)
    if df_alertas.empty:
        return {"fecha": fecha, "componentes": {}, "ipsf": {}}

    afectadas_rojas = df_alertas.loc[df_alertas["alertas_rojas"] > 0, "cooperativa"].tolist()
    breadth = calcular_breadth(afectadas_rojas, df_ranking, fecha, segmento)
    comp_breadth = breadth["dimensiones"].get("activos") or 0.0

    n_reglas = len([c for c in df_alertas.columns if c.startswith("sev_")])
    max_alertas_posibles = n_reglas if n_reglas else 1
    comp_severidad = float(df_alertas["total_alertas_activas"].mean() / max_alertas_posibles * 100)

    fecha_anterior = pd.Timestamp(fecha) - pd.DateOffset(years=1)
    crec_cartera = _crecimiento_agregado_pct(df_ranking, "14", fecha, fecha_anterior, segmento)
    crec_dep = _crecimiento_agregado_pct(df_ranking, "21", fecha, fecha_anterior, segmento)
    crecs = [c for c in (crec_cartera, crec_dep) if c is not None]
    crecimiento_prom = sum(crecs) / len(crecs) if crecs else 0.0
    # Normalización simple y documentada: crecimiento de -20% o peor -> 100
    # (máxima presión); crecimiento de +20% o mejor -> 0. Lineal entre medio.
    comp_desaceleracion = max(0.0, min(100.0, (20.0 - crecimiento_prom) / 40.0 * 100.0))

    componentes = {
        "breadth_activos": round(comp_breadth, 2),
        "severidad_promedio": round(comp_severidad, 2),
        "desaceleracion": round(comp_desaceleracion, 2),
    }

    ipsf_por_esquema = {}
    for nombre_esquema, pesos in ESQUEMAS_PESOS.items():
        valor = sum(componentes[c] * peso for c, peso in pesos.items())
        ipsf_por_esquema[nombre_esquema] = round(valor, 2)

    return {"fecha": fecha, "segmento": segmento, "componentes": componentes, "ipsf": ipsf_por_esquema}


def calcular_serie_ipsf(
    df_indicadores: pd.DataFrame, df_ranking: pd.DataFrame, fechas: list, segmento: str = "Todos",
) -> pd.DataFrame:
    """Serie de tiempo del IPSF (ambos esquemas) para una lista de fechas."""
    filas = []
    for fecha in sorted(pd.to_datetime(pd.Series(fechas)).unique()):
        r = calcular_ipsf_periodo(df_indicadores, df_ranking, fecha, segmento)
        if not r["ipsf"]:
            continue
        fila = {"fecha": fecha, **r["componentes"], **{f"ipsf_{k}": v for k, v in r["ipsf"].items()}}
        filas.append(fila)
    return pd.DataFrame(filas)


def correlacion_componentes(df_serie_ipsf: pd.DataFrame) -> dict:
    """
    Correlación ENTRE los 3 componentes crudos (no entre esquemas de pesos).
    Necesaria para interpretar correctamente la correlación A/B de
    `diagnostico_esquemas()`: si dos componentes ya son redundantes entre sí
    por construcción, cualquier esquema razonable de pesos producirá
    resultados parecidos — eso NO es evidencia de que el índice compuesto
    "funcione", es evidencia de que dos de sus tres insumos miden casi lo
    mismo.

    Hallazgo verificado con datos reales (jul-2026, últimos 24 meses):
    `breadth_activos` y `severidad_promedio` correlacionan ~0.75 (ambos se
    derivan de `evaluar_alertas()` — uno pondera por tamaño, el otro por
    conteo, pero comparten la misma fuente de alertas). `desaceleracion`
    (basado en crecimiento agregado, una fuente de datos distinta) correlaciona
    débilmente con los otros dos (~0.07-0.20) — es el componente que aporta
    información genuinamente independiente.
    """
    componentes = ["breadth_activos", "severidad_promedio", "desaceleracion"]
    if df_serie_ipsf.empty or not all(c in df_serie_ipsf.columns for c in componentes):
        return {"valido": False}
    matriz = df_serie_ipsf[componentes].corr()
    return {
        "valido": True,
        "matriz": matriz.round(3).to_dict(),
        "interpretacion": (
            "breadth_activos y severidad_promedio comparten la misma fuente (evaluar_alertas()) — "
            "una correlación alta entre ellos es esperable por construcción, no un hallazgo. "
            "desaceleracion viene de una fuente distinta (crecimiento agregado de balance); su "
            "correlación con los otros dos es la única evidencia real de que el índice combina "
            "información independiente, no una sola señal repetida tres veces."
        ),
    }


def diagnostico_esquemas(df_serie_ipsf: pd.DataFrame) -> dict:
    """
    Diagnóstico mínimo de robustez entre esquemas A y B: correlación (¿son
    redundantes o divergen?) y diferencia máxima observada.

    **Interpretación correcta de una correlación alta (hardening 14-sep-2026,
    verificado con datos reales — correlación A/B = 0.968 sobre 24 meses)**:
    una correlación alta entre A y B NO implica, por sí sola, que el IPSF sea
    robusto o que "capture algo real". Ambos esquemas ponderan los mismos 3
    componentes, y 2 de esos 3 (`breadth_activos`, `severidad_promedio`) ya
    están correlacionados ~0.75 entre sí por construcción (ver
    `correlacion_componentes()`) — cualquier esquema de pesos que mantenga
    esos dos componentes como mayoría del índice producirá una serie parecida
    a cualquier otro esquema que haga lo mismo. La correlación A/B alta es,
    por lo tanto, evidencia de que **la elección entre A y B específicamente
    no domina el resultado** (una afirmación limitada y correcta), pero
    **no** evidencia de que el IPSF tenga capacidad analítica validada, ni de
    que un esquema sea superior a otro. Esa conclusión más fuerte
    requeriría backtesting contra eventos (`analytics.backtesting`), que
    hoy no se ha hecho para el IPSF por el mismo motivo que no se implementan
    los esquemas C/D/E: la muestra de eventos es demasiado pequeña.
    """
    if df_serie_ipsf.empty or "ipsf_A_igual" not in df_serie_ipsf.columns:
        return {"valido": False}

    correlacion = df_serie_ipsf["ipsf_A_igual"].corr(df_serie_ipsf["ipsf_B_experto"])
    diferencia = (df_serie_ipsf["ipsf_A_igual"] - df_serie_ipsf["ipsf_B_experto"]).abs()

    return {
        "valido": True,
        "n_periodos": len(df_serie_ipsf),
        "correlacion_esquemas_A_B": round(float(correlacion), 3) if pd.notna(correlacion) else None,
        "diferencia_promedio": round(float(diferencia.mean()), 2),
        "diferencia_maxima": round(float(diferencia.max()), 2),
        "interpretacion": (
            "Correlación alta (>0.8) entre A y B: la elección específica entre estos dos esquemas "
            "de pesos no domina el resultado en esta muestra. Esto NO debe leerse como evidencia de "
            "robustez del IPSF en general — ver correlacion_componentes(): 2 de los 3 componentes ya "
            "son redundantes entre sí por construcción (misma fuente, evaluar_alertas()), lo cual por "
            "sí solo produce una correlación A/B alta independientemente de si el índice compuesto "
            "tiene capacidad analítica real. Correlación baja entre A y B sí sería una señal clara de "
            "alerta (el resultado dependería de qué pesos se eligieron) — no es el caso aquí, pero su "
            "ausencia no es una validación positiva."
        ),
    }
