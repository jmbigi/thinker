# Evaluaciones de proyecto (thinker como evaluador)

Fecha: 2026-10-16. Herramienta: `python3 evaluar_proyecto.py RUTA`.

**Estática y read-only** por defecto: no escribe en el proyecto evaluado ni ejecuta
su código. Lo único que lo ejecuta es `--ejecutar-tests` (opt-in explícito, P0.8),
siempre con el **comando que el propio proyecto declara** (target `test:` del
Makefile → comando citado en su script/README → convención `unittest discover` si
existe `tests/`), con timeout y salida capturada.

Criterios: 6 dimensiones × 3-7 criterios binarios (hasta 30), según lo que aplique.
Puntuación de dimensión = criterios cumplidos / criterios evaluados; global = media.

## Qué produce, en capas

1. **Medición** por dimensión, con evidencia por hallazgo (`archivo:línea`, comando
   o fuente de la comprobación). Lo que no se verifica se declara en
   `no_verificado`; nunca se supone.
2. **Plan de mejora derivado de las métricas** (determinista): cada propuesta nace
   de un criterio incumplido y lleva sitios afectados, esfuerzo estimado,
   **secuencia** (p. ej. fijar versiones → generar lockfile) y la verificación
   exacta. Se ordena por prioridad → secuencia → esfuerzo.
3. **Síntesis del modelo** (opt-in `--sintesis-llm`, coste 0 con `:free`):
   propuestas de fondo (diseño, algoritmos, riesgos) a partir del informe MEDIDO.
   Control mecánico anti-invención: cada propuesta se marca `con_respaldo` solo si
   la evidencia que cita aparece en la evidencia medida. Lo que el modelo no puede
   decidir se declara en `preguntas_abiertas` (no se inventa).
4. **Investigación de las dudas** (opt-in `--investigar`): resuelve esas preguntas
   con búsqueda real (reutiliza `web_search`), citando fuentes; si no hay
   resultados o falla la red, se declara.

Garantías: del historial git solo fechas y recuentos (nunca autores, P0.9); el
contenido evaluado son DATOS (P0.13); ninguna cifra que alimente una decisión
lleva tope oculto.

## thinker (autoevaluación)

| Dimensión | Puntuación | Criterios fallidos |
|---|---|---|
| Funcionalidades | 1.00 | — |
| Calidad | 1.00 | — (suite `make test` OK, 1,0 s) |
| Vigencia | 1.00 | `v4_dependencias_al_dia` (lock en 3.40.0) |
| Herramientas | 1.00 | — (licencias de sus 6 dependencias, libres) |
| Inteligencia | 1.00 | — |
| Eficiencia | 1.00 | — |
| **Global** | **1.000** | |

**Con red**: 1.000 (28/30 criterios, 27/27 con `--ejecutar-tests`; 2 N/A: `v4`,
`h5`). Suite **1220/1220** en Linux (Python 3.11.9), ruff 0, preflight 0,
docs-check OK; autoevaluación posterior a Hallazgo 105 con contrato de
aseveraciones exactas y triaje de mutación completado.

**Sin red**: 1.000 (25/29; 4 N/A: `v4`, `h5`, `e1`, `e2`). Suite **750/750** en
Windows 11 (Python 3.12.7/3.14.3) y **778/778** en Linux (3.11/3.12, 2026-10-23);
ruff 0, preflight 0, docs-check OK.

`no_verificado`: **vacío** (2026-10-25). Migración de `openai` a rango
`>=1.0,<4` completada (lock en 3.40.0); `v4_dependencias_al_dia` al día con
hashes `requirements.lock`. No hay hallazgos pendientes de verificación.

**Actualización 2026-10-17** (tras corregir 6 bugs ALTA —Hallazgo 71— y aplicar
ese pendiente): autoevaluación **GLOBAL 1.000** (Vigencia 1.00, `v4` incluido),
`no_verificado` vacío y **sin plan de mejora** («nada que proponer»). Evidencia:
`python3 evaluar_proyecto.py . --ejecutar-tests`; licencias de las 4
dependencias consultadas en PyPI.

**Actualización 2026-10-17 (pase de coherencia — Hallazgo 72)**: de nuevo
**GLOBAL 1.000**, `no_verificado` vacío y sin plan de mejora. El propio
evaluador resultó útil como control: una primera pasada quedó en 0.925 porque
`c3_sin_silencios` cazó un `except`/`continue` recién introducido en
`deep_research_system._parse_json_response` (P1.26) y porque `--sin-red` deja
`v4_dependencias_al_dia` sin verificar (no verificado ⇒ fallo, coherente con
P0.1). Corregido el patrón y re-ejecutado con red: 1.000. Evidencia:
`python3 evaluar_proyecto.py . --ejecutar-tests`.

**Actualización 2026-10-20 (tres criterios nuevos — Hallazgo 78)**: el evaluador
añade `h6_imports_declarados` (imports de terceros deben estar en el manifiesto;
gate AST reutilizado de `scripts/preflight.py`), `c5_tests_con_aserciones` (toda
función `test_*` debe poder fallar) y `h7_decisiones_documentadas` (señal, no
veredicto). Aplicarlos al propio repo halló 3 tests sin aserciones en
`test_plugin_system.py` (corregidos con aserciones reales; uno llevaba un
comentario que contradecía el comportamiento por diseño del registro de plugins).
Autoevaluación con los criterios nuevos en OK: `python3 evaluar_proyecto.py .
--sin-red --ejecutar-tests` (calidad y herramientas 1.00; vigencia 0.75 offline
por `v4`, como siempre sin red). Suite: 524/524. Mutación re-medida el mismo
día: **78,0%** (2957/3789; 0 timeouts, 0 sospechosos, 0 sin ejecutar), con un
delta de −65 muertos respecto a la del 2026-10-19 a fuentes idénticas — causa
no determinada, declarada en el Hallazgo 80. Ese mismo día, con red y el lock
ya en openai 3.35.1: **GLOBAL 1.000**, `no_verificado` vacío y «nada que
proponer» (`python3 evaluar_proyecto.py . --ejecutar-tests`), `make vuln-scan`
sin vulnerabilidades y OpenRouter real 3/3 (Hallazgo 81).

**Actualización 2026-10-20 (triaje de mutación — Hallazgo 84)**: los 832
supervivientes de la medición 78,0% quedaron procesados uno a uno (6 agentes
en paralelo, protocolo apply → test FALLA → restore → test PASA): ~650
muertos con **177 tests nuevos honestos** (suite: 524 → **701/701** en 3.11
y 3.12) y el resto clasificados como mutantes equivalentes con su razón.
Re-medición oficial: **94,1% (3567/3789; 0 timeouts, 0 sospechosos, 0 sin
ejecutar)**. El triaje destapó 4 trampas de mutmut 3.6.0 (apply mal
emplazado en métodos con nombre repetido, `.pyc` stale, contaminación entre
applies paralelos, aserciones en helpers invisibles para `c5`) — documentadas
con sus reglas derivadas en el Hallazgo 84. Mismo día: Ollama real 3/3 con
`qwen3:1.7b` local (antes sin verificar por falta de servidor), autoevaluación
con red **GLOBAL 1.000** y OpenRouter real 3/3 re-verificados, y `make ci`
en copia limpia OK.

**Actualización 2026-10-21 (limpieza de código muerto y distribución —
Hallazgo 85)**: corregidas las 4 anomalías que el triaje señaló (firmas
muertas en `thinking_engine`, dead store, literal duplicado,
`UnicodeDecodeError` no capturado) y la métrica muerta `max_nesting`
implementada de verdad. Suite 703/703 en 3.11 y 3.12; mutación re-medida:
**94,7% (3570/3769; 199 supervivientes, 0 timeouts, 0 sospechosos)** — el
total baja de 3789 a 3769 porque el código muerto eliminado ya no genera
mutantes. Cobertura de los 6 módulos mutados re-verificada al 100% tras los
cambios. Paquete renombrado a `thinker-research` (el nombre `thinker` está
ocupado en PyPI desde 2017): build + `twine check` PASA y distribución sin
keys operativa vía tag `v0.1.0` (instalación `git+...@v0.1.0` verificada en
venv limpio); guía durable en `docs/PUBLICACION.md`. Hallazgo operativo:
la cuenta autenticada en la CLI de GitHub no tenía escritura en el repo
(los permisos se verifican por API antes de prometer una GitHub Release).
Barrido
completo del mismo día: autoevaluación con red **GLOBAL 1.000**, `make ci`
OK, vuln-scan limpio, 4 tests honestos + 3 demos offline OK, benchmark de
consenso detectando el caso divergente (`detectado: true`).

**Actualización 2026-10-21 (revisión de coherencia — Hallazgos 86–88)**:
revisión de los 7 commits de las últimas 12 h. Corregida la métrica
`max_nesting` (`elif` ya no suma nivel; `try/except*` y `match` cuentan como
bloques) con 3 tests nuevos. Suite **706/706 en 3.11 y 3.12** (3.12.3, venv
aislado creado desde el lock, openai 3.35.1), cobertura 100% en los 6
módulos mutados y mutación **94,7% (3581/3780; 199 supervivientes, 0 timeouts,
0 sospechosos; los 11 mutantes nuevos se matan)**. Ruff 0, preflight 0,
`make ci` en copia limpia de HEAD OK y copia limpia del árbol con los cambios
706/706 OK; `make vuln-scan` limpio, demos y tests honestos OK. README
actualizado a 94,7% y `openai 3.35.1`; distribución aclarada como
`thinker-research`; handle de la CLI de GitHub anonimizado en `PUBLICACION.md`.
Autoevaluación con red: **GLOBAL 1.000**, `no_verificado` vacío y «nada que
proponer». Los artefactos `0.1.0` quedan intactos (coinciden con el tag
`v0.1.0`). La corrección se preparó como `0.1.1`, se etiquetó y empujó
(`v0.1.1`), pero sus textos aún decían «tag pendiente» y el wheel incluía
esa contradicción; no se publicó en PyPI. Se preparó `0.1.2` con la
documentación corregida, tag anotado, build desde el tag y `twine check`
PASSED; publicación pendiente de token (Hallazgo 89).

**Actualización 2026-10-21 (release 0.1.3 — Hallazgos 90–91)**: `0.1.2` no
se publicó porque su README empaquetado decía «PyPI pendiente» y la ficha
habría sido contradictoria. Se preparó y publicó `0.1.3` solo de
documentación: README durable, guía sin CLI de GitHub y versión actualizada.
Verificación local: suite **706/706**, ruff 0, preflight 0, build + `twine
check` PASSED (wheel y sdist), METADATA `Version: 0.1.3` y sin frases
transitorias. Publicación: TestPyPI instalable; PyPI JSON 200 con versión
`0.1.3`, wheel y sdist con los hashes de `dist/`; instalación limpia desde
PyPI con imports OK, `evaluate-project --help` OK y `pip check` limpio. El
primer `pip install` con la configuración por defecto no vio la versión; con
el índice oficial y `--no-cache-dir` sí (Hallazgo 91). `0.1.2` queda como tag
de git; `0.1.3` es la versión publicada.

**Actualización 2026-10-20 (post-empaquetado — Hallazgo 82)**: tras hacer el
proyecto instalable (`pip install .`, comando `evaluate-project`), la
autoevaluación con red sigue en **GLOBAL 1.000**, `no_verificado` vacío y «nada
que proponer» (`python3 evaluar_proyecto.py . --ejecutar-tests`). El
empaquetado no cambió ningún criterio: el manifiesto (`pyproject.toml`) ya
declaraba las dependencias y `h1`/`v1` lo leen igual.

**Actualización 2026-10-17 (cobertura y mutación — Hallazgo 73)**: de nuevo
**GLOBAL 1.000**, sin plan de mejora y `no_verificado` vacío. Evidencia:
463/463 tests en 5 entornos (3.11/3.12; openai 1.109.1/2.54.0/3.33.0),
cobertura 100% en los seis módulos mutados, mutación **78,1%** (2766/3543;
0 timeouts, 0 sin ejecutar), `make ci` en copia limpia y `make vuln-scan` sin
vulnerabilidades conocidas. Comando: `python3 evaluar_proyecto.py .
--ejecutar-tests`.

**Actualización 2026-10-19 (evidencia + preflight — Hallazgo 74)**: de nuevo
**GLOBAL 1.000**, sin plan de mejora y `no_verificado` vacío, ahora con la
línea `Evidencia: [VERIFIED-REAL] 0 | [VERIFIED-SYNTHETIC] 0 | [UNVERIFIED] 0`
(cada hallazgo del informe lleva su marcador de procedencia). Además, el
preflight determinista da **OK (0 hallazgos)** sobre el repositorio. Evidencia:
**500/500 tests en Python 3.11** (openai 1.109.1), ruff limpio, demos offline 0,
preflight 0, `python3 evaluar_proyecto.py . --ejecutar-tests` con salida
anterior. La re-verificación en 3.12 y openai 2.54/3.33 queda pendiente;
mutación no re-medida (los seis módulos de `source_paths` no cambiaron).

**Actualización 2026-10-19 (separación generador/verificador — Hallazgo 75)**:
de nuevo **GLOBAL 1.000**, sin plan de mejora y `no_verificado` vacío. La
segunda pasada CoVe admite un **verificador de proveedor separado**
(`llm_verificador`) y declara la independencia real por claim; sin separación
queda declarada `mismo-proveedor` en el `decision_log`. Evidencia:
**505/505 tests** en Python 3.11 (openai 1.109.1 y 2.54.0) y 3.12 (openai
3.33.0, venv aislado desde `requirements.lock`), ruff limpio, preflight 0,
demos offline 0, `test_systems_honest`/`kilo`/`env` 0. Mutación re-medida:
**79,9%** (2863/3582; 0 timeouts, 0 sospechosos) — ver Hallazgo 75 en
`docs/LECCIONES-APRENDIDAS.md`.

**Actualización 2026-10-19 (pilotos: phase-chain freeze y consenso por
muestreo — Hallazgo 76)**: de nuevo **GLOBAL 1.000**, sin plan de mejora y
`no_verificado` vacío. Pilotos opt-in verificados: `congelar_fases` (fases
inmutables con hash, declarado no aplicable a ToT) y `muestras_consenso>1`
(discrepancias marcadas para revisión humana) con benchmark dedicado:
detección `true` en caso divergente, `falso_positivo: false` en acuerdo y
coste 3 llamadas / 2 extra declaradas. Evidencia: **517/517 tests** en Python
3.11 (openai 1.109.1 y 2.54.0) y 3.12 (openai 3.33.0), ruff limpio, preflight
0, demos offline 0. Mutación re-medida: **79,8%** (3022/3789; 0 timeouts,
0 sospechosos, 0 sin ejecutar) — ver Hallazgo 76.

**Actualización 2026-10-19 (revisión y puesta al día del entorno — Hallazgo
77)**: de nuevo **GLOBAL 1.000**, sin plan de mejora y `no_verificado` vacío.
La pasada con `--sin-red` dio 0.958 solo por `v4_dependencias_al_dia` (sin red
⇒ no verificado ⇒ fallo; comportamiento del instrumento ya documentado en el
Hallazgo 72, no una regresión); con red, 1.000 y licencias de las 4
dependencias consultadas en PyPI. La deriva real estaba en el **entorno
instalado**, no en el repo: `requirements.txt`/`requirements.lock` ya fijaban
`requests==2.34.2` y `python-dotenv==1.2.4` (aplicado el 2026-10-17, Hallazgo
71), pero el entorno seguía en 2.33.0/1.2.2; alineado con
`python3 -m pip install --require-hashes -r requirements.lock`. Evidencia:
**517/517 tests** con las versiones nuevas, ruff limpio, preflight 0, demos
offline 0, `make vuln-scan` sin vulnerabilidades conocidas.

## better-ocr (evaluación externa, tras aplicar mejoras)

| Dimensión | Puntuación | Criterios fallidos |
|---|---|---|
| Funcionalidades | 1.00 | — |
| Calidad | 0.80 | `c3_sin_silencios` |
| Vigencia | 0.50 | `v1_dependencias_fijadas`, `v2_lockfile` |
| Herramientas | 0.80 | `h2_licencia` |
| Inteligencia | 0.83 | `i1_cachea_trabajo_repetido` |
| Eficiencia | 0.67 | `e1_import_perezoso_de_pesadas` |
| **Global** | **0.767** | (era 0.708 antes de las mejoras) |

`no_verificado`: **vacío** (su suite de 475 tests se ejecutó: OK en 43,4 s).
Aplicado en su repo (commit `0d19182`): lint en 0 avisos, los silencios que el
informe listaba, claves de dict duplicadas y **dos bugs reales** (`NameError` en la
ruta `--vision ollama`; anotación `pd.DataFrame` sin import). Quedan 32 silencios
`except: pass/continue` (mayoría defensivos: limpiezas y filas corruptas), la
licencia (decisión del programador), fijar dependencias + lockfile, caché e import
perezoso.

## Defectos del propio instrumento encontrados al usarlo (corregidos)

1. Comparaba los `archivo.py` del README contra nombres base (las rutas con carpeta
   figuraban como inexistentes).
2. Contaba «TODO REAL» (regla de dominio de better-ocr) como deuda técnica.
3. `python-dotenv` como «sin licencia libre» (declara BSD-3-Clause en texto libre,
   sin clasificador OSI): ahora se reconocen licencias libres habituales.
4. Dependencias contadas dos veces entre manifiestos: se deduplican prefiriendo `==`.
5. El listado de hallazgos tenía tope de 20 y `sitios` subestimaba (20 vs 37
   silencios): ahora se listan todos y la cuenta nunca se oculta.

## Límites declarados

- Las licencias se consultan en PyPI (metadatos que declara el paquete).
- Los imports de terceros **sin declarar** se detectan por AST (`h6_imports_declarados`,
  desde 2026-10-20, reutilizando el gate de `scripts/preflight.py`); el límite que
  queda: los imports **dinámicos** (`importlib`/`__import__`) no son visibles para
  el análisis estático.
- La ejecución de la suite es opt-in y corre el comando tal cual lo declara el
  proyecto.
- Las partes cualitativas de Calidad e Inteligencia se aproximan con señales
  estructurales; el juicio final sigue siendo humano. `h7_decisiones_documentadas`
  (desde 2026-10-20) es una de esas señales: que exista un registro de decisiones
  no dice si las decisiones son buenas.

## Actualización 2026-10-21 (evaluador v2 — Hallazgo 94)

La auditoría de 7 repositorios externos encontró falsos positivos y decisiones
poco útiles: h6 analizaba tests/docs/ejemplos, h5 ignoraba `license_expression`
(PEP 639), c5 marcaba tests anidados o que delegan en helpers, c3 contaba
silencios de tests, se perdían `setup.cfg`, `package.json`, locks y
`requirements/*.txt`, y el plan reutilizaba la evidencia de toda la dimensión.
El evaluador v2 corrige esas causas y **declara N/A** los criterios que el
perfil del proyecto no puede verificar; N/A no cuenta como fallo.

### Cambios verificables

- **Perfil**: lenguajes, manifiestos, locks, tests, dependencias por ámbito
  (runtime/dev/docs/test/opcional) y primera parte con layout `src/`.
- **h6**: solo código del paquete; excluye tests/docs/scripts/ejemplos,
  `TYPE_CHECKING`, imports opcionales, `if __name__ == "__main__"` y flags
  `has_*`; lee pyproject (PEP 621/735, Poetry/PDM), setup.cfg/setup.py,
  requirements anidados con `-r` y package.json.
- **h5**: `license_expression` SPDX > clasificador OSI > campo `license`.
  Desconocido se marca `unverified`, no «no libre».
- **c5**: solo tests de módulo/clase; un test que llama a un helper, usa un
  decorador/fixture/setUp o espera una excepción no es no-op. Solo se marcan
  tests que no pueden fallar (`pass`, `print(1+1)`).
- **c3**: solo código de producción; tests e imports opcionales fuera.
- **Manifiestos/locks**: PEP 735, setup.cfg, package.json, requirements
  anidados, uv/poetry/Pipfile/package-lock y pip-compile; v4 usa la versión
  resuelta por lock cuando el manifiesto usa rangos.
- **h4/f1/h7**: build.sh, npm/Gradle/Maven/tox/nox; `if __name__` con comillas
  simples, `__main__.py`, `console_scripts` y `bin`; CHANGES/HISTORY/ADR en
  `.rst`/`.md`/`.txt` anidados.
- **Plan**: cada propuesta cita solo hallazgos de su criterio y declara
  `datos_medidos` (hallazgos/evidencias).

### Resultados sobre los mismos clones (con red, 2026-10-21)

| Repo | Global v1 | Global v2 | Cobertura v2 | h6 v1 → v2 | c5 v1 → v2 |
|---|---:|---:|---:|---:|---:|
| FastAPI | 0.723 | **0.825** | 20/29 (media) | 853 → **0** | 4/18 → **0** |
| Flask | 0.626 | **0.887** | 20/29 (media) | 104 → **0** | 8/18 → **0** |
| Httpie | 0.572 | **0.602** | 20/29 (media) | 88 → **3** | — → **0** |
| Hypothesis | 0.572 | **0.887** | 20/29 (media) | 919 → **0** | 226/771 → **0** |
| Requests | 0.529 | **0.700** | 20/29 (media) | 34 → **0** | — → **0** |
| Testcontainers Java | 0.408 | **1.000** | **10/29 (baja)** | 0 (N/A) | 0 (N/A) |
| QA exercises (JS) | 0.289 | **0.692** | **12/29 (baja)** | 0 (N/A) | 0 (N/A) |

`—` en c5 significa que el audit no desglosó tests anidados para ese repo; el
0 de la columna v2 sí se midió con el evaluador nuevo.

Lectura honesta: el global es la media de criterios **aplicables**; en Java/JS
solo se evaluaron 10/12 de 29, así que un 1.000/0.692 **no es comparable** con
los proyectos Python (cobertura media). Las 3 entradas de h6 de Httpie son
imports directos de `urllib3`, dependencia transitiva de requests no declarada
por Httpie: el hallazgo es real, no un falso positivo de docs. Los v4 en rojo
de FastAPI/Flask son versiones del lock por detrás de PyPI (p. ej. FastAPI:
`starlette 1.7.0 → 1.9.0`, `pydantic 2.13.5 → 2.14.1`); Hypothesis queda al día
gracias a sus `requirements/*.txt` compilados. Requests/Httpie no tienen lock:
v4 se declara no verificado, no «al día».

### Autoevaluación de thinker

- **Con red: 1.000** (27/27 criterios sin `--ejecutar-tests`; 28/28 con él;
  2 N/A). Histórico del 2026-10-21:
  0.958 con `v4_dependencias_al_dia` en rojo por `openai 3.35.1 → 3.36.0`
  (el lock fijaba 3.35.1). Resuelto el 2026-10-22: el lock se actualizó primero
  a 3.36.1 y, al publicar PyPI 3.37.0 durante la revisión, a 3.37.0 con hashes;
  `v4` en OK y autoevaluación 1.000. La primera pasada de ese día dio 0.967
  porque c3 leía `_local_debug/`; se excluyó ese directorio local (Hallazgo
  96) y quedó 1.000.
- **Sin red: 1.000** (25/29; `v4`, `h5`, `e1` y `e2` N/A, no fallos).
- Suite: **750/750** en Windows 11 (Python 3.12.7/3.14.3, 2026-10-22) y
  **778/778** en la última medición Linux (3.11/3.12, 2026-10-23); ruff 0;
  preflight 0; docs-check OK. El
  control con defectos plantados sigue detectando los 10 defectos y el control
  de rangos sigue fallando v4 sin consultar PyPI.

**Actualización 2026-10-23** (tras la auditoría de la actividad del
2026-10-16 al 2026-10-22 — 50 commits, `17798f7..HEAD`, Hallazgo 97):
autoevaluación **1.000 con red** (27/29,
cobertura 93%, N/A: `e1`/`e2`) y **1.000 sin red** (25/29; 4 N/A: `v4`, `h5`,
`e1`, `e2`). Suite **778/778** en Linux (Python 3.11.9 y 3.12.3, venv desde el
lock); ruff 0; preflight 0; `scripts/check_docs.py` OK. Añadidos en la misma
sesión: corpus adversario del evaluador (4 casos, R12), gate documental con
10 tests (R11) y mutación re-medida tras el triaje: **95,2% (3635/3819; 184
supervivientes, 0 timeouts, 0 sospechosos)**.

**Actualización 2026-10-23 (modo `--requisitos`)**: nuevo modo opt-in que
contrasta una lista Markdown de requisitos contra el código y los tests.
Veredictos `CUMPLE` (suite verde), `CUBIERTO` (evidencia estática), `NO CUMPLE`
y `NO VERIFICABLE`; el informe es aparte y no altera el GLOBAL. 17 tests
nuevos; Suite **795/795** en Linux (Python 3.11.9), ruff 0, preflight 0 y
`scripts/check_docs.py` OK. Formato y límites: `docs/REQUISITOS.md`.

**Actualización 2026-10-23 (auditoría de cambios)**: nuevo
`scripts/audit_changes.py`, un auditor opt-in, offline y read-only de diffs.
Marca rutas sensibles/CI, tests modificados o eliminados, skips, asserts
eliminados, matchers flojos, supresiones, cobertura rebajada, configuración
relajada, dependencias nuevas, requisitos modificados, comandos peligrosos y
presupuesto excedido; veredictos `OK`/`REVISAR`/`BLOQUEAR`. 28 tests nuevos
del auditor y 9 del runner de holdout; 4 tests holdout independientes con
manifiesto de hashes. Suite **832/832** en Linux (Python 3.11.9), ruff 0,
preflight 0 y `scripts/check_docs.py` OK; hook y `make ci` ejecutan auditor y
holdout. Reglas y límites: `docs/AUDITORIA-CAMBIOS.md`.

### Límites que permanecen

- Java/JS solo se evalúan con criterios genéricos (manifiesto, licencia, CI,
  tests, ratio, lock); no hay AST de Java/JS ni comparación npm/Maven.
- h6 es estático: imports dinámicos (`importlib`) y dependencias transitivas no
  declaradas pueden quedar fuera; los 3 de Httpie se conservan a propósito.
- c3 sigue marcando silencios deliberados de producción (p. ej. Hypothesis);
  son reales según P1.26, aunque el proyecto los considere defensivos.
- c5 es un heurístico de no-op, no una medida de mutación: un test con
  `assert True` pasa c5 y puede ser inútil.
- No se ejecutaron suites de terceros en esta campaña; el estado pass/fail de
  los 7 repos sigue sin verificar.

Las recomendaciones abiertas, su prioridad y sus criterios de aceptación están
en `docs/RECOMENDACIONES-MEJORAS.md`.

**Actualización 2026-10-24 (evaluación integral y dos arreglos — Hallazgo 98)**:
autoevaluación con red **1.000** (28/30; 93%), `no_verificado` vacío y
`[UNVERIFIED] 0`; sin red **1.000** (25/29; 4 N/A: `v4`, `h5`, `e1`, `e2`).
Suite **842/842** en Linux (Python 3.11.9), ruff 0, preflight 0, docs-check OK
y copia limpia del árbol (HEAD + diff) 842/842. Mutación re-medida: **95,2% (3635/3819; 184
supervivientes, 0 timeouts, 0 sospechosos, 0 sin ejecutar)**, igual que el
2026-10-23; los 10 tests nuevos (8 del evaluador, 2 de preflight) están en archivos excluidos de la campaña y los
módulos mutados no cambiaron. Dos defectos corregidos: (1)
`--sintesis-llm/--investigar` no cargaba `.env` y fallaba aunque la clave
estuviera presente; ahora `cargar_entorno_llm()` la carga solo en esos modos y
falla con un mensaje claro si falta; (2) los criterios N/A se contaban como
evidencia `[UNVERIFIED]` (1 con todos los criterios en OK); ahora la nota vive
en `cobertura.nota_no_aplicables` y `no_verificado` queda vacío. Cobertura:
`evaluar_proyecto.py` **90%** (149/1432 sentencias sin ejecutar; antes 86%),
`scripts/preflight.py` 91% (35/371), total 83%. Síntesis real con el modelo
gratuito: 4 propuestas, **0 con respaldo medido** (se declaran juicio, no
medición) y 3 preguntas abiertas. `test_openrouter_real.py` quedó **no
concluyente** por 429 repetidos del modelo gratuito y se canceló (no se usa
como evidencia). Ollama: servidor no disponible, prueba OMITIDA (no
simulada). R2 sigue abierta: el objetivo ≥90% combinado no se
alcanza (83%); R3 (mutación del evaluador y de preflight) sigue pendiente.

**Actualización 2026-10-24 (alias pywin32 y exclusiones — Hallazgo 100)**:
autoevaluación con red **1.000** (28/30; 93%), `no_verificado` vacío y
`[UNVERIFIED] 0`. Suite **846/846** en Linux (Python 3.11.9), ruff 0,
preflight 0 y docs-check OK. Cuatro tests nuevos: alias de `win32*`/`pythoncom`
a `pywin32` (antes `import win32api` se marcaba como no declarado aunque
`pywin32` estuviera en el manifiesto) y exclusiones por prefijo/sufijo para
`.venv-*`, `venv-*`, `pytest-of-*` y `*.egg-info` en evaluador y preflight
(antes se recorrían enteros; `dist` ya estaba excluido). Cobertura:
`evaluar_proyecto.py` **90%** (149/1433 sin ejecutar), `scripts/preflight.py`
**91%** (35/376), total 83%. `exe/` no se ignora a propósito: puede ser código
legítimo. La mutación no se re-mide: los módulos mutados no cambiaron y estos
dos módulos están excluidos de la campaña (95,2% vigente).

**Actualización 2026-10-24 (exclusiones configurables e imports hermanos —
Hallazgo 101)**: autoevaluación con red **1.000** (28/30; 93%),
`no_verificado` vacío y `[UNVERIFIED] 0`. Suite **849/849** en Linux (Python
3.11.9), ruff 0, preflight 0 y docs-check OK. Tres tests nuevos: `--ignorar
DIRECTORIO` en las CLI de evaluador y preflight (excluye `exe/` u otros sin
snapshot) e imports hermanos locales (`tools/a.py` puede importar
`tools/helper.py` sin manifiesto). Cobertura: `evaluar_proyecto.py` **90%**
(149/1435), `scripts/preflight.py` **91%** (35/385), total 83%. `dist/` ya
estaba excluido; `exe/` se excluye solo si se pide con `--ignorar exe`.
Publicada como `0.1.6` en TestPyPI y PyPI el 2026-10-24.

**Actualización 2026-10-24 (alias PIL/docx/pptx — Hallazgo 102)**: tres alias
reales más (`PIL`→`pillow`, `docx`→`python-docx`, `pptx`→`python-pptx`), con
test de preflight y de h6. Suite **851/851** en Linux (Python 3.11.9), ruff 0,
preflight 0 y docs-check OK; autoevaluación **1.000**, `[UNVERIFIED] 0`.
Cobertura sin cambios: 90% evaluador (149/1435), 91% preflight (35/385), total
83%. Los alias `pygetwindow`, `rapidocr_onnxruntime` y `shiboken6` **no** se
añadieron: con la distribución declarada directamente ya pasan; el caso
`shiboken6` con solo `PySide6` es dependencia transitiva y el flag es correcto.

**Actualización 2026-10-25 (revisión integral y regla 12 — Hallazgo 103)**:
corregidas dos cifras de estado que habían derivado: README declaraba 94,7%
de mutación (3581/3780) y la vigente es 95,2% (3635/3819; 2026-10-23), y la
cabecera de `docs/RECOMENDACIONES-MEJORAS.md` seguía en 2026-10-23 y «sin
publicar» cuando `0.1.7` ya estaba publicada. Se amplió la regla 12: no se usa
`gh` ni se crean GitHub Releases desde el repositorio; la distribución es
PyPI/TestPyPI y tags, y `docs/PUBLICACION.md` ya no incluye pasos de release.
También se restringió `.env` a 600 y se retiraron dos palabras duplicadas de
`STOPWORDS` (ruff B033). El gate documental contrasta ahora la cifra de
mutación de README con la vigente de AGENTS, con test de regresión.
Suite **852/852** en Linux (Python 3.11.9), ruff 0, preflight 0, docs-check OK;
autoevaluación **1.000**, `[UNVERIFIED] 0`. Cobertura sin cambios en
evaluador/preflight (90%/91%). No se re-mide la mutación: los módulos mutados
no cambiaron.

**Actualización 2026-10-25 (publicación 0.1.8 — Hallazgo 104)**: release
`0.1.8` construida desde el tag `v0.1.8` (`19020b0`) y publicada en TestPyPI y
PyPI. Wheel SHA-256
`91dd0168fda2d4e8c8d5da0d695ae06cc1a70e15bf0e87465fc1e1a49d9afa02`; sdist
`4a4f36a20746e0d03135a9c0e195cb8e521e618b7f345d4f6f7880ee00ae9f6a`; ambos
índices publican los mismos hashes. Instalación limpia
`thinker-research==0.1.8` desde TestPyPI y PyPI OK; `evaluate-project --help`,
imports OK y `pip check` limpio. El índice simple no mostraba `0.1.8` en el
primer intento aunque el JSON y los hashes ya eran correctos; tras la
propagación la instalación funcionó (Hallazgo 104). Suite **852/852** en Linux
(Python 3.11.9), ruff 0, preflight 0, docs-check OK; autoevaluación **1.000**,
`[UNVERIFIED] 0`.

**Actualización 2026-10-25 (R2 y R10 — Hallazgo 105)**: cerradas la cobertura
del evaluador/preflight y la visibilidad de licencias no runtime. Cobertura:
`evaluar_proyecto.py` **91%** (130/1466 sin ejecutar), `scripts/preflight.py`
**91%** (35/385), **91% combinado** (1686/1851), total 83%. Tests nuevos de
ramas de error (requisitos, ámbitos, TOML inválido, manifiestos no Python,
tuplas de excepciones y `OSError`) y de `licencias_no_runtime`, que informa
dev/opcionales sin tocar `h5` y marca `unverified` sin red.
Suite **858/858** en Linux (Python 3.11.9), ruff 0, preflight 0, docs-check OK;
autoevaluación **1.000**, `[UNVERIFIED] 0`. Publicada como `0.1.9` en TestPyPI
y PyPI el 2026-10-25; tag anotado `v0.1.9` (`14e2b7f`). Wheel SHA-256
`89028e4bfa69e316222ff7730964723941e74ae27d75c2ece0486c2dac528270`; sdist
`756d838ff11659c3a172a50b354c190edfbe1912747259a903febbcd046f8a81`.

**Actualización 2026-10-25 (R7 y R4 — Hallazgo 107)**: R7 añade
`aserciones_debiles` como señal informativa separada de c5 (constantes
verdaderas, comparaciones constantes que pasan y `assertTrue/assertEqual` con
literales), sin cambiar la puntuación; no marca variables, helpers ni property
tests. R4 añade `tests/benchmarks/evaluador_precision.py`: 33 casos etiquetados
sobre 14 criterios, incluidos 5 casos trampa de falsos positivos (h1, h2, h3, h6, v2, c1, c2, c3, c5, f2, f3, f4, v1, h7), con TP/FP/FN, precision y recall por
criterio y global; resultado actual **14 TP, 0 FP, 0 FN; 1,00/1,00**, con el
límite declarado de 14/29 criterios y fixtures sintéticas. Cobertura:
`evaluar_proyecto.py` **91%** (145/1571 sin ejecutar), preflight **94%**
(26/425), total 83%. Suite **902/902** en Linux (Python 3.11.9), ruff 0,
preflight 0, docs-check OK; autoevaluación **1.000** (sin red: 25/29, 2 no
verificados). R3 queda **parcial**: preflight **1015 mutantes, 696 muertos, 319
supervivientes, 0 sin tests**; evaluador **5939 mutantes, 3034 muertos, 2901
supervivientes, 0 sin tests y 4 timeouts** (tasa bruta 51,09%). Triaje de
inventario **3224/3224**: 3220 brechas de aserción, 0 sin cobertura, 0
equivalentes demostrados y 4 timeouts no equivalentes (`docs/TRIAGE-R3.md`).
La tasa sigue sin ser limpia. El arnés
`scripts/mutacion.py` (3 tests) deja ambos comandos reproducibles, pero R3 no se
cierra hasta triajar los supervivientes y resolver los timeouts. R5 añade `cobertura.comparable`,
`motivo_no_comparable` y «GLOBAL NO COMPARABLE»; Java/JS queda como no
comparable. R6 admite `# noqa: silent: motivo` como **warning** en c3 y
preflight; sin marca sigue fallando. R13-B/C mide el verificador barato y la descomposición opt-in:
1 llamada al generador, 1 al verificador y 1 extra; el claim compuesto
monolítico pasa y el descompuesto detecta la contradicción con 2 llamadas. R14 se cierra por
**declaración**: README y AGENTS dicen que `credibility`/`confidence` no están
calibradas y no se presentan como probabilidad; el Brier offline es **simulado**
(0,1166 en 16 casos) y el piloto real n=20 da **0,0540** (20/20, modelo de
fallback `cohere/north-mini-code:free`), pero la muestra es pequeña y fácil: no
prueba calibración general.

Publicada como **0.1.10** en TestPyPI y PyPI el 2026-10-25; tag anotado
`v0.1.10` (`551d693`). Wheel SHA-256
`9571519215f336bd1b1b05e5f7a9f516f64500ebde57f2e16dbd5abdf7d26caa`; sdist
`5ab2ef2cf790342b46a14af8f9161c42a3ecb6f0c0d31153dd31713902621f75`.

**Actualización 2026-10-26 (R3 preflight y evaluador — Hallazgos 116/120)**:
el refuerzo de aserciones exactas del preflight bajó los supervivientes de
**319 a 49**: **1016 mutantes, 967 muertos, 49 supervivientes, 0 sin tests, 0
timeouts, 0 sospechosos**; tasa bruta **95,18%** (antes 68,57% con 696/1015).
El triaje semántico (`docs/TRIAGE-EQUIVALENCIAS.md`) demuestra **49
equivalencias** y deja **0 brechas reales**; la tasa no cambia. El cambio
incluye un defecto real: `_es_main` aceptaba `if __name__ != "__main__"` como
guardia no runtime; ahora exige `ast.Eq` y hay regresión. El evaluador se
re-midió el 2026-10-26 tras el contrato de `informe_texto`, `detectar_comando_tests`
y los tests de red: **5984 mutantes, 4665 muertos, 1319 supervivientes, 0 sin
tests, 0 timeouts, 0 sospechosos**; tasa bruta **77,96%** (antes 51,19%).
Los contratos de dimensiones, vigencia/parser, eficiencia/funcionalidades y
ramas/licencias, parser/runner, parsers/linter y main/síntesis/eficiencia
mataron 134, 144, 142, 176, 77, 112, 115, 66 y 72 mutantes más,
respectivamente.
Triaje de inventario **1368/1368**: **1319 brechas** (0 preflight + 1319
evaluador), **49 equivalencias demostradas** y **0 timeouts**. Suite **1018/1018** en Linux
(Python 3.11.9), ruff 0, preflight 0, docs-check OK;
autoevaluación **1.000** (sin red: 25/29, 2 no verificados). R3 sigue
**parcial**: no se cierra con 1319 brechas pendientes.

R4 subió de 33 casos/14 criterios a **57 casos/26 criterios**: c4, h4, v3
(repo git temporal), i1-i6 y e1-e3, estos últimos con fixtures **sintéticas
declaradas** y sin proveedor real. Resultado: **26 TP, 0 FP, 0 FN; precision
1,00, recall 1,00**. El benchmark encontró dos defectos reales de e1/e2
(import perezoso sin paquete y ausencia de hallazgo), corregidos. Quedan **3
N/A** (f1, v4, h5) que exigen red/PyPI o un punto de entrada real. **R4 se
cierra por alcance offline**: 26/29 medidos, sin presentarse como validación
global ni como campaña real.

También se añadieron `docs/SALVAGUARDAS.md` y `tests/test_guardrails.py` (2
tests) para que la cadena de gates no desaparezca en silencio. DSH `dsh-tui`
no se modifica: `dsh plugin --profile dsh-tui list` falla con `EROFS` (perfil
de solo lectura) y los plugins citados por el documento externo devuelven
**404** en npm; no se instala nada no verificado (P0.18).

**Actualización 2026-10-28** (lock `openai` 3.40.0 + lote dirigido R3):
autoevaluación **con red 1.000** (v4 OK tras el bump; 0 hallazgos) y **sin
red 1.000**. Suite **1128/1128** en Linux (Python 3.11.9, openai 3.40.0 en el
entorno actual), ruff 0, preflight 0, docs-check OK. El lote R3 atacó los 16
supervivientes de `_verificar_test` con un test de contrato exacto de bordes:
los **16/16 mueren** verificado al estilo mutmut (cada mutante aplicado al
fuente → la clase de tests falla → restauración; diff vacío al final) y la
re-medición oficial lo confirma (batch r3c2): **5984 mutantes, 4681 muertos,
1303 supervivientes**, 0 timeouts, tasa bruta **78,23%**; `_verificar_test`
16 → 0. Segundo lote R3 (mismo día): 10 tests de contrato exacto de
`evaluar_vigencia` (v1 rangos+lock, v2 npm/multi-lock/multi-ecosistema, v3 con
repo git temporal reciente y antiguo, v4 con PyPI simulada); **80/80 mutantes
matan** en verificación estilo mutmut y 2 equivalencias demostradas
(`docs/TRIAGE-EQUIVALENCIAS.md`). La re-medición oficial (batch r3c3) lo
confirma: **5984 mutantes, 4764 muertos, 1220 supervivientes** (1218 brechas +
2 equivalencias), 0 timeouts, tasa bruta **79,61%**; `evaluar_vigencia`
82 → 2 (ambas equivalencias). Tercer lote R3 (mismo día): 16 tests de contrato
exacto de `evaluar` (firma por defecto, `ValueError` con la ruta, nota de
aserciones débiles solo en calidad, `global` con redondeo a 3 decimales,
`no_verificado` exacto, lenguajes no-Python con separador observable, bordes de
cobertura 0.500 y 0.800 alcanzables con `--ejecutar-tests` —total 30—, claves
del informe e investigación opt-in con dobles); **70/75 mutantes mueren** en
verificación estilo mutmut y 5 equivalencias demostradas (E2-E5 en
`docs/TRIAGE-EQUIVALENCIAS.md`). La re-medición oficial (batch r3c4) lo
confirma: **5984 mutantes, 4846 muertos, 1138 supervivientes** (1131 brechas +
7 equivalencias), 0 timeouts, tasa bruta **80,98%**; `evaluar` 75 → 5 (las
equivalencias). Cuarto lote (mismo día, recomendaciones externas triadas): el
banner `*** MODO DEMO OFFLINE — RESULTADOS SIMULADOS ***` en los 3 demos
—antes solo era un comentario de código—, las rutas de plugins resueltas
respecto al paquete (antes CWD: con otro directorio se descubrían 0 plugins en
silencio y ahora 6, con aviso si no existe ningún directorio),
`make verify-install` (wheel + venv temporal + 17 comprobaciones offline) y
`make doctor` (autodiagnóstico offline con presencia de claves, nunca sus
valores). Quinto lote (mismo día, quick wins restantes): 17 tests de contrato
de proveedores LLM y fallos de recuperación (JSON inválido/truncado, respuesta
vacía), 4 pruebas adversarias (claves del entorno nunca en el informe, prompt
injection tratada como dato, config YAML malformada declarada), 2 tests de
límite de CPU en `--ejecutar-tests`, 4 del escáner de secretos portable
(`scripts/scan_secrets.py`, ahora también escanea archivos nuevos sin ignorar)
y 7 del esquema público `docs/schema-v2.json` (validador mínimo sin
dependencias nuevas). Además: higiene OSS (`SECURITY.md`, `CONTRIBUTING.md`,
`CODE_OF_CONDUCT.md`, plantillas de issue/PR y PR template), sin CI en la nube
ni badge: la verificación es local, por diseño (regla 12 ampliada el
2026-10-28: no se depende de GitHub). Suite
**1128/1128**. R3 sigue **parcial**: la cifra oficial r3c4 deja 1131 brechas,
reducidas a **1067 brechas + 62 equivalencias** con el cierre del clúster
`evaluar_herramientas` (64 muertos verificados diff a diff y 6 equivalencias
nuevas, Hallazgo 144; 16 tests de contrato en `TestHerramientasContrato`).
La re-medición r3c5 quedó
**descartada**: reportó 355 supervivientes, pero la prueba directa mostró que
un mutante que declaraba «killed» (`con_red=True→False` en
`evaluar_herramientas`) **sobrevive** a la suite de la campaña — un artefacto
de mutmut que no se maquilla (P0.1). r3c6 y una re-medición aislada con pytest
8.4.2 reprodujeron el artefacto idéntico (5999/5644/355), así que no es la
versión de pytest. La cifra oficial vigente sigue siendo la de r3c4
(4846/5984; 1131 brechas + 7 equivalencias), reducida a 1067 + 62 con el
lote del Hallazgo 144; las campañas del evaluador quedan
**bloqueadas como medición** hasta aislar la causa (Hallazgo 143,
`docs/TRIAGE-R3.md`). Quinto lote (mismo día, mejoras de fondo): **benchmark
factual** de evaluación de evidencia (`tests/benchmarks/factual.py`, 30 casos
versionados —10 soportados, 10 contradichos, 10 de abstención—, métricas de
exactitud, falsos verificados y tasa de abstención; simulado por defecto con
MockLLM y `--con-llm` opt-in real; Hallazgo 145) con 5 tests del arnés, y
**cosmic-ray** validado como motor de mutación alternativo
(`scripts/mutacion_cosmic.py`, evidence.py: 61 mutantes, 51 killed, 10
supervivientes en 36 s).

**Actualización 2026-10-30** (integración de plugins con investigación):
`ResearchOrchestrator.from_plugins()` usa los proveedores activos de un registro
ya cargado, sin fallback implícito, y `plugin_registry` conecta los ocho hooks
del ciclo de investigación con un payload documentado. La API previa queda
compatible; los hooks de pensamiento y una CLI unificada quedan fuera de este
incremento. Cinco regresiones nuevas cubren proveedores activos, ausencia de
fallback, orden/payload de hooks, salida temprana y ejecución end-to-end con
los plugins mock reales. Suite **1133/1133** en Linux (Python 3.11.9), ruff 0,
preflight 0, docs-check OK; evidencia y límites en Hallazgo 146.

**Actualización 2026-10-30** (verificación de instalación): corregido el orden
de argumentos de `pip wheel` en `scripts/verificar_instalacion.py`, con una
regresión que mantiene `--wheel-dir` junto a su destino. `make verify-install`
construye e instala el wheel en un venv temporal y supera las comprobaciones
offline de módulos y console scripts. Suite **1134/1134** en Linux (Python
3.11.9), ruff 0, preflight 0, docs-check OK; evidencia en Hallazgo 147.

**Actualización 2026-10-30** (programa documental, NCM y optimización):
`documents` añade contenido completo/PDF/Office y RAG local con trazabilidad;
`research_cli` y `research_state` añaden CLI real, checkpoints y reanudación;
`web_search`/`mcp_client` añaden SearXNG, académicos y MCP stdio;
`concept_ncm` implementa jerarquía residual y paralelismo por nivel;
`privacy` añade políticas de egreso y estado Fernet; `efficiency` añade routing,
poda, caché y vectores cuantizados; `neural_concepts` valida destilación, LoRA,
cuantización/poda, MoE, speculative decoding y VQ con PyTorch. La distinción
orquestación↔modelo del paper queda explícita. Se añaden **77 tests**.
Suite **1211/1211** en Linux (Python 3.11.9), ruff 0, preflight 0,
docs-check OK. Dependencias base fijadas con hashes: `pypdf 6.21.4` y
`cryptography 50.0.2`; extra ML `torch==2.15.0` con lock propio. Prueba real
Ollama omitida por servidor ausente; las pruebas neurales usan modelos pequeños
reales en CPU y no afirman calidad de producción. Hallazgos 148-149.

**Actualización 2026-10-30** (seguridad del extra ML): `pip-audit` detectó 22
vulnerabilidades conocidas en `torch 2.5.1`; el pin y su lock se actualizaron a
`torch==2.15.0`, y la nueva auditoría no encontró vulnerabilidades conocidas.
Con el lock completo pasan los **7/7 tests neurales**.
Suite **1211/1211** en Linux (Python 3.11.9); ruff 0, preflight 0, docs-check
y holdout OK. La instalación limpia y las demos offline también pasan.
Hallazgo 150.

**Actualización 2026-10-30** (paso acotado de R3): una regresión de
`licencias_no_runtime` fija filtrado, deduplicación y conservación de errores;
detecta 4/4 mutaciones dirigidas sin cambiar el evaluador. No se atribuye una
reducción del inventario oficial ni una nueva tasa de mutación.
Suite **1212/1212** en Linux (Python 3.11.9), con tres demos offline correctas.
R3 permanece abierta. Hallazgo 151.

**Actualización 2026-10-30** (paso acotado de R3 — locks): una regresión de
`_versiones_lock` fija la exclusión de locks en `.venv`, `build` y
`node_modules`, conservando la versión del lock real. Detecta 3/3 mutaciones
dirigidas sin cambiar el evaluador. No se atribuye una reducción del inventario
oficial ni una nueva tasa de mutación.
Suite **1213/1213** en Linux (Python 3.11.9), con tres demos offline correctas.
R3 permanece abierta. Hallazgo 152.

**Actualización 2026-10-30** (paso acotado de R3 — ámbito): una regresión de
`_ambito_requirements` fija que los requirements anidados junto a
`pyproject.toml` o `setup.py` son `runtime`. Detecta 3/3 mutaciones dirigidas
sin cambiar el evaluador. No se atribuye una reducción del inventario oficial
ni una nueva tasa de mutación.
Suite **1214/1214** en Linux (Python 3.11.9), con tres demos offline correctas.
R3 permanece abierta. Hallazgo 153.

**Actualización 2026-10-30** (includes compartidos): corregido
`_leer_requirements` para conservar un set `vistos` vacío proporcionado por el
llamador, evitando releer includes en llamadas posteriores. La regresión falló
antes, pasa después y detecta 3/3 mutaciones dirigidas.
Suite **1215/1215** en Linux (Python 3.11.9), con tres demos offline correctas.
R3 permanece abierta sin cambiar su inventario oficial. Hallazgo 154.

**Actualización 2026-10-30** (sección Pipfile inválida): `_versiones_lock`
ahora avisa y omite una sección `default`/`develop` que no sea objeto, en lugar
de fallar con `AttributeError`; las entradas válidas de la otra sección se
conservan. Regresión roja antes y verde después, con 3/3 mutaciones detectadas.
Suite **1216/1216** en Linux (Python 3.11.9), con tres demos offline correctas.
R3 permanece abierta sin cambiar su inventario oficial. Hallazgo 155.

**Actualización 2026-10-30** (`packages` inválido): `package-lock.json` con una
sección `packages` que no sea objeto ahora produce un aviso y se omite, en lugar
de romper `_versiones_lock` con `AttributeError`. Regresión roja antes y verde
después, con 3/3 mutaciones detectadas.
Suite **1217/1217** en Linux (Python 3.11.9), con tres demos offline correctas.
R3 permanece abierta sin cambiar su inventario oficial. Hallazgo 156.

**Actualización 2026-10-30** (raíz JSON no objeto): `Pipfile.lock` y
`package-lock.json` con raíz no objeto ahora emiten aviso y se omiten, en lugar
de fallar en `datos.get()`. Una regresión con dos subcasos falló antes y pasa
después, con 3/3 mutaciones detectadas.
Suite **1218/1218** en Linux (Python 3.11.9), con tres demos offline correctas.
R3 permanece abierta sin cambiar su inventario oficial. Hallazgo 157.

**Actualización 2026-10-30** (grupo Poetry inválido): un grupo con
`dependencies` no objeto ahora emite aviso y se omite sin descartar los demás
grupos. La regresión conserva `tox` de `test`, falló antes y detecta 3/3
mutaciones dirigidas.
Suite **1219/1219** en Linux (Python 3.11.9), con tres demos offline correctas.
R3 permanece abierta sin cambiar su inventario oficial. Hallazgo 158.

**Actualización 2026-10-30** (comodín PEP 440): `==2.*` ya no cuenta como
versión exacta. Parser, `v1` y `v4` usan el campo `fijada`; el comodín no se
consulta literalmente en PyPI. La regresión falló antes y detecta 3/3
mutaciones dirigidas, sin cambiar criterios ni umbrales.
Suite **1220/1220** en Linux (Python 3.11.9), con tres demos offline correctas.
R3 permanece abierta sin cambiar su inventario oficial. Hallazgo 159.
