# -*- coding: utf-8 -*-
"""
Genera `CATALOGO_INDICADORES.md`: documentación automática de todos los
indicadores financieros de la plataforma — los 41 oficiales de la SEPS
(pre-calculados, extraídos del pivot cache de cada boletín) y los ~15 nuevos
del Motor Central (Fase 2.3: migrados del script R de referencia; Fase 2.4:
índices ejecutivos de segundo nivel).

Es un **generador**, no un documento escrito a mano: lee directamente
`config/indicator_mapping.py` (para los oficiales) y
`analytics/catalogo_indicadores.py` (para los nuevos) y renderiza el
Markdown. Si un indicador se agrega, se quita, o cambia de rango/categoría
en esas fuentes, volver a ejecutar este script regenera la documentación
correcta — no hay prosa que pueda quedar desactualizada en silencio.

Uso:
    python scripts/generar_documentacion_indicadores.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.indicator_mapping import (  # noqa: E402
    ESCALAS_COLORES_HEATMAP,
    ETIQUETAS_INDICADORES,
    GRUPOS_INDICADORES,
    RANGOS_HEATMAP,
)
from analytics.catalogo_indicadores import CATALOGO_NUEVOS_INDICADORES  # noqa: E402

try:
    from procesar_camel import INDICADORES_MAP
except ModuleNotFoundError:
    from scripts.procesar_camel import INDICADORES_MAP

REPO_ROOT = Path(__file__).parent.parent
SALIDA = REPO_ROOT / "CATALOGO_INDICADORES.md"


def _categoria_de(codigo: str) -> str:
    for categoria, codigos in GRUPOS_INDICADORES.items():
        if codigo in codigos:
            return categoria
    return "Sin categoría"


def _campo_seps_de(codigo: str) -> str:
    """Nombre del campo original en el pivot cache de la SEPS (p. ej. 'I28_ROE')."""
    for campo, (cod, _nombre, _cat) in INDICADORES_MAP.items():
        if cod == codigo:
            return campo
    return "—"


def _renderizar_indicador_seps(codigo: str) -> str:
    nombre = ETIQUETAS_INDICADORES.get(codigo, codigo)
    categoria = _categoria_de(codigo)
    rango = RANGOS_HEATMAP.get(codigo)
    escala = ESCALAS_COLORES_HEATMAP.get(codigo, "—")
    campo_seps = _campo_seps_de(codigo)
    direccion = {
        "RdYlGn": "Mayor es mejor",
        "RdYlGn_r": "Menor es mejor",
        "Blues": "Informativo (sin dirección única en la metodología vigente)",
    }.get(escala, "—")

    return f"""### `{codigo}` — {nombre}

| Campo | Valor |
|---|---|
| **Nombre** | {nombre} |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `{campo_seps}`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `{campo_seps}` → código interno `{codigo}` |
| **Interpretación** | {direccion} (escala de color `{escala}` en los heatmaps) |
| **Rango esperado** | {f"{rango[0]} – {rango[1]}%" if rango else "No calibrado"} |
| **Categoría CAMEL** | {categoria} |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |
"""


def _renderizar_indicador_nuevo(entrada) -> str:
    return f"""### `{entrada.codigo}` — {entrada.nombre}

| Campo | Valor |
|---|---|
| **Nombre** | {entrada.nombre} |
| **Descripción** | {entrada.descripcion} |
| **Fórmula** | {entrada.formula} |
| **Variables** | {entrada.variables} |
| **Interpretación financiera** | {entrada.interpretacion} |
| **Rango esperado** | {entrada.rango_esperado} |
| **Módulo** | `{entrada.modulo}` |
| **Dependencias** | {entrada.dependencias} |
| **Frecuencia de actualización** | {entrada.frecuencia_actualizacion} |
| **Fuente** | {entrada.fuente} |
"""


def generar() -> None:
    codigos_seps = sorted(ETIQUETAS_INDICADORES.keys())
    nuevos = CATALOGO_NUEVOS_INDICADORES

    partes = [
        "# CATÁLOGO DE INDICADORES — Motor Central",
        "",
        "**Radar Cooperativo Ecuador — COSEDE**",
        "",
        f"Generado automáticamente por `scripts/generar_documentacion_indicadores.py` "
        f"a partir de `config/indicator_mapping.py` y `analytics/catalogo_indicadores.py`. "
        f"**No editar este archivo a mano** — los cambios se pierden en la siguiente "
        f"regeneración; edite las fuentes y vuelva a ejecutar el script.",
        "",
        f"- Indicadores oficiales SEPS (pre-calculados): **{len(codigos_seps)}**",
        f"- Indicadores nuevos del Motor Central (Fase 2.3 + 2.4): **{len(nuevos)}**",
        f"- **Total: {len(codigos_seps) + len(nuevos)}**",
        "",
        "---",
        "",
        "## Índice",
        "",
    ]

    partes.append("**Oficiales SEPS**, por categoría CAMEL:")
    for categoria, codigos in GRUPOS_INDICADORES.items():
        partes.append(f"- **{categoria}**: {len(codigos)} indicadores ({', '.join(codigos)})")
    partes.append("")
    partes.append("**Nuevos (Motor Central)**, por dominio:")
    dominios_nuevos = {}
    for e in nuevos:
        dominio = e.modulo.split(".")[1] if "." in e.modulo else e.modulo
        dominios_nuevos.setdefault(dominio, []).append(e.codigo)
    for dominio, codigos in dominios_nuevos.items():
        partes.append(f"- **{dominio}**: {len(codigos)} indicadores ({', '.join(codigos)})")

    partes.append("")
    partes.append("---")
    partes.append("")
    partes.append("## Indicadores oficiales SEPS (pre-calculados)")
    partes.append("")
    for codigo in codigos_seps:
        partes.append(_renderizar_indicador_seps(codigo))

    partes.append("---")
    partes.append("")
    partes.append("## Indicadores nuevos del Motor Central")
    partes.append("")
    for entrada in nuevos:
        partes.append(_renderizar_indicador_nuevo(entrada))

    partes.append("---")
    partes.append("")
    partes.append(
        "*Documento generado automáticamente. Para regenerarlo tras un cambio: "
        "`python scripts/generar_documentacion_indicadores.py`.*"
    )

    SALIDA.write_text("\n".join(partes), encoding="utf-8")
    print(f"[OK] {SALIDA.relative_to(REPO_ROOT)} generado: "
          f"{len(codigos_seps)} indicadores SEPS + {len(nuevos)} nuevos.")


if __name__ == "__main__":
    generar()
