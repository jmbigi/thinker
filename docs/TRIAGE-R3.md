# Triaje R3 — 668 brechas, 102 equivalencias y 0 timeouts

> Estado: **inventario completo, deuda abierta**. Cada caso tiene categoría;
> las equivalencias tienen prueba en `docs/TRIAGE-EQUIVALENCIAS.md`. Última
> medición global: 2026-10-28 (batch r3c4); cierre acotado de Poetry y corrección
> aritmética del inventario: 2026-11-01.

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
| Evaluador | **668** | **53** | **0** | **0** |
| **Total** | **668** | **102** | **0** | **0** |

Los **668** casos de brecha son aserciones que faltan: sus funciones se
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

### Evaluador — 673 brechas + 35 equivalencias

Re-medición 2026-10-28 (batch r3c4): **5984 mutantes, 4846 muertos, 1138
supervivientes, 0 sin tests, 0 timeouts, 0 sospechosos**; tasa bruta
**80,98%** (antes 79,61%). `evaluar` pasa de 75 a **5**, los cinco
equivalencias demostradas (E2-E5 en `docs/TRIAGE-EQUIVALENCIAS.md`, Hallazgo
140; 16 tests de contrato exacto en `TestEvaluarContrato`, incluidos los
bordes 0.500/0.800 que solo son alcanzables con `--ejecutar-tests`, total 30).
Lote 2026-10-28 (Hallazgo 144): `evaluar_herramientas` pasa de 70 a **0
brechas** — **64 muertos** verificados diff a diff y **6 equivalencias
demostradas** (E6-E8) con 16 tests de contrato exacto
(`tests/test_herramientas_contrato.py`). Distribución por función (completa
en `build/triaje-eval-r3c4.json`; el clúster evaluar_herramientas ya cerrado):

| Función | Casos |
|---|---:|
| `evaluar_herramientas` | 0 (64 muertos + 6 equivalencias) |
| `main` | 0 (65 muertos + 2 equivalencias) |
| `_dependencias_pyproject` | 0 (48 muertos + 1 equivalencia) |
| `evaluar_calidad` | 0 (47 muertos) |
| `_dependencias` | 0 (44 muertos + 2 equivalencias) |
| `licencias_no_runtime` | 0 (37 muertos) |
| `parsear_requisitos` | 0 (35 muertos + 1 equivalencia) |
| `_ambito_requirements` | 0 (19 muertos + 14 equivalencias) |
| `_versiones_lock` | 0 (32 muertos + 2 equivalencias) |
| `evaluar_inteligencia` | 0 (30 muertos) |
| `sintetizar_con_llm` | 0 (29 muertos) |
| `evaluar` | 5 (equivalencias) |

Cierre dirigido de `_ambito_requirements` (2026-10-31): **77 mutantes, 63
muertos y 14 supervivientes**, todos equivalentes demostradas (E9). Los 44
muertos de r3c4 pasan a 63 (+19) y los 33 supervivientes a 14, todos
reclasificados; el clúster de 33 queda cerrado. Dos regresiones cubren todas
las marcas de nombres y los bordes de ruta. Se confirmaron 10/10 muertes con la
selección real y los 14 equivalentes en 11 contratos de ruta, con el fuente
restaurado. Evidencia: `build/ambito-r3-verificacion.json`. Contabilidad:
**1067 → 1034 brechas** y **62 → 76 equivalencias**, sin nueva tasa global.

Cierre dirigido de `licencias_no_runtime` (2026-10-31): **120 mutantes, 120
muertos y 0 supervivientes**. Diez muertes se confirmaron aplicando los diffs y
ejecutando la selección real, con el fuente restaurado. No fueron necesarios
cambios de producción ni nuevos tests. Evidencia:
`build/licencias-r3-verificacion.json`. El clúster de 37 queda cerrado:
**1034 → 997 brechas**, con **76 equivalencias** intactas y sin nueva tasa
global.

Cierre dirigido de `_dependencias_pyproject` (2026-10-31): **259 mutantes, 258
muertos y 1 equivalencia (E10), 0 brechas**. El mutante 5 sobrevivió a la
primera muestra directa; se demostró que `None` y `""` siguen el mismo fallback
en TOML inválido con/sin dependencias y válido. Otras 10 muertes no equivalentes
se confirmaron con la selección real, con el fuente restaurado. Evidencia:
`build/pyproject-r3-verificacion.json`. El clúster de 48 queda cerrado:
**997 → 949 brechas** y **76 → 77 equivalencias**, sin nueva tasa global.

Cierre dirigido de `_versiones_lock` (2026-10-31): **203 mutantes, 201 muertos
y 2 equivalencias (E11), 0 brechas**. Los valores ausentes de `package` producen
las mismas cero iteraciones. El mutante 12 reveló una brecha real con paquetes
incompletos y quedó cubierto por una nueva regresión. Diez muertes no equivalentes
y dos equivalencias fueron verificadas, con el fuente restaurado. Evidencia:
`build/lock-r3-verificacion.json`. El clúster de 32 queda cerrado:
**949 → 917 brechas** y **77 → 79 equivalencias**, sin nueva tasa global.

Cierre dirigido de `_dependencias` (2026-10-31): **138 mutantes, 136 muertos
y 2 equivalencias (E12), 0 brechas**. `vistos_req=None` usa la inicialización
ya existente del lector, con deduplicación idéntica; los directorios admitidos
por el filtro de manifiestos producen lecturas vacías. Diez muertes no
equivalentes (1, 3–5 y 7–12) se confirmaron aplicando los diffs y ejecutando
`tests.test_evaluar_proyecto`, `tests.test_evaluador_corpus` y
`tests.test_evaluador_precision`, con el fuente restaurado. No fueron necesarios
cambios de producción ni nuevos tests. Evidencia:
`build/deps-r3-verificacion.json`. El clúster de 44 queda cerrado:
**917 → 879 brechas** y **79 → 81 equivalencias**, sin nueva tasa global.

Cierre dirigido de `main` (2026-10-31): **162 mutantes, 160 muertos y 2
equivalencias (E13), 0 brechas**. La campaña inicial produjo 97 muertos y 65
supervivientes; diez muertes fueron confirmadas directamente. Dos regresiones
fijan el contrato de ayuda y `con_red=True` por defecto, y la segunda campaña
dejó 158 muertos y 4 supervivientes. Los mutantes 3 y 12 murieron al aplicar la
verificación final; 76 y 108 eliminan el `default=None` que `argparse` ya asigna
y fueron equivalentes. El original restaurado pasó la selección. Evidencia:
`build/main-r3-verificacion.json`. El clúster de 65 queda cerrado sin cambios
de producción: **879 → 814 brechas** y **81 → 83 equivalencias**, sin nueva
tasa global.

Cierre dirigido de `evaluar_calidad` (2026-10-31): **339 mutantes, 339
muertos y 0 supervivientes**. Diez diffs representativos (1–5, 50, 100, 200,
300 y 339) fueron detectados al aplicarlos y ejecutar la selección real; el
original restaurado también pasó. No fueron necesarios cambios de producción
ni nuevos tests. Evidencia: `build/calidad-r3-verificacion.json`. El clúster
de 47 queda cerrado: **814 → 767 brechas**, con **83 equivalencias** intactas
y sin nueva tasa global.

Cierre dirigido de `parsear_requisitos` (2026-10-31): **218 mutantes, 217
muertos y 1 equivalencia (E14), 0 brechas**. La campaña inicial declaró 218/218
muertos, pero la muestra directa encontró dos supervivientes. El mutante 3 cambia
una excepción inalcanzable; el 218 reveló una brecha en el mensaje de archivo sin
requisitos y quedó cubierto por una regresión exacta. Otras ocho muertes fueron
confirmadas y el original restaurado pasó la selección. Evidencia:
`build/requisitos-r3-verificacion.json`. El clúster de 35 queda cerrado sin
cambios de producción: **767 → 732 brechas** y **83 → 84 equivalencias**, sin
nueva tasa global.

Cierre dirigido de `evaluar_inteligencia` (2026-10-31): **139 mutantes, 139
muertos y 0 supervivientes**. La campaña declaró 139/139, pero la muestra directa
encontró que 130 y 139 sobrevivían al cambiar la evidencia de los hallazgos. Una
regresión fija el contrato completo de un proyecto LLM sin señales y mata ambos;
otras siete muertes fueron confirmadas y el original restaurado pasó. Evidencia:
`build/inteligencia-r3-verificacion.json`. El clúster de 30 queda cerrado sin
cambios de producción: **732 → 702 brechas**, con **84 equivalencias** intactas
y sin nueva tasa global.

Cierre dirigido de `sintetizar_con_llm` (2026-10-31): **139 mutantes, 139
muertos y 0 supervivientes**. La campaña reprodujo 110 muertos y 29 brechas.
Siete regresiones nuevas fijan los contratos restantes y otra exige el mensaje
exacto; los 29 supervivientes y diez mutantes de control fueron detectados al
aplicar sus diffs, con el original restaurado verde. Evidencia:
`build/sintesis-r3-verificacion.json`. El clúster de 29 queda cerrado sin cambios
de producción: **702 → 673 brechas**, con **84 equivalencias** intactas y sin
nueva tasa global.

Re-medición acotada de `evaluar_eficiencia` (2026-10-31): **190 mutantes, 190
muertos y 0 supervivientes**. Diez diffs representativos fueron detectados al
aplicarlos y el original restaurado pasó. No fueron necesarios cambios de
producción ni tests. Evidencia: `build/eficiencia-r3-verificacion.json`. La
contabilidad permanece en **673 brechas + 84 equivalencias**: sin la distribución
histórica detallada no se asigna un descuento.

Cierre acotado de `_digesto` (2026-10-31): **68 mutantes, 68 muertos y 0
supervivientes**. La campaña inicial produjo 55 muertos y 13 brechas. Tres
regresiones fijan el límite de 20 hallazgos, los defaults de cobertura y el
marcador sin fallos. Los 13 supervivientes y diez controles fueron detectados al
aplicar sus diffs, con el original restaurado verde. Evidencia:
`build/digesto-r3-verificacion.json`. La contabilidad permanece en **673 brechas
+ 84 equivalencias** por falta de distribución histórica detallada.

Cierre acotado de `evaluar_funcionalidades` (2026-10-31): **224 mutantes, 224
muertos y 0 supervivientes**. La campaña declaró 224/224, pero la muestra directa
encontró dos supervivientes: 50 (`README.txt`) y 100 (severidad del módulo
prometido). Una regresión con `README.txt` y una referencia inexistente mata
ambos; otros ocho controles murieron y el original restaurado pasó. Evidencia:
`build/funcionalidades-r3-verificacion.json`. La contabilidad permanece en
**673 brechas + 84 equivalencias** por falta de distribución histórica.

Re-medición acotada de `detectar_comando_tests` (2026-10-31): **235 mutantes,
235 muertos y 0 supervivientes**. Diez diffs representativos fueron detectados
al aplicarlos y el original restaurado pasó. No fueron necesarios cambios de
producción ni tests. Evidencia: `build/runner-r3-verificacion.json`. La
contabilidad permanece en **673 brechas + 84 equivalencias** por falta de
distribución histórica detallada.

Verificación acotada de `_puntuacion_texto` (2026-10-31): **4 mutantes, 4
muertos y 0 supervivientes**. Los cuatro diffs fueron detectados al aplicarlos
directamente y el original restaurado pasó. No fueron necesarios cambios de
producción ni tests. Evidencia: `build/puntuacion-r3-verificacion.json`. La
contabilidad permanece en **673 brechas + 84 equivalencias**.

Cierre acotado de `investigar_preguntas` (2026-10-31): **43 mutantes, 43
muertos y 0 supervivientes**. La campaña inicial produjo 29 muertos y 14 brechas.
Cuatro regresiones fijan límite de fuentes, consulta, recuperación de errores y
metadatos ausentes. Los 14 supervivientes y diez controles fueron detectados al
aplicar sus diffs, con el original restaurado verde. Evidencia:
`build/investigar-r3-verificacion.json`. La contabilidad permanece en
**673 brechas + 84 equivalencias** por falta de distribución histórica.

Cierre acotado de `_linter_configurado` (2026-10-31): **79 mutantes, 78 muertos
+ 1 equivalencia (E15), 0 supervivientes**. La muestra directa detectó 60 y 70
vivos pese al 79/79 inicial. El 60 solo cambia mayúsculas bajo `re.I` y conserva
idéntica salida en seis variantes; el 70 cambia el glob `eslint.config.*` y muere
al añadir `eslint.config.js` a la regresión existente. Otros ocho controles
murieron y el original restaurado pasó. Evidencia:
`build/linter-r3-verificacion.json`. La contabilidad permanece en **673 brechas**
y sube a **85 equivalencias** por falta de distribución histórica.

Cierre acotado de `_tiene_punto_entrada` (2026-10-31): **90 mutantes, 90
muertos y 0 supervivientes**. La muestra directa detectó 60 y 80 vivos pese al
90/90 inicial: faltaban `setup.cfg` con `console_scripts` y `package.json` con
solo `bin` o solo `main`. Una regresión con tres subcasos mata ambos; otros ocho
controles murieron y el original restaurado pasó. Evidencia:
`build/entry-r3-verificacion.json`. La contabilidad permanece en
**673 brechas + 85 equivalencias** por falta de distribución histórica.

Cierre acotado de `plan_texto` (2026-10-31): **42 mutantes, 39 muertos + 3
equivalencias (E16), 0 supervivientes**. La campaña produjo 33 muertos y 9 brechas.
Una regresión fija el mensaje vacío y el orden exacto, matando 35 por orden
estable; 3/5/41 conservan salidas idénticas y son equivalentes. Los otros seis
supervivientes y diez controles murieron, con el original restaurado verde.
Evidencia: `build/plan-r3-verificacion.json`. La contabilidad permanece en
**673 brechas** y sube a **86 equivalencias** por falta de distribución histórica.

Cierre acotado de `_registro_decisiones` (2026-10-31): **57 mutantes, 57
muertos y 0 supervivientes**. La muestra directa detectó 2, 3, 15 y 25 vivos pese
al 57/57 inicial. Una regresión con `ADR-001.md`, `releasenotes.md` y
`decision.adoc` mata los cuatro; otros seis controles murieron y el original
restaurado pasó. Evidencia: `build/decisiones-r3-verificacion.json`. La
contabilidad permanece en **673 brechas + 86 equivalencias** por falta de
distribución histórica.

Cierre acotado de `_normalizar_release` (2026-10-31): **20 mutantes, 20 muertos
y 0 supervivientes**. Una regresión fija entradas no numéricas, prefijos y
sufijos, separadores y eliminación de ceros finales. Los 20 diffs fueron
detectados al aplicarlos al módulo real y el original restaurado pasó. No fueron
necesarios cambios de producción. Evidencia: `build/release-r3-verificacion.json`.
La contabilidad permanece en **673 brechas + 86 equivalencias** por falta de
distribución histórica.

Cierre acotado de `_es_manifiesto` (2026-10-31): **26 mutantes, 24 muertos + 2
equivalencias (E17), 0 supervivientes**. Una regresión fija 23 rutas de
manifiestos, locks y `requirements/*`. Los 24 diffs no equivalentes fueron
detectados directamente; 6 y 7 produjeron salidas idénticas al original en 20
rutas y tienen prueba en E17. El original restaurado pasó, sin cambios de
producción. Evidencias: `build/manifiestos-r3-verificacion.json` y
`build/manifiestos-e17-verificacion.json`. La contabilidad permanece en **673
brechas** y sube a **88 equivalencias** por falta de distribución histórica.

Cierre acotado de `_es_no_codigo` (2026-10-31): **7 mutantes, 7 muertos y 0
supervivientes**. Una regresión con 19 rutas fija los directorios excluidos y
archivos con nombres parecidos. Los siete diffs fueron detectados al aplicarlos
al módulo real y el original restaurado pasó. No fueron necesarios cambios de
producción. Evidencia: `build/no-codigo-r3-verificacion.json`. La contabilidad
permanece en **673 brechas + 88 equivalencias** por falta de distribución
histórica.

Cierre acotado de `_es_lock_python` (2026-10-31): **12 mutantes, 12 muertos y 0
supervivientes**. Una regresión con 16 rutas fija locks Python, locks npm,
mayúsculas, extensiones y directorios `requirements/*`. Los 12 diffs fueron
detectados al aplicarlos al módulo real y el original restaurado pasó. No fueron
necesarios cambios de producción. Evidencia: `build/lock-python-r3-verificacion.json`.
La contabilidad permanece en **673 brechas + 88 equivalencias** por falta de
distribución histórica.

Cierre acotado de `_es_test` (2026-10-31): **39 mutantes, 36 muertos + 2
equivalencias (E18), 0 supervivientes**. Una regresión con 26 rutas fija Python,
JS/TS, Go, Java y directorios de tests. El mutante 36 elimina `src/test/` y muere;
37/39 producen salidas idénticas en 28 rutas y tienen prueba en E18. El original
restaurado pasó, sin cambios de producción. Evidencias:
`build/es-test-r3-verificacion.json` y `build/es-test-e18-verificacion.json`.
La contabilidad permanece en **673 brechas** y sube a **90 equivalencias** por
falta de distribución histórica.

Cierre acotado de `_es_lock` (2026-10-31): **51 mutantes objetivo, 46 muertos +
5 equivalencias (E19), 0 supervivientes**. La campaña generó 135 mutantes
incluyendo helpers; el clúster tiene 51. Una regresión con 27 comprobaciones fija
mayoría estricta, hashes, comentarios y directivas. Los casos 24, 29 y 32 murieron
con las dos nuevas fronteras; 15–17 y 23/26 son equivalentes demostradas. El
original restaurado pasó, sin cambios de producción. Evidencias:
`build/es-lock-r3-verificacion.json` y `build/es-lock-e19-verificacion.json`.
La contabilidad permanece en **673 brechas** y sube a **95 equivalencias** por
falta de distribución histórica.

Cierre acotado de `_parsear_requisito` (2026-10-31): **75 mutantes, 72 muertos +
3 equivalencias (E20), 0 supervivientes**. La verificación directa inicial dejó
67 muertos y ocho supervivientes. Un contrato con siete formas válidas y 14
entradas rechazadas mató 1, 11, 12, 33 y 34. Los casos 10 y 13 conservan el primer
segmento; 18 es redundante con la regex que ya rechaza directivas. El original
restaurado pasó, sin cambios de producción. Evidencias:
`build/parser-r3-verificacion.json` y `build/parser-e20-verificacion.json`.
La contabilidad permanece en **673 brechas** y sube a **98 equivalencias** por
falta de distribución histórica.

Cierre acotado de `_resolver_evidencia`, `_verificar_archivo` y
`_verificar_formal` (2026-10-31): **71 mutantes, 71 muertos y 0 supervivientes**.
La verificación directa inicial detectó 62; las pruebas exactas de mensajes,
procedencia y evidencia externa mataron ocho más. El caso 3 de
`_resolver_evidencia` parecía equivalente, pero `XXapp.pyXX` demostró que añadir
`X` al argumento de `strip()` cambia el resultado; una regresión lo mató. No se
registró una equivalencia. Un bucle de symlinks producía `RuntimeError` en
Python 3.11: ahora se declara evidencia no verificable en vez de interrumpir el
análisis. Evidencias: `build/requisitos-verificacion-directa.json`,
`build/requisitos-verificacion-cierre.json` y
`build/resolver-mutante3-cierre.json`. La contabilidad permanece en **673
brechas + 98 equivalencias** por falta de distribución histórica.

Cierre histórico de `_requisito_poetry` (2026-11-01): los mutantes 5–9
sobrevivían tanto al commit r3c4 `5623448` como al código actual. La traducción
de rangos Poetry `^`/`~` a PEP 508 y dos regresiones nuevas cierran los cinco.
La función corregida genera 87 mutantes: 79 muertos en campaña, seis más tras
reforzar aserciones y dos equivalencias de `UserWarning` por defecto (E21).
Resultado: **85 muertos + 2 equivalencias, 0 brechas**. Los cinco históricos
también mueren en verificación directa; original restaurado. Evidencias:
`build/poetry-comparativa-r3.json`, `build/poetry-cierre-actual.json`,
`build/poetry-verificacion-directa.json` y
`build/poetry-historicos-verificacion.json`. R3 pasa de 673 a **668 brechas**.
El total de equivalencias corrige además el desfase de E16 (tres casos sumados
como uno): era 49+51=100, no 98; con E21 queda en **102** (49+53), sin nueva
tasa global.

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

- **Triaje de inventario:** r3c4 completo, con cierres dirigidos posteriores de
  `_ambito_requirements`, `licencias_no_runtime`, `_dependencias_pyproject`,
  `_versiones_lock`, `_dependencias`, `main`, `evaluar_calidad`,
  `parsear_requisitos`, `evaluar_inteligencia`, `sintetizar_con_llm`,
  `_linter_configurado`, `_tiene_punto_entrada`, `plan_texto`,
  `_registro_decisiones`, `_normalizar_release`, `_es_manifiesto`,
  `_es_no_codigo`, `_es_lock_python`, `_es_test`, `_es_lock`,
  `_parsear_requisito`, `_resolver_evidencia`, `_verificar_archivo`,
  `_verificar_formal` y `_requisito_poetry`: **668 brechas + 102 equivalencias**.
- **Equivalentes demostrados:** 102 (49 en preflight y 53 en el evaluador), todos
  con prueba; no se cuentan como muertos. El total corrige el desfase de E16,
  que había sumado tres equivalencias como una.
- **Tasas históricas:** 967/1016 (preflight) y 4846/5984 (evaluador); no se
  recalculan por clasificar. Los timeouts quedaron en 0.
- **R3 no se cierra como tasa limpia:** quedan **668 brechas**, todas del
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
  mutmut 3.6.0 reprodujo el artefacto, y también mutmut 3.8.1 y
  `--max-children 1` (cuatro hipótesis descartadas; Hallazgo 143). Causa raíz
  **no determinada**; las campañas del evaluador quedan **bloqueadas como
  medición**. La cifra oficial vigente es la de r3c4 (4846/5984; 1131 brechas)
  hasta que una campaña pase esta verificación.
