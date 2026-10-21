# Publicación en PyPI — `thinker-research`

> Guía durable para publicar y mantener el paquete en PyPI.
> Estado al 2026-10-21: **versión `0.1.1` preparada localmente, publicación
> pendiente de credenciales y de commit/tag** (ver «Estado actual»). Detalle
> del renombrado en `LECCIONES-APRENDIDAS.md` (Hallazgo 85).

## Estado actual

- Nombre: **`thinker-research`** (`thinker` está ocupado desde 2017 por otro
  autor — verificado contra la API de PyPI el 2026-10-20).
- `pyproject.toml` lleva `name = "thinker-research"`, versión `0.1.1`
  (en preparación; la última etiquetada es `0.1.0`).
- `python3 -m build` genera `dist/thinker_research-0.1.1.tar.gz` + wheel;
  `python3 -m twine check dist/*` PASA. Los artefactos `0.1.0` del tag
  `v0.1.0` se conservan intactos.
- Wheel `0.1.1` verificado end-to-end: instalación en venv aislado, imports
  de librería, `evaluate-project` desde otro directorio y `max_nesting`
  correcto (`if/elif/elif` = 1).
- **Bloqueo**: la subida requiere el token de PyPI del programador y, antes,
  el tag de la versión `0.1.1` (el commit se prepara en esta revisión; P0.7).

## Versión 0.1.1 (en preparación, 2026-10-21)

Incluye el arreglo de `_max_nesting` (`elif` no suma nivel; `try/except*` y
`match` cuentan como bloques), 3 tests nuevos y la puesta al día de cifras.
Verificación local: suite 706/706 en 3.11 y 3.12, ruff 0, preflight 0,
cobertura 100% en los 6 módulos mutados, mutación 94,7% (3581/3780; 199
supervivientes, 0 timeouts), build + `twine check` PASSED, wheel instalado y
probado desde otro directorio. **Pendiente**: tag `v0.1.1` y subida (el
commit se prepara en esta revisión; todo con orden explícita, P0.7). No se
ha publicado nada.

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
3. Tag de git con la versión de `pyproject.toml` (p. ej.
   `git tag v0.1.1 && git push --tags`; con orden del programador, P0.7).
4. Entrada en `docs/EVALUACIONES.md` y hallazgo en
   `docs/LECCIONES-APRENDIDAS.md` si el proceso enseña algo nuevo (P1.20).

## Vía sin keys: distribución por tag de git (YA OPERATIVA)

Mientras no haya token de PyPI, el paquete se distribuye por el remoto:

```bash
pip install git+https://github.com/jmbigi/thinker.git@v0.1.0   # tag fijado
```

- Tag `v0.1.0` creado y empujado el 2026-10-21 (commit `e0f46b6`).
- Verificado end-to-end el 2026-10-21: venv limpio +
  `pip install git+...@v0.1.0` → dist `thinker-research 0.1.0`, imports de
  librería OK y `evaluate-project` funcional desde otro directorio.
- **GitHub Release con artefactos (wheel/sdist): BLOQUEADA** — la cuenta
  autenticada en `gh` tiene solo lectura en `jmbigi/thinker` (`push: false`,
  verificado vía API el 2026-10-21); el push por SSH usa otra identidad.
  Comprueba la identidad con `gh auth status`. Para crearla: `gh auth login`
  con una cuenta con escritura en el repo y
  `gh release create v0.1.1 dist/*0.1.1* --repo jmbigi/thinker`. En `dist/`
  están los artefactos de `v0.1.0` y los de `0.1.1` preparados localmente; el
  tag `v0.1.1` aún no existe.

## Notas

- El nombre de distribución (`thinker-research`) y los de importación
  (`evaluar_proyecto`, `deep_research_system`, ...) son independientes: el
  renombrado no afecta al código ni a los usuarios de la librería.
- `dist/` está en `.gitignore`: los artefactos no se versionan.
- Versiones: una versión ya subida a PyPI **no se puede reemplazar**; un
  error exige subir la siguiente versión (o `yank` como último recurso).
