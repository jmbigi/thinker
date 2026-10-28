# Política de seguridad

`thinker` (`thinker-research`) es un proyecto **local-first**: no hay servicio
en la nube ni datos de terceros almacenados por los mantenedores. Esta política
cubre el paquete publicado en PyPI, los comandos `evaluate-project`, `think`,
`research` y `code-design`, el subsistema de plugins y los scripts del
repositorio.

## Cómo reportar una vulnerabilidad

Usa el **reporte privado de GitHub Security Advisories** del repositorio
(botón «Report a vulnerability» en la pestaña *Security*):

<https://github.com/jmbigi/thinker/security/advisories/new>

No abras un issue público con detalles explotables. No se usan correos
personales como canal.

## Qué está en alcance

- Fuga de credenciales (API keys, tokens) en informes, logs o mensajes de
  error generados por el proyecto.
- Ejecución de código no prevista: `--ejecutar-tests` ejecuta el comando que
  el proyecto evaluado declara, **con los permisos del usuario** (riesgo
  conocido; ver más abajo). Cualquier ejecución fuera de ese opt-in es un
  fallo de seguridad.
- Escape del directorio de plugins (path traversal) en el registro de plugins.
- Prompt injection: contenido recuperado de la web que consiga que el sistema
  lo trate como instrucciones privilegiadas en lugar de datos.
- Manipulación de la evaluación (`evaluar_proyecto`) para ocultar hallazgos
  reales.

## Qué queda fuera de alcance

- Vulnerabilidades de dependencias de terceros: se reportan upstream. El
  proyecto publica SBOM (`make sbom`) y `make vuln-scan` (pip-audit) para
  seguirlas.
- Limitaciones **declaradas** del proyecto: `MockLLM`/`MockSearchAPI` son
  simulados y lo dicen; `credibility`/`confidence` no están calibradas; la
  ejecución de tests ajenos es opt-in y no está en sandbox (se acota con
  timeout y límites de recursos donde el SO lo permite).
- Ataques que requieran control del entorno local del usuario.

## Riesgos conocidos y declarados

- **`--ejecutar-tests` no es un sandbox**: ejecuta código del proyecto
  evaluado con los permisos del usuario. Es opt-in explícito, usa el comando
  que el proyecto declara, `shell=False` y timeout; en Linux se añaden límites
  de CPU y memoria al subproceso. No ejecutes el evaluador con
  `--ejecutar-tests` sobre código en el que no confías.
- Los proveedores LLM reciben el texto que el pipeline envía; el proyecto no
  envía claves a nadie más que al proveedor configurado.

## Plazos de respuesta

- Acuse de recibo: **7 días laborables**.
- Análisis inicial y plan: **30 días**.
- Publicación de la corrección: cuando esté verificada con tests; si aplica, se
  emite un aviso de seguridad y una versión nueva en PyPI.

Estos plazos son objetivos razonables de un mantenedor único, no un SLA
contractual.
