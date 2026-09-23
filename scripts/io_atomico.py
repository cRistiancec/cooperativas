# -*- coding: utf-8 -*-
"""
Escritura atómica de Parquet — hardening 14-sep-2026 (P1, integridad de
actualización).

Problema: `df.to_parquet(destino, ...)` escribe directamente sobre el
archivo productivo. Si el proceso muere a mitad de la escritura (falta de
memoria, timeout del runner, corte de red en un job de CI), el resultado es
un Parquet TRUNCADO o corrupto reemplazando silenciosamente al archivo
anterior, que sí era válido. `master_data/*.parquet` es exactamente el tipo
de archivo — grande, escrito por procesos de larga duración — donde esto
puede ocurrir.

Patrón aplicado: escribir a un archivo temporal en el MISMO directorio
(mismo filesystem, requisito para que el rename sea atómico) y solo
reemplazar el archivo productivo con `os.replace()` una vez que la
escritura terminó completamente sin excepciones. `os.replace()` en Linux es
atómico a nivel de sistema de archivos (rename(2)): en cualquier instante,
un lector ve o el archivo viejo completo, o el archivo nuevo completo —
nunca un estado intermedio. Si `to_parquet()` falla, el archivo temporal
queda huérfano (se limpia en el `finally`) y el archivo productivo original
permanece intacto y sin tocar.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pandas as pd


def guardar_parquet_atomico(df: pd.DataFrame, destino: Path, **kwargs: Any) -> None:
    """
    Reemplazo directo de `df.to_parquet(destino, **kwargs)` con escritura
    atómica: escribe a `destino.tmp_atomico`, y solo si termina sin errores,
    reemplaza `destino`. Si algo fallara entre medio, `destino` (si ya
    existía) permanece exactamente como estaba antes de la llamada.
    """
    destino = Path(destino)
    temporal = destino.with_name(f".{destino.name}.tmp_atomico")
    try:
        df.to_parquet(temporal, **kwargs)
        os.replace(temporal, destino)  # atómico en el mismo filesystem (POSIX rename)
    except Exception:
        temporal.unlink(missing_ok=True)
        raise
