# -*- coding: utf-8 -*-
"""
Tests unitarios de la capa `analytics/` con datos sintéticos (no dependen de
`master_data/`, por velocidad e independencia del entorno).
"""

import unittest

import pandas as pd

from analytics.alertas import evaluar_alertas
from analytics.camels_score import calcular_score_camel, clasificar_score
from analytics.concentracion import (
    calcular_cr,
    calcular_hhi,
    clasificar_hhi,
    coeficiente_gini,
    curva_lorenz,
)
from analytics.crecimiento import (
    bandas_percentil,
    calcular_cartera_en_riesgo,
    variacion_anual_cartera_en_riesgo,
)
from analytics.indices_ejecutivos import (
    calcular_indice_estabilidad,
    calcular_indice_fortaleza,
    calcular_indice_resiliencia,
    calcular_indice_riesgo_integral,
    calcular_indice_vulnerabilidad,
    calcular_score_financiero_integral,
    clasificar_riesgo_integral,
)
from analytics.rentabilidad import (
    calcular_margen_financiero,
    calcular_roe_ajustado,
    calcular_tasas_implicitas,
)
from analytics.stress_testing import ESCENARIOS, aplicar_escenario


class ConcentracionTests(unittest.TestCase):
    def test_hhi_monopolio_es_10000(self):
        valores = pd.Series([100.0])
        self.assertAlmostEqual(calcular_hhi(valores), 10000.0)
        self.assertEqual(clasificar_hhi(10000.0), "Alta concentración")

    def test_hhi_reparto_equitativo(self):
        valores = pd.Series([25.0, 25.0, 25.0, 25.0])
        # 4 participantes iguales: HHI = 4 * 25^2 = 2500
        self.assertAlmostEqual(calcular_hhi(valores), 2500.0)

    def test_cr_top_n(self):
        valores = pd.Series([50.0, 30.0, 10.0, 5.0, 5.0])
        self.assertAlmostEqual(calcular_cr(valores, 2), 80.0)
        self.assertAlmostEqual(calcular_cr(valores, 5), 100.0)

    def test_gini_igualdad_perfecta_es_cero(self):
        valores = pd.Series([10.0, 10.0, 10.0, 10.0])
        self.assertAlmostEqual(coeficiente_gini(valores), 0.0, places=6)

    def test_gini_maxima_concentracion_tiende_a_uno(self):
        valores = pd.Series([0.0, 0.0, 0.0, 100.0])
        self.assertGreater(coeficiente_gini(valores), 0.7)

    def test_curva_lorenz_incluye_origen(self):
        valores = pd.Series([10.0, 20.0, 30.0])
        curva = curva_lorenz(valores)
        self.assertEqual(curva.iloc[0]["pct_instituciones"], 0)
        self.assertEqual(curva.iloc[0]["pct_valor_acumulado"], 0)
        self.assertAlmostEqual(curva.iloc[-1]["pct_valor_acumulado"], 1.0)


class CamelsScoreTests(unittest.TestCase):
    def _df_indicadores_sinteticos(self):
        """
        Universo de 10 cooperativas con calidad decreciente (BUENA la mejor,
        MALA la peor, y 8 intermedias), para que los percentiles tengan
        resolución suficiente y las clasificaciones extremas sean válidas
        (con solo 2 instituciones, rank(pct=True) no puede producir un
        percentil cercano a 0 ni a 100 para ninguna de las dos).
        """
        fecha = pd.Timestamp("2026-06-30")
        filas = []
        nombres = ["BUENA"] + [f"MEDIA_{i}" for i in range(8)] + ["MALA"]
        n = len(nombres)
        for i, coop in enumerate(nombres):
            # i=0 (BUENA) -> mejor calidad; i=n-1 (MALA) -> peor calidad.
            factor = i / (n - 1)  # 0 = mejor, 1 = peor
            indicadores = {
                "SUF_PAT": 5.0 - 4.5 * factor,
                "ACT_PROD": 0.95 - 0.35 * factor,
                "AP_PC": 1.1 - 0.3 * factor,
                "ACT_IMPR": 0.05 + 0.35 * factor,
                "MOR_TOT": 0.02 + 0.18 * factor,
                "COB_TOT": 2.0 - 1.7 * factor,
                "GO_ACT": 0.02 + 0.08 * factor,
                "GO_MNF": 0.5 + 1.0 * factor,
                "GP_ACT": 0.01 + 0.07 * factor,
                "ROE": 0.15 - 0.25 * factor,
                "ROA": 0.02 - 0.04 * factor,
                "LIQ": 0.4 - 0.35 * factor,
            }
            for codigo, valor in indicadores.items():
                filas.append({
                    "cooperativa": coop, "segmento": "SEGMENTO 1", "fecha": fecha,
                    "codigo": codigo, "valor": valor,
                })
        return pd.DataFrame(filas)

    def test_cooperativa_con_mejores_indicadores_tiene_mayor_score(self):
        df = self._df_indicadores_sinteticos()
        score = calcular_score_camel(df, pd.Timestamp("2026-06-30"))
        buena = score[score["cooperativa"] == "BUENA"].iloc[0]
        mala = score[score["cooperativa"] == "MALA"].iloc[0]
        self.assertGreater(buena["score_total"], mala["score_total"])
        self.assertEqual(clasificar_score(buena["score_total"]), "Sólido")
        self.assertEqual(clasificar_score(mala["score_total"]), "Crítico")

    def test_score_vacio_si_no_hay_datos_en_la_fecha(self):
        df = self._df_indicadores_sinteticos()
        score = calcular_score_camel(df, pd.Timestamp("2020-01-31"))
        self.assertTrue(score.empty)


class AlertasTests(unittest.TestCase):
    def test_evalua_severidad_correcta_por_regla(self):
        fecha = pd.Timestamp("2026-06-30")
        df = pd.DataFrame([
            {"cooperativa": "SANA", "segmento": "SEGMENTO 1", "fecha": fecha, "codigo": "MOR_TOT", "valor": 0.03},
            {"cooperativa": "SANA", "segmento": "SEGMENTO 1", "fecha": fecha, "codigo": "ROE", "valor": 0.05},
            {"cooperativa": "CRITICA", "segmento": "SEGMENTO 1", "fecha": fecha, "codigo": "MOR_TOT", "valor": 0.20},
            {"cooperativa": "CRITICA", "segmento": "SEGMENTO 1", "fecha": fecha, "codigo": "ROE", "valor": -0.05},
        ])
        alertas = evaluar_alertas(df, fecha)
        sana = alertas[alertas["cooperativa"] == "SANA"].iloc[0]
        critica = alertas[alertas["cooperativa"] == "CRITICA"].iloc[0]

        self.assertEqual(sana["semaforo"], "ok")
        self.assertEqual(critica["semaforo"], "crit")
        self.assertEqual(critica["sev_MOR_TOT"], 2)
        self.assertEqual(critica["sev_ROE"], 2)


class StressTestingTests(unittest.TestCase):
    def _panel_sintetico(self):
        return pd.DataFrame([{
            "cooperativa": "COOP X", "segmento": "SEGMENTO 1",
            "activos": 1_000_000.0, "cartera": 700_000.0, "depositos": 800_000.0,
            "patrimonio": 150_000.0, "fondos_disponibles": 100_000.0,
        }])

    def test_escenario_base_no_altera_el_balance(self):
        panel = self._panel_sintetico()
        resultado = aplicar_escenario(panel, "Base")
        fila = resultado.iloc[0]
        self.assertAlmostEqual(fila["patrimonio_post"], fila["patrimonio"])
        self.assertAlmostEqual(fila["activos_post"], fila["activos"])
        self.assertAlmostEqual(fila["solvencia_post"], fila["solvencia_pre"])

    def test_escenario_extremo_reduce_patrimonio_en_dolares(self):
        panel = self._panel_sintetico()
        resultado = aplicar_escenario(panel, "Extremo")
        fila = resultado.iloc[0]
        parametros = ESCENARIOS["Extremo"]

        perdida_esperada = 700_000.0 * (parametros["shock_mora_pp"] / 100) * parametros["tasa_perdida_incremental"]
        salida_esperada = 800_000.0 * (parametros["shock_depositos_pct"] / 100)

        self.assertAlmostEqual(fila["perdida_credito"], perdida_esperada)
        self.assertAlmostEqual(fila["salida_efectivo"], salida_esperada)
        self.assertAlmostEqual(fila["patrimonio_post"], 150_000.0 - perdida_esperada)
        self.assertAlmostEqual(fila["fondos_disponibles_post"], 100_000.0 - salida_esperada)
        # El patrimonio en dólares SIEMPRE cae con la pérdida crediticia.
        self.assertLess(fila["patrimonio_post"], fila["patrimonio"])

    def test_shock_solo_credito_sin_salida_depositos_reduce_la_razon_de_solvencia(self):
        """
        Aísla el efecto crediticio puro (sin shock de depósitos) para verificar
        que, en ausencia de contracción del balance, la razón de solvencia sí
        se comporta de forma monótona: cae con la pérdida crediticia.
        """
        panel = self._panel_sintetico()
        parametros_solo_credito = {
            "shock_depositos_pct": 0.0, "shock_mora_pp": 10.0, "tasa_perdida_incremental": 0.60,
        }
        resultado = aplicar_escenario(panel, parametros_solo_credito)
        fila = resultado.iloc[0]
        self.assertLess(fila["solvencia_post"], fila["solvencia_pre"])

    def test_shock_grande_de_depositos_puede_mejorar_la_razon_pese_a_la_perdida(self):
        """
        Documenta la propiedad conocida (no un bug): cuando la salida de
        depósitos es grande frente a la pérdida crediticia, la razón
        Patrimonio/Activos puede subir levemente porque el denominador se
        contrae más rápido que el numerador. Ver docstring de
        `aplicar_escenario` para la explicación completa.
        """
        panel = self._panel_sintetico()
        resultado = aplicar_escenario(panel, "Extremo")
        fila = resultado.iloc[0]
        self.assertGreaterEqual(fila["solvencia_post"], fila["solvencia_pre"])
        # Pero el patrimonio absoluto sí cayó — la mejora es puramente de razón.
        self.assertLess(fila["patrimonio_post"], fila["patrimonio"])

    def test_shock_depositos_grande_genera_brecha_de_liquidez(self):
        panel = self._panel_sintetico()
        resultado = aplicar_escenario(panel, "Extremo")
        fila = resultado.iloc[0]
        # 30% de 800,000 = 240,000 > 100,000 de fondos disponibles -> brecha
        self.assertTrue(fila["brecha_liquidez"])


class RentabilidadTests(unittest.TestCase):
    """
    Migración de la sección "INDICADORES DE RENTABILIDAD" del script R de
    referencia (`AUDITORIA_MOTOR_INDICADORES.md`, Categoría 3).
    """

    FECHA = pd.Timestamp("2026-06-30")

    def _df_ranking_3_meses(self, valores_por_mes: dict, codigo: str) -> pd.DataFrame:
        """3 cortes mensuales de una sola cuenta de balance, para 1 cooperativa."""
        filas = []
        for fecha, valor in valores_por_mes.items():
            filas.append({
                "fecha": fecha, "segmento": "SEGMENTO 1", "cooperativa": "COOP X",
                "codigo": codigo, "valor": valor,
            })
        return pd.DataFrame(filas)

    def test_tasas_implicitas_signo_y_magnitud(self):
        # Depósitos promedio 3m = 900k; intereses causados 12m = 90k -> pasiva = 10%
        df_ranking = pd.concat([
            self._df_ranking_3_meses({
                pd.Timestamp("2026-04-30"): 880_000.0,
                pd.Timestamp("2026-05-31"): 900_000.0,
                pd.Timestamp("2026-06-30"): 920_000.0,
            }, codigo="21"),
            self._df_ranking_3_meses({
                pd.Timestamp("2026-04-30"): 480_000.0,
                pd.Timestamp("2026-05-31"): 500_000.0,
                pd.Timestamp("2026-06-30"): 520_000.0,
            }, codigo="14"),
        ], ignore_index=True)
        df_pyg = pd.DataFrame([
            {"fecha": self.FECHA, "segmento": "SEGMENTO 1", "cooperativa": "COOP X",
             "codigo": "4101", "valor_12m": 90_000.0},
            {"fecha": self.FECHA, "segmento": "SEGMENTO 1", "cooperativa": "COOP X",
             "codigo": "5104", "valor_12m": 100_000.0},
        ])
        resultado = calcular_tasas_implicitas(df_ranking, df_pyg, self.FECHA).iloc[0]
        self.assertAlmostEqual(resultado["tasa_pasiva_implicita"], 90_000 / 900_000 * 100, places=4)
        self.assertAlmostEqual(resultado["tasa_activa_implicita"], 100_000 / 500_000 * 100, places=4)
        self.assertAlmostEqual(resultado["spread_financiero"],
                                resultado["tasa_activa_implicita"] - resultado["tasa_pasiva_implicita"])
        # Una cooperativa sana presta más caro de lo que capta.
        self.assertGreater(resultado["spread_financiero"], 0)

    def test_margen_financiero_es_ingresos_menos_gastos(self):
        codigos_ingreso = ["51", "52", "53", "54"]
        codigos_gasto = ["41", "42", "43", "44"]
        filas = [
            {"fecha": self.FECHA, "segmento": "SEGMENTO 1", "cooperativa": "COOP X",
             "codigo": c, "valor_12m": 10_000.0} for c in codigos_ingreso
        ] + [
            {"fecha": self.FECHA, "segmento": "SEGMENTO 1", "cooperativa": "COOP X",
             "codigo": c, "valor_12m": 3_000.0} for c in codigos_gasto
        ]
        df_pyg = pd.DataFrame(filas)
        resultado = calcular_margen_financiero(df_pyg, self.FECHA)
        # 4*10,000 - 4*3,000 = 28,000
        self.assertAlmostEqual(resultado.iloc[0]["margen_financiero"], 28_000.0)

    def test_roe_ajustado_excluye_otros_ingresos_del_numerador(self):
        df_ranking = self._df_ranking_3_meses({
            pd.Timestamp("2026-04-30"): 100_000.0,
            pd.Timestamp("2026-05-31"): 100_000.0,
            pd.Timestamp("2026-06-30"): 100_000.0,
        }, codigo="3")
        df_pyg = pd.DataFrame([
            {"fecha": self.FECHA, "segmento": "SEGMENTO 1", "cooperativa": "COOP X",
             "codigo": "5", "valor_12m": 50_000.0},
            {"fecha": self.FECHA, "segmento": "SEGMENTO 1", "cooperativa": "COOP X",
             "codigo": "4", "valor_12m": 40_000.0},
            {"fecha": self.FECHA, "segmento": "SEGMENTO 1", "cooperativa": "COOP X",
             "codigo": "56", "valor_12m": 5_000.0},
        ])
        resultado = calcular_roe_ajustado(df_ranking, df_pyg, self.FECHA).iloc[0]
        # (50,000 - 40,000 - 5,000) / 100,000 = 5%, no 10% (que sería sin ajustar)
        self.assertAlmostEqual(resultado["roe_ajustado"], 5.0)

    def test_promedio_movil_solo_usa_los_ultimos_3_cortes(self):
        """Un corte muy antiguo fuera de la ventana de 3 meses no debe influir."""
        df_ranking = self._df_ranking_3_meses({
            pd.Timestamp("2018-01-31"): 10.0,  # fuera de ventana: distorsionaría el promedio
            pd.Timestamp("2026-04-30"): 100_000.0,
            pd.Timestamp("2026-05-31"): 100_000.0,
            pd.Timestamp("2026-06-30"): 100_000.0,
        }, codigo="3")
        df_pyg = pd.DataFrame([
            {"fecha": self.FECHA, "segmento": "SEGMENTO 1", "cooperativa": "COOP X",
             "codigo": "5", "valor_12m": 10_000.0},
            {"fecha": self.FECHA, "segmento": "SEGMENTO 1", "cooperativa": "COOP X",
             "codigo": "4", "valor_12m": 0.0},
            {"fecha": self.FECHA, "segmento": "SEGMENTO 1", "cooperativa": "COOP X",
             "codigo": "56", "valor_12m": 0.0},
        ])
        resultado = calcular_roe_ajustado(df_ranking, df_pyg, self.FECHA).iloc[0]
        self.assertAlmostEqual(resultado["roe_ajustado"], 10_000 / 100_000 * 100)


class CrecimientoTests(unittest.TestCase):
    """Migración de "TASAS DE CRECIMIENTO" y `CER` del script R de referencia."""

    def test_cartera_en_riesgo_suma_las_cuentas_de_su_cooperativa_y_fecha(self):
        fecha = pd.Timestamp("2026-06-30")
        df_balance = pd.DataFrame([
            {"fecha": fecha, "segmento": "SEGMENTO 1", "cooperativa": "COOP X", "codigo": "1425", "valor": 1_000.0},
            {"fecha": fecha, "segmento": "SEGMENTO 1", "cooperativa": "COOP X", "codigo": "1426", "valor": 2_000.0},
            # Otra cooperativa y otra fecha no deben mezclarse en el resultado.
            {"fecha": fecha, "segmento": "SEGMENTO 1", "cooperativa": "COOP Y", "codigo": "1425", "valor": 999.0},
            {"fecha": pd.Timestamp("2025-06-30"), "segmento": "SEGMENTO 1", "cooperativa": "COOP X",
             "codigo": "1425", "valor": 500.0},
        ])
        resultado = calcular_cartera_en_riesgo(df_balance, fecha)
        fila_x = resultado[resultado["cooperativa"] == "COOP X"].iloc[0]
        self.assertAlmostEqual(fila_x["cartera_en_riesgo"], 3_000.0)

    def test_variacion_anual_cartera_en_riesgo(self):
        actual, anterior = pd.Timestamp("2026-06-30"), pd.Timestamp("2025-06-30")
        df_balance = pd.DataFrame([
            {"fecha": actual, "segmento": "SEGMENTO 1", "cooperativa": "COOP X", "codigo": "1425", "valor": 5_000.0},
            {"fecha": anterior, "segmento": "SEGMENTO 1", "cooperativa": "COOP X", "codigo": "1425", "valor": 3_000.0},
        ])
        resultado = variacion_anual_cartera_en_riesgo(df_balance, actual, anterior).iloc[0]
        self.assertAlmostEqual(resultado["variacion_cartera_en_riesgo"], 2_000.0)

    def test_bandas_percentil_orden_y_limites(self):
        valores = pd.Series(range(1, 101))  # 1..100
        p10, p90 = bandas_percentil(valores, 10, 90)
        self.assertLess(p10, p90)
        self.assertAlmostEqual(p10, 10.9, places=1)
        self.assertAlmostEqual(p90, 90.1, places=1)

    def test_bandas_percentil_con_serie_vacia_devuelve_nan(self):
        p10, p90 = bandas_percentil(pd.Series([], dtype=float))
        self.assertTrue(pd.isna(p10))
        self.assertTrue(pd.isna(p90))


class IndicesEjecutivosTests(unittest.TestCase):
    """
    Índices de segundo nivel (Fase 2.4). No migran nada del script R —son
    indicadores nuevos— así que las pruebas verifican la propiedad que cada
    metodología promete (mejor insumo ⇒ mejor índice), no un valor exacto
    tomado de una fuente externa.
    """

    FECHA = pd.Timestamp("2026-06-30")

    def _df_indicadores(self, valores_por_coop: dict) -> pd.DataFrame:
        filas = []
        for coop, indicadores in valores_por_coop.items():
            for codigo, valor in indicadores.items():
                filas.append({
                    "cooperativa": coop, "segmento": "SEGMENTO 1", "fecha": self.FECHA,
                    "codigo": codigo, "valor": valor,
                })
        return pd.DataFrame(filas)

    def test_score_financiero_integral_favorece_mejores_fundamentales(self):
        df_ind = self._df_indicadores({
            "BUENA": {"LIQ": 0.30, "SUF_PAT": 3.0, "ROE": 0.15, "COB_TOT": 1.8, "MOR_TOT": 0.02},
            "MALA": {"LIQ": 0.08, "SUF_PAT": 0.8, "ROE": -0.10, "COB_TOT": 0.3, "MOR_TOT": 0.20},
        })
        df_crecimiento = pd.DataFrame([
            {"cooperativa": "BUENA", "crecimiento_pct": 12.0},
            {"cooperativa": "MALA", "crecimiento_pct": -5.0},
        ])
        resultado = calcular_score_financiero_integral(df_ind, df_crecimiento, self.FECHA)
        buena = resultado[resultado["cooperativa"] == "BUENA"].iloc[0]["score_financiero_integral"]
        mala = resultado[resultado["cooperativa"] == "MALA"].iloc[0]["score_financiero_integral"]
        self.assertGreater(buena, mala)

    def test_indice_vulnerabilidad_penaliza_morosidad_y_vulnerabilidad_patrimonial_altas(self):
        df_ind = self._df_indicadores({
            "SANA": {"MOR_TOT": 0.02, "VULN_PAT": 0.05, "CART_IMPR_PAT": 0.10},
            "FRAGIL": {"MOR_TOT": 0.22, "VULN_PAT": 0.60, "CART_IMPR_PAT": 0.90},
        })
        resultado = calcular_indice_vulnerabilidad(
            df_ind, df_pyg=pd.DataFrame(), df_ranking=pd.DataFrame(), fecha=self.FECHA
        )
        sana = resultado[resultado["cooperativa"] == "SANA"].iloc[0]["indice_vulnerabilidad"]
        fragil = resultado[resultado["cooperativa"] == "FRAGIL"].iloc[0]["indice_vulnerabilidad"]
        self.assertGreater(fragil, sana, "La cooperativa con peores señales debe ser más vulnerable, no menos.")

    def test_indice_fortaleza_favorece_mas_capital_liquidez_y_rentabilidad(self):
        df_ind = self._df_indicadores({
            "FUERTE": {"SUF_PAT": 4.0, "LIQ": 0.35, "COB_TOT": 2.0, "ROA": 0.03, "ROE": 0.18},
            "DEBIL": {"SUF_PAT": 0.5, "LIQ": 0.06, "COB_TOT": 0.2, "ROA": -0.02, "ROE": -0.15},
        })
        df_crecimiento = pd.DataFrame([
            {"cooperativa": "FUERTE", "crecimiento_pct": 8.0},
            {"cooperativa": "DEBIL", "crecimiento_pct": -10.0},
        ])
        resultado = calcular_indice_fortaleza(df_ind, df_crecimiento, self.FECHA)
        fuerte = resultado[resultado["cooperativa"] == "FUERTE"].iloc[0]["indice_fortaleza"]
        debil = resultado[resultado["cooperativa"] == "DEBIL"].iloc[0]["indice_fortaleza"]
        self.assertGreater(fuerte, debil)

    def test_indice_resiliencia_penaliza_poco_colchon_de_patrimonio(self):
        df_ranking = pd.DataFrame([
            # Mismo tamaño de cartera/depósitos; COLCHONADA tiene mucho más patrimonio relativo.
            {"fecha": self.FECHA, "segmento": "SEGMENTO 1", "cooperativa": "COLCHONADA",
             "codigo": "1", "valor": 1_000_000.0},
            {"fecha": self.FECHA, "segmento": "SEGMENTO 1", "cooperativa": "COLCHONADA",
             "codigo": "14", "valor": 700_000.0},
            {"fecha": self.FECHA, "segmento": "SEGMENTO 1", "cooperativa": "COLCHONADA",
             "codigo": "21", "valor": 800_000.0},
            {"fecha": self.FECHA, "segmento": "SEGMENTO 1", "cooperativa": "COLCHONADA",
             "codigo": "3", "valor": 300_000.0},
            {"fecha": self.FECHA, "segmento": "SEGMENTO 1", "cooperativa": "COLCHONADA",
             "codigo": "11", "valor": 150_000.0},
            {"fecha": self.FECHA, "segmento": "SEGMENTO 1", "cooperativa": "AJUSTADA",
             "codigo": "1", "valor": 1_000_000.0},
            {"fecha": self.FECHA, "segmento": "SEGMENTO 1", "cooperativa": "AJUSTADA",
             "codigo": "14", "valor": 700_000.0},
            {"fecha": self.FECHA, "segmento": "SEGMENTO 1", "cooperativa": "AJUSTADA",
             "codigo": "21", "valor": 800_000.0},
            {"fecha": self.FECHA, "segmento": "SEGMENTO 1", "cooperativa": "AJUSTADA",
             "codigo": "3", "valor": 30_000.0},
            {"fecha": self.FECHA, "segmento": "SEGMENTO 1", "cooperativa": "AJUSTADA",
             "codigo": "11", "valor": 40_000.0},
        ])
        resultado = calcular_indice_resiliencia(df_ranking, self.FECHA, "Todos", escenario="Extremo")
        colchonada = resultado[resultado["cooperativa"] == "COLCHONADA"].iloc[0]
        ajustada = resultado[resultado["cooperativa"] == "AJUSTADA"].iloc[0]
        self.assertGreater(colchonada["indice_resiliencia"], ajustada["indice_resiliencia"])
        self.assertTrue(ajustada["capital_insuficiente"])
        self.assertFalse(colchonada["capital_insuficiente"])

    def test_indice_estabilidad_penaliza_la_volatilidad_al_mismo_nivel_promedio(self):
        fechas = pd.date_range("2025-07-31", periods=12, freq="ME")
        filas = []
        for i, fecha in enumerate(fechas):
            es_ultima = (i == len(fechas) - 1)
            # ESTABLE: morosidad constante en 5%. VOLATIL: mismo valor que ESTABLE
            # en la fecha de corte (para que el componente "nivel" quede empatado
            # entre ambas) pero oscilando 1%-9% en los 11 meses previos (para que
            # solo el componente "consistencia" las diferencie).
            filas.append({"cooperativa": "ESTABLE", "segmento": "SEGMENTO 1", "fecha": fecha,
                          "codigo": "MOR_TOT", "valor": 0.05})
            valor_volatil = 0.05 if es_ultima else (0.01 if i % 2 == 0 else 0.09)
            filas.append({"cooperativa": "VOLATIL", "segmento": "SEGMENTO 1", "fecha": fecha,
                          "codigo": "MOR_TOT", "valor": valor_volatil})
            for coop in ("ESTABLE", "VOLATIL"):
                filas.append({"cooperativa": coop, "segmento": "SEGMENTO 1", "fecha": fecha,
                              "codigo": "LIQ", "valor": 0.20})
                filas.append({"cooperativa": coop, "segmento": "SEGMENTO 1", "fecha": fecha,
                              "codigo": "ROE", "valor": 0.05})
        df_ind = pd.DataFrame(filas)
        resultado = calcular_indice_estabilidad(df_ind, fechas[-1], "Todos")
        estable = resultado[resultado["cooperativa"] == "ESTABLE"].iloc[0]
        volatil = resultado[resultado["cooperativa"] == "VOLATIL"].iloc[0]
        self.assertAlmostEqual(estable["nivel"], volatil["nivel"], msg="El nivel debía quedar empatado por diseño.")
        self.assertGreater(estable["consistencia"], volatil["consistencia"])
        self.assertGreater(estable["indice_estabilidad"], volatil["indice_estabilidad"])

    def test_indice_riesgo_integral_combina_los_tres_componentes_con_sus_pesos(self):
        df_score = pd.DataFrame([
            {"cooperativa": "A", "segmento": "SEGMENTO 1", "score_financiero_integral": 80.0},
            {"cooperativa": "B", "segmento": "SEGMENTO 1", "score_financiero_integral": 80.0},
        ])
        df_vuln = pd.DataFrame([
            {"cooperativa": "A", "indice_vulnerabilidad": 10.0},   # poco vulnerable
            {"cooperativa": "B", "indice_vulnerabilidad": 90.0},   # muy vulnerable
        ])
        df_alertas = pd.DataFrame([
            {"cooperativa": "A", "total_alertas_activas": 0},
            {"cooperativa": "B", "total_alertas_activas": 5},
        ])
        resultado = calcular_indice_riesgo_integral(df_score, df_vuln, df_alertas)
        a = resultado[resultado["cooperativa"] == "A"].iloc[0]["riesgo_integral"]
        b = resultado[resultado["cooperativa"] == "B"].iloc[0]["riesgo_integral"]
        # Mismo score financiero, pero B es más vulnerable y tiene más alertas -> A debe rankear mejor.
        self.assertGreater(a, b)

    def test_clasificar_riesgo_integral_bandas_y_limites(self):
        self.assertEqual(clasificar_riesgo_integral(90), "Excelente")
        self.assertEqual(clasificar_riesgo_integral(85), "Excelente")
        self.assertEqual(clasificar_riesgo_integral(84.9), "Muy Bueno")
        self.assertEqual(clasificar_riesgo_integral(55), "Bueno")
        self.assertEqual(clasificar_riesgo_integral(40), "Vigilancia")
        self.assertEqual(clasificar_riesgo_integral(25), "Riesgo Medio")
        self.assertEqual(clasificar_riesgo_integral(10), "Riesgo Alto")
        self.assertEqual(clasificar_riesgo_integral(0), "Riesgo Crítico")
        self.assertEqual(clasificar_riesgo_integral(float("nan")), "Sin datos")


class CatalogoIndicadoresTests(unittest.TestCase):
    """
    Fase 2.6 — documentación automática. No verifica el contenido en prosa
    (eso lo audita un humano leyendo `CATALOGO_INDICADORES.md`), sino la
    integridad estructural del registro que lo alimenta: sin códigos
    duplicados y sin campos vacíos, que es justo lo que rompería la
    documentación generada en silencio.
    """

    def test_sin_codigos_duplicados(self):
        from analytics.catalogo_indicadores import CATALOGO_NUEVOS_INDICADORES
        codigos = [e.codigo for e in CATALOGO_NUEVOS_INDICADORES]
        self.assertEqual(len(codigos), len(set(codigos)), f"Códigos duplicados: {codigos}")

    def test_ningun_campo_requerido_esta_vacio(self):
        from analytics.catalogo_indicadores import CATALOGO_NUEVOS_INDICADORES
        campos = ["codigo", "nombre", "descripcion", "formula", "variables",
                  "interpretacion", "rango_esperado", "modulo", "dependencias",
                  "frecuencia_actualizacion", "fuente"]
        for entrada in CATALOGO_NUEVOS_INDICADORES:
            for campo in campos:
                with self.subTest(codigo=entrada.codigo, campo=campo):
                    self.assertTrue(getattr(entrada, campo).strip(), f"{entrada.codigo}.{campo} está vacío")

    def test_el_modulo_referenciado_existe_de_verdad(self):
        """Cada entrada apunta a una función real del motor — no a un nombre que se movió o se borró."""
        import importlib
        from analytics.catalogo_indicadores import CATALOGO_NUEVOS_INDICADORES
        for entrada in CATALOGO_NUEVOS_INDICADORES:
            with self.subTest(codigo=entrada.codigo):
                modulo_path, funcion = entrada.modulo.rsplit(".", 1)
                modulo = importlib.import_module(modulo_path)
                self.assertTrue(
                    hasattr(modulo, funcion),
                    f"{entrada.modulo} no existe — {modulo_path} no tiene {funcion!r}",
                )


if __name__ == "__main__":
    unittest.main()
