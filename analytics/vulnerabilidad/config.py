"""Configuración del módulo. Todo supuesto metodológico vive aquí (auditable)."""
# indicador -> (signo de vulnerabilidad: +1 si valores altos = más vulnerable)
INDICADORES = {
    "solvencia_proxy": -1,   # patrimonio/activos (proxy; no es el indicador regulatorio de suficiencia patrimonial)
    "liquidez": -1,          # fondos disponibles / depósitos corto plazo (exacto vs SEPS)
    "morosidad": +1,         # cartera improductiva / cartera bruta (exacto vs SEPS)
    "cobertura": -1,         # provisiones / cartera improductiva (exacto vs SEPS)
    "roa": -1,               # ROA anualizado YTD (≈92% exacto vs SEPS)
    "eficiencia": +1,        # gastos de operación / ingresos operativos 12m (no reconciliado)
}
WINSOR = (0.01, 0.99)        # recorte pooled de colas antes de estandarizar
SEGMENTOS = ["SEGMENTO 1", "SEGMENTO 2", "SEGMENTO 3"]
SEMILLA = 20260930
N_PESOS_ALEATORIOS = 500
HORIZONTE_ALERTA_M = 12      # ventana de predicción del evento
CORTE_TEMPORAL = "2023-12-31"  # entrenamiento <= corte; prueba > corte
EVENTOS_CSV = "docs/audit/EVENTOS_ESTADO_JURIDICO_CANDIDATOS.csv"
