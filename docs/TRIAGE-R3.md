# Triaje R3 — 2959 supervivientes y 0 timeouts

> Estado: **inventario completo, deuda abierta**. Cada caso tiene categoría;
> ninguno se declara equivalente sin prueba. Última medición: 2026-10-26.

## Método

1. Campaña persistente por objetivo:
   `preflight` (**1016 mutantes**, lote 5) y `evaluar` (**5939 mutantes**,
   campaña 26c).
2. Copias de mutación conservadas en `build/mut-run-2` (preflight) y
   `build/mut-eval-2026-10-26c` (evaluador; ambas ignoradas por git).
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
   - `equivalente`: **no se asigna sin una prueba semántica**. En este triaje
     no se demostró ninguno.

## Resultado

| Objetivo | Supervivientes | Timeouts | Sin categoría | Equivalentes |
|---|---:|---:|---:|---:|
| Preflight | **60** | 0 | **0** | **0** |
| Evaluador | **2899** | **0** | **0** | **0** |
| **Total** | **2959** | **0** | **0** | **0** |

Los **2959** supervivientes son brechas de aserción: sus funciones se ejecutan,
pero los tests no detectan el cambio. **No hay ningún caso sin cobertura** que
pueda resolverse solo añadiendo un test de humo; hace falta aserción exacta.

### Preflight — 60

Campaña 2026-10-26: **1016 mutantes, 956 muertos, 60 supervivientes, 0 sin
tests, 0 timeouts, 0 sospechosos**; tasa bruta **94,09%** (antes 696/1015,
68,57%). El refuerzo de aserciones exactas (contrato del hallazgo, CLI, alias,
umbrales de duplicados, manifiestos, `modulos_locales` y archivos ilegibles)
mató 260 mutantes más de los que ya caían; el total sube en 1 por el arreglo
de `_es_main` (nuevo mutante de `ast.Eq`).

| Función | Casos |
|---|---:|
| `dependencias_declaradas` | 23 |
| `revisar_duplicados` | 7 |
| `_leer_requisitos` | 6 |
| `cargar_modulos` | 5 |
| `revisar_silencios` | 5 |
| `_nombre_requisito` | 4 |
| `revisar_imports` | 4 |
| `modulos_locales` | 3 |
| `main` | 2 |
| `revisar_tareas` | 1 |

Lectura: la mayoría de los 60 restantes son **candidatos a equivalencia** por
defaults de `dict.get` que el helper ya trata, codificación UTF-8 con distinta
grafía o ramas cuyo valor no cambia la salida. No se declaran equivalentes sin
prueba semántica; por eso siguen contando como brechas.

### Evaluador — 2899

| Función | Casos |
|---|---:|
| `evaluar_herramientas` | 211 |
| `evaluar_vigencia` | 205 |
| `evaluar_calidad` | 202 |
| `informe_texto` | 200 |
| `evaluar_eficiencia` | 136 |
| `evaluar_inteligencia` | 131 |
| `_dependencias_pyproject` | 120 |
| `evaluar` | 104 |
| `evaluar_funcionalidades` | 103 |
| `licencia_pypi` | 88 |
| `main` | 84 |
| `detectar_comando_tests` | 81 |

Campaña 2026-10-26c: **5939 mutantes, 3040 muertos, 2899 supervivientes, 0 sin
tests, 0 timeouts, 0 sospechosos**; tasa bruta **51,19%** (antes 3034/5939,
51,09%). El cambio respecto a la campaña anterior son los tests de timeouts y
el aislamiento de `test_sintesis_sin_python_dotenv`; el resto de la deuda de
aserciones del evaluador sigue igual.

## Los 4 timeouts: resueltos y re-medidos

Los cuatro se clasificaban como **`timeout_no_equivalente`**. En la campaña
26c ya no aparece ninguno: **0 timeouts**.

| Mutante | Cambio | Cómo se acotó | Resultado 26c |
|---|---|---|---|
| `x_ejecutar_tests__mutmut_15` | `cwd=str(ruta)` → `cwd=None` | test `test_cwd_es_el_proyecto_evaluado` (2026-10-25) | killed |
| `x_ejecutar_tests__mutmut_21` | elimina `cwd=str(ruta)` | mismo test | killed |
| `x_main__mutmut_137` | `a or b` → `a and b` | tests de `main` sin clave + mock de `evaluar`; aislamiento de `test_sintesis_sin_python_dotenv` | killed |
| `x_main__mutmut_139` | `if not KEY` → `if KEY` | mismo conjunto | killed |

Los tests nuevos usan mocks y fallan rápido, sin ejecuciones reales. Un test
que llamaba al evaluador real en la ruta de error era la causa de que la
campaña se colgara; se aisló antes de la re-medición.

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

Los JSON completos de este triaje están en `build/triaje-preflight-batch5.json`
y `build/triaje-evaluar-2026-10-26c.json` (ignorados por git). Este documento
conserva el resumen y la clasificación.

## Conclusión

- **Triaje de inventario:** completo, 2959/2959 casos con categoría.
- **Equivalentes demostrados:** 0. No se usa «equivalente» como cajón de sastre.
- **Tasa:** 956/1016 (preflight) y 3040/5939 (evaluador); no cambia por
  clasificar. Los 4 timeouts quedaron en 0.
- **R3 no se cierra como tasa limpia:** quedan 2959 aserciones por reforzar.
  El preflight pasó de 319 a 60 brechas; el evaluador sigue siendo la deuda
  principal.
