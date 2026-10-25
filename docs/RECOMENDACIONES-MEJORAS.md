# Recomendaciones de mejora de thinker

**Fecha:** 2026-10-22, actualizado el **2026-10-23**. **Base:** commit `19dbbd2`
más los arreglos de la auditoría del Hallazgo 97 (sin publicar).
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
| **P1** | R2. Subir la cobertura de `evaluar_proyecto.py` y `preflight.py` (parcial) | 90% / 91% (83% combinado); faltan ramas de error | Medio | Bajo |
| **P1** | R3. Medir mutación del evaluador y preflight | La mutación global excluye ambos módulos; 95,2% no los cubre | Medio-alto | Medio |
| **Hecho** | R9. [Cerrada 2026-10-24] Publicar 0.1.4 | Publicada en TestPyPI y PyPI; tag `v0.1.4`; 842/842 | Medio | Medio |
| **P2** | R4. Benchmark completo de precisión/recall del evaluador | El corpus cubre regresiones conocidas; falta TP/FP/FN por criterio | Medio | Bajo |
| **P2** | R5. Decidir el alcance Java/JS (soporte real o límite explícito) | Cobertura 10/29 y 12/29; un 1.000/0.692 no es comparable | Alto | Alto |
| **P2** | R6. Política para silencios deliberados de producción | c3 marca 97 en Hypothesis; son reales para P1.26 pero no accionables sin política | Bajo | Político |
| **P2** | R7. Medir calidad de aserciones, no solo tests no-op | `assert True` pasa c5; c5 no mide fuerza de la suite | Medio | Bajo |
| **Hecho** | R8. [Cerrada 2026-10-22] Versionar el esquema JSON del informe | `schema_version: 2` y test de contrato | Bajo | Bajo |
| **P3** | R10. Reportar licencias de dev/opcionales sin mezclarlas con runtime | h5 solo puntúa runtime; el riesgo de dev no se ve | Bajo | Bajo |
| **P3** | R13. CoVe con descomposición de claims y verificador más barato | La literatura 2026 documenta la asimetría de la verificación | Medio | Medio |
| **P3** | R14. Calibrar `credibility`/`confidence` o declararlas no calibradas | Restringir la salida evita texto inventado, no garantiza probabilidad correcta | Medio | Bajo |

**Orden recomendado:** R2 → R3; R4, R5, R6, R7, R10 y R13 se deciden después
de R2–R3. R1, R8, R9, R11 y R12 están cerradas; R5, R6 y R13 requieren
decisión del programador y no deben hacerse «por inercia».

## 2. Estado medido (evidencia de partida)

| Señal | Valor | Cómo se midió |
|---|---:|---|
| Suite completa | **849/849** en Linux 3.11.9 (2026-10-24) | `python3 -m unittest discover -s tests -q` |
| CI local (última copia limpia) | **OK** | copia limpia del árbol (HEAD + diff); `make ci` usa `rm -rf` en el temporal |
| Lint / preflight / docs-check | **0 / 0 / OK** | `ruff check .`, `scripts/preflight.py`, `scripts/check_docs.py` |
| Autoevaluación con red | **1.000** (28/30; 93% de cobertura; N/A `e1`/`e2`) | `python3 evaluar_proyecto.py . --ejecutar-tests --json` |
| Lock `openai` | **3.37.0** con hashes (2026-10-22) | `requirements.lock` |
| Autoevaluación sin red | **1.000** (25/29; N/A `v4`, `h5`, `e1`, `e2`) | `python3 evaluar_proyecto.py . --sin-red --json` |
| Cobertura `evaluar_proyecto.py` | **90%** (149/1435 sentencias sin ejecutar) | comando de la sección 8 |
| Cobertura `scripts/preflight.py` | **91%** (35/385) | comando de la sección 8 |
| Mutación global | **95,2%** (3635/3819; 2026-10-24) | `make mutation`; **excluye** evaluador y preflight |
| Paquete publicado | **0.1.5** (2026-10-24; TestPyPI y PyPI) | `pyproject.toml` / `docs/PUBLICACION.md` |

Lectura: el proyecto está sano en tests y CI, pero la calidad del **evaluador**
no está medida con la misma fuerza que el núcleo: cobertura incompleta en ramas
de error y ausencia de campaña de mutación. Esa es la deuda principal.

## 3. Lo que ya está cerrado (no reabrir sin nueva evidencia)

No se recomienda volver a trabajar en esto; ya tiene tests y evidencia:

- h6 limitado al código del paquete, con `src/`, pyproject/PEP 735, setup.cfg,
  setup.py, requirements anidados, `TYPE_CHECKING`, opcionales y `if __name__`.
- h5 con `license_expression` PEP 639, clasificador OSI y `unverified` cuando
  no hay metadato.
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

### R2 — Subir la cobertura del evaluador y preflight (P1, medio)

- **Problema medido (actualizado 2026-10-24):** **90%** en `evaluar_proyecto.py`
  (149/1435 sentencias sin ejecutar) y 91% en `scripts/preflight.py` (35/385);
  83% combinado. Las líneas sin cubrir incluyen ramas de error de PyPI,
  licencias desconocidas, manifiestos malformados, imports condicionales,
  `package-lock`, errores de sintaxis y rutas del CLI. El corpus adversario
  subió el evaluador de 83% a 86% (2026-10-23) y los 17 tests del 2026-10-24
  (11 del evaluador y 6 de preflight, incluidos alias pywin32, exclusiones
  por prefijo, `--ignorar` e imports hermanos) lo llevaron a 90%, con
  preflight en 91%; el objetivo combinado sigue sin alcanzarse.
- **Acción:** añadir tests honestos para esas ramas; cada test debe fallar con
  el comportamiento anterior. No perseguir el 100% a costa de tests triviales.
  Objetivo inicial: **≥90% en cada archivo** y **≥90% combinado**.
- **Criterio de aceptación:** informe de cobertura reproducible; ramas de error
  declaradas o cubiertas; suite completa en verde; documentar el comando y el
  resultado.
- **Riesgo:** bajo; el riesgo real es escribir tests que solo ejecutan líneas y
  no comprueban comportamiento.

### R3 — Medir mutación del evaluador y preflight (P1, medio-alto)

- **Problema medido:** `make mutation` mide el núcleo, pero excluye
  `evaluar_proyecto.py` y `scripts/preflight.py` (los tests que los importan
  fuera de `source_paths` se excluyen de la campaña). El 95,2% actual **no
  cubre** el código del evaluador ni el de preflight.
- **Acción:** campaña de mutación separada para evaluador/preflight, con el
  mismo protocolo de triaje: aplicar mutante → test debe fallar → restaurar →
  test debe pasar. Registrar supervivientes y clasificar equivalentes con razón.
  No mezclar su denominador con el 95,2% del núcleo.
- **Criterio de aceptación:** comando reproducible; línea base documentada;
  0 mutantes sin ejecutar; 0 supervivientes sin triaje; tasa declarada con su
  denominador y exclusiones.
- **Riesgo:** medio; mutmut puede requerir aislar imports y puede ser lento.

### R4 — Benchmark de precisión/recall del evaluador (P2, medio)

- **Problema medido:** la auditoría de 7 repos y el control de 10 defectos fueron
  una campaña puntual. No hay un arnés que impida volver a introducir falsos
  positivos como los de h6 (853 en FastAPI) o h5 (12/12).
- **Estado 2026-10-23:** **parcialmente cerrada**. `tests/test_evaluador_corpus.py`
  convierte en contrato 4 regresiones reales del Hallazgo 97 (Poetry exacta,
  requirements sueltos como falso lock, prosa de README como runner y comando
  válido detectado). Falta el benchmark completo con TP/FP/FN por criterio.
- **Acción (pendiente):** convertir el control en un benchmark determinista y
  offline con etiquetas por criterio y trampas: imports en docs, tests
  anidados, helpers, tests no-op reales, `license_expression`, imports
  opcionales, proyectos multilingües y locks. Salida JSON con TP/FP/FN por
  criterio. Los clones de terceros no se versionan; se usan solo como campaña
  manual opt-in.
- **Criterio de aceptación:** control 10/10; 0 falsos positivos en las trampas
  etiquetadas; resultados reproducibles byte a byte; el benchmark falla si
  reaparece una regresión conocida.
- **Riesgo:** bajo; el riesgo es sobreajustar el benchmark a los casos ya vistos.

### R5 — Decidir el alcance Java/JS (P2, alto)

- **Problema medido:** Testcontainers Java tiene 10/29 criterios y QA JS 12/29;
  no hay AST de Java/JS, ni comparación npm/Maven, ni aserciones de esos
  lenguajes. El 1.000/0.692 es «todo lo aplicable pasó», no calidad global.
- **Acción:** elegir una de dos:
  1. **Alcance explícito (recomendado ahora):** declarar que el evaluador es
     para Python y que Java/JS solo reciben señales genéricas; impedir rankings
     entre coberturas distintas y mostrar la advertencia en el informe.
  2. **Soporte real (solo si hay demanda):** parsear Gradle/Maven/npm,
     lockfiles y tests con aserciones; añadir fixtures y controles.
- **Criterio de aceptación (opción 1):** el informe no presenta un global
  comparable si la cobertura es baja; documentado y probado. (Opción 2): tests
  de dependencias, locks y aserciones para cada ecosistema, con control de
  falsos positivos.
- **Riesgo:** alto; prometer paridad multi-lenguaje sin AST sería peor que
  declarar el límite.

### R6 — Política para silencios deliberados de producción (P2, bajo)

- **Problema medido:** c3 marca 97 silencios en Hypothesis. Muchos son
  defensivos (`except OSError: pass` al borrar un archivo temporal), pero P1.26
  prohíbe silencios. El informe es correcto; la acción no es obvia.
- **Acción:** decisión del programador, no automática:
  - **Opción A (recomendada para este proyecto):** mantener c3 estricto y
    corregir o justificar cada silencio en el proyecto evaluado.
  - **Opción B:** permitir una marca explícita `# noqa: silent` con motivo
    obligatorio, y que c3 la reporte como «silencioso aceptado», nunca la ignore
    en silencio.
- **Criterio de aceptación:** política escrita; tests de la marca (si B);
  ningún `except: pass` desaparece del informe sin trazabilidad.
- **Riesgo:** político; una marca mal usada puede convertirse en un bypass.

### R7 — Medir calidad de aserciones, no solo tests no-op (P2, medio)

- **Problema medido:** c5 detecta tests que no pueden fallar (`pass`,
  `print(1+1)`), pero `assert True` y tautologías pasan. c5 no mide la fuerza de
  la suite y no debe presentarse como si lo hiciera.
- **Acción:** añadir una señal separada de «aserción débil» para constantes
  obvias (`assert True`, `assert 1`, comparaciones de una constante consigo
  misma) y documentar que la fuerza real se mide con mutación. No convertirla
  en fallo automático sin revisar falsos positivos.
- **Criterio de aceptación:** fixtures con `assert True`, property tests y
  helpers; 0 falsos positivos en los casos válidos; el informe distingue
  «no-op» de «débil» y no promete cobertura.
- **Riesgo:** medio; la detección sintáctica de tautologías es limitada.

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
  `pip check` limpio. La GitHub Release con artefactos queda como tarea manual
  desde la web (regla 12).
- **Criterio de aceptación:** [x] `pip install thinker-research==0.1.4` en venv
  limpio; [x] `evaluate-project --help` y evaluación de humo; [x] suite
  **842/842** en Linux; [x] tag verificado. Windows queda pendiente de
  re-verificación con esta suite.
- **Riesgo:** cerrado; una release no se deshace.

### R10 — Licencias de dev/opcionales visibles, fuera del score runtime (P3, bajo)

- **Problema medido:** h5 solo consulta dependencias runtime. Las de desarrollo
  y opcionales no se ven, aunque también se distribuyen en el repositorio y
  pueden afectar a la reproducibilidad/licencias.
- **Acción:** añadir una sección informativa `licencias_no_runtime` con ámbito
  y fuente, sin cambiar la puntuación h5 (que sigue siendo runtime). Si no hay
  red, declararlo `unverified`.
- **Criterio de aceptación:** informe separado; no mezcla con el score; tests de
  un proyecto con extra no libre.
- **Riesgo:** bajo.

### R11 — Gate documental (P3, bajo) — CERRADA 2026-10-23

- **Problema medido:** las cifras de estado presente derivaban entre auditorías
  (`747` con la suite en 750; `25/27` con 4 N/A; `verify_install.py` eliminado
  pero citado en presente). Detectarlo dependía de una revisión manual.
- **Acción ejecutada:** `scripts/check_docs.py` (offline, read-only) contrasta
  el nº de tests declarado en `AGENTS.md` y `docs/EVALUACIONES.md` con el
  conteo estático por AST, los pines de `requirements.txt` con
  `requirements.lock` (y los rangos), y la versión de `pyproject.toml` con la
  publicada en `docs/PUBLICACION.md`. Integrado en `make check` y en el hook
  pre-commit; 10 tests propios. Códigos 0/1/2 (cuadra/discrepancia/no
  verificable).
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
  declarado que sí se detecta. Complementa a R4 (benchmark completo pendiente).
- **Criterio de aceptación:** [x] cada caso falla con el comportamiento
  anterior; [x] sin red ni escrituras fuera del temporal.
- **Riesgo:** bajo.

### R13 — CoVe con descomposición de claims y verificador más barato (P3, medio)

- **Origen:** la literatura 2026 documenta la **asimetría de la verificación**
  (clasificar es más fácil que generar, así que un verificador más pequeño
  puede bastar) y la **descomposición de claims** en subpreguntas verificables
  ([Zylos Research](https://zylos.ai/research/2026-04-10-llm-as-judge-production-agent-verification-2026/),
  [DeepVerifier, arXiv 2601.15808](https://arxiv.org/pdf/2601.15808)).
- **Estado actual:** thinker ya ofrece `llm_verificador` separado, declara la
  independencia real y marca `discrepancia_muestreo`; lo que falta es un
  ejemplo/helper de verificador barato y la descomposición de claims
  compuestos.
- **Acción propuesta (opt-in):** (a) documentar y probar un verificador de
  modelo más barato en la segunda pasada; (b) descomponer claims con varias
  afirmaciones en subpreguntas y registrar cada subveredicto; (c) mantener la
  discrepancia para revisión humana, nunca silenciosa.
- **Criterio de aceptación:** benchmark offline con `MockLLM` donde un claim
  compuesto que la pasada monolítica dejaba pasar se detecta al descomponerlo;
  coste en llamadas declarado; sin red por defecto.
- **Riesgo:** medio; más llamadas implican más coste y latencia, por eso es
  opt-in y no un defecto.

### R14 — Calibrar `credibility`/`confidence` o declararlas no calibradas (P3, medio)

- **Origen:** un ensayo sobre diversificación arquitectónica (2026) recuerda que
  restringir la salida a un esquema elimina la alucinación de **formato libre**,
  pero **no garantiza que la probabilidad asignada a la opción correcta sea la
  más alta**. La fuente de producto que cita no se pudo verificar en esta sesión
  (cuota de búsqueda), así que aquí se adopta el principio, no sus cifras
  (ver `docs/REFERENCIAS-IA.md` §4).
- **Problema medido:** `EvidenceEvaluator` pide `credibility` y `confidence` al
  modelo y los normaliza a [0,1], pero nadie comprueba que estén calibrados:
  un 0,9 puede no corresponder a un 90% de acierto.
- **Acción propuesta (offline, sin dependencias):** benchmark con casos
  etiquetados y un `MockLLM` que devuelva confianzas conocidas; calcular
  **Brier score** y una tabla de fiabilidad por tramos (0–0,2, …, 0,8–1,0).
  Con los datos reales (opt-in) repetir sobre un conjunto pequeño y declarar el
  resultado. Si la calibración es mala, documentarlo en el README y no
  presentar `confidence` como probabilidad.
- **Criterio de aceptación:** informe reproducible con Brier y tabla de
  fiabilidad; el README/AGENTS declara si `confidence` está calibrada o no;
  ningún texto del proyecto la presenta como probabilidad sin esa medición.
- **Riesgo:** bajo; el riesgo es interpretar mal una muestra pequeña, que se
  declara como tal.

## 5. Orden de trabajo y dependencias

1. **R1** (lock) — desbloquea una autoevaluación 1.000 honesta.
2. **R2** (cobertura) — asegura que R3 y R4 miden sobre código ejercitado.
3. **R3** (mutación) — mide fuerza real; puede revelar tests débiles de R2.
4. **R4** (benchmark completo) — amplía el corpus ya cerrado a TP/FP/FN.
5. **R8, R11 y R12 (cerradas):** esquema JSON v2, gate documental y corpus
   adversario ya están en el repositorio con tests.
6. **R9 (cerrada):** `0.1.4` está publicada en TestPyPI y PyPI, con tag
   `v0.1.4` y artefactos verificados; la GitHub Release queda como tarea
   manual desde la web.
7. **R5, R6, R7, R10, R13 y R14** — decisiones de producto/alcance; no bloquean
   R1–R4.

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

## 7. Decisiones que requieren al programador

1. **R5:** ¿se invierte en Java/JS o se declara el alcance Python? Recomendación:
   declarar alcance ahora; invertir solo con demanda real.
2. **R6:** ¿c3 estricto o marca `# noqa: silent` con motivo? Recomendación:
   estricto para thinker; la marca solo si un proyecto externo la necesita.
3. **R9:** ventana de release 0.1.4 y si se publica en TestPyPI antes.
4. **R13:** ¿se adopta el verificador barato y la descomposición de claims como
   piloto opt-in? Recomendación: sí, con benchmark offline y coste declarado;
   nunca como defecto sin medir el coste en llamadas.
5. **R14:** ¿se mide la calibración de `credibility`/`confidence` o se declara
   directamente no calibrada? Recomendación: medir con Brier offline y
   declararlo; no presentar confianza del modelo como probabilidad.
6. **R1, R8, R11 y R12 (cerradas):** lock 3.37.0, esquema JSON v2, gate
   documental y corpus adversario; el canario y la suite pasan.

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
