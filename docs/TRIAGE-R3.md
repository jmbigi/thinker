# Triaje R3 — 1131 brechas, 56 equivalencias y 0 timeouts

> Estado: **inventario completo, deuda abierta**. Cada caso tiene categoría;
> las equivalencias tienen prueba en `docs/TRIAGE-EQUIVALENCIAS.md`. Última
> medición: 2026-10-28 (batch r3c4; las de 2026-10-26, r3c2 y r3c3 quedan como
> histórico).

## Método

1. Campaña persistente por objetivo:
   `preflight` (**1016 mutantes**, lote 6) y `evaluar` (**5984 mutantes**,
   batch r3c).
2. Copias de mutación conservadas en `build/mut-preflight-cierre3` y
   `build/mut-eval-batch-r3c` (ambas ignoradas por git).
3. Cobertura de las pruebas seleccionadas por la propia campaña:
   preflight 392/425 líneas; evaluador 1366/1571.
4. `scripts/triaje_mutantes.py` cruza cada superviviente con la función que lo
   contiene y la cobertura de esa función, y exporta su diff.
5. Categorías:
   - `cobertura_sin_deteccion`: la función se ejecuta, pero la mutación
     sobrevive. Es una **brecha de aserción**, no una equivalencia.
   - `sin_cobertura`: la función no se ejecuta. No apareció ninguna.
   - `timeout`: el mutante no termina; se clasifica aparte y no se cuenta como
     muerto.
   - `equivalente`: **solo con prueba semántica** (49 en preflight; ver
     `docs/TRIAGE-EQUIVALENCIAS.md`). No se usa como cajón de sastre.

## Resultado

| Objetivo | Brechas | Equivalentes | Timeouts | Sin categoría |
|---|---:|---:|---:|---:|
| Preflight | **0** | **49** | 0 | **0** |
| Evaluador | **1131** | **7** | **0** | **0** |
| **Total** | **1131** | **56** | **0** | **0** |

Los **1131** casos de brecha son aserciones que faltan: sus funciones se
ejecutan, pero los tests no detectan el cambio. No hay ningún caso sin
cobertura que se resuelva solo con un test de humo; hace falta aserción exacta.

### Preflight — 49 (0 brechas + 49 equivalencias)

Campaña 2026-10-26: **1016 mutantes, 967 muertos, 49 supervivientes, 0 sin
tests, 0 timeouts, 0 sospechosos**; tasa bruta **95,18%** (antes 696/1015,
68,57%). El refuerzo de aserciones exactas (contrato del hallazgo, CLI, alias,
umbrales de duplicados, manifiestos, `modulos_locales`, archivos ilegibles,
umbral exacto de 60 nodos, include con comentarios, locale C en proceso y byte
nulo) mató 271 mutantes más de los que ya caían; el total sube en 1 por el
arreglo de `_es_main` (nuevo mutante de `ast.Eq`).

Los 49 supervivientes son **equivalencias demostradas** en
`docs/TRIAGE-EQUIVALENCIAS.md` (grupos 1-14); no hay brechas reales. Los
mutantes `encoding=None` se mataron cambiando la locale a `C` **en proceso**
(no en un subproceso, que no habría sido mapeado por la campaña),
`cargar_modulos` 60 con un byte nulo (`lineno is None` → línea 0) y
`revisar_imports` 59 con `import os` seguido de `import os, requests`.

### Evaluador — 1131 brechas + 7 equivalencias

Re-medición 2026-10-28 (batch r3c4): **5984 mutantes, 4846 muertos, 1138
supervivientes, 0 sin tests, 0 timeouts, 0 sospechosos**; tasa bruta
**80,98%** (antes 79,61%). `evaluar` pasa de 75 a **5**, los cinco
equivalencias demostradas (E2-E5 en `docs/TRIAGE-EQUIVALENCIAS.md`, Hallazgo
140; 16 tests de contrato exacto en `TestEvaluarContrato`, incluidos los
bordes 0.500/0.800 que solo son alcanzables con `--ejecutar-tests`, total 30).
Distribución por función (completa en `build/triaje-eval-r3c4.json`):

| Función | Casos |
|---|---:|
| `evaluar_herramientas` | 70 |
| `main` | 65 |
| `_dependencias_pyproject` | 48 |
| `evaluar_calidad` | 47 |
| `_dependencias` | 44 |
| `licencias_no_runtime` | 37 |
| `parsear_requisitos` | 35 |
| `_ambito_requirements` | 33 |
| `_versiones_lock` | 32 |
| `evaluar_inteligencia` | 30 |
| `sintetizar_con_llm` | 29 |
| `evaluar` | 5 (equivalencias) |

Re-medición 2026-10-28 (batch r3c3): 5984 mutantes, 4764 muertos, 1220
supervivientes, 0 sin tests, 0 timeouts, 0 sospechosos; tasa bruta
79,61% (antes 78,23%). `evaluar_vigencia` pasó de 82 a **2**, ambas
equivalencias demostradas (E1, Hallazgo 139). Distribución de entonces en
`build/triaje-eval-r3c3.json`.

Re-medición 2026-10-28 (batch r3c2): 5984 mutantes, 4681 muertos, 1303
supervivientes, 0 sin tests, 0 timeouts, 0 sospechosos; tasa bruta
78,23% (antes 77,96%). `_verificar_test` pasa de 16 a **0** (Hallazgo
138). Distribución de entonces en `build/triaje-eval-r3c2.json`.

Campaña 2026-10-26 (batch digesto-calidad-h5): 5984 mutantes, 4665 muertos,
1319 supervivientes, 0 sin tests, 0 timeouts, 0 sospechosos; tasa bruta
77,96% (antes 51,19%). El contrato exacto de `informe_texto` y
`detectar_comando_tests`, los tests de `--sin-red` y el aislamiento de `main`
mataron 504 mutantes; el contrato de `evaluar_herramientas`/`evaluar_calidad`
mató 134; el de `evaluar_vigencia`/`_dependencias_pyproject`, 144; el de
`evaluar_eficiencia`/`evaluar_funcionalidades` y ramas nuevas, 142; el de
silencios/h5/h6/vigencia con red y licencias PyPI, 176; el de parser de
requisitos/runner/inteligencia, 77; el de setup.cfg/package.json/agregador/
linter, 112; el de main/síntesis/eficiencia, 115; el de ámbito/verificación/cobertura, 66; el de digesto/errores de calidad/h5,
72 más. La campaña mantiene 0 timeouts.

## Los 4 timeouts: resueltos y re-medidos

En la campaña r3c no aparece ninguno: **0 timeouts**.

| Mutante | Cambio | Cómo se acotó | Resultado |
|---|---|---|---|
| `x_ejecutar_tests__mutmut_15/21` | `cwd` ausente/None | test `test_cwd_es_el_proyecto_evaluado` | killed |
| `x_main__mutmut_137/139` (IDs antiguos) | `or`→`and` / `not KEY` | tests de `main` sin clave + mock de `evaluar` | killed |
| `x_evaluar__mutmut_39` | elimina `con_red` al llamar a vigencia | `TestSinRedNoTocaPyPI` (parchea PyPI y exige no llamarla) | killed |
| `x_main__mutmut_160` | `con_red=not sin_red` invertido | `TestSinRedNoTocaPyPI` para `--sin-red` | killed |

Los tests usan mocks y fallan rápido, sin ejecuciones reales. Un test que
llamaba al evaluador real en la ruta de error era la causa de que la campaña
se colgara; se aisló antes de la re-medición.

## Reproducción

```bash
python3 scripts/mutacion.py --objetivo preflight --json
python3 scripts/mutacion.py --objetivo evaluar --json
# con el temporal de cada campaña:
cd <temporal>
python3 -m coverage run --source=. -m pytest <selección>
python3 -m coverage json -o /ruta/coverage.json
cd RUTA_DEL_REPO
python3 scripts/triaje_mutantes.py --destino <temporal> \
  --cobertura /ruta/coverage.json --salida /ruta/triaje.json
```

Los JSON completos están en `build/triaje-preflight-triage-final.json`,
`build/triaje-eval-batch-r3c.json` (2026-10-26), `build/triaje-eval-r3c2.json`,
`build/triaje-eval-r3c3.json` y `build/triaje-eval-r3c4.json` (2026-10-28)
(ignorados por git). Este
documento conserva el resumen y la clasificación.

## Conclusión

- **Triaje de inventario:** completo, 1187/1187 casos con categoría
  (1131 brechas + 56 equivalencias).
- **Equivalentes demostrados:** 56 (49 en preflight y 7 en el evaluador), todos
  con prueba; no se cuentan como muertos.
- **Tasas:** 967/1016 (preflight) y 4846/5984 (evaluador); no cambian por
  clasificar. Los timeouts quedaron en 0.
- **R3 no se cierra como tasa limpia:** quedan **1131 brechas**, todas del
  evaluador; el preflight ya no tiene brechas reales. El evaluador sigue siendo
  la deuda principal.
- **Criterio de aceptación de campañas futuras (lección del artefacto r3c5/
  r3c6):** ninguna cifra de campaña se publica sin una **muestra directa
  verificada**: 5-10 diffs declarados «killed» se aplican a mano al fuente, se
  ejecuta la suite de la campaña y deben **fallar**. Si alguno sobrevive, la
  campaña se descarta y se investiga el entorno. El 2026-10-28 se descartaron
  **tres** campañas (5999/5644/355, 94,08%): las tres idénticas, con la prueba
  directa mostrando que cuatro diffs «killed» sobreviven, tanto en el repo
  como en el temporal de la campaña; un venv aislado con pytest **8.4.2** y
  mutmut 3.6.0 reprodujo el artefacto, así que no es la versión de pytest
  (Hallazgo 143). Causa raíz **no determinada**; las campañas del evaluador
  quedan **bloqueadas como medición**. La cifra oficial vigente es la de r3c4
  (4846/5984; 1131 brechas) hasta que una campaña pase esta verificación.
