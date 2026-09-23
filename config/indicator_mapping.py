# -*- coding: utf-8 -*-
"""
Mapeo de códigos contables e indicadores financieros para cooperativas.
Fuente: Superintendencia de Economía Popular y Solidaria - Catálogo Único de Cuentas
"""

# =============================================================================
# CODIGOS DE BALANCE GENERAL
# =============================================================================

CODIGOS_BALANCE = {
    # ACTIVOS (Código 1)
    'activo_total': '1',
    'fondos_disponibles': '11',
    'operaciones_interbancarias': '12',
    'inversiones': '13',
    'cartera_creditos': '14',
    'deudores_aceptaciones': '15',
    'cuentas_por_cobrar': '16',
    'bienes_arrendamiento': '17',
    'activos_fijos': '18',
    'otros_activos': '19',

    # PASIVOS (Código 2)
    'pasivo_total': '2',
    'obligaciones_publico': '21',
    'operaciones_interbancarias_pas': '22',
    'obligaciones_inmediatas': '23',
    'aceptaciones_circulacion': '24',
    'cuentas_por_pagar': '25',
    'obligaciones_financieras': '26',
    'valores_circulacion': '27',
    'obligaciones_convertibles': '28',
    'otros_pasivos': '29',

    # PATRIMONIO (Código 3)
    'patrimonio': '3',
    'capital_social': '31',
    'prima_descuento': '32',
    'reservas': '33',
    'otros_aportes': '34',
    'superavit_valuaciones': '35',
    'resultados': '36',
}

# Subcuentas importantes de cartera
CODIGOS_CARTERA = {
    'cartera_comercial': '1401',
    'cartera_consumo': '1402',
    'cartera_vivienda': '1403',
    'cartera_microcredito': '1404',
    'cartera_educativo': '1405',
    'cartera_inversion_publica': '1406',
    'cartera_vencida': '1421',
    'provision_cartera': '1499',
}

# =============================================================================
# SEGMENTOS DE COOPERATIVAS
# =============================================================================

SEGMENTOS = {
    'SEGMENTO 1': 'Segmento 1 (>80M activos)',
    'SEGMENTO 2': 'Segmento 2 (20-80M activos)',
    'SEGMENTO 3': 'Segmento 3 (5-20M activos)',
    'SEGMENTO 1 MUTUALISTA': 'Mutualistas',
}

# =============================================================================
# ETIQUETAS AMIGABLES PARA UI
# =============================================================================

ETIQUETAS_BALANCE = {
    '1': 'Total Activos',
    '11': 'Fondos Disponibles',
    '13': 'Inversiones',
    '14': 'Cartera de Créditos',
    '2': 'Total Pasivos',
    '21': 'Depósitos del Público',
    '26': 'Obligaciones Financieras',
    '3': 'Patrimonio',
    '31': 'Capital Social',
}

# =============================================================================
# PALETA DE COLORES POR SEGMENTO
# =============================================================================

COLORES_SEGMENTO = {
    'SEGMENTO 1': '#1f77b4',          # Azul
    'SEGMENTO 2': '#ff7f0e',          # Naranja
    'SEGMENTO 3': '#2ca02c',          # Verde
    'SEGMENTO 1 MUTUALISTA': '#d62728',  # Rojo
}

# =============================================================================
# COLORES PARA COOPERATIVAS (ordenadas por tamaño de activos)
# Top 10: Colores brillantes y saturados
# Top 11-30: Colores medios
# Resto: Colores suaves pero distinguibles
# =============================================================================

COLORES_COOPERATIVAS = {
    # =========================================================================
    # TOP 10 - Colores BRILLANTES y MUY SATURADOS
    # =========================================================================
    'JUVENTUD ECUATORIANA PROGRESISTA LTDA': '#E63946',   # Rojo vibrante
    'JARDIN AZUAYO LTDA': '#F4A261',                      # Naranja cálido
    'ALIANZA DEL VALLE LTDA': '#2A9D8F',                  # Verde azulado
    'POLICIA NACIONAL LTDA': '#264653',                   # Azul petróleo
    '29 DE OCTUBRE LTDA': '#E9C46A',                          # Amarillo dorado
    'Mutualista Pichincha': '#9B5DE5',  # Púrpura brillante
    'COOPROGRESO LTDA': '#00BBF9',                        # Cian eléctrico
    'SAN FRANCISCO LTDA': '#00F5D4',                          # Turquesa neón
    'FERNANDO DAQUILEMA LTDA': '#F15BB5',                 # Rosa fucsia
    'ANDALUCIA LTDA': '#FEE440',                          # Amarillo limón

    # =========================================================================
    # TOP 11-30 - Colores MEDIOS (saturación media-alta)
    # =========================================================================
    'MUSHUC RUNA LTDA': '#7B68EE',                            # Azul slate medio
    'OSCUS LTDA': '#20B2AA',                              # Verde agua
    'DE LA PEQUEÑA EMPRESA DE COTOPAXI LTDA': '#FF6B6B',  # Coral
    'RIOBAMBA LTDA': '#4ECDC4',                               # Turquesa medio
    'DE LA PEQUEÑA EMPRESA BIBLIAN LTDA': '#45B7D1',      # Azul cielo
    'ATUNTAQUI LTDA': '#96CEB4',                          # Verde salvia
    'CHIBULEO LTDA': '#DDA0DD',                           # Ciruela
    'VICENTINA MANUEL ESTEBAN GODOY ORTEGA LTDA': '#F7DC6F',  # Mostaza
    'AMBATO LTDA': '#BB8FCE',                                 # Lavanda
    '23 DE JULIO LTDA': '#85C1E9',                        # Azul bebé
    'TULCAN LTDA': '#F8B500',                             # Ámbar
    'EL SAGRARIO LTDA': '#58D68D',                            # Verde esmeralda
    'DE LA PEQUEÑA EMPRESA DE PASTAZA LTDA': '#EC7063',   # Salmón
    'KULLKI WASI LTDA': '#AF7AC5',                            # Orquídea
    'PABLO MUÑOZ VEGA LTDA': '#5DADE2',                   # Celeste
    'PILAHUIN TIO LTDA': '#F5B041',                       # Naranja suave
    'DE LOS SERVIDORES PUBLICOS DEL MINISTERIO DE EDUCACION Y CULTURA': '#48C9B0',  # Aguamarina
    'Mutualista Azuay': '#D7BDE2',  # Malva
    'SAN JOSE LTDA': '#A3E4D7',                           # Menta
    'ERCO LTDA': '#FAD7A0',                               # Melocotón

    # =========================================================================
    # TOP 31-60 - Colores SECUNDARIOS
    # =========================================================================
    'INDIGENA SAC LTDA': '#7DCEA0',                           # Verde jade
    'COMERCIO LTDA': '#F1948A',                               # Rosa coral
    'SANTA ROSA LTDA': '#85929E',                         # Gris acero
    'ALFONSO JARAMILLO LEON CAJA': '#82E0AA',                 # Verde claro
    'PADRE JULIAN LORENTE LTDA': '#F7C6C7',                   # Rosa pálido
    'CHONE LTDA': '#AED6F1',                                  # Azul hielo
    'LA MERCED LTDA': '#D5F5E3',                          # Verde menta
    'ONCE DE JUNIO LTDA': '#FADBD8',                          # Rosa bebé
    'DE LA PEQUEÑA EMPRESA GUALAQUIZA': '#D6EAF8',            # Azul cielo pálido
    'VIRGEN DEL CISNE': '#E8DAEF',                            # Lila pálido
    'YUYAY LTDA': '#FCF3CF',                                  # Crema
    '15 DE ABRIL LTDA': '#D4EFDF',                            # Verde agua pálido
    'DE LA PEQUEÑA EMPRESA CACPE LOJA LTDA': '#FDEBD0',       # Vainilla
    '9 DE OCTUBRE LTDA': '#E5E8E8',                           # Gris perla
    'CALCETA LTDA': '#F9E79F',                                # Amarillo paja
    'LUCHA CAMPESINA': '#A9DFBF',                             # Verde pastel
    'ACCION IMBABURAPAK LTDA': '#F5B7B1',                     # Melocotón rosado
    'PROVIDA LTDA': '#D2B4DE',                                # Púrpura pálido
    'DE LA PEQUEÑA EMPRESA CACPE ZAMORA CHINCHIPE LTDA.': '#AEB6BF',  # Gris azulado
    'DE LA PEQUEÑA EMPRESA CACPE YANTZAZA LTDA': '#A2D9CE',   # Turquesa pálido
    'MANANTIAL DE ORO LTDA': '#F8C471',                       # Naranja claro
    'SAN FRANCISCO DE ASIS LTDA': '#C39BD3',                  # Violeta
    'JUAN PIO DE MORA LTDA': '#7FB3D5',                       # Azul acero
    'LUZ DEL VALLE': '#F7DC6F',                               # Dorado claro
    'GUARANDA LTDA': '#76D7C4',                               # Turquesa claro
    'SAN ANTONIO LTDA LOS RIOS': '#F0B27A',                   # Mandarina
    'COOPAC AUSTRO LTDA': '#BB8FCE',                          # Morado suave
    'CREDI YA LTDA': '#73C6B6',                               # Verde mar
    'Mutualista Ambato': '#F1C40F',  # Oro
    'MAQUITA CUSHUN LTDA': '#E59866',                         # Terracota

    # =========================================================================
    # TOP 61-100 - Colores TERCIARIOS
    # =========================================================================
    '4 DE OCTUBRE': '#85C1E9',
    'PREVISION AHORRO Y DESAROLLO LTDA': '#A3E4D7',
    'SANTA ISABEL LTDA': '#D7BDE2',
    'ALIANZA MINAS LTDA': '#FAD7A0',
    'VENCEDORES LTDA': '#A9CCE3',
    'PEDRO MONCAYO LTDA': '#F9E79F',
    'VISION DE LOS ANDES VIS ANDES': '#D5F5E3',
    'HUANCAVILCA LTDA': '#FADBD8',
    'Mutualista Imbabura': '#E8DAEF',
    'ARTESANOS LTDA': '#D6EAF8',
    'SAN ANTONIO LTDA - IMBABURA': '#FCF3CF',
    'TEXTIL 14 DE MARZO': '#FDEBD0',
    'MINGA LTDA': '#D4EFDF',
    'SISA': '#F5CBA7',
    'MUJERES UNIDAS TANTANAKUSHKA WARMIKUNAPAC': '#D2B4DE',
    'SANTA ANA LTDA': '#AEB6BF',
    'EDUCADORES DEL AZUAY LTDA': '#A2D9CE',
    'EDUCADORES TULCAN LTDA': '#F8C471',
    'CRECER WIÑARI LTDA': '#C39BD3',
    'CREDIL LTDA': '#7FB3D5',
    'FASAYÑAN LTDA': '#76D7C4',
    'SUMAK KAWSAY LTDA': '#F0B27A',
    'EDUCADORES DE LOJA - CACEL LTDA.': '#BB8FCE',
    'COTOCOLLAO LTDA': '#73C6B6',
    'LA BENEFICA LTDA': '#E59866',
    'ANDINA LTDA': '#82E0AA',
    'CORPORACION CENTRO LTDA': '#F7C6C7',
    'FINANZAS CORPORATIVAS LTDA': '#AED6F1',
    'PUELLARO LTDA': '#D5F5E3',
    'SUMAK SAMY LTDA': '#FADBD8',
    'SEÑOR DE GIRON': '#D6EAF8',
    'UNION EL EJIDO': '#E8DAEF',
    'MAQUITA CUSHUNCHIC LTDA': '#FCF3CF',
    'EDUCADORES DE CHIMBORAZO LTDA': '#D4EFDF',
    'MARCABELI LTDA': '#FDEBD0',
    'TENA LTDA': '#F9E79F',
    'HUAICANA LTDA': '#A9DFBF',
    'PUSHAK RUNA LTDA': '#F5B7B1',
    'SAN GABRIEL LTDA': '#D2B4DE',
    'SAN MIGUEL DE LOS BANCOS LTDA': '#AEB6BF',

    # =========================================================================
    # TOP 101-150 - Colores CUATERNARIOS
    # =========================================================================
    'ECUACREDITOS LTDA': '#A2D9CE',
    '16 DE JULIO LTDA': '#F8C471',
    'POLITECNICA LTDA': '#C39BD3',
    'KISAPINCHA LTDA': '#7FB3D5',
    'FONDO PARA EL DESARROLLO Y LA VIDA': '#76D7C4',
    'CREDIAMIGO LTDA': '#F0B27A',
    'ACCION TUNGURAHUA LTDA': '#BB8FCE',
    'MULTIEMPRESARIAL': '#73C6B6',
    'EDUCADORES DE TUNGURAHUA LTDA': '#E59866',
    'INTERANDINA': '#82E0AA',
    'UNIBLOCK Y SERVICIOS LTDA': '#F7C6C7',
    'IMBABURA IMBACOOP LTDA': '#AED6F1',
    'INDIGENAS GALAPAGOS LTDA': '#D5F5E3',
    'OCCIDENTAL': '#FADBD8',
    'FINANCREDIT LTDA': '#D6EAF8',
    'FUTURO LAMANENSE': '#E8DAEF',
    'MICROEMPRESARIAL SUCRE': '#FCF3CF',
    'SAN MIGUEL DE PALLATANGA': '#D4EFDF',
    'LAS NAVES LTDA': '#FDEBD0',
    'GAÑANSOL LTDA': '#F9E79F',
    'HERMES GAIBOR VERDESOTO': '#A9DFBF',
    'COCA LTDA': '#F5B7B1',
    'COORAMBATO LTDA': '#D2B4DE',
    'UNIDAD Y PROGRESO': '#AEB6BF',
    'SAN JUAN DE COTOGCHOA': '#A2D9CE',
    'DE INDIGENAS CHUCHUQUI LTDA': '#F8C471',
    'CAÑAR LTDA': '#C39BD3',
    'DE LA MICROEMPRESA FORTUNA': '#7FB3D5',
    'SAN MARTIN DE TISALEO LTDA': '#76D7C4',
    'SANTA ANITA LTDA': '#F0B27A',
    'INTELIGENCIA DE NEGOCIOS LTDA': '#BB8FCE',
    '15 DE AGOSTO DE PILACOTO': '#73C6B6',
    'LA DOLOROSA LTDA': '#E59866',
    'FOCLA': '#82E0AA',
    'MIGRANTES DEL ECUADOR LTDA': '#F7C6C7',
    'ECUAFUTURO LTDA': '#AED6F1',
    'NUEVA ESPERANZA LTDA': '#D5F5E3',
    'LOS ANDES LATINOS LTDA': '#FADBD8',
    'CREDIAMBATO LTDA': '#D6EAF8',
    'METROPOLIS LTDA': '#E8DAEF',
    'CREDIMAS': '#FCF3CF',
    'DEL MAGISTERIO DE PICHINCHA': '#D4EFDF',
    'CHUNCHI LTDA': '#FDEBD0',
    'RURAL SIERRA NORTE': '#F9E79F',
    'CREDI FACIL LTDA': '#A9DFBF',
    'CRISTO REY': '#F5B7B1',
    'SIMIATUG LTDA': '#D2B4DE',
    '13 DE ABRIL': '#AEB6BF',
    'SOL DE LOS ANDES LTDA CHIMBORAZO': '#A2D9CE',
    'EDUCADORES DE PASTAZA LTDA': '#F8C471',

    # =========================================================================
    # TOP 151-200+ - Colores QUINARIOS (ciclo de paleta suave)
    # =========================================================================
    'COORCOTOPAXI LTDA': '#C39BD3',
    'SAN MIGUEL LTDA': '#7FB3D5',
    'ILINIZA LTDA': '#76D7C4',
    'ANGAHUANA': '#F0B27A',
    'CAMPESINA COOPAC': '#BB8FCE',
    'PUJILI LTDA': '#73C6B6',
    'SALINAS LTDA': '#E59866',
    'SAN JORGE LTDA': '#82E0AA',
    'ABDON CALDERON LTDA': '#F7C6C7',
    'GRUPO DIFARE': '#AED6F1',
    'LA FLORESTA LTDA': '#D5F5E3',
    'SAN CRISTOBAL LTDA': '#FADBD8',
    'UNIOTAVALO LTDA': '#D6EAF8',
    'EMPRENDEDORES COOPEMPRENDER LTDA': '#E8DAEF',
    'GONZANAMA': '#FCF3CF',
    'SAN MIGUEL DE SIGCHOS': '#D4EFDF',
    'EL MOLINO LTDA': '#FDEBD0',
    'PRODUCCION AHORRO INVERSION SERVICIO PAIS LTDA': '#F9E79F',
    'JUVENTUD UNIDA LTDA': '#A9DFBF',
    'DEL AZUAY': '#F5B7B1',
    'SALITRE LTDA': '#D2B4DE',
    'ORDEN Y SEGURIDAD "OYS"': '#AEB6BF',
    'JADAN': '#A2D9CE',
    'MAGISTERIO MANABITA LTDA': '#F8C471',
    'ANTORCHA LTDA': '#C39BD3',
    'SUMAC LLACTA LTDA': '#7FB3D5',
    'CORPUCOOP LTDA': '#76D7C4',
    'ETAPA': '#F0B27A',
    'UNIVERSIDAD CATOLICA DEL ECUADOR': '#BB8FCE',
    'BASE DE TAURA': '#73C6B6',
    'SAN PEDRO LTDA': '#E59866',
    'CACPE CELICA': '#82E0AA',
    'INDIGENA SAC PILLARO LTDA': '#F7C6C7',
    'ESPERANZA DEL FUTURO LTDA': '#AED6F1',
    'EDUCADORES Y ASOCIADOS ZAMORA CHINCHIPE': '#D5F5E3',
    'PICHINCHA LTDA': '#FADBD8',
    'SOLIDARIDAD, EMPRENDIMIENTO Y COOPERACION': '#D6EAF8',
    'PUCARA LTDA': '#E8DAEF',
    'SARAGUROS': '#FCF3CF',
    'CIUDAD DE ZAMORA': '#D4EFDF',
    'DE LA CAMARA DE COMERCIO DE GONZANAMA': '#FDEBD0',
    'SAN MARCOS': '#F9E79F',
    'METROPOLITANA LTDA': '#A9DFBF',
    '17 DE MARZO LTDA': '#F5B7B1',
    'DE LOS EMPLEADOS JUBILADOS Y EX-EMPLEADOS DEL BANCO CENTRAL DEL ECUADOR': '#D2B4DE',
    'SIDETAMC': '#AEB6BF',
    'DR CORNELIO SAENZ VERA LTDA': '#A2D9CE',
    'VILCABAMBA CACVIL': '#F8C471',
    'AGRICOLA JUNIN': '#C39BD3',
    '16 DE JUNIO': '#7FB3D5',
    'CIUDAD DE QUITO': '#76D7C4',
    'LA NUESTRA LTDA': '#F0B27A',
    'CAMARA DE COMERCIO DE SANTO DOMINGO': '#BB8FCE',
}


def obtener_color_cooperativa(cooperativa: str) -> str:
    """Retorna el color asignado a una cooperativa."""
    return COLORES_COOPERATIVAS.get(cooperativa, '#636363')


def obtener_color_segmento(segmento: str) -> str:
    """Retorna el color asignado a un segmento."""
    return COLORES_SEGMENTO.get(segmento, '#636363')


# =============================================================================
# INDICADORES CAMEL - Agrupación para UI
# =============================================================================

GRUPOS_INDICADORES = {
    'C - Capital': [
        'SUF_PAT',
        'VULN_PAT',
        'CART_IMPR_PAT',
        'FK',
        'FI',
        'CAP_NETO',
    ],
    'A - Calidad de Activos': [
        'ACT_IMPR',
        'ACT_PROD',
        'AP_PC',
        'CART_REF',
        'CART_REEST',
        'CART_VENCER',
    ],
    'A - Morosidad por Cartera': [
        'MOR_TOT',
        'MOR_CONS',
        'MOR_INMOB',
        'MOR_MICRO',
        'MOR_PROD',
        'MOR_VIV_IP',
        'MOR_EDU',
    ],
    'A - Cobertura por Cartera': [
        'COB_TOT',
        'COB_CONS',
        'COB_INMOB',
        'COB_MICRO',
        'COB_PROD',
        'COB_VIV_IP',
        'COB_EDU',
    ],
    'M - Management y Eficiencia': [
        'GO_ACT',
        'GO_MNF',
        'GP_ACT',
    ],
    'E - Earnings (Rentabilidad)': [
        'ROE',
        'ROA',
        'INTERM',
        'MARG_PAT',
        'MARG_ACT',
        'REND_CONS',
        'REND_INMOB',
        'REND_MICRO',
        'REND_PROD',
        'REND_VIV',
        'REND_EDU',
    ],
    'L - Liquidez': [
        'LIQ',
    ],
}

# Etiquetas amigables para cada indicador CAMEL
ETIQUETAS_INDICADORES = {
    'ACT_IMPR': 'Activos Improductivos / Activos',
    'ACT_PROD': 'Activos Productivos / Activos',
    'AP_PC': 'Activos Productivos / Pasivos con Costo',
    'MOR_TOT': 'Morosidad Total',
    'MOR_CONS': 'Morosidad Consumo',
    'MOR_INMOB': 'Morosidad Inmobiliaria',
    'MOR_MICRO': 'Morosidad Microcrédito',
    'MOR_PROD': 'Morosidad Productivo',
    'MOR_VIV_IP': 'Morosidad Vivienda Interés Público',
    'MOR_EDU': 'Morosidad Educativo',
    'COB_TOT': 'Cobertura Total',
    'COB_CONS': 'Cobertura Consumo',
    'COB_INMOB': 'Cobertura Inmobiliaria',
    'COB_MICRO': 'Cobertura Microcrédito',
    'COB_PROD': 'Cobertura Productivo',
    'COB_VIV_IP': 'Cobertura Vivienda Interés Público',
    'COB_EDU': 'Cobertura Educativo',
    'GO_ACT': 'Gastos de Operación / Activo Promedio',
    'GO_MNF': 'Gastos de Operación / Margen Financiero',
    'GP_ACT': 'Gastos de Personal / Activo Promedio',
    'ROE': 'ROE',
    'ROA': 'ROA',
    'INTERM': 'Intermediación Financiera',
    'MARG_PAT': 'Margen de Intermediación / Patrimonio',
    'MARG_ACT': 'Margen de Intermediación / Activo',
    'REND_CONS': 'Rendimiento Cartera Consumo',
    'REND_INMOB': 'Rendimiento Cartera Inmobiliaria',
    'REND_MICRO': 'Rendimiento Cartera Microcrédito',
    'REND_PROD': 'Rendimiento Cartera Productivo',
    'REND_VIV': 'Rendimiento Cartera Vivienda IP',
    'REND_EDU': 'Rendimiento Cartera Educativo',
    'LIQ': 'Fondos Disponibles / Depósitos CP',
    'VULN_PAT': 'Cart. Improd. Descubierta / Patrimonio',
    'CART_IMPR_PAT': 'Cartera Improductiva / Patrimonio',
    'FK': 'FK',
    'FI': 'FI',
    'CAP_NETO': 'Índice de Capitalización Neto',
    'SUF_PAT': 'Suficiencia Patrimonial',
    'CART_REF': 'Cartera de Créditos Refinanciada',
    'CART_REEST': 'Cartera de Créditos Reestructurada',
    'CART_VENCER': 'Cartera por Vencer Total',
}

# Escalas de colores para heatmap
ESCALAS_COLORES_HEATMAP = {
    # Mayor es mejor (verde = alto)
    'ACT_PROD': 'RdYlGn',
    'AP_PC': 'RdYlGn',
    'ROE': 'RdYlGn',
    'ROA': 'RdYlGn',
    'LIQ': 'RdYlGn',
    'COB_TOT': 'RdYlGn', 'COB_CONS': 'RdYlGn', 'COB_INMOB': 'RdYlGn',
    'COB_MICRO': 'RdYlGn', 'COB_PROD': 'RdYlGn', 'COB_VIV_IP': 'RdYlGn',
    'COB_EDU': 'RdYlGn',
    'CAP_NETO': 'RdYlGn',
    'SUF_PAT': 'RdYlGn',
    'CART_VENCER': 'RdYlGn',
    'MARG_PAT': 'RdYlGn',
    'MARG_ACT': 'RdYlGn',
    # Menor es mejor (rojo = alto)
    'ACT_IMPR': 'RdYlGn_r',
    'CART_REF': 'RdYlGn_r',
    'CART_REEST': 'RdYlGn_r',
    'MOR_TOT': 'RdYlGn_r', 'MOR_CONS': 'RdYlGn_r', 'MOR_INMOB': 'RdYlGn_r',
    'MOR_MICRO': 'RdYlGn_r', 'MOR_PROD': 'RdYlGn_r', 'MOR_VIV_IP': 'RdYlGn_r',
    'MOR_EDU': 'RdYlGn_r',
    'GO_ACT': 'RdYlGn_r',
    'GO_MNF': 'RdYlGn_r',
    'GP_ACT': 'RdYlGn_r',
    'VULN_PAT': 'RdYlGn_r',
    'CART_IMPR_PAT': 'RdYlGn_r',
    # Neutral (informativos: sin una dirección "mejor/peor" única en la metodología vigente)
    'FK': 'Blues',
    'FI': 'Blues',
    'INTERM': 'Blues',
    'REND_CONS': 'Blues', 'REND_INMOB': 'Blues', 'REND_MICRO': 'Blues',
    'REND_PROD': 'Blues', 'REND_VIV': 'Blues', 'REND_EDU': 'Blues',
}

# Rangos de valores para heatmap (en porcentaje)
# Basados en análisis de percentiles P5-P95 de cooperativas ecuatorianas
# Rangos similares a bancos donde aplica, ajustados por distribución real
RANGOS_HEATMAP = {
    # C - Capital
    'VULN_PAT': [0, 60],
    'CART_IMPR_PAT': [0, 80],
    'FK': [0, 30],
    'FI': [100, 130],
    'CAP_NETO': [0, 25],
    'SUF_PAT': [0, 300],  # P50≈230%, P95 distorsionado por outliers de instituciones muy pequeñas

    # A - Calidad de Activos
    'ACT_IMPR': [0, 25],
    'ACT_PROD': [75, 100],
    'AP_PC': [90, 130],
    'CART_REF': [0, 30],      # P50≈6.8%, P95≈23.5%
    'CART_REEST': [0, 35],    # P50≈12.8%, P95≈32%
    'CART_VENCER': [0, 25],   # P50≈16.6%, P95≈21.5%

    # A - Morosidad por Cartera
    'MOR_TOT': [0, 15],
    'MOR_CONS': [0, 15],
    'MOR_INMOB': [0, 15],
    'MOR_MICRO': [0, 15],
    'MOR_PROD': [0, 15],
    'MOR_VIV_IP': [0, 15],
    'MOR_EDU': [0, 15],

    # A - Cobertura por Cartera
    'COB_TOT': [0, 250],
    'COB_CONS': [0, 200],
    'COB_INMOB': [0, 200],
    'COB_MICRO': [0, 200],
    'COB_PROD': [0, 200],
    'COB_VIV_IP': [0, 200],
    'COB_EDU': [0, 200],

    # M - Management y Eficiencia
    'GO_ACT': [0, 10],
    'GO_MNF': [75, 150],
    'GP_ACT': [0, 5],

    # E - Earnings (Rentabilidad)
    'ROE': [-5, 15],
    'ROA': [-1, 3],
    'INTERM': [50, 200],       # P50≈103%, P95≈181%
    'MARG_PAT': [-30, 20],     # P5≈-25.7%, P50≈0.6%, P95≈13.9%
    'MARG_ACT': [-5, 5],       # P5≈-3.4%, P50≈0.1%, P95≈2.5%
    'REND_CONS': [0, 20],      # P50≈14.9%, P95≈16.8%
    'REND_INMOB': [0, 15],     # P50≈8.3%, P95≈11.1%
    'REND_MICRO': [0, 25],     # P50≈17.8%, P95≈22.3%
    'REND_PROD': [0, 15],      # P95≈11.1%, mediana 0 (pocas cooperativas con esta línea)
    'REND_VIV': [0, 10],       # línea de negocio poco común en el sistema
    'REND_EDU': [0, 10],       # línea de negocio poco común en el sistema

    # L - Liquidez
    'LIQ': [10, 50],
}
