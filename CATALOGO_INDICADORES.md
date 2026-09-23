# CATÁLOGO DE INDICADORES — Motor Central

**Radar Cooperativo Ecuador — COSEDE**

Generado automáticamente por `scripts/generar_documentacion_indicadores.py` a partir de `config/indicator_mapping.py` y `analytics/catalogo_indicadores.py`. **No editar este archivo a mano** — los cambios se pierden en la siguiente regeneración; edite las fuentes y vuelva a ejecutar el script.

- Indicadores oficiales SEPS (pre-calculados): **41**
- Indicadores nuevos del Motor Central (Fase 2.3 + 2.4): **14**
- **Total: 55**

---

## Índice

**Oficiales SEPS**, por categoría CAMEL:
- **C - Capital**: 6 indicadores (SUF_PAT, VULN_PAT, CART_IMPR_PAT, FK, FI, CAP_NETO)
- **A - Calidad de Activos**: 6 indicadores (ACT_IMPR, ACT_PROD, AP_PC, CART_REF, CART_REEST, CART_VENCER)
- **A - Morosidad por Cartera**: 7 indicadores (MOR_TOT, MOR_CONS, MOR_INMOB, MOR_MICRO, MOR_PROD, MOR_VIV_IP, MOR_EDU)
- **A - Cobertura por Cartera**: 7 indicadores (COB_TOT, COB_CONS, COB_INMOB, COB_MICRO, COB_PROD, COB_VIV_IP, COB_EDU)
- **M - Management y Eficiencia**: 3 indicadores (GO_ACT, GO_MNF, GP_ACT)
- **E - Earnings (Rentabilidad)**: 11 indicadores (ROE, ROA, INTERM, MARG_PAT, MARG_ACT, REND_CONS, REND_INMOB, REND_MICRO, REND_PROD, REND_VIV, REND_EDU)
- **L - Liquidez**: 1 indicadores (LIQ)

**Nuevos (Motor Central)**, por dominio:
- **rentabilidad**: 5 indicadores (TASA_PASIVA_IMPLICITA, TASA_ACTIVA_IMPLICITA, SPREAD_FINANCIERO, MARGEN_FINANCIERO_12M, ROE_AJUSTADO)
- **crecimiento**: 3 indicadores (CRECIMIENTO_CAPTACIONES, CRECIMIENTO_COLOCACIONES, CARTERA_EN_RIESGO)
- **indices_ejecutivos**: 6 indicadores (SCORE_FINANCIERO_INTEGRAL, INDICE_VULNERABILIDAD, INDICE_FORTALEZA, INDICE_RESILIENCIA, INDICE_ESTABILIDAD, INDICE_RIESGO_INTEGRAL)

---

## Indicadores oficiales SEPS (pre-calculados)

### `ACT_IMPR` — Activos Improductivos / Activos

| Campo | Valor |
|---|---|
| **Nombre** | Activos Improductivos / Activos |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `I2_prop_act_impr_net`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `I2_prop_act_impr_net` → código interno `ACT_IMPR` |
| **Interpretación** | Menor es mejor (escala de color `RdYlGn_r` en los heatmaps) |
| **Rango esperado** | 0 – 25% |
| **Categoría CAMEL** | A - Calidad de Activos |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `ACT_PROD` — Activos Productivos / Activos

| Campo | Valor |
|---|---|
| **Nombre** | Activos Productivos / Activos |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `I3_prop_act_prod_net`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `I3_prop_act_prod_net` → código interno `ACT_PROD` |
| **Interpretación** | Mayor es mejor (escala de color `RdYlGn` en los heatmaps) |
| **Rango esperado** | 75 – 100% |
| **Categoría CAMEL** | A - Calidad de Activos |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `AP_PC` — Activos Productivos / Pasivos con Costo

| Campo | Valor |
|---|---|
| **Nombre** | Activos Productivos / Pasivos con Costo |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `I4_uti_pas_cost_prod_gene`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `I4_uti_pas_cost_prod_gene` → código interno `AP_PC` |
| **Interpretación** | Mayor es mejor (escala de color `RdYlGn` en los heatmaps) |
| **Rango esperado** | 90 – 130% |
| **Categoría CAMEL** | A - Calidad de Activos |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `CAP_NETO` — Índice de Capitalización Neto

| Campo | Valor |
|---|---|
| **Nombre** | Índice de Capitalización Neto |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `I50_Indi_capi_neto`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `I50_Indi_capi_neto` → código interno `CAP_NETO` |
| **Interpretación** | Mayor es mejor (escala de color `RdYlGn` en los heatmaps) |
| **Rango esperado** | 0 – 25% |
| **Categoría CAMEL** | C - Capital |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `CART_IMPR_PAT` — Cartera Improductiva / Patrimonio

| Campo | Valor |
|---|---|
| **Nombre** | Cartera Improductiva / Patrimonio |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `I47_Carte_impr_patri_dic`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `I47_Carte_impr_patri_dic` → código interno `CART_IMPR_PAT` |
| **Interpretación** | Menor es mejor (escala de color `RdYlGn_r` en los heatmaps) |
| **Rango esperado** | 0 – 80% |
| **Categoría CAMEL** | C - Capital |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `CART_REEST` — Cartera de Créditos Reestructurada

| Campo | Valor |
|---|---|
| **Nombre** | Cartera de Créditos Reestructurada |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `I43_Cart_cred_reest`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `I43_Cart_cred_reest` → código interno `CART_REEST` |
| **Interpretación** | Menor es mejor (escala de color `RdYlGn_r` en los heatmaps) |
| **Rango esperado** | 0 – 35% |
| **Categoría CAMEL** | A - Calidad de Activos |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `CART_REF` — Cartera de Créditos Refinanciada

| Campo | Valor |
|---|---|
| **Nombre** | Cartera de Créditos Refinanciada |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `I42_Cart_cred_ref_xven`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `I42_Cart_cred_ref_xven` → código interno `CART_REF` |
| **Interpretación** | Menor es mejor (escala de color `RdYlGn_r` en los heatmaps) |
| **Rango esperado** | 0 – 30% |
| **Categoría CAMEL** | A - Calidad de Activos |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `CART_VENCER` — Cartera por Vencer Total

| Campo | Valor |
|---|---|
| **Nombre** | Cartera por Vencer Total |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `I44_cartera_x_vencer`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `I44_cartera_x_vencer` → código interno `CART_VENCER` |
| **Interpretación** | Mayor es mejor (escala de color `RdYlGn` en los heatmaps) |
| **Rango esperado** | 0 – 25% |
| **Categoría CAMEL** | A - Calidad de Activos |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `COB_CONS` — Cobertura Consumo

| Campo | Valor |
|---|---|
| **Nombre** | Cobertura Consumo |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `Cober_carte_consu`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `Cober_carte_consu` → código interno `COB_CONS` |
| **Interpretación** | Mayor es mejor (escala de color `RdYlGn` en los heatmaps) |
| **Rango esperado** | 0 – 200% |
| **Categoría CAMEL** | A - Cobertura por Cartera |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `COB_EDU` — Cobertura Educativo

| Campo | Valor |
|---|---|
| **Nombre** | Cobertura Educativo |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `I24_Cober_carte_educ`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `I24_Cober_carte_educ` → código interno `COB_EDU` |
| **Interpretación** | Mayor es mejor (escala de color `RdYlGn` en los heatmaps) |
| **Rango esperado** | 0 – 200% |
| **Categoría CAMEL** | A - Cobertura por Cartera |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `COB_INMOB` — Cobertura Inmobiliaria

| Campo | Valor |
|---|---|
| **Nombre** | Cobertura Inmobiliaria |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `I18_Cober_carte_inmob`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `I18_Cober_carte_inmob` → código interno `COB_INMOB` |
| **Interpretación** | Mayor es mejor (escala de color `RdYlGn` en los heatmaps) |
| **Rango esperado** | 0 – 200% |
| **Categoría CAMEL** | A - Cobertura por Cartera |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `COB_MICRO` — Cobertura Microcrédito

| Campo | Valor |
|---|---|
| **Nombre** | Cobertura Microcrédito |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `I19_Cober_carte_micro`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `I19_Cober_carte_micro` → código interno `COB_MICRO` |
| **Interpretación** | Mayor es mejor (escala de color `RdYlGn` en los heatmaps) |
| **Rango esperado** | 0 – 200% |
| **Categoría CAMEL** | A - Cobertura por Cartera |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `COB_PROD` — Cobertura Productivo

| Campo | Valor |
|---|---|
| **Nombre** | Cobertura Productivo |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `I20_Cober_carte_produ`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `I20_Cober_carte_produ` → código interno `COB_PROD` |
| **Interpretación** | Mayor es mejor (escala de color `RdYlGn` en los heatmaps) |
| **Rango esperado** | 0 – 200% |
| **Categoría CAMEL** | A - Cobertura por Cartera |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `COB_TOT` — Cobertura Total

| Campo | Valor |
|---|---|
| **Nombre** | Cobertura Total |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `I15_Cober_carte`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `I15_Cober_carte` → código interno `COB_TOT` |
| **Interpretación** | Mayor es mejor (escala de color `RdYlGn` en los heatmaps) |
| **Rango esperado** | 0 – 250% |
| **Categoría CAMEL** | A - Cobertura por Cartera |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `COB_VIV_IP` — Cobertura Vivienda Interés Público

| Campo | Valor |
|---|---|
| **Nombre** | Cobertura Vivienda Interés Público |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `I23_Cober_carte_vivi_ip`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `I23_Cober_carte_vivi_ip` → código interno `COB_VIV_IP` |
| **Interpretación** | Mayor es mejor (escala de color `RdYlGn` en los heatmaps) |
| **Rango esperado** | 0 – 200% |
| **Categoría CAMEL** | A - Cobertura por Cartera |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `FI` — FI

| Campo | Valor |
|---|---|
| **Nombre** | FI |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `I49_FI`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `I49_FI` → código interno `FI` |
| **Interpretación** | Informativo (sin dirección única en la metodología vigente) (escala de color `Blues` en los heatmaps) |
| **Rango esperado** | 100 – 130% |
| **Categoría CAMEL** | C - Capital |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `FK` — FK

| Campo | Valor |
|---|---|
| **Nombre** | FK |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `I48_FK`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `I48_FK` → código interno `FK` |
| **Interpretación** | Informativo (sin dirección única en la metodología vigente) (escala de color `Blues` en los heatmaps) |
| **Rango esperado** | 0 – 30% |
| **Categoría CAMEL** | C - Capital |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `GO_ACT` — Gastos de Operación / Activo Promedio

| Campo | Valor |
|---|---|
| **Nombre** | Gastos de Operación / Activo Promedio |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `I25_Efici_opera`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `I25_Efici_opera` → código interno `GO_ACT` |
| **Interpretación** | Menor es mejor (escala de color `RdYlGn_r` en los heatmaps) |
| **Rango esperado** | 0 – 10% |
| **Categoría CAMEL** | M - Management y Eficiencia |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `GO_MNF` — Gastos de Operación / Margen Financiero

| Campo | Valor |
|---|---|
| **Nombre** | Gastos de Operación / Margen Financiero |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `I26_Grad_abso`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `I26_Grad_abso` → código interno `GO_MNF` |
| **Interpretación** | Menor es mejor (escala de color `RdYlGn_r` en los heatmaps) |
| **Rango esperado** | 75 – 150% |
| **Categoría CAMEL** | M - Management y Eficiencia |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `GP_ACT` — Gastos de Personal / Activo Promedio

| Campo | Valor |
|---|---|
| **Nombre** | Gastos de Personal / Activo Promedio |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `I27_Efic_adm_pers`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `I27_Efic_adm_pers` → código interno `GP_ACT` |
| **Interpretación** | Menor es mejor (escala de color `RdYlGn_r` en los heatmaps) |
| **Rango esperado** | 0 – 5% |
| **Categoría CAMEL** | M - Management y Eficiencia |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `INTERM` — Intermediación Financiera

| Campo | Valor |
|---|---|
| **Nombre** | Intermediación Financiera |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `I30_Interm_fin`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `I30_Interm_fin` → código interno `INTERM` |
| **Interpretación** | Informativo (sin dirección única en la metodología vigente) (escala de color `Blues` en los heatmaps) |
| **Rango esperado** | 50 – 200% |
| **Categoría CAMEL** | E - Earnings (Rentabilidad) |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `LIQ` — Fondos Disponibles / Depósitos CP

| Campo | Valor |
|---|---|
| **Nombre** | Fondos Disponibles / Depósitos CP |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `I45_Fond_dis_sob_total_depo_cort_plz`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `I45_Fond_dis_sob_total_depo_cort_plz` → código interno `LIQ` |
| **Interpretación** | Mayor es mejor (escala de color `RdYlGn` en los heatmaps) |
| **Rango esperado** | 10 – 50% |
| **Categoría CAMEL** | L - Liquidez |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `MARG_ACT` — Margen de Intermediación / Activo

| Campo | Valor |
|---|---|
| **Nombre** | Margen de Intermediación / Activo |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `I32_Marg_inter_est_activ`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `I32_Marg_inter_est_activ` → código interno `MARG_ACT` |
| **Interpretación** | Mayor es mejor (escala de color `RdYlGn` en los heatmaps) |
| **Rango esperado** | -5 – 5% |
| **Categoría CAMEL** | E - Earnings (Rentabilidad) |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `MARG_PAT` — Margen de Intermediación / Patrimonio

| Campo | Valor |
|---|---|
| **Nombre** | Margen de Intermediación / Patrimonio |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `I31_Marg_inter_est_patri`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `I31_Marg_inter_est_patri` → código interno `MARG_PAT` |
| **Interpretación** | Mayor es mejor (escala de color `RdYlGn` en los heatmaps) |
| **Rango esperado** | -30 – 20% |
| **Categoría CAMEL** | E - Earnings (Rentabilidad) |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `MOR_CONS` — Morosidad Consumo

| Campo | Valor |
|---|---|
| **Nombre** | Morosidad Consumo |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `Moros_carte_consu`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `Moros_carte_consu` → código interno `MOR_CONS` |
| **Interpretación** | Menor es mejor (escala de color `RdYlGn_r` en los heatmaps) |
| **Rango esperado** | 0 – 15% |
| **Categoría CAMEL** | A - Morosidad por Cartera |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `MOR_EDU` — Morosidad Educativo

| Campo | Valor |
|---|---|
| **Nombre** | Morosidad Educativo |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `I14_Moros_carte_educ`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `I14_Moros_carte_educ` → código interno `MOR_EDU` |
| **Interpretación** | Menor es mejor (escala de color `RdYlGn_r` en los heatmaps) |
| **Rango esperado** | 0 – 15% |
| **Categoría CAMEL** | A - Morosidad por Cartera |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `MOR_INMOB` — Morosidad Inmobiliaria

| Campo | Valor |
|---|---|
| **Nombre** | Morosidad Inmobiliaria |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `I8_Moros_carte_inmob`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `I8_Moros_carte_inmob` → código interno `MOR_INMOB` |
| **Interpretación** | Menor es mejor (escala de color `RdYlGn_r` en los heatmaps) |
| **Rango esperado** | 0 – 15% |
| **Categoría CAMEL** | A - Morosidad por Cartera |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `MOR_MICRO` — Morosidad Microcrédito

| Campo | Valor |
|---|---|
| **Nombre** | Morosidad Microcrédito |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `I9_Moros_carte_micro`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `I9_Moros_carte_micro` → código interno `MOR_MICRO` |
| **Interpretación** | Menor es mejor (escala de color `RdYlGn_r` en los heatmaps) |
| **Rango esperado** | 0 – 15% |
| **Categoría CAMEL** | A - Morosidad por Cartera |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `MOR_PROD` — Morosidad Productivo

| Campo | Valor |
|---|---|
| **Nombre** | Morosidad Productivo |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `I10_Moros_carte_produ`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `I10_Moros_carte_produ` → código interno `MOR_PROD` |
| **Interpretación** | Menor es mejor (escala de color `RdYlGn_r` en los heatmaps) |
| **Rango esperado** | 0 – 15% |
| **Categoría CAMEL** | A - Morosidad por Cartera |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `MOR_TOT` — Morosidad Total

| Campo | Valor |
|---|---|
| **Nombre** | Morosidad Total |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `I5_Moros_carte`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `I5_Moros_carte` → código interno `MOR_TOT` |
| **Interpretación** | Menor es mejor (escala de color `RdYlGn_r` en los heatmaps) |
| **Rango esperado** | 0 – 15% |
| **Categoría CAMEL** | A - Morosidad por Cartera |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `MOR_VIV_IP` — Morosidad Vivienda Interés Público

| Campo | Valor |
|---|---|
| **Nombre** | Morosidad Vivienda Interés Público |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `I13_Moros_carte_vivi_ip`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `I13_Moros_carte_vivi_ip` → código interno `MOR_VIV_IP` |
| **Interpretación** | Menor es mejor (escala de color `RdYlGn_r` en los heatmaps) |
| **Rango esperado** | 0 – 15% |
| **Categoría CAMEL** | A - Morosidad por Cartera |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `REND_CONS` — Rendimiento Cartera Consumo

| Campo | Valor |
|---|---|
| **Nombre** | Rendimiento Cartera Consumo |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `I34_Rend_cart_consu_x_venc`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `I34_Rend_cart_consu_x_venc` → código interno `REND_CONS` |
| **Interpretación** | Informativo (sin dirección única en la metodología vigente) (escala de color `Blues` en los heatmaps) |
| **Rango esperado** | 0 – 20% |
| **Categoría CAMEL** | E - Earnings (Rentabilidad) |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `REND_EDU` — Rendimiento Cartera Educativo

| Campo | Valor |
|---|---|
| **Nombre** | Rendimiento Cartera Educativo |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `I41_Rend_cart_educ_x_venc`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `I41_Rend_cart_educ_x_venc` → código interno `REND_EDU` |
| **Interpretación** | Informativo (sin dirección única en la metodología vigente) (escala de color `Blues` en los heatmaps) |
| **Rango esperado** | 0 – 10% |
| **Categoría CAMEL** | E - Earnings (Rentabilidad) |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `REND_INMOB` — Rendimiento Cartera Inmobiliaria

| Campo | Valor |
|---|---|
| **Nombre** | Rendimiento Cartera Inmobiliaria |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `I35_Rend_cart_inmob_x_venc`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `I35_Rend_cart_inmob_x_venc` → código interno `REND_INMOB` |
| **Interpretación** | Informativo (sin dirección única en la metodología vigente) (escala de color `Blues` en los heatmaps) |
| **Rango esperado** | 0 – 15% |
| **Categoría CAMEL** | E - Earnings (Rentabilidad) |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `REND_MICRO` — Rendimiento Cartera Microcrédito

| Campo | Valor |
|---|---|
| **Nombre** | Rendimiento Cartera Microcrédito |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `I36_Rend_cart_micro_x_venc`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `I36_Rend_cart_micro_x_venc` → código interno `REND_MICRO` |
| **Interpretación** | Informativo (sin dirección única en la metodología vigente) (escala de color `Blues` en los heatmaps) |
| **Rango esperado** | 0 – 25% |
| **Categoría CAMEL** | E - Earnings (Rentabilidad) |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `REND_PROD` — Rendimiento Cartera Productivo

| Campo | Valor |
|---|---|
| **Nombre** | Rendimiento Cartera Productivo |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `I37_Rend_cart_prod_x_venc`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `I37_Rend_cart_prod_x_venc` → código interno `REND_PROD` |
| **Interpretación** | Informativo (sin dirección única en la metodología vigente) (escala de color `Blues` en los heatmaps) |
| **Rango esperado** | 0 – 15% |
| **Categoría CAMEL** | E - Earnings (Rentabilidad) |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `REND_VIV` — Rendimiento Cartera Vivienda IP

| Campo | Valor |
|---|---|
| **Nombre** | Rendimiento Cartera Vivienda IP |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `I40_Rend_cart_vivie_x_venc`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `I40_Rend_cart_vivie_x_venc` → código interno `REND_VIV` |
| **Interpretación** | Informativo (sin dirección única en la metodología vigente) (escala de color `Blues` en los heatmaps) |
| **Rango esperado** | 0 – 10% |
| **Categoría CAMEL** | E - Earnings (Rentabilidad) |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `ROA` — ROA

| Campo | Valor |
|---|---|
| **Nombre** | ROA |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `I29_ROA`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `I29_ROA` → código interno `ROA` |
| **Interpretación** | Mayor es mejor (escala de color `RdYlGn` en los heatmaps) |
| **Rango esperado** | -1 – 3% |
| **Categoría CAMEL** | E - Earnings (Rentabilidad) |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `ROE` — ROE

| Campo | Valor |
|---|---|
| **Nombre** | ROE |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `I28_ROE`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `I28_ROE` → código interno `ROE` |
| **Interpretación** | Mayor es mejor (escala de color `RdYlGn` en los heatmaps) |
| **Rango esperado** | -5 – 15% |
| **Categoría CAMEL** | E - Earnings (Rentabilidad) |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `SUF_PAT` — Suficiencia Patrimonial

| Campo | Valor |
|---|---|
| **Nombre** | Suficiencia Patrimonial |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `I1_suficiencia_patrimonial`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `I1_suficiencia_patrimonial` → código interno `SUF_PAT` |
| **Interpretación** | Mayor es mejor (escala de color `RdYlGn` en los heatmaps) |
| **Rango esperado** | 0 – 300% |
| **Categoría CAMEL** | C - Capital |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

### `VULN_PAT` — Cart. Improd. Descubierta / Patrimonio

| Campo | Valor |
|---|---|
| **Nombre** | Cart. Improd. Descubierta / Patrimonio |
| **Descripción** | Indicador financiero oficial de la Superintendencia de Economía Popular y Solidaria (SEPS), publicado en la hoja "5. Indicadores Financieros" del boletín mensual. |
| **Fórmula** | No publicada por la SEPS — es un indicador **pre-calculado**, extraído directamente del pivot cache oficial (campo `I46_Carte_impro_descu_rela_patri_resul`). La plataforma no reproduce el cálculo: consume el valor tal como lo reporta el regulador. |
| **Variables** | Campo SEPS `I46_Carte_impro_descu_rela_patri_resul` → código interno `VULN_PAT` |
| **Interpretación** | Menor es mejor (escala de color `RdYlGn_r` en los heatmaps) |
| **Rango esperado** | 0 – 60% |
| **Categoría CAMEL** | C - Capital |
| **Módulo** | `config/indicator_mapping.py` (mapeo) · `scripts/procesar_camel.py` (extracción) · `analytics/camels_score.py`, `analytics/solvencia.py`, `analytics/credito.py`, `analytics/liquidez.py` (consumo, según el indicador) |
| **Dependencias** | `master_data/indicadores.parquet` |
| **Frecuencia de actualización** | Mensual (con cada boletín de la SEPS) |
| **Fuente** | SEPS (oficial, pre-calculado) |

---

## Indicadores nuevos del Motor Central

### `TASA_PASIVA_IMPLICITA` — Tasa Pasiva Implícita

| Campo | Valor |
|---|---|
| **Nombre** | Tasa Pasiva Implícita |
| **Descripción** | Costo efectivo de fondeo: cuánto paga la cooperativa, en promedio, por sus depósitos. |
| **Fórmula** | interés causado en depósitos (12 meses) / promedio móvil 3 meses de depósitos del público |
| **Variables** | pyg.codigo=4101 (valor_12m); balance.codigo=21 (promedio 3 cortes) |
| **Interpretación financiera** | Más alta que la del sistema puede indicar dependencia de captación cara (plazo fijo agresivo) para sostener el fondeo. |
| **Rango esperado** | 2% – 15% anual (P5–P95 del sistema, jun-2026) |
| **Módulo** | `analytics.rentabilidad.calcular_tasas_implicitas` |
| **Dependencias** | pyg.parquet, agg_ranking_cooperativas.parquet |
| **Frecuencia de actualización** | Mensual (con cada actualización de datos SEPS) |
| **Fuente** | Calculado — Motor Central (migrado de TASA_PI, script R) |

### `TASA_ACTIVA_IMPLICITA` — Tasa Activa Implícita

| Campo | Valor |
|---|---|
| **Nombre** | Tasa Activa Implícita |
| **Descripción** | Rendimiento efectivo de la cartera: cuánto genera, en promedio, cada dólar prestado. |
| **Fórmula** | interés ganado en cartera (12 meses) / promedio móvil 3 meses de cartera bruta |
| **Variables** | pyg.codigo=5104 (valor_12m); balance.codigo=14 (promedio 3 cortes) |
| **Interpretación financiera** | Muy por encima del sistema puede señalar una cartera de mayor riesgo (tasas más altas compensan mayor probabilidad de impago). |
| **Rango esperado** | 11% – 31% anual (P5–P95 del sistema, jun-2026) |
| **Módulo** | `analytics.rentabilidad.calcular_tasas_implicitas` |
| **Dependencias** | pyg.parquet, agg_ranking_cooperativas.parquet |
| **Frecuencia de actualización** | Mensual |
| **Fuente** | Calculado — Motor Central (migrado de TASA_AI, script R) |

### `SPREAD_FINANCIERO` — Spread Financiero

| Campo | Valor |
|---|---|
| **Nombre** | Spread Financiero |
| **Descripción** | Margen de intermediación en puntos porcentuales: la diferencia entre lo que la cooperativa cobra por prestar y lo que paga por captar. |
| **Fórmula** | tasa_activa_implicita − tasa_pasiva_implicita |
| **Variables** | Ver Tasa Activa Implícita, Tasa Pasiva Implícita |
| **Interpretación financiera** | Motor estructural de rentabilidad. Un spread que se comprime en el tiempo, con volumen de negocio estable, anticipa presión sobre el margen financiero. |
| **Rango esperado** | 4.5% – 26.5% (P5–P95 del sistema, jun-2026) |
| **Módulo** | `analytics.rentabilidad.calcular_tasas_implicitas` |
| **Dependencias** | pyg.parquet, agg_ranking_cooperativas.parquet |
| **Frecuencia de actualización** | Mensual |
| **Fuente** | Calculado — Motor Central (migrado de TASA_MF, script R) |

### `MARGEN_FINANCIERO_12M` — Margen Financiero (12 meses, USD)

| Campo | Valor |
|---|---|
| **Nombre** | Margen Financiero (12 meses, USD) |
| **Descripción** | Resultado financiero neto en dólares: ingresos financieros menos gastos financieros, anualizado. |
| **Fórmula** | (intereses + comisiones + utilidades financieras + servicios) − (intereses + comisiones + pérdidas financieras + provisiones), suma móvil 12 meses |
| **Variables** | pyg.codigo∈{51,52,53,54,41,42,43,44} (valor_12m) |
| **Interpretación financiera** | La cifra en dólares detrás del spread — relevante para tamaño absoluto, no solo el ratio. |
| **Rango esperado** | Positivo en la gran mayoría del sistema; negativo es señal de alerta operativa |
| **Módulo** | `analytics.rentabilidad.calcular_margen_financiero` |
| **Dependencias** | pyg.parquet |
| **Frecuencia de actualización** | Mensual |
| **Fuente** | Calculado — Motor Central (migrado de MARGEN_FINANCIERO, script R) |

### `ROE_AJUSTADO` — ROE Ajustado

| Campo | Valor |
|---|---|
| **Nombre** | ROE Ajustado |
| **Descripción** | Rentabilidad patrimonial excluyendo ingresos no recurrentes ("otros ingresos"), sobre patrimonio promedio de 3 meses. |
| **Fórmula** | (ingresos − gastos − otros_ingresos) [12m] / patrimonio_promedio_3m |
| **Variables** | pyg.codigo∈{5,4,56} (valor_12m); balance.codigo=3 (promedio 3 cortes) |
| **Interpretación financiera** | Una brecha grande frente al ROE oficial indica que la rentabilidad reportada depende de partidas no operativas — insumo directo del Índice de Vulnerabilidad. |
| **Rango esperado** | -105% – 15% (observado en el sistema, jun-2026; el ROE oficial no penaliza otros ingresos y por eso es sistemáticamente más alto) |
| **Módulo** | `analytics.rentabilidad.calcular_roe_ajustado` |
| **Dependencias** | pyg.parquet, agg_ranking_cooperativas.parquet |
| **Frecuencia de actualización** | Mensual |
| **Fuente** | Calculado — Motor Central (migrado de ROE_ADJ, script R) |

### `CRECIMIENTO_CAPTACIONES` — Crecimiento de Captaciones

| Campo | Valor |
|---|---|
| **Nombre** | Crecimiento de Captaciones |
| **Descripción** | Variación absoluta y porcentual de los depósitos del público entre dos fechas. |
| **Fórmula** | (depósitos_actual − depósitos_anterior) ; (depósitos_actual / depósitos_anterior − 1) × 100 |
| **Variables** | agg_ranking_cooperativas.codigo=21, dos fechas |
| **Interpretación financiera** | Horizonte anual (fecha_anterior = -12 meses) o mensual (-1 mes), según qué fecha se pase. Contracción sostenida es señal temprana de fuga de depósitos. |
| **Rango esperado** | Variable — depende del horizonte y del ciclo del sistema |
| **Módulo** | `analytics.crecimiento.crecimiento_captaciones` |
| **Dependencias** | utils.data_loader.obtener_crecimiento_anual, agg_ranking_cooperativas.parquet |
| **Frecuencia de actualización** | Mensual |
| **Fuente** | Calculado — Motor Central (migrado de CAPGA/TCAPGA/CAPGM/TCAPGM, script R) |

### `CRECIMIENTO_COLOCACIONES` — Crecimiento de Colocaciones

| Campo | Valor |
|---|---|
| **Nombre** | Crecimiento de Colocaciones |
| **Descripción** | Variación absoluta y porcentual de la cartera bruta entre dos fechas. |
| **Fórmula** | (cartera_actual − cartera_anterior) ; (cartera_actual / cartera_anterior − 1) × 100 |
| **Variables** | agg_ranking_cooperativas.codigo=14, dos fechas |
| **Interpretación financiera** | Insumo del Score Financiero Integral y del ranking de crecimiento de Panorama. Crecimiento muy por encima del sistema, sin deterioro de mora, puede indicar ganancia de mercado; acompañado de mora al alza, sobre-extensión del crédito. |
| **Rango esperado** | Variable — depende del horizonte y del ciclo del sistema |
| **Módulo** | `analytics.crecimiento.crecimiento_colocaciones` |
| **Dependencias** | utils.data_loader.obtener_crecimiento_anual, agg_ranking_cooperativas.parquet |
| **Frecuencia de actualización** | Mensual |
| **Fuente** | Calculado — Motor Central (migrado de COLGA/TCOLGA/COLGM/TCOLGM, script R) |

### `CARTERA_EN_RIESGO` — Cartera en Riesgo (CER)

| Campo | Valor |
|---|---|
| **Nombre** | Cartera en Riesgo (CER) |
| **Descripción** | Suma de la cartera vencida y que no devenga intereses en todas las líneas de negocio (comercial, consumo, inmobiliaria, microcrédito) y modalidades (prioritario, productivo, ordinario). |
| **Fórmula** | Σ cuentas de cartera vencida / que no devenga intereses (36 cuentas de 4 dígitos) |
| **Variables** | balance.codigo∈CODIGOS_CARTERA_EN_RIESGO (36 códigos, ver analytics/crecimiento.py) |
| **Interpretación financiera** | Medida en dólares (no ratio) de exposición crediticia deteriorada — complementa a MOR_TOT (%) con la magnitud absoluta. |
| **Rango esperado** | Variable según tamaño de la institución |
| **Módulo** | `analytics.crecimiento.calcular_cartera_en_riesgo` |
| **Dependencias** | utils.data_loader.cargar_balance_por_codigos, balance.parquet |
| **Frecuencia de actualización** | Mensual |
| **Fuente** | Calculado — Motor Central (migrado de CER, script R) |

### `SCORE_FINANCIERO_INTEGRAL` — Score Financiero Integral

| Campo | Valor |
|---|---|
| **Nombre** | Score Financiero Integral |
| **Descripción** | Índice compuesto 0-100 de salud financiera general, combinando seis dimensiones con igual ponderación. |
| **Fórmula** | promedio simple de percentiles orientados: liquidez(LIQ) + solvencia(SUF_PAT) + rentabilidad(ROE) + cobertura(COB_TOT) + morosidad(MOR_TOT, invertido) + crecimiento(cartera YoY) |
| **Variables** | indicadores.parquet (LIQ, SUF_PAT, ROE, COB_TOT, MOR_TOT); crecimiento_colocaciones |
| **Interpretación financiera** | 100 = mejor desempeño relativo dentro del universo comparado (sistema o segmento) en la fecha de corte. Es un ranking relativo, no una nota absoluta — no es comparable entre fechas distintas ni entre universos distintos (Todos vs. un segmento). |
| **Rango esperado** | 0-100 por construcción (percentiles); en la práctica P25≈38, P75≈63 (jun-2026) |
| **Módulo** | `analytics.indices_ejecutivos.calcular_score_financiero_integral` |
| **Dependencias** | analytics.camels_score._percentil_orientado, analytics.crecimiento.crecimiento_colocaciones, indicadores.parquet |
| **Frecuencia de actualización** | Mensual |
| **Fuente** | Nuevo — no existe en el script R (índice de segundo nivel pedido en la ampliación) |

### `INDICE_VULNERABILIDAD` — Índice de Vulnerabilidad

| Campo | Valor |
|---|---|
| **Nombre** | Índice de Vulnerabilidad |
| **Descripción** | Índice compuesto 0-100 de fragilidad financiera: 100 = más vulnerable dentro del universo comparado. |
| **Fórmula** | percentil del z-score promedio de: MOR_TOT, VULN_PAT, CART_IMPR_PAT, y la brecha (ROE oficial − ROE ajustado) |
| **Variables** | indicadores.parquet (MOR_TOT, VULN_PAT, CART_IMPR_PAT, ROE); ROE_AJUSTADO |
| **Interpretación financiera** | La brecha de ROE es la señal nueva (no está en el R ni la publica la SEPS por separado): una brecha grande indica que la rentabilidad reportada depende de ingresos no recurrentes, no de la operación central. |
| **Rango esperado** | 0-100 por construcción; distribución centrada en 50 por diseño (z-score) |
| **Módulo** | `analytics.indices_ejecutivos.calcular_indice_vulnerabilidad` |
| **Dependencias** | analytics.rentabilidad.calcular_roe_ajustado, indicadores.parquet, pyg.parquet, agg_ranking_cooperativas.parquet |
| **Frecuencia de actualización** | Mensual |
| **Fuente** | Nuevo — no existe en el script R |

### `INDICE_FORTALEZA` — Índice de Fortaleza

| Campo | Valor |
|---|---|
| **Nombre** | Índice de Fortaleza |
| **Descripción** | Índice compuesto 0-100: 100 = institución más sólida dentro del universo comparado. |
| **Fórmula** | promedio simple de percentiles orientados: SUF_PAT + LIQ + COB_TOT + ROA + ROE + crecimiento de activos YoY |
| **Variables** | indicadores.parquet (SUF_PAT, LIQ, COB_TOT, ROA, ROE); crecimiento_activos |
| **Interpretación financiera** | Similar en construcción al Score Financiero Integral pero con foco en capital, liquidez y cobertura (defensivo) más crecimiento — no morosidad, que es el foco del Índice de Vulnerabilidad. |
| **Rango esperado** | 0-100 por construcción; P25≈37, P75≈65 (jun-2026) |
| **Módulo** | `analytics.indices_ejecutivos.calcular_indice_fortaleza` |
| **Dependencias** | analytics.camels_score._percentil_orientado, analytics.crecimiento.crecimiento_activos, indicadores.parquet |
| **Frecuencia de actualización** | Mensual |
| **Fuente** | Nuevo — no existe en el script R |

### `INDICE_RESILIENCIA` — Índice de Resiliencia

| Campo | Valor |
|---|---|
| **Nombre** | Índice de Resiliencia |
| **Descripción** | Índice compuesto 0-100: capacidad de una institución de soportar un escenario de estrés (por defecto, "Severo"). |
| **Fórmula** | percentil de solvencia_post-shock, con penalización de 20 puntos si queda capital insuficiente y 10 si queda brecha de liquidez |
| **Variables** | Salida de analytics.stress_testing.aplicar_escenario |
| **Interpretación financiera** | Reutiliza el motor de Stress Testing existente en vez de duplicar la mecánica de shock — es "capacidad para soportar escenarios adversos" aplicando el módulo que la plataforma ya tiene para eso. |
| **Rango esperado** | 0-100 por construcción |
| **Módulo** | `analytics.indices_ejecutivos.calcular_indice_resiliencia` |
| **Dependencias** | analytics.stress_testing.construir_panel_balance, analytics.stress_testing.aplicar_escenario, agg_ranking_cooperativas.parquet |
| **Frecuencia de actualización** | Mensual |
| **Fuente** | Nuevo — no existe en el script R |

### `INDICE_ESTABILIDAD` — Índice de Estabilidad

| Campo | Valor |
|---|---|
| **Nombre** | Índice de Estabilidad |
| **Descripción** | Índice compuesto 0-100: promedio de "nivel" (percentil actual) y "consistencia" (baja volatilidad histórica) de liquidez, morosidad y rentabilidad. |
| **Fórmula** | 0.5 × percentil(LIQ, MOR_TOT invertido, ROE en la fecha de corte) + 0.5 × percentil(1/coef._variación de esos mismos indicadores en los últimos 12 meses) |
| **Variables** | indicadores.parquet (LIQ, MOR_TOT, ROE), ventana de 12 meses |
| **Interpretación financiera** | Diferencia deliberada frente a Fortaleza/Score Integral (que solo miran el corte actual): una cooperativa cuya morosidad oscila mucho mes a mes es menos "estable" que otra con el mismo nivel promedio pero consistente. |
| **Rango esperado** | 0-100 por construcción; P25≈39, P75≈61 (jun-2026) |
| **Módulo** | `analytics.indices_ejecutivos.calcular_indice_estabilidad` |
| **Dependencias** | analytics.camels_score._percentil_orientado, indicadores.parquet (12 meses de historia) |
| **Frecuencia de actualización** | Mensual |
| **Fuente** | Nuevo — no existe en el script R |

### `INDICE_RIESGO_INTEGRAL` — Índice de Riesgo Integral

| Campo | Valor |
|---|---|
| **Nombre** | Índice de Riesgo Integral |
| **Descripción** | Índice compuesto 0-100 (100 = mejor / menor riesgo) que combina Score Financiero Integral, Índice de Vulnerabilidad y alertas activas, clasificado en 7 bandas. |
| **Fórmula** | 0.5 × score_financiero_integral + 0.3 × (100 − indice_vulnerabilidad) + 0.2 × (100 − alertas_normalizado) |
| **Variables** | Salidas de calcular_score_financiero_integral, calcular_indice_vulnerabilidad, evaluar_alertas |
| **Interpretación financiera** | Clasificación en 7 bandas: Excelente (≥85) / Muy Bueno (≥70) / Bueno (≥55) / Vigilancia (≥40) / Riesgo Medio (≥25) / Riesgo Alto (≥10) / Riesgo Crítico (<10). Ponderaciones documentadas en PESOS_RIESGO_INTEGRAL — ajustables por Riesgos y Estudios sin tocar la estructura del módulo. |
| **Rango esperado** | 0-100 por construcción; observado 30-85 (jun-2026, ningún caso llegó a Riesgo Alto/Crítico en esa fecha) |
| **Módulo** | `analytics.indices_ejecutivos.calcular_indice_riesgo_integral` |
| **Dependencias** | calcular_score_financiero_integral, calcular_indice_vulnerabilidad, analytics.alertas.evaluar_alertas |
| **Frecuencia de actualización** | Mensual |
| **Fuente** | Nuevo — no existe en el script R |

---

*Documento generado automáticamente. Para regenerarlo tras un cambio: `python scripts/generar_documentacion_indicadores.py`.*