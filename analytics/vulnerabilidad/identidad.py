"""Identidad estable de la entidad: la SEPS añade el sufijo «EN LIQUIDACION» al nombre cuando la cooperativa entra en
liquidación. Sin vincularlas, la misma entidad aparece como una salida y una entrada falsas. El vínculo es sólo textual y
determinista (sufijo exacto + fechas contiguas sin solape); el nombre original se conserva en `cooperativa_fuente`."""
import re
SUFIJO = re.compile(r"\s+EN LIQUIDACI[OÓ]N\s*$", re.IGNORECASE)

def entidad_id(nombre: str) -> str:
    return SUFIJO.sub("", str(nombre)).strip()

def en_liquidacion_por_nombre(nombre: str) -> bool:
    return bool(SUFIJO.search(str(nombre)))
