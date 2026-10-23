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
| Vigencia | 0.75 | `v4_dependencias_al_dia` |
| Herramientas | 1.00 | — (licencias de sus 4 dependencias, libres) |
| Inteligencia | 1.00 | — |
| Eficiencia | 1.00 | — |
| **Global** | **0.958** | |

`no_verificado`: **vacío**. Único hallazgo: `requests 2.33.0 → 2.34.2` y
`python-dotenv 1.2.2 → 1.2.4` (rutina). `openai` ya no computa: se migró a un
rango `>=1.0,<4` verificado en 1.109.1, 2.54.0 y 3.33.0.

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
  **775/775** en la última medición Linux (3.11/3.12, 2026-10-23); ruff 0;
  preflight 0; docs-check OK. El
  control con defectos plantados sigue detectando los 10 defectos y el control
  de rangos sigue fallando v4 sin consultar PyPI.

**Actualización 2026-10-23** (tras la auditoría de la actividad del
2026-10-16 al 2026-10-22 — 50 commits, `17798f7..HEAD`, Hallazgo 97):
autoevaluación **1.000 con red** (27/29,
cobertura 93%, N/A: `e1`/`e2`) y **1.000 sin red** (25/29; 4 N/A: `v4`, `h5`,
`e1`, `e2`). Suite **775/775** en Linux (Python 3.11.9 y 3.12.3, venv desde el
lock); ruff 0; preflight 0; `scripts/check_docs.py` OK. Añadidos en la misma
sesión: corpus adversario del evaluador (4 casos, R12) y gate documental con
10 tests (R11).

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
