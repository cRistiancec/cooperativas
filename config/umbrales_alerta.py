# -*- coding: utf-8 -*-
"""
Umbrales del sistema de Alertas Tempranas.

IMPORTANTE: estos umbrales son **referenciales**, calibrados sobre los
percentiles P75/P90 (cola de riesgo elevado) de la distribución real del
sistema a jun-2026 —no sobre la mediana, para evitar que "estar por debajo
del promedio" se confunda con una alerta— y en prácticas supervisoras
habituales. **No constituyen límites regulatorios oficiales de la SEPS ni
de COSEDE.** Se centralizan aquí (en vez de dispersos en cada página) para
que Riesgos y Estudios pueda auditarlos y ajustarlos en un solo lugar.

Cada regla define, sobre un indicador oficial (ratio 0-1 salvo que se
indique lo contrario):
    - `alerta_amarilla`: umbral de vigilancia.
    - `alerta_roja`: umbral crítico.
    - `direccion`: 'mayor_es_peor' o 'menor_es_peor'.
"""

from __future__ import annotations

from typing import Dict, TypedDict


class ReglaAlerta(TypedDict):
    etiqueta: str
    alerta_amarilla: float
    alerta_roja: float
    direccion: str  # 'mayor_es_peor' | 'menor_es_peor'


REGLAS_ALERTA: Dict[str, ReglaAlerta] = {
    'MOR_TOT': {
        # P75 ≈ 9.9%, P90 ≈ 12.1% (jun-2026): se flaggea la cola alta, no la mediana (~7.1%).
        'etiqueta': 'Morosidad Total',
        'alerta_amarilla': 0.10,   # 10%
        'alerta_roja': 0.14,       # 14%
        'direccion': 'mayor_es_peor',
    },
    'ROE': {
        # P25 ≈ 0.2%, P10 ≈ -3.7% (jun-2026).
        'etiqueta': 'Rentabilidad Patrimonial (ROE)',
        'alerta_amarilla': 0.01,   # < 1% anual
        'alerta_roja': -0.02,      # < -2% anual
        'direccion': 'menor_es_peor',
    },
    'ROA': {
        # P25 ≈ 0.02%, P10 ≈ -0.48% (jun-2026).
        'etiqueta': 'Rentabilidad de Activos (ROA)',
        'alerta_amarilla': 0.001,
        'alerta_roja': -0.002,
        'direccion': 'menor_es_peor',
    },
    'LIQ': {
        'etiqueta': 'Liquidez (Fondos Disp. / Depósitos CP)',
        'alerta_amarilla': 0.15,
        'alerta_roja': 0.10,
        'direccion': 'menor_es_peor',
    },
    'CAP_NETO': {
        # ADVERTENCIA METODOLÓGICA (auditoría sep-2026 contra Fichas Metodológicas
        # SEPS v3.0): CAP_NETO = FK/FI (ficha 57), NO es el ratio de Solvencia
        # oficial (PTC / Activos Ponderados por Riesgo, ficha 62). El 9% de abajo
        # es un umbral referencial propio de este módulo (percentil, ver cabecera
        # del archivo); NO debe leerse como "cumple el 9% mínimo regulatorio de
        # Solvencia" (ficha 63) — ese indicador requiere el Formulario de
        # Solvencia (FS01), fuente que este pipeline no procesa. Ver
        # docs/RIESGO_METODOLOGIA.md §3.2.
        'etiqueta': 'Capitalización Neta (FK/FI)',
        'alerta_amarilla': 0.09,
        'alerta_roja': 0.06,
        'direccion': 'menor_es_peor',
    },
    'VULN_PAT': {
        'etiqueta': 'Vulnerabilidad Patrimonial',
        'alerta_amarilla': 0.30,   # 30%
        'alerta_roja': 0.60,       # 60%
        'direccion': 'mayor_es_peor',
    },
    'COB_TOT': {
        # P25 ≈ 92%, P10 ≈ 70% (jun/jul-2026). Cobertura < 100% ya significa
        # que las provisiones no alcanzan a cubrir toda la cartera
        # improductiva; se flaggea la cola donde la brecha es amplia.
        # Agregado sep-2026 como insumo para la regla de interacción
        # "deterioro de cartera compuesto" (morosidad↑ + cobertura↓ + ROA↓,
        # ver analytics/interaccion.py) — antes no existía ninguna regla de
        # alerta para cobertura en este módulo.
        'etiqueta': 'Cobertura de Cartera Improductiva',
        'alerta_amarilla': 0.80,   # 80%
        'alerta_roja': 0.60,       # 60%
        'direccion': 'menor_es_peor',
    },
}

# Crecimiento interanual de depósitos: una caída fuerte es señal de fuga de depósitos.
UMBRAL_CAIDA_DEPOSITOS_AMARILLA = -5.0   # % interanual
UMBRAL_CAIDA_DEPOSITOS_ROJA = -15.0      # % interanual

# Número de alertas activas (de las reglas anteriores) para clasificar el semáforo agregado.
UMBRAL_NUM_ALERTAS_AMARILLO = 1
UMBRAL_NUM_ALERTAS_ROJO = 3
