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

**Con red**: 1.000 (30/30 criterios con `--ejecutar-tests`; sin N/A).
Suite **1426/1426** en Linux (Python 3.11.9 con openai 3.42.1 y ruff 0.15.14;
3.12.3/3.14.4 desde el lock con openai 3.45.0 y ruff 0.13.2), preflight 0,
docs-check OK; Hallazgo 225: deepseek-free-agent con autorización formal, egreso
loopback, salida no confiable y requisitos trazados. Su disponibilidad/calidad real
permanece no verificada sin servicio y sesión; no se simuló.

**Sin red**: 1.000 (27/29; 2 N/A: `v4`, `h5`). En Windows 11
(Python 3.12.7/3.14.3) la última medición histórica es 750/750 (2026-10-22);
ruff 0, preflight 0, docs-check OK.

`no_verificado`: **vacío** (2026-11-04). Migración de `openai` a rango
`>=1.0,<4` completada (lock en 3.45.0); `v4_dependencias_al_dia` al día con
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

**Actualización 2026-10-30** (comodín en locks): los locks textuales reutilizan
`dep["fijada"]` y ya no devuelven `2.*` como versión resuelta. La regresión
falló antes, conserva `click==8.1.7` y detecta 3/3 mutaciones dirigidas.
Suite **1221/1221** en Linux (Python 3.11.9), con tres demos offline correctas.
R3 permanece abierta sin cambiar su inventario oficial. Hallazgo 160.

**Actualización 2026-10-30** (falso lock por comodín): `_es_lock` deja de contar
`==2.*` como línea fijada, conserva versiones exactas y `--hash=`, y mantiene la
regla de mayoría. La regresión falló antes y detecta 3/3 mutaciones dirigidas.
Suite **1222/1222** en Linux (Python 3.11.9), con tres demos offline correctas.
R3 permanece abierta sin cambiar su inventario oficial. Hallazgo 161.

**Actualización 2026-10-30** (relleno de ceros PEP 440): `2.31` y `2.31.0` ya
no se reportan como versiones distintas en `v4`. La normalización se limita a
releases numéricas y valores de texto; la regresión cubre ambos sentidos y el
caso previo con `None`, con 3/3 mutaciones detectadas.
Suite **1223/1223** en Linux (Python 3.11.9), con tres demos offline correctas.
R3 permanece abierta sin cambiar su inventario oficial. Hallazgo 162.

**Actualización 2026-10-30** (validación de estado): `context_from_state`
rechaza ahora `iteration` con cadenas, booleanos, negativos o floats, en lugar
de restaurarlos como válidos. La regresión cubre cuatro valores, falló antes y
detecta 3/3 mutaciones dirigidas; el esquema no cambia.
Suite **1224/1224** en Linux (Python 3.11.9), con tres demos offline correctas.
R3 permanece abierta sin cambiar su inventario oficial. Hallazgo 163.

**Actualización 2026-10-30** (`decomposed` estricto): la cadena `"false"` ya no
se restaura como `True`; el campo exige booleano y conserva `True`/`False`.
La regresión cubre cuatro entradas inválidas, falló antes y detecta 3/3
mutaciones dirigidas; el esquema no cambia.
Suite **1225/1225** en Linux (Python 3.11.9), con tres demos offline correctas.
R3 permanece abierta sin cambiar su inventario oficial. Hallazgo 164.

**Actualización 2026-10-30** (duración finita): `duration_seconds` rechaza
`NaN` e infinitos mediante `math.isfinite`, evitando un `start_time` inválido.
La regresión incluye NaN/±inf y una duración válida, falló en los dos casos
nuevos y detecta 3/3 mutaciones dirigidas.
Suite **1226/1226** en Linux (Python 3.11.9), con tres demos offline correctas.
R3 permanece abierta sin cambiar su inventario oficial. Hallazgo 165.

**Actualización 2026-10-30** (setuptools mínimo): el verificador de instalación
exige ahora `setuptools>=77`, coherente con `pyproject.toml`; una versión menor
selecciona aislamiento en vez de fallar con `--no-build-isolation`. Regresión
65.5/77 y 3/3 mutaciones detectadas.
Suite **1227/1227** en Linux (Python 3.11.9), tres demos y `make verify-install`
con 82.0.1 correctos. Con 65.5.0 solo se verificó la selección de aislamiento.
R3 permanece abierta. Hallazgo 166.

**Actualización 2026-10-31** (cierre R3 de `_ambito_requirements`): campaña
acotada de 77 mutantes con 63 muertos y 14 equivalencias demostradas. Los 44
muertos previos pasan a 63 (+19) y los 33 supervivientes a 14, todos
reclasificados; el clúster queda cerrado. R3 baja de **1067 a 1034 brechas** y
sube de 62 a **76 equivalencias**, sin recalcular la tasa global histórica.
Dos regresiones nuevas cubren nombres y bordes de ruta; 10 muertes verificadas
directamente y 14 mutantes comparados en 11 contratos.
Suite **1229/1229** en Linux (Python 3.11.9), con tres demos offline correctas.
R3 permanece abierta con las demás funciones pendientes. Hallazgo 167.

**Actualización 2026-10-31** (cierre R3 de `licencias_no_runtime`): campaña
acotada de 120 mutantes, **120 muertos y 0 supervivientes**. Diez muertes se
confirmaron aplicando los diffs y ejecutando la selección real; el fuente quedó
restaurado. El clúster de 37 queda cerrado sin cambios de código ni tests.
R3 baja de **1034 a 997 brechas**, con **76 equivalencias** sin cambios y sin
recalcular la tasa global histórica. Suite **1229/1229** en Linux (Python
3.11.9), verificada en el pre-commit. Hallazgo 168.

**Actualización 2026-10-31** (cierre R3 de `_dependencias_pyproject`): 259
mutantes, **258 muertos + 1 equivalencia, 0 brechas**. El mutante 5 sobrevivió
a la primera muestra directa; se investigó y se demostró que `None` y `""`
siguen el mismo fallback. Otras 10 muertes fueron confirmadas y el fuente quedó
restaurado. El clúster de 48 queda cerrado sin cambios de código ni tests.
R3 baja de **997 a 949 brechas** y sube de 76 a **77 equivalencias**, sin
recalcular la tasa global histórica. Suite **1229/1229** en Linux (Python
3.11.9), verificada en el pre-commit. Hallazgo 169.

**Actualización 2026-10-31** (cierre R3 de `_versiones_lock`): 203 mutantes,
**201 muertos + 2 equivalencias, 0 brechas**. Los valores ausentes de `package`
producen las mismas cero iteraciones (E11); el mutante 12 reveló una brecha real
con paquetes incompletos y quedó cubierto por una nueva regresión. Diez muertes
no equivalentes y dos equivalencias fueron verificadas, con fuente restaurado.
El clúster de 32 queda cerrado: R3 baja de **949 a 917 brechas** y sube de 77 a
**79 equivalencias**, sin recalcular la tasa global histórica.
Suite **1230/1230** en Linux (Python 3.11.9), con tres demos offline correctas.
R3 permanece abierta con las demás funciones pendientes. Hallazgo 170.

**Actualización 2026-10-31** (cierre R3 de `_dependencias`): 138 mutantes,
**136 muertos + 2 equivalencias, 0 brechas**. El conjunto inicial `None` y el
filtro que admite directorios como manifiestos no cambian la salida (E12). Diez
muertes no equivalentes fueron confirmadas aplicando los diffs y ejecutando la
selección real, con el fuente restaurado. El clúster de 44 queda cerrado sin
cambios de producción ni nuevos tests: R3 baja de **917 a 879 brechas** y sube
de 79 a **81 equivalencias**, sin recalcular la tasa global histórica.
Suite **1230/1230** en Linux (Python 3.11.9). R3 permanece abierta con las demás
funciones pendientes. Hallazgo 171.

**Actualización 2026-10-31** (cierre R3 de `main`): 162 mutantes, **160 muertos
+ 2 equivalencias, 0 brechas**. Dos regresiones fijan el contrato completo de
`--help` y la propagación de `con_red=True` por defecto. La campaña pasó de 97
muertos/65 supervivientes a 158/4; los mutantes 3 y 12 murieron en la
verificación directa final y 76/108 demostraron ser equivalentes (E13). Diez
muertes adicionales fueron confirmadas y el original restaurado pasó la
selección. El clúster de 65 queda cerrado sin cambios de producción: R3 baja de
**879 a 814 brechas** y sube de 81 a **83 equivalencias**, sin recalcular la
tasa global histórica. Suite **1232/1232** en Linux (Python 3.11.9). R3
permanece abierta con las demás funciones pendientes. Hallazgo 172.

**Actualización 2026-10-31** (cierre R3 de `evaluar_calidad`): campaña acotada
de 339 mutantes, **339 muertos y 0 supervivientes**. Diez diffs representativos
(1–5, 50, 100, 200, 300 y 339) fueron detectados al aplicarlos y ejecutar la
selección real; el original restaurado también pasó. El clúster de 47 queda
cerrado sin cambios de producción ni nuevos tests: R3 baja de **814 a 767
brechas**, con **83 equivalencias** intactas y sin recalcular la tasa global
histórica. Suite **1232/1232** en Linux (Python 3.11.9). R3 permanece abierta
con las demás funciones pendientes. Hallazgo 173.

**Actualización 2026-10-31** (cierre R3 de `parsear_requisitos`): 218 mutantes,
**217 muertos + 1 equivalencia, 0 brechas**. La campaña declaró 218/218, pero la
muestra directa encontró dos supervivientes: 3 es equivalencia por una excepción
inalcanzable (E14) y 218 quedó cubierto por una regresión exacta del mensaje de
archivo sin requisitos. Otras ocho muertes fueron confirmadas y el original
restaurado pasó. El clúster de 35 queda cerrado sin cambios de producción: R3
baja de **767 a 732 brechas** y sube de 83 a **84 equivalencias**, sin recalcular
la tasa global histórica. Suite **1233/1233** en Linux (Python 3.11.9). R3
permanece abierta con las demás funciones pendientes. Hallazgo 174.

**Actualización 2026-10-31** (cierre R3 de `evaluar_inteligencia`): 139 mutantes,
**139 muertos y 0 supervivientes**. La campaña declaró 139/139, pero la muestra
directa encontró dos supervivientes (130 y 139) que cambiaban la evidencia de los
hallazgos. Una nueva regresión fija el contrato completo de un proyecto LLM sin
señales y mata ambos; otras siete muertes fueron confirmadas y el original
restaurado pasó. El clúster de 30 queda cerrado sin cambios de producción: R3
baja de **732 a 702 brechas**, con **84 equivalencias** intactas y sin recalcular
la tasa global histórica. Suite **1234/1234** en Linux (Python 3.11.9). R3
permanece abierta con las demás funciones pendientes. Hallazgo 175.

**Actualización 2026-10-31** (cierre R3 de `sintetizar_con_llm`): 139 mutantes,
**139 muertos y 0 supervivientes**. La campaña reprodujo 110 muertos y las 29
brechas históricas. Siete regresiones nuevas fijan prompt, defaults, errores,
campos ausentes, modelo, conteo y barreras anti-invención; otra existente exige
ahora el mensaje exacto. Los 29 supervivientes y diez mutantes de control fueron
detectados directamente, con el original restaurado verde. El clúster de 29 queda
cerrado sin cambios de producción: R3 baja de **702 a 673 brechas**, con
**84 equivalencias** intactas y sin recalcular la tasa global histórica.
Suite **1241/1241** en Linux (Python 3.11.9). R3 permanece abierta. Hallazgo 176.

**Actualización 2026-10-31** (re-medición acotada de `evaluar_eficiencia`):
campaña de 190 mutantes, **190 muertos y 0 supervivientes**. Diez diffs
representativos (1–5, 50, 100, 150, 180 y 190) fueron detectados al aplicarlos
y el original restaurado pasó. No fueron necesarios cambios de producción ni
tests. Suite **1241/1241** en Linux (Python 3.11.9). R3 se mantiene en
**673 brechas + 84 equivalencias** porque la distribución histórica detallada no
está disponible y no se inventa un descuento. Evidencia:
`build/eficiencia-r3-verificacion.json`. Hallazgo 177.

**Actualización 2026-10-31** (cierre acotado de `_digesto`): campaña de 68
mutantes, inicialmente 55 muertos y 13 supervivientes. Tres regresiones fijan el
límite por defecto de 20 hallazgos, los interrogantes de cobertura ausente y el
marcador `—` sin fallos. Los **13/13 supervivientes** y diez controles fueron
detectados directamente; el original restaurado pasó. Resultado: **68/68
muertos**, sin equivalencias ni cambios de producción. R3 permanece en
**673 brechas + 84 equivalencias** por falta de distribución histórica detallada.
Suite **1244/1244** en Linux (Python 3.11.9). Evidencia:
`build/digesto-r3-verificacion.json`. Hallazgo 178.

**Actualización 2026-10-31** (cierre acotado de `evaluar_funcionalidades`):
campaña de 224 mutantes, **224 muertos y 0 supervivientes**. La muestra directa
detectó dos supervivientes pese al 224/224 inicial: 50 cambia `README.txt` y 100
la severidad de un módulo prometido inexistente. Una regresión con `README.txt`
y `faltante.py` mata ambos; otros ocho controles murieron y el original restaurado
pasó. No hubo equivalencias ni cambios de producción. R3 permanece en
**673 brechas + 84 equivalencias** por falta de distribución histórica detallada.
Suite **1245/1245** en Linux (Python 3.11.9). Evidencia:
`build/funcionalidades-r3-verificacion.json`. Hallazgo 179.

**Actualización 2026-10-31** (re-medición de `detectar_comando_tests`): campaña
de 235 mutantes, **235 muertos y 0 supervivientes**. Diez diffs representativos
(1–5, 50, 100, 150, 200 y 235) fueron detectados al aplicarlos y el original
restaurado pasó. No fueron necesarios cambios de producción ni tests.
Suite **1245/1245** en Linux (Python 3.11.9). R3 permanece en
**673 brechas + 84 equivalencias** por falta de distribución histórica detallada.
Evidencia: `build/runner-r3-verificacion.json`. Hallazgo 180.

**Actualización 2026-10-31** (verificación de `_puntuacion_texto`): la campaña
solo generó cuatro mutantes. Los **4/4 fueron detectados al aplicarlos
directamente** y el original restaurado pasó la selección. No fueron necesarios
cambios de producción ni tests. Suite **1245/1245** en Linux (Python 3.11.9).
R3 permanece en **673 brechas + 84 equivalencias** por falta de distribución
histórica detallada. Evidencia: `build/puntuacion-r3-verificacion.json`.
Hallazgo 181.

**Actualización 2026-10-31** (cierre acotado de `investigar_preguntas`): campaña
de 43 mutantes, inicialmente 29 muertos y 14 supervivientes. Cuatro regresiones
fijan el límite de dos fuentes, la consulta de cinco términos, la continuación
tras error y los metadatos vacíos. Los **14/14 supervivientes** y diez controles
fueron detectados; el original restaurado pasó. Resultado: **43/43 muertos**,
sin equivalencias ni cambios de producción. R3 permanece en
**673 brechas + 84 equivalencias** por falta de distribución histórica.
Suite **1249/1249** en Linux (Python 3.11.9). Evidencia:
`build/investigar-r3-verificacion.json`. Hallazgo 182.

**Actualización 2026-10-31** (regla 16: métricas, análisis y resumen de calidad):
se incorporó la obligación de registrar todas las métricas disponibles y su
evolución, analizar la calidad y publicar un resumen gráfico breve en el README.
Medición actual: **7/7 gates PASS**, **1249/1249 tests**, holdout 4/4 y
autoevaluación offline **1.000 (27/29; 2 N/A: v4/h5; cobertura 93,1%)**.
La suite creció **121 tests (+10,7%)** desde 1128; R3 bajó **458 brechas
(-40,5%)** desde 1131 y las equivalencias subieron de 62 a **84**. Se conservan
por separado los históricos de mutación del núcleo (95,2%), preflight (95,18%)
y evaluador (80,98%): no prueban calidad del LLM ni de producción.
Suite **1249/1249** en Linux (Python 3.11.9). Evidencia:
`docs/informe-calidad.json` y resumen Mermaid en `README.md`. Hallazgo 183.

**Actualización 2026-10-31** (verificación de citas, fuentes, RAG y holdout del
evaluador): se añadieron dos módulos de análisis y tres instrumentos de medida,
sin presentar heurísticas como verdad. `citation_verifier.py` separa existencia
de la cita (`EXACT_MATCH`/`FOUND`/`NOT_FOUND`/`UNVERIFIABLE`) de soporte del
claim (`SUPPORTED`/`PARTIALLY_SUPPORTED`/`CONTRADICTED`/`UNVERIFIABLE`), detecta
fragmentos inexistentes y duplica URLs normalizadas; es una comprobación léxica
determinista, **no** una prueba semántica. `source_quality.py` publica
dimensiones separadas (autoridad, independencia, actualidad, relevancia,
soporte y trazabilidad) y evita una nota única que mezcle reputación con
respaldo. El pipeline envuelve snippets y claims en `<untrusted_source>` y
declara que son DATOS: mitiga inyección de instrucciones de forma estructural,
pero no garantiza que un modelo las obedezca.

Medición offline (Linux, Python 3.11.9, venv aislado con `pypdf` para el doctor):
**1287/1287 tests**, ruff 0, preflight 0, holdout 4/4 y docs-check OK. El
benchmark sintético del evaluador mantiene **F1 1.000** en 57 fixtures y 26
criterios; el holdout nuevo de 6 proyectos sintéticos discrimina las 9/9
relaciones de orden (completo > deficiente, completo > README engañoso,
pequeño completo > grande vacío, tests reales > tests no-op), con **global
0.889/0.362/0.446/0.529/0.889/0.856**. La recuperación léxica BM25+coseno, sin
embeddings, obtiene en 10 pasajes y 16 consultas **Recall@1 0.875, Recall@5
0.938, MRR 0.906 y nDCG@10 0.914**; las paráfrasis sin términos exactos son el
límite visible. La calibración simulada de 16 casos da **Brier 0.1166 y ECE
0.1437**, y sigue declarada **no calibrada**: no hay etiquetas humanas
suficientes. Cobertura de líneas **82,57%** y de ramas **82,42%** (2382/2890),
medida con `coverage --branch`.

Estos números son **sintéticos y del propio proyecto**: no sustituyen una
campaña de 100 repositorios con evaluación humana independiente, ni una prueba
semántica de citas, ni una validación en Windows/macOS en esta sesión. El
benchmark del evaluador y el holdout comparten autor; sirven para detectar
regresiones y confundir documentación con calidad, no para afirmar validez
externa. Suite **1287/1287** en Linux (Python 3.11.9). Evidencia:
`docs/metricas-calidad.json`, `tests/benchmarks/rag_retrieval.py` y
`tests/benchmarks/evaluador_holdout.py`. Hallazgo 184.

**Actualización 2026-10-31** (cierre acotado de `_linter_configurado`): 79
mutantes, **78 muertos + 1 equivalencia (E15), 0 supervivientes**. La muestra
directa encontró dos supervivientes: 60 solo cambia mayúsculas bajo `re.I` y
conserva idéntica salida en seis variantes; 70 cambia el glob de
`eslint.config.js`. Se añadió ese archivo a la regresión existente y 70 murió;
otros ocho controles murieron y el original restaurado pasó. No hubo cambios de
producción ni nuevos tests. R3 permanece en **673 brechas** y sube a
**85 equivalencias** por falta de distribución histórica detallada.
Suite **1287/1287** en Linux (Python 3.11.9). Evidencia:
`build/linter-r3-verificacion.json`. Hallazgo 185.

**Actualización 2026-10-31** (cierre acotado de `_tiene_punto_entrada`): 90
mutantes, **90 muertos y 0 supervivientes**. La muestra directa detectó 60 y 80
vivos pese al 90/90 inicial: faltaban `setup.cfg` con `console_scripts` y
`package.json` con solo `bin` o solo `main`. Una regresión con tres subcasos mata
ambos; otros ocho controles murieron y el original restaurado pasó. No hubo
cambios de producción ni equivalencias. R3 permanece en **673 brechas + 85
equivalencias** por falta de distribución histórica detallada.
Suite **1288/1288** en Linux (Python 3.11.9). Evidencia:
`build/entry-r3-verificacion.json`. Hallazgo 186.

**Actualización 2026-10-31** (cierre acotado de `plan_texto`): 42 mutantes,
**39 muertos + 3 equivalencias (E16), 0 supervivientes**. La campaña produjo 33
muertos y 9 brechas. Una regresión fija el mensaje vacío y el orden exacto con
`media` antes de `alta`, matando 35 por orden estable. Los casos 3/5 y 41 conservan
salidas idénticas y son equivalentes; los otros seis supervivientes y diez
controles murieron, con el original restaurado verde. R3 permanece en
**673 brechas** y sube a **86 equivalencias** por falta de distribución histórica.
Suite **1289/1289** en Linux (Python 3.11.9). Evidencia:
`build/plan-r3-verificacion.json`. Hallazgo 187.

**Actualización 2026-10-31** (cierre acotado de `_registro_decisiones`): 57
mutantes, **57 muertos y 0 supervivientes**. La muestra directa detectó 2, 3, 15
y 25 vivos pese al 57/57 inicial. Una regresión con `ADR-001.md`,
`releasenotes.md` y `decision.adoc` mata los cuatro; otros seis controles
murieron y el original restaurado pasó. No hubo cambios de producción ni
equivalencias. R3 permanece en **673 brechas + 86 equivalencias** por falta de
distribución histórica detallada. Suite **1290/1290** en Linux (Python 3.11.9).
Evidencia: `build/decisiones-r3-verificacion.json`. Hallazgo 188.

**Actualización 2026-10-31** (cierre acotado de `_normalizar_release`): 20
mutantes, **20 muertos y 0 supervivientes**. Una regresión con 15 casos fija
valores no textuales, formatos no numéricos, separadores y ceros finales. Los
20/20 diffs fueron detectados al aplicarlos al módulo real; el original
restaurado pasó. No hubo cambios de producción ni equivalencias. R3 permanece
en **673 brechas + 86 equivalencias** por falta de distribución histórica.
Suite **1291/1291** en Linux (Python 3.11.9). Evidencia:
`build/release-r3-verificacion.json`. Hallazgo 189.

**Actualización 2026-10-31** (cierre acotado de `_es_manifiesto`): 26 mutantes,
**24 muertos + 2 equivalencias (E17), 0 supervivientes**. Una regresión con 23
rutas fija nombres conocidos, sufijos, mayúsculas, locks y `requirements/*`.
Los 24 diffs no equivalentes fueron detectados directamente; los mutantes 6 y 7
produjeron salidas idénticas al original en 20 rutas, con demostración adicional
en E17. El original restaurado pasó. No hubo cambios de producción. R3 permanece
en **673 brechas** y sube a **88 equivalencias** por falta de distribución
histórica detallada. Suite **1292/1292** en Linux (Python 3.11.9). Evidencias:
`build/manifiestos-r3-verificacion.json` y
`build/manifiestos-e17-verificacion.json`. Hallazgo 190.

**Actualización 2026-10-31** (cierre acotado de `_es_no_codigo`): 7 mutantes,
**7 muertos y 0 supervivientes**. Una regresión con 19 rutas fija directorios
de documentación/ejemplos y archivos con nombres similares. Los 7/7 diffs fueron
detectados al aplicarlos al módulo real; el original restaurado pasó. No hubo
cambios de producción ni equivalencias. R3 permanece en **673 brechas + 88
equivalencias** por falta de distribución histórica.
Suite **1293/1293** en Linux (Python 3.11.9).
Evidencia: `build/no-codigo-r3-verificacion.json`.
Hallazgo 191.

**Actualización 2026-10-31** (corrección de `_normalizar_release`): se reprodujo
un falso «dependencia atrasada» con `requests==01.0` frente a PyPI `1.0`.
PyPA exige interpretar cada componente por su valor entero; la función devolvía
`01` y `1`, y `v4` era `False`. Ahora normaliza enteros antes de recortar ceros
finales, sin añadir dependencias ni afirmar soporte PEP 440 completo para otros
sufijos. Las dos direcciones `01.0 ↔ 1.0` pasan en el evaluador real con PyPI
simulada. Suite **1293/1293** en Linux (Python 3.11.9), sin nuevas pruebas:
se ampliaron dos contratos existentes. Evidencia:
`build/versiones-enteras-verificacion.json`. Hallazgo 192.

**Actualización 2026-10-31** (comparación PEP 440 completa en `v4`): el evaluador
marcaba `2.0` como atrasado frente a `1.0` por comparar desigualdad textual.
Se sustituye el normalizador parcial por `packaging.version.Version`; las versiones
inválidas se reportan como no verificadas, nunca como atrasos. Se comprueban
`2.0 → 1.0` sin falso hallazgo, equivalencias de ceros y `1.0-1 = 1.0.post1`.
Nueva dependencia `packaging 26.3` (Apache-2.0/BSD-2-Clause), lock con hashes y
`openai 3.42.0`; evaluador 237/237 en venv aislado y pip-audit sin vulnerabilidades
conocidas. Suite **1293/1293** en Linux (Python 3.11.9). Evidencia:
`build/pep440-versiones-verificacion.json`. Hallazgo 193.

**Actualización 2026-10-31** (cierre acotado de `_es_lock_python`): 12 mutantes,
**12 muertos y 0 supervivientes**. Una regresión con 16 rutas fija locks Python,
locks npm, mayúsculas y directorios `requirements/*`. Los 12/12 diffs fueron
detectados al aplicarlos al módulo real; el original restaurado pasó. No hubo
cambios de producción ni equivalencias. R3 permanece en **673 brechas + 88
equivalencias** por falta de distribución histórica.
Suite **1294/1294** en Linux (Python 3.11.9). Evidencia:
`build/lock-python-r3-verificacion.json`. Hallazgo 194.

**Actualización 2026-10-31** (preparación de `0.1.16`): se añade `packaging`
al contrato offline de `scripts/verificar_instalacion.py` y se elimina el texto
obsoleto «8 módulos» en favor del recuento real y se separa el extra opcional
`ml`: la instalación normal no exige `torch`, pero cualquier otro ImportError
sigue fallando. Una regresión impide omitir la nueva dependencia en instalaciones
sin dependencias.
Suite **1397/1397** en Linux (Python 3.11.9). La publicación queda condicionada
a la validación del
wheel/sdist y a la instalación desde TestPyPI y PyPI; no se declara aquí antes
de comprobarla. Evidencia de gates: `docs/informe-calidad.json`. Hallazgo 195.

**Actualización 2026-10-31** (CI sin `rm -rf`): la limpieza temporal de
`scripts/ci.sh` usaba un comando prohibido por las reglas. Se sustituye por
Python con validación del directorio generado por `mktemp`; una regresión impide
reintroducirlo. `bash -n` y 3/3 pruebas de salvaguarda pasan.
Suite **1296/1296** en Linux (Python 3.11.9). La CI estándar se ejecuta sobre
el commit que contiene esta corrección antes del tag `v0.1.16`. Hallazgo 196.

**Actualización 2026-10-31** (publicación de `0.1.16`): wheel y sdist construidos
desde `v0.1.16`, `twine check` PASSED y publicados en TestPyPI y PyPI. SHA-256:
`1016dad281f05d04442092ae8adb7788b83e5d8ceddd56ddcfc02bc87226ab71` (wheel) y
`f2340d3d18b8232c73bc1eed3f33cb27f305266c215604b4b2b509be0c900677` (sdist);
ambos índices coinciden. Instalación limpia real en cada índice, `pip check`,
19 módulos obligatorios, consola y PEP 440 verificados.
Suite **1296/1296** en Linux (Python 3.11.9); CI limpia OK. `main` y tag anotado
`v0.1.16` (`1cc7039`)
empujados. Evidencia: `build/release16-verificacion.json`. Hallazgo 197.

**Actualización 2026-10-31** (cierre acotado de `_es_test`): 39 mutantes,
**36 muertos + 2 equivalencias (E18), 0 supervivientes**. Una regresión con 26
rutas fija Python, JS/TS, Go, Java, directorios y falsos positivos. El mutante
36 elimina `src/test/` y muere; 37/39 producen salidas idénticas en 28 rutas por
la normalización `lower()` ya existente. Los 36 diffs no equivalentes fueron
detectados directamente y el original restaurado pasó. No hubo cambios de
producción. R3 permanece en **673 brechas** y sube a **90 equivalencias** por
falta de distribución histórica.
Suite **1297/1297** en Linux (Python 3.11.9). Evidencias:
`build/es-test-r3-verificacion.json` y `build/es-test-e18-verificacion.json`.
Hallazgo 198.

**Actualización 2026-10-31** (cierre acotado de `_es_lock`): la campaña generó
135 mutantes incluyendo helpers; el clúster tiene **51 objetivo, 46 muertos +
5 equivalencias (E19), 0 supervivientes**. Un contrato con 27 comprobaciones
fija mayoría estricta, hashes, comentarios, `.in`, directorios y directivas.
Los casos 24, 29 y 32 murieron con las dos nuevas fronteras; 15–17 son
redundantes con el filtro `.txt` y 23/26 conservan el primer segmento.
El original restaurado pasó, sin cambios de producción. R3 permanece en **673
brechas** y sube a **95 equivalencias** por falta de distribución histórica.
Suite **1298/1298** en Linux (Python 3.11.9). Evidencias:
`build/es-lock-r3-verificacion.json` y `build/es-lock-e19-verificacion.json`.
Hallazgo 199.

**Actualización 2026-10-31** (cierre acotado de `_parsear_requisito`): 75
mutantes, **72 muertos + 3 equivalencias (E20), 0 supervivientes**. La verificación
directa inicial dejó 67 muertos y ocho supervivientes. Una regresión con siete
formas válidas y 14 entradas rechazadas cubre metadatos, comentarios, directivas
y `.zip`; mata 1, 11, 12, 33 y 34. Los casos 10 y 13 conservan el primer segmento;
18 es redundante con la regex que ya rechaza directivas. El original restaurado
pasó, sin cambios de producción. R3 permanece en **673 brechas** y sube a **98
equivalencias** por falta de distribución histórica.
Suite **1299/1299** en Linux (Python 3.11.9). Evidencias:
`build/parser-r3-verificacion.json` y `build/parser-e20-verificacion.json`.
Hallazgo 200.

**Actualización 2026-10-31** (evidencia no resoluble y cierre de tres contratos):
un bucle de enlaces simbólicos interrumpía `_resolver_evidencia` con
`RuntimeError` en Python 3.11. La regresión roja anterior al arreglo ahora exige
`NO VERIFICABLE`. Se fijaron contención de rutas, procedencia y mensajes de
`_verificar_archivo`/`_verificar_formal`. Los 71 mutantes del clúster fueron
aplicados directamente y detectados; un candidato a equivalencia se descartó con
`XXapp.pyXX`. R3 permanece en **673 brechas + 98 equivalencias**, sin nueva tasa
global ni descuento del inventario histórico. Suite **1303/1303** en Linux
(Python 3.11.9). Evidencias: `build/requisitos-verificacion-directa.json`,
`build/requisitos-verificacion-cierre.json` y
`build/resolver-mutante3-cierre.json`. Hallazgo 201.

**Actualización 2026-10-31** (preparación de `0.1.17`): se incrementa la versión
para distribuir el arreglo de evidencia no resoluble. Suite **1303/1303** en Linux
(Python 3.11.9), 7/7 gates PASS, demos offline y CI limpia del commit `eab1e7f`
verificados; ese commit
ya está en `origin/main`. **No se declara publicada** antes de comprobar wheel,
sdist, hashes e instalación limpia en TestPyPI y PyPI. Hallazgo 202.

**Actualización 2026-10-31** (publicación de `0.1.17`): wheel y sdist construidos
desde `v0.1.17` con setuptools 82.0.1; `twine check` PASSED y publicados en
TestPyPI y PyPI. SHA-256:
`19364d1681fb248e5ffc4fd7021d3ac7d8e697e0029e56302b1ae4df2dd01871` (wheel) y
`45b74837934a66c76fc4e7b3e93db6e6cb2d3c702e3b8af4ff4b36362c5a7d5f` (sdist);
ambos índices coinciden. Instalaciones limpias desde ambos índices con `pip
check`, 18 módulos base, consola absoluta del venv y bucle de evidencia no
verificable. El extra `ml` no se exige en la instalación base.
Suite **1303/1303** en Linux (Python 3.11.9); CI limpia OK. `main` y tag anotado
`v0.1.17` (`760e5f4`) empujados. Evidencia:
`build/release17-verificacion.json`. Hallazgo 203.

**Actualización 2026-10-31** (integridad de fuentes y citas): la normalización
ya no descarta puertos ni parámetros de contenido al agrupar duplicados o
asociar claims; solo elimina rastreadores conocidos. URLs malformadas quedan
sin host evaluable en vez de interrumpir el análisis. Una fecha futura ya no
recibe actualidad máxima y un claim sin fuente no se asocia por identificadores
ausentes. Diez regresiones nuevas: siete rojas antes de las correcciones y tres
de contrato exacto para bordes y asociaciones. Suite **1313/1313** en Linux
(Python 3.11.9), ruff/preflight y tres demos offline verificados. La campaña
aislada de 1314 mutantes pasó de 629 muertos/515 supervivientes/170 sin tests a
695/449/170, con 0 timeouts. En las cuatro funciones modificadas (198 mutantes)
quedan **193 muertos + 5 equivalencias demostradas** tras el cierre directo;
no se recalcula la tasa global ni se altera R3. Evidencias:
`build/diagnostico-url.json`, `build/diagnostico-asociacion.json`,
`build/regresiones-url-rojo.log`, `build/regresion-asociacion-rojo.log`,
`build/regresiones-fuentes-verde.log`, `build/mutacion-fuentes.json`,
`build/mutacion-fuentes-cierre.json`, `build/mutacion-fuentes-cierre-objetivo.json`,
`build/mutacion-fuentes-verificacion-final.json` y
`build/userinfo-equivalencias.json`. Hallazgo 204.

**Actualización 2026-11-01** (preparación de `0.1.18`): la versión de
mantenimiento distribuye las correcciones de identidad de fuentes y citas.
Commit funcional `3183386` en `origin/main`. Suite **1313/1313** en Linux
(Python 3.11.9), 7/7 gates PASS, tres demos offline y CI limpia OK. Cobertura
82,74% líneas/82,78% ramas (2389/2886). Autoevaluación con red y tests **1.000
(30/30; sin N/A)** y sin red **1.000 (27/29; 2 N/A)**. Dos fallos iniciales del
runner fueron reproducidos y atribuidos al `PATH` del intérprete base sin
`pypdf`; con el venv declarado el resultado es verde, sin cambios de código para
ocultar el entorno. **No se declara publicada** antes de verificar tag,
artefactos, hashes e instalación limpia. Evidencias:
`build/ci-3183386.log`, `build/autoevaluacion-final-red-tests-validada.json`,
`build/autoevaluacion-final-offline.json` y `docs/informe-calidad.json`.
Hallazgo 205.

**Actualización 2026-11-01** (publicación de `0.1.18`): wheel y sdist construidos
desde `v0.1.18` con build aislado; `twine check` PASSED y publicados en TestPyPI
y PyPI. SHA-256:
`2b00457c1b0f4932e8fc86f1c3443c97715a3e89a753e7cb93c45e7484ff2f17` (wheel) y
`cd616fddc7b604ff61a052148a049cf1fb8bcea55af59b3e29d6929f394bbdf6` (sdist);
ambos índices coinciden. Instalaciones limpias desde ambos índices con `pip
check`, 20 módulos base, consola absoluta del venv y las tres correcciones
reproducidas; el extra `ml` sigue siendo opcional. Suite **1313/1313** en Linux
(Python 3.11.9) y CI limpia OK sobre `5c2e304`. `main` y tag anotado `v0.1.18`
(objeto `5291e12`) empujados y verificados. Evidencia:
`build/release18-verificacion.json`. Hallazgo 206.

**Actualización 2026-11-01** (cierre histórico de `_requisito_poetry`): los
mutantes 5–9 sobrevivían tanto en r3c4 como en el código actual. La corrección
traduce rangos Poetry `^`/`~` a PEP 508, conserva `*` sin restricción y avisa
sobre formas inválidas. Dos regresiones nuevas y una expectativa fortalecida;
23 salidas validadas con `packaging.requirements`. Suite **1315/1315** en Linux
(Python 3.11.9). La función actual tiene 87 mutantes: **85 muertos + 2
equivalencias**; los cinco históricos también mueren. R3 queda en **668 brechas +
102 equivalencias**: 673→668 por el clúster y 100→102 por E21. El 98 anterior
además estaba desfasado: E16 demuestra 3 pero solo sumó 1; 49+51=100. Evidencias:
`build/poetry-comparativa-r3.json`, `build/poetry-cierre-actual.json`,
`build/poetry-verificacion-directa.json`,
`build/poetry-historicos-verificacion.json` y
`build/poetry-pep508-validacion.json`. Hallazgo 207.

**Actualización 2026-11-01** (preparación de `0.1.19`): la versión distribuye
la traducción de restricciones Poetry y el cierre histórico R3. Commit funcional
`0339b07` en `origin/main`. Suite **1315/1315** en Linux (Python 3.11.9), 7/7
gates PASS, tres demos offline y CI limpia OK. Cobertura 82,81% líneas/82,87%
ramas (2405/2902). R3: **668 brechas + 102 equivalencias**. **No se declara
publicada** antes de verificar tag, artefactos, hashes e instalación limpia.
Evidencias: `build/ci-0339b07.log`, `build/metricas-0339b07.log`,
`build/informe-0339b07.log` y `docs/informe-calidad.json`. Hallazgo 208.

**Actualización 2026-11-01** (publicación de `0.1.19`): wheel y sdist construidos
desde `v0.1.19` con build aislado; `twine check` PASSED y publicados en TestPyPI
y PyPI. SHA-256:
`e87a04db9a1f7434117bf23422fc135bb4c82a5aa14aa7325f1f9b89093a7b11` (wheel) y
`d799faef8c577dbc5db4521b4db171a920717e64f1a9bf9afded66804fdb5cfd` (sdist);
ambos índices coinciden. Instalaciones limpias desde ambos índices con `pip
check`, 20 módulos base, consola absoluta del venv y traducción Poetry validada
con `packaging.requirements`; el extra `ml` sigue siendo opcional.
Suite **1315/1315** en Linux (Python 3.11.9) y CI limpia OK sobre `edaed96`. `main` y
tag anotado `v0.1.19` (objeto `d345dc2`) empujados y verificados. Evidencia:
`build/release19-verificacion.json`. Hallazgo 209.

**Actualización 2026-11-01** (100 brechas R3 resueltas): dos familias acotadas de
aserciones y seis grupos funcionales suman exactamente **100 mutantes históricos
muertos**, con **14 equivalencias demostradas** aparte. Se añadieron 13 contratos
nuevos y se reforzaron bordes de comparación, ConfigParser, CPU, runner y `.env`.
R3 queda en **568 brechas + 116 equivalencias** (49 preflight + 67 evaluador).
Suite **1328/1328** en Linux (Python 3.11.9). Evidencias:
`build/r3-100-lote1-verificacion.json`, `build/r3-100-lote1-bordes.json`,
`build/r3-100-80-verificacion.json`, `build/r3-100-22-verificacion.json`,
`build/r3-100-setup-cierre.json` y `build/r3-100-equivalencias-normalizadas.json`.
Hallazgo 210.

**Actualización 2026-11-01** (200 brechas R3 resueltas): verificación directa
r3c4/actual con solo el diff de cada mutante. Cada descuento exige supervivencia
en r3c4 y fallo con las pruebas actuales, evitando el artefacto de Mutmut y la
reintroducción de arreglos posteriores. Se seleccionaron exactamente **200
muertes**; tres excedentes no se descuentan. Se añadieron 14 contratos y se
reforzaron bordes de runner, entrypoints, linter, funcionalidades y eficiencia.
R3 queda en **368 brechas + 126 equivalencias** (49 preflight + 77 evaluador);
las 10 equivalencias nuevas E28-E31 no se cuentan como muertes.
Suite **1342/1342** en Linux (Python 3.11.9). Evidencias:
`build/r3-200-final.json`, `build/r3-200-local-base87.json`,
`build/r3-200-equivalencias-nuevas.json` y
`build/r3-200-equivalencias-setup.json`. Hallazgo 211.

**Actualización 2026-11-01** (auditor de cambios): el auditor confundía una
cadena o clave de diccionario que contenía `self.assertTrue(True)` con una
aserción laxa. La detección de literales se limita ahora a aserciones y matchers;
las demás reglas, incluidas las configuraciones JSON, no cambian. Regresión
añadida en `tests/test_audit_changes.py`. R3 permanece en **368 brechas + 126
equivalencias**. Suite **1343/1343** en Linux (Python 3.11.9). Cambio
distribuible: release `0.1.20` publicada en TestPyPI y PyPI, tag `v0.1.20`.
Hallazgo 212.

**Actualización 2026-11-01** (otras 200 brechas R3 resueltas): segundo lote con
el mismo arnés pareado r3c4/actual; solo cuenta una muerte si el mutante
sobrevive a la selección de r3c4 y falla con las pruebas actuales. Se
seleccionaron exactamente **200 muertes** de 204 candidatas válidas; cuatro
excedentes no se descuentan. Un mutante antes clasificado equivalente
(`_llamada_aserion_debil` 42) muere ahora con el contrato del tercer argumento
de `assertEqual`: se deja **fuera del conteo** hasta revisar esa equivalencia.
Se añadieron 3 métodos de prueba (dos contratos y una regresión de aislamiento
de git) y se reforzaron bordes de descubrimiento,
aserciones, silencios, perfiles, runner y requisitos. La regresión
`test_no_hereda_el_indice_del_hook` corrige un defecto real: durante el hook,
git exporta `GIT_INDEX_FILE` y los fixtures lo heredaban, sobrescribiendo el
índice del repositorio anfitrión; `evaluar_proyecto._git` también sanea
`GIT_DIR`/`GIT_WORK_TREE`/`GIT_INDEX_FILE` para inspeccionar solo el repo
objetivo. R3 queda en **168 brechas
+ 126 equivalencias** (49 preflight + 77 evaluador). Suite **1346/1346** en Linux
(Python 3.11.9). Evidencias: `build/r3-400-final.json`,
`build/r3-200-b2-resto.json`, `build/r3-200-b2-worker0.json`,
`build/r3-200-b2-worker2.json` y `build/r3-200-b2-restauracion-manual.json`.
Hallazgo 213.

**Actualización 2026-11-01** (cierre parcial R3, Hallazgo 214): el lote de 200
no se alcanzó. Se demostraron **99 muertes** y **13 equivalencias nuevas**
(E32) sobre el inventario abierto; 0 hallazgos nuevos fuera del inventario.
R3 queda en **69 brechas + 139 equivalencias** (49 preflight + 90 evaluador).
Faltan **101 muertes** para las 200 pedidas. Se añadieron 4 contratos de borde
(`informe_texto` con defaults mínimos, comentarios de requirements, `tag` con
prefijo `XX` y `setup.cfg`). Suite **1397/1397** en Linux (Python 3.11.9).
Evidencias: `build/r3-300-final.json`, `build/r3-200-b3-abiertas.json`,
`build/r3-200-b3-sup26.json` y `build/r3-200-b3-if35.json`. Hallazgo 214.

**Actualización 2026-11-02** (preparación de `0.1.21`): la versión incorpora el
aislamiento de variables git en el evaluador y sus fixtures, avisos de imports
dinámicos en preflight, pruebas de contrato adicionales y el objetivo de mutación
`citas`. Suite **1397/1397** en Linux (Python 3.11.9) y CI limpia sobre `90c9063`; `make check` PASS,
incluidos secretos, holdout y pre-commit. Benchmark factual opt-in con
`nvidia/nemotron-3-ultra-550b-a55b:free`: **30/30**, exactitud 1,0, 0 falsos
verificados y abstención 1,0; es un conjunto pequeño y no prueba calidad general.
R3 permanece en **69 brechas + 139 equivalencias**; la campaña completa del
evaluador terminó por timeout y no aporta una nueva tasa. Los artefactos y la
publicación quedan condicionados a su verificación real.

**Actualización 2026-11-02** (publicación de `0.1.21`): wheel y sdist construidos
desde `v0.1.21` (`29a80b9`), `twine check` PASSED y publicados en TestPyPI y PyPI.
SHA-256: `43f3fa6d1e0078d38d0c9530e5006e437b3857e201031d7efdd26d7f1dc16b04`
(wheel) y `51249059200f708ef9e8f79e7e9a433be59a518b98103b9ed30c41f679c9b2c1`
(sdist), idénticos en ambos índices. Instalaciones limpias desde TestPyPI y PyPI
con `pip check`, 19 módulos obligatorios y cuatro consolas verificados. El primer
pip de PyPI no vio la versión; el segundo, tras 20 s, pasó.
Suite **1397/1397** en Linux (Python 3.11.9) y CI limpia sobre `29a80b9`. Evidencias:
`build/release21-build.log`, `build/release21-testpypi.json` y
`build/release21-pypi.json`. Hallazgo 215.

**Actualización 2026-11-04** (coherencia del estado de recomendaciones): la
autoevaluación offline con suite real mantuvo **1.000 (27/29; 2 N/A)** y el
benchmark del evaluador repitió **57 casos, 26 criterios, F1 1.00**. El
analizador estático solo encontró tres avisos de demo/estilo, que no se
vendieron como mejoras sustantivas. La revisión sí reprodujo un falso verde:
`check_docs` daba OK con `pyproject.toml` en `0.1.21` y la tabla de estado de
`RECOMENDACIONES-MEJORAS.md` en `0.1.19`. Dos regresiones fallaron antes del
cambio; ahora el gate contrasta esa fila con el paquete y exige el dato.
`tests.test_check_docs`: **14/14**. Suite **1399/1399** en Linux (Python
3.11.9). Cobertura medida con `metricas_calidad.py --con-cobertura`: **84,01%
de líneas y 84,55% de ramas** (2484/2938). R3 permanece en **69 brechas +
139 equivalencias**. Hallazgo 216.

**Actualización 2026-11-04** (preparación de `0.1.22` y cierre R3 acotado): la
versión incorpora el gate de coherencia documental y de versiones y dos
regresiones de aserciones. Suite **1401/1401** en Linux (Python 3.11.9). La
campaña generó 6144 mutantes y 37 supervivientes: 36 equivalencias ya
documentadas y un mutante de `package_json` que las pruebas actuales sí matan.
La muestra de diez «killed» detectó dos falsos positivos de campaña; ambos
sobrevivían en `r3c4` y ahora mueren con las nuevas pruebas. R3 baja de **69 a
67 brechas**, con **139 equivalencias** intactas. La tasa global de esta
campaña se descarta por esos dos falsos «killed»; no se presenta como medición
válida. Evidencias: `build/verificacion-directa-current.json`,
`build/r3-cierre2-aislado.json` y `build/r3-cierre2-historico.json`. Cobertura
actual: **84,03% de líneas y 84,58% de ramas** (2485/2938). Hallazgo 217.
Artefactos, tag, publicación e instalaciones pendientes de verificación.

**Actualización 2026-11-04** (publicación de `0.1.22`): wheel y sdist construidos
desde `v0.1.22` (`dd3e3cb`), `twine check` PASSED y publicados en TestPyPI y PyPI.
SHA-256: `5be6c05a4199dc1171d16a1a426990341902974bc0411b83752958ce11afd616`
(wheel) y `8f84a52faa4b85d67b21dbaf34bae57c686acb4e1be931a83ba5e225400941cb`
(sdist), idénticos en ambos índices. Instalaciones limpias desde TestPyPI y PyPI
con `pip check`, 19 módulos obligatorios y cuatro consolas verificados. La primera
instalación de PyPI no vio la versión; se comprobó la propagación del índice
simple y el reintento pasó. Suite **1401/1401** en Linux (Python 3.11.9) y CI
limpia sobre `dd3e3cb`. R3 queda en **67 brechas + 139 equivalencias**, sin una
nueva tasa global válida. Evidencia: `build/release22-verificacion.json`.
Hallazgo 218.

**Actualización 2026-11-04** (deduplicación de equivalencias): el inventario del
evaluador contiene 90 registros, pero **78 casos únicos**. E32 repite 12 casos ya
contados en E22–E27 y solo aporta `_leer_requirements` 25. El total correcto es
**127 equivalencias únicas** (49 preflight + 78 evaluador), no 139. Los registros
históricos se conservan con `duplicado_de` y los inventarios JSON versionados.
`tests/test_triaje_equivalencias.py` protege el contrato. Suite **1402/1402** en Linux (Python 3.11.9). Las **67 brechas** siguen abiertas; las verificaciones
funcionales se registran por lotes separados. Hallazgo 219.

**Actualización 2026-11-04** (revalidación y cierre de preflight): cuatro
contratos nuevos cierran **17 brechas** en metadatos de warnings, paquetes
anidados e imports dinámicos. Los mutantes 29/30 y 62 no se cuentan como brechas:
son equivalentes porque el paquete ya está en `modulos_locales` o la rama no
cambia el resultado. E1 se validó con IDs actuales 234/236; E13/E14 con 29/30 y
62. E23 124/126 no son equivalencias vigentes y están cubiertos por tests. El
resultado es **125 equivalencias validadas** (49 preflight + 76 evaluador) y
Suite **1406/1406** en Linux (Python 3.11.9). Evidencias:
`build/r3-preflight-cierre17.json`, `build/r3-preflight-cierre-dinamicos.json` y
`build/r3-e1-actual-verificacion.json`. Cobertura actual: **84,05% de líneas y
84,62% de ramas** (2486/2938). Hallazgo 220.

**Actualización 2026-11-04** (cierre histórico R3): los 355 candidatos tienen
veredicto individual: **304 detectados por tests actuales, 34 equivalencias
conocidas y 17 contextos especiales revisados**. Los 34 supervivientes pertenecen
al inventario validado; no quedan brechas abiertas. Se añade una regresión de
línea vacía que falla con `[] != ['requests']` y cuatro pasadas originales
verdes. Resultado: **0 brechas + 125 equivalencias validadas** y Suite **1407/1407** en Linux (Python 3.11.9). Evidencias:
`build/r3-consolidado-355.json` y `build/r3-no-aplicable-casos.json`. No se
recalcula una tasa global de mutación. Hallazgo 221.

**Actualización 2026-11-04** (dependencias, medición real y Python 3.14): la
autoevaluación con red detectó `openai 3.42.0 → 3.45.0`; el lock actualiza solo
`openai`, `anyio` y `typing-inspection`, pasa `pip-audit` sin vulnerabilidades.
Suite **1409/1409** en Linux (Python 3.11.9, 3.12.3 y 3.14.4; openai 3.45.0,
ruff 0.13.2). El benchmark
factual ahora devuelve Brier, ECE e IC bootstrap (antes prometía Brier y no lo
exponía). Mediciones reales opt-in con
`nvidia/nemotron-3-ultra-550b-a55b:free`: piloto **20/20, Brier 0,0050, ECE
0,0650, IC95 [0,0034; 0,0066]** y factual **30/30, 0 falsos, abstención 1,0,
Brier 0,0044, ECE 0,0590, IC95 [0,0031; 0,0059]**. Son muestras pequeñas y
fáciles, con confianza concentrada en 0,8-1,0: **no prueban calibración
general**. Se corrigió además el bucle de symlinks en Python 3.14, que devuelve
la ruta en vez de lanzar `RuntimeError`; los enlaces rotos conservan el veredicto
`NO CUMPLE`. Cobertura **84,04% de líneas y 84,59% de ramas** (2487/2940).
Evidencias: `build/mejoras-suite-py31{1,2,4}-lock345-verified.log`,
`build/mejoras-calibracion-real-n20.json`, `build/mejoras-factual-real-n30.json`
y `docs/metricas-calidad.json`. Hallazgo 223.

**Actualización 2026-11-04** (publicación de `0.1.23`): artefactos construidos
desde el tag `v0.1.23` (commit `29e1420`; objeto `d2b02a4`), `twine check`
PASSED y publicados en TestPyPI y PyPI. Suite **1409/1409** en Linux
(3.11.9, 3.12.3 y 3.14.4) y 7/7 gates PASS. SHA-256:
`da834c889601f39d7970296135e0afc61f97e9c9dfd981b039cf545f47b91d7d` (wheel) y
`a9bd500905d4ba5a32b1c8e76c89383b467cbf5fd07675c91e98ebc09925f328` (sdist).
Ambos índices publican esos hashes; instalaciones limpias con `pip check`,
19 módulos obligatorios y cuatro consolas. La primera instalación directa de
PyPI chocó con la propagación del índice simple mientras JSON y hashes ya eran
correctos; se consultó con `pip index versions` y el reintento sin caché pasó.
Evidencias: `build/release23-verificacion.json`,
`build/release23-testpypi-verificacion.log` y
`build/release23-pypi-verificacion.log`. Hallazgo 224.


**Actualización 2026-11-06** (deepseek-free-agent, Hallazgo 225): integración sin
API key ni fallback pagado, con autorización formal, endpoint loopback, política
`public`, salida no confiable y 14 contratos nuevos. Suite **1426/1426** en Linux
(Python 3.11.9 con openai 3.42.1; 3.12.3/3.14.4 desde el lock con openai 3.45.0).
Requisitos: **10 CUMPLE + 1 CUBIERTO + 1 NO VERIFICABLE**, sin `NO CUMPLE`; la
especificación formal es evidencia estática y la disponibilidad/calidad real sigue
sin verificar porque no hay servicio ni sesión autorizada. Cobertura **84,23% de
líneas y 84,75% de ramas** (2517/2970). El auditor del diff dio **REVISAR** (0 alta,
4 media: 938 líneas, reglas, requisitos y tests nuevos), con autorización explícita
de commit/push del programador; no se usaron exclusiones ni se elevaron presupuestos. Evidencias:
`build/deepseek-free-agent-requisitos.json`,
`build/deepseek-free-agent-suite-31{2,4}.log` y `docs/metricas-calidad.json`.


**Actualización 2026-11-06** (activación y prueba real, Hallazgo 226): servicio
local 1.11.3 aislado en `build/`, `npm audit` 0 vulnerabilidades y escucha solo en
`127.0.0.1:9527`. Una pregunta factual respondió **«París» en 44,14 s**. La revisión
real demostró que `keyboard.type` enviaba el prefijo al encontrar saltos de línea;
la tarea completa ahora se normaliza a una línea con regresión offline. Un pipeline
con documento público terminó en **349,61 s**, con **1 fuente, 4 claims y 4
evaluaciones**, pero la descomposición recibió `One more step before you proceed...`
y quedó con **0 citas válidas**. Se añadió rechazo explícito de ese texto intermedio.
Esto verifica conexión y recorrido, no calidad/disponibilidad general.
Suite **1426/1426** en Linux, Ruff y docs-check OK. Evidencia no versionada:
`build/deepseek-free-agent-runtime/workspace/resultado-fotosintesis-2.json`.


**Actualización 2026-11-06** (investigación DeepSeek gratuita y prueba local,
Hallazgo 227): se verificó `deepseek-r1:8b` Q4_K_M (5,2 GB, MIT) con Ollama. Una
pregunta factual respondió **«París» en 19,45 s** y el pipeline privado terminó en
**77,41 s**, con **1 fuente, 3 claims y 3 evaluaciones**. El informe negó contenido
presente en la fuente, por lo que el recorrido funciona pero la calidad no se declara
perfecta. La investigación de proveedores confirmó que no hay DeepSeek cloud gratuito
e ilimitado verificable; OVHcloud devolvió 404 y OpenRouter no lista DeepSeek a precio
cero. Suite **1426/1426** en Linux, sin cambios funcionales posteriores. Evidencia no
versionada: `build/deepseek-free-agent-runtime/workspace/resultado-ollama-deepseek.json`.
