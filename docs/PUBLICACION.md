# Publicación en PyPI — `thinker-research`

> Guía durable para publicar y mantener el paquete en PyPI.
> Estado al 2026-10-21: **paquete listo, publicación pendiente de credenciales**
> (ver «Estado actual»). Detalle del renombrado en `LECCIONES-APRENDIDAS.md`
> (Hallazgo 85).

## Estado actual

- Nombre: **`thinker-research`** (`thinker` está ocupado desde 2017 por otro
  autor — verificado contra la API de PyPI el 2026-10-20).
- `pyproject.toml` ya lleva `name = "thinker-research"`, versión `0.1.0`.
- `python3 -m build` genera `dist/thinker_research-0.1.0.tar.gz` + wheel;
  `python3 -m twine check dist/*` PASA.
- Wheel verificado end-to-end: instalación en venv limpio, imports de
  librería y `evaluate-project` desde otro directorio.
- **Bloqueo**: la subida requiere el token de PyPI del programador.

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
3. Tag de git con la versión: `git tag v0.1.0 && git push --tags`
   (con orden del programador, P0.7).
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
  autenticada en `gh` (`mainturingcode`) tiene solo lectura en
  `jmbigi/thinker` (`push: false`, verificado vía API el 2026-10-21); el
  push por SSH usa otra identidad. Para crearla: `gh auth login` con una
  cuenta con escritura en el repo y
  `gh release create v0.1.0 dist/* --repo jmbigi/thinker`. Los artefactos
  listos están en `dist/` (regenerarlos con el checklist de abajo si
  cambiaron).

## Notas

- El nombre de distribución (`thinker-research`) y los de importación
  (`evaluar_proyecto`, `deep_research_system`, ...) son independientes: el
  renombrado no afecta al código ni a los usuarios de la librería.
- `dist/` está en `.gitignore`: los artefactos no se versionan.
- Versiones: una versión ya subida a PyPI **no se puede reemplazar**; un
  error exige subir la siguiente versión (o `yank` como último recurso).
