# Auditoría de cambios de agentes (`scripts/audit_changes.py`)

Herramienta **opt-in, offline y read-only** para revisar un diff antes de
aceptarlo. No detecta “intención” ni autoría: detecta **señales mecánicas**
compatibles con cambios no solicitados, sustitución de requisitos o
debilitamiento de la verificación. Un hallazgo es evidencia para revisar, no una
prueba de culpabilidad.

## Qué detecta

| Regla | Señal | Severidad |
|---|---|---|
| `ruta_sensible` | `.env`, claves, certificados | alta |
| `ci_hooks` | `.github/`, `scripts/hooks/`, `.pre-commit-config.yaml` | alta |
| `test_borrado` | archivo de test eliminado | alta |
| `tests_modificados` | cualquier cambio en `tests/` | media |
| `holdout_modificado` | cambio en `holdout/` (revisar hashes) | media |
| `skip_añadido` | `@pytest.mark.skip`, `xfail`, `self.skipTest`, `it.skip` | alta |
| `asserts_eliminados` | test conservado con menos aserciones que antes | alta |
| `test_eliminado` | función de test borrada (posible limpieza) | media |
| `matcher_flojo` | `assertEqual` → `assertTrue`, `toBe` → `toBeDefined` | media |
| `supresion_global` | `# noqa` sin código, `# type: ignore` sin código, `@ts-nocheck`, `eslint-disable` de bloque | alta |
| `supresion_especifica` | `# noqa: E501`, `type: ignore[...]`, `eslint-disable-next-line` | media |
| `cobertura_rebajada` | `fail_under` o `coverageThreshold` bajado | alta |
| `config_relajada` | `strict: false`, `continue-on-error: true`, `allow_failure: true` | alta |
| `config_revisar` | `--ignore`, `extend-ignore`, `exclude`, `omit` añadidos | media |
| `lockfile` | lockfile modificado | media |
| `dependencia_nueva` | dependencia añadida en manifiesto/requirements | media |
| `requisitos_modificados` | `docs/REQUISITOS.md`, `requisitos*.md`, `specs/**` | media |
| `reglas_modificadas` | `AGENTS.md` | media |
| `manifiesto` | `pyproject.toml`, `requirements.txt`, `package.json`, etc. | media |
| `config_build` | `Makefile`, `tox.ini`, `pytest.ini`, `setup.cfg` | media |
| `archivo_eliminado` | archivo no test eliminado | media |
| `binario` | archivo binario modificado | media |
| `comando_peligroso` | `git push --force`, `git reset --hard`, `rm -rf`, `--no-verify`, `curl \| bash` | alta |
| `eval_exec` | `eval(` o `exec(` añadidos en código | media |
| `presupuesto_archivos` | más de `--max-archivos` archivos | media |
| `presupuesto_lineas` | más de `--max-lineas` líneas cambiadas | media |

Los patrones y las reglas viven en el código; esta tabla es el contrato
funcional. Si se añade una regla, se actualizan la tabla y los tests.

## Uso

```bash
python3 scripts/audit_changes.py --staged
python3 scripts/audit_changes.py --base origin/main
git diff origin/main...HEAD | python3 scripts/audit_changes.py --diff -
python3 scripts/audit_changes.py --base HEAD~1 --json
python3 scripts/audit_changes.py --base origin/main --permitir tests/ --permitir docs/
```

`--permitir RUTA` suprime el hallazgo de **ruta** para ese prefijo, pero no
desactiva las reglas de contenido: un test permitido sigue siendo revisado por
skips, asserts y cobertura. Es deliberado: permitir tocar tests no significa
permitir debilitarlos. Un archivo de test **eliminado** se marca siempre como
`BLOQUEAR`, incluso con `--permitir tests/`.

## Veredictos y códigos de salida

- `OK`: ninguna señal.
- `REVISAR`: hay señales medias o bajas; un humano decide.
- `BLOQUEAR`: hay al menos una señal alta.

Códigos: `0` sin hallazgos o por debajo del umbral; `1` hallazgos según
`--fallar-en`; `2` error de entrada o de `git diff`.

`--fallar-en {ninguno,revisar,bloquear}` (defecto `revisar`) permite usar el
auditor como aviso o como gate.

## Cómo integrarlo

Pre-commit local, solo sobre lo preparado:

```bash
python3 scripts/audit_changes.py --staged --fallar-en bloquear
```

CI, comparando la rama con la base:

```bash
python3 scripts/audit_changes.py --base origin/main --fallar-en bloquear --json
```

El hook del repo ya lo ejecuta con `--staged --fallar-en bloquear`: solo las
señales altas bloquean; los cambios de tests/configuración se muestran como
`REVISAR` y quedan para el humano. El auditor está pensado para ejecutarse
**fuera del alcance de escritura del agente** (CI, otra rama, otro checkout).
Si el agente puede editar el auditor, la política o el workflow, el control
deja de ser fiable.

Cambiar `scripts/hooks/pre-commit` se marca como `BLOQUEAR` (alta). Si es
intencional, revisa el diff y usa `git commit --no-verify` de forma explícita;
el primer commit que instala este hook se hizo con el hook anterior, porque el
nuevo aún no estaba instalado.

## Holdout

`holdout/` es una suite independiente que **no** descubre `make test`.
`scripts/run_holdout.py` verifica el SHA-256 de cada `test_*.py` contra
`holdout/HASHES.json` y después ejecuta los tests:

```bash
python3 scripts/run_holdout.py          # verifica hashes y ejecuta
python3 scripts/run_holdout.py --update # actualiza hashes; revisar el diff
make holdout
```

Si un test holdout cambia sin actualizar el manifiesto, el runner falla con
código 2. Si se actualizan ambos, el auditor marca `holdout_modificado` para
revisión humana. El holdout se ejecuta en el hook pre-commit y en `make ci`.
Es **tamper-evidence**, no una protección criptográfica: alguien con permiso
para editar tests y manifiesto puede hacerlo; el control real es que ese cambio
se revise y que el runner se ejecute fuera del alcance del agente.

## Límites

- No detecta autoría ni intención: un humano puede hacer los mismos cambios.
- No entiende semántica: un test reescrito para comprobar algo verdadero pero
  irrelevante puede pasar. Para eso hacen falta holdout tests, mutación y
  revisión.
- Un test borrado puede ser limpieza legítima; por eso es `REVISAR`, no
  `BLOQUEAR`, salvo que se borre el archivo completo.
- Un `assert` movido a un helper puede parecer una pérdida; el auditor marca
  `REVISAR` cuando hay asserts añadidos y `BLOQUEAR` cuando el test sobrevive
  sin ninguno.
- No sustituye a `scan-secrets.sh`, `preflight`, la suite ni la revisión
  humana. Es una capa más.
- El diff puede contener secretos; la salida redacta patrones conocidos y
  trunca la evidencia, pero no es un escáner de secretos.

## Relación con `--requisitos`

`evaluar_proyecto.py --requisitos` comprueba que cada requisito tenga evidencia
y que la suite pase. El auditor de cambios mira **cómo cambió** el repositorio:
si se tocaron tests, cobertura, CI, requisitos o configuración. Se complementan:
`CUMPLE` con tests debilitados es un falso positivo que el auditor debe
detectar y un humano debe revisar.
