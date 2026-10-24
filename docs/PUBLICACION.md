# Publicación en PyPI — `thinker-research`

> Guía durable para publicar y mantener el paquete en PyPI.
> Estado al 2026-10-24: **versión `0.1.5` publicada en TestPyPI y PyPI**.
> Tags `v0.1.0`, `v0.1.1`, `v0.1.2`, `v0.1.3`, `v0.1.4` y `v0.1.5`
> empujados; `v0.1.2`, `v0.1.3`, `v0.1.4` y `v0.1.5` son anotados. `0.1.2` **no
> se publicó**: su README decía que PyPI estaba pendiente y la ficha se habría
> contradicho; `0.1.3` corrige el texto con una formulación durable. No se usa
> la CLI de GitHub (regla propia 12): las GitHub Releases se crean desde la
> web. Detalle del renombrado en `LECCIONES-APRENDIDAS.md` (Hallazgo 85);
> incidencias de release en los Hallazgos 89, 90 y 91.

## Estado actual

- Nombre: **`thinker-research`** (`thinker` está ocupado desde 2017 por otro
  autor — verificado contra la API de PyPI el 2026-10-20).
- `pyproject.toml` lleva `name = "thinker-research"`, versión `0.1.5`
  publicada en TestPyPI y PyPI.
- `0.1.3` es una release **solo de documentación**: README durable, guía de
  publicación sin CLI de GitHub y versión actualizada. No cambia código.
- `python3 -m build` genera `dist/thinker_research-0.1.3.tar.gz` + wheel;
  `python3 -m twine check dist/thinker_research-0.1.3*` PASA. Los
  artefactos `0.1.0`, `0.1.1` y `0.1.2` se conservan intactos.
- **No subir `dist/*`**: incluye versiones antiguas. Subir solo
  `dist/thinker_research-0.1.5*` (ya existen).
- **Publicación completada de `0.1.3`**: está en TestPyPI y PyPI; el tag
  anotado `v0.1.3` está empujado y los hashes de PyPI coinciden con los
  artefactos generados desde el tag.
- **Publicación completada de `0.1.4`**: TestPyPI y PyPI, con hashes
  coincidentes, tag anotado `v0.1.4` (`858bdf8`) y verificación limpia; ver la
  sección 0.1.4.
- **Publicación completada de `0.1.5`**: TestPyPI y PyPI, con hashes
  coincidentes, tag anotado `v0.1.5` (`6ed121c`) y verificación limpia; ver la
  sección 0.1.5.
- **Pendiente administrativo**: crear el token limitado a
  `thinker-research` y revocar el token global; la GitHub Release, si se
  quiere, se crea desde la web.

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
  `python3 -m twine check dist/thinker_research-0.1.5*` en verde.
- [ ] Revisar el METADATA del wheel: `Name: thinker-research`,
  `Version: 0.1.5` y sin frases transitorias sobre PyPI o el tag.
- [ ] `git status` limpio, tag anotado y `git ls-remote` confirma el tag en
  el remoto.

## Ensayo en TestPyPI (recomendado siempre)

```bash
python3 -m twine upload -r testpypi dist/thinker_research-0.1.5*
# Verificar instalación desde TestPyPI en un venv limpio:
python3 -m venv /tmp/venv-testpypi-014
/tmp/venv-testpypi-014/bin/pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  thinker-research==0.1.5
/tmp/venv-testpypi-014/bin/evaluate-project --help
```

(`--extra-index-url` es necesario: las dependencias están en PyPI real, no
en TestPyPI. No usar `dist/*`: subiría también `0.1.0`–`0.1.5`.)

## Publicación real

```bash
python3 -m twine upload dist/thinker_research-0.1.5*
```

Verificación post-publicación (obligatoria, P0.1):

```bash
curl -s https://pypi.org/pypi/thinker-research/0.1.5/json | python3 -c \
  "import json,sys; print(json.load(sys.stdin)['info']['version'])"
python3 -m venv /tmp/venv-pypi-014
/tmp/venv-pypi-014/bin/pip install --index-url https://pypi.org/simple/ \
  --no-cache-dir thinker-research==0.1.5
cd /tmp && /tmp/venv-pypi-014/bin/evaluate-project --help
```

Si pip no ve la versión pero el JSON y el índice simple sí, contrasta los
hashes y prueba el índice oficial con `--no-cache-dir` antes de concluir que
la subida falló (Hallazgo 91).

## Tareas tras publicar

Estado de `0.1.5`: publicación en TestPyPI y PyPI, hashes, tag anotado y
documentación hechos. Quedan dos tareas administrativas:

1. Token scoped al proyecto + revocar el global (ver reglas arriba).
2. GitHub Release `v0.1.5`: el tag ya está empujado, pero la Release con
   wheel/sdist sigue **pendiente de crear desde la web**; la API de GitHub no
   muestra ninguna release para `v0.1.5` (verificado el 2026-10-24).

Para la próxima release: actualizar el estado en
`README.md`/`docs/PUBLICACION.md` solo después de verificar la versión en
PyPI; no prometas disponibilidad antes de comprobarla (P0.1).

## Vía sin keys: distribución por tag de git (OPERATIVA)

Tags de referencia: `v0.1.0` (commit `e0f46b6`), `v0.1.1` (`a56e0b8`),
`v0.1.2` (anotado), `v0.1.3` (anotado), `v0.1.4` (anotado) y `v0.1.5`
(anotado). `0.1.5` está publicada en PyPI y también puede instalarse por git;
verifica que su tag esté en el remoto e instala:

```bash
git ls-remote --tags origin v0.1.5   # debe aparecer antes de instalar
pip install git+https://github.com/jmbigi/thinker.git@v0.1.5
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
- **GitHub Release con artefactos (wheel/sdist)**: se crea desde la web del
  repositorio (*Releases → Draft a new release*), eligiendo el tag y
  adjuntando `dist/thinker_research-0.1.5*`. No se usa la CLI de GitHub
  (regla propia 12). La cuenta debe tener permisos de escritura; si no, la
  release no se puede crear. En `dist/` están los artefactos de `v0.1.0`,
  `v0.1.1`, `0.1.2`, `0.1.3`, `0.1.4` y `0.1.5`.

## Notas

- El nombre de distribución (`thinker-research`) y los de importación
  (`evaluar_proyecto`, `deep_research_system`, ...) son independientes: el
  renombrado no afecta al código ni a los usuarios de la librería.
- `dist/` está en `.gitignore`: los artefactos no se versionan.
- Versiones: una versión ya subida a PyPI **no se puede reemplazar**; un
  error exige subir la siguiente versión (o `yank` como último recurso).
- `0.1.3` no cambia código; si aparece un cambio funcional, corresponde a
  otra versión.
