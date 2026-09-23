# -*- coding: utf-8 -*-
"""
Asistente Inteligente institucional.

Dos modos, siempre disponibles:

1. **Asistente local determinístico** (`responder_local`): responde preguntas
   factuales frecuentes consultando directamente los datos reales del
   sistema (metadata, KPIs, alertas, score CAMEL). No requiere ninguna clave
   externa y nunca inventa cifras — si no reconoce la pregunta, lo dice.

2. **Asistente con Claude (Anthropic)** (`responder_con_claude`): integración
   real vía el SDK oficial `anthropic`. Se activa solo si hay una clave API
   configurada (en `st.secrets["ANTHROPIC_API_KEY"]` o ingresada en la
   sesión). El prompt de sistema inyecta un resumen de los datos reales más
   recientes del sistema para que las respuestas estén ancladas a cifras
   verificables, no a conocimiento general del modelo sobre el sector.

Preparado para extender a otros proveedores (OpenAI, Gemini, LLM local) sin
cambiar la interfaz de las páginas: basta añadir una función
`responder_con_<proveedor>` con la misma firma.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd
import streamlit as st

from utils.logging_config import get_logger

logger = get_logger(__name__)

MODELO_CLAUDE_DEFECTO = "claude-sonnet-5"


def obtener_clave_claude() -> Optional[str]:
    """Busca la clave de Anthropic en `st.secrets` o en la sesión (ingresada manualmente)."""
    try:
        clave = st.secrets.get("ANTHROPIC_API_KEY")
        if clave:
            return clave
    except Exception:
        pass
    return st.session_state.get("sps_anthropic_key_manual")


def claude_disponible() -> bool:
    return bool(obtener_clave_claude())


def construir_contexto_sistema(
    metadata: Dict, alertas_resumen: Optional[Dict] = None, score_resumen: Optional[Dict] = None
) -> str:
    """
    Arma un resumen compacto de datos reales y recientes del sistema, para
    inyectarlo como contexto verificable en el prompt de sistema de Claude.
    """
    partes = [
        "Eres el Asistente Inteligente institucional de RADAR COOPERATIVO ECUADOR, "
        "una plataforma de inteligencia de riesgos de COSEDE (Ecuador) para el sector "
        "financiero popular y solidario (cooperativas de ahorro y crédito).",
        "Responde en español, de forma precisa y profesional, como lo haría un analista "
        "de riesgos senior. Nunca inventes cifras, nombres de cooperativas, fechas, eventos "
        "regulatorios (liquidaciones, fusiones, sanciones) ni conclusiones normativas que no "
        "estén respaldadas por los datos de este resumen o por la metodología documentada en "
        "docs/RIESGO_METODOLOGIA.md. Distingue explícitamente HECHO (un dato o cálculo que "
        "viene directo de la plataforma) de INFERENCIA (una lectura o hipótesis tuya sobre ese "
        "dato) cuando ofrezcas una interpretación — nunca presentes una inferencia como si fuera "
        "un hecho verificado. Si la pregunta requiere un dato, evento o clasificación regulatoria "
        "que no está en este resumen ni puedes derivar de él con la metodología conocida, responde "
        "exactamente: 'Información insuficiente para determinarlo.' — y sugiere en qué módulo de "
        "la plataforma podría verificarse.",
        "",
        "Datos reales del sistema (última actualización disponible):",
        f"- Instituciones: {metadata.get('cooperativas', 'N/D')}",
        f"- Período de datos: {metadata.get('fecha_min', 'N/D')[:7] if metadata.get('fecha_min') else 'N/D'} "
        f"a {metadata.get('fecha_max', 'N/D')[:7] if metadata.get('fecha_max') else 'N/D'}",
        f"- Registros de balance procesados: {metadata.get('registros_totales', 'N/D')}",
    ]

    if alertas_resumen:
        partes.append(
            f"- Alertas Tempranas (última fecha): {alertas_resumen.get('crit', 0)} instituciones críticas, "
            f"{alertas_resumen.get('warn', 0)} en vigilancia, {alertas_resumen.get('ok', 0)} sin alertas."
        )
    if score_resumen:
        partes.append(
            f"- Score CAMEL promedio del sistema: {score_resumen.get('promedio', 'N/D')}/100."
        )

    partes.append(
        "\nSi te preguntan por un dato específico de una cooperativa que no está en este "
        "resumen, indica al usuario que puede consultarlo en el módulo correspondiente "
        "de la plataforma (Panorama, Riesgo de Crédito, CAMEL Score, Alertas Tempranas, etc.)."
    )
    return "\n".join(partes)


def _aplicar_guardrails_deterministicos(respuesta: str) -> str:
    """
    Capa de control DETERMINÍSTICA sobre la salida del LLM — hardening
    14-sep-2026, pedido explícito: "no confiar únicamente en instrucciones
    de prompt para controles críticos". Un prompt de sistema puede ser
    ignorado por el modelo; esta función se ejecuta en código Python sobre
    el texto ya generado, sin depender de que el LLM haya obedecido nada.

    Único control implementado hoy: la plataforma tiene una regla dura,
    verificada por test (`RiesgoSistemicoEstadoTests::test_nunca_devuelve_la_palabra_crisis`),
    de que ningún componente analítico usa la palabra "crisis" como
    categoría — es la palabra más fuerte que el objetivo prohíbe declarar
    sin evidencia. Si el LLM la usa de todos modos (no se puede impedir en
    origen), se adjunta una advertencia visible en vez de dejarla pasar sin
    marcar. No se reescribe ni se censura el texto del modelo (evitar dar
    una falsa sensación de respuesta "limpia") — se hace visible el
    problema para que el usuario lo note.

    No pretende ser un verificador de hechos completo (eso requeriría NER +
    comparación contra `contexto_sistema`, con riesgo alto de falsos
    positivos/negativos) — se mantiene deliberadamente simple y explicable,
    consistente con "no agregar complejidad innecesaria" del objetivo.
    """
    if "crisis" in respuesta.lower():
        respuesta += (
            "\n\n---\n⚠️ **Aviso automático (control determinístico, no del modelo)**: esta respuesta "
            "usa la palabra 'crisis'. Ningún componente analítico de esta plataforma calcula o declara "
            "'crisis' como categoría — el estado más severo que produce el sistema es 'EVENTO EXTREMO' "
            "(ver módulo Riesgo Sistémico → Estado Sistémico). Verifica la clasificación oficial antes "
            "de citar esta respuesta como una conclusión validada."
        )
    return respuesta


def responder_con_claude(
    mensaje: str, historial: List[Dict[str, str]], contexto_sistema: str, modelo: str = MODELO_CLAUDE_DEFECTO
) -> str:
    """Llama a la API de Claude (Anthropic) con el historial de la conversación."""
    import anthropic

    clave = obtener_clave_claude()
    if not clave:
        raise RuntimeError("No hay una clave de Anthropic configurada.")

    cliente = anthropic.Anthropic(api_key=clave)

    mensajes = [{"role": m["role"], "content": m["content"]} for m in historial if m["role"] in ("user", "assistant")]
    mensajes.append({"role": "user", "content": mensaje})

    logger.info("Llamando a Claude (%s), %d mensajes en el historial", modelo, len(mensajes))
    try:
        respuesta = cliente.messages.create(
            model=modelo,
            max_tokens=1024,
            system=contexto_sistema,
            messages=mensajes,
        )
    except Exception:
        logger.exception("Fallo la llamada a la API de Claude")
        raise
    return _aplicar_guardrails_deterministicos(respuesta.content[0].text)


# =============================================================================
# ASISTENTE LOCAL DETERMINÍSTICO (sin clave externa)
# =============================================================================

def responder_local(mensaje: str, metadata: Dict, alertas_df: Optional[pd.DataFrame] = None,
                     score_df: Optional[pd.DataFrame] = None) -> str:
    """
    Responde preguntas factuales frecuentes con datos reales, sin requerir
    ninguna API externa. Usa coincidencia simple de palabras clave — no es
    un modelo de lenguaje, es un enrutador determinístico a consultas ya
    calculadas en la plataforma.
    """
    texto = mensaje.lower().strip()

    if any(p in texto for p in ["cuántas cooperativas", "cuantas cooperativas", "número de cooperativas", "numero de instituciones"]):
        return f"El sistema procesa actualmente **{metadata.get('cooperativas', 'N/D')} instituciones** (Segmentos 1, 2, 3 y Mutualistas)."

    if any(p in texto for p in ["período", "periodo", "desde cuándo", "desde cuando", "qué años", "que años"]):
        fmin = str(metadata.get("fecha_min", ""))[:7]
        fmax = str(metadata.get("fecha_max", ""))[:7]
        return f"Los datos cubren el período **{fmin} a {fmax}** ({metadata.get('meses', 'N/D')} meses)."

    if any(p in texto for p in ["alerta crítica", "alerta critica", "en rojo", "instituciones críticas"]):
        if alertas_df is not None and not alertas_df.empty:
            criticas = alertas_df[alertas_df["semaforo"] == "crit"]
            n = len(criticas)
            ejemplos = ", ".join(criticas["cooperativa"].head(5).tolist())
            return (
                f"Hay **{n} instituciones** con semáforo crítico en la fecha más reciente evaluada. "
                f"Ejemplos: {ejemplos}{'...' if n > 5 else ''}. Ver el detalle completo en el módulo "
                "**Alertas Tempranas**."
            )
        return "No tengo el detalle de alertas cargado en esta sesión. Consulta el módulo **Alertas Tempranas**."

    if any(p in texto for p in ["score camel", "mejor score", "score promedio"]):
        if score_df is not None and not score_df.empty:
            promedio = score_df["score_total"].mean()
            mejor = score_df.iloc[0]["cooperativa"]
            return (
                f"El score CAMEL promedio del sistema es **{promedio:.1f}/100**. La institución con "
                f"mejor score es **{mejor}**. Ver el detalle en el módulo **CAMEL Score**."
            )
        return "No tengo el score CAMEL cargado en esta sesión. Consulta el módulo **CAMEL Score**."

    if any(p in texto for p in ["hola", "buenos días", "buenas tardes", "qué puedes hacer", "que puedes hacer", "ayuda"]):
        return (
            "Puedo responder preguntas sobre el estado general del sistema (número de instituciones, "
            "período de datos, alertas críticas, score CAMEL promedio) usando datos reales de la "
            "plataforma. Para análisis específicos por cooperativa o indicador, te recomiendo el "
            "módulo correspondiente en el menú lateral. Si configuras una clave de Claude, puedo "
            "responder preguntas más abiertas."
        )

    return (
        "Información insuficiente para determinarlo con el asistente local determinístico "
        "(solo reconoce un conjunto fijo de preguntas frecuentes, sin inventar respuestas). "
        "Puedes consultar el módulo correspondiente en el menú lateral, o configurar una clave de "
        "Claude (Anthropic) en **Configuración** para habilitar respuestas conversacionales más amplias."
    )
