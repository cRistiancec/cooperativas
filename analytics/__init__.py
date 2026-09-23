# -*- coding: utf-8 -*-
"""
Capa de analítica de riesgos del RADAR COOPERATIVO ECUADOR.

Cada submódulo implementa una familia de cálculos de riesgo prudencial,
construidos exclusivamente sobre los datos oficiales ya existentes en
`master_data/` (balance, PyG e indicadores CAMEL de la SEPS). Ningún
submódulo inventa datos: donde la métrica clásica requiere información que
el proyecto no tiene (p. ej. datos de crédito a nivel de operación para
matrices de transición, o exposiciones interbancarias para redes de
contagio), la función o la página lo declara explícitamente.
"""
