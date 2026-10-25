# Recomendaciones de mejora de thinker

**Fecha:** 2026-10-22, actualizado el **2026-10-25**. **Base:** commit `143d71b`
más los arreglos de R7/R4 y la release `0.1.9` publicada.
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
| **Hecho** | R2. [Cerrada 2026-10-25] Subir la cobertura de `evaluar_proyecto.py` y `preflight.py` | 91% / 91% (91% combinado); ramas de error cubiertas | Medio | Bajo |
| **P1** | R3. Medir mutación del evaluador y preflight | La mutación global excluye ambos módulos; 95,2% no los cubre | Medio-alto | Medio |
| **Hecho** | R9. [Cerrada 2026-10-24] Publicar 0.1.4 | Publicada en TestPyPI y PyPI; tag `v0.1.4`; 842/842 | Medio | Medio |
| **Parcial** | R4. [Parcial 2026-10-25] Benchmark de precisión/recall del evaluador | 10 casos/5 criterios con TP/FP/FN y 1.00/1.00; faltan 24 criterios y trampas reales | Medio | Bajo |
| **P2** | R5. Decidir el alcance Java/JS (soporte real o límite explícito) | Cobertura 10/29 y 12/29; un 1.000/0.692 no es comparable | Alto | Alto |
| **P2** | R6. Política para silencios deliberados de producción | c3 marca 97 en Hypothesis; son reales para P1.26 pero no accionables sin política | Bajo | Político |
| **Hecho** | R7. [Cerrada 2026-10-25] Medir calidad de aserciones, no solo tests no-op | `aserciones_debiles` informativo; c5 no cambia | Medio | Bajo |
| **Hecho** | R8. [Cerrada 2026-10-22] Versionar el esquema JSON del informe | `schema_version: 2` y test de contrato | Bajo | Bajo |
| **Hecho** | R10. [Cerrada 2026-10-25] Reportar licencias de dev/opcionales sin mezclarlas con runtime | `licencias_no_runtime` informativo; h5 sigue siendo runtime | Bajo | Bajo |
| **P3** | R13. CoVe con descomposición de claims y verificador más barato | La literatura 2026 documenta la asimetría de la verificación | Medio | Medio |
| **P3** | R14. Calibrar `credibility`/`confidence` o declararlas no calibradas | Restringir la salida evita texto inventado, no garantiza probabilidad correcta | Medio | Bajo |

**Orden recomendado:** R3; R4 y las decisiones R5/R6 después.
R1, R2, R7, R8, R9, R10, R11 y R12 están cerradas; R5, R6 y R13 requieren
decisión del programador y no deben hacerse «por inercia».

## 2. Estado medido (evidencia de partida)

| Señal | Valor | Cómo se midió |
|---|---:|---|
| Suite completa | **862/862** en Linux 3.11.9 (2026-10-25) | `python3 -m unittest discover -s tests -q` |
| CI local (última copia limpia) | **OK** | copia limpia del árbol (HEAD + diff); `make ci` usa `rm -rf` en el temporal |
| Lint / preflight / docs-check | **0 / 0 / OK** | `ruff check .`, `scripts/preflight.py`, `scripts/check_docs.py` |
| Autoevaluación con red | **1.000** (28/30; 93% de cobertura; N/A `e1`/`e2`) | `python3 evaluar_proyecto.py . --ejecutar-tests --json` |
| Lock `openai` | **3.37.0** con hashes (2026-10-22) | `requirements.lock` |
| Autoevaluación sin red | **1.000** (25/29; N/A `v4`, `h5`, `e1`, `e2`) | `python3 evaluar_proyecto.py . --sin-red --json` |
| Cobertura `evaluar_proyecto.py` | **91%** (145/1536 sentencias sin ejecutar) | comando de la sección 8 |
| Cobertura `scripts/preflight.py` | **91%** (35/385) | comando de la sección 8 |
| Mutación global | **95,2%** (3635/3819; 2026-10-24) | `make mutation`; **excluye** evaluador y preflight |
| Paquete publicado | **0.1.9** (2026-10-25; TestPyPI y PyPI) | `pyproject.toml` / `docs/PUBLICACION.md` |

Lectura: el proyecto está sano en tests, CI y cobertura (91% en evaluador y
preflight). La deuda principal que queda es la **mutación** de esos dos
módulos (R3) y el benchmark de precisión/recall (R4); no la cobertura.

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
  ejecutar), preflight **91%** (35/385), **91% combinado**. Tras R7/R4 el
  módulo crece a 1536 sentencias y sigue en **91%** (145/1536); suite
  **862/862**, ruff 0. Comando: el de la sección 8.
- **Criterio de aceptación:** [x] ≥90% en cada archivo; [x] ≥90% combinado;
  [x] ramas de error cubiertas o declaradas; [x] suite en verde; [x] comando
  reproducible documentado.
- **Riesgo:** bajo; los tests comprueban comportamiento, no solo ejecutan
  líneas.

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

### R4 — Benchmark de precisión/recall del evaluador — PARCIAL 2026-10-25

- **Problema medido:** la auditoría de 7 repos y el control de 10 defectos fueron
  una campaña puntual. No hay un arnés que impida volver a introducir falsos
  positivos como los de h6 (853 en FastAPI) o h5 (12/12).
- **Estado 2026-10-25:** **parcial**. `tests/benchmarks/evaluador_precision.py`
  ejecuta 10 casos sintéticos etiquetados sobre 5 criterios (h2, c3, c5, f3 y
  h6), calcula TP/FP/FN, precision y recall por criterio y global, y admite
  `--json`. Resultado actual: **5 TP, 0 FP, 0 FN; precision 1.00, recall 1.00**
  en esos 10 casos. `tests/test_evaluador_precision.py` fija métricas y
  balance del corpus.
- **Límite declarado:** cubre **5 de los 29 criterios posibles** y son fixtures
  sintéticas; no es una campaña sobre proyectos reales. El benchmark no debe
  presentarse como validación global del evaluador.
- **Acción pendiente:** ampliar a más criterios y trampas (imports en docs,
  tests anidados, helpers, `license_expression`, imports opcionales, proyectos
  multilingües y locks), y conservar clones reales solo como campaña manual
  opt-in.
- **Criterio de aceptación:** [x] TP/FP/FN por criterio; [x] JSON reproducible;
  [x] 0 FP en los casos etiquetados; [ ] cobertura completa de criterios;
  [ ] trampas reales adicionales.
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
  **862/862**, ruff 0; el informe distingue no-op de débil. Limitación
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

## 5. Deuda pendiente priorizada (2026-10-25)

**Abiertas:** R3, R4 (parcial), R5, R6, R13 y R14. **Cerradas:** R1, R2, R7,
R8, R9, R10, R11 y R12. Una recomendación abierta es deuda solo si tiene un
criterio de aceptación medible; las limitaciones declaradas del README no se
cuentan como deuda.

| Orden | ID | Prioridad | Deuda | Próximo paso concreto | Criterio de aceptación | Esfuerzo |
|---|---|---|---|---|---|---|
| 1 | **R3** | **P1** | Mutación del evaluador y preflight | Campaña separada de `mutmut` sobre esos dos módulos, sin mezclar su denominador con el 95,2% del núcleo | Comando reproducible; línea base; 0 mutantes sin ejecutar; 0 supervivientes sin triaje; tasa con denominador y exclusiones | Medio-alto |
| 2 | **R4** | P2 | Benchmark TP/FP/FN del evaluador (parcial) | Ampliar los 10 casos/5 criterios actuales a más criterios y trampas reales | Precisión y recall por criterio; 0 FP en trampas; cobertura completa declarada | Medio |
| 3 | **R5** | P2 | Alcance Java/JS | Decidir soporte real o límite explícito; hoy la cobertura es 10/29 y 12/29 | Decisión documentada; si se limita, el informe lo dice sin presentar el GLOBAL como comparable | Alto |
| 4 | **R6** | P2 | Silencios deliberados de producción | Política para `# noqa: silent` con motivo frente a `except: pass` real | Regla documentada; tests de ambos casos; sin falsos positivos en c3 | Bajo |
| 5 | **R13** | P3 | CoVe con descomposición de claims | Piloto opt-in con verificador más barato y coste declarado | Benchmark offline de coste/calidad; nunca como defecto sin medir llamadas | Medio |
| 6 | **R14** | P3 | Calibración de `credibility`/`confidence` | Brier y tabla de fiabilidad offline, o declararlas no calibradas | Informe reproducible; README/AGENTS no las presentan como probabilidad sin medición | Medio |

**Orden recomendado:** R3 → R4 → decisiones R5/R6 → R13/R14.

- **R3 y R4 no requieren decisión del programador**: se pueden ejecutar cuando
  haya tiempo; R3 es la deuda P1 principal.
- **R5, R6 y R13 sí requieren decisión** de producto/alcance; no deben hacerse
  «por inercia».
- **R14** puede cerrarse pronto declarando explícitamente que `confidence` no
  está calibrada, si no se va a medir Brier.
- Las cerradas R1/R2/R7/R8/R9/R10/R11/R12 no se reabren sin evidencia nueva.

**No es deuda** (son límites declarados, no defectos pendientes): que
`MockSearchAPI` no haga investigación real, los 429 de modelos gratuitos, que
la CI sea local, que macOS no se haya probado y que Windows no se haya
re-ejecutado con la suite actual.

**Regla 14 — dogfooding ≥90%:** todas las tareas de esta deuda se ejecutan con
componentes de thinker en al menos el 90% de los casos. Cada tarea se registra
así, y el registro se conserva en el informe de cierre del lote:

| Tarea | Componente de thinker | Evidencia que aportó | Verificación humana/automática |
|---|---|---|---|
| R3 | `evaluar_proyecto`/`preflight`/`mutmut` | piloto preflight: 495/949 muertos, 414 supervivientes, 40 sin tests; evaluador pendiente | campaña reproducible y triaje |
| R4 | `evaluar_proyecto` y `tests/benchmarks` | 10 casos, 5 criterios, 5 TP/0 FP/0 FN, 1,00/1,00 | `test_evaluador_precision` |
| R7 | `evaluar_proyecto` | `aserciones_debiles` + 2 tests; c5 sin cambios | suite 862/862 |

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

## 7. Decisiones que requieren al programador

1. **R5:** ¿se invierte en Java/JS o se declara el alcance Python? Recomendación:
   declarar alcance ahora; invertir solo con demanda real.
2. **R6:** ¿c3 estricto o marca `# noqa: silent` con motivo? Recomendación:
   estricto para thinker; la marca solo si un proyecto externo la necesita.
3. **R13:** ¿se adopta el verificador barato y la descomposición de claims como
   piloto opt-in? Recomendación: sí, con benchmark offline y coste declarado;
   nunca como defecto sin medir el coste en llamadas.
4. **R14:** ¿se mide la calibración de `credibility`/`confidence` o se declara
   directamente no calibrada? Recomendación: medir con Brier offline y
   declararlo; no presentar confianza del modelo como probabilidad.

R3, R4 y R7 no requieren una decisión de producto: se pueden ejecutar cuando
haya tiempo. R1, R2, R8, R9, R10, R11 y R12 están cerradas y no se reabren sin
evidencia nueva.

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
