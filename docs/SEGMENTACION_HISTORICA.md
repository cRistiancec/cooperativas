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
