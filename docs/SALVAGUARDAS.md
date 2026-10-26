# Salvaguardas verificables de thinker

**Fecha:** 2026-10-26. **Alcance:** qué protege este repositorio, con qué
comando se comprueba y qué no se puede prometer. No es una lista de deseos ni
una dependencia de herramientas externas.

## 1. Principio

Una salvaguarda que no se ejecuta no protege. En thinker, cada protección es
un **gate determinista y offline** con salida real, o un test que falla. Las
afirmaciones sin salida se marcan como **no verificadas**, nunca como éxito
(P0.1/P0.2/P1.6).

## 2. Cadena ejecutable

| Riesgo | Salvaguarda | Comando | Evidencia |
|---|---|---|---|
| Sintaxis rota | `py_compile` | hook pre-commit / `make check` | código de salida |
| Estilo y errores estáticos | `ruff check .` | hook / `make check` | 0 errores |
| Silencios, imports no declarados, duplicados, tareas asyncio | `scripts/preflight.py` | hook / `make check` | informe por gate |
| Cifras y pines desactualizados | `scripts/check_docs.py` | hook / `make check` | 0 discrepancias |
| Regresiones funcionales | suite `unittest` | hook / `make test` | `N/N OK` |
| Secretos y datos personales | `scripts/scan-secrets.sh` | hook / `make secrets` | 0 hallazgos |
| Cambios no solicitados o tests debilitados | `scripts/audit_changes.py` | hook / `make audit-diff` | bloqueos |
| Alteración del holdout | `scripts/run_holdout.py` | hook / `make holdout` | hashes + tests |
| Dependencias de archivos no versionados | `scripts/ci.sh` | `make ci` | copia limpia de HEAD en verde |
| Deriva de la documentación | `scripts/check_docs.py` | hook / `make check` | cifras cuadradas |
| Autoevaluación del proyecto | `evaluar_proyecto.py` | `make check` (offline) | informe JSON |

`make check` encadena lint, preflight, docs-check, tests, secretos, CI y el
hook completo. El hook es la última barrera antes de un commit; `--no-verify`
es una excepción deliberada, no el flujo normal.

## 3. Jerarquía de evidencia

`evidence.py` distingue tres procedencias, y el informe las muestra:

1. **`verified-real`**: observación o ejecución real reproducida en esta
   máquina (tests, AST, salida de un comando).
2. **`verified-synthetic`**: fixture o simulación declarada como tal; sirve
   para probar el instrumento, no para afirmar calidad del mundo real.
3. **`unverified`**: no comprobado; se declara y no se suma como éxito.

`MockLLM` y `MockSearchAPI` son **simulados** y así se etiquetan. Un Brier
simulado no es calibración; una suite sin ejecutar no es suite verde.

## 4. Protocolo anti-alucinación para agentes

Antes de decir «hecho», «arreglado», «tests en verde» o «commit creado»:

1. Ejecutar el gate correspondiente **en esta sesión** y mostrar salida real.
2. Si no se ejecutó, escribir **«no verificado»** y explicar por qué.
3. No citar APIs, rutas, versiones ni cifras sin `grep`/`--help`/medición.
4. No declarar equivalentes de mutación sin una prueba semántica.
5. Actualizar las cifras de estado presente (`AGENTS.md`,
   `docs/EVALUACIONES.md`, `README.md`) en el mismo cambio; el gate documental
   falla si no cuadran.
6. Registrar el uso de IA con `Assisted-by:` cuando el proyecto lo requiera
   (P1.14), sin co-autoría de modelos (P1.13).

## 5. DSH (`dsh-tui`): estado verificado y límite

El 2026-10-26 se comprobó el entorno, sin instalar nada:

- `dsh --version` responde `0.2.1-rc.2`.
- `dsh plugin --profile dsh-tui list` falla con `EROFS` al escribir
  `~/.dsh/profiles/dsh-tui/package.json.lock`: el perfil es de solo lectura en
  esta sesión.
- En el registro npm, `dsh-quality-review`, `evidence-first`,
  `dsh-agent-governor` y `dsh-gatedflow` devuelven **404**; el resto de nombres
  del documento externo no se pudo verificar por caché npm de solo lectura.

**Decisión:** no se instalan plugins externos no verificados. Hacerlo
modificaría el perfil del agente, añadiría código de terceros sin revisión de
licencia/seguridad (P0.18) y podría introducir una falsa sensación de
protección. Las garantías que se necesitan ya están cubiertas por los gates de
este repositorio y por las reglas P0/P1; instalar una herramienta no sustituye
una medición.

## 6. Cómo añadir una salvaguarda

1. Añadir el gate determinista (offline, con código de salida claro).
2. Añadirlo al hook y a `make check` (o a `make ci` si necesita copia limpia).
3. Añadir su nombre a `tests/test_guardrails.py` para que no desaparezca.
4. Documentarlo aquí y en `AGENTS.md`; actualizar cifras si aplica.
5. Verificar con salida real y registrar el hallazgo en
   `docs/LECCIONES-APRENDIDAS.md`.

## 7. Límites

- No prueba autoría, intención ni corrección semántica de un cambio; eso exige
  revisión humana (P1.15).
- `audit_changes.py` detecta señales mecánicas, no demuestra que un cambio sea
  seguro.
- La CI es local: no hay una nube independiente que valide el resultado.
- Los gates offline no sustituyen la ejecución real de proveedores; esa
  ejecución es opt-in, se declara y puede fallar por red o cuota.
