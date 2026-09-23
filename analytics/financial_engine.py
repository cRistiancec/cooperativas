# -*- coding: utf-8 -*-
"""
Motor Central de Indicadores Financieros — punto de entrada único.

Toda página Streamlit que necesite calcular un indicador financiero
(liquidez, cartera, morosidad, cobertura, rentabilidad, capital,
concentración, riesgo sistémico, alertas o stress testing) debe importarlo
desde aquí — `from analytics.financial_engine import ...` — y no desde los
submódulos de dominio individuales ni, mucho menos, recalculando algo
inline en la propia página.

Este módulo **no duplica ninguna fórmula**: es una fachada que re-exporta
las funciones que ya existían, cada una en su archivo de dominio
(`analytics/liquidez.py`, `analytics/credito.py`, etc.), sin tocar su
implementación. La razón de mantener los archivos de dominio separados en
vez de fusionarlos en uno solo es la misma que ya seguía el proyecto antes
de este motor: cada dominio es una unidad de código pequeña, con su propia
documentación de las limitaciones de datos que le aplican (ver, p. ej., la
nota sobre vintage curves en `credito.py` o sobre interconectividad en
`sistemico.py`) — fusionarlos perdería esa trazabilidad sin ganar nada.

Organización por dominio (según la metodología institucional migrada del
script R de referencia — ver `AUDITORIA_MOTOR_INDICADORES.md`):

    LIQUIDEZ        → analytics.liquidez
    CARTERA         → analytics.credito (paneles) + analytics.cartera (Fase 2.3)
    MOROSIDAD       → analytics.credito
    COBERTURA       → analytics.credito
    CAPITAL         → analytics.solvencia
    RENTABILIDAD    → analytics.camels_score (score) + analytics.rentabilidad (Fase 2.3)
    EFICIENCIA      → indicadores oficiales SEPS (GO_ACT, GO_MNF, GP_ACT) — sin
                      módulo propio; se consumen directamente de indicadores.parquet
    CRECIMIENTO     → analytics.crecimiento (Fase 2.3)
    CONCENTRACIÓN   → analytics.concentracion
    RIESGO SISTÉMICO→ analytics.sistemico
    ALERTAS         → analytics.alertas
    STRESS TESTING  → analytics.stress_testing
    ÍNDICES         → analytics.indices_ejecutivos (Fase 2.4)
"""

from __future__ import annotations

# =============================================================================
# LIQUIDEZ
# =============================================================================
from analytics.liquidez import (
    CODIGO_DEPOSITOS as LIQUIDEZ_CODIGO_DEPOSITOS,
    CODIGO_FONDOS_DISPONIBLES,
    CODIGO_INVERSIONES,
    calcular_cobertura_retiro,
    calcular_liquidez_ampliada,
)

# =============================================================================
# CARTERA / MOROSIDAD / COBERTURA
# =============================================================================
from analytics.credito import (
    CARTERAS_COBERTURA,
    CARTERAS_MOROSIDAD,
    CODIGO_CARTERA_TOTAL,
    CODIGO_CARTERA_VENCIDA,
    CODIGO_PROVISION_CARTERA,
    construir_panel_morosidad_cobertura,
    construir_serie_cartera_vencida,
)

# =============================================================================
# CAPITAL / SOLVENCIA
# =============================================================================
from analytics.solvencia import (
    CODIGO_ACTIVOS as SOLVENCIA_CODIGO_ACTIVOS,
    CODIGO_PATRIMONIO,
    ETIQUETAS_SOLVENCIA,
    INDICADORES_SOLVENCIA,
    UMBRAL_SOLVENCIA_REGULATORIO,
    calcular_patrimonio_sobre_activos,
    evaluar_solvencia_oficial,
)

# =============================================================================
# CONCENTRACIÓN
# =============================================================================
from analytics.concentracion import (
    calcular_cr,
    calcular_hhi,
    clasificar_hhi,
    coeficiente_gini,
    curva_lorenz,
)

# =============================================================================
# RIESGO SISTÉMICO
# =============================================================================
from analytics.sistemico import (
    CODIGO_ACTIVOS as SISTEMICO_CODIGO_ACTIVOS,
    CODIGO_CARTERA as SISTEMICO_CODIGO_CARTERA,
    CODIGO_DEPOSITOS as SISTEMICO_CODIGO_DEPOSITOS,
    PESOS_IIS,
    calcular_indice_importancia_sistemica,
)

# =============================================================================
# RENTABILIDAD — SCORE COMPUESTO CAMEL
# =============================================================================
from analytics.camels_score import (
    CATEGORIAS_CAMEL,
    DIRECCION_INDICADOR,
    INDICADORES_VULNERABILIDAD,
    calcular_score_camel,
    clasificar_score,
)

# =============================================================================
# RENTABILIDAD — TASAS IMPLÍCITAS, SPREAD Y ROE AJUSTADO (Fase 2.3)
# =============================================================================
from analytics.rentabilidad import (
    CODIGO_GASTOS_TOTAL,
    CODIGO_INGRESOS_TOTAL,
    CODIGO_INTERES_CAUSADO_DEPOSITOS,
    CODIGO_INTERES_GANADO_CARTERA,
    CODIGO_OTROS_INGRESOS,
    calcular_margen_financiero,
    calcular_roe_ajustado,
    calcular_tasas_implicitas,
)

# =============================================================================
# CRECIMIENTO — CAPTACIONES, COLOCACIONES, CARTERA EN RIESGO (Fase 2.3)
# =============================================================================
from analytics.crecimiento import (
    CODIGOS_CARTERA_EN_RIESGO,
    bandas_percentil,
    calcular_cartera_en_riesgo,
    calcular_crecimiento_yoy_mensual,
    crecimiento_activos,
    crecimiento_captaciones,
    crecimiento_colocaciones,
    variacion_anual_cartera_en_riesgo,
)

# =============================================================================
# ÍNDICES EJECUTIVOS DE SEGUNDO NIVEL (Fase 2.4)
# =============================================================================
from analytics.indices_ejecutivos import (
    PESOS_RIESGO_INTEGRAL,
    calcular_indice_estabilidad,
    calcular_indice_fortaleza,
    calcular_indice_resiliencia,
    calcular_indice_riesgo_integral,
    calcular_indice_vulnerabilidad,
    calcular_score_financiero_integral,
    clasificar_riesgo_integral,
)

# =============================================================================
# ALERTAS TEMPRANAS
# =============================================================================
from analytics.alertas import evaluar_alertas

# =============================================================================
# STRESS TESTING
# =============================================================================
from analytics.stress_testing import (
    ESCENARIOS,
    aplicar_escenario,
    construir_panel_balance,
)

# =============================================================================
# PERSISTENCIA TEMPORAL DE ALERTAS (hardening 14-sep-2026)
# =============================================================================
from analytics.persistencia import (
    UMBRAL_PERSISTENTE_MESES,
    calcular_persistencia_alertas,
    ventana_fechas,
)

# =============================================================================
# BREADTH / AMPLITUD (hardening 14-sep-2026)
# =============================================================================
from analytics.breadth import (
    UMBRAL_GENERALIZADO_PCT,
    breadth_por_segmento,
    calcular_breadth,
)

# =============================================================================
# INTERACCIÓN ENTRE INDICADORES (hardening 14-sep-2026)
# =============================================================================
from analytics.interaccion import REGLAS_INTERACCION, evaluar_interacciones

# =============================================================================
# ESTADO SISTÉMICO / CONTRACCIÓN — ANALÍTICO EXPERIMENTAL (hardening 14-sep-2026)
# =============================================================================
from analytics.riesgo_sistemico_estado import ESTADOS, evaluar_estado_sistemico

# =============================================================================
# IPSF — EXPERIMENTAL (hardening 14-sep-2026)
# =============================================================================
from analytics.ipsf import (
    ESQUEMAS_NO_IMPLEMENTADOS,
    ESQUEMAS_PESOS,
    calcular_ipsf_periodo,
    calcular_serie_ipsf,
    correlacion_componentes,
    diagnostico_esquemas,
)

# =============================================================================
# EVENTOS PROXY Y BACKTESTING PROXY (hardening 14-sep-2026)
# =============================================================================
from analytics.eventos import TIPO_EVENTO_PROXY, TIPO_EVENTO_TEXTUAL, detectar_eventos_salida
from analytics.backtesting import evaluar_alertas_previas_a_eventos

# =============================================================================
# CALIDAD DE DATOS (hardening 14-sep-2026)
# =============================================================================
from analytics.data_quality import (
    detectar_cambios_de_segmento,
    detectar_cambios_abruptos,
    detectar_denominadores_cero,
    detectar_entidades_nuevas_y_desaparecidas,
    reporte_calidad_fecha,
    validar_duplicados,
    validar_faltantes,
    validar_fechas,
)

__all__ = [
    # Liquidez
    "CODIGO_FONDOS_DISPONIBLES", "CODIGO_INVERSIONES", "LIQUIDEZ_CODIGO_DEPOSITOS",
    "calcular_liquidez_ampliada", "calcular_cobertura_retiro",
    # Cartera / Morosidad / Cobertura
    "CARTERAS_MOROSIDAD", "CARTERAS_COBERTURA", "CODIGO_CARTERA_VENCIDA",
    "CODIGO_PROVISION_CARTERA", "CODIGO_CARTERA_TOTAL",
    "construir_panel_morosidad_cobertura", "construir_serie_cartera_vencida",
    # Capital / Solvencia (vulnerabilidad patrimonial — analítico/oficial SEPS)
    "SOLVENCIA_CODIGO_ACTIVOS", "CODIGO_PATRIMONIO", "INDICADORES_SOLVENCIA",
    "ETIQUETAS_SOLVENCIA", "calcular_patrimonio_sobre_activos",
    # Solvencia OFICIAL/REGULATORIA (PTC/APPR, ficha SEPS 62-63, fuente FS01)
    "UMBRAL_SOLVENCIA_REGULATORIO", "evaluar_solvencia_oficial",
    # Concentración
    "calcular_hhi", "calcular_cr", "curva_lorenz", "coeficiente_gini", "clasificar_hhi",
    # Riesgo sistémico
    "SISTEMICO_CODIGO_ACTIVOS", "SISTEMICO_CODIGO_CARTERA", "SISTEMICO_CODIGO_DEPOSITOS",
    "PESOS_IIS", "calcular_indice_importancia_sistemica",
    # Rentabilidad / Score CAMEL
    "DIRECCION_INDICADOR", "CATEGORIAS_CAMEL", "INDICADORES_VULNERABILIDAD",
    "calcular_score_camel", "clasificar_score",
    # Rentabilidad — tasas implícitas, spread, ROE ajustado
    "CODIGO_INTERES_CAUSADO_DEPOSITOS", "CODIGO_INTERES_GANADO_CARTERA",
    "CODIGO_INGRESOS_TOTAL", "CODIGO_GASTOS_TOTAL", "CODIGO_OTROS_INGRESOS",
    "calcular_tasas_implicitas", "calcular_margen_financiero", "calcular_roe_ajustado",
    # Crecimiento — captaciones, colocaciones, cartera en riesgo
    "CODIGOS_CARTERA_EN_RIESGO", "crecimiento_captaciones", "crecimiento_colocaciones",
    "crecimiento_activos", "calcular_cartera_en_riesgo", "variacion_anual_cartera_en_riesgo", "bandas_percentil",
    # Índices ejecutivos de segundo nivel
    "calcular_score_financiero_integral", "calcular_indice_vulnerabilidad",
    "calcular_indice_fortaleza", "calcular_indice_resiliencia", "calcular_indice_estabilidad",
    "calcular_indice_riesgo_integral", "clasificar_riesgo_integral", "PESOS_RIESGO_INTEGRAL",
    # Alertas
    "evaluar_alertas",
    # Stress testing
    "ESCENARIOS", "construir_panel_balance", "aplicar_escenario",
    # Persistencia temporal de alertas
    "UMBRAL_PERSISTENTE_MESES", "calcular_persistencia_alertas", "ventana_fechas",
    # Breadth / amplitud
    "UMBRAL_GENERALIZADO_PCT", "calcular_breadth", "breadth_por_segmento",
    # Interacción entre indicadores
    "REGLAS_INTERACCION", "evaluar_interacciones",
    # Estado sistémico / contracción — ANALÍTICO EXPERIMENTAL
    "ESTADOS", "evaluar_estado_sistemico",
    # IPSF — EXPERIMENTAL
    "ESQUEMAS_PESOS", "ESQUEMAS_NO_IMPLEMENTADOS", "calcular_ipsf_periodo",
    "calcular_serie_ipsf", "diagnostico_esquemas", "correlacion_componentes",
    # Eventos proxy y backtesting proxy
    "TIPO_EVENTO_PROXY", "TIPO_EVENTO_TEXTUAL", "detectar_eventos_salida",
    "evaluar_alertas_previas_a_eventos",
    # Calidad de datos
    "validar_fechas", "validar_duplicados", "validar_faltantes",
    "detectar_denominadores_cero", "detectar_entidades_nuevas_y_desaparecidas",
    "detectar_cambios_de_segmento", "detectar_cambios_abruptos", "reporte_calidad_fecha",
]
