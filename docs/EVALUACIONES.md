# Evaluaciones de proyecto (thinker como evaluador)

Fecha: 2026-10-16. Herramienta: `python3 evaluar_proyecto.py RUTA`.

**Estática y read-only** por defecto: no escribe en el proyecto evaluado ni ejecuta
su código. Lo único que lo ejecuta es `--ejecutar-tests` (opt-in explícito, P0.8),
siempre con el **comando que el propio proyecto declara** (target `test:` del
Makefile → comando citado en su script/README → convención `unittest discover` si
existe `tests/`), con timeout y salida capturada.

Criterios: 6 dimensiones × 4-5 criterios binarios (hasta 26), según lo que aplique.
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
- Solo se ven dependencias **declaradas**: herramientas usadas sin declarar (p. ej.
  Playwright del sistema en better-ocr) no aparecen.
- La ejecución de la suite es opt-in y corre el comando tal cual lo declara el
  proyecto.
- Las partes cualitativas de Calidad e Inteligencia se aproximan con señales
  estructurales; el juicio final sigue siendo humano.
