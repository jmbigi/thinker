# Evaluaciones de proyecto (thinker como evaluador)

Fecha: 2026-10-16. Herramienta: `python3 evaluar_proyecto.py RUTA [--json] [--sin-red] [--ejecutar-tests]`.

**Estática y read-only** por defecto: no escribe en el proyecto evaluado ni ejecuta
su código. Lo único que lo ejecuta es `--ejecutar-tests` (opt-in explícito, P0.8),
y siempre con el **comando que el propio proyecto declara** (target `test:` del
Makefile, comando citado en su script/README, o la convención `unittest discover`
si existe `tests/`), con timeout y salida capturada.

Criterios: 6 dimensiones × 4 criterios (hasta 26 en total, según lo que aplique).
Puntuación de dimensión = criterios cumplidos / criterios evaluados; global = media.

Garantías: del historial git solo fechas y recuentos (nunca autores, P0.9); el
contenido evaluado son DATOS (P0.13); cada hallazgo con evidencia; y **lo que no se
verifica se declara** en `no_verificado`.

## thinker (autoevaluación)

| Dimensión | Puntuación | Criterios fallidos |
|---|---|---|
| Funcionalidades | 1.00 | — |
| Calidad | 1.00 | — (suite ejecutada: `make test`, 1,0 s, OK) |
| Vigencia | 0.75 | `v4_dependencias_al_dia` |
| Herramientas | 1.00 | — (licencias de las 4 dependencias: libres) |
| Inteligencia | 1.00 | — |
| Eficiencia | 1.00 | — |
| **Global** | **0.958** | |

`no_verificado`: **vacío** (antes: «la suite no se ejecuta» y «licencias no
consultadas»). Único hallazgo: dependencias por detrás de PyPI —
`requests 2.33.0 → 2.34.2`, `openai 1.109.1 → 3.33.0`, `python-dotenv 1.2.2 → 1.2.4`.
El salto de `openai` (1.x → 3.x) exige revisar el SDK: **decisión del programador**.

## better-ocr (evaluación externa)

| Dimensión | Puntuación | Criterios fallidos |
|---|---|---|
| Funcionalidades | 1.00 | — |
| Calidad | 0.60 | `c2_linter_configurado`, `c3_sin_silencios` (suite OK: 43,4 s) |
| Vigencia | 0.50 | `v1_dependencias_fijadas`, `v2_lockfile` |
| Herramientas | 0.80 | `h2_licencia` |
| Inteligencia | 0.83 | `i1_cachea_trabajo_repetido` |
| Eficiencia | 0.67 | `e1_import_perezoso_de_pesadas` |
| **Global** | **0.733** | |

Datos medidos: 39 archivos Python / 18.069 líneas (12.381 de código + 5.688 de
tests; proporción 0,46); 133 commits, todos en los últimos 180 días; **su suite
(475 tests) pasa** y el propio proyecto la declara. `no_verificado`: **vacío**.

Hallazgos con evidencia:

- **Alta — sin archivo de licencia** (P1.18).
- **Alta — 5 `except` con `pass`** (contra su propio P1.26): `analizar_cuit.py:406`,
  `auditoria_graficos.py:1756`, `buscador.py:172`, `buscador.py:398`,
  `buscador.py:475` (verificados a mano).
- **Media — sin linter configurado**; **6 dependencias sin fijar** y **sin
  lockfile**; **sin caché**; **sin import perezoso** de pesadas.

## Defectos del propio evaluador encontrados al usarlo (corregidos)

1. Comparaba los `archivo.py` del README contra nombres base → las rutas con
   carpeta (`scripts/bateria_360.py`) salían como inexistentes.
2. Contaba «TODO REAL» (regla de dominio de better-ocr) como deuda técnica.
3. `python-dotenv` figuraba como «sin licencia libre»: declara BSD-3-Clause en el
   campo de texto libre, sin clasificador OSI. Ahora se reconocen licencias libres
   habituales por nombre.
4. Las dependencias declaradas en dos manifiestos se contaban dos veces; ahora se
   deduplican prefiriendo la declaración más específica (`==`).

Los cuatro se detectaron **usando la herramienta contra proyectos reales**, no en
abstracto; los tres primeros eran falsos positivos y se corrigieron tras
verificarlos a mano.

## Límites declarados

- Las licencias se consultan en PyPI (metadatos declarados por el paquete): una
  licencia mal declarada allí no se detecta.
- Solo se ven dependencias **declaradas**: herramientas usadas sin declarar (p.
  ej. Playwright del sistema en better-ocr) no aparecen.
- La ejecución de la suite es opt-in y corre el comando tal cual lo declara el
  proyecto; el evaluador no lo modifica ni lo interpreta.
- Las partes cualitativas de Calidad e Inteligencia se aproximan con señales
  estructurales; el juicio final sigue siendo humano.
