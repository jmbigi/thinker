# Recomendaciones de mejora de thinker

**Fecha:** 2026-10-22. **Base:** commit `7152838` (estado previo a la revisión
Windows y al cierre de R1).
**Alcance:** recomendaciones abiertas, no una lista de deseos. Cada una nace de
una medición de este repositorio o de la campaña de evaluación externa y lleva
su criterio de aceptación. Lo ya cerrado no se repite como si estuviera
pendiente.

## 1. Resumen ejecutivo

| Prioridad | Recomendación | Por qué ahora | Esfuerzo | Riesgo |
|---|---|---|---|---|
| **Hecho** | R1. [Cerrada 2026-10-22] Actualizar el lock de `openai` y re-verificar la autoevaluación | Lock 3.37.0 con hashes; autoevaluación con red 1.000 | Bajo | Bajo |
| **P1** | R2. Subir la cobertura de `evaluar_proyecto.py` y `preflight.py` | 83% / 87% (84% combinado); hay ramas de error sin prueba | Medio | Bajo |
| **P1** | R3. Medir mutación del evaluador y preflight | La mutación global excluye ambos módulos; 94,7% no los cubre | Medio-alto | Medio |
| **P2** | R4. Benchmark reproducible de precisión/recall del evaluador | La evidencia actual es una campaña puntual, no una regresión automática | Medio | Bajo |
| **P2** | R5. Decidir el alcance Java/JS (soporte real o límite explícito) | Cobertura 10/29 y 12/29; un 1.000/0.692 no es comparable | Alto | Alto |
| **P2** | R6. Política para silencios deliberados de producción | c3 marca 97 en Hypothesis; son reales para P1.26 pero no accionables sin política | Bajo | Político |
| **P2** | R7. Medir calidad de aserciones, no solo tests no-op | `assert True` pasa c5; c5 no mide fuerza de la suite | Medio | Bajo |
| **P3** | R8. Versionar el esquema JSON del informe | v2 cambió campos (`N/A`, `cobertura`, `global_nota`) sin `schema_version` | Bajo | Bajo |
| **P3** | R9. Publicar 0.1.4 tras R2–R3 | Hay cambios nuevos en `main` pero el paquete sigue en 0.1.3 | Medio | Medio |
| **P3** | R10. Reportar licencias de dev/opcionales sin mezclarlas con runtime | h5 solo puntúa runtime; el riesgo de dev no se ve | Bajo | Bajo |

**Orden recomendado:** R2 → R4 → R3 → R8 → R9; R5, R6, R7 y R10 se
deciden después de R2–R4. R1 está cerrada (2026-10-22) y R9 es rutina
verificable; R5 y R6 requieren decisión del programador y no deben hacerse «por
inercia».

## 2. Estado medido (evidencia de partida)

| Señal | Valor | Cómo se midió |
|---|---:|---|
| Suite completa | **750/750** en Windows 11 (3.12.7/3.14.3); 747/747 en la última medición Linux (3.11/3.12) | `python3 -m unittest discover -s tests -q` |
| CI local (última copia limpia) | **OK** | `make ci` sobre `48c5a41`; no repetido en Windows (bash/make no disponibles allí) |
| Lint / preflight | **0 / 0** | `ruff check .`, `python3 scripts/preflight.py` |
| Autoevaluación con red | **1.000** (27/27; 28/28 con `--ejecutar-tests`; 2 N/A) | `python3 evaluar_proyecto.py . --json` |
| Lock `openai` | **3.37.0** con hashes (2026-10-22) | `requirements.lock` |
| Autoevaluación sin red | **1.000** (v4/h5 N/A) | `python3 evaluar_proyecto.py . --sin-red --json` |
| Cobertura `evaluar_proyecto.py` | **83%** (188/1136 sentencias sin ejecutar) | comando de la sección 8 |
| Cobertura `scripts/preflight.py` | **87%** (50/371) | comando de la sección 8 |
| Mutación global | **94,7%** (3581/3780; histórica) | `make mutation`; **excluye** evaluador y preflight |
| Paquete publicado | **0.1.3** | `pyproject.toml` / `docs/PUBLICACION.md` |

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

- **Problema medido:** 83% en `evaluar_proyecto.py` y 87% en
  `scripts/preflight.py`. Las líneas sin cubrir incluyen ramas de error de
  PyPI, licencias desconocidas, manifiestos malformados, imports condicionales,
  `package-lock`, errores de sintaxis y rutas del CLI.
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
  fuera de `source_paths` se excluyen de la campaña). El 94,7% histórico **no
  cubre** el código nuevo del evaluador.
- **Acción:** campaña de mutación separada para evaluador/preflight, con el
  mismo protocolo de triaje: aplicar mutante → test debe fallar → restaurar →
  test debe pasar. Registrar supervivientes y clasificar equivalentes con razón.
  No mezclar su denominador con el 94,7% del núcleo.
- **Criterio de aceptación:** comando reproducible; línea base documentada;
  0 mutantes sin ejecutar; 0 supervivientes sin triaje; tasa declarada con su
  denominador y exclusiones.
- **Riesgo:** medio; mutmut puede requerir aislar imports y puede ser lento.

### R4 — Benchmark de precisión/recall del evaluador (P2, medio)

- **Problema medido:** la auditoría de 7 repos y el control de 10 defectos fueron
  una campaña puntual. No hay un arnés que impida volver a introducir falsos
  positivos como los de h6 (853 en FastAPI) o h5 (12/12).
- **Acción:** convertir el control en un benchmark determinista y offline con
  etiquetas por criterio y trampas: imports en docs, tests anidados, helpers,
  tests no-op reales, `license_expression`, imports opcionales, proyectos
  multilingües y locks. Salida JSON con TP/FP/FN por criterio. Los clones de
  terceros no se versionan; se usan solo como campaña manual opt-in.
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

### R8 — Versionar el esquema JSON (P3, bajo)

- **Problema medido:** el informe v2 añadió `cobertura`, `no_aplica`,
  `global_nota` y permite `global: null`. Un consumidor que asuma el esquema
  anterior puede romperse sin aviso.
- **Acción:** añadir `"schema_version": 2` al nivel superior; documentar los
  campos y su significado; probar el contrato con un test que falle si cambia
  sin versión.
- **Criterio de aceptación:** JSON con versión; documentación de campos;
  consumidores actualizados o declarados incompatibles.
- **Riesgo:** bajo.

### R9 — Publicar 0.1.4 tras R2–R3 (P3, medio)

- **Problema medido:** `main` tiene cambios desde 0.1.3 (evaluador v2) pero el
  paquete publicado sigue en 0.1.3. No se debe publicar solo porque hay commits:
  primero hay que cerrar cobertura/mutación y verificar (el lock ya está
  cerrado).
- **Acción:** seguir `docs/PUBLICACION.md`: bump de versión, actualizar README/
  AGENTS, construir, `twine check`, instalar en venv limpio desde el artefacto,
  subir a TestPyPI y PyPI, tag anotado y release por la web (sin `gh`, regla 12).
- **Criterio de aceptación:** `pip install thinker-research==0.1.4` en venv
  limpio; `evaluate-project --help` y una evaluación de humo; suite 750/750
  (Windows 3.12.7/3.14.3; Linux en verde); tag y release verificados.
- **Riesgo:** medio; una release no se deshace.

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

## 5. Orden de trabajo y dependencias

1. **R1** (lock) — desbloquea una autoevaluación 1.000 honesta.
2. **R2** (cobertura) — asegura que R3 y R4 miden sobre código ejercitado.
3. **R4** (benchmark) — fija la línea base de precisión/recall.
4. **R3** (mutación) — mide fuerza real; puede revelar tests débiles de R2.
5. **R8** (schema) — antes de que más consumidores usen el JSON.
6. **R9** (release) — solo con R1–R3 cerrados y CI limpio.
7. **R5, R6, R7, R10** — decisiones de producto/alcance; no bloquean R1–R4.

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

## 7. Decisiones que requieren al programador

1. **R5:** ¿se invierte en Java/JS o se declara el alcance Python? Recomendación:
   declarar alcance ahora; invertir solo con demanda real.
2. **R6:** ¿c3 estricto o marca `# noqa: silent` con motivo? Recomendación:
   estricto para thinker; la marca solo si un proyecto externo la necesita.
3. **R9:** ventana de release 0.1.4 y si se publica en TestPyPI antes.
4. **R1 (cerrada):** se actualizó `openai` a 3.37.0; el canario y la suite
   pasan.

## 8. Verificación reproducible

Sin red (tests, lint, preflight, autoevaluación offline):

```bash
python3 -m unittest discover -s tests -q
ruff check .
python3 scripts/preflight.py
python3 evaluar_proyecto.py . --sin-red --json
make ci                 # exporta HEAD a una copia limpia
```

Cobertura de evaluador/preflight:

```bash
COVERAGE_FILE=/tmp/coverage-eval \
  python3 -m coverage run --source=. -m unittest tests.test_evaluar_proyecto tests.test_preflight
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
