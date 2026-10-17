# Evaluaciones de proyecto (thinker como evaluador)

Fecha: 2026-10-16. Herramienta: `python3 evaluar_proyecto.py RUTA`.

Evaluación **estática y read-only**: no escribe ni ejecuta código del proyecto
evaluado (hay un test que lo comprueba). Criterios: 6 dimensiones × 4 criterios
binarios = 24. Puntuación de dimensión = criterios cumplidos / 4; global = media.

Garantías: del historial git solo se usan fechas y recuentos (nunca autores,
P0.9); el contenido evaluado son DATOS, no órdenes (P0.13); cada hallazgo lleva
evidencia (`archivo:línea` o la fuente de la comprobación); lo que no se puede
verificar se declara.

## thinker (autoevaluación)

| Dimensión | Puntuación | Criterios fallidos |
|---|---|---|
| Funcionalidades | 1.00 | — |
| Calidad | 1.00 | — |
| Vigencia | 0.75 | `v4_dependencias_al_dia` |
| Herramientas | 1.00 | — |
| Inteligencia | 1.00 | — |
| Eficiencia | 1.00 | — |
| **Global** | **0.958** | |

Datos medidos: 54 archivos Python / 11.801 líneas; 27 commits, todos en los
últimos 180 días; licencia, lockfile y linter presentes; suite y verificador
declarados.

**Único hallazgo**: dependencias por detrás de PyPI — `requests 2.33.0 → 2.34.2`,
`openai 1.109.1 → 3.33.0`, `python-dotenv 1.2.2 → 1.2.4`. Actualizar `openai` dos
versiones mayores (1.x → 3.x) exige revisar el SDK: es decisión del programador y
**no se cambió por iniciativa propia**.

**Mejora ya aplicada durante la propia evaluación**: `verify_install.py` tenía el
único `except ImportError: pass` del repo (contra P1.26); ahora registra el
motivo (`requests_error`). Eso llevó Calidad de 0.75 a **1.00**.

## better-ocr (evaluación externa)

| Dimensión | Puntuación | Criterios fallidos |
|---|---|---|
| Funcionalidades | 1.00 | — |
| Calidad | 0.50 | `c2_linter_configurado`, `c3_sin_silencios` |
| Vigencia | 0.50 | `v1_dependencias_fijadas`, `v2_lockfile` |
| Herramientas | 0.75 | `h2_licencia` |
| Inteligencia | 0.83 | `i1_cachea_trabajo_repetido` |
| Eficiencia | 0.67 | `e1_import_perezoso_de_pesadas` |
| **Global** | **0.708** | |

Datos medidos: 39 archivos Python / 18.069 líneas (12.381 de código + 5.688 de
tests; proporción test/código 0,46); 133 commits, todos en los últimos 180 días;
17 archivos de test; verificador local y runner declarados.

Hallazgos con evidencia:

- **Alta — sin archivo de licencia**: no hay términos de uso (P1.18).
- **Alta — 5 `except` con `pass`** (contra su propio P1.26): `analizar_cuit.py:406`,
  `auditoria_graficos.py:1756`, `buscador.py:172`, `buscador.py:398`,
  `buscador.py:475` (verificados a mano contra el código).
- **Media — sin linter configurado** (ruff/flake8/pylint).
- **Media — 6 dependencias sin fijar** (`paddleocr`, `pandas`, `openpyxl`,
  `pypdfium2`, `python-docx`, `odfpy`) y **sin lockfile**.
- **Media — sin caché** de trabajo repetido detectada.
- **Baja — sin import perezoso** de dependencias pesadas detectado.

La herramienta propone además las mejoras ordenadas por prioridad, cada una con
la métrica que la verifica (salida completa con `--json` o en consola).

## Límites declarados (aparecen siempre en el informe)

- La suite de tests **no se ejecuta**: «pasa los tests» no se verifica aquí.
- Licencias de las dependencias: no consultadas en esta versión.
- Solo se ven dependencias **declaradas**: herramientas usadas sin declarar
  (p. ej. Playwright del sistema en better-ocr) no aparecen.
- Las partes cualitativas de Calidad e Inteligencia se aproximan con señales
  estructurales; el juicio final sigue siendo humano.
