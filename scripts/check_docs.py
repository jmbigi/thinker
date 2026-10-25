"""Verificación determinista de cifras de estado presente en la documentación.

Offline y read-only (P0.1/P0.2): contrasta las afirmaciones volátiles que
envejecen con cada cambio contra el estado real del repositorio — nº de tests
declarado, pines de `requirements.txt` frente a `requirements.lock`, versión
del paquete frente a la publicada y cifra de mutación de `README.md` frente a
la vigente de `AGENTS.md`. Los históricos fechados no se comprueban.

Uso: python3 scripts/check_docs.py [RAIZ]
Códigos: 0 todo cuadra | 1 discrepancias | 2 error de lectura/parseo.
"""

import ast
import re
import sys
import tomllib
from pathlib import Path

PATRON_TESTS = re.compile(r"(\d+)/(\d+) en")
PATRON_MUTACION_README = re.compile(
    r"La suite mata el \*\*([\d,]+)%\*\* de los mutantes de `mutmut`"
    r"\s*\((\d+)/(\d+);", re.S | re.I)
PATRON_MUTACION_AGENTS = re.compile(
    r"la mutación global es ([\d,]+)% \((\d+)/(\d+);", re.I)


def contar_tests(raiz: Path) -> int:
    """Métodos `test_*` en clases TestCase de `tests/` (conteo estático).

    No importa ni ejecuta nada: el mismo criterio que usa unittest para
    descubrir, sin efectos laterales (P0.8).
    """
    total = 0
    for archivo in (raiz / "tests").rglob("*.py"):
        arbol = ast.parse(archivo.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.ClassDef):
                continue
            bases = {ast.unparse(base) for base in nodo.bases}
            if not any("TestCase" in base for base in bases):
                continue
            total += sum(1 for hijo in nodo.body
                         if isinstance(hijo, ast.FunctionDef)
                         and hijo.name.startswith("test"))
    return total


def _declarado_agents(raiz: Path) -> int:
    lineas = (raiz / "AGENTS.md").read_text(encoding="utf-8").splitlines()
    indice = next((i for i, linea in enumerate(lineas)
                   if "Plataformas verificadas" in linea), None)
    if indice is None:
        raise ValueError("AGENTS.md no tiene la viñeta 'Plataformas verificadas'")
    fragmento = "\n".join(lineas[indice:indice + 12])
    coincidencia = PATRON_TESTS.search(fragmento)
    if not coincidencia:
        raise ValueError("AGENTS.md no declara la cifra 'N/N en' de la suite")
    if coincidencia.group(1) != coincidencia.group(2):
        raise ValueError(f"cifra asimétrica en AGENTS.md: "
                         f"{coincidencia.group(1)}/{coincidencia.group(2)}")
    return int(coincidencia.group(1))


def _declarado_evaluaciones(raiz: Path) -> int:
    texto = (raiz / "docs" / "EVALUACIONES.md").read_text(encoding="utf-8")
    indice = texto.rfind("**Actualización ")
    if indice == -1:
        raise ValueError("EVALUACIONES.md sin bloque '**Actualización '")
    coincidencia = re.search(r"Suite \*\*(\d+)/\1\*\* en Linux", texto[indice:])
    if not coincidencia:
        raise ValueError("el último bloque de EVALUACIONES.md no declara "
                         "'Suite **N/N** en Linux'")
    return int(coincidencia.group(1))


def _cifra_mutacion(texto: str, patron: re.Pattern) -> tuple | None:
    """Extrae (porcentaje, muertos, total) de una afirmación de mutación."""
    coincidencia = patron.search(texto)
    if coincidencia is None:
        return None
    return (coincidencia.group(1), int(coincidencia.group(2)),
            int(coincidencia.group(3)))


def _leer_requisitos(raiz: Path):
    pines, rangos = {}, {}
    for linea in (raiz / "requirements.txt").read_text(encoding="utf-8").splitlines():
        linea = linea.split("#", 1)[0].strip()
        if not linea or linea.startswith(("-", "git+", "http")):
            continue
        coincidencia = re.match(r"([A-Za-z0-9][A-Za-z0-9._-]*)\s*(.*)", linea)
        if not coincidencia:
            continue
        nombre, especificacion = coincidencia.group(1).lower(), coincidencia.group(2).strip()
        if especificacion.startswith("=="):
            pines[nombre] = especificacion[2:].strip()
        elif especificacion:
            rangos[nombre] = especificacion
    return pines, rangos


def _leer_lock(raiz: Path) -> dict:
    versiones = {}
    for linea in (raiz / "requirements.lock").read_text(encoding="utf-8").splitlines():
        if not linea.strip() or linea.startswith(("#", " ", "-")):
            continue
        coincidencia = re.match(r"([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;]+)", linea)
        if coincidencia:
            versiones[coincidencia.group(1).lower()] = coincidencia.group(2)
    return versiones


def _version_tupla(texto: str) -> tuple:
    return tuple(int(parte) for parte in re.findall(r"\d+", texto))


def _cumple_rango(version: str, especificacion: str) -> bool:
    """Rangos simples de requirements (`>=1.0,<4`), sin dependencias extra."""
    actual = _version_tupla(version)
    for restriccion in especificacion.split(","):
        restriccion = restriccion.strip()
        if not restriccion:
            continue
        coincidencia = re.match(r"(>=|<=|==|!=|>|<)\s*(\S+)", restriccion)
        if not coincidencia:
            raise ValueError(f"restricción no soportada: {restriccion!r}")
        operador, limite = coincidencia.group(1), _version_tupla(
            coincidencia.group(2))
        if not {
            ">=": actual >= limite, "<=": actual <= limite,
            "==": actual == limite, "!=": actual != limite,
            ">": actual > limite, "<": actual < limite,
        }[operador]:
            return False
    return True


def verificar(raiz: Path) -> list[str]:
    problemas = []

    real = contar_tests(raiz)
    for nombre, declarado in (("AGENTS.md", _declarado_agents(raiz)),
                              ("docs/EVALUACIONES.md",
                               _declarado_evaluaciones(raiz))):
        if declarado != real:
            problemas.append(f"{nombre} declara {declarado} tests y hay {real}: "
                             "actualiza la cifra o retira la afirmación")

    readme = raiz / "README.md"
    if readme.exists():
        de_readme = _cifra_mutacion(readme.read_text(encoding="utf-8"),
                                    PATRON_MUTACION_README)
        de_agents = _cifra_mutacion(
            (raiz / "AGENTS.md").read_text(encoding="utf-8"),
            PATRON_MUTACION_AGENTS)
        if de_readme is None:
            problemas.append(
                "README.md no declara la cifra de mutación en el formato "
                "esperado ('La suite mata el **N%** ...')")
        elif de_agents is None:
            problemas.append(
                "README.md declara la cifra de mutación y AGENTS.md no tiene "
                "la cifra vigente ('la mutación global es ...')")
        elif de_readme != de_agents:
            problemas.append(
                f"README.md declara mutación {de_readme[0]}% "
                f"({de_readme[1]}/{de_readme[2]}) y AGENTS.md "
                f"{de_agents[0]}% ({de_agents[1]}/{de_agents[2]}): "
                "actualiza la cifra o retira la afirmación")

    pines, rangos = _leer_requisitos(raiz)
    lock = _leer_lock(raiz)
    for nombre, version in sorted(pines.items()):
        if nombre not in lock:
            problemas.append(f"requirements.txt fija {nombre}=={version} pero "
                             "no está en requirements.lock")
        elif lock[nombre] != version:
            problemas.append(f"requirements.txt fija {nombre}=={version} y el "
                             f"lock tiene {lock[nombre]}")
    for nombre, especificacion in sorted(rangos.items()):
        if nombre not in lock:
            problemas.append(f"requirements.txt declara {nombre}{especificacion} "
                             "pero no está en requirements.lock")
        elif not _cumple_rango(lock[nombre], especificacion):
            problemas.append(f"{nombre} del lock ({lock[nombre]}) no cumple "
                             f"el rango declarado {especificacion}")

    datos = tomllib.loads((raiz / "pyproject.toml").read_text(encoding="utf-8"))
    version = (datos.get("project") or {}).get("version")
    texto_publicacion = (raiz / "docs" / "PUBLICACION.md").read_text(encoding="utf-8")
    publicadas = set(re.findall(
        r"versión\s+`(\d+\.\d+\.\d+)`\s+publicada en TestPyPI y PyPI",
        texto_publicacion))
    publicadas |= set(re.findall(
        r"thinker-research (\d+\.\d+\.\d+)", texto_publicacion))
    if not version:
        problemas.append("pyproject.toml no declara [project] version")
    elif version not in publicadas:
        problemas.append(f"pyproject declara versión {version} y PUBLICACION.md "
                         f"no la menciona como publicada ({sorted(publicadas)})")

    return problemas


def main(argv=None) -> int:
    argumentos = sys.argv[1:] if argv is None else argv
    raiz = Path(argumentos[0]) if argumentos else Path(__file__).resolve().parent.parent
    try:
        problemas = verificar(raiz)
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        print(f"DOCS: no verificable: {exc}", file=sys.stderr)
        return 2
    if problemas:
        print(f"DOCS: {len(problemas)} discrepancia(s)")
        for problema in problemas:
            print(f"  [FALLO] {problema}")
        return 1
    print("DOCS: OK (cifras y pines de estado presente cuadran)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
