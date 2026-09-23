# -*- coding: utf-8 -*-
"""
Configuración centralizada de logging del RADAR COOPERATIVO ECUADOR.

Tres archivos con propósitos distintos, todos con rotación (evita
crecimiento sin límite en el contenedor de despliegue):

    logs/app.log          — INFO y superior, actividad general de la app.
    logs/error.log         — ERROR y superior (subconjunto de app.log, aislado
                              para que un operador pueda revisar solo fallas).
    logs/performance.log   — duraciones de operaciones costosas (carga de
                              datos, entrenamiento de modelos, render de página).

Streamlit Cloud además captura stdout en sus logs de plataforma, por lo que
se mantiene un `StreamHandler` en paralelo a los archivos.

`logs/` puede no ser escribible en algunos entornos de despliegue efímeros;
toda la configuración de archivo está envuelta en try/except para que un
fallo de logging **nunca** tumbe la aplicación — en el peor caso, se
degrada silenciosamente a solo consola.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Iterator

_FORMATO = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
_LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"
_MAX_BYTES = 5 * 1024 * 1024  # 5 MB por archivo
_BACKUPS = 3

_configurado = False
_performance_logger: logging.Logger | None = None


def _crear_handler_archivo(nombre_archivo: str, nivel: int) -> RotatingFileHandler | None:
    """Crea un RotatingFileHandler; devuelve None si el directorio no es escribible."""
    try:
        _LOGS_DIR.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            _LOGS_DIR / nombre_archivo, maxBytes=_MAX_BYTES, backupCount=_BACKUPS, encoding="utf-8"
        )
        handler.setLevel(nivel)
        handler.setFormatter(logging.Formatter(_FORMATO))
        return handler
    except OSError:
        return None


def _configurar() -> None:
    global _configurado, _performance_logger
    if _configurado:
        return

    raiz = logging.getLogger()
    raiz.setLevel(logging.INFO)

    consola = logging.StreamHandler()
    consola.setLevel(logging.INFO)
    consola.setFormatter(logging.Formatter(_FORMATO))
    raiz.addHandler(consola)

    handler_app = _crear_handler_archivo("app.log", logging.INFO)
    if handler_app:
        raiz.addHandler(handler_app)

    handler_error = _crear_handler_archivo("error.log", logging.ERROR)
    if handler_error:
        raiz.addHandler(handler_error)

    logger_perf = logging.getLogger("performance")
    logger_perf.setLevel(logging.INFO)
    logger_perf.propagate = False  # no duplicar también en app.log
    handler_perf = _crear_handler_archivo("performance.log", logging.INFO)
    if handler_perf:
        logger_perf.addHandler(handler_perf)
    else:
        logger_perf.addHandler(consola)
    _performance_logger = logger_perf

    _configurado = True


def get_logger(nombre: str) -> logging.Logger:
    """Devuelve un logger con el formato institucional, configurado una sola vez por proceso."""
    _configurar()
    return logging.getLogger(nombre)


def get_performance_logger() -> logging.Logger:
    """Logger dedicado a `logs/performance.log` (no se mezcla con app.log)."""
    _configurar()
    assert _performance_logger is not None
    return _performance_logger


@contextmanager
def medir_rendimiento(operacion: str) -> Iterator[None]:
    """
    Context manager que registra en `logs/performance.log` la duración de un
    bloque de código. Uso:

        with medir_rendimiento("carga_balance_completo"):
            df, calidad = cargar_balance()
    """
    logger = get_performance_logger()
    inicio = time.perf_counter()
    try:
        yield
    finally:
        duracion_ms = (time.perf_counter() - inicio) * 1000
        logger.info("%s | %.1f ms", operacion, duracion_ms)
