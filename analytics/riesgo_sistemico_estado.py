# -*- coding: utf-8 -*-
"""
Estado sistémico y clasificación de contracción — ANALÍTICO EXPERIMENTAL.

Combina crecimiento agregado (cartera, depósitos, activos), breadth de
alertas activas (`analytics.breadth`), persistencia (`analytics.persistencia`)
y concentración (`analytics.concentracion`) en una clasificación discreta
del estado del sistema. Es la pieza que el objetivo pide para no "definir
contracción solamente por caída del crédito": ningún estado se decide con
una sola variable.

**Etiqueta metodológica obligatoria**: este es un módulo ANALÍTICO, no un
indicador oficial ni un modelo validado por backtesting histórico completo
(ver `analytics.backtesting` para el intento de validación disponible y sus
limitaciones). La clasificación es un árbol de decisión transparente y
documentado — no una caja negra ni un índice compuesto con pesos ocultos —
pero eso no la convierte en una predicción probada. Nunca usar "CRISIS"
como resultado: el vocabulario más fuerte disponible es "EVENTO EXTREMO",
y solo se alcanza con evidencia en múltiples dimensiones a la vez.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from analytics.alertas import evaluar_alertas
from analytics.breadth import calcular_breadth
from analytics.concentracion import calcular_hhi, clasificar_hhi
from analytics.persistencia import calcular_persistencia_alertas, ventana_fechas

CODIGO_ACTIVOS = "1"
CODIGO_CARTERA = "14"
CODIGO_DEPOSITOS = "21"

ESTADOS = [
    "NORMAL",
    "DESACELERACIÓN",
    "CONTRACCIÓN SECTORIAL",
    "CONTRACCIÓN SIGNIFICATIVA",
    "ESTRÉS SISTÉMICO POTENCIAL",
    "EVENTO EXTREMO",
]

# Umbrales analíticos (no regulatorios) para el árbol de decisión. Elegidos
# con el mismo criterio que el resto de la plataforma: cola de la
# distribución, no la mediana. Documentados aquí, en un solo lugar, para
# que Riesgos pueda auditarlos/ajustarlos.
UMBRAL_CRECIMIENTO_DESACELERACION_PCT = 5.0   # crecimiento YoY por debajo de esto ya es "lento"
UMBRAL_CRECIMIENTO_CONTRACCION_PCT = 0.0      # YoY negativo = contracción nominal
UMBRAL_BREADTH_SECTORIAL_PCT = 15.0           # % activos en alerta roja
UMBRAL_BREADTH_SIGNIFICATIVO_PCT = 25.0       # coincide con breadth.UMBRAL_GENERALIZADO_PCT
UMBRAL_PERSISTENCIA_MESES = 3                 # meses consecutivos para "no es ruido de un mes"


def _crecimiento_agregado_pct(df_ranking: pd.DataFrame, codigo: str, fecha_actual, fecha_anterior,
                               segmento: str) -> Optional[float]:
    """Crecimiento YoY de la SUMA de una cuenta en el universo (no promedio por cooperativa)."""
    mask_a = (df_ranking["fecha"] == fecha_actual) & (df_ranking["codigo"] == codigo)
    mask_b = (df_ranking["fecha"] == fecha_anterior) & (df_ranking["codigo"] == codigo)
    if segmento != "Todos":
        mask_a &= df_ranking["segmento"] == segmento
        mask_b &= df_ranking["segmento"] == segmento

    total_actual = df_ranking.loc[mask_a, "valor"].sum()
    total_anterior = df_ranking.loc[mask_b, "valor"].sum()
    if total_anterior <= 0:
        return None
    return round((total_actual / total_anterior - 1) * 100, 2)


def evaluar_estado_sistemico(
    df_indicadores: pd.DataFrame,
    df_ranking: pd.DataFrame,
    fecha_actual,
    fecha_anterior_yoy,
    segmento: str = "Todos",
    meses_ventana_persistencia: int = 6,
) -> dict:
    """
    Evalúa el estado sistémico en `fecha_actual` comparado interanualmente
    contra `fecha_anterior_yoy` (normalmente el mismo mes del año previo).

    Devuelve el flujo completo pedido por el objetivo: ESTADO, DRIVERS,
    EVIDENCIA, AMPLITUD, PERSISTENCIA, CONFIANZA, LIMITACIONES.
    """
    # --- Crecimiento agregado (3 dimensiones, no solo crédito) ---
    crec_cartera = _crecimiento_agregado_pct(df_ranking, CODIGO_CARTERA, fecha_actual, fecha_anterior_yoy, segmento)
    crec_depositos = _crecimiento_agregado_pct(df_ranking, CODIGO_DEPOSITOS, fecha_actual, fecha_anterior_yoy, segmento)
    crec_activos = _crecimiento_agregado_pct(df_ranking, CODIGO_ACTIVOS, fecha_actual, fecha_anterior_yoy, segmento)

    # --- Breadth de alertas rojas ---
    df_alertas = evaluar_alertas(df_indicadores, fecha_actual, segmento)
    afectadas_rojas = df_alertas.loc[df_alertas["alertas_rojas"] > 0, "cooperativa"].tolist() if not df_alertas.empty else []
    breadth = calcular_breadth(afectadas_rojas, df_ranking, fecha_actual, segmento)
    pct_activos_afectados = breadth["dimensiones"].get("activos") or 0.0

    # --- Persistencia (ventana de meses hasta fecha_actual) ---
    fechas_disp = df_indicadores["fecha"].unique()
    ventana = ventana_fechas(fechas_disp, fecha_actual, meses_ventana_persistencia)
    df_persist = calcular_persistencia_alertas(df_indicadores, ventana, segmento)
    n_persistentes = int(df_persist["alerta_persistente"].sum()) if not df_persist.empty else 0
    pct_persistentes = (
        round(n_persistentes / len(df_persist) * 100, 2) if not df_persist.empty else 0.0
    )

    # --- Concentración (contexto: ¿el deterioro está en pocas manos grandes?) ---
    mask_hhi = (df_ranking["fecha"] == fecha_actual) & (df_ranking["codigo"] == CODIGO_ACTIVOS)
    if segmento != "Todos":
        mask_hhi &= df_ranking["segmento"] == segmento
    hhi = calcular_hhi(df_ranking.loc[mask_hhi, "valor"])

    # --- Árbol de decisión (documentado, sin pesos ocultos) ---
    drivers = []
    evidencia_en_contra = []

    crecimientos_validos = [c for c in (crec_cartera, crec_depositos, crec_activos) if c is not None]
    crecimiento_min = min(crecimientos_validos) if crecimientos_validos else None

    nivel_crecimiento = 0  # 0=normal, 1=desaceleracion, 2=contraccion
    if crecimiento_min is not None:
        if crecimiento_min < UMBRAL_CRECIMIENTO_CONTRACCION_PCT:
            nivel_crecimiento = 2
            drivers.append(
                f"Crecimiento YoY negativo en al menos una dimensión (mínimo: {crecimiento_min:.1f}%)"
            )
        elif crecimiento_min < UMBRAL_CRECIMIENTO_DESACELERACION_PCT:
            nivel_crecimiento = 1
            drivers.append(
                f"Crecimiento YoY débil en al menos una dimensión (mínimo: {crecimiento_min:.1f}%)"
            )
        else:
            evidencia_en_contra.append(f"Crecimiento YoY saludable (mínimo entre dimensiones: {crecimiento_min:.1f}%)")

    nivel_breadth = 0  # 0=bajo, 1=sectorial, 2=significativo
    if pct_activos_afectados >= UMBRAL_BREADTH_SIGNIFICATIVO_PCT:
        nivel_breadth = 2
        drivers.append(f"{pct_activos_afectados:.1f}% de los activos del sistema en entidades con alerta roja")
    elif pct_activos_afectados >= UMBRAL_BREADTH_SECTORIAL_PCT:
        nivel_breadth = 1
        drivers.append(f"{pct_activos_afectados:.1f}% de los activos del sistema en entidades con alerta roja")
    else:
        evidencia_en_contra.append(f"Solo {pct_activos_afectados:.1f}% de los activos en alerta roja")

    persistencia_relevante = n_persistentes > 0 and pct_persistentes >= 5.0
    if persistencia_relevante:
        drivers.append(
            f"{n_persistentes} entidades ({pct_persistentes:.1f}%) con alertas activas "
            f">= {UMBRAL_PERSISTENCIA_MESES} meses consecutivos — no es ruido de un mes"
        )
    else:
        evidencia_en_contra.append("Sin un número relevante de alertas persistentes (>=3 meses)")

    # Puntaje simple y documentado (no una fórmula oculta): cada dimensión
    # aporta 0-2 puntos, la persistencia actúa como multiplicador de
    # severidad (exige persistencia para escalar a los dos estados más altos).
    puntaje = nivel_crecimiento + nivel_breadth
    if puntaje == 0:
        estado = "NORMAL"
    elif puntaje == 1:
        estado = "DESACELERACIÓN"
    elif puntaje == 2 and not persistencia_relevante:
        estado = "CONTRACCIÓN SECTORIAL"
    elif puntaje == 2 and persistencia_relevante:
        estado = "CONTRACCIÓN SIGNIFICATIVA"
    elif puntaje == 3 and persistencia_relevante:
        estado = "ESTRÉS SISTÉMICO POTENCIAL"
    elif puntaje >= 4 and persistencia_relevante:
        estado = "EVENTO EXTREMO"
    else:
        estado = "CONTRACCIÓN SECTORIAL"  # puntaje=3 o 4 sin persistencia: no escala sin confirmar con el tiempo

    # --- Requisito explícito de evidencia MULTIDIMENSIONAL (hardening 14-sep-2026) ---
    # Hallazgo de la batería de escenarios sintéticos A-H: una caída YoY
    # aislada en una sola dimensión (p. ej. solo cartera, o solo depósitos),
    # sin ningún respaldo de breadth ni de persistencia, alcanzaba
    # "CONTRACCIÓN SECTORIAL" únicamente por el puntaje de crecimiento —
    # exactamente el antipatrón que el objetivo prohíbe ("contracción" no
    # puede equivaler a "crecimiento negativo de cartera/depósitos"). Se
    # exige que al menos 2 de las 3 señales de evidencia (crecimiento
    # negativo, breadth >=15%, persistencia relevante) concurran para que el
    # estado pueda ser cualquiera de la familia "CONTRACCIÓN"/"ESTRÉS"/
    # "EVENTO EXTREMO"; con una sola señal, el resultado se limita a
    # DESACELERACIÓN (se documenta como evidencia insuficiente, no se
    # descarta el driver).
    n_senales_evidencia = sum([nivel_crecimiento == 2, nivel_breadth >= 1, persistencia_relevante])
    if estado not in ("NORMAL", "DESACELERACIÓN") and n_senales_evidencia < 2:
        estado = "DESACELERACIÓN"
        evidencia_en_contra.append(
            "Solo una dimensión de evidencia disponible (crecimiento, breadth o persistencia, sin "
            "que las otras dos corroboren) — no se confirma como contracción; se requiere evidencia "
            "multidimensional para escalar más allá de DESACELERACIÓN."
        )

    # --- Confianza (declarada, no una probabilidad estadística) ---
    factores_confianza = []
    if crecimientos_validos and len(crecimientos_validos) == 3:
        factores_confianza.append("alta")
    else:
        factores_confianza.append("media")
    if breadth["n_entidades_universo"] < 20:
        factores_confianza.append("baja (universo pequeño, breadth poco representativo)")
    confianza = "alta" if factores_confianza == ["alta"] else "media"

    return {
        "estado": estado,
        "fecha": fecha_actual,
        "fecha_comparacion": fecha_anterior_yoy,
        "segmento": segmento,
        "drivers": drivers,
        "evidencia_en_contra": evidencia_en_contra,
        "amplitud": {
            "pct_activos_afectados": pct_activos_afectados,
            "pct_entidades_afectadas": breadth["pct_entidades"],
            "clasificacion_breadth": breadth["clasificacion"],
        },
        "persistencia": {
            "n_entidades_persistentes": n_persistentes,
            "pct_entidades_persistentes": pct_persistentes,
            "ventana_meses": len(ventana),
        },
        "crecimiento_yoy_pct": {
            "cartera": crec_cartera, "depositos": crec_depositos, "activos": crec_activos,
        },
        "concentracion": {"hhi_activos": round(hhi, 1), "clasificacion_hhi": clasificar_hhi(hhi)},
        "confianza": confianza,
        "limitaciones": [
            "Clasificación ANALÍTICA EXPERIMENTAL: árbol de decisión transparente, "
            "sin validación completa por backtesting histórico (ver analytics.backtesting).",
            "No incluye interconectividad real entre entidades (dato no publicado por SEPS).",
            "No incluye indicadores macroprudenciales (Credit-to-GDP Gap, DSR) por falta de fuente.",
            "El umbral de breadth (15%/25% de activos) y el árbol de puntaje son elegidos por "
            "este equipo, no derivados de un límite regulatorio ni de un estudio de eventos previos.",
        ],
    }
