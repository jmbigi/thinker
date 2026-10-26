# Triaje R3 — 3238 supervivientes y 4 timeouts

> Estado: **inventario completo, deuda abierta**. Cada caso tiene categoría;
> ninguno se declara equivalente sin prueba. Fecha: 2026-10-25.

## Método

1. Campaña persistente por objetivo:
   `preflight` (1015 mutantes) y `evaluar` (5939 mutantes).
2. Copia de mutación conservada en `build/mut-preflight-final` y
   `build/mut-evaluar-final` (no versionadas).
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
| Preflight | **337** | 0 | **0** | **0** |
| Evaluador | **2901** | **4** | **0** | **0** |
| **Total** | **3238** | **4** | **0** | **0** |

Los **3238** supervivientes son brechas de aserción: sus funciones se ejecutan,
pero los tests no detectan el cambio. **No hay ningún caso sin cobertura** que
pueda resolverse solo añadiendo un test de humo; hace falta aserción exacta.

### Preflight — 337

| Función | Casos |
|---|---:|
| `dependencias_declaradas` | 68 |
| `main` | 35 |
| `cargar_modulos` | 27 |
| `revisar_imports` | 29 |
| `revisar_silencios` | 28 |
| `modulos_locales` | 26 |
| `revisar_duplicados` | 21 |
| `_alias_asyncio` | 21 |
| `imprimir` | 20 |
| `_es_main` | 13 |
| `revisar_tareas` | 12 |
| `_nombre_requisito` | 7 |

### Evaluador — 2901

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

## Los 4 timeouts

Los cuatro se clasifican como **`timeout_no_equivalente`**: no son mutantes
equivalentes; introducen efectos no acotados.

| Mutante | Cambio | Riesgo |
|---|---|---|
| `x_ejecutar_tests__mutmut_15` | `cwd=str(ruta)` → `cwd=None` | ejecuta la suite en el directorio equivocado; puede colgarse |
| `x_ejecutar_tests__mutmut_21` | elimina `cwd=str(ruta)` | mismo riesgo |
| `x_main__mutmut_137` | `a or b` → `a and b` | activa la ruta LLM/red solo en combinaciones no previstas |
| `x_main__mutmut_139` | `if not KEY` → `if KEY` | invierte la comprobación de clave; intenta red sin clave |

No se matan con la suite actual. Necesitan tests con **mocks y timeouts
acotados**, no ejecuciones reales.

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

Los JSON completos de este triaje están en `build/triaje-preflight.json` y
`build/triaje-evaluar.json` (ignorados por git). Este documento conserva el
resumen y la clasificación.

## Conclusión

- **Triaje de inventario:** completo, 3242/3242 casos con categoría.
- **Equivalentes demostrados:** 0. No se usa «equivalente» como cajón de sastre.
- **Tasa:** 645/1015 (preflight) y 3034/5939 (evaluador); no cambia por
  clasificar. Los 4 timeouts no son muertos.
- **R3 no se cierra como tasa limpia:** quedan 3238 aserciones por reforzar y 4
  timeouts por acotar. El triaje convierte 3238 incógnitas en deuda accionable.
