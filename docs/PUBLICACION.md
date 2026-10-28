# Publicación en PyPI — `thinker-research`

> Guía durable para publicar y mantener el paquete en PyPI.
> Estado al 2026-10-28: **versión `0.1.13` publicada en TestPyPI y PyPI**.
> Tags `v0.1.0`, `v0.1.1`, `v0.1.2`, `v0.1.3`, `v0.1.4`, `v0.1.5`, `v0.1.6`,
> `v0.1.7`, `v0.1.8`, `v0.1.9`, `v0.1.10`, `v0.1.11`, `v0.1.12` y `v0.1.13` empujados; `v0.1.2` a `v0.1.13` son anotados. `0.1.2` **no
> se publicó**: su README decía que PyPI estaba pendiente y la ficha se habría
> contradicho; `0.1.3` corrige el texto con una formulación durable. No se usa
> la CLI `gh` ni se crean GitHub Releases desde el repositorio (regla propia
> 12): la distribución se hace por PyPI/TestPyPI y tags de git. Detalle del
> renombrado en `LECCIONES-APRENDIDAS.md` (Hallazgo 85);
> incidencias de release en los Hallazgos 89, 90 y 91.

## Estado actual

- Nombre: **`thinker-research`** (`thinker` está ocupado desde 2017 por otro
  autor — verificado contra la API de PyPI el 2026-10-20).
- `pyproject.toml` lleva `name = "thinker-research"`, versión `0.1.13`
  publicada en TestPyPI y PyPI.
- `0.1.3` es una release **solo de documentación**: README durable, guía de
  publicación sin CLI de GitHub ni GitHub Releases y versión actualizada. No
  cambia código.
- `python3 -m build` genera `dist/thinker_research-0.1.3.tar.gz` + wheel;
  `python3 -m twine check dist/thinker_research-0.1.3*` PASA. Los
  artefactos `0.1.0`, `0.1.1` y `0.1.2` se conservan intactos.
- **No subir `dist/*`**: incluye versiones antiguas. Subir solo
  `dist/thinker_research-0.1.13*` (ya existen).
- **Publicación completada de `0.1.3`**: está en TestPyPI y PyPI; el tag
  anotado `v0.1.3` está empujado y los hashes de PyPI coinciden con los
  artefactos generados desde el tag.
- **Publicación completada de `0.1.4`**: TestPyPI y PyPI, con hashes
  coincidentes, tag anotado `v0.1.4` (`858bdf8`) y verificación limpia; ver la
  sección 0.1.4.
- **Publicación completada de `0.1.5`**: TestPyPI y PyPI, con hashes
  coincidentes, tag anotado `v0.1.5` (`6ed121c`) y verificación limpia; ver la
  sección 0.1.5.
- **Publicación completada de `0.1.6`**: TestPyPI y PyPI, con hashes
  coincidentes, tag anotado `v0.1.6` (`4b4216e`) y verificación limpia; ver la
  sección 0.1.6.
- **Publicación completada de `0.1.7`**: TestPyPI y PyPI, con hashes
  coincidentes, tag anotado `v0.1.7` (`4e631ed`) y verificación limpia; ver la
  sección 0.1.7.
- **Publicación completada de `0.1.8`**: TestPyPI y PyPI, con hashes
  coincidentes, tag anotado `v0.1.8` (`18990b0`) y verificación limpia; ver la
  sección 0.1.8.
- **Publicación completada de `0.1.9`**: TestPyPI y PyPI, con hashes
  coincidentes, tag anotado `v0.1.9` (`14e2b7f`) y verificación limpia; ver la
  sección 0.1.9.
- **Pendiente administrativo**: crear el token limitado a
  `thinker-research` y revocar el token global.
- **Sin GitHub Release**: la distribución no la requiere; no se crea ni se
  documenta como tarea pendiente (regla 12).

## Versión 0.1.4 (2026-10-24)

Incluye los 13 commits posteriores a `v0.1.3`: evaluador v2 con perfil,
cobertura, criterios N/A y parsers; modo `--requisitos`; auditor de cambios
y holdout con hashes; CoVe con verificador separado y consenso por muestreo;
portabilidad Windows; y los arreglos del 2026-10-24 (carga de `.env` para
`--sintesis-llm/--investigar` y N/A separado de la evidencia no verificada).

Artefactos: `thinker-research 0.1.4` (wheel y sdist), construidos desde una
copia limpia; `twine check` PASSED. Hashes SHA-256:
`835a5c355322f2b0de2f15e1dc69b4911df6a6177d2dbc4cd66f287d6171d8fe` (wheel)
y `e3014903654316cd0760cdc950588dac8d9a998b1917c172bb0b468beec69422`
(sdist). **Publicada en TestPyPI y PyPI el 2026-10-24**. Verificación:
ambos índices simples publican los artefactos con esos hashes; instalación
limpia `thinker-research==0.1.4` desde TestPyPI y desde PyPI OK;
`evaluate-project --help` incluye `--requisitos`; imports OK y `pip check`
limpio. El endpoint `https://pypi.org/pypi/thinker-research/json` puede
tardar en reflejar la última versión aunque el índice simple y la instalación
ya la sirvan (misma clase de retardo que el Hallazgo 91); el endpoint
`.../0.1.4/json` responde 200. El `README.md` empaquetado se actualizó en un
commit posterior a la publicación, para no alterar los artefactos ya
verificados. Tag anotado `v0.1.4` (commit `858bdf8`) creado y empujado;
`git ls-remote` confirma el tag y su objeto.

## Versión 0.1.13 (2026-10-28)

Paquete `thinker-research 0.1.13` (wheel y sdist). Incluye la re-medición
oficial R3 del evaluador (batch r3c2: **4681/5984**, 1303 brechas, 0 timeouts;
`_verificar_test` 16 → 0 con su test de contrato exacto) y el README
empaquetado al día (la página de 0.1.12 quedó con el texto de 0.1.11, patrón
documentado en la nota de 0.1.4). Sin cambios de código de runtime.

Estado: **publicada en TestPyPI y PyPI el 2026-10-28**. Artefactos
construidos desde el tag `v0.1.13`; `twine check` PASSED. Hashes SHA-256:
`f97e981edecaa719b60eeb6b6737ff9a9a5353a3dce83e90e2eb321945f51594` (wheel) y
`f139ba5f321db39472a146b391b3ae73e2148e2f427ac0c065b19f6b7ce12a65` (sdist).
Verificación: ambos índices publican esos hashes; instalación limpia
`thinker-research==0.1.13` desde TestPyPI y desde PyPI OK;
`evaluate-project --help`, imports OK y `pip check` limpio. El índice simple
tardó ~1-2 min en servir la versión (JSON correcto desde el inicio; mismo
retardo documentado en los Hallazgos 91/104). Tag anotado `v0.1.13` empujado
y verificado con `git ls-remote`.

## Versión 0.1.12 (2026-10-28)

Paquete `thinker-research 0.1.12` (wheel y sdist). Incluye el lock de `openai`
3.37.0 → **3.40.0** (la autoevaluación con red
detectó la deriva en `v4_dependencias_al_dia`; verificado en venv aislado:
suite **1018/1018** y canario 2/2 con 3.40.0), los arreglos de lint
F541/F401 (ruff de vuelta a 0) y `veracidad_layer.py` (commit previo).

Estado: **publicada en TestPyPI y PyPI el 2026-10-28**. Artefactos
construidos desde el tag `v0.1.12`; `twine check` PASSED. Hashes SHA-256:
`f63d6d74a23ba50ef530bb92ceb791287ec473aebe6337201f793a6c4bb1a9cf` (wheel) y
`6ae4b0143dd2ee041713a5dfc70de704328106b67ae78273ab93d6005809c156` (sdist).
Verificación: ambos índices publican esos hashes; instalación limpia
`thinker-research==0.1.12` desde TestPyPI y desde PyPI OK;
`evaluate-project --help`, imports OK y `pip check` limpio. El índice simple
de PyPI tardó ~1 min en servir la versión (JSON correcto desde el inicio;
misma clase de retardo que los Hallazgos 91/104). Tag anotado `v0.1.12`
empujado y verificado con `git ls-remote`.

## Versión 0.1.11 (2026-10-25)

Incluye R13-C (descomposición opt-in de claims compuestos), R4 con 33
casos/14 criterios y 5 trampas, R14-C con piloto real n=20 (Brier 0,0540), el
arreglo de `extras_require` en `setup.py` y 3 tests de casos límite de
manifiestos. R3 sigue parcial: preflight 1015 mutantes, 645 muertos, 370
supervivientes sin triaje. El evaluador se midió después de publicar: 5939
mutantes, 3034 muertos, 2901 supervivientes y 4 timeouts (51,09%), sin triaje.
Suite 891/891, cobertura evaluador 91% y preflight 94%.

Artefactos: `thinker-research 0.1.11` (wheel y sdist), construidos desde el
tag `v0.1.11`; `twine check` PASSED. Hashes SHA-256:
`701091811d6cd3c2cbd352dd98ebdb51b48bb1efd8c8d0cdeba2b571f1fa3e76` (wheel)
y `0fd2a514ae55b45cfe294e644e3cbb9fb2bb18a32452c3ad263094bcbb1d0434`
(sdist). **Publicada en TestPyPI y PyPI el 2026-10-25**. Verificación: ambos
índices publican esos hashes; instalación limpia
`thinker-research==0.1.11` desde PyPI OK; `evaluate-project --help`, imports
OK y `pip check` limpio. Tag anotado `v0.1.11` empujado.

## Versión 0.1.10 (2026-10-25)

Incluye R5-A (comparabilidad y «GLOBAL NO COMPARABLE»), R6-C (marca de
silencio con motivo y warnings), R13-B (verificador barato medido) y R14-B
(Brier offline simulado), más 3 tests de helpers de preflight. R3 sigue
parcial: preflight 1005 mutantes, 557 muertos, 448 supervivientes sin triaje;
el evaluador no se midió. Suite 879/879, docs-check OK.

Artefactos: `thinker-research 0.1.10` (wheel y sdist), `twine check` PASSED.
Hashes SHA-256:
`9571519215f336bd1b1b05e5f7a9f516f64500ebde57f2e16dbd5abdf7d26caa` (wheel)
y `5ab2ef2cf790342b46a14af8f9161c42a3ecb6f0c0d31153dd31713891621f75`
(sdist). **Publicada en TestPyPI y PyPI el 2026-10-25**. Verificación:
ambos índices publican esos hashes; instalación limpia
`thinker-research==0.1.10` desde TestPyPI y PyPI OK; `evaluate-project --help`,
imports OK y `pip check` limpio. Tag anotado `v0.1.10` (`551d693`) empujado.

## Versión 0.1.9 (2026-10-25)

Cierra R2 (cobertura **91%** del evaluador, **91%** de preflight y **91%**
combinado, con ramas de error cubiertas) y R10 (`licencias_no_runtime`
informativo, con ámbito y fuente, fuera del score `h5`). Tests nuevos de
ramas de error y de licencias no runtime. Suite 858/858, ruff 0.

Artefactos: `thinker-research 0.1.9` (wheel y sdist), construidos desde el
tag `v0.1.9`; `twine check` PASSED. Hashes SHA-256:
`88918e4bfa69e316222ff7730964723941e74ae27d75c2ece0486c2dac528270` (wheel)
y `756d838ff11659c3a172a50b354c190edfbe1912747259a903febbcd046f8a81`
(sdist). **Publicada en TestPyPI y PyPI el 2026-10-25**. Verificación:
ambos índices publican esos hashes; instalación limpia
`thinker-research==0.1.9` desde TestPyPI y PyPI OK; `evaluate-project --help`,
imports OK y `pip check` limpio. El índice simple tardó unos segundos en ver
la versión (JSON y hashes ya correctos); se verificó tras la propagación
(Hallazgo 104). Tag anotado `v0.1.9` (`14e2b7f`) empujado y verificado.

## Versión 0.1.8 (2026-10-25)

Amplía la regla 12 (sin `gh` ni GitHub Releases desde el repo), corrige la
cifra de mutación de README a 95,2% (3635/3819; 2026-10-23), actualiza la
cabecera de RECOMENDACIONES y amplía `check_docs` para contrastar la mutación
de README con AGENTS, con test de regresión; retira duplicados de STOPWORDS
(B033). Suite 852/852, cobertura 90% evaluador / 91% preflight.

Artefactos: `thinker-research 0.1.8` (wheel y sdist), construidos desde el
tag `v0.1.8`; `twine check` PASSED. Hashes SHA-256:
`91dd0168fda2d4e8c8d5da0d695ae06cc1a70e15bf0e87465fc1e1a49d9afa02` (wheel)
y `4a4f36a20746e0d03135a9c0e195cb8e521e618b7f345d4f6f7880ee00ae9f6a`
(sdist). **Publicada en TestPyPI y PyPI el 2026-10-25**. Verificación:
ambos índices publican esos hashes; instalación limpia
`thinker-research==0.1.8` desde TestPyPI y PyPI OK; `evaluate-project --help`,
imports OK y `pip check` limpio. El índice simple tardó unos segundos en ver
la versión (JSON y hashes ya correctos); se verificó tras la propagación
(Hallazgo 104). Tag anotado `v0.1.8` (`18990b0`) empujado y verificado.

## Versión 0.1.7 (2026-10-24)

Tres alias reales más: `PIL`→`pillow`, `docx`→`python-docx` y
`pptx`→`python-pptx`, con test de preflight y de h6. Se descartaron
`pygetwindow`, `rapidocr_onnxruntime` y `shiboken6`: con la distribución
declarada directamente ya pasan; `shiboken6` con solo `PySide6` es una
dependencia transitiva y el flag es correcto. Incluye la regla 13 (no
manipular la evaluación) en `AGENTS.md`. Suite **851/851**, cobertura 90%
evaluador / 91% preflight.

Artefactos: `thinker-research 0.1.7` (wheel y sdist), construidos desde el
tag `v0.1.7`; `twine check` PASSED. Hashes SHA-256:
`d06e95a9c6df3335fc0705b81ee07b42a1b8633b144751f5159da15fe92a4e5f` (wheel)
y `614b42c5bcff5f6c0d1cab1e2063a4a2b13753609dd4892cfea50e2d9a105899`
(sdist). **Publicada en TestPyPI y PyPI el 2026-10-24**. Verificación:
ambos índices simples publican esos hashes; instalación limpia
`thinker-research==0.1.7` desde TestPyPI y PyPI OK; `--ignorar` presente,
imports OK y `pip check` limpio. Tag anotado `v0.1.7` (`4e631ed`)
empujado y verificado.

## Versión 0.1.6 (2026-10-24)

Mejoras rápidas de usabilidad y precisión:
`--ignorar DIRECTORIO` repetible en las CLI de evaluador y preflight (permite
excluir `exe/` u otros directorios sin snapshot) e imports hermanos locales
(`tools/a.py` puede importar `tools/helper.py` sin manifiesto). `dist/` ya
estaba excluido; `exe/` no se ignora por defecto. Tres tests nuevos; suite
**849/849**, cobertura 90% evaluador / 91% preflight.

Artefactos: `thinker-research 0.1.6` (wheel y sdist), construidos desde el
tag `v0.1.6`; `twine check` PASSED. Hashes SHA-256:
`4ed2ef35251d570dbc36d0ab0dd83817cac3ef1f2546b79a2a6b5e99ea5e3bc2` (wheel)
y `189d57a7dee4c7d2d5ad6b100973a7c0893362b9f7cea10323b1831fe0b4f04c`
(sdist). **Publicada en TestPyPI y PyPI el 2026-10-24**. Verificación:
ambos índices simples publican esos hashes; instalación limpia
`thinker-research==0.1.6` desde TestPyPI y PyPI OK; `--ignorar` presente,
imports OK y `pip check` limpio. El índice simple mostró 0.1.6 antes que
pip; tras unos segundos de propagación la instalación quedó verificada
(misma clase de retardo que el Hallazgo 91).

## Versión 0.1.5 (2026-10-24)

Corrige dos falsos positivos y un coste de exploración del evaluador:
alias de `win32api`/`win32con`/`win32gui`/`win32com`/`pythoncom`/`pywintypes`
a `pywin32` (antes `import win32api` se marcaba como no declarado aunque
`pywin32` estuviera en el manifiesto) y exclusiones por prefijo/sufijo para
`.venv-*`, `venv-*`, `pytest-of-*` y `*.egg-info` en evaluador y preflight.
`dist/` ya estaba excluido; `exe/` no se ignora a propósito. Cuatro tests
nuevos; suite **846/846**, cobertura 90% evaluador / 91% preflight.

Artefactos: `thinker-research 0.1.5` (wheel y sdist), construidos desde el
tag `v0.1.5`; `twine check` PASSED. Hashes SHA-256:
`4c3fa7e76f73fc12425dc733cdd413f1072c700fedb79fe65997ccb8c1fbf3e3` (wheel)
y `2e75a2ccc1e8cdf6ac033dac2e55a566ac60910416bcf564fc462618b1892389`
(sdist). **Publicada en TestPyPI y PyPI el 2026-10-24**. Verificación:
ambos índices simples publican esos hashes; instalación limpia
`thinker-research==0.1.5` desde TestPyPI y PyPI OK; `--requisitos`
presente, imports OK y `pip check` limpio. El índice simple mostró 0.1.5
antes que pip; tras unos segundos de propagación la instalación quedó
verificada (misma clase de retardo que el Hallazgo 91).

## Versión 0.1.3 (2026-10-21)

Publicada en TestPyPI y PyPI; sustituye a `0.1.2`, que no se publicó. Corrige
el README empaquetado, que en `0.1.2` decía «La publicación en
PyPI sigue pendiente»: PyPI usa el README como descripción del proyecto, así
que esa frase habría contradicho la ficha recién publicada (Hallazgo 90). La
nueva formulación distingue la instalación por tag (siempre disponible) de la
instalación por PyPI y no afirma un estado transitorio.

Verificación local (2026-10-21): suite **706/706**, ruff 0, preflight 0,
build + `twine check` **PASSED** (wheel y sdist), METADATA `Name:
thinker-research` / `Version: 0.1.3` y sin la frase «PyPI pendiente»; wheel
instalado en un venv temporal, imports OK y `evaluate-project --help` OK.
Publicación: PyPI JSON 200 con `0.1.3`, wheel y sdist con los mismos hashes
que `dist/`; TestPyPI instalable; instalación limpia desde PyPI con imports
OK y `pip check` sin conflictos. El primer `pip install` con la configuración
por defecto no vio la versión; con el índice oficial
(`https://pypi.org/simple/`) y `--no-cache-dir` sí (Hallazgo 91).

## Versión 0.1.2 (2026-10-21) — no publicada

Incluye el arreglo de `_max_nesting` (`elif` no suma nivel; `try/except*` y
`match` cuentan como bloques), 3 tests nuevos, la puesta al día de cifras y
la corrección del estado posterior al tag de `0.1.1` (Hallazgo 89).
Verificación local: suite 706/706 en 3.11 y 3.12 (3.12.3, venv aislado
creado desde el lock, openai 3.35.1), ruff 0, preflight 0, cobertura 100%
en los 6 módulos mutados, mutación 94,7% (3581/3780; 199 supervivientes, 0
timeouts), build desde el tag `v0.1.2` + `twine check` PASSED, wheel
instalado y probado desde otro directorio. El tag `v0.1.2` está empujado,
pero **no se publicó en PyPI**: el README empaquetado conservaba la frase
«PyPI pendiente» y la ficha habría sido contradictoria. `0.1.3` lo corrige.

## Reglas de seguridad del token (P0.6)

1. El token **nunca** se pega en chats, ni en `.env`, ni en comandos cuya
   salida se registre (quedaría en logs).
2. Vive SOLO en `~/.pypirc` con `chmod 600` (o en el gestor de claves del
   sistema vía `keyring`).
3. Primer token: alcance «Entire account» (el proyecto no existe aún).
   **Tras la primera subida**: crear un token con alcance solo a
   `thinker-research`, actualizar `~/.pypirc` y revocar el global.
4. PyPI exige 2FA en la cuenta para poder subir.

## Preparación (una vez)

```ini
# ~/.pypirc  (permisos: chmod 600)
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-TOKEN_REAL

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-TOKEN_TESTPYPI
```

Tokens en https://pypi.org/manage/account/token/ y
https://test.pypi.org/manage/account/token/.

## Checklist pre-publicación (cada release)

- [ ] Versión incrementada en `pyproject.toml` (`[project] version`).
- [ ] Batería en verde: `ruff check .`, `python3 scripts/preflight.py`,
  `python3 -m unittest discover -s tests`, `make ci`.
- [ ] **Artefactos de build limpios** (Hallazgo 83: setuptools no limpia
  `build/` entre compilaciones y puede empaquetar paquetes retirados):
  construir desde una copia limpia del tag o apartar `build/` y
  `*.egg-info/`; no borrar `dist/`, que conserva las versiones anteriores.
- [ ] `python3 -m build` y
  `python3 -m twine check dist/thinker_research-0.1.13*` en verde.
- [ ] Revisar el METADATA del wheel: `Name: thinker-research`,
  `Version: 0.1.9` y sin frases transitorias sobre PyPI o el tag.
- [ ] `git status` limpio, tag anotado y `git ls-remote` confirma el tag en
  el remoto.

## Ensayo en TestPyPI (recomendado siempre)

```bash
python3 -m twine upload -r testpypi dist/thinker_research-0.1.13*
# Verificar instalación desde TestPyPI en un venv limpio:
python3 -m venv /tmp/venv-testpypi-019
/tmp/venv-testpypi-019/bin/pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  thinker-research==0.1.13
/tmp/venv-testpypi-019/bin/evaluate-project --help
```

(`--extra-index-url` es necesario: las dependencias están en PyPI real, no
en TestPyPI. No usar `dist/*`: subiría también `0.1.0`–`0.1.9`.)

## Publicación real

```bash
python3 -m twine upload dist/thinker_research-0.1.13*
```

Verificación post-publicación (obligatoria, P0.1):

```bash
curl -s https://pypi.org/pypi/thinker-research/0.1.13/json | python3 -c \
  "import json,sys; print(json.load(sys.stdin)['info']['version'])"
python3 -m venv /tmp/venv-pypi-019
/tmp/venv-pypi-019/bin/pip install --index-url https://pypi.org/simple/ \
  --no-cache-dir thinker-research==0.1.13
cd /tmp && /tmp/venv-pypi-019/bin/evaluate-project --help
```

Si pip no ve la versión pero el JSON y el índice simple sí, contrasta los
hashes y prueba el índice oficial con `--no-cache-dir` antes de concluir que
la subida falló (Hallazgo 91).

## Tareas tras publicar

Estado de `0.1.9`: publicación en TestPyPI y PyPI, hashes, tag anotado y
documentación hechos. Queda una tarea administrativa:

1. Token scoped al proyecto + revocar el global (ver reglas arriba).

No hay tarea de GitHub Release: la distribución se hace con PyPI/TestPyPI y
tags de git, y no se depende de la CLI ni de una cuenta de GitHub (regla 12).

Para la próxima release: actualizar el estado en
`README.md`/`docs/PUBLICACION.md` solo después de verificar la versión en
PyPI; no prometas disponibilidad antes de comprobarla (P0.1).

## Vía sin keys: distribución por tag de git (OPERATIVA)

Tags de referencia: `v0.1.0` (commit `e0f46b6`), `v0.1.1` (`a56e0b8`),
`v0.1.2` (anotado), `v0.1.3` (anotado), `v0.1.4` (anotado), `v0.1.5`
(anotado), `v0.1.6` (anotado), `v0.1.7` (anotado), `v0.1.8` (anotado) y
`v0.1.9` (anotado). `0.1.9` está publicada en PyPI y también puede instalarse
por git; verifica que su tag esté en el remoto e instala:

```bash
git ls-remote --tags origin v0.1.9   # debe aparecer antes de instalar
pip install git+https://github.com/jmbigi/thinker.git@v0.1.9
```

- `v0.1.0` verificado end-to-end el 2026-10-21: venv limpio +
  `pip install git+...@v0.1.0` → dist `thinker-research 0.1.0`, imports de
  librería OK y `evaluate-project` funcional desde otro directorio.
- `v0.1.1` verificado el 2026-10-21: instalación desde el tag, imports OK,
  `evaluate-project` OK y `max_nesting` de `elif` = 1.
- `v0.1.2` verificado localmente desde el tag antes de empujarlo; el remoto
  se comprueba con `git ls-remote` antes de anunciar la instalación.
- `v0.1.4` verificado el 2026-10-24: tag anotado empujado (`858bdf8`) e
  instalación limpia desde PyPI y TestPyPI; `--requisitos` presente, imports
  OK y `pip check` limpio.
- `v0.1.5` verificado el 2026-10-24: tag anotado empujado (`6ed121c`) e
  instalación limpia desde PyPI y TestPyPI; alias/exclusiones incluidas,
  `--requisitos` presente, imports OK y `pip check` limpio.
- `v0.1.6` verificado el 2026-10-24: tag anotado empujado, instalación limpia
  desde PyPI y TestPyPI; `--ignorar` e imports hermanos incluidos, imports OK
  y `pip check` limpio.
- `v0.1.7` verificado el 2026-10-24: tag anotado empujado, instalación limpia
  desde PyPI y TestPyPI; alias PIL/docx/pptx incluidos, imports OK y
  `pip check` limpio.
- `v0.1.8` verificado el 2026-10-25: tag anotado empujado (`18990b0`),
  instalación limpia desde PyPI y TestPyPI; imports OK y `pip check` limpio.
- `v0.1.9` verificado el 2026-10-25: tag anotado empujado (`14e2b7f`),
  instalación limpia desde PyPI y TestPyPI; imports OK y `pip check` limpio.
- **Sin GitHub Release**: la distribución se hace con los artefactos de
  PyPI/TestPyPI y los tags de git; no se crean releases desde el repositorio
  ni se depende de la CLI o de una cuenta de GitHub (regla propia 12). En
  `dist/` están los artefactos de `v0.1.0`, `v0.1.1`, `0.1.2`, `0.1.3`,
  `0.1.4`, `0.1.5`, `0.1.6`, `0.1.7`, `0.1.8` y `0.1.9`.

## Notas

- El nombre de distribución (`thinker-research`) y los de importación
  (`evaluar_proyecto`, `deep_research_system`, ...) son independientes: el
  renombrado no afecta al código ni a los usuarios de la librería.
- `dist/` está en `.gitignore`: los artefactos no se versionan.
- Versiones: una versión ya subida a PyPI **no se puede reemplazar**; un
  error exige subir la siguiente versión (o `yank` como último recurso).
- `0.1.3` no cambia código; si aparece un cambio funcional, corresponde a
  otra versión.
