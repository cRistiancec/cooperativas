# -*- coding: utf-8 -*-
"""
Registro estructurado de los indicadores **nuevos** del Motor Central
(Fase 2.3 — migrados del script R de referencia; Fase 2.4 — índices
ejecutivos de segundo nivel). No incluye los 41 indicadores oficiales de la
SEPS: esos ya están descritos en `config/indicator_mapping.py`
(`ETIQUETAS_INDICADORES`, `GRUPOS_INDICADORES`, `RANGOS_HEATMAP`) y
`scripts/generar_documentacion_indicadores.py` los incorpora al catálogo
final leyendo esa fuente directamente — no se duplican aquí.

Cada entrada tiene los 9 campos pedidos para la documentación automática:
nombre, descripción, fórmula, variables, interpretación financiera, rango
esperado, módulo, dependencias y frecuencia de actualización. Este archivo
es la **fuente de datos**; `scripts/generar_documentacion_indicadores.py` es
el que la renderiza a Markdown — separar dato de renderizado es lo que hace
que la documentación sea "automática" (se regenera del código, no se escribe
a mano) en vez de una prosa que se desactualiza en silencio.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EntradaCatalogo:
    codigo: str
    nombre: str
    descripcion: str
    formula: str
    variables: str
    interpretacion: str
    rango_esperado: str
    modulo: str
    dependencias: str
    frecuencia_actualizacion: str
    fuente: str


CATALOGO_NUEVOS_INDICADORES: list[EntradaCatalogo] = [
    # ------------------------------------------------------------------ Rentabilidad
    EntradaCatalogo(
        codigo="TASA_PASIVA_IMPLICITA",
        nombre="Tasa Pasiva Implícita",
        descripcion="Costo efectivo de fondeo: cuánto paga la cooperativa, en promedio, por sus depósitos.",
        formula="interés causado en depósitos (12 meses) / promedio móvil 3 meses de depósitos del público",
        variables="pyg.codigo=4101 (valor_12m); balance.codigo=21 (promedio 3 cortes)",
        interpretacion="Más alta que la del sistema puede indicar dependencia de captación cara (plazo fijo agresivo) para sostener el fondeo.",
        rango_esperado="2% – 15% anual (P5–P95 del sistema, jun-2026)",
        modulo="analytics.rentabilidad.calcular_tasas_implicitas",
        dependencias="pyg.parquet, agg_ranking_cooperativas.parquet",
        frecuencia_actualizacion="Mensual (con cada actualización de datos SEPS)",
        fuente="Calculado — Motor Central (migrado de TASA_PI, script R)",
    ),
    EntradaCatalogo(
        codigo="TASA_ACTIVA_IMPLICITA",
        nombre="Tasa Activa Implícita",
        descripcion="Rendimiento efectivo de la cartera: cuánto genera, en promedio, cada dólar prestado.",
        formula="interés ganado en cartera (12 meses) / promedio móvil 3 meses de cartera bruta",
        variables="pyg.codigo=5104 (valor_12m); balance.codigo=14 (promedio 3 cortes)",
        interpretacion="Muy por encima del sistema puede señalar una cartera de mayor riesgo (tasas más altas compensan mayor probabilidad de impago).",
        rango_esperado="11% – 31% anual (P5–P95 del sistema, jun-2026)",
        modulo="analytics.rentabilidad.calcular_tasas_implicitas",
        dependencias="pyg.parquet, agg_ranking_cooperativas.parquet",
        frecuencia_actualizacion="Mensual",
        fuente="Calculado — Motor Central (migrado de TASA_AI, script R)",
    ),
    EntradaCatalogo(
        codigo="SPREAD_FINANCIERO",
        nombre="Spread Financiero",
        descripcion="Margen de intermediación en puntos porcentuales: la diferencia entre lo que la cooperativa cobra por prestar y lo que paga por captar.",
        formula="tasa_activa_implicita − tasa_pasiva_implicita",
        variables="Ver Tasa Activa Implícita, Tasa Pasiva Implícita",
        interpretacion="Motor estructural de rentabilidad. Un spread que se comprime en el tiempo, con volumen de negocio estable, anticipa presión sobre el margen financiero.",
        rango_esperado="4.5% – 26.5% (P5–P95 del sistema, jun-2026)",
        modulo="analytics.rentabilidad.calcular_tasas_implicitas",
        dependencias="pyg.parquet, agg_ranking_cooperativas.parquet",
        frecuencia_actualizacion="Mensual",
        fuente="Calculado — Motor Central (migrado de TASA_MF, script R)",
    ),
    EntradaCatalogo(
        codigo="MARGEN_FINANCIERO_12M",
        nombre="Margen Financiero (12 meses, USD)",
        descripcion="Resultado financiero neto en dólares: ingresos financieros menos gastos financieros, anualizado.",
        formula="(intereses + comisiones + utilidades financieras + servicios) − (intereses + comisiones + pérdidas financieras + provisiones), suma móvil 12 meses",
        variables="pyg.codigo∈{51,52,53,54,41,42,43,44} (valor_12m)",
        interpretacion="La cifra en dólares detrás del spread — relevante para tamaño absoluto, no solo el ratio.",
        rango_esperado="Positivo en la gran mayoría del sistema; negativo es señal de alerta operativa",
        modulo="analytics.rentabilidad.calcular_margen_financiero",
        dependencias="pyg.parquet",
        frecuencia_actualizacion="Mensual",
        fuente="Calculado — Motor Central (migrado de MARGEN_FINANCIERO, script R)",
    ),
    EntradaCatalogo(
        codigo="ROE_AJUSTADO",
        nombre="ROE Ajustado",
        descripcion="Rentabilidad patrimonial excluyendo ingresos no recurrentes (\"otros ingresos\"), sobre patrimonio promedio de 3 meses.",
        formula="(ingresos − gastos − otros_ingresos) [12m] / patrimonio_promedio_3m",
        variables="pyg.codigo∈{5,4,56} (valor_12m); balance.codigo=3 (promedio 3 cortes)",
        interpretacion="Una brecha grande frente al ROE oficial indica que la rentabilidad reportada depende de partidas no operativas — insumo directo del Índice de Vulnerabilidad.",
        rango_esperado="-105% – 15% (observado en el sistema, jun-2026; el ROE oficial no penaliza otros ingresos y por eso es sistemáticamente más alto)",
        modulo="analytics.rentabilidad.calcular_roe_ajustado",
        dependencias="pyg.parquet, agg_ranking_cooperativas.parquet",
        frecuencia_actualizacion="Mensual",
        fuente="Calculado — Motor Central (migrado de ROE_ADJ, script R)",
    ),
    # ------------------------------------------------------------------ Crecimiento
    EntradaCatalogo(
        codigo="CRECIMIENTO_CAPTACIONES",
        nombre="Crecimiento de Captaciones",
        descripcion="Variación absoluta y porcentual de los depósitos del público entre dos fechas.",
        formula="(depósitos_actual − depósitos_anterior) ; (depósitos_actual / depósitos_anterior − 1) × 100",
        variables="agg_ranking_cooperativas.codigo=21, dos fechas",
        interpretacion="Horizonte anual (fecha_anterior = -12 meses) o mensual (-1 mes), según qué fecha se pase. Contracción sostenida es señal temprana de fuga de depósitos.",
        rango_esperado="Variable — depende del horizonte y del ciclo del sistema",
        modulo="analytics.crecimiento.crecimiento_captaciones",
        dependencias="utils.data_loader.obtener_crecimiento_anual, agg_ranking_cooperativas.parquet",
        frecuencia_actualizacion="Mensual",
        fuente="Calculado — Motor Central (migrado de CAPGA/TCAPGA/CAPGM/TCAPGM, script R)",
    ),
    EntradaCatalogo(
        codigo="CRECIMIENTO_COLOCACIONES",
        nombre="Crecimiento de Colocaciones",
        descripcion="Variación absoluta y porcentual de la cartera bruta entre dos fechas.",
        formula="(cartera_actual − cartera_anterior) ; (cartera_actual / cartera_anterior − 1) × 100",
        variables="agg_ranking_cooperativas.codigo=14, dos fechas",
        interpretacion="Insumo del Score Financiero Integral y del ranking de crecimiento de Panorama. Crecimiento muy por encima del sistema, sin deterioro de mora, puede indicar ganancia de mercado; acompañado de mora al alza, sobre-extensión del crédito.",
        rango_esperado="Variable — depende del horizonte y del ciclo del sistema",
        modulo="analytics.crecimiento.crecimiento_colocaciones",
        dependencias="utils.data_loader.obtener_crecimiento_anual, agg_ranking_cooperativas.parquet",
        frecuencia_actualizacion="Mensual",
        fuente="Calculado — Motor Central (migrado de COLGA/TCOLGA/COLGM/TCOLGM, script R)",
    ),
    EntradaCatalogo(
        codigo="CARTERA_EN_RIESGO",
        nombre="Cartera en Riesgo (CER)",
        descripcion="Suma de la cartera vencida y que no devenga intereses en todas las líneas de negocio (comercial, consumo, inmobiliaria, microcrédito) y modalidades (prioritario, productivo, ordinario).",
        formula="Σ cuentas de cartera vencida / que no devenga intereses (36 cuentas de 4 dígitos)",
        variables="balance.codigo∈CODIGOS_CARTERA_EN_RIESGO (36 códigos, ver analytics/crecimiento.py)",
        interpretacion="Medida en dólares (no ratio) de exposición crediticia deteriorada — complementa a MOR_TOT (%) con la magnitud absoluta.",
        rango_esperado="Variable según tamaño de la institución",
        modulo="analytics.crecimiento.calcular_cartera_en_riesgo",
        dependencias="utils.data_loader.cargar_balance_por_codigos, balance.parquet",
        frecuencia_actualizacion="Mensual",
        fuente="Calculado — Motor Central (migrado de CER, script R)",
    ),
    # ------------------------------------------------------------------ Índices ejecutivos
    EntradaCatalogo(
        codigo="SCORE_FINANCIERO_INTEGRAL",
        nombre="Score Financiero Integral",
        descripcion="Índice compuesto 0-100 de salud financiera general, combinando seis dimensiones con igual ponderación.",
        formula="promedio simple de percentiles orientados: liquidez(LIQ) + solvencia(SUF_PAT) + rentabilidad(ROE) + cobertura(COB_TOT) + morosidad(MOR_TOT, invertido) + crecimiento(cartera YoY)",
        variables="indicadores.parquet (LIQ, SUF_PAT, ROE, COB_TOT, MOR_TOT); crecimiento_colocaciones",
        interpretacion="100 = mejor desempeño relativo dentro del universo comparado (sistema o segmento) en la fecha de corte. Es un ranking relativo, no una nota absoluta — no es comparable entre fechas distintas ni entre universos distintos (Todos vs. un segmento).",
        rango_esperado="0-100 por construcción (percentiles); en la práctica P25≈38, P75≈63 (jun-2026)",
        modulo="analytics.indices_ejecutivos.calcular_score_financiero_integral",
        dependencias="analytics.camels_score._percentil_orientado, analytics.crecimiento.crecimiento_colocaciones, indicadores.parquet",
        frecuencia_actualizacion="Mensual",
        fuente="Nuevo — no existe en el script R (índice de segundo nivel pedido en la ampliación)",
    ),
    EntradaCatalogo(
        codigo="INDICE_VULNERABILIDAD",
        nombre="Índice de Vulnerabilidad",
        descripcion="Índice compuesto 0-100 de fragilidad financiera: 100 = más vulnerable dentro del universo comparado.",
        formula="percentil del z-score promedio de: MOR_TOT, VULN_PAT, CART_IMPR_PAT, y la brecha (ROE oficial − ROE ajustado)",
        variables="indicadores.parquet (MOR_TOT, VULN_PAT, CART_IMPR_PAT, ROE); ROE_AJUSTADO",
        interpretacion="La brecha de ROE es la señal nueva (no está en el R ni la publica la SEPS por separado): una brecha grande indica que la rentabilidad reportada depende de ingresos no recurrentes, no de la operación central.",
        rango_esperado="0-100 por construcción; distribución centrada en 50 por diseño (z-score)",
        modulo="analytics.indices_ejecutivos.calcular_indice_vulnerabilidad",
        dependencias="analytics.rentabilidad.calcular_roe_ajustado, indicadores.parquet, pyg.parquet, agg_ranking_cooperativas.parquet",
        frecuencia_actualizacion="Mensual",
        fuente="Nuevo — no existe en el script R",
    ),
    EntradaCatalogo(
        codigo="INDICE_FORTALEZA",
        nombre="Índice de Fortaleza",
        descripcion="Índice compuesto 0-100: 100 = institución más sólida dentro del universo comparado.",
        formula="promedio simple de percentiles orientados: SUF_PAT + LIQ + COB_TOT + ROA + ROE + crecimiento de activos YoY",
        variables="indicadores.parquet (SUF_PAT, LIQ, COB_TOT, ROA, ROE); crecimiento_activos",
        interpretacion="Similar en construcción al Score Financiero Integral pero con foco en capital, liquidez y cobertura (defensivo) más crecimiento — no morosidad, que es el foco del Índice de Vulnerabilidad.",
        rango_esperado="0-100 por construcción; P25≈37, P75≈65 (jun-2026)",
        modulo="analytics.indices_ejecutivos.calcular_indice_fortaleza",
        dependencias="analytics.camels_score._percentil_orientado, analytics.crecimiento.crecimiento_activos, indicadores.parquet",
        frecuencia_actualizacion="Mensual",
        fuente="Nuevo — no existe en el script R",
    ),
    EntradaCatalogo(
        codigo="INDICE_RESILIENCIA",
        nombre="Índice de Resiliencia",
        descripcion="Índice compuesto 0-100: capacidad de una institución de soportar un escenario de estrés (por defecto, \"Severo\").",
        formula="percentil de solvencia_post-shock, con penalización de 20 puntos si queda capital insuficiente y 10 si queda brecha de liquidez",
        variables="Salida de analytics.stress_testing.aplicar_escenario",
        interpretacion="Reutiliza el motor de Stress Testing existente en vez de duplicar la mecánica de shock — es \"capacidad para soportar escenarios adversos\" aplicando el módulo que la plataforma ya tiene para eso.",
        rango_esperado="0-100 por construcción",
        modulo="analytics.indices_ejecutivos.calcular_indice_resiliencia",
        dependencias="analytics.stress_testing.construir_panel_balance, analytics.stress_testing.aplicar_escenario, agg_ranking_cooperativas.parquet",
        frecuencia_actualizacion="Mensual",
        fuente="Nuevo — no existe en el script R",
    ),
    EntradaCatalogo(
        codigo="INDICE_ESTABILIDAD",
        nombre="Índice de Estabilidad",
        descripcion="Índice compuesto 0-100: promedio de \"nivel\" (percentil actual) y \"consistencia\" (baja volatilidad histórica) de liquidez, morosidad y rentabilidad.",
        formula="0.5 × percentil(LIQ, MOR_TOT invertido, ROE en la fecha de corte) + 0.5 × percentil(1/coef._variación de esos mismos indicadores en los últimos 12 meses)",
        variables="indicadores.parquet (LIQ, MOR_TOT, ROE), ventana de 12 meses",
        interpretacion="Diferencia deliberada frente a Fortaleza/Score Integral (que solo miran el corte actual): una cooperativa cuya morosidad oscila mucho mes a mes es menos \"estable\" que otra con el mismo nivel promedio pero consistente.",
        rango_esperado="0-100 por construcción; P25≈39, P75≈61 (jun-2026)",
        modulo="analytics.indices_ejecutivos.calcular_indice_estabilidad",
        dependencias="analytics.camels_score._percentil_orientado, indicadores.parquet (12 meses de historia)",
        frecuencia_actualizacion="Mensual",
        fuente="Nuevo — no existe en el script R",
    ),
    EntradaCatalogo(
        codigo="INDICE_RIESGO_INTEGRAL",
        nombre="Índice de Riesgo Integral",
        descripcion="Índice compuesto 0-100 (100 = mejor / menor riesgo) que combina Score Financiero Integral, Índice de Vulnerabilidad y alertas activas, clasificado en 7 bandas.",
        formula="0.5 × score_financiero_integral + 0.3 × (100 − indice_vulnerabilidad) + 0.2 × (100 − alertas_normalizado)",
        variables="Salidas de calcular_score_financiero_integral, calcular_indice_vulnerabilidad, evaluar_alertas",
        interpretacion="Clasificación en 7 bandas: Excelente (≥85) / Muy Bueno (≥70) / Bueno (≥55) / Vigilancia (≥40) / Riesgo Medio (≥25) / Riesgo Alto (≥10) / Riesgo Crítico (<10). Ponderaciones documentadas en PESOS_RIESGO_INTEGRAL — ajustables por Riesgos y Estudios sin tocar la estructura del módulo.",
        rango_esperado="0-100 por construcción; observado 30-85 (jun-2026, ningún caso llegó a Riesgo Alto/Crítico en esa fecha)",
        modulo="analytics.indices_ejecutivos.calcular_indice_riesgo_integral",
        dependencias="calcular_score_financiero_integral, calcular_indice_vulnerabilidad, analytics.alertas.evaluar_alertas",
        frecuencia_actualizacion="Mensual",
        fuente="Nuevo — no existe en el script R",
    ),
]
