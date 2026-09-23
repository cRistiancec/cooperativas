# -*- coding: utf-8 -*-
"""
Forecast (ARIMA) de series temporales del sistema.

Se usa `statsmodels` (ARIMA clásico) en vez de Prophet/LSTM para mantener el
footprint de memoria bajo, consistente con las optimizaciones ya aplicadas
al proyecto para operar dentro del límite de RAM de Streamlit Cloud (~1GB,
ver `README.md`). El orden (p,d,q) se selecciona con una búsqueda acotada por
AIC sobre un conjunto pequeño de combinaciones razonables para series
mensuales de negocio (sin estacionalidad SARIMA para no sobre-ajustar con
~100 observaciones).
"""

from __future__ import annotations

import warnings
from typing import Dict, Tuple

import numpy as np
import pandas as pd

from utils.logging_config import get_logger

logger = get_logger(__name__)

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", module="statsmodels")
warnings.filterwarnings("ignore", category=UserWarning, module="statsmodels")
try:
    from statsmodels.tools.sm_exceptions import ConvergenceWarning, ValueWarning
    warnings.filterwarnings("ignore", category=ConvergenceWarning)
    warnings.filterwarnings("ignore", category=ValueWarning)
except ImportError:
    pass

_ORDENES_CANDIDATOS = [(1, 1, 1), (2, 1, 1), (1, 1, 0), (0, 1, 1), (2, 1, 2)]


def _mejor_orden_arima(serie: pd.Series) -> Tuple[int, int, int]:
    """Selecciona el orden ARIMA con menor AIC entre un conjunto acotado de candidatos."""
    from statsmodels.tsa.arima.model import ARIMA

    mejor_aic = np.inf
    mejor_orden = (1, 1, 1)
    for orden in _ORDENES_CANDIDATOS:
        try:
            modelo = ARIMA(serie, order=orden).fit()
            if modelo.aic < mejor_aic:
                mejor_aic = modelo.aic
                mejor_orden = orden
        except Exception as e:
            # Es normal que algunos órdenes candidatos no converjan para
            # ciertas series; se registra a nivel debug y se prueba el
            # siguiente candidato, sin interrumpir la selección.
            logger.debug("Orden ARIMA %s no convergió: %s", orden, e)
            continue
    return mejor_orden


def forecast_serie(serie: pd.Series, pasos: int = 6) -> Dict:
    """
    Entrena un ARIMA sobre `serie` (indexada por fecha, valores numéricos) y
    proyecta `pasos` periodos hacia adelante con intervalo de confianza 95%.

    Returns:
        dict con: orden ARIMA usado, fechas futuras, valores proyectados,
        límites inferior/superior del IC 95%, y el AIC del modelo ajustado.
    """
    from statsmodels.tsa.arima.model import ARIMA

    serie = serie.dropna()
    if len(serie) < 24:
        raise ValueError("Se requieren al menos 24 observaciones para un forecast confiable.")

    orden = _mejor_orden_arima(serie)
    modelo = ARIMA(serie, order=orden).fit()
    logger.info("ARIMA entrenado: orden=%s, aic=%.1f, n_obs=%d, pasos=%d", orden, modelo.aic, len(serie), pasos)

    pronostico = modelo.get_forecast(steps=pasos)
    valores = pronostico.predicted_mean
    intervalo = pronostico.conf_int(alpha=0.05)

    ultima_fecha = serie.index[-1]
    fechas_futuras = pd.date_range(start=ultima_fecha, periods=pasos + 1, freq="ME")[1:]

    return {
        "orden": orden,
        "aic": float(modelo.aic),
        "fechas_futuras": fechas_futuras,
        "valores": valores.values,
        "limite_inferior": intervalo.iloc[:, 0].values,
        "limite_superior": intervalo.iloc[:, 1].values,
    }


def evaluar_backtest(serie: pd.Series, pasos_holdout: int = 6) -> Dict:
    """
    Backtest simple: entrena con todo excepto los últimos `pasos_holdout`
    periodos, proyecta esos periodos, y compara contra el valor real
    (MAPE — error porcentual absoluto medio). Da una medida honesta de
    desempeño en vez de solo mostrar el forecast sin validar.
    """
    serie = serie.dropna()
    if len(serie) < 24 + pasos_holdout:
        raise ValueError("Serie insuficiente para backtest.")

    serie_train = serie.iloc[:-pasos_holdout]
    serie_test = serie.iloc[-pasos_holdout:]

    resultado = forecast_serie(serie_train, pasos=pasos_holdout)
    valores_pred = resultado["valores"]
    valores_reales = serie_test.values

    errores_pct = np.abs((valores_reales - valores_pred) / valores_reales) * 100
    mape = float(np.mean(errores_pct))
    logger.info("Backtest ARIMA: mape=%.2f%%, holdout=%d meses", mape, pasos_holdout)

    return {
        "mape": mape,
        "fechas_test": serie_test.index,
        "valores_reales": valores_reales,
        "valores_predichos": valores_pred,
        "orden": resultado["orden"],
    }
