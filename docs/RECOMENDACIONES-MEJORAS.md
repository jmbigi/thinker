# Recomendaciones de mejora de thinker

**Fecha:** 2026-10-22, actualizado el **2026-11-04**. **Base inicial:** commit
`6d20a4c`, más las decisiones del programador del 2026-10-25, la release `0.1.15`
publicada y el refuerzo de aserciones del preflight del 2026-10-26.
**Alcance:** recomendaciones abiertas, no una lista de deseos. Cada una nace de
una medición de este repositorio o de la campaña de evaluación externa y lleva
su criterio de aceptación. Lo ya cerrado no se repite como si estuviera
pendiente.

## 1. Resumen ejecutivo

| Prioridad | Recomendación | Por qué ahora | Esfuerzo | Riesgo |
|---|---|---|---|---|
| **Hecho** | R1. [Cerrada 2026-10-22] Actualizar el lock de `openai` y re-verificar la autoevaluación | Lock 3.37.0 con hashes; autoevaluación con red 1.000 | Bajo | Bajo |
| **Hecho** | R11. [Cerrada 2026-10-23] Gate documental `scripts/check_docs.py` | Las cifras de docs derivaban en cada auditoría; ahora fallan si no cuadran | Bajo | Bajo |
| **Hecho** | R12. [Cerrada 2026-10-23] Corpus adversario del evaluador | 4 regresiones de la auditoría (Poetry, locks, prosa/runner) como contrato | Bajo | Bajo |
| **Hecho** | R2. [Cerrada 2026-10-25] Subir la cobertura de `evaluar_proyecto.py` y `preflight.py` | 91% / 93% actual (91% combinado); ramas de error cubiertas | Medio | Bajo |
| **Hecho** | R3. [Cerrada 2026-11-04; decisión C] Medir mutación del evaluador y preflight | Preflight: 967/1016, 49 equivalencias y 0 brechas; evaluador: 4846/5984 histórico, **0 brechas + 125 equivalencias validadas** tras los clústeres anteriores, la deduplicación de E32 y la revalidación por contenido, 0 timeouts. La campaña de 6144 mutantes no aporta tasa global válida | Medio-alto | Medio |
| **Hecho** | R9. [Cerrada 2026-10-24] Publicar 0.1.4 | Publicada en TestPyPI y PyPI; tag `v0.1.4`; 842/842 | Medio | Medio |
| **Hecho** | R4. [Cerrada 2026-10-26, alcance offline] Benchmark de precisión/recall del evaluador | 57 casos/26 criterios con 5 trampas y 1,00/1,00; 3 N/A declaradas (red/PyPI/entrada real) | Medio | Bajo |
| **Hecho** | R5. [Cerrada 2026-10-25, A] Alcance Python explícito y bloqueo de comparabilidad | `cobertura.comparable`; Java/JS no comparable; 2 tests | Alto | Alto |
| **Hecho** | R6. [Cerrada 2026-10-25, C con warnings] Política para silencios deliberados de producción | Marca externa con motivo; warnings en c3/preflight; 5 tests | Bajo | Político |
| **Hecho** | R7. [Cerrada 2026-10-25] Medir calidad de aserciones, no solo tests no-op | `aserciones_debiles` informativo; c5 no cambia | Medio | Bajo |
| **Hecho** | R8. [Cerrada 2026-10-22] Versionar el esquema JSON del informe | `schema_version: 2` y test de contrato | Bajo | Bajo |
| **Hecho** | R10. [Cerrada 2026-10-25] Reportar licencias de dev/opcionales sin mezclarlas con runtime | `licencias_no_runtime` informativo; h5 sigue siendo runtime | Bajo | Bajo |
| **Hecho** | R13. [Cerrada 2026-10-25, B+C] CoVe con verificador barato y descomposición opt-in | 1+1 llamadas; claim compuesto detectado; 28/14 en R4 | Medio | Medio |
| **Hecho** | R14. [Cerrada 2026-10-25, por declaración; B+C piloto] Declarar `credibility`/`confidence` no calibradas | Brier simulado 0,1166; piloto real n=20 Brier 0,0050 y factual real n=30 Brier 0,0044, ambos con IC; sin calibración general | Medio | Bajo |

**Estado de decisiones (2026-10-26; R3 actualizado el 2026-11-04):** R5-A,
R6-C, R13-B/C y R14-B/C implementadas; R3-C **cerrada** (preflight 49: 49
equivalencias y 0 brechas; evaluador **0 brechas + 76 equivalencias validadas**;
0 timeouts). **R4 se cierra por alcance offline**: 26/29 criterios medidos y 3 N/A
declaradas, no una validación global.
R1, R2, R4, R5, R6, R7, R8, R9, R10, R11, R12, R13 y R14 están cerradas.

### 1.1 Decisiones del programador (2026-10-25)

| ID | Decisión | Estado | Siguiente paso |
|---|---|---|---|
| **R5** | **A**: alcance Python explícito y bloqueo de comparabilidad | **Implementada y cerrada** | Hecho: `cobertura.comparable` y tests |
| **R6** | **C con warnings**: estricto para thinker; marca externa con motivo, reportada como warning | **Implementada y cerrada** | Hecho: warnings en c3/preflight |
| **R13** | **B con vía a C**: verificador barato; descomposición después | **B y C implementadas; cerrada** | Hecho: descomposición opt-in |
| **R14** | **B con vía a C**: Brier offline simulado; datos reales después | **B y C (piloto n=20 y factual n=30, con IC); declaración vigente** | Muestra aún pequeña y fácil; no afirmar calibración general |
| **R3** | **C**: test-first, luego triaje; reporte parcial honesto hasta cerrar | **Cerrada**; preflight 49 equivalencias y 0 brechas, evaluador 0 brechas + 125 equivalencias validadas, 0 timeouts | Inventario cerrado; tasas históricas sin recalcular |
| **R4** | Sin decisión de producto; ampliar cobertura | **Cerrada por alcance offline** (57 casos/26 criterios; 3 N/A) | Campaña real con red/PyPI queda opt-in y fuera de alcance |

**No queda ninguna decisión de producto pendiente.** R14 tiene un piloto real
n=20 y un benchmark factual n=30, ambos con intervalo bootstrap; siguen sin
representar una calibración general. R3 queda **cerrada** con 355 candidatos
tratados, 304 detectados, 34 equivalencias conocidas y 17 contextos revisados;
quedan **0 brechas + 125 equivalencias validadas**.

## 2. Estado medido (evidencia de partida)

| Señal | Valor | Cómo se midió |
|---|---:|---|
| Suite completa | **1492/1492** en Linux 3.11.9 (2026-11-07) | `python3 -m unittest discover -s tests -q` |
| CI local (última copia limpia) | **OK** | copia limpia de HEAD; limpieza Python validada del temporal |
| Lint / preflight / docs-check | **0 / 0 / OK** | `ruff check .`, `scripts/preflight.py`, `scripts/check_docs.py` |
| Autoevaluación con red | **1.000** (30/30; 0 N/A) | `python3 evaluar_proyecto.py . --ejecutar-tests --json` |
| Lock `openai` | **3.45.0** con hashes (2026-11-04) | `requirements.lock` |
| Autoevaluación sin red | **1.000** (27/29; N/A `v4`, `h5`) | `python3 evaluar_proyecto.py . --sin-red --json` |
| Cobertura `evaluar_proyecto.py` | **99%** (18/1645 sentencias sin ejecutar) | comando de la sección 8 |
| Cobertura `scripts/preflight.py` | **100%** (0/461) | comando de la sección 8 |
| Mutación global | **95,2%** (3635/3819; 2026-10-24) | `make mutation`; **excluye** evaluador y preflight |
| Mutación preflight | **95,18%** (967/1016; 49 supervivientes, 0 timeouts; 2026-10-26) | `python3 scripts/mutacion.py --objetivo preflight` |
| Mutación evaluador | **80,98%** (4846/5984; 1138 supervivientes: 1131 brechas + 7 equivalencias, 0 timeouts; 2026-10-28) | `python3 scripts/mutacion.py --objetivo evaluar` |
| Paquete actual | **0.1.23** (2026-11-04; publicado en TestPyPI y PyPI) | `pyproject.toml` / `docs/PUBLICACION.md` |

Lectura: el proyecto está sano en tests, CI y cobertura (91% en evaluador y
preflight). La deuda histórica de **mutación** de esos dos módulos (R3) quedó
cerrada el 2026-11-04 con **0 brechas + 125 equivalencias validadas**; las tasas
de la tabla son mediciones históricas, no una tasa global recalculada. R4 se
cerró por alcance offline (26/29; 3 N/A).

## 3. Lo que ya está cerrado (no reabrir sin nueva evidencia)

No se recomienda volver a trabajar en esto; ya tiene tests y evidencia:

- h6 limitado al código del paquete, con `src/`, pyproject/PEP 735, setup.cfg,
  setup.py, requirements anidados, `TYPE_CHECKING`, opcionales y `if __name__`.
- h5 con `license_expression` PEP 639, clasificador OSI y `unverified` cuando
  no hay metadato.
- R2: cobertura del evaluador y preflight al 91% cada uno y 91% combinado,
  con ramas de error cubiertas.
- R10: `licencias_no_runtime` informa dev/opcionales sin tocar el score h5.
- R7: `aserciones_debiles` separa la señal informativa de c5; no marca
  variables, helpers ni property tests.
- c5 sin falsos positivos por helpers, endpoints anidados o property tests; c3
  sin tests ni imports opcionales.
- Perfil de proyecto, criterios N/A, cobertura y plan con evidencia por criterio.
- h4/f1/h7 con `build.sh`, npm/Gradle, comillas simples, `__main__.py` y docs
  `.rst`/`HISTORY`.
- Núcleo de investigación: caché, timeout, CoVe opt-in con verificador separado,
  CRAG, consenso en ToT, routing y fidelidad RAGAS-like ya están documentados e
  implementados según `AGENTS.md` y `docs/ESTADO-2026-10-16.md`.
- Las dos propuestas de `docs/REFERENCIAS-IA.md` aparcadas siguen aparcadas con
  motivo medido: paralelización (agravaría el 429) y DSPy (dependencia y
  campaña). No se reabren en este documento.

## 4. Recomendaciones: estado y acciones

### R1 — Actualizar el lock de `openai` (P1, bajo esfuerzo) — CERRADA 2026-10-22

- **Problema medido:** `v4_dependencias_al_dia` era el único fallo de la
  autoevaluación con red: `openai 3.35.1 → 3.36.0` en la consulta del
  2026-10-21 (durante la revisión PyPI publicó 3.37.0). El lock fijaba 3.35.1
  y el manifiesto permite `<4`.
- **Acción ejecutada:** `make lock` ahora usa `--upgrade` (sin él, uv conserva
  los pines del lock anterior); lock regenerado primero con openai **3.36.1**
  y, al publicarse 3.37.0, de nuevo con **3.37.0**;
  httpx2/httpcore2 2.16.0 y el resto sin cambios. Instalación verificada con
  `python3 -m pip install --require-hashes -r requirements.lock` en Python
  3.12.7; suite y canario de compatibilidad en verde.
- **Criterio de aceptación:** [x] suite en verde (750/750 en Windows 11
  3.12.7/3.14.3; última medición Linux 747/747); [x] autoevaluación con red
  **1.000** (27/27 criterios sin ejecutar tests; 28/28 con
  `--ejecutar-tests`; 2 N/A); [x] `v4` en OK; [x] lock con hashes (3.37.0); [x]
  ninguna otra dependencia cambió sin declararlo.
- **Riesgo:** una versión nueva de openai puede romper la superficie usada. Si
  falla, mantener el lock anterior y documentar la incompatibilidad; no
  maquillar el resultado.

### R2 — Subir la cobertura del evaluador y preflight — CERRADA 2026-10-25

- **Problema medido (histórico):** 90% en `evaluar_proyecto.py` (149/1435 sin
  ejecutar) y 91% en preflight (35/385); 83% total del proyecto. Faltaban
  ramas de error de requisitos, ámbitos de requirements, TOML inválido,
  manifiestos no Python, excepciones y lectura.
- **Acción ejecutada:** tests honestos para esas ramas (`_parsear_requisito`,
  `_ambito_requirements`, fallback de TOML inválido, manifiestos
  npm/Gradle/Maven/Go/Cargo/tox/nox, tuplas de excepciones y `OSError` de
  lectura). No se persiguió el 100% ni se añadieron tests triviales.
- **Evidencia:** en el cierre, `evaluar_proyecto.py` **91%** (130/1466 sin
  ejecutar), preflight **91%** (35/385), **91% combinado**. Tras R5/R6 el
  módulo crece a 1571 sentencias y sigue en **91%** (145/1571); suite
  **902/902**, ruff 0. Comando: el de la sección 8.
- **Criterio de aceptación:** [x] ≥90% en cada archivo; [x] ≥90% combinado;
  [x] ramas de error cubiertas o declaradas; [x] suite en verde; [x] comando
  reproducible documentado.
- **Riesgo:** bajo; los tests comprueban comportamiento, no solo ejecutan
  líneas.

### R3 — Medir mutación del evaluador y preflight — CERRADA 2026-11-04 (decisión C)

- **Decisión 2026-10-25: C.** Test-first, luego triaje; reporte parcial con el
  número de no triados; no cerrar hasta 0 sin tests y 0 supervivientes sin
  triaje. Ejecutada y cerrada con **0 brechas + 125 equivalencias validadas**;
  el historial conserva las cifras de cada campaña en su fecha.
- **Problema medido:** `make mutation` mide el núcleo, pero excluye
  `evaluar_proyecto.py` y `scripts/preflight.py`. El 95,2% actual **no cubre**
  el código del evaluador ni el de preflight.
- **Acción ejecutada:** `scripts/mutacion.py` empaqueta las campañas
  `--objetivo preflight|evaluar` en copia limpia, con la selección de tests
  correspondiente y exclusión del test que evalúa el repo real (no aplica al
  sandbox). El arnés copia sin `.env`/`.git`, usa `also_copy` para
  `evidence.py` y `scripts/` y suma 3 tests.
- **Preflight (2026-10-26, lote 6):** **1016 mutantes, 967 muertos, 49
  supervivientes, 0 sin tests, 0 timeouts, 0 sospechosos**; tasa bruta
  **95,18%** (antes 696/1015, 68,57%; 319 supervivientes). El lote añadió
  aserciones exactas del contrato del hallazgo, CLI, alias de asyncio,
  umbrales de duplicados, manifiestos, `modulos_locales` y archivos ilegibles.
  Además corrigió un defecto real: `_es_main` aceptaba `__name__ !=
  "__main__"` como guardia no runtime; ahora exige `ast.Eq`. El triaje
  semántico de `docs/TRIAGE-EQUIVALENCIAS.md` demuestra **49 equivalencias**
  y **0 brechas reales**: los 6 `encoding=None` se mataron con locale C en
  proceso, `lineno` con un byte nulo y el `continue`/`break` restante se
  demostró equivalente.
- **Evaluador (2026-10-26, batch r3c):** **5984 mutantes, 4665 muertos,
  1319 supervivientes, 0 sin tests, 0 timeouts**, 0 sospechosos; tasa bruta
  **77,96%** (4665/5984). El contrato exacto de `informe_texto` y
  `detectar_comando_tests`, junto con los tests de `--sin-red` y `cwd`, mató
  504 mutantes; el contrato de `evaluar_herramientas`/`evaluar_calidad` mató
  134 más; el de `evaluar_vigencia`/`_dependencias_pyproject` mató 144;
  eficiencia/funcionalidades y ramas nuevas, 142; silencios/h5/h6/vigencia
  con red y licencias PyPI, 176; parser/runner/inteligencia, 77 más. La
  parsers/linter, 112; main/síntesis/eficiencia, 115 más. La campaña
  mantiene 0 timeouts.
- **Triaje de inventario (2026-10-26):** **1368/1368** casos con categoría:
  **1319 brechas de aserción** (0 preflight + 1319 evaluador), **0 sin
  cobertura**, **49 equivalencias demostradas** y **0 timeouts**. Detalle y
  razones en `docs/TRIAGE-R3.md` y `docs/TRIAGE-EQUIVALENCIAS.md`. Aquella no
  era una tasa limpia: los 1319 casos seguían sin matar en esa medición.
- **Re-medición oficial (2026-10-28, batch r3c2):** **5984 mutantes, 4681
  muertos, 1303 supervivientes, 0 sin tests, 0 timeouts**, 0 sospechosos; tasa
  bruta **78,23%**. El test de contrato exacto de `_verificar_test` (Hallazgo
  138) mata sus 16 supervivientes (16 → 0). Campaña y triaje en
  `build/mut-eval-r3c2` y `build/triaje-eval-r3c2.json`.
- **Re-medición oficial (2026-10-28, batch r3c3):** **5984 mutantes, 4764
  muertos, 1220 supervivientes, 0 sin tests, 0 timeouts**, 0 sospechosos; tasa
  bruta **79,61%**. El contrato exacto de `evaluar_vigencia` (Hallazgo 139:
  10 tests con `a_dict()` completo, repo git temporal y PyPI simulada) mata
  80 de sus 82 supervivientes (82 → 2); los 2 restantes son equivalencias
  demostradas (E1: default falsy de `dict.get`). Campaña y triaje conservados
  en `build/mut-eval-r3c3` y `build/triaje-eval-r3c3.json`.
- **Re-medición oficial (2026-10-28, batch r3c4):** **5984 mutantes, 4846
  muertos, 1138 supervivientes, 0 sin tests, 0 timeouts**, 0 sospechosos; tasa
  bruta **80,98%**. El contrato exacto de `evaluar` (Hallazgo 140: 16 tests en
  `TestEvaluarContrato`, con los bordes 0.500/0.800 alcanzables vía
  `--ejecutar-tests` y la firma por defecto verificada con mocks) mata 70 de
  sus 75 supervivientes (75 → 5); los 5 restantes son equivalencias demostradas
  (E2-E5: `ruta` no usada, `next` sin default, rama `else` inalcanzable y
  `"py"` imposible). Campaña y triaje conservados
  en `build/mut-eval-r3c4` y `build/triaje-eval-r3c4.json`.
- **Límite:** los denominadores no se mezclan con el 95,2% del núcleo ni entre
  sí. La mejora del preflight no autoriza a presentar el evaluador como sano.
- **Criterio de aceptación:** [x] evaluador medido; [x] comando reproducible
  empaquetado; [x] 0 mutantes sin categoría de triaje (1368/1368); [x] 0
  timeouts (re-medido); [x] deuda histórica cerrada con **0 brechas + 125
  equivalencias validadas**; [—] nueva tasa global: no se recalcula por los
  artefactos de campaña documentados en los Hallazgos 217 y 221.
- **Riesgo:** cerrado para el inventario histórico; una campaña nueva exigirá
  validación cruzada antes de aceptar sus conteos.

### R4 — Benchmark de precisión/recall del evaluador — CERRADA 2026-10-26 (alcance offline)

- **Problema medido:** la auditoría de 7 repos y el control de 10 defectos fueron
  una campaña puntual. No hay un arnés que impida volver a introducir falsos
  positivos como los de h6 (853 en FastAPI) o h5 (12/12).
- **Estado 2026-10-26:** **cerrada por alcance offline**. `tests/benchmarks/evaluador_precision.py`
  ejecuta **57 casos sintéticos etiquetados sobre 26 criterios** y declara **3
  N/A** con motivo (f1, v4, h5). Incluye h1, h2, h3, h6, v1, v2, c1-c5,
  f2-f4, h4, h7, v3 (repo git temporal con fecha relativa), i1-i6 y e1-e3,
  además de **5 casos trampa** de falsos positivos (imports en docs, import
  opcional, except con return, TODO en tests y helper sin assert). La
  ampliación del 2026-10-26 añadió c4/h4, v3 y las señales LLM (i1-i6,
  e1-e3) con fixtures **declaradas como sintéticas**; no se llamó a ningún
  proveedor. Calcula TP/FP/FN, precision y recall por criterio y global, y
  admite `--json`. Resultado actual: **26 TP, 0 FP, 0 FN; precision 1,00,
  recall 1,00** en esos 57 casos. El benchmark destapó dos defectos reales: e1
  contaba imports perezosos sin mirar el paquete y e1/e2 no emitían hallazgo al
  fallar; ambos corregidos y cubiertos por los casos.
- **Límite declarado:** cubre **26 de los 29 criterios posibles** y son
  fixtures sintéticas; no es una campaña sobre proyectos reales. El benchmark
  no debe presentarse como validación global del evaluador. Los 3 N/A
  restantes requieren red/PyPI (v4, h5) o un punto de entrada real (f1); no se
  simulan proveedores ni mediciones de fabricante.
- **Cierre 2026-10-26:** se cierra **por alcance**, no por cobertura total:
  26/29 criterios medidos y 3 N/A con motivo. No se presenta como validación
  global ni como campaña sobre proyectos reales. La campaña real con red/PyPI
  y la búsqueda de trampas nuevas quedan opt-in, fuera del alcance de esta
  recomendación; si aparece un falso positivo reproducible, se añade caso.
- **Criterio de aceptación:** [x] TP/FP/FN por criterio; [x] JSON reproducible;
  [x] 0 FP en los casos etiquetados; [x] cobertura offline 26/29 con 3 N/A
  justificadas; [x] 5 trampas de FP; [—] campaña real/red: fuera de alcance,
  opt-in y declarada.
- **Riesgo:** bajo; el riesgo es sobreajustar el benchmark a los casos ya vistos.

### R5 — Decidir el alcance Java/JS — CERRADA 2026-10-25 (decisión A)

- **Decisión 2026-10-25: A, implementada.** Alcance Python explícito y bloqueo
  de comparabilidad; Java/JS solo reciben señales genéricas.
- **Problema medido:** Testcontainers Java tenía 10/29 criterios y QA JS 12/29;
  no hay AST de Java/JS, ni comparación npm/Maven, ni aserciones de esos
  lenguajes. El 1.000/0.692 era «todo lo aplicable pasó», no calidad global.
- **Implementación:** `cobertura.comparable` (solo con ratio ≥80%),
  `cobertura.motivo_no_comparable`, `cobertura.nota_lenguajes` y rótulo
  **«GLOBAL NO COMPARABLE»** en el informe de texto. Un proyecto Java de prueba
  (8/29, 28%) queda marcado como no comparable.
- **Evidencia:** 2 tests nuevos (`TestComparabilidadR5`), suite **902/902**,
  ruff 0, docs-check OK. JSON aditivo: no rompe `schema_version: 2`.
- **Criterio de aceptación:** [x] no se presenta un global comparable con
  cobertura baja; [x] advertencia visible; [x] documentado y probado.
- **Riesgo:** bajo; no se promete paridad Java/JS. Invertir en soporte real
  sigue abierto solo con demanda.

### R6 — Política para silencios deliberados de producción — CERRADA 2026-10-25 (decisión C con warnings)

- **Decisión 2026-10-25: C con warnings, implementada.** Thinker mantiene c3
  estricto; los proyectos externos pueden usar `# noqa: silent: motivo`; los
  marcados se reportan como warning y nunca se ocultan.
- **Problema medido:** c3 marcaba 97 silencios en Hypothesis; muchos son
  defensivos (`except OSError: pass` al borrar un temporal), pero P1.26 prohíbe
  silencios. El informe era correcto; faltaba una vía trazable para externos.
- **Implementación:** marca `# noqa: silent: motivo` (motivo ≥3 caracteres) en
  la línea del `except`; c3 y preflight separan hallazgos de **advertencias**.
  Sin marca o con motivo vacío sigue fallando. Los warnings se muestran en
  texto y JSON; thinker no usa la marca.
- **Evidencia:** 5 tests nuevos (3 de c3 y 2 de preflight), suite **902/902**,
  ruff 0, docs-check OK; preflight propio: 0 hallazgos, 0 warnings.
- **Criterio de aceptación:** [x] política escrita; [x] tests de marca; [x]
  ningún silencio desaparece sin trazabilidad; [x] thinker estricto.
- **Riesgo:** político; la marca puede usarse mal, por eso exige motivo y se
  reporta como warning, nunca como limpio.

### R7 — Medir calidad de aserciones, no solo tests no-op — CERRADA 2026-10-25

- **Problema medido:** c5 detectaba tests que no pueden fallar (`pass`,
  `print(1+1)`), pero `assert True` y tautologías pasaban. c5 no mide la fuerza
  de la suite y no debe presentarse como si lo hiciera.
- **Acción ejecutada:** campo `aserciones_debiles` y sección de texto, con
  detección conservadora de `assert True`/constantes verdaderas,
  comparaciones de constantes que pasan y `assertTrue/assertFalse/assertEqual`
  con literales. No toca `c5` ni la puntuación; no marca variables, helpers ni
  property tests.
- **Evidencia:** dos tests nuevos (detección y no falsos positivos); suite
  **902/902**, ruff 0; el informe distingue no-op de débil. Limitación
  declarada: no detecta tautologías con variables ni `__eq__` personalizados.
- **Criterio de aceptación:** [x] fixtures con `assert True`; [x] 0 falsos
  positivos en property tests/helpers; [x] no-op y débil separados; [x] no
  promete cobertura.
- **Riesgo:** bajo; la detección sintáctica es limitada y se declara.

### R8 — Versionar el esquema JSON (P3, bajo) — CERRADA 2026-10-22

- **Problema medido:** el informe v2 añadió `cobertura`, `no_aplica`,
  `global_nota` y permite `global: null`. Un consumidor que asuma el esquema
  anterior puede romperse sin aviso.
- **Acción ejecutada:** `SCHEMA_VERSION = 2` y `"schema_version": 2` al nivel
  superior del informe; test de contrato en
  `test_thinker_pasa_su_propia_evaluacion`; campos documentados en README.
- **Criterio de aceptación:** [x] JSON con versión; [x] documentación de
  campos; [x] consumidores pueden declarar incompatibilidad comprobando la
  versión.
- **Riesgo:** bajo.

### R9 — Publicar 0.1.4 (CERRADA 2026-10-24, medio)

- **Problema medido (histórico):** `main` tenía cambios desde 0.1.3 (evaluador
  v2, lock 3.37.0, arreglos del Hallazgo 97 y CoVe del 23-oct) pero el paquete
  publicado seguía en 0.1.3. El tag `v0.1.3` (`8a9d948`) **precede** los
  arreglos del 22-oct (`b7711ab`), así que `pip install
  thinker-research==0.1.3` no incluía las correcciones del evaluador ni las de
  esta auditoría.
- **Cierre:** `0.1.4` publicado en TestPyPI y PyPI el 2026-10-24, con los
  mismos hashes en ambos índices; tag anotado `v0.1.4` (`858bdf8`) empujado;
  instalación limpia verificada, `--requisitos` presente, imports OK y
  `pip check` limpio. No hay tarea de GitHub Release: la distribución es
  PyPI/TestPyPI y tags de git (regla 12 ampliada el 2026-10-25).
- **Criterio de aceptación:** [x] `pip install thinker-research==0.1.4` en venv
  limpio; [x] `evaluate-project --help` y evaluación de humo; [x] suite
  **842/842** en Linux; [x] tag verificado. Windows queda pendiente de
  re-verificación con esta suite.
- **Riesgo:** cerrado; una release no se deshace.

### R10 — Licencias de dev/opcionales visibles, fuera del score runtime — CERRADA 2026-10-25

- **Problema medido:** h5 solo consultaba dependencias runtime. Las de
  desarrollo y opcionales no se veían, aunque también se distribuyen en el
  repositorio y pueden afectar a la reproducibilidad/licencias.
- **Acción ejecutada:** campo de primer nivel `licencias_no_runtime` con
  nombre, ámbito, origen, versión, licencia, fuente y procedencia
  (`real`/`unverified`). `h5_licencias_libres` sigue midiendo solo runtime.
  Sin red, cada entrada se declara `unverified`; el informe de texto incluye
  una sección informativa separada.
- **Evidencia:** dos tests nuevos: un extra no libre se reporta fuera del score
  y no cambia h5; sin red queda `unverified`. Suite 858/858.
- **Criterio de aceptación:** [x] informe separado; [x] no mezcla con el score;
  [x] test de extra no libre; [x] `--sin-red` declarado.
- **Riesgo:** bajo.

### R11 — Gate documental (P3, bajo) — CERRADA 2026-10-23

- **Problema medido:** las cifras de estado presente derivaban entre auditorías
  (`747` con la suite en 750; `25/27` con 4 N/A; `verify_install.py` eliminado
  pero citado en presente). Detectarlo dependía de una revisión manual.
- **Acción ejecutada:** `scripts/check_docs.py` (offline, read-only) contrasta
  el nº de tests declarado en `AGENTS.md` y `docs/EVALUACIONES.md` con el
  conteo estático por AST, los pines de `requirements.txt` con
  `requirements.lock` (y los rangos), la versión de `pyproject.toml` con la
  publicada en `docs/PUBLICACION.md` y la cifra de mutación de `README.md` con
  la vigente de `AGENTS.md`. Integrado en `make check` y en el hook
  pre-commit; 11 tests propios. Códigos 0/1/2
  (cuadra/discrepancia/no verificable).
- **Criterio de aceptación:** [x] falla cuando una cifra no cuadra (validado
  durante el desarrollo: declaraba 761 y había 774); [x] falla con el motivo y
  el archivo correctos; [x] no toca históricos fechados.
- **Riesgo:** bajo; un falso positivo obliga a actualizar la cifra, no a
  silenciar el gate.

### R12 — Corpus adversario del evaluador (P3, bajo) — CERRADA 2026-10-23

- **Problema medido:** el parser Poetry inventaba paquetes, `_es_lock`
  aceptaba requirements sueltos y la prosa del README se convertía en comando.
- **Acción ejecutada:** `tests/test_evaluador_corpus.py` fija 4 contratos
  offline: versión exacta Poetry sin paquete inventado, requirements sueltos
  que no cuentan como lock, prosa que no se convierte en runner y comando
  declarado que sí se detecta. Complementa a R4 (26/29 medidos; 3 N/A declaradas).
- **Criterio de aceptación:** [x] cada caso falla con el comportamiento
  anterior; [x] sin red ni escrituras fuera del temporal.
- **Riesgo:** bajo.

### R13 — CoVe con descomposición de claims y verificador barato — CERRADA 2026-10-25 (B+C)

- **Decisión 2026-10-25: B con vía a C, B y C implementadas.** Verificador
  barato medido y descomposición de claims opt-in.
- **Origen:** la literatura 2026 documenta la **asimetría de la verificación**
  y la **descomposición de claims** en subpreguntas verificables.
- **Implementación:** `EvidenceEvaluator(descomponer_claims=True)` separa
  claims compuestos por conjunciones simples, evalúa cada subclaim y agrega:
  cualquier `contradicted` → `contradicted`; todos `supported` → `supported`;
  resto → `not_addressed`. Registra `subclaims`, `descomposicion` y la decisión.
- **Evidencia:** benchmark `tests/benchmarks/claims_compuestos.py`: el claim
  monolítico pasa como `supported` con **1 llamada**; el descompuesto detecta
  la contradicción con **2 llamadas** y `subclaims=2`. Test
  `TestClaimsCompuestos`, suite **902/902**, ruff 0.
- **Criterio de aceptación:** [x] claim compuesto detectado por descomposición;
  [x] coste en llamadas declarado; [x] sin red; [x] opt-in.
- **Riesgo:** la división es heurística, no semántica; se declara. Por eso es
  opt-in y no el modo por defecto.

### R14 — Calibrar `credibility`/`confidence` o declararlas no calibradas — CERRADA 2026-10-25 (declaración + B/C piloto)

- **Decisión 2026-10-25: B con vía a C, B y C (piloto) implementadas.**
- **Acción:** README/AGENTS declaran que **no están calibradas**. Brier
  offline simulado (0,1166, 16 pares); piloto real inicial n=20 con Brier
  0,0540 (modelo de fallback `cohere/north-mini-code:free`).
- **Remedición 2026-11-04:** piloto n=20 con
  `nvidia/nemotron-3-ultra-550b-a55b:free`: **20/20, Brier 0,0050, ECE 0,0650,
  IC95 [0,0034; 0,0066]**. Benchmark factual de 30 casos (10 por categoría):
  **30/30, 0 falsos verificados, abstención 1,0, Brier 0,0044, ECE 0,0590,
  IC95 [0,0031; 0,0059]**. Los instrumentos ya calculan intervalos.
- **Límite:** ambas muestras son pequeñas y fáciles, con confianzas concentradas
  en 0,8-1,0; no prueban calibración general ni convierten `confidence` en
  probabilidad. La muestra representativa por dominio sigue pendiente.
- **Evidencia:** `build/mejoras-calibracion-real-n20.json` y
  `build/mejoras-factual-real-n30.json`; 14 pruebas offline del contrato de
  métricas, benchmark factual y calibración.
- **Criterio:** [x] declaración; [x] Brier simulado; [x] Brier real n=20 y
  factual n=30; [x] intervalos bootstrap; [ ] muestra representativa por
  dominio (trabajo externo).
- **Riesgo:** bajo; los resultados se declaran como muestras acotadas, no como
  certificado.

## 5. Deuda priorizada y cierre (histórico desde 2026-10-25; actualizado 2026-11-04)

**Cerrada:** R3-C (2026-11-04).
**Cerradas:** R1, R2, R4, R5, R6, R7, R8, R9, R10, R11, R12, R13 y R14. Una
recomendación abierta es deuda solo si tiene un criterio de aceptación
medible; las limitaciones declaradas del README no se cuentan como deuda.

| Orden | ID | Estado | Deuda | Evidencia de cierre | Esfuerzo |
|---|---|---|---|---|---|
| 1 | **R3** | **Cerrada** | Mutación del evaluador y preflight | 355 candidatos tratados: 304 detectados, 34 equivalencias conocidas y 17 contextos revisados; **0 brechas + 125 equivalencias validadas**, 0 timeouts; tasas históricas separadas | Medio-alto |

**Orden:** no queda deuda P1 abierta por ejecutar; R4 se cerró por alcance offline.
R5-A, R6-C, R13-B/C y R14-B/C están implementadas; R14-C es un piloto real
n=20, no una calibración general.

- **R3 no requiere decisión de producto**: R3-C está cerrada; no se reabre sin
  evidencia nueva.
- **R5, R6 y R13 están cerradas**; no se reabren sin evidencia nueva.
- **R14** cerrada por declaración; B (Brier simulado) y C (piloto real n=20)
  implementadas; ampliar la muestra sigue siendo trabajo futuro.
- Las cerradas R1/R2/R5/R6/R7/R8/R9/R10/R11/R12/R13/R14 no se reabren sin evidencia.

**No es deuda** (son límites declarados, no defectos pendientes): que
`MockSearchAPI` no haga investigación real, los 429 de modelos gratuitos, que
la CI sea local, que macOS no se haya probado y que Windows no se haya
re-ejecutado con la suite actual.

**Regla 14 — dogfooding ≥90%:** todas las tareas de esta deuda se ejecutan con
componentes de thinker en al menos el 90% de los casos. Cada tarea se registra
así, y el registro se conserva en el informe de cierre del lote:

| Tarea | Componente de thinker | Evidencia que aportó | Verificación humana/automática |
|---|---|---|---|
| R3 (2026-10-25) | `evaluar_proyecto`/`preflight`/`mutmut` | `scripts/mutacion.py`; preflight 696/1015, 319 brechas; evaluador 3034/5939, 2901 brechas + 4 timeouts; triaje 3224/3224 | 3 tests del arnés + 3 de helpers + 6 de manifiestos; triaje de inventario completo |
| R3 (2026-10-26) | `preflight`, `mutacion`/`triaje_mutantes`, `evaluar_proyecto` y `code_design_improvement_tools` | preflight 967/1016, 49 equivalencias y 0 brechas; evaluador 4665/5984, 1319 brechas, 0 timeouts; autoevaluación offline 1.000 (25/29, 86,2% cobertura) sin hallazgos; el análisis estático no reportó defectos → se reforzaron aserciones, no se refactorizó; el triaje dirigió los clusters y detectó `_es_main`, e1/e2 | 116 tests nuevos en la suite (preflight, evaluador y salvaguardas), 2 campañas re-medidas, triaje 1368/1368, 0 timeouts; suite 1018/1018 |
| R4 | `evaluar_proyecto` y `tests/benchmarks` | 57 casos (5 trampas), 26 criterios, 26 TP/0 FP/0 FN, 1,00/1,00; c4/h4/v3/i1-i6/e1-e3 añadidos; encontró y corrigió dos defectos e1/e2 | `test_evaluador_precision` |
| R7 | `evaluar_proyecto` | `aserciones_debiles` + 2 tests; c5 sin cambios | suite 902/902 (cierre); 1018/1018 actual |
| R3 (2026-10-28) | `triaje_mutantes` (JSON de triaje) y `evaluar_proyecto` | 16 supervivientes de `_verificar_test` con su diff; 3 bordes sin aserción exacta identificados (rama `existe is None`, condición `ejecutado/error`, cadena de motivo) | 1 test de contrato nuevo; **16/16 mutantes mueren** (verificación manual estilo mutmut) y la **re-medición oficial r3c2 lo confirma**: 4681/5984, 1303 brechas, 0 timeouts; suite **1019/1019** |
| R3 (2026-10-28, vigencia) | `triaje_mutantes` (JSON r3c2) y `evaluar_proyecto` | 82 supervivientes de `evaluar_vigencia` con su diff; patrones: argumentos de `_git`, tuplas de hallazgo, notas exactas y contadores de v4 | 10 tests de contrato nuevos (repo git temporal + PyPI simulada); **80/82 mueren** en verificación manual; 2 equivalencias demostradas (E1); **re-medición oficial r3c3**: 4764/5984 (79,61%), 1218 brechas, 0 timeouts; suite **1029/1029** |
| R3 (2026-10-28, evaluar) | `triaje_mutantes` (JSON r3c3) y `evaluar_proyecto` | 75 supervivientes de `evaluar` con su diff; la exploración empírica de fixtures evitó declarar 3 falsas equivalencias de borde (0.500/0.800 alcanzables con `--ejecutar-tests`, total 30) | 16 tests de contrato nuevos (fixture completa 29/29, dobles de LLM/búsqueda, bordes con suite ejecutada); **70/75 mueren** en verificación manual; 5 equivalencias demostradas (E2-E5); **re-medición oficial r3c4**: 4846/5984 (80,98%), 1131 brechas, 0 timeouts; suite **1045/1045** |
| R3 (2026-10-28, herramientas) | `triaje_mutantes` (JSON r3c4) y `evaluar_proyecto` | 70 supervivientes de `evaluar_herramientas` con su diff; el experimento blanco de mutmut del Hallazgo 143 guió el método (verificación diff a diff, no campaña masiva) | 16 tests de contrato nuevos (`TestHerramientasContrato`); **64/70 mueren** en verificación manual; 6 equivalencias demostradas (E6-E8); contabilidad 1131 → **1067 brechas + 62 equivalencias**; suite **1107/1107** |
| R3 (2026-10-30, licencias no runtime) | `code_design_improvement_tools` y `evaluar_proyecto` | Thinker comparó candidatos R3: `licencias_no_runtime`, 40 líneas/complejidad 6; se eligió por alcance pequeño. Sin JSON r3c4 no se inventaron IDs | 1 test de contrato; **4/4 mutaciones dirigidas detectadas**; suite **1212/1212** y demos OK. Avance local: R3 y su inventario oficial no cambian sin re-medición |
| R3 (2026-10-30, locks ignorados) | `code_design_improvement_tools` y `evaluar_proyecto` | `_versiones_lock`: 62 líneas/complejidad 20, sin issues; se acotó el trabajo a la guarda de directorios excluidos, sin refactor | 1 test de contrato; **3/3 mutaciones dirigidas detectadas**; suite **1213/1213** y demos OK. R3 y su inventario oficial no cambian sin re-medición |
| R3 (2026-10-30, ámbito junto a manifiestos) | `code_design_improvement_tools` y `evaluar_proyecto` | Thinker comparó tres candidatos; `_ambito_requirements` fue el más acotado: 27 líneas/complejidad 8, sin issues. Se eligió la rama de manifiestos anidados | 1 test de contrato para `pyproject.toml` y `setup.py`; **3/3 mutaciones dirigidas detectadas**; suite **1214/1214** y demos OK. R3 y su inventario oficial no cambian sin re-medición |
| R3 (2026-10-30, includes compartidos) | `code_design_improvement_tools`, `evaluar_proyecto` y `preflight` | `_leer_requirements`: 24 líneas/complejidad 5; la reproducción mostró segunda lectura duplicada y 0 archivos en `vistos`. El patrón explícito de preflight confirmó la corrección | 1 regresión roja antes y verde después; `None` ya no se confunde con set vacío; **3/3 mutaciones detectadas**; suite **1215/1215** y demos OK. Inventario oficial sin re-medición |
| R3 (2026-10-30, sección Pipfile inválida) | `code_design_improvement_tools` y `evaluar_proyecto` | Thinker midió `_versiones_lock` (62 líneas/complejidad 20) y se acotó el caso: `default` como lista no vacía causaba `AttributeError` | 1 regresión roja antes y verde después; aviso explícito, sección inválida omitida y `develop` conservado; **3/3 mutaciones detectadas**; suite **1216/1216** y demos OK |
| R3 (2026-10-30, packages inválido) | `code_design_improvement_tools` y `evaluar_proyecto` | Tras aislar Pipfile, Thinker midió 69 líneas/complejidad 21 y se eligió solo `package-lock`: una lista no vacía en `packages` causaba `AttributeError` | 1 regresión roja antes y verde después; salida `{}` y aviso explícito; **3/3 mutaciones detectadas**; suite **1217/1217** y demos OK. Inventario oficial sin re-medición |
| R3 (2026-10-30, raíz JSON no objeto) | `code_design_improvement_tools` y `evaluar_proyecto` | Thinker midió `_versiones_lock` (76 líneas/complejidad 22); ambos parsers reproducían `AttributeError` con raíz lista | 1 regresión con dos subcasos, roja antes y verde después; aviso y salida `{}`; **3/3 mutaciones detectadas**; suite **1218/1218** y demos OK |
| R3 (2026-10-30, grupo Poetry inválido) | `code_design_improvement_tools` y `evaluar_proyecto` | Thinker midió `_dependencias_pyproject` (77 líneas/complejidad 20); un grupo con `dependencies` lista rompía `.items()` | 1 regresión roja antes y verde después; aviso para `dev` y grupo `test` conservado; **3/3 mutaciones detectadas**; suite **1219/1219** y demos OK |
| R3 (2026-10-30, comodín PEP 440) | `code_design_improvement_tools` y `evaluar_proyecto` | Thinker midió `_parsear_requisito` (29 líneas/complejidad 5); `==2.*` producía `fijada=True`, `v1=True` y comparación literal en PyPI | PEP 440 confirma coincidencia por prefijo; parser, v1 y v4 usan `fijada`; regresión sin llamada PyPI, **3/3 mutaciones detectadas**; suite **1220/1220** y demos OK |
| R3 (2026-10-30, comodín en locks) | `code_design_improvement_tools` y `evaluar_proyecto` | Thinker midió `_versiones_lock` (86 líneas/complejidad 24); un lock textual devolvía `requests: 2.*` como versión resuelta | 1 regresión roja antes y verde después; salida exacta solo `click: 8.1.7`; **3/3 mutaciones detectadas**; suite **1221/1221** y demos OK |
| R3 (2026-10-30, falso lock por comodín) | `code_design_improvement_tools` y `evaluar_proyecto` | Thinker midió `_es_lock` (19 líneas/complejidad 3); la búsqueda textual `==` aceptaba `2.*` como lock | Regresión con comodín falso y controles exacto/hash verdaderos; mayoría intacta, **3/3 mutaciones detectadas**; suite **1222/1222** y demos OK |
| R3 (2026-10-30, relleno de ceros PEP 440) | `code_design_improvement_tools` y `evaluar_proyecto` | Thinker midió `evaluar_vigencia` (104 líneas/complejidad 19); `2.31` frente a PyPI `2.31.0` daba falso «atrasada» | Normalización solo de releases numéricas; regresión en ambos sentidos y compatibilidad con `None`; **3/3 mutaciones detectadas**; suite **1223/1223** y demos OK |
| R15 (2026-10-30, iteration inválida) | `code_design_improvement_tools` y `research_state` | Thinker midió el módulo (136 líneas/7 funciones/complejidad 12); `context_from_state` aceptaba `iteration="0"`, booleanos y negativos | Regresión con 4 valores inválidos, roja antes y verde después; esquema intacto; **3/3 mutaciones detectadas**; suite **1224/1224** y demos OK |
| R15 (2026-10-30, decomposed no booleano) | `code_design_improvement_tools` y `research_state` | Thinker midió el módulo actualizado (140 líneas/complejidad 13); `decomposed="false"` se restauraba como `True` por `bool(...)` | Regresión con 4 inválidos y controles `True`/`False`; validación estricta, **3/3 mutaciones detectadas**; suite **1225/1225** y demos OK |
| R15 (2026-10-30, duración no finita) | `code_design_improvement_tools` y `research_state` | Thinker midió el módulo (144 líneas/complejidad 14); `NaN` e infinito producían `start_time` no finito | `math.isfinite` en `duration_seconds`; regresión con NaN/±inf y control válido, **3/3 mutaciones detectadas**; suite **1226/1226** y demos OK |
| Instalación limpia (2026-10-30) | `code_design_improvement_tools` y `scripts/verificar_instalacion.py` | `make verify-install` falló con setuptools 65.5.0; pyproject exige >=77 y el verificador solo comprobaba presencia | Versión mediante `importlib.metadata`; regresión 65.5/77 y selección de aislamiento; **3/3 mutaciones detectadas**; suite **1227/1227**, demos y wheel/instalación con 82.0.1 OK |
| R3 (2026-10-31, cierre `_ambito_requirements`) | `triaje_mutantes`, `code_design_improvement_tools` y `evaluar_proyecto` | Campaña acotada: 77 mutantes; diffs agrupados en nombres/bordes y 14 equivalencias semánticas. La salida guió dos regresiones, no cambios de producción | 44→63 muertos (+19), 33→14 supervivientes (todos equivalentes); 10/10 muertes directas y 14/14 comparaciones en 11 rutas; **1067→1034 brechas, 62→76 equivalencias**; suite **1229/1229** y demos OK |
| R3 (2026-10-31, cierre `licencias_no_runtime`) | `code_design_improvement_tools` y `evaluar_proyecto` | Thinker midió 40 líneas/complejidad 6; la campaña acotada produjo 120 mutantes y 0 supervivientes | 10/10 muertes directas, fuente restaurado; **1034→997 brechas**, 76 equivalencias intactas; sin cambios de producción ni tests |
| R3 (2026-10-31, cierre `_dependencias_pyproject`) | `code_design_improvement_tools` y `evaluar_proyecto` | Thinker midió 83 líneas/complejidad 21; la primera muestra directa detectó el mutante 5 superviviente y obligó a revisar la medición | 258 muertos + 1 equivalencia, 0 brechas; 10 muertes no equivalentes directas y fallback idéntico en 3 entradas; **997→949 brechas, 76→77 equivalencias** |
| R3 (2026-10-31, cierre `_versiones_lock`) | `code_design_improvement_tools` y `evaluar_proyecto` | Thinker midió 86 líneas/complejidad 24; los mutantes 7/9 fueron equivalentes y el 12 reveló una brecha real con paquetes incompletos | 201 muertos + 2 equivalencias, 0 brechas; 10 muertes directas y nueva regresión; **949→917 brechas, 77→79 equivalencias**; suite **1230/1230** y demos OK |
| R3 (2026-10-31, cierre `_dependencias`) | `code_design_improvement_tools` y `evaluar_proyecto` | Thinker midió 47 líneas/complejidad 9; la campaña acotada produjo 138 mutantes y la revisión directa distinguió 136 muertos de 2 equivalencias | 10/10 muertes directas y 2 equivalencias comprobadas, fuente restaurado; **917→879 brechas, 79→81 equivalencias**; sin cambios de producción ni tests |
| R3 (2026-10-31, cierre `main`) | `code_design_improvement_tools` y `evaluar_proyecto` | Thinker midió 67 líneas/complejidad 7; 65 supervivientes guiaron dos contratos de CLI y la revisión de defaults de `argparse` | 160 muertos + 2 equivalencias, 0 brechas; 10 muertes directas, 2 regresiones y cierre directo de 4 casos; **879→814 brechas, 81→83 equivalencias**; suite **1232/1232** |
| R3 (2026-10-31, cierre `evaluar_calidad`) | `code_design_improvement_tools` y `evaluar_proyecto` | Thinker midió 122 líneas/complejidad 23; la campaña acotada produjo 339 mutantes y 0 supervivientes | 10/10 muertes directas, fuente restaurado; **814→767 brechas**, 83 equivalencias intactas; sin cambios de producción ni tests |
| R3 (2026-10-31, cierre `parsear_requisitos`) | `code_design_improvement_tools` y `evaluar_proyecto` | Thinker midió 122 líneas, 2 funciones y complejidad 21; la muestra directa corrigió el 218/218 inicial a **217 muertos + 1 equivalencia** | Una regresión mata el mutante 218; E14 demostrada, otras ocho muertes directas y original restaurado; **767→732 brechas, 83→84 equivalencias**; suite **1233/1233** |
| R3 (2026-10-31, cierre `evaluar_inteligencia`) | `code_design_improvement_tools` y `evaluar_proyecto` | Thinker midió 36 líneas, 1 función y complejidad 4, sin incidencias; la muestra directa detectó dos supervivientes pese al 139/139 de campaña | Una regresión de contrato mata 130/139; otras siete muertes directas y original restaurado; **732→702 brechas**, 84 equivalencias intactas; suite **1234/1234** |
| R3 (2026-10-31, cierre `sintetizar_con_llm`) | `code_design_improvement_tools` y `evaluar_proyecto` | Thinker midió 44 líneas, 1 función y complejidad 5; la campaña reprodujo 110 muertos y 29 brechas | Siete regresiones nuevas; **29/29 supervivientes y 10/10 controles detectados**, original restaurado; **702→673 brechas**, 84 equivalencias intactas; suite **1241/1241** |
| R3 (2026-10-31, re-medición `evaluar_eficiencia`) | `code_design_improvement_tools` y `evaluar_proyecto` | Thinker midió 66 líneas, 1 función y complejidad 10; la campaña produjo 190 mutantes y 0 supervivientes | 10/10 muertes directas, original restaurado; sin cambios de producción ni tests; R3 permanece en **673 brechas + 84 equivalencias** por falta de distribución histórica |
| R3 (2026-10-31, cierre `_digesto`) | `code_design_improvement_tools` y `evaluar_proyecto` | Thinker comparó tres candidatos y eligió `_digesto`: 21 líneas/complejidad 3; la campaña produjo 55 muertos y 13 supervivientes | Tres regresiones nuevas; **13/13 supervivientes y 10/10 controles detectados**, original restaurado; **68/68 muertos**; R3 permanece en **673 brechas + 84 equivalencias** por falta de distribución histórica; suite **1244/1244** |
| R3 (2026-10-31, cierre `evaluar_funcionalidades`) | `code_design_improvement_tools` y `evaluar_proyecto` | Thinker midió 75 líneas/complejidad 14; la muestra directa detectó dos supervivientes pese al 224/224 de campaña | Una regresión de `README.txt` y severidad alta mata 50/100; otros ocho controles y original restaurado verdes; **224/224 muertos**; R3 permanece en **673 brechas + 84 equivalencias**; suite **1245/1245** |
| R3 (2026-10-31, re-medición `detectar_comando_tests`) | `code_design_improvement_tools` y `evaluar_proyecto` | Thinker midió 78 líneas/complejidad 16; la campaña produjo 235 mutantes y 0 supervivientes | 10/10 muertes directas, original restaurado; sin cambios de producción ni tests; R3 permanece en **673 brechas + 84 equivalencias** por falta de distribución histórica |
| R3 (2026-10-31, verificación `_puntuacion_texto`) | `code_design_improvement_tools` y `evaluar_proyecto` | Thinker midió 2 líneas/complejidad 0; solo se generaron cuatro mutantes | **4/4 diffs detectados directamente**, original restaurado; sin cambios de producción ni tests; R3 permanece en **673 brechas + 84 equivalencias** |
| R3 (2026-10-31, cierre `investigar_preguntas`) | `code_design_improvement_tools` y `evaluar_proyecto` | Thinker midió 23 líneas/complejidad 2; la campaña produjo 29 muertos y 14 supervivientes | Cuatro regresiones nuevas; **14/14 supervivientes y 10/10 controles detectados**, original restaurado; **43/43 muertos**; R3 permanece en **673 brechas + 84 equivalencias**; suite **1249/1249** |
| Regla 16 (2026-10-31, métricas y resumen de calidad) | `evaluar_proyecto`, `scripts/informe_calidad.py` y `check_docs` | La autoevaluación real corrigió el estado offline a **1.000 (27/29; 2 N/A)**; los deltas guiaron el resumen: +121 tests y −458 brechas R3 | **7/7 gates PASS**, 1249/1249 tests y holdout 4/4; evolución y gráfico breve publicados en README; detalle y límites enlazados |
| R3 (2026-10-31, cierre `_linter_configurado`) | `code_design_improvement_tools` y `evaluar_proyecto` | Thinker comparó tres candidatos y eligió 22 líneas/complejidad 7; la muestra directa detectó 60/70 vivos pese al 79/79 inicial | E15 demostrada en seis variantes; regresión de `eslint.config.js` mata 70; otros ocho controles y original verdes; **78 muertos + 1 equivalencia**; R3: **673 brechas + 85 equivalencias** |
| R3 (2026-10-31, cierre `_tiene_punto_entrada`) | `code_design_improvement_tools` y `evaluar_proyecto` | Thinker midió 32 líneas/complejidad 11; la muestra directa detectó 60 y 80 vivos pese al 90/90 de campaña | Una regresión con `console_scripts`, solo `bin` y solo `main` mata ambos; otros ocho controles y original verdes; **90/90 muertos**; R3 permanece en **673 brechas + 85 equivalencias**; suite **1288/1288** |
| R3 (2026-10-31, cierre `plan_texto`) | `code_design_improvement_tools` y `evaluar_proyecto` | Thinker comparó tres candidatos y eligió 13 líneas/complejidad 2; la campaña produjo 33 muertos y 9 supervivientes | Una regresión mata 35 por orden estable; 3/5/41 son E16 con salidas idénticas; otros seis supervivientes y diez controles mueren; **39 muertos + 3 equivalencias**; R3: **673 brechas + 86 equivalencias**; suite **1289/1289** |
| R3 (2026-10-31, cierre `_registro_decisiones`) | `code_design_improvement_tools` y `evaluar_proyecto` | Thinker midió 17 líneas/complejidad 5; la muestra directa detectó 2, 3, 15 y 25 vivos pese al 57/57 inicial | Una regresión con ADR, release notes y AsciiDoc mata los cuatro; otros seis controles y original verdes; **57/57 muertos**; R3 permanece en **673 brechas + 86 equivalencias**; suite **1290/1290** |
| R3 (2026-10-31, evidencia no resoluble) | `code_design_improvement_tools` y documentación oficial de `pathlib` | Thinker acotó cuatro funciones; un bucle real de symlinks reveló `RuntimeError`, no señalado por el análisis estático | Regresión roja antes del arreglo; 71/71 mutantes detectados, candidato a equivalencia refutado por `XXapp.pyXX`; R3 permanece en **673 brechas + 98 equivalencias**; suite **1303/1303** |
| Integridad de fuentes (2026-10-31) | `code_design_improvement_tools`, autoevaluación y campaña Mutmut aislada | El análisis acotó los candidatos sin señalar estilo; las reproducciones mostraron URLs fusionadas, claim mal asociado, fecha futura con valor 1.0 y asociación por IDs ausentes | 10 regresiones y contratos de bordes; 198 mutantes en cuatro funciones: **193 muertos + 5 equivalencias demostradas**, originales restaurados; suite **1313/1313**; R3 intacto en 673 brechas + 98 equivalencias |
| R3 (2026-11-01, cierre `_requisito_poetry`) | `code_design_improvement_tools`, Mutmut acotado y documentación oficial Poetry/PEP 440 | Thinker priorizó helpers; cinco supervivientes idénticos en r3c4 y actual; la especificación confirmó pérdida de versión en `^`/`~` | Dos regresiones y contratos reforzados; 87 mutantes actuales: **85 muertos + 2 equivalencias**, cinco históricos muertos, originales restaurados; **673→668 brechas**; corrección aritmética 100→102 equivalencias; suite **1315/1315** |
| R3 (2026-11-01, Hallazgo 210) | `code_design_improvement_tools` y campañas Mutmut acotadas | Thinker priorizó helpers y los diffs guiaron contratos de bordes; 20+58+22 muertos en tres lotes, con 2+10+2 equivalencias demostradas por separado | 13 contratos; **100 brechas históricas resueltas + 14 equivalencias**, no contadas como muertes; R3: **668→568 brechas + 116 equivalencias**; suite **1328/1328** |
| R3 (2026-11-01, Hallazgo 211) | `code_design_improvement_tools`, `evaluar_proyecto` y arnés pareado r3c4/actual | Thinker priorizó clústeres; la reproducción 5644/355 confirmó el artefacto y se rechazó. El arnés aplicó solo diffs localizados y revalidó la base 87 para no contar arreglos posteriores | 14 contratos; **200 muertes exactas**, 3 excedentes fuera; **10 equivalencias** E28-E31; originales restaurados y hashes verificados; R3: **568→368 brechas + 126 equivalencias**; suite **1342/1342** |
| Auditor de cambios (2026-11-01, Hallazgo 212) | `audit_changes` y pruebas de regresión | El gate marcó una cadena de datos como matcher flojo; la prueba de `tsconfig` refutó el primer filtro global | Helper limitado a aserciones y matchers; 29/29 tests del auditor; suite **1343/1343**; R3 sin cambios; release `0.1.20` publicada y tag `v0.1.20` |
| R3 (2026-11-01, Hallazgo 213) | `evaluar_proyecto`, arnés pareado r3c4/actual y `code_design_improvement_tools` | Thinker priorizó helpers abiertos; el arnés solo contó muertes con supervivencia en r3c4 y fallo actual, y detectó que un equivalente previo ahora muere | 3 métodos (2 contratos y la regresión de `GIT_INDEX_FILE` en fixtures); **205 muertes halladas**, **200 contadas** y 4 excedentes; 1 equivalencia previa excluida hasta revisión; originales restaurados por SHA-256; R3: **368→168 brechas + 126 equivalencias**; suite **1346/1346** |
| R3 (2026-11-01, Hallazgo 214) | `evaluar_proyecto`, arnés pareado r3c4/actual y `tests.helpers` | El lote de 200 no se alcanzó: 86 muertes ya detectadas por contratos previos, 13 nuevas y 13 equivalencias; la cola del plan quedó en `historico_killed` y los clústeres cerrados se excluyeron para no duplicar | 4 contratos de borde (`informe_texto`, requirements, tag `XX`, `setup.cfg`); **99 muertes + 13 equivalencias E32**; R3: **168→69 brechas + 139 equivalencias**; 0 hallazgos nuevos fuera del inventario; faltan 101 muertes; suite **1397/1397** |
| Coherencia documental (2026-11-04, Hallazgo 216) | `evaluar_proyecto`, `code_design_improvement_tools` y `check_docs` | La autoevaluación con suite real dio 1.000 offline; el analizador solo aportó tres avisos de demo/estilo, descartados como mejora sustantiva. La revisión del gate encontró `0.1.19` en recomendaciones frente a `0.1.21` en el paquete pese a «DOCS: OK» | Dos regresiones rojas antes del arreglo; el gate contrasta la fila de paquete actual/publicado con `pyproject.toml`; 14/14 pruebas del gate, suite **1399/1399** y R3 sin cambios |
| R3 (2026-11-04, Hallazgo 217) | `scripts/mutacion.py`, `triaje_mutantes.py` y verificación directa r3c4/actual | La campaña de 6144 mutantes dejó 37 supervivientes: 36 equivalencias conocidas y un falso superviviente ya cubierto. La muestra de diez «killed» destapó dos brechas reales e invalidó la tasa global | Dos regresiones de `lineno=None` y campo duplicado; ambos diffs sobrevivían en r3c4 y ahora mueren de forma aislada; R3: **69→67 brechas + 139 equivalencias**; suite **1401/1401** |
| Deduplicación y preflight (2026-11-04, Hallazgos 219-220) | `scripts/mutacion.py`, `triaje_mutantes.py` y diffs directos por contenido | E32 repite 12 casos; los 90 registros del evaluador son 78 únicos. La revalidación detectó deriva de IDs y dos casos E23 cubiertos por tests; preflight aportó 17 brechas nuevas | Inventarios JSON + contrato de conteo: **127 únicas** y **125 validadas** (49+76); cuatro contratos cierran **17/17** mutantes nuevos, original verde, suite **1406/1406** |
| Cierre histórico (2026-11-04, Hallazgo 221) | Cuatro workers con fixtures actuales y revisión manual de contextos | Los 355 candidatos quedan con veredicto individual: 304 detectados, 34 equivalencias conocidas y 17 `no_aplicable` revisados; los 34 supervivientes están en el inventario validado | **0 brechas + 125 equivalencias validadas**; una regresión de línea vacía falla con `[] != ['requests']`; cuatro originales verdes; suite **1407/1407** |
| Coherencia posterior al cierre (2026-11-04, Hallazgo 222) | `check_docs` y `evaluar_proyecto` | `DOCS: OK` y autoevaluación offline 1.000 (27/29; 2 N/A; 0 hallazgos) no detectaron que secciones vigentes seguían llamando «parcial» y «pendiente» a R3; la revisión semántica guio una corrección solo documental | Rótulos actuales reconciliados con **0 brechas + 125 equivalencias validadas**; historial fechado intacto, búsqueda de rótulos obsoletos sin coincidencias y gates offline; suite **1407/1407**, sin cambios de producción ni release |
| Actualización y validación real (2026-11-04, Hallazgo 223) | `evaluar_proyecto`, benchmark factual, calibración real y suites con lock | La autoevaluación con red detectó `openai 3.42.0 → 3.45.0`; el benchmark factual prometía Brier pero no lo devolvía, y Python 3.14 no lanzaba la excepción esperada ante un bucle de symlinks | Lock con **3 actualizaciones** y sin vulnerabilidades; regresión `KeyError` corregida con Brier/ECE/IC; bucle y enlace roto contratados; **1409/1409 en 3.11/3.12/3.14** con openai 3.45.0; factual real **30/30** y piloto **20/20**, ambos acotados |

No cuenta una ejecución decorativa al final: si la salida de thinker no cambió
o no validó una decisión, la tarea no se contabiliza. Si thinker alucina, se
descarta y se anota; la verificación empírica sigue siendo obligatoria.

## 6. Qué NO hacer

- **No** convertir el global en un ranking universal: la cobertura varía y el
  informe ya lo declara. Un 1.000 con 10/29 no es comparable con 20/29.
- **No** contar N/A como 0 para «castigar» proyectos multilingües: sería un
  falso suspenso.
- **No** ejecutar suites de terceros por defecto; sigue siendo opt-in
  (`--ejecutar-tests`) y read-only fuera de eso.
- **No** aplicar cambios automáticamente a proyectos evaluados; el evaluador
  propone, el humano decide.
- **No** subir la versión ni publicar para que la autoevaluación sea 1.000; la
  métrica se corrige con evidencia, no con un bump.
- **No** añadir un parser SPDX completo como dependencia sin evaluar licencia,
  mantenimiento y coste; primero medir los casos reales.
- **No** silenciar el gate documental editando el script: si una cifra no
  cuadra, se actualiza la cifra o se retira la afirmación (regla propia 11).

## 7. Estado de ejecución

**Implementado:** R5-A (comparabilidad), R6-C (warnings), R13-B/C
(verificador barato y descomposición), R14-B/C (Brier simulado y piloto real
n=20) y R4 cerrada por alcance offline (57 casos/26 criterios; 3 N/A
declaradas). **Historial de ejecución de R3 (cerrado el 2026-11-04):**

1. **R3-C (cerrada):** el punto de partida registró preflight 0 brechas reales
   (967/1016; 95,18%; 49 equivalencias) y evaluador 1319 brechas (4665/5984;
   77,96%), con **0 timeouts** y triaje 1368/1368. El 2026-10-28 se atacaron
   16 (`_verificar_test`; 16/16
   muertos, r3c2), 80 de `evaluar_vigencia` (82 → 2, ambas equivalencias
   demostradas; r3c3) y 70 de `evaluar` (75 → 5, las cinco equivalencias
   demostradas E2-E5; r3c4) y 64 de `evaluar_herramientas` (70 → 0: 64
   muertos + 6 equivalencias E6-E8, Hallazgo 144), y el cierre dirigido de
   `_ambito_requirements` (33 → 0: 19 muertos + 14 equivalencias E9, Hallazgo
   167), `licencias_no_runtime` (37 → 0: 37 muertos, Hallazgo 168) y
   `_dependencias_pyproject` (48 → 0: 48 muertos + 1 equivalencia E10, Hallazgo
   169), `_versiones_lock` (32 → 0: 32 muertos + 2 equivalencias E11, Hallazgo
   170), `_dependencias` (44 → 0: 44 muertos + 2 equivalencias E12, Hallazgo
   171), `main` (65 → 0: 65 muertos + 2 equivalencias E13, Hallazgo 172),
   `evaluar_calidad` (47 → 0: 47 muertos, Hallazgo 173), `parsear_requisitos`
   (35 → 0: 35 muertos + 1 equivalencia E14, Hallazgo 174),
   `evaluar_inteligencia` (30 → 0: 30 muertos, Hallazgo 175) y
   `sintetizar_con_llm` (29 → 0: 29 muertos, Hallazgo 176): en ese punto
   quedaban **673** (tasa histórica: 4846/5984; 80,98%); el criterio vigente
   era no cerrar hasta llegar a 0 brechas.
   La re-medición de `evaluar_eficiencia` confirmó **190/190 muertos** y 10/10
   controles directos (Hallazgo 177), sin cambiar el conteo por falta de
   distribución histórica detallada. El cierre de `_digesto` añadió tres
   regresiones y confirmó **68/68 muertos** (13 antiguos supervivientes y 10/10
   controles; Hallazgo 178), con el mismo límite de contabilidad. Después,
   `evaluar_funcionalidades` añadió una regresión y confirmó **224/224 muertos**
   (dos antiguos supervivientes y 10/10 controles totales; Hallazgo 179).
   `detectar_comando_tests` confirmó después **235/235 muertos** y 10/10
   controles directos, sin nuevas regresiones (Hallazgo 180).
   `_puntuacion_texto` confirmó sus **4/4 mutantes** en verificación directa
   (Hallazgo 181), sin cambiar el inventario. `investigar_preguntas` añadió cuatro
   regresiones y confirmó **43/43 muertos** (14 antiguos supervivientes y 10/10
   controles; Hallazgo 182), con el mismo límite de contabilidad. Después,
   `_linter_configurado` cerró con **78 muertos + 1 equivalencia (E15)** y una
   regresión de `eslint.config.js` (Hallazgo 185): **673 brechas + 85
   equivalencias**. `_tiene_punto_entrada` añadió después una regresión y confirmó
   **90/90 muertos** (Hallazgo 186), con la suite en **1288/1288**. `plan_texto`
   cerró después con **39 muertos + 3 equivalencias (E16)** y suite **1289/1289**
   (Hallazgo 187): R3 queda en **673 brechas + 86 equivalencias**.
   `_registro_decisiones` añadió otra regresión y confirmó **57/57 muertos**
   (Hallazgo 188), con la suite en **1290/1290**. El cierre histórico de
   `_requisito_poetry` (Hallazgo 207) añadió dos regresiones, corrigió la
   traducción `^`/`~` y cerró cinco mutantes de r3c4: **673→668 brechas** y
   **102 equivalencias** tras corregir también el desfase de E16; suite
   **1315/1315**. El Hallazgo 210 añadió 13 contratos y cerró exactamente
   **100 brechas históricas** en tres lotes (20+58+22 muertos); las **14
   equivalencias** demostradas se clasificaron aparte. El Hallazgo 211 añadió
   14 contratos y demostró exactamente **200 brechas** con diffs localizados;
   la base 87 se revalidó, tres excedentes quedaron fuera y E28-E31 sumaron
   **10 equivalencias**. El Hallazgo 213 repitió el método pareado y demostró
   otras **200 brechas** (205 halladas, 4 excedentes fuera y una equivalencia
   previa excluida hasta revisión). El Hallazgo 214 cerró **99 muertes + 13
   equivalencias** del inventario abierto y no alcanzó las 200 pedidas: faltan
   101 muertes. El Hallazgo 217 añadió dos regresiones y verificó ambos diffs
   en r3c4 y en el código actual, con dos falsos «killed» que invalidan la tasa
   global de la nueva campaña. El Hallazgo 219 demuestra que E32 repite 12 casos
   de E22–E27: hay **127 equivalencias únicas**, no 139. El Hallazgo 220 valida
   **125 equivalencias** (49 preflight + 76 evaluador) y cierra **17 brechas**
   nuevas con cuatro contratos; E23 124/126 quedan cubiertos por tests. Estado
   actual: **67→0 brechas + 125 equivalencias validadas**; suite **1409/1409**.
   La deuda R3 queda cerrada.

R14-C completó un piloto real n=20 (Brier 0,0050) y un factual n=30 (Brier
0,0044), ambos con intervalos; una muestra representativa por dominio y la
validación humana independiente siguen siendo trabajo externo. R1, R2, R5, R6, R7,
R8, R9, R10, R11, R12, R13 y R14 están cerradas.

## 8. Verificación reproducible

Sin red (tests, lint, preflight, gate documental, autoevaluación offline):

```bash
python3 -m unittest discover -s tests -q
ruff check .
python3 scripts/preflight.py
python3 scripts/check_docs.py
python3 evaluar_proyecto.py . --sin-red --json
make ci                 # exporta HEAD a una copia limpia
```

Cobertura de evaluador/preflight/corpus:

```bash
COVERAGE_FILE=/tmp/coverage-eval \
  python3 -m coverage run --source=. -m unittest \
    tests.test_evaluar_proyecto tests.test_preflight tests.test_evaluador_corpus
COVERAGE_FILE=/tmp/coverage-eval \
  python3 -m coverage report -m evaluar_proyecto.py scripts/preflight.py
```

Autoevaluación con red (consulta PyPI; opt-in):

```bash
python3 evaluar_proyecto.py . --json
```

Campaña externa (clones fuera del repo; no ejecuta sus suites):

```bash
for repo in fastapi flask httpie hypothesis requests; do
  python3 evaluar_proyecto.py "/ruta/a/$repo" --json > "/tmp/$repo-v2.json"
done
```

Los informes de la campaña 2026-10-21 y sus cifras están en
`docs/EVALUACIONES.md`; las causas y decisiones, en el Hallazgo 94 de
`docs/LECCIONES-APRENDIDAS.md`.

## 9. Criterio de cierre de estas recomendaciones

Una recomendación se considera cerrada solo si:

1. tiene una prueba o una medición reproducible que la respalde;
2. el criterio de aceptación está en el repositorio (test, comando o documento);
3. la salida real se conserva y se puede repetir;
4. si no se puede verificar, se declara `unverified` y no se presenta como
   éxito.

Este documento no promete que thinker sea un ranking universal de calidad:
promete que sus diagnósticos sean **verificables, acotados y honestos**.

## 10. Programa comparativo y de optimización (2026-10-30)

Estas recomendaciones nacen de la comparativa externa y de las reglas NCM y de
eficiencia solicitadas por el programador. Estado: **implementadas y verificadas
offline**, no una promesa de calidad de producción.

| ID | Alcance | Estado y criterio de aceptación |
|---|---|---|
| **R15** | Contenido completo, documentos, CLI y persistencia | **Hecho**: HTML/PDF/TXT/MD/CSV/DOCX/PPTX/XLSX con hash/localización; RAG local híbrida; CLI Markdown/JSON; checkpoints idempotentes y reanudación sin repetir trabajo. |
| **R16** | Conectores, NCM, paralelismo y privacidad | **Hecho**: SearXNG/arXiv/PubMed/Semantic Scholar; MCP stdio con allowlist/timeouts; NCM residual con hashes y paralelismo determinista; presupuestos; políticas de egreso y estado Fernet. |
| **R17** | Routing, poda, caché y subsistema neural opt-in | **Hecho**: routing heurístico declarado, poda con métricas, caché exacta/semántica opt-in, vectores INT4/INT8; destilación, LoRA, cuantización/poda de pesos, MoE, speculative decoding y VQ con modelos pequeños reales. |

**Evidencia común:** **1290/1290 tests**, ruff 0, preflight 0, docs-check OK;
`pypdf 6.21.4` y `cryptography 50.0.2` en `requirements.lock`;
`torch==2.15.0` en el extra `ml` y su lock; `pip-audit` no encontró
vulnerabilidades conocidas en ese lock. Las pruebas reales de Ollama se
omitieron por servidor ausente. No se ejecutó RACE/FACT oficial ni un benchmark
real de calidad de modelos de producción; eso permanece como validación externa
opt-in, no como resultado afirmado.

Comandos de aceptación adicionales:

```bash
python3 -m unittest tests.test_documents tests.test_research_state \
  tests.test_research_cli tests.test_concept_ncm tests.test_parallel_research \
  tests.test_privacy tests.test_efficiency tests.test_neural_concepts
make verify-install
python3 -m tests.benchmarks.external --dataset query.jsonl --kind drb \
  --provider mock --max-tasks 1 --json
```

## 11. Validación de citas, fuentes y recuperación (2026-10-31)

| ID | Alcance | Estado y criterio de aceptación |
|---|---|---|
| **R18** | Verificación de citas y calidad de fuentes | **Hecho**: `citation_verifier.py` separa existencia y soporte, detecta fragmentos ausentes y duplica URLs; `source_quality.py` publica dimensiones separadas sin nota única. Aceptación: tests offline y límites declarados. |
| **R19** | Medición RAG y calibración | **Hecho**: Recall@1/3/5/10, MRR y nDCG@10 sobre 10 pasajes/16 consultas; ECE añadido al Brier simulado. Aceptación: `python3 -m tests.benchmarks.rag_retrieval` y `tests/test_calibracion_confianza.py`. |
| **R20** | Discriminación del evaluador | **Hecho**: holdout sintético de 6 proyectos y 9 relaciones de orden; evita confundir README con calidad y tamaño con calidad. Aceptación: 9/9 y `tests/test_evaluador_holdout.py`. |
| **R21** | Validación externa real | **Pendiente declarada**: 100 repositorios reales con evaluación humana independiente y re-medición Windows/macOS. No se sustituye con fixtures sintéticas ni se presenta como hecho. |

Evidencia: **1287/1287 tests**, holdout 9/9, RAG Recall@5 0.938/MRR 0.906,
calibración simulada Brier 0.1166/ECE 0.1437 (**no calibrada**), cobertura
82,57% líneas/82,42% ramas. Registro: `docs/metricas-calidad.json`.
