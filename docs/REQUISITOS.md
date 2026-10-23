# Verificación de requisitos (`--requisitos`)

Modo **opt-in** del evaluador: contrasta una lista de requisitos declarados por
el usuario contra el proyecto evaluado. Es **read-only**; lo único que puede
ejecutar es la suite de tests del proyecto, y solo con `--ejecutar-tests`
(P0.8). Sin ese flag no se ejecuta nada del proyecto.

El modo no entra en el `GLOBAL` de las seis dimensiones: es un informe aparte
con su propio resumen. Un requisito no es una dimensión de calidad.

## Formato

Archivo Markdown con un bloque por requisito. La cabecera recomendada es
`## ID: título`; si no hay ID explícito se autogenera `R1`, `R2`… y se avisa
de que no es estable. Los campos son viñetas `- Clave: valor`.

```markdown
# Requisitos

## R1: Login con credenciales válidas
- Enunciado: El sistema debe permitir iniciar sesión con usuario y contraseña.
- Criterio de aceptación: Con credenciales válidas se crea una sesión y se
  devuelve 200.
- Verificación: test
- Evidencia: tests/test_auth.py::test_login_valido
- Tags: req~login~1

## R2: Exportación a PDF
- Enunciado: El sistema debe exportar informes a PDF.
- Criterio de aceptación: El comando `export --pdf` genera un archivo PDF
  válido con el informe solicitado.
- Verificación: archivo
- Evidencia: app/export.py

## R3: Revisión de accesibilidad
- Enunciado: La interfaz debe ser accesible.
- Criterio de aceptación: Revisión manual con lector de pantalla.
- Verificación: manual
```

Las claves admiten español e inglés (`Enunciado`/`Statement`,
`Criterio de aceptación`/`Acceptance criteria`, `Verificación`/`Verification`,
`Evidencia`/`Evidence`, `Tags`/`Tag`, `Notas`/`Notes`), sin distinguir
mayúsculas ni acentos. Los campos obligatorios son `Enunciado` y `Criterio de
aceptación`; un campo obligatorio ausente o duplicado es un error con línea, no
un veredicto silencioso. Las líneas de continuación de `Enunciado` y `Criterio`
deben ir **indentadas** (como en los ejemplos); el resto de prosa se ignora.

## Métodos de verificación

| Valor | Qué hace | Veredicto máximo |
|---|---|---|
| `test` | Comprueba que el archivo y, en Python, la función de test existen | `CUBIERTO`; `CUMPLE` solo con suite verde |
| `archivo` | Comprueba que el archivo de evidencia existe | `CUBIERTO` |
| `tag` | Busca la etiqueta en código y tests | `CUBIERTO` |
| `formal` | Comprueba que el artefacto formal declarado existe | `CUBIERTO` |
| `manual` | No se puede automatizar | `NO VERIFICABLE` |

La evidencia debe ser una ruta **relativa al proyecto**; una ruta absoluta
fuera del proyecto se declara `NO VERIFICABLE` y no se lee. Para un test Python
se admite `ruta.py::test_funcion`, `ruta.py::Clase::test_metodo` o
`ruta.py::test_parametrizado[caso]`; el nombre se comprueba con AST.

## Veredictos

- `CUMPLE`: la suite del proyecto se ejecutó con `--ejecutar-tests`, terminó
  verde y el test declarado existe. No se aísla el test: el veredicto se apoya
  en la suite completa y así se declara en el motivo.
- `CUBIERTO`: la evidencia estática existe (archivo, test, tag o artefacto
  formal), pero no se ha ejecutado o no prueba comportamiento. **No es
  “cumple”.**
- `NO CUMPLE`: la evidencia declarada no existe, el test no se encuentra o la
  suite ejecutada falló.
- `NO VERIFICABLE`: no hay método, es manual, el criterio no es medible o la
  evidencia está fuera del proyecto. Requiere revisión humana.

Un criterio demasiado corto o con términos vagos (`fácil`, `rápido`, `óptimo`,
`etc.`) genera un **aviso**; si además no hay evidencia, el veredicto es
`NO VERIFICABLE`. El aviso no sustituye a la evidencia.

## Uso

```bash
python3 evaluar_proyecto.py RUTA --requisitos requisitos.md
python3 evaluar_proyecto.py RUTA --requisitos requisitos.md --ejecutar-tests
evaluate-project RUTA --requisitos requisitos.md --json
```

Con `--json`, el informe añade la clave opcional `requisitos`:

```json
{
  "schema_version": 2,
  "requisitos": {
    "archivo": "requisitos.md",
    "total": 3,
    "resumen": {"cumple": 1, "cubierto": 1, "no_cumple": 0, "no_verificable": 1},
    "afecta_global": false,
    "nota": "CUMPLE exige suite verde; CUBIERTO es solo evidencia estática; no afecta al GLOBAL",
    "items": [
      {
        "id": "R1",
        "titulo": "Login con credenciales válidas",
        "origen": "requisitos.md:3",
        "veredicto": "CUMPLE",
        "motivo": "suite completa verde (test declarado, no aislado)",
        "evidencia_observada": "tests/test_auth.py",
        "tipo_evidencia": "verified-real",
        "avisos": []
      }
    ],
    "no_verificado": ["..."]
  }
}
```

El resto del contrato JSON no cambia (`schema_version: 2`): la clave es
opcional y solo aparece con `--requisitos`.

## Límites declarados

- La validación del nombre de test es Python-first (AST). En otros lenguajes se
  comprueba el archivo, no el test concreto.
- La comprobación AST solo verifica que exista una función con ese nombre; no
  confirma que el runner la descubra ni que sea un test válido.
- `CUMPLE` no demuestra equivalencia semántica entre requisito y test; demuestra
  que la suite declarada pasa y que el test existe.
- Un `tag` demuestra cobertura declarada, no que el código implemente el
  requisito.
- La calidad del resultado depende de que el criterio de aceptación sea medible.
  Un requisito general que no se pueda operationalizar debe quedar como
  `NO VERIFICABLE`.
