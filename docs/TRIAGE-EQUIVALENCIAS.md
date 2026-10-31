# Triaje semántico de preflight (R3) — 49 equivalentes, 0 brechas

**Fecha:** 2026-10-26. **Base:** campaña de preflight `1016` mutantes,
`967` muertos, `49` supervivientes, `0` timeouts. Este documento **no cambia la
tasa**: los equivalentes no se cuentan como muertos. Solo evita llamar
«brecha» a una mutación que produce exactamente el mismo resultado observable.

## Método

Una mutación es **equivalente** aquí solo si se puede demostrar que el programa
observable es idéntico para todas las entradas válidas, no si «pasa los tests».
Las pruebas se apoyan en el código, la semántica de Python y tests ya
existentes; no se declara equivalente ninguna mutación de la que no haya una
razón completa. Las 9 restantes se dejan como brechas reales o no demostradas.

## Grupos demostrados (49)

### 1. Codificación `"UTF-8"` frente a `"utf-8"` (7)

Mutantes: `dependencias_declaradas` 51, 158, 211; `revisar_duplicados` 33;
`_leer_requisitos` 10; `cargar_modulos` 13; `revisar_silencios` 9.

**Prueba:** los nombres de códec de Python no distinguen mayúsculas
(`codecs.lookup("UTF-8").name == "utf-8"`); `open(..., encoding=...)` usa el
mismo códec. `Path.read_text("UTF-8")` y `read_text("utf-8")` leen los mismos
bytes. Verificado en esta máquina.

### 2. Defaults de `dict.get` que el helper ya trata (14)

Mutantes: `dependencias_declaradas` 76, 78, 83, 85, 102, 104, 113, 115, 125,
127, 132, 134, 141, 143.

**Prueba:** cuando la clave falta, `[]`, `{}`, `None` y el default omitido son
indistinguibles en este código:

- `_nombres_de_lista(None)` devuelve `set()` (test
  `test_nombres_de_lista_y_setup`).
- `isinstance(None, dict)` es `False`; un `{}` vacío no aporta nombres.
- Los bucles solo se ejecutan si el valor es `dict`/`list`; un `None` los
  omite y un contenedor vacío no añade nada.

No hay efecto lateral: los valores no se mutan ni se registran.

### 3. `configparser` y mayúsculas en opciones (2)

Mutantes: `dependencias_declaradas` 179, 183 (`INSTALL_REQUIRES`,
`TESTS_REQUIRE`).

**Prueba:** `ConfigParser.optionxform` convierte las opciones a minúsculas por
defecto; `has_option("options", "INSTALL_REQUIRES")` consulta
`install_requires`. Verificado.

### 4. `valor = ""` frente a `None` en `setup.py` (1)

Mutante: `dependencias_declaradas` 246.

**Prueba:** `_nombres_setup("")` devuelve `set()`; el `if valor is not None`
solo decide si llamar al helper, y la llamada no añade nombres. El resultado es
el mismo.

### 5. `type_ignores=None` frente a `[]` (2)

Mutantes: `revisar_duplicados` 12, 14.

**Prueba:** ambos lados construyen `ast.Module(..., type_ignores=<mismo
valor>)` para **todas** las funciones de la misma pasada. El hash cambia de
texto, pero la relación «firma de A == firma de B» no cambia: se comparan dos
dumps generados con el mismo valor. No hay hashes persistidos entre ejecuciones.

### 6. `include_attributes` falsy (2)

Mutantes: `revisar_duplicados` 28, 30 (`None` u omitido frente a `False`).

**Prueba:** `ast.dump` trata `include_attributes` como booleano; `None` y el
default `False` producen el mismo texto. Verificado:
`ast.dump(..., include_attributes=None) == ast.dump(..., include_attributes=False)`.

### 7. Severidad por defecto `"media"` (2)

Mutantes: `revisar_duplicados` 49, `revisar_tareas` 30.

**Prueba:** `Hallazgo` declara `severidad: str = "media"`; omitir el argumento
produce exactamente `"media"`.

### 8. `--allow` sin valor: `[]`, `None` y omitido (2)

Mutantes: `main` 32, 37.

**Prueba:** `main` pasa `args.allow` a `ejecutar` y de ahí a
`revisar_imports`; allí `permitidos or ()` convierte `None` y `[]` en la misma
tupla vacía. `_normalizar` solo se aplica a elementos existentes.

### 9. Primer elemento de `split("#", ...)` (6)

Mutantes: `_leer_requisitos` 15, 18; `_nombre_requisito` 5, 6, 7, 8.

**Prueba:** `split("#", 1)[0]`, `split("#", 2)[0]` y `split("#")[0]` devuelven
siempre el prefijo anterior al primer `#`. En `_nombre_requisito`, el regex
`^([A-Za-z0-9_.\-]+)` solo mira el nombre inicial: `rsplit` o no dividir dejan
intacto ese prefijo; si la línea empieza por `#` o está vacía, ambos caminos
devuelven `None`. No se incluyen aquí los mutantes de `_leer_requisitos` que
cambian la ruta de un `-r` con comentarios: esos no son equivalentes (se
probaron y se corrigió el test correspondiente).

### 10. `filename` de `ast.parse` (2)

Mutantes: `cargar_modulos` 40, 41.

**Prueba:** `filename` solo se guarda en `SyntaxError.filename`; el código usa
`exc.msg` y `exc.lineno`, nunca `filename`. Los módulos y los hallazgos son
idénticos.

### 11. Línea de `ExceptHandler` y texto de reserva (3)

Mutantes: `revisar_silencios` 19, 20, 22.

**Prueba:** un `ExceptHandler` no puede estar en la línea 1: la gramática exige
un `try` anterior, así que `lineno >= 2`; `0 < lineno` y `1 < lineno` son
equivalentes, y `0 <= lineno` también. El texto de reserva `"XXXX"` solo se usa
si el índice de línea está fuera de rango; ese texto no coincide con
`_MARCA_SILENCIO`, igual que `""`, y el resultado (hallazgo) no cambia.

### 12. Condición redundante en `modulos_locales` (3)

Mutantes: `modulos_locales` 9, 16, 17.

**Prueba:** `(directorio / "__init__.py").exists()` implica
`any(directorio.glob("*.py"))` porque `__init__.py` es un `.py`; el `or` no
aporta nada. El `continue` del bucle `for base in (root, root / "src")`: `root`
es un directorio por contrato; si `root/src` no existe es la última iteración,
donde `continue` y `break` hacen lo mismo.

### 13. Paquete hermano ya está en `modulos_locales` (2)

Mutantes: `revisar_imports` 28, 29.

**Prueba:** `modulos_locales` recorre el árbol y añade todo directorio con
`__init__.py` o algún `.py`, incluidos los paquetes anidados; el conjunto
`hermanos |= {p.parent.name ...}` solo añade nombres que ya están en `locales`.
No se añaden módulos de directorios ignorados porque el archivo tampoco estaría
en `modulos`.

### 14. `continue` en el bucle de un `Import` opcional (1)

Mutante: `revisar_imports` 56 (`continue` → `break` cuando la línea está en
`opcionales`).

**Prueba:** para un `ast.Import`, todas las entradas de `importados` comparten
`nodo.lineno`; si esa línea es opcional, ninguna entrada se procesa y `break` o
`continue` terminan el bucle sin efectos. Para un `ast.ImportFrom` solo hay una
entrada. El resultado observable es el mismo.

## Sin brechas reales

Los 6 mutantes de `encoding=None` se mataron con un test que cambia la locale a
`C` **en proceso** (no en un subproceso): si `read_text` usa `None`, la lectura
falla y el test falla. `cargar_modulos` 60 se mató con un archivo con byte nulo
(`SyntaxError.lineno is None`, el informe debe decir línea 0); `revisar_imports`
59 se mató con `import os` seguido de `import os, requests`.

Los 49 supervivientes restantes están cubiertos por los grupos 1-14. No se
declara una equivalencia sin prueba; el mutante 56 se añadió aquí tras
comprobar que todas las entradas de un `Import` comparten línea.

## Consecuencia

- **Brechas reales de preflight:** **0**.
- **Equivalencias demostradas:** **49** (no cuentan como muertos).
- **Tasa de mutación:** **967/1016 = 95,18%**; no cambia por este triaje.
- No quedan brechas reales de preflight; las 49 equivalencias no se cuentan
  como muertos y no inflan la tasa.


## Evaluador: 2 equivalencias demostradas (2026-10-28, batch r3c2)

### E1. Default de `dict.get` en la comparación de versiones (2)

Mutantes: `evaluar_vigencia` 246 y 248 —
`perfil.versiones_lock.get(_clave_nombre(d["nombre"]), "")` muta a default
`None` (246) y a default omitido (248, equivalente a `None`).

**Prueba:** el valor solo se usa en `if not version: continue` y, cuando es
verdadero, en la comparación con PyPI. `None` y `""` son ambos falsos, así que
las tres formas ejecutan el mismo `continue` ante las mismas entradas y
ninguna dependencia sin versión llega a compararse: el programa observable es
idéntico. Verificado aplicando ambos mutantes al fuente: la clase
`TestVigenciaContrato` (que incluye los casos con dependencia sin versión)
sigue en verde; los 80 mutantes restantes de `evaluar_vigencia` mueren con
los tests de contrato exacto añadidos el 2026-10-28 (Hallazgo 139).

**Consecuencia para la contabilidad del evaluador:** los equivalentes no se
cuentan como muertos; pasan de «brecha» a «equivalencia demostrada». Tras el
lote: evaluador 1221 brechas + 2 equivalencias; total R3: 1221 brechas +
51 equivalencias.

### E2. `ruta` no se usa en `evaluar_inteligencia` (1)

Mutante: `evaluar` 46 — `evaluar_inteligencia(ruta, perfil)` muta a
`evaluar_inteligencia(None, perfil)`.

**Prueba:** el cuerpo de `evaluar_inteligencia` (líneas 1823-1858 de
`evaluar_proyecto.py`) no referencia `ruta` en ninguna línea: todos los
criterios se calculan desde `perfil` (`perfil.es_llm`, `perfil.codigo_py`).
Pasar `None` es inobservable para cualquier entrada. Verificado aplicando el
mutante al fuente: `TestEvaluarContrato` sigue en verde.

### E3. `next(...)` sin default al buscar la dimensión `calidad` (1)

Mutante: `evaluar` 62 — `next((d for d in dimensiones if d.nombre ==
"calidad"), None)` muta a `next(...)` sin default.

**Prueba:** `dimensiones` es una lista literal construida dos líneas antes en
la propia función `evaluar`, y uno de sus elementos es siempre
`evaluar_calidad(...)` (cuyo `nombre` es `"calidad"` por construcción de
`Dimension`). El generador siempre produce un elemento, así que el default
`None` nunca se usa: con o sin él el resultado es idéntico y nunca se eleva
`StopIteration`.

### E4. Rama `else 0.0` del ratio de cobertura es inalcanzable (1)

Mutante: `evaluar` 134 — `ratio = round(...) if total_criterios else 0.0`
muta el `0.0` a `1.0`.

**Prueba:** la rama `else` solo se ejecuta con `total_criterios == 0`, es
decir, cero criterios evaluados y cero N/A en las seis dimensiones. Pero
`evaluar_herramientas` asigna `h1_manifiesto`, `h2_licencia` y
`h7_decisiones_documentadas` **incondicionalmente** (sin guarda de perfil), así
que `evaluados >= 3` para cualquier proyecto. Verificado empíricamente: un
directorio vacío y uno con solo un README dan `evaluados = 3` (los tres
criterios de herramientas). `total_criterios` nunca es 0 y la rama está
muerta.

### E5. `"py"` nunca es un lenguaje del perfil (2)

Mutantes: `evaluar` 141 y 142 — el segundo elemento de la tupla
`("python", "py")` del filtro `leng.lower() not in (...)` muta a `"XXpyXX"` y
a `"PY"`.

**Prueba:** `perfil.lenguajes` se construye en `analizar_perfil` exclusivamente
con los **valores** de `EXTENSIONES` (`".py" → "Python"`, `".java" → "Java"`,
etc.); ninguno es `"py"`. Además `leng.lower()` siempre produce minúsculas, así
que `"PY"` tampoco puede casar. La pertenencia al segundo elemento de la tupla
es inobservable para cualquier proyecto real. Verificado aplicando ambos
mutantes: `TestEvaluarContrato` (que incluye un proyecto Python + JavaScript +
Java) sigue en verde.

**Consecuencia del segundo lote del evaluador (2026-10-28, clúster
`evaluar`):** 75 supervivientes triados → **70 mutantes muertos** con 16 tests
nuevos de contrato exacto en `TestEvaluarContrato` (firma por defecto con red,
mensaje de `ValueError`, nota de aserciones débiles solo en calidad, global con
redondeo a 3 decimales, `no_verificado` exacto con y sin código, notas de
lenguajes con dos no-Python, cobertura completa 29/29, niveles en los bordes
observables 0.500 y 0.800 —alcanzables con `--ejecutar-tests`, que añade
`c1b_suite_pasa` y sube el total a 30—, claves y valores del informe, e
investigación opt-in con `StubLLM`/`StubSearch` y `investigar_preguntas`
patcheada) y **5 equivalencias demostradas** (E2-E5). Verificación estilo
mutmut aplicando los 75 diffs uno a uno: 70/70 muertos y los 5 equivalentes
siguiendo en verde. Contabilidad del evaluador: 1221 − 75 = **1146 brechas** +
**7 equivalencias** (E1 + E2-E5).

### E6. Patrón de licencia en minúsculas con `re.I` (1)

Mutante: `evaluar_herramientas` 52 — `re.match(r"(LICEN[CS]E|COPYING)",
p.name, re.I)` muta el patrón a minúsculas `(licen[cs]e|copying)`.

**Prueba:** con `re.IGNORECASE` el conjunto de nombres que casan es
exactamente el mismo para ambos patrones (los corchetes ya cubren ambas
mayúsculas y `re.I` cubre el resto). Inobservable para cualquier proyecto.
Verificado aplicando el mutante: `tests/test_herramientas_contrato.py` sigue
en verde.

### E7. Rama `runner_extra` con `tox.ini`/`noxfile.py` inalcanzable (4)

Mutantes: `evaluar_herramientas` 158, 159 (`tox.ini` → `XXtox.iniXX` /
`TOX.INI`) y 161, 162 (`noxfile.py` → `XXnoxfile.pyXX` / `NOXFILE.PY`).

**Prueba:** `detectar_comando_tests` reconoce `tox.ini` y `noxfile.py` como
runner **siempre que existen** (origen `tox.ini` / `noxfile.py`, verificado en
el test `test_tox_y_noxfile_se_detectan_por_deteccion_no_por_runner_extra`):
la rama `elif runner_extra` solo se ejecuta cuando `deteccion` es None, y
`next()` de `(build.sh, tox.ini, noxfile.py)` solo puede devolver `build.sh`
—los otros dos ya habrían producido detección—. Las mutaciones sobre esas dos
tuplas son código inalcanzable.

### E8. `root` no se usa en `cargar_modulos` con `archivos` dados (1)

Mutante: `evaluar_herramientas` 315 —
`cargar_modulos(None, archivos=perfil.codigo_paquete)`.

**Prueba:** `cargar_modulos` solo usa `root` para `archivos_python(root)`
cuando `archivos is None` (aquí nunca) y para `_relativa(root, ruta)` al
registrar un hallazgo de **sintaxis**; con código parseable no se ejecuta
ninguna. Verificado aplicando el mutante: la clase de contrato sigue en verde.

**Consecuencia del tercer lote del evaluador (2026-10-28, clúster
`evaluar_herramientas`):** 70 supervivientes triados → **64 mutantes muertos**
con 16 tests de contrato exacto en `tests/test_herramientas_contrato.py`
(manifiestos con truncado en 8/9, licencia con mayúscula, cada señal de CI
aislada, runner por `build.sh`, h5 con libres/no libres/no verificables
—error con licencia conocida y dos no-libres—, h6 con módulo del lock y con
import de tercero, h7 con 9 fuentes) y **6 equivalencias demostradas**
(E6-E8). Verificación diff a diff: 70/70 aplicados, 64 muertos y los 6
equivalentes en verde. Contabilidad del evaluador: 1131 − 64 = **1067
brechas** + **62 equivalencias** (E1-E8), pendiente de re-medición oficial
cuando la herramienta vuelva a ser fiable (Hallazgo 143).

### E9. Marcas redundantes de `_ambito_requirements` (14)

Mutantes 23/24 (`mkdocs`) y 34-45 (`dev`, `lint`, `type`, `ci`, `bench`,
`check`, cada uno en dos formas).

**Prueba:** `mkdocs` contiene la subcadena `doc`, así que quitar la tercera
marca no altera la condición. Las marcas de desarrollo devuelven `dev`, igual
que el fallback; las rutas `runtime` explícitas no contienen esas marcas. Por
tanto las 14 mutaciones producen exactamente las mismas salidas.

**Verificación (2026-10-31):** campaña acotada de 77 mutantes con mutmut 3.6.0:
63 muertos y 14 supervivientes, todos equivalentes. Diez muertes se confirmaron
aplicando los diffs y ejecutando la selección; cada uno de los 14 se comparó
contra el original en 11 contratos de ruta, con salidas idénticas y fuente
restaurado. Evidencia: `build/ambito-r3-verificacion.json`.

**Contabilidad:** 44 → 63 muertos (+19) y 33 → 14 supervivientes, todos
reclasificados como equivalentes. El clúster de 33 queda cerrado: R3 pasa de
1067 a **1034 brechas** y de 62 a **76 equivalencias**. No se recalcula la tasa
global histórica.

### E10. `None` y `""` siguen el mismo fallback de TOML (1)

Mutante 5 de `_dependencias_pyproject`: `datos = None` cambia a `datos = ""` al
capturar `TOMLDecodeError`.

**Prueba:** ambos valores no son instancias de `dict`; por tanto entran en la
misma rama `if not isinstance(datos, dict)` y usan el fallback textual. La salida
es idéntica en TOML inválido con dependencias, inválido sin dependencias y TOML
válido. El mutante sobrevivió a la primera muestra directa y se investigó en vez
de ocultarlo; otras 10 muertes no equivalentes fueron confirmadas.

**Contabilidad (2026-10-31):** 259 mutantes: **258 muertos + 1 equivalente, 0
brechas**. El clúster de 48 queda cerrado: R3 pasa de 997 a **949 brechas** y de
76 a **77 equivalencias**. Evidencia: `build/pyproject-r3-verificacion.json`.

### E11. Valores ausentes de `package` no producen iteraciones (2)

Mutantes 7 y 9 de `_versiones_lock`: el valor por omisión de `package` cambia de
`[]` a `None` o se elimina el segundo argumento de `get`, que también es `None`.

**Prueba:** con la clave ausente, `isinstance(paquetes, list)` es falso en ambos
casos y se ejecuta la lista vacía `[]`; no hay iteraciones. Con la clave presente,
el valor por omisión no interviene. Original y mutantes devolvieron el mismo
resultado en `uv.lock` vacío, `poetry.lock` válido y `pdm.lock` con `package` de
tipo incorrecto.

**Contabilidad (2026-10-31):** 203 mutantes: **201 muertos + 2 equivalentes, 0
brechas**. El mutante 12 no era equivalente y quedó cubierto por una regresión de
paquetes incompletos. El clúster de 32 queda cerrado: R3 pasa de 949 a **917
brechas** y de 77 a **79 equivalencias**. Evidencia:
`build/lock-r3-verificacion.json`.

### E12. Inicialización y filtros redundantes de `_dependencias` (2)

Mutante 2: `vistos_req = set()` cambia a `vistos_req = None`. Mutante 6:
`p.is_file() and not any(...)` cambia a `p.is_file() or not any(...)` al seleccionar
manifiestos.

**Prueba:** `_leer_requirements` inicializa el conjunto cuando recibe `None`, por lo
que un include compartido con dependencias duplicadas produce la misma salida en el
original y en el mutante 2. En el mutante 6, los directorios con nombres de
`requirements.txt`, `pyproject.toml`, `setup.cfg`, `setup.py` o `package.json`
pueden llegar a los lectores, pero estos devuelven vacío: no se añade ninguna
dependencia ni cambia el resultado.

**Verificación (2026-10-31):** campaña acotada de 138 mutantes con mutmut 3.6.0.
Se aplicaron diez muertes no equivalentes (1, 3–5 y 7–12) y se ejecutaron
`tests.test_evaluar_proyecto`, `tests.test_evaluador_corpus` y
`tests.test_evaluador_precision`; todas fueron detectadas. Las dos equivalencias
se comprobaron directamente, con el fuente restaurado. Evidencia:
`build/deps-r3-verificacion.json`.

**Contabilidad:** **136 muertos + 2 equivalentes, 0 brechas**. El clúster de 44
queda cerrado sin cambios de producción ni nuevos tests: R3 pasa de 917 a **879
brechas** y de 79 a **81 equivalencias**. No se recalcula la tasa global histórica.
