# Segmentación histórica (point-in-time) en la ingesta

**Regla:** el segmento de una cooperativa en un corte es el que dice el archivo oficial de la SEPS **de ese corte**.
Nunca se infiere por tamaño, por nombre ni se proyecta el segmento vigente hacia atrás.

## Arquitectura
| Pieza | Rol |
|---|---|
| `master_data/dim_segmento_historico.parquet` | Fuente única de verdad: `cooperativa, fecha, segmento_historico, fuente` (1 fila por cooperativa-corte). |
| `master_data/dim_segmento_historico_cambios.json` | Bitácora de revisiones retrospectivas de la SEPS (segmento distinto al registrado antes, o filas retiradas). |
| `scripts/segmento_historico.py` | Normaliza, valida (ausente/desconocido/contradictorio ⇒ **falla**), hace upsert por mes, `--rehidratar`, `--verificar`, y `acoplar_segmento()` para cualquier dataset. |
| `procesar_balance_cooperativas.py` | Alimenta la dimensión en cada ingesta y acopla `segmento_historico` al balance. |
| `procesar_pyg.py`, `procesar_camel.py`, `generar_entidades.py` | Acoplan el segmento desde la **misma** dimensión (los tres datasets no pueden discrepar). |
| `generar_agregados.py` | Además de `agg_metricas_sistema` (segmento vigente), genera `agg_metricas_sistema_historico.parquet` por `segmento_historico`. **Para análisis sistémico por período usar este último.** |
| `validar_actualizacion.py` | Puerta CRÍTICA: dimensión existente, sin huecos ni duplicados, corte nuevo cubierto con segmento oficial (no estimado) en balance/PyG/CAMEL. |
| `utils/data_loader.cargar_segmento_historico()` | Lee la dimensión con prioridad sobre cualquier backfill. |

## Semántica de columnas
- `segmento` / `segmento_actual`: último segmento conocido (rankings "hoy"). **No usar para series históricas.**
- `segmento_historico`: segmento oficial del corte. `segmento_historico_estimado = True` solo donde la dimensión no cubre.

## Puesta en marcha (una sola vez)
1. Reunir todos los ZIP históricos en `balances_cooperativas/` (2018-… ; no se versionan).
2. `python scripts/segmento_historico.py --rehidratar balances_cooperativas/` (termina con `--verificar`).
3. Regenerar: `procesar_balance_cooperativas.py`, `generar_agregados.py`, `procesar_pyg.py`, `procesar_camel.py`, `generar_entidades.py`.
4. Versionar `master_data/dim_segmento_historico.parquet` y los parquets regenerados.
5. Desde ahí la ingesta mensual (GitHub Actions) mantiene la dimensión sola; si la dimensión falta, el paso de verificación y la validación mensual **fallan** a propósito.

## Revisiones retrospectivas
Si la SEPS republica un mes con otro segmento, el upsert reemplaza el mes completo y deja el cambio en la bitácora. El
mes se reprocesa en balance/PyG/CAMEL porque la dimensión manda.

## Qué NO resuelve
- Meses para los que no existan ZIP originales: quedan `segmento_historico_estimado = True` (declarado, no oculto).
- Que los nombres de cooperativa difieran entre normalizadores (balance, PyG y CAMEL tienen el suyo): lo que no empareja
  queda estimado y se informa en `pct_cubierto` de cada dataset.

## Ingesta desde la fuente (sin archivos externos) — hallazgos y diseño final

Verificado contra el portal oficial (`estadisticas.seps.gob.ec`, oct-2026):

| Fuente del portal | Contenido | Segmento |
|---|---|---|
| EEFF Mensuales 2018 y 2019 (panel "Años anteriores") | CSV mensual por entidad | **Exacto, cada mes** |
| EEFF Mensuales 2020-2026 | Boletines XLSM por segmento con **un solo corte** (dic; 2026: sep) | Exacto en ese corte |
| **Entidades trimestral 2018-2026** (XLSX hasta 2024, TXT UTF-8 2025, TXT UTF-16 2026) | Registro oficial: fecha de corte, RUC, razón social, **SEGMENTO**, estado jurídico | Exacto por trimestre |

Consecuencia: el portal ya no publica los CSV mensuales de 2020-2025 que alimentaron el
balance histórico del repositorio, así que el segmento mensual de esos años se reconstruye así:

1. Dato **exacto** del mes cuando existe (CSV 2018-19, boletines).
2. Si no, el **último corte trimestral ≤ mes** (nunca uno futuro), a lo sumo 2 meses atrás.
   Las filas quedan con `es_arrastrado = True` y `fecha_corte_origen`.

`SIN SEGMENTO` (entidades extintas / sin clasificar) se conserva en
`entidades_trimestral.parquet` con segmento nulo y no entra a la dimensión. Un segmento
desconocido distinto de ese hace fallar la ingesta.

Comandos (todo desde el portal):

```bash
python scripts/backfill_segmento_desde_fuente.py      # descarga 2018->hoy y reconstruye la dimensión
python scripts/segmento_historico.py --acoplar-master # aplica la dimensión a balance/pyg/indicadores
python scripts/segmento_historico.py --actualizar-entidades   # ingesta periódica (workflow)
python scripts/segmento_historico.py --verificar
```

Calidad medida el 2026-10-18: 99,4 % de los pares cooperativa-mes del balance con segmento
point-in-time real (resto marcado `segmento_historico_estimado`); en 4 424 pares donde coinciden
dato exacto y trimestral hay 43 discrepancias (0,97 %), todas en meses de recalificación
anual (mayo 2018), por lo que se prioriza el dato exacto. Nombres con mojibake en el balance
(`CRÃ‰DITO`) se reparan solo para el cruce.

Limitaciones: jul-ago 2026 (y feb-abr, etc. donde falta corte) son arrastre de un corte
anterior; los CSV mensuales 2020-2025 ya no están en la fuente, por lo que el balance
histórico no puede regenerarse desde ella.
