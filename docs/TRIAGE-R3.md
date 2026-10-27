# Triaje R3 — 1517 brechas, 49 equivalencias y 0 timeouts

> Estado: **inventario completo, deuda abierta**. Cada caso tiene categoría;
> las equivalencias tienen prueba en `docs/TRIAGE-EQUIVALENCIAS.md`. Última
> medición: 2026-10-26.

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
| Evaluador | **1517** | 0 | **0** | **0** |
| **Total** | **1517** | **49** | **0** | **0** |

Los **1517** casos de brecha son aserciones que faltan: sus funciones se
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

### Evaluador — 1517

| Función | Casos |
|---|---:|
| `evaluar_herramientas` | 91 |
| `evaluar_calidad` | 76 |
| `evaluar_vigencia` | 82 |
| `_dependencias_pyproject` | 48 |
| `evaluar_eficiencia` | 27 |
| `evaluar_funcionalidades` | 43 |
| `evaluar` | 102 |
| `main` | 65 |
| `sintetizar_con_llm` | 29 |
| `licencia_pypi` | 19 |

Campaña 2026-10-26 (batch main-sintesis-eficiencia): **5984 mutantes, 4467 muertos,
1517 supervivientes, 0 sin tests, 0 timeouts, 0 sospechosos**; tasa bruta
**74,65%** (antes 51,19%). El contrato exacto de `informe_texto` y
`detectar_comando_tests`, los tests de `--sin-red` y el aislamiento de `main`
mataron 504 mutantes; el contrato de `evaluar_herramientas`/`evaluar_calidad`
mató 134; el de `evaluar_vigencia`/`_dependencias_pyproject`, 144; el de
`evaluar_eficiencia`/`evaluar_funcionalidades` y ramas nuevas, 142; el de
silencios/h5/h6/vigencia con red y licencias PyPI, 176; el de parser de
requisitos/runner/inteligencia, 77; el de setup.cfg/package.json/agregador/
linter, 112; el de main/síntesis/eficiencia, 115 más. La campaña mantiene
0 timeouts.

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

Los JSON completos están en `build/triaje-preflight-triage-final.json` y
`build/triaje-eval-batch-r3c.json` (ignorados por git). Este documento conserva
el resumen y la clasificación.

## Conclusión

- **Triaje de inventario:** completo, 1566/1566 casos con categoría
  (1517 brechas + 49 equivalencias).
- **Equivalentes demostrados:** 49, todos en preflight y con prueba; no se
  cuentan como muertos.
- **Tasas:** 967/1016 (preflight) y 4467/5984 (evaluador); no cambian por
  clasificar. Los timeouts quedaron en 0.
- **R3 no se cierra como tasa limpia:** quedan **1517 brechas**, todas del
  evaluador; el preflight ya no tiene brechas reales. El evaluador sigue siendo
  la deuda principal.
