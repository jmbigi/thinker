# Publicación en PyPI — `thinker-research`

> Guía durable para publicar y mantener el paquete en PyPI.
> Estado al 2026-10-21: **versión `0.1.2` preparada**; PyPI y GitHub
> Release pendientes de credenciales/permisos. Tags `v0.1.0` y `v0.1.1`
> ya empujados; `v0.1.2` es un tag anotado (verifica el remoto antes de
> instalar). Detalle del renombrado en `LECCIONES-APRENDIDAS.md`
> (Hallazgo 85); incidencia de release en el Hallazgo 89.

## Estado actual

- Nombre: **`thinker-research`** (`thinker` está ocupado desde 2017 por otro
  autor — verificado contra la API de PyPI el 2026-10-20).
- `pyproject.toml` lleva `name = "thinker-research"`, versión `0.1.2`.
- `python3 -m build` genera `dist/thinker_research-0.1.2.tar.gz` + wheel;
  `python3 -m twine check dist/*` PASA. Los artefactos `0.1.0` y `0.1.1`
  se conservan intactos.
- Wheel `0.1.2` verificado end-to-end: instalación en venv aislado, imports
  de librería, `evaluate-project` desde otro directorio y `max_nesting`
  correcto (`if/elif/elif` = 1).
- **Bloqueo**: la subida requiere el token de PyPI del programador; la
  GitHub Release requiere permisos de escritura. `0.1.2` no se ha subido a
  PyPI. La distribución por git usa el tag anotado `v0.1.2`; verifica que
  esté empujado.

## Versión 0.1.2 (2026-10-21)

Incluye el arreglo de `_max_nesting` (`elif` no suma nivel; `try/except*` y
`match` cuentan como bloques), 3 tests nuevos, la puesta al día de cifras y
la corrección del estado posterior al tag de `0.1.1` (Hallazgo 89).
Verificación local: suite 706/706 en 3.11 y 3.12 (3.12.3, venv aislado
creado desde el lock, openai 3.35.1), ruff 0, preflight 0, cobertura 100%
en los 6 módulos mutados, mutación 94,7% (3581/3780; 199 supervivientes, 0
timeouts), build desde el tag `v0.1.2` + `twine check` PASSED, wheel
instalado y probado desde otro directorio. `0.1.1` quedó etiquetado y
empujado, pero no se publicó en PyPI; `0.1.2` es la versión destinada a
PyPI. **Publicación pendiente** del token; antes de instalar desde el
remoto, verifica que el tag `v0.1.2` esté empujado.

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
  apartar `build/`, `dist/` y `*.egg-info/` antes de construir.
- [ ] `python3 -m build` y `python3 -m twine check dist/*` en verde.

## Ensayo en TestPyPI (recomendado siempre)

```bash
python3 -m twine upload -r testpypi dist/*
# Verificar instalación desde TestPyPI en un venv limpio:
python3 -m venv /tmp/venv-testpypi
/tmp/venv-testpypi/bin/pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  thinker-research
/tmp/venv-testpypi/bin/evaluate-project --help
```

(`--extra-index-url` es necesario: las dependencias están en PyPI real, no
en TestPyPI.)

## Publicación real

```bash
python3 -m twine upload dist/*
```

Verificación post-publicación (obligatoria, P0.1):

```bash
curl -s https://pypi.org/pypi/thinker-research/json | python3 -c \
  "import json,sys; print(json.load(sys.stdin)['info']['version'])"
python3 -m venv /tmp/venv-pypi && /tmp/venv-pypi/bin/pip install thinker-research
cd /tmp && /tmp/venv-pypi/bin/evaluate-project --help
```

## Tareas tras publicar

1. README: añadir `pip install thinker-research` como vía de instalación
   (NO antes: prometer un paquete no publicado viola P0.1).
2. Token scoped al proyecto + revocar el global (ver reglas arriba).
3. Tag anotado con la versión de `pyproject.toml` (para `0.1.2`:
   `git tag -a v0.1.2 -m "Release 0.1.2"` si aún no existe; empújalo con
   `git push origin v0.1.2`, con orden del programador, P0.7).
4. Entrada en `docs/EVALUACIONES.md` y hallazgo en
   `docs/LECCIONES-APRENDIDAS.md` si el proceso enseña algo nuevo (P1.20).

## Vía sin keys: distribución por tag de git (OPERATIVA)

Tags de referencia: `v0.1.0` (commit `e0f46b6`), `v0.1.1` (`a56e0b8`) y
`v0.1.2` (anotado). Para usar `0.1.2` por git, verifica que su tag esté en
el remoto y instala:

```bash
git ls-remote --tags origin v0.1.2   # debe aparecer antes de instalar
pip install git+https://github.com/jmbigi/thinker.git@v0.1.2
```

- `v0.1.0` verificado end-to-end el 2026-10-21: venv limpio +
  `pip install git+...@v0.1.0` → dist `thinker-research 0.1.0`, imports de
  librería OK y `evaluate-project` funcional desde otro directorio.
- `v0.1.1` verificado el 2026-10-21: instalación desde el tag, imports OK,
  `evaluate-project` OK y `max_nesting` de `elif` = 1.
- `v0.1.2` verificado localmente desde el tag antes de empujarlo; el remoto
  se comprueba con `git ls-remote` antes de anunciar la instalación.
- **GitHub Release con artefactos (wheel/sdist): BLOQUEADA** — la cuenta
  autenticada en `gh` tiene solo lectura en `jmbigi/thinker` (`push: false`,
  verificado vía API el 2026-10-21); el push por SSH usa otra identidad.
  Comprueba la identidad con `gh auth status`. Para crearla: `gh auth login`
  con una cuenta con escritura en el repo y
  `gh release create v0.1.2 dist/*0.1.2* --repo jmbigi/thinker` (el tag
  debe estar empujado). En `dist/` están los artefactos de `v0.1.0`,
  `v0.1.1` y `0.1.2`.

## Notas

- El nombre de distribución (`thinker-research`) y los de importación
  (`evaluar_proyecto`, `deep_research_system`, ...) son independientes: el
  renombrado no afecta al código ni a los usuarios de la librería.
- `dist/` está en `.gitignore`: los artefactos no se versionan.
- Versiones: una versión ya subida a PyPI **no se puede reemplazar**; un
  error exige subir la siguiente versión (o `yank` como último recurso).
