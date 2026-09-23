# CHECKLIST DE PRODUCCIÓN — RADAR COOPERATIVO ECUADOR

Cada ítem fue verificado mediante ejecución real (no asumido). Detalle completo y evidencia en `AUDITORIA_FINAL.md`.

```
Arquitectura                  ✅   Rutas relativas, capas verificadas, sin notebooks
Dependencias                  ✅   pip check: sin conflictos; kaleido no usado eliminado
Configuración                 ✅   config.toml corregido (CORS/XSRF, file watcher)
Compilación                   ✅   py_compile: 0 errores en todo el proyecto
Calidad estática (pyflakes)   ✅   0 imports muertos / variables sin usar (17 corregidos)
Inicio Streamlit              ✅   "You can now view..." confirmado, causa de cierres corregida
Navegación                    ✅   15/16 páginas OK con AppTest · 1/16 con nota de memoria (ver abajo)
Gráficos                      ✅   Plotly verificado presente (no solo "sin error")
KPIs                          ✅   Verificado contenido real en Panorama
Filtros                       ✅   Interacción real probada (segmento, escenario)
Exportaciones                 ✅   PNG vía Plotly.js (cliente, no depende de kaleido)
Datos                         ✅   Todos los Parquet/JSON existen, rutas relativas, metadata válido
CSS                           ✅   Carga vía ui/theme.py, sin errores en ninguna página
Performance                   ✅   Predicate pushdown aplicado: -80% memoria en Riesgo de Crédito
Memoria                       ⚠️   Balance General requiere ~2GB (detalle contable completo); ver nota
CPU                           ✅   <2% en idle, medido con el servidor corriendo
Logging                       ✅   logs/app.log, error.log, performance.log generando contenido real
Seguridad                     ✅   Sin secretos hardcodeados, sin path traversal, sin file_uploader
Puerto 8501 (esta sesión)      ⚠️   Terminado por agente externo de Codespaces; ver nota
Puerto (alternativo, 8700)     ✅   Health 200 sostenido >2min, 16 páginas recorridas sin error
Browser                       ✅   Local/Network/External URL responden (curl 200); pública 302 (auth)
Codespaces                    ⚠️   Causa raíz confirmada con strace (SIGTERM externo); ver nota
Deploy                        ✅   requirements.txt limpio, sin rutas absolutas, listo para Cloud
Producción                    ⚠️   Ver notas de Memoria y Puerto 8501 — código y config no son la causa
```

## Nota sobre Puerto 8501 / Codespaces (afecta las filas "Puerto 8501", "Codespaces" y parte de "Producción")

**Puerto 8501 / Codespaces (esta sesión):** con `strace -f -e trace=signal`, se capturó la señal exacta
que apaga el servidor en el puerto 8501: `SIGTERM {si_code=SI_USER, si_pid=0, si_uid=61876}` — enviada
deliberadamente por un proceso **fuera del namespace de este contenedor** (no es OOM, no es el propio
código, no es el file watcher). Se probó exhaustivamente: comando exacto de `postAttachCommand`,
reintentos inmediatos, con y sin file watcher — el resultado es idéntico siempre en 8501, y **nunca**
ocurre en ningún otro puerto (8600, 8700, verificado repetidamente con horas de diferencia). La causa
más probable es haber terminado por error, al inicio de esta auditoría, el proceso que
`postAttachCommand` había lanzado originalmente al adjuntarse este Codespace, dejando desincronizado
el estado del agente de *port forwarding* para ese puerto específico durante el resto de la sesión.
**Remediación:** reconstruir/reiniciar este Codespace (acción del usuario, no ejecutable desde el
contenedor). Detalle técnico completo en `AUDITORIA_FINAL.md` §5.1.

## Nota sobre Memoria (afecta las filas "Memoria" y parte de "Producción")

**`2_Balance_General.py`:** esta página carga el balance contable completo
(24.169.638 filas) porque su función central (drill-down a nivel de 4-6 dígitos de cualquier cuenta,
cooperativa y mes) no está cubierta por ningún archivo pre-agregado. Se midió un pico de ~1.8-2GB de
RAM y se aplicó la optimización segura disponible (PyArrow `self_destruct`, -17% de pico). **No se
marca con ✅ ciego** porque, en el entorno de este Codespace (memoria compartida con VS Code/Pylance,
1.8-3.6GB disponibles de forma fluctuante), la página no cargó exitosamente el 100% de las veces
durante las pruebas. El resto de la plataforma (15 de 16 páginas, incluyendo la que antes tenía el
mismo problema y ya fue optimizada — Riesgo de Crédito) no presenta esta limitación.

**Acción recomendada antes de considerar esto completamente cerrado:**
1. Medir el pico de RAM real en el entorno de despliegue de destino (Streamlit Cloud u otro) —
   puede diferir de este Codespace compartido.
2. Si el margen resulta insuficiente, aplicar a `2_Balance_General.py` el mismo patrón de
   *predicate pushdown* ya implementado y verificado en `6_Riesgo_Credito.py` (filtrar en la
   lectura del Parquet, no después) — documentado en `AUDITORIA_FINAL.md` §11.

## Resumen de verificación

- **34/34 tests automatizados** pasando (`test_actualizacion`, `test_analytics`, `test_models`, `test_smoke_pages`).
- **`pip check`**: sin conflictos de dependencias.
- **`pyflakes`**: 0 hallazgos tras la limpieza de 17 imports/variables muertas.
- **Arranque real de Streamlit**: causa raíz de cierres inesperados identificada (file watcher +
  actividad concurrente de archivos) y corregida en `.streamlit/config.toml`; verificado estable
  >90s con health 200 sostenido.
- **Optimización de memoria verificada con números reales**: -17% en cargadores generales,
  -80% en el caso específico de Riesgo de Crédito (predicate pushdown).
- **Seguridad**: sin hallazgos (secretos, path traversal, superficie de subida de archivos).

Este checklist y `AUDITORIA_FINAL.md` reflejan el estado verificado el 22 de julio de 2026.
