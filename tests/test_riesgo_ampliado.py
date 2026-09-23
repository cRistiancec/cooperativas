# -*- coding: utf-8 -*-
"""
Tests unitarios de los módulos de riesgo ampliado (persistencia, breadth,
interacción, calidad de datos, estado sistémico, eventos, backtesting, IPSF)
con datos sintéticos — mismo criterio que `tests/test_analytics.py`: no
dependen de `master_data/`, por velocidad e independencia del entorno.

Los tests que sí necesitan verificar los datos reales (segmento_historico
vs segmento_actual, cobertura de solvencia.parquet, entidades_cooperativas)
están en `tests/test_consistencia_datos.py`, junto al resto de pruebas de
consistencia sobre `master_data/`.
"""

from __future__ import annotations

import unittest

import pandas as pd

from analytics.alertas import evaluar_alertas
from analytics.backtesting import evaluar_alertas_previas_a_eventos
from analytics.breadth import UMBRAL_GENERALIZADO_PCT, calcular_breadth
from analytics.data_quality import (
    detectar_cambios_de_segmento,
    detectar_denominadores_cero,
    detectar_entidades_nuevas_y_desaparecidas,
    validar_duplicados,
    validar_fechas,
)
from analytics.crecimiento import calcular_crecimiento_yoy_mensual
from analytics.eventos import detectar_eventos_salida
from analytics.interaccion import REGLAS_INTERACCION, evaluar_interacciones
from analytics.ipsf import calcular_ipsf_periodo, calcular_serie_ipsf, diagnostico_esquemas
from analytics.persistencia import calcular_persistencia_alertas, ventana_fechas
from analytics.riesgo_sistemico_estado import ESTADOS, evaluar_estado_sistemico
from services.asistente_ia import _aplicar_guardrails_deterministicos, construir_contexto_sistema, responder_local


def _fecha(mes_str):
    return pd.Timestamp(mes_str)


def _fila_indicador(coop, fecha, codigo, valor, segmento="SEGMENTO 1"):
    return {"cooperativa": coop, "segmento": segmento, "fecha": fecha, "codigo": codigo, "valor": valor}


class PersistenciaTests(unittest.TestCase):
    def _construir_panel(self):
        """
        4 meses. CRONICA: alerta roja de morosidad los 4 meses (persistente).
        NUEVA: solo alerta en el último mes. INTERMITENTE: alerta en meses 1 y
        3, sana en 2 y 4 (recurrente, pero NO activa hoy).
        """
        fechas = [_fecha(m) for m in ["2026-04-30", "2026-05-31", "2026-06-30", "2026-07-31"]]
        patrones = {
            "CRONICA": [0.20, 0.20, 0.20, 0.20],
            "NUEVA": [0.03, 0.03, 0.03, 0.20],
            "INTERMITENTE": [0.20, 0.03, 0.20, 0.03],
            "SANA": [0.03, 0.03, 0.03, 0.03],
        }
        filas = []
        for coop, valores in patrones.items():
            for fecha, valor in zip(fechas, valores):
                filas.append(_fila_indicador(coop, fecha, "MOR_TOT", valor))
                filas.append(_fila_indicador(coop, fecha, "ROE", 0.05))
        return pd.DataFrame(filas), fechas

    def test_clasifica_persistente_nueva_recurrente_correctamente(self):
        df, fechas = self._construir_panel()
        resultado = calcular_persistencia_alertas(df, fechas, umbral_persistente_meses=3)
        resultado = resultado.set_index("cooperativa")

        self.assertTrue(resultado.loc["CRONICA", "alerta_persistente"])
        self.assertEqual(resultado.loc["CRONICA", "meses_consecutivos_activa"], 4)

        self.assertTrue(resultado.loc["NUEVA", "alerta_nueva"])
        self.assertFalse(resultado.loc["NUEVA", "alerta_persistente"])

        self.assertTrue(resultado.loc["INTERMITENTE", "alerta_recurrente"])
        self.assertEqual(resultado.loc["INTERMITENTE", "meses_consecutivos_activa"], 0)

        self.assertEqual(resultado.loc["SANA", "meses_consecutivos_activa"], 0)
        self.assertFalse(resultado.loc["SANA", "alerta_recurrente"])

    def test_ventana_fechas_respeta_el_limite_y_la_referencia(self):
        fechas_disponibles = [_fecha(m) for m in
                               ["2026-01-31", "2026-02-28", "2026-03-31", "2026-04-30", "2026-05-31"]]
        ventana = ventana_fechas(fechas_disponibles, _fecha("2026-04-30"), 2)
        self.assertEqual(ventana, [_fecha("2026-03-31"), _fecha("2026-04-30")])


class BreadthTests(unittest.TestCase):
    def _df_ranking(self):
        fecha = _fecha("2026-07-31")
        filas = []
        # GRANDE concentra el 40% de los activos; el resto se reparte entre 4 pequeñas.
        pesos = {"GRANDE": 400.0, "PEQ_1": 150.0, "PEQ_2": 150.0, "PEQ_3": 150.0, "PEQ_4": 150.0}
        for coop, activos in pesos.items():
            filas.append({"cooperativa": coop, "segmento": "SEGMENTO 1", "fecha": fecha,
                           "codigo": "1", "valor": activos})
        return pd.DataFrame(filas), fecha

    def test_una_entidad_grande_afectada_es_generalizado(self):
        df_ranking, fecha = self._df_ranking()
        resultado = calcular_breadth(["GRANDE"], df_ranking, fecha)
        self.assertGreaterEqual(resultado["dimensiones"]["activos"], UMBRAL_GENERALIZADO_PCT)
        self.assertEqual(resultado["clasificacion"], "RIESGO GENERALIZADO")

    def test_una_entidad_pequena_afectada_es_concentrado(self):
        df_ranking, fecha = self._df_ranking()
        resultado = calcular_breadth(["PEQ_1"], df_ranking, fecha)
        self.assertLess(resultado["dimensiones"]["activos"], UMBRAL_GENERALIZADO_PCT)
        self.assertEqual(resultado["clasificacion"], "RIESGO CONCENTRADO")

    def test_sin_afectadas_devuelve_cero_por_ciento(self):
        df_ranking, fecha = self._df_ranking()
        resultado = calcular_breadth([], df_ranking, fecha)
        self.assertEqual(resultado["dimensiones"]["activos"], 0.0)


class InteraccionTests(unittest.TestCase):
    def test_deterioro_cartera_compuesto_se_activa_solo_con_las_tres_senales(self):
        fecha = _fecha("2026-07-31")
        df = pd.DataFrame([
            {"cooperativa": "TRIPLE", "segmento": "SEGMENTO 1", "fecha": fecha,
             "codigo": "MOR_TOT", "valor": 0.20},
        ])
        # Construir manualmente la salida de evaluar_alertas simulada (columnas sev_*)
        alertas = pd.DataFrame([
            {"cooperativa": "TRIPLE", "segmento": "SEGMENTO 1", "sev_MOR_TOT": 2, "sev_COB_TOT": 1, "sev_ROA": 1,
             "alertas_rojas": 1, "alertas_amarillas": 2},
            {"cooperativa": "SOLO_MORA", "segmento": "SEGMENTO 1", "sev_MOR_TOT": 2, "sev_COB_TOT": 0, "sev_ROA": 0,
             "alertas_rojas": 1, "alertas_amarillas": 0},
        ])
        resultado = evaluar_interacciones(alertas)
        self.assertTrue(resultado.set_index("cooperativa").loc["TRIPLE", "deterioro_cartera_compuesto"])
        self.assertFalse(resultado.set_index("cooperativa").loc["SOLO_MORA", "deterioro_cartera_compuesto"])

    def test_regla_sin_columnas_disponibles_se_omite_sin_error(self):
        alertas = pd.DataFrame([
            {"cooperativa": "X", "segmento": "SEGMENTO 1", "sev_MOR_TOT": 2, "sev_COB_TOT": 2, "sev_ROA": 1,
             "alertas_rojas": 2, "alertas_amarillas": 0},
        ])
        resultado = evaluar_interacciones(alertas)
        self.assertNotIn("presion_fondeo", resultado.columns)
        self.assertIn("n_interacciones_activas", resultado.columns)

    def test_todas_las_reglas_documentan_su_mecanismo_economico(self):
        for nombre, regla in REGLAS_INTERACCION.items():
            self.assertGreater(len(regla["descripcion"]), 40, msg=f"{nombre} sin justificación suficiente")


class DataQualityTests(unittest.TestCase):
    def test_validar_fechas_detecta_un_mes_faltante(self):
        fechas = [_fecha(m) for m in ["2026-01-31", "2026-02-28", "2026-04-30"]]  # falta marzo
        df = pd.DataFrame({"fecha": fechas})
        resultado = validar_fechas(df)
        self.assertTrue(resultado["tiene_huecos"])
        self.assertEqual(len(resultado["meses_faltantes"]), 1)

    def test_validar_duplicados_detecta_clave_repetida(self):
        fecha = _fecha("2026-07-31")
        df = pd.DataFrame([
            {"cooperativa": "A", "codigo": "MOR_TOT", "fecha": fecha, "valor": 0.05},
            {"cooperativa": "A", "codigo": "MOR_TOT", "fecha": fecha, "valor": 0.06},
        ])
        resultado = validar_duplicados(df, ["cooperativa", "codigo"])
        self.assertEqual(resultado["registros_con_clave_duplicada"], 2)

    def test_detectar_denominadores_cero(self):
        fecha = _fecha("2026-07-31")
        df_ranking = pd.DataFrame([
            {"cooperativa": "OK", "segmento": "SEGMENTO 1", "fecha": fecha, "codigo": "1", "valor": 100.0},
            {"cooperativa": "SIN_ACTIVOS", "segmento": "SEGMENTO 1", "fecha": fecha, "codigo": "1", "valor": 0.0},
        ])
        resultado = detectar_denominadores_cero(df_ranking, fecha, codigo_denominador="1")
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado.iloc[0]["cooperativa"], "SIN_ACTIVOS")

    def test_detectar_cambios_de_segmento(self):
        df = pd.DataFrame([
            {"cooperativa": "MIGRA", "fecha": _fecha("2020-01-31"), "segmento_historico": "SEGMENTO 3"},
            {"cooperativa": "MIGRA", "fecha": _fecha("2026-01-31"), "segmento_historico": "SEGMENTO 1"},
            {"cooperativa": "ESTABLE", "fecha": _fecha("2020-01-31"), "segmento_historico": "SEGMENTO 2"},
            {"cooperativa": "ESTABLE", "fecha": _fecha("2026-01-31"), "segmento_historico": "SEGMENTO 2"},
        ])
        resultado = detectar_cambios_de_segmento(df)
        self.assertIn("MIGRA", resultado["cooperativa"].tolist())
        self.assertNotIn("ESTABLE", resultado["cooperativa"].tolist())

    def test_detectar_entidades_nuevas_y_desaparecidas(self):
        df = pd.DataFrame([
            {"cooperativa": "VIEJA", "fecha": _fecha("2026-06-30")},
            {"cooperativa": "VIEJA", "fecha": _fecha("2026-07-31")},
            {"cooperativa": "NUEVA", "fecha": _fecha("2026-07-31")},
            {"cooperativa": "DESAPARECIDA", "fecha": _fecha("2026-06-30")},
        ])
        resultado = detectar_entidades_nuevas_y_desaparecidas(
            df, fecha_actual=_fecha("2026-07-31"), fecha_anterior=_fecha("2026-06-30")
        )
        self.assertIn("NUEVA", resultado["nuevas"])
        self.assertNotIn("VIEJA", resultado["nuevas"])
        self.assertIn("DESAPARECIDA", resultado["desaparecidas"])


class EventosTests(unittest.TestCase):
    def test_detecta_salida_por_cese_de_reporte(self):
        fechas_activa = [_fecha(m) for m in ["2026-01-31", "2026-07-31"]]
        fechas_salida = [_fecha(m) for m in ["2026-01-31", "2026-02-28"]]
        df = pd.DataFrame(
            [{"cooperativa": "ACTIVA", "fecha": f} for f in fechas_activa]
            + [{"cooperativa": "SALIO EN LIQUIDACION", "fecha": f} for f in fechas_salida]
        )
        resultado = detectar_eventos_salida(df, meses_gracia=3)
        self.assertIn("SALIO EN LIQUIDACION", resultado["cooperativa"].tolist())
        self.assertNotIn("ACTIVA", resultado["cooperativa"].tolist())
        fila = resultado.set_index("cooperativa").loc["SALIO EN LIQUIDACION"]
        self.assertTrue(fila["liquidacion_declarada_en_nombre"])


class RiesgoSistemicoEstadoTests(unittest.TestCase):
    def _panel_normal(self):
        fechas = [_fecha("2025-07-31"), _fecha("2026-07-31")]
        filas = []
        for coop in ["A", "B", "C", "D", "E"]:
            for fecha, factor in zip(fechas, [1.0, 1.10]):  # +10% YoY, sano
                filas.append({"cooperativa": coop, "segmento": "SEGMENTO 1", "fecha": fecha,
                               "codigo": "1", "valor": 100.0 * factor})
                filas.append({"cooperativa": coop, "segmento": "SEGMENTO 1", "fecha": fecha,
                               "codigo": "14", "valor": 80.0 * factor})
                filas.append({"cooperativa": coop, "segmento": "SEGMENTO 1", "fecha": fecha,
                               "codigo": "21", "valor": 70.0 * factor})
        df_ranking = pd.DataFrame(filas)
        df_ind = pd.DataFrame([
            {"cooperativa": coop, "segmento": "SEGMENTO 1", "fecha": fecha, "codigo": "MOR_TOT", "valor": 0.03}
            for coop in ["A", "B", "C", "D", "E"] for fecha in fechas
        ])
        return df_ind, df_ranking, fechas

    def test_estado_normal_con_crecimiento_sano_y_sin_alertas(self):
        df_ind, df_ranking, fechas = self._panel_normal()
        resultado = evaluar_estado_sistemico(df_ind, df_ranking, fechas[-1], fechas[0])
        self.assertEqual(resultado["estado"], "NORMAL")
        self.assertIn(resultado["estado"], ESTADOS)

    def test_nunca_devuelve_la_palabra_crisis(self):
        df_ind, df_ranking, fechas = self._panel_normal()
        resultado = evaluar_estado_sistemico(df_ind, df_ranking, fechas[-1], fechas[0])
        self.assertNotIn("CRISIS", resultado["estado"].upper())

    def test_contraccion_de_cartera_aislada_no_escala_sin_breadth_ni_persistencia(self):
        """
        Hardening 14-sep-2026: una caída YoY en una sola dimensión (aquí,
        cartera -20%, con activos/depósitos sanos, sin breadth ni
        persistencia) NO debe alcanzar la familia "CONTRACCIÓN" — el
        objetivo prohíbe explícitamente equiparar "contracción" con "caída
        aislada de cartera". Debe quedar acotada a DESACELERACIÓN.
        """
        fechas = [_fecha("2025-07-31"), _fecha("2026-07-31")]
        filas = []
        for coop in ["A", "B", "C", "D", "E"]:
            filas.append({"cooperativa": coop, "segmento": "SEGMENTO 1", "fecha": fechas[0],
                           "codigo": "14", "valor": 100.0})
            filas.append({"cooperativa": coop, "segmento": "SEGMENTO 1", "fecha": fechas[1],
                           "codigo": "14", "valor": 80.0})  # -20% YoY, aislado
            for codigo in ("1", "21"):
                filas.append({"cooperativa": coop, "segmento": "SEGMENTO 1", "fecha": fechas[0],
                               "codigo": codigo, "valor": 100.0})
                filas.append({"cooperativa": coop, "segmento": "SEGMENTO 1", "fecha": fechas[1],
                               "codigo": codigo, "valor": 112.0})  # +12% YoY, sano
        df_ranking = pd.DataFrame(filas)
        df_ind = pd.DataFrame([
            {"cooperativa": coop, "segmento": "SEGMENTO 1", "fecha": fecha, "codigo": "MOR_TOT", "valor": 0.03}
            for coop in ["A", "B", "C", "D", "E"] for fecha in fechas
        ])
        resultado = evaluar_estado_sistemico(df_ind, df_ranking, fechas[-1], fechas[0])
        self.assertEqual(resultado["estado"], "DESACELERACIÓN")
        self.assertNotIn("CONTRACCIÓN", resultado["estado"])


class BacktestingTests(unittest.TestCase):
    def test_evalua_alerta_previa_antes_de_un_evento_de_salida(self):
        fechas = [_fecha(m) for m in
                  ["2026-01-31", "2026-02-28", "2026-03-31", "2026-04-30", "2026-05-31"]]
        filas = []
        for fecha in fechas:
            filas.append(_fila_indicador("DETERIORO_PREVIO", fecha, "MOR_TOT", 0.20))
            filas.append(_fila_indicador("DETERIORO_PREVIO", fecha, "ROE", 0.05))
        # Deja de reportar tras 2026-03-31 (tiene 2+ meses de alerta antes de salir).
        df = pd.DataFrame(filas)
        df = df[~((df["cooperativa"] == "DETERIORO_PREVIO") & (df["fecha"] > _fecha("2026-03-31")))]

        # Referencia sana que sigue reportando todo el período (evita eventos falsos y da "fecha_max").
        for fecha in fechas:
            df = pd.concat([df, pd.DataFrame([
                _fila_indicador("REFERENCIA", fecha, "MOR_TOT", 0.03),
                _fila_indicador("REFERENCIA", fecha, "ROE", 0.05),
            ])], ignore_index=True)

        resultado = evaluar_alertas_previas_a_eventos(df, meses_anticipacion=3, meses_gracia_evento=1,
                                                        umbral_persistente_meses=1)
        self.assertGreaterEqual(resultado["n_eventos_proxy"], 1)
        self.assertIn("DETERIORO_PREVIO", resultado["detalle"]["cooperativa"].tolist())
        fila = resultado["detalle"].set_index("cooperativa").loc["DETERIORO_PREVIO"]
        self.assertTrue(fila["tuvo_alerta_previa"])

    def test_documenta_limitaciones_siempre(self):
        df = pd.DataFrame(columns=["cooperativa", "fecha", "codigo", "valor"])
        resultado = evaluar_alertas_previas_a_eventos(df)
        self.assertGreater(len(resultado["limitaciones"]), 0)


class IPSFTests(unittest.TestCase):
    def _panel(self):
        fechas = [_fecha("2025-07-31"), _fecha("2026-07-31")]
        filas = []
        for coop in ["A", "B", "C"]:
            for fecha in fechas:
                filas.append({"cooperativa": coop, "segmento": "SEGMENTO 1", "fecha": fecha,
                               "codigo": "14", "valor": 100.0})
                filas.append({"cooperativa": coop, "segmento": "SEGMENTO 1", "fecha": fecha,
                               "codigo": "21", "valor": 100.0})
                filas.append({"cooperativa": coop, "segmento": "SEGMENTO 1", "fecha": fecha,
                               "codigo": "1", "valor": 100.0})
        df_ranking = pd.DataFrame(filas)
        df_ind = pd.DataFrame([
            {"cooperativa": coop, "segmento": "SEGMENTO 1", "fecha": fecha, "codigo": "MOR_TOT", "valor": 0.03}
            for coop in ["A", "B", "C"] for fecha in fechas
        ])
        return df_ind, df_ranking, fechas

    def test_componentes_en_rango_0_100(self):
        df_ind, df_ranking, fechas = self._panel()
        resultado = calcular_ipsf_periodo(df_ind, df_ranking, fechas[-1])
        for valor in resultado["componentes"].values():
            self.assertGreaterEqual(valor, 0.0)
            self.assertLessEqual(valor, 100.0)
        for valor in resultado["ipsf"].values():
            self.assertGreaterEqual(valor, 0.0)
            self.assertLessEqual(valor, 100.0)

    def test_diagnostico_esquemas_sobre_serie_vacia_no_es_valido(self):
        self.assertFalse(diagnostico_esquemas(pd.DataFrame())["valido"])

    def test_serie_ipsf_tiene_una_fila_por_fecha_con_datos(self):
        df_ind, df_ranking, fechas = self._panel()
        serie = calcular_serie_ipsf(df_ind, df_ranking, fechas)
        self.assertLessEqual(len(serie), len(fechas))


class CrecimientoYoYMensualTests(unittest.TestCase):
    """
    Hardening 14-sep-2026 (P1): `pages/2_Balance_General.py` reimplementaba
    inline el crecimiento YoY mes a mes para el heatmap mensual. Se
    centralizó en `analytics.crecimiento.calcular_crecimiento_yoy_mensual`.
    Este test reproduce la fórmula ORIGINAL (tal como vivía en la página
    antes del refactor) y verifica equivalencia numérica exacta contra la
    función centralizada — no debe cambiar ningún resultado.
    """

    def _implementacion_original_de_la_pagina(self, df_completo, codigo, segmento="Todos", cooperativas=None):
        """Copia literal de la lógica que vivía en obtener_datos_heatmap_mensual() antes del refactor."""
        df_filtrado = df_completo[df_completo['codigo'] == codigo].copy()
        if segmento != "Todos":
            df_filtrado = df_filtrado[df_filtrado['segmento'] == segmento]
        if cooperativas:
            df_filtrado = df_filtrado[df_filtrado['cooperativa'].isin(cooperativas)]
        if df_filtrado.empty:
            return df_filtrado

        df_filtrado['año'] = df_filtrado['fecha'].dt.year
        df_filtrado['mes'] = df_filtrado['fecha'].dt.month
        df_filtrado['valor_millones'] = df_filtrado['valor'] / 1_000_000
        df_filtrado = df_filtrado.sort_values(['cooperativa', 'año', 'mes'])
        df_filtrado['valor_ano_anterior'] = df_filtrado.groupby(['cooperativa', 'mes'], observed=True)['valor_millones'].shift(1)
        df_filtrado['crecimiento_yoy'] = ((df_filtrado['valor_millones'] / df_filtrado['valor_ano_anterior']) - 1) * 100
        return df_filtrado

    def _panel_multi_cooperativa_multi_anio(self):
        filas = []
        # 3 cooperativas, 26 meses (para cubrir ≥2 años completos + un cambio de segmento en una de ellas).
        fechas = pd.date_range("2024-06-30", periods=26, freq="ME")
        valores_base = {"A": 100.0, "B": 250.0, "C": 40.0}
        for coop, base in valores_base.items():
            for i, fecha in enumerate(fechas):
                segmento = "SEGMENTO 2" if (coop == "B" and fecha < pd.Timestamp("2025-06-30")) else "SEGMENTO 1"
                valor = base * (1 + 0.01 * i) * 1_000_000  # valores grandes, como cuentas reales de balance
                filas.append({"cooperativa": coop, "segmento": segmento, "fecha": fecha,
                               "codigo": "1", "valor": valor})
        return pd.DataFrame(filas)

    def test_equivalencia_numerica_exacta_con_la_implementacion_original(self):
        df = self._panel_multi_cooperativa_multi_anio()
        original = self._implementacion_original_de_la_pagina(df, "1")
        nuevo = calcular_crecimiento_yoy_mensual(df, "1")

        original = original.sort_values(["cooperativa", "fecha"]).reset_index(drop=True)
        nuevo = nuevo.sort_values(["cooperativa", "fecha"]).reset_index(drop=True)

        self.assertEqual(len(original), len(nuevo))
        pd.testing.assert_series_equal(
            original["crecimiento_yoy"].reset_index(drop=True),
            nuevo["crecimiento_yoy"].reset_index(drop=True),
            check_names=False, atol=1e-9,
        )

    def test_equivalencia_con_filtro_de_segmento(self):
        df = self._panel_multi_cooperativa_multi_anio()
        original = self._implementacion_original_de_la_pagina(df, "1", segmento="SEGMENTO 1")
        nuevo = calcular_crecimiento_yoy_mensual(df, "1", segmento="SEGMENTO 1")
        self.assertEqual(len(original), len(nuevo))
        # SEGMENTO 1 excluye a "B" antes de 2025-06-30 — confirma que el filtro se aplicó igual en ambas.
        self.assertEqual(set(original["cooperativa"].unique()), set(nuevo["cooperativa"].unique()))

    def test_primer_anio_de_cada_cooperativa_queda_sin_comparacion(self):
        df = self._panel_multi_cooperativa_multi_anio()
        nuevo = calcular_crecimiento_yoy_mensual(df, "1")
        primeros_12_meses = nuevo.sort_values(["cooperativa", "fecha"]).groupby("cooperativa").head(12)
        self.assertTrue(primeros_12_meses["crecimiento_yoy"].isna().all())


class AsistenteIATests(unittest.TestCase):
    """
    Hardening 14-sep-2026: el Asistente IA no debe depender únicamente de
    instrucciones de prompt para controles críticos. Estos tests verifican
    la capa determinística (`_aplicar_guardrails_deterministicos`) y que el
    modo local (sin LLM) nunca inventa datos.
    """

    def test_guardrail_marca_la_palabra_crisis(self):
        r = _aplicar_guardrails_deterministicos("El sistema atraviesa una crisis sistémica.")
        self.assertIn("Aviso automático", r)
        self.assertIn("EVENTO EXTREMO", r)

    def test_guardrail_no_modifica_respuestas_sin_la_palabra_prohibida(self):
        original = "El sistema está en desaceleración, sin evidencia de contracción generalizada."
        self.assertEqual(_aplicar_guardrails_deterministicos(original), original)

    def test_contexto_sistema_instruye_distinguir_hecho_de_inferencia(self):
        contexto = construir_contexto_sistema({"cooperativas": 200, "fecha_min": "2020-01-01",
                                                 "fecha_max": "2026-07-31", "registros_totales": 1000})
        self.assertIn("HECHO", contexto)
        self.assertIn("INFERENCIA", contexto)
        self.assertIn("Información insuficiente para determinarlo.", contexto)

    def test_respuesta_local_sin_match_no_inventa_y_remite_a_modulo(self):
        r = responder_local("cuál es el ROE proyectado para la cooperativa XYZ el próximo trimestre",
                             {"cooperativas": 200})
        self.assertIn("Información insuficiente para determinarlo", r)

    def test_respuesta_local_con_match_usa_solo_datos_provistos(self):
        r = responder_local("cuántas cooperativas hay", {"cooperativas": 207})
        self.assertIn("207", r)


if __name__ == "__main__":
    unittest.main()
