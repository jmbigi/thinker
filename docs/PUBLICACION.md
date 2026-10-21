# Publicación en PyPI — `thinker-research`

> Guía durable para publicar y mantener el paquete en PyPI.
> Estado al 2026-10-21: **versión `0.1.3` preparada**; PyPI pendiente del
> token. Tags `v0.1.0`, `v0.1.1` y `v0.1.2` ya empujados; `v0.1.2` es un tag
> anotado. `0.1.2` **no se publicó**: su README decía que PyPI estaba
> pendiente y la ficha se habría contradicho; `0.1.3` corrige el texto con
> una formulación durable. No se usa la CLI de GitHub (regla propia 12):
> las GitHub Releases se crean desde la web. Detalle del renombrado en
> `LECCIONES-APRENDIDAS.md` (Hallazgo 85); incidencias de release en los
> Hallazgos 89 y 90.

## Estado actual

- Nombre: **`thinker-research`** (`thinker` está ocupado desde 2017 por otro
  autor — verificado contra la API de PyPI el 2026-10-20).
- `pyproject.toml` lleva `name = "thinker-research"`, versión `0.1.3`.
- `0.1.3` es una release **solo de documentación**: README durable, guía de
  publicación sin CLI de GitHub y versión actualizada. No cambia código.
- `python3 -m build` genera `dist/thinker_research-0.1.3.tar.gz` + wheel;
  `python3 -m twine check dist/thinker_research-0.1.3*` PASA. Los
  artefactos `0.1.0`, `0.1.1` y `0.1.2` se conservan intactos.
- **No subir `dist/*`**: incluye versiones antiguas. Subir solo
  `dist/thinker_research-0.1.3*`.
- **Bloqueo**: la subida requiere el token de PyPI del programador; la
  GitHub Release requiere permisos de escritura en el repositorio. `0.1.3`
  no se ha subido a PyPI. La distribución por git usará el tag anotado
  `v0.1.3`, que se crea al cerrar esta release; verifica que esté empujado
  antes de anunciarlo.

## Versión 0.1.3 (2026-10-21)

Sustituye a `0.1.2` como versión destinada a PyPI. Corrige el README
empaquetado, que en `0.1.2` decía «La publicación en PyPI sigue pendiente»:
PyPI usa el README como descripción del proyecto, así que esa frase habría
contradicho la ficha recién publicada (Hallazgo 90). La nueva formulación
distingue la instalación por tag (siempre disponible) de la instalación por
PyPI («cuando la versión esté publicada») y no afirma un estado transitorio.

Verificación local del árbol de trabajo (2026-10-21): suite **706/706**,
ruff 0, preflight 0, build + `twine check` **PASSED** (wheel y sdist),
METADATA `Name: thinker-research` / `Version: 0.1.3` y sin la frase
«PyPI pendiente»; wheel instalado en un venv temporal, imports OK y
`evaluate-project --help` OK. Los artefactos finales se reconstruyen desde
el tag `v0.1.3` antes de subir.

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
  `python3 -m twine check dist/thinker_research-0.1.3*` en verde.
- [ ] Revisar el METADATA del wheel: `Name: thinker-research`,
  `Version: 0.1.3` y sin frases transitorias sobre PyPI o el tag.
- [ ] `git status` limpio, tag anotado y `git ls-remote` confirma el tag en
  el remoto.

## Ensayo en TestPyPI (recomendado siempre)

```bash
python3 -m twine upload -r testpypi dist/thinker_research-0.1.3*
# Verificar instalación desde TestPyPI en un venv limpio:
python3 -m venv /tmp/venv-testpypi-013
/tmp/venv-testpypi-013/bin/pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  thinker-research==0.1.3
/tmp/venv-testpypi-013/bin/evaluate-project --help
```

(`--extra-index-url` es necesario: las dependencias están en PyPI real, no
en TestPyPI. No usar `dist/*`: subiría también `0.1.0`–`0.1.2`.)

## Publicación real

```bash
python3 -m twine upload dist/thinker_research-0.1.3*
```

Verificación post-publicación (obligatoria, P0.1):

```bash
curl -s https://pypi.org/pypi/thinker-research/json | python3 -c \
  "import json,sys; print(json.load(sys.stdin)['info']['version'])"
python3 -m venv /tmp/venv-pypi-013
/tmp/venv-pypi-013/bin/pip install thinker-research==0.1.3
cd /tmp && /tmp/venv-pypi-013/bin/evaluate-project --help
```

## Tareas tras publicar

1. Actualizar el estado en `README.md`/`docs/PUBLICACION.md` solo después de
   verificar la versión en PyPI. El README ya usa una frase condicional
   durable; no prometas disponibilidad antes de comprobarla (P0.1).
2. Token scoped al proyecto + revocar el global (ver reglas arriba).
3. Tag anotado con la versión de `pyproject.toml` (para `0.1.3`:
   `git tag -a v0.1.3 -m "Release 0.1.3"` si aún no existe; empújalo con
   `git push origin v0.1.3`, con orden del programador, P0.7).
4. Entrada en `docs/EVALUACIONES.md` y hallazgo en
   `docs/LECCIONES-APRENDIDAS.md` si el proceso enseña algo nuevo (P1.20).

## Vía sin keys: distribución por tag de git (OPERATIVA)

Tags de referencia: `v0.1.0` (commit `e0f46b6`), `v0.1.1` (`a56e0b8`) y
`v0.1.2` (anotado). `0.1.3` es la versión preparada para PyPI; para usarla
por git, verifica que su tag esté en el remoto y instala:

```bash
git ls-remote --tags origin v0.1.3   # debe aparecer antes de instalar
pip install git+https://github.com/jmbigi/thinker.git@v0.1.3
```

- `v0.1.0` verificado end-to-end el 2026-10-21: venv limpio +
  `pip install git+...@v0.1.0` → dist `thinker-research 0.1.0`, imports de
  librería OK y `evaluate-project` funcional desde otro directorio.
- `v0.1.1` verificado el 2026-10-21: instalación desde el tag, imports OK,
  `evaluate-project` OK y `max_nesting` de `elif` = 1.
- `v0.1.2` verificado localmente desde el tag antes de empujarlo; el remoto
  se comprueba con `git ls-remote` antes de anunciar la instalación.
- **GitHub Release con artefactos (wheel/sdist)**: se crea desde la web del
  repositorio (*Releases → Draft a new release*), eligiendo el tag y
  adjuntando `dist/thinker_research-0.1.3*`. No se usa la CLI de GitHub
  (regla propia 12). La cuenta debe tener permisos de escritura; si no, la
  release no se puede crear. En `dist/` están los artefactos de `v0.1.0`,
  `v0.1.1`, `0.1.2` y `0.1.3`.

## Notas

- El nombre de distribución (`thinker-research`) y los de importación
  (`evaluar_proyecto`, `deep_research_system`, ...) son independientes: el
  renombrado no afecta al código ni a los usuarios de la librería.
- `dist/` está en `.gitignore`: los artefactos no se versionan.
- Versiones: una versión ya subida a PyPI **no se puede reemplazar**; un
  error exige subir la siguiente versión (o `yank` como último recurso).
- `0.1.3` no cambia código; si aparece un cambio funcional, corresponde a
  otra versión.
