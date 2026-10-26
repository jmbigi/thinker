# Recomendaciones de mejora de thinker

**Fecha:** 2026-10-22, actualizado el **2026-10-26**. **Base:** commit `38f8839`
más las decisiones del programador del 2026-10-25, la release `0.1.11` publicada
y el refuerzo de aserciones del preflight del 2026-10-26.
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
| **Parcial** | R3. [Parcial 2026-10-26; decisión C] Medir mutación del evaluador y preflight | Preflight: 967/1016, 49 equivalencias y 0 brechas; evaluador: 4352/5984, 1632 brechas, 0 timeouts; triaje 1681/1681 | Medio-alto | Medio |
| **Hecho** | R9. [Cerrada 2026-10-24] Publicar 0.1.4 | Publicada en TestPyPI y PyPI; tag `v0.1.4`; 842/842 | Medio | Medio |
| **Hecho** | R4. [Cerrada 2026-10-26, alcance offline] Benchmark de precisión/recall del evaluador | 57 casos/26 criterios con 5 trampas y 1,00/1,00; 3 N/A declaradas (red/PyPI/entrada real) | Medio | Bajo |
| **Hecho** | R5. [Cerrada 2026-10-25, A] Alcance Python explícito y bloqueo de comparabilidad | `cobertura.comparable`; Java/JS no comparable; 2 tests | Alto | Alto |
| **Hecho** | R6. [Cerrada 2026-10-25, C con warnings] Política para silencios deliberados de producción | Marca externa con motivo; warnings en c3/preflight; 5 tests | Bajo | Político |
| **Hecho** | R7. [Cerrada 2026-10-25] Medir calidad de aserciones, no solo tests no-op | `aserciones_debiles` informativo; c5 no cambia | Medio | Bajo |
| **Hecho** | R8. [Cerrada 2026-10-22] Versionar el esquema JSON del informe | `schema_version: 2` y test de contrato | Bajo | Bajo |
| **Hecho** | R10. [Cerrada 2026-10-25] Reportar licencias de dev/opcionales sin mezclarlas con runtime | `licencias_no_runtime` informativo; h5 sigue siendo runtime | Bajo | Bajo |
| **Hecho** | R13. [Cerrada 2026-10-25, B+C] CoVe con verificador barato y descomposición opt-in | 1+1 llamadas; claim compuesto detectado; 28/14 en R4 | Medio | Medio |
| **Hecho** | R14. [Cerrada 2026-10-25, por declaración; B+C piloto] Declarar `credibility`/`confidence` no calibradas | Brier simulado 0,1166; piloto real n=20 Brier 0,0540; sin calibración general | Medio | Bajo |

**Estado de decisiones (2026-10-26):** R5-A, R6-C, R13-B/C y R14-B/C
implementadas; R3-C en ejecución (preflight 49: 49 equivalencias y 0 brechas; evaluador 1632; 0 timeouts). **R4 se cierra por alcance offline**: 26/29
criterios medidos y 3 N/A declaradas, no una validación global. R3 es la deuda
P1 y sigue abierta.
R1, R2, R4, R5, R6, R7, R8, R9, R10, R11, R12, R13 y R14 están cerradas.

### 1.1 Decisiones del programador (2026-10-25)

| ID | Decisión | Estado | Siguiente paso |
|---|---|---|---|
| **R5** | **A**: alcance Python explícito y bloqueo de comparabilidad | **Implementada y cerrada** | Hecho: `cobertura.comparable` y tests |
| **R6** | **C con warnings**: estricto para thinker; marca externa con motivo, reportada como warning | **Implementada y cerrada** | Hecho: warnings en c3/preflight |
| **R13** | **B con vía a C**: verificador barato; descomposición después | **B y C implementadas; cerrada** | Hecho: descomposición opt-in |
| **R14** | **B con vía a C**: Brier offline simulado; datos reales después | **B y C (piloto n=20); declaración vigente** | Ampliar muestra; no afirmar calibración general |
| **R3** | **C**: test-first, luego triaje; reporte parcial honesto hasta cerrar | En ejecución; preflight 49 equivalencias y 0 brechas, evaluador 1632, 0 timeouts | Reforzar 1632 aserciones; timeouts ya en 0 |
| **R4** | Sin decisión de producto; ampliar cobertura | **Cerrada por alcance offline** (57 casos/26 criterios; 3 N/A) | Campaña real con red/PyPI queda opt-in y fuera de alcance |

**No queda ninguna decisión de producto pendiente.** Lo que falta es ejecución. R14 ya tiene un piloto real n=20; ampliar la muestra
no cambia su cierre por declaración. R3 no se cierra hasta que las 1632
brechas de aserción estén resueltas; los timeouts ya están en 0 tras la
re-medición.

## 2. Estado medido (evidencia de partida)

| Señal | Valor | Cómo se midió |
|---|---:|---|
| Suite completa | **994/994** en Linux 3.11.9 (2026-10-26) | `python3 -m unittest discover -s tests -q` |
| CI local (última copia limpia) | **OK** | copia limpia del árbol (HEAD + diff); `make ci` usa `rm -rf` en el temporal |
| Lint / preflight / docs-check | **0 / 0 / OK** | `ruff check .`, `scripts/preflight.py`, `scripts/check_docs.py` |
| Autoevaluación con red | **1.000** (28/30; 93% de cobertura; N/A `e1`/`e2`) | `python3 evaluar_proyecto.py . --ejecutar-tests --json` |
| Lock `openai` | **3.37.0** con hashes (2026-10-22) | `requirements.lock` |
| Autoevaluación sin red | **1.000** (25/29; N/A `v4`, `h5`, `e1`, `e2`) | `python3 evaluar_proyecto.py . --sin-red --json` |
| Cobertura `evaluar_proyecto.py` | **91%** (145/1571 sentencias sin ejecutar) | comando de la sección 8 |
| Cobertura `scripts/preflight.py` | **93%** (26/425) | comando de la sección 8 |
| Mutación global | **95,2%** (3635/3819; 2026-10-24) | `make mutation`; **excluye** evaluador y preflight |
| Mutación preflight | **95,18%** (967/1016; 49 supervivientes, 0 timeouts; 2026-10-26) | `python3 scripts/mutacion.py --objetivo preflight` |
| Mutación evaluador | **72,73%** (4352/5984; 1632 supervivientes, 0 timeouts; 2026-10-26) | `python3 scripts/mutacion.py --objetivo evaluar` |
| Paquete publicado | **0.1.11** (2026-10-25; TestPyPI y PyPI) | `pyproject.toml` / `docs/PUBLICACION.md` |

Lectura: el proyecto está sano en tests, CI y cobertura (91% en evaluador y
preflight). La deuda principal que queda es la **mutación** de esos dos
módulos (R3); R4 se cerró por alcance offline (26/29; 3 N/A).

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

### R3 — Medir mutación del evaluador y preflight — PARCIAL 2026-10-26 (decisión C)

- **Decisión 2026-10-25: C.** Test-first, luego triaje; reporte parcial con el
  número de no triados; no cerrar hasta 0 sin tests y 0 supervivientes sin
  triaje. En ejecución.
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
- **Evaluador (2026-10-26, batch r3c):** **5984 mutantes, 4352 muertos,
  1632 supervivientes, 0 sin tests, 0 timeouts**, 0 sospechosos; tasa bruta
  **72,73%** (4352/5984). El contrato exacto de `informe_texto` y
  `detectar_comando_tests`, junto con los tests de `--sin-red` y `cwd`, mató
  504 mutantes; el contrato de `evaluar_herramientas`/`evaluar_calidad` mató
  134 más; el de `evaluar_vigencia`/`_dependencias_pyproject` mató 144;
  eficiencia/funcionalidades y ramas nuevas, 142; silencios/h5/h6/vigencia
  con red y licencias PyPI, 176; parser/runner/inteligencia, 77 más. La
  parsers/linter, 112 más. La campaña mantiene 0 timeouts.
- **Triaje de inventario (2026-10-26):** **1681/1681** casos con categoría:
  **1632 brechas de aserción** (0 preflight + 1632 evaluador), **0 sin
  cobertura**, **49 equivalencias demostradas** y **0 timeouts**. Detalle y
  razones en `docs/TRIAGE-R3.md` y `docs/TRIAGE-EQUIVALENCIAS.md`. No es una
  tasa limpia: 1632 siguen sin matar.
- **Límite:** los denominadores no se mezclan con el 95,2% del núcleo ni entre
  sí. La mejora del preflight no autoriza a presentar el evaluador como sano.
- **Criterio de aceptación:** [x] evaluador medido; [x] comando reproducible
  empaquetado; [x] 0 mutantes sin categoría de triaje (1681/1681); [x] 0
  timeouts (re-medido); [ ] tasa limpia (1632 aserciones pendientes).
- **Riesgo:** medio; el triaje del evaluador sigue siendo la deuda principal.

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
  offline simulado (0,1166, 16 pares) y piloto real con OpenRouter:
  **n=20, Brier 0,0540, 20/20 aciertos**, modelo de fallback
  `cohere/north-mini-code:free`.
- **Límite:** la muestra real es pequeña y fácil (hechos evidentes); no prueba
  calibración general. No se presenta `confidence` como probabilidad.
- **Evidencia:** `tests/benchmarks/calibracion_real.py`,
  `tests/test_calibracion_real.py` (2 tests), suite **902/902**, ruff 0.
- **Criterio:** [x] declaración; [x] Brier simulado; [x] Brier real n=20;
  [ ] muestra representativa/intervalos (trabajo futuro).
- **Riesgo:** bajo; el piloto se declara como piloto, no como certificado.

## 5. Deuda pendiente priorizada (2026-10-25)

**Abierta:** R3-C (parcial).
**Cerradas:** R1, R2, R4, R5, R6, R7, R8, R9, R10, R11, R12, R13 y R14. Una
recomendación abierta es deuda solo si tiene un criterio de aceptación
medible; las limitaciones declaradas del README no se cuentan como deuda.

| Orden | ID | Prioridad | Deuda | Próximo paso concreto | Criterio de aceptación | Esfuerzo |
|---|---|---|---|---|---|---|
| 1 | **R3** | **P1 / C** | Mutación del evaluador y preflight (parcial) | Test-first, luego triaje; reforzar 1632 aserciones (0 timeouts) | Comando reproducible; 0 mutantes sin categoría; 1632 brechas resueltas; 0 timeouts re-medidos; tasa con denominador y exclusiones | Medio-alto |

**Orden:** R3-C es la única deuda P1 abierta; R4 se cerró por alcance offline.
R5-A, R6-C, R13-B/C y R14-B/C están implementadas; R14-C es un piloto real
n=20, no una calibración general.

- **R3 no requiere decisión de producto**: R3-C es P1 y sigue abierta; no se
  cierra con 1632 brechas.
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
| R3 (2026-10-26) | `preflight`, `mutacion`/`triaje_mutantes`, `evaluar_proyecto` y `code_design_improvement_tools` | preflight 967/1016, 49 equivalencias y 0 brechas; evaluador 4352/5984, 1632 brechas, 0 timeouts; autoevaluación offline 1.000 (25/29, 86,2% cobertura) sin hallazgos; el análisis estático no reportó defectos → se reforzaron aserciones, no se refactorizó; el triaje dirigió los clusters y detectó `_es_main`, e1/e2 | 92 tests nuevos en la suite (preflight, evaluador y salvaguardas), 2 campañas re-medidas, triaje 1681/1681, 0 timeouts; suite 994/994 |
| R4 | `evaluar_proyecto` y `tests/benchmarks` | 57 casos (5 trampas), 26 criterios, 26 TP/0 FP/0 FN, 1,00/1,00; c4/h4/v3/i1-i6/e1-e3 añadidos; encontró y corrigió dos defectos e1/e2 | `test_evaluador_precision` |
| R7 | `evaluar_proyecto` | `aserciones_debiles` + 2 tests; c5 sin cambios | suite 902/902 (cierre); 994/994 actual |

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
declaradas). **Pendiente de ejecución:**

1. **R3-C:** preflight 0 brechas reales (967/1016; 95,18%; 49 equivalencias) y
   evaluador 1632 brechas (4352/5984; 72,73%), con **0 timeouts** y
   triaje 1681/1681. Queda reforzar 1632 aserciones; no cerrar hasta 0 brechas.

R14-C completó un piloto real n=20 (Brier 0,0540); ampliar la muestra para
afirmar calibración general sigue siendo trabajo futuro. R1, R2, R5, R6, R7,
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
