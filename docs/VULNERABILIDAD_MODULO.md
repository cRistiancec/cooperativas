# Módulo de vulnerabilidad financiera (S1–S3)

Código: `analytics/vulnerabilidad/`; resultados: `reports/vulnerabilidad/`; artefacto de la app: `master_data/panel_vulnerabilidad.parquet`.
Reproducir: `python analytics/construir_panel.py . <dir>` → `python -m analytics.vulnerabilidad.run_all <dir>/panel_cooperativas_S1S3.parquet reports/vulnerabilidad master_data/panel_vulnerabilidad.parquet` → `python -m analytics.vulnerabilidad.camel_vs_indice reports/vulnerabilidad/camel_vs_indice.json`.

## Identidad de la entidad (corrección de cierre)
El panel usa un identificador estable por entidad: (i) se corrigió la codificación (UTF-8 leído como cp1252) que partía 17 cooperativas en dos identidades sin solape de fechas (2018–2021 / 2022+); (ii) el sufijo «EN LIQUIDACION» que la SEPS añade al nombre se vincula a la misma entidad (7 casos, fechas contiguas), conservando `cooperativa_fuente`. Efecto: 255 → 232 cooperativas en el panel, series completas y rezagos correctos. Equivalencias: `master_data/equivalencias_nombres.csv`.

## Definiciones (verificadas contra indicadores SEPS 2020+)
| Indicador | Fórmula | Concordancia con SEPS |
|---|---|---|
| Liquidez | fondos disponibles (11) / (2101+210305+210310) | exacta |
| Morosidad, cobertura | improductiva/bruta; provisiones/improductiva | exactas |
| ROA, ROE | resultado YTD ×12/m ÷ promedio de saldos (dic. previo..m) | corr 0,9997 / 0,9985; mediana de diferencia 0 |
| Capitalización (proxy) | (activos − pasivos)/activos, incluye el resultado del ejercicio | no es solvencia regulatoria |
| Eficiencia | gasto de operación/ingreso operativo, 12m | no reconciliada |
Identidad contable: A = P + Pat + resultado YTD (ene–nov); A = P + Pat en diciembre (resultado ya cerrado). Activos ≤ 0 → ratio nulo; infinitos → nulos.

## Índice compuesto (exploratorio)
Z orientado (alto = más vulnerable), winsorización 1–99 % pooled; pesos iguales y PCA (sin pesos negativos); 500 pesos Dirichlet. PC1 explica 32,5 %; Spearman iguales vs PCA = 0,93; con pesos aleatorios mínimo 0,55 y percentil 5 = 0,70: ordenamiento razonablemente robusto, no invariante a pesos extremos.

## Panel con efectos fijos (entidad + mes; errores agrupados por cooperativa)
n = 15.846 obs., 228 cooperativas, 61 con reclasificación (de ellas se identifica el efecto segmento).
- Crecimiento de activos 12m: −0,0058 (p<0,001); tamaño (ln activos): −0,146 (p=0,024). Parte es mecánica (denominadores); no causal.
- Segmento 2 vs 1: −0,11 (p=0,12); segmento 3 vs 1: −0,08 (p=0,37). **No significativos** tras unificar identidades (antes de la corrección S2 aparecía significativo: era un artefacto de las series partidas).
- Heterogeneidad del efecto del crecimiento por segmento: Wald p=0,80.
- Persistencia (índice t → t+12, por fecha): 0,26 (p<0,001), n=13.181.

## Sensibilidad a la calidad de la clasificación
Solo 47,0 % de las observaciones (34,4 % en 2020+) tiene el segmento del archivo SEPS del propio mes; 52,5 % es arrastrado y 0,5 % estimado. Con solo clasificación exacta (n=6.604 en FE):
- Mediana del índice por segmento (todas / exactas): S1 −0,16 / −0,19; S2 −0,03 / −0,05; S3 0,11 / 0,12. **El orden S1 < S2 < S3 se mantiene**; las diferencias descriptivas son robustas a la clasificación.
- Efectos FE de segmento: no significativos en ambas muestras (S2: p=0,12 / 0,16; S3: p=0,37 / 0,67).
Conclusión: las diferencias descriptivas del índice entre segmentos son estables; no hay evidencia de efecto del segmento *dentro* de la entidad. Cobertura por año/mes/segmento: `reports/vulnerabilidad/cobertura_segmentos.csv`.

## CAMEL vs. índice (asociación, no validación)
Spearman transversal por fecha (81 fechas, n por fecha 151–201): mediana −0,88 (rango −0,91 a −0,82); último corte −0,87 (n=191). Signo esperado (CAMEL alto = mejor; índice alto = peor). Comparten insumos (morosidad, cobertura, ROA, liquidez): la asociación es en parte mecánica. CAMEL: percentiles por indicador → promedio por letra → media simple de 5 letras (pesos iguales; verificado). El índice no sustituye al CAMEL.

## Alertas
Desviaciones estadísticas internas (z robusto mediana/MAD ≥ umbral frente a pares del mismo segmento y fecha; umbral 1,5–3,0 seleccionable; el número de alertas es muy sensible al umbral). Única regla contable: patrimonio total negativo. **No son umbrales regulatorios ni probabilidad de insolvencia.**
Patrimonio negativo: 20 observaciones / 7 entidades; es real (pérdidas acumuladas, cód. 36, superan capital y reservas; identidad contable exacta, 0 duplicados); varias entidades terminan «EN LIQUIDACION». Se conservan.

## Modelo de alerta temprana: exploratorio, NO validado
Eventos: estado jurídico EXTINTA/EN LIQUIDACIÓN (tabla trimestral) o sufijo «EN LIQUIDACION» en el nombre; 16 entidades en el panel, 13 con observaciones previas. Con orígenes rodantes (2020-12…2023-06; entrenamiento ≤ corte, prueba 24 m) el logit regularizado da AUC 0,96–0,98 pero **el AUC agrupa observaciones de solo 2–5 entidades de prueba** (cada una aporta hasta 12 positivos autocorrelacionados), con PR-AUC 0,06–0,25 frente a prevalencias de 0,4–1,3 %. No se interpreta como capacidad predictiva ni se publica probabilidad alguna. XGBoost no se justifica.
### Plan para un modelo predictivo futuro
1. **Evento observable:** liquidación/extinción/intervención con fecha oficial (no «dejó de reportar»); confirmar fusiones y absorciones para no contarlas como quiebra.
2. **Horizonte:** 6, 12 y 24 meses, fijados ex ante; observaciones posteriores al evento se excluyen.
3. **Fuga de información:** predictores solo con información al corte t; segmento point-in-time; sin usar el sufijo «EN LIQUIDACION» ni el estado jurídico como predictor; winsorización y estandarización calculadas solo en entrenamiento.
4. **Partición:** temporal con orígenes rodantes y bloques por entidad (validación cruzada agrupada por cooperativa).
5. **Métricas:** AUC y PR-AUC a nivel de entidad (no de observación), Brier, calibración, sensibilidad al umbral, por segmento; IC por bootstrap de entidades.
6. **Datos mínimos:** ≥ 30–50 entidades con evento (hoy 13); ampliar a S4–S5 y a la serie oficial 2000–2017 si existe; modelos de supervivencia (riesgo discreto) cuando haya tamaño suficiente.
