# Módulo de vulnerabilidad financiera (S1–S3)

Implementa el diseño de investigación (índice compuesto, panel FE, alerta temprana). Código: `analytics/vulnerabilidad/`; resultados: `reports/vulnerabilidad/`.

Reproducir: `python analytics/construir_panel.py . <dir>` y luego `python -m analytics.vulnerabilidad.run_all <dir>/panel_cooperativas_S1S3.parquet reports/vulnerabilidad`.

## Definiciones (verificadas contra indicadores SEPS 2020+)
| Indicador | Fórmula | Concordancia con SEPS |
|---|---|---|
| Liquidez | fondos disponibles (11) / (2101+210305+210310) | exacta (n=14.590) |
| Morosidad, cobertura | cartera improductiva / bruta; provisiones / improductiva | exactas |
| ROA, ROE | resultado YTD ×12/m ÷ promedio de saldos fin de mes (dic. previo..m) | corr 0,9997 / 0,9985; mediana dif. 0 |
| Solvencia (proxy), eficiencia | patrimonio/activos; gasto operación/ingreso operativo 12m | no reconciliadas |

ROA/ROE a 12 meses y liquidez solo-vista se conservan como alternas (corr 0,71 y 0,38 con SEPS): no usarlas como oficiales.

## Índice compuesto
Z_k orientado (alto = más vulnerable), winsorización 1–99 % pooled, pesos iguales y PCA (sin pesos negativos), 500 pesos Dirichlet para sensibilidad. PC1 explica 32 % de la varianza; Spearman entre pesos iguales y PCA = 0,93; mínimo en pesos aleatorios 0,56 (p05 = 0,70). Conclusión: el ordenamiento es razonablemente robusto, pero no invariante a pesos extremos.

## Panel con efectos fijos (entidad + mes, errores agrupados por cooperativa)
n = 15.601 obs., 242 cooperativas, 60 con reclasificación dentro de S1–S3 (de ellas se identifica el efecto segmento).
- Crecimiento de activos 12m reduce el índice (−0,0054; p<0,001): en parte mecánico (ROA, solvencia y morosidad responden al denominador). No es causal.
- Segmento 2 vs 1: −0,17 (p=0,026); segmento 3 vs 1: −0,14 (p=0,13). Frágil.
- Heterogeneidad del efecto del crecimiento por segmento: Wald p=0,95 (no se rechaza homogeneidad).
- Persistencia: coef. del índice a t+12 = 0,27 (p<0,001) con FE.

## Alerta temprana: NO estimable con rigor
Solo 16 cooperativas con estado jurídico EXTINTA/EN LIQUIDACIÓN pasan al panel, y solo 8 tienen observaciones en los 12 meses previos (la mayoría de los eventos ocurre en 2018–2020). Con orígenes temporales rodantes (2020-12 a 2023-06) ninguno cumple el mínimo de ≥3 cooperativas con evento en entrenamiento y ≥2 en prueba. Un AUC alto con un solo evento en prueba (p. ej. 0,98 con origen 2020-12) no es evidencia y no se reporta como resultado. XGBoost no está justificado. Vías para mejorar: confirmar las 30 salidas sin registro posterior (fusiones/absorciones), ampliar a S4–S5 y definir eventos con criterios regulatorios (plan de regularización, intervención).

## Limitaciones
Segmento estimado (arrastrado) ≈0,5 %; PyG y CAMEL desde 2020; jul–ago 2026 arrastrados desde junio; resultados descriptivos y asociativos, no causales.
