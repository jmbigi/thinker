#!/usr/bin/env python3
"""Preflight determinista, offline y read-only para el código Python.

Comprueba, con AST y sin ejecutar el código analizado:

1. **sintaxis**: todos los ``*.py`` parsean.
2. **imports**: cada import de terceros está declarado en el manifiesto
   (``requirements.txt``/``pyproject.toml``); stdlib y módulos locales no
   necesitan declaración.
3. **silencios**: ``except`` cuyo cuerpo es solo ``pass``, ``continue`` o
   ``...`` (P1.26).
4. **duplicados**: cuerpos de función idénticos y sustanciales (>= 60 nodos
   AST), para detectar copia-pega accidental sin castigar envoltorios pequeños.
5. **tareas**: ``asyncio.create_task``/``ensure_future`` usados como expresión
   suelta, sin guardar la referencia (el event loop puede recolectar la tarea).

No sustituye a los tests, a ruff ni al evaluador: añade una pregunta que esos
instrumentos no hacen. Códigos de salida: 0 = limpio, 1 = hallazgos, 2 = error
de entrada/lectura. Lo no comprobado se declara: no hay red ni ejecución de
código ajeno.
"""

import argparse
import ast
import hashlib
import json
import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from evidence import EvidenceKind  # noqa: E402

IGNORAR = {
    ".git", ".venv", "venv", "__pycache__", "node_modules", ".mypy_cache",
    ".pytest_cache", ".ruff_cache", "mutants", ".tox", "build", "dist",
}
# Nombres de distribución que no coinciden con el módulo que se importa.
ALIAS_IMPORTACION = {
    "dotenv": "python-dotenv",
    "yaml": "pyyaml",
}
MIN_NODOS_DUPLICADO = 60


@dataclass(frozen=True)
class Hallazgo:
    """Un hallazgo con evidencia estática verificable."""

    gate: str
    archivo: str
    linea: int
    mensaje: str
    severidad: str = "media"
    tipo_evidencia: EvidenceKind = EvidenceKind.VERIFIED_REAL

    def a_dict(self) -> Dict[str, Any]:
        return {
            "gate": self.gate,
            "archivo": self.archivo,
            "linea": self.linea,
            "mensaje": self.mensaje,
            "severidad": self.severidad,
            "tipo_evidencia": self.tipo_evidencia.value,
        }


@dataclass
class ResultadoGate:
    """Hallazgos de una comprobación concreta."""

    nombre: str
    hallazgos: List[Hallazgo] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.hallazgos

    def a_dict(self) -> Dict[str, Any]:
        return {
            "nombre": self.nombre,
            "ok": self.ok,
            "hallazgos": [h.a_dict() for h in self.hallazgos],
        }


def archivos_python(root: Path) -> List[Path]:
    """Archivos ``*.py`` bajo ``root``, excluyendo directorios generados."""
    return sorted(
        p for p in root.rglob("*.py")
        if not any(parte in IGNORAR for parte in p.relative_to(root).parts))


def _relativa(root: Path, ruta: Path) -> str:
    return ruta.relative_to(root).as_posix()


def _normalizar(nombre: str) -> str:
    return re.sub(r"[-_.]+", "-", nombre).strip().lower()


def cargar_modulos(root: Path) -> Tuple[Dict[Path, ast.Module], ResultadoGate]:
    """Parsea cada archivo una sola vez; un error de sintaxis es un hallazgo."""
    resultado = ResultadoGate("sintaxis")
    modulos: Dict[Path, ast.Module] = {}
    for ruta in archivos_python(root):
        try:
            texto = ruta.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            resultado.hallazgos.append(Hallazgo(
                "sintaxis", _relativa(root, ruta), 0,
                f"no se pudo leer: {type(exc).__name__}: {exc}", "alta"))
            continue
        try:
            modulos[ruta] = ast.parse(texto, filename=str(ruta))
        except SyntaxError as exc:
            resultado.hallazgos.append(Hallazgo(
                "sintaxis", _relativa(root, ruta), exc.lineno or 0,
                f"error de sintaxis: {exc.msg}", "alta"))
    return modulos, resultado


def _nombre_requisito(linea: str) -> Optional[str]:
    """Nombre de un requisito PEP 508/requirements; ``None`` si no aplica."""
    linea = linea.split("#", 1)[0].strip()
    if not linea or linea.startswith("-"):
        return None
    coincidencia = re.match(r"([A-Za-z0-9_.\-]+)", linea)
    return coincidencia.group(1) if coincidencia else None


def dependencias_declaradas(root: Path) -> Tuple[Set[str], List[Hallazgo]]:
    """Dependencias directas declaradas, normalizadas para comparar imports."""
    declaradas: Set[str] = set()
    hallazgos: List[Hallazgo] = []

    requisitos = root / "requirements.txt"
    if requisitos.exists():
        for linea in requisitos.read_text(encoding="utf-8").splitlines():
            nombre = _nombre_requisito(linea)
            if nombre:
                declaradas.add(_normalizar(nombre))

    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            datos = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            hallazgos.append(Hallazgo(
                "imports", "pyproject.toml", 0,
                f"TOML inválido, no se pueden verificar dependencias: {exc}",
                "alta"))
        else:
            proyecto = datos.get("project", {})
            listas = [proyecto.get("dependencies", [])]
            opcionales = proyecto.get("optional-dependencies", {})
            if isinstance(opcionales, dict):
                listas.extend(opcionales.values())
            for lista in listas:
                if not isinstance(lista, list):
                    continue
                for item in lista:
                    if isinstance(item, str):
                        nombre = _nombre_requisito(item)
                        if nombre:
                            declaradas.add(_normalizar(nombre))
    return declaradas, hallazgos


def modulos_locales(root: Path) -> Set[str]:
    """Módulos importables del propio proyecto (incluye namespace packages)."""
    locales = {p.stem for p in root.glob("*.py")}
    for directorio in root.iterdir():
        if not directorio.is_dir() or directorio.name in IGNORAR:
            continue
        if (directorio / "__init__.py").exists() or any(directorio.glob("*.py")):
            locales.add(directorio.name)
    return locales


def _import_declarado(modulo: str, stdlib: Set[str], locales: Set[str],
                      declaradas: Set[str], permitidos: Set[str]) -> bool:
    if modulo in stdlib or modulo in locales:
        return True
    normalizado = _normalizar(ALIAS_IMPORTACION.get(modulo, modulo))
    return (normalizado in declaradas or modulo in permitidos
            or normalizado in permitidos)


def revisar_imports(root: Path, modulos: Dict[Path, ast.Module],
                    permitidos: Optional[Iterable[str]] = None) -> ResultadoGate:
    resultado = ResultadoGate("imports")
    declaradas, hallazgos_manifiesto = dependencias_declaradas(root)
    resultado.hallazgos.extend(hallazgos_manifiesto)
    stdlib = set(sys.stdlib_module_names)
    locales = modulos_locales(root)
    permitidos_norm = {_normalizar(m) for m in (permitidos or ())}
    vistos: Set[Tuple[Path, str]] = set()

    for ruta, arbol in sorted(modulos.items()):
        for nodo in ast.walk(arbol):
            importados: List[Tuple[str, int]] = []
            if isinstance(nodo, ast.Import):
                importados = [(alias.name.split(".")[0], nodo.lineno)
                              for alias in nodo.names]
            elif (isinstance(nodo, ast.ImportFrom) and nodo.level == 0
                  and nodo.module):
                importados = [(nodo.module.split(".")[0], nodo.lineno)]
            for modulo, linea in importados:
                clave = (ruta, modulo)
                if clave in vistos:
                    continue
                vistos.add(clave)
                if _import_declarado(modulo, stdlib, locales, declaradas,
                                     permitidos_norm):
                    continue
                resultado.hallazgos.append(Hallazgo(
                    "imports", _relativa(root, ruta), linea,
                    f"import no declarado: {modulo}", "alta"))
    return resultado


def _cuerpo_silencioso(cuerpo: List[ast.stmt]) -> bool:
    if len(cuerpo) != 1:
        return False
    unico = cuerpo[0]
    if isinstance(unico, (ast.Pass, ast.Continue)):
        return True
    return (isinstance(unico, ast.Expr)
            and isinstance(unico.value, ast.Constant)
            and unico.value.value is Ellipsis)


def revisar_silencios(root: Path,
                      modulos: Dict[Path, ast.Module]) -> ResultadoGate:
    resultado = ResultadoGate("silencios")
    for ruta, arbol in sorted(modulos.items()):
        for nodo in ast.walk(arbol):
            if (isinstance(nodo, ast.ExceptHandler)
                    and _cuerpo_silencioso(nodo.body)):
                resultado.hallazgos.append(Hallazgo(
                    "silencios", _relativa(root, ruta), nodo.lineno,
                    "except con pass/continue/... (P1.26)", "alta"))
    return resultado


def revisar_duplicados(root: Path,
                       modulos: Dict[Path, ast.Module]) -> ResultadoGate:
    resultado = ResultadoGate("duplicados")
    vistos: Dict[str, Tuple[Path, int, str]] = {}
    for ruta, arbol in sorted(modulos.items()):
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            cuerpo = ast.Module(body=nodo.body, type_ignores=[])
            nodos = sum(1 for _ in ast.walk(cuerpo))
            if len(nodo.body) < 2 or nodos < MIN_NODOS_DUPLICADO:
                continue
            firma = hashlib.sha256(
                ast.dump(cuerpo, include_attributes=False).encode("utf-8")
            ).hexdigest()
            anterior = vistos.get(firma)
            if anterior is None:
                vistos[firma] = (ruta, nodo.lineno, nodo.name)
                continue
            resultado.hallazgos.append(Hallazgo(
                "duplicados", _relativa(root, ruta), nodo.lineno,
                f"cuerpo idéntico a {_relativa(root, anterior[0])}:"
                f"{anterior[1]} ({anterior[2]}); actual: {nodo.name}", "media"))
    return resultado


def _alias_asyncio(arbol: ast.Module) -> Tuple[Set[str], Dict[str, str]]:
    """Alias de ``asyncio`` y de sus funciones de creación de tareas."""
    alias_modulo = {"asyncio"}
    alias_funcion: Dict[str, str] = {}
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            for alias in nodo.names:
                if alias.name == "asyncio":
                    alias_modulo.add(alias.asname or "asyncio")
        elif (isinstance(nodo, ast.ImportFrom) and nodo.level == 0
              and nodo.module == "asyncio"):
            for alias in nodo.names:
                if alias.name in ("create_task", "ensure_future"):
                    alias_funcion[alias.asname or alias.name] = alias.name
    return alias_modulo, alias_funcion


def _nombre_tarea(func: ast.expr, alias_modulo: Set[str],
                  alias_funcion: Dict[str, str]) -> Optional[str]:
    if isinstance(func, ast.Name) and func.id in alias_funcion:
        return f"asyncio.{alias_funcion[func.id]}"
    if isinstance(func, ast.Attribute) and func.attr in (
            "create_task", "ensure_future"):
        base = func.value
        while isinstance(base, ast.Attribute):
            base = base.value
        if isinstance(base, ast.Name) and base.id in alias_modulo:
            return f"asyncio.{func.attr}"
    return None


def revisar_tareas(root: Path,
                   modulos: Dict[Path, ast.Module]) -> ResultadoGate:
    resultado = ResultadoGate("tareas")
    for ruta, arbol in sorted(modulos.items()):
        alias_modulo, alias_funcion = _alias_asyncio(arbol)
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.Expr) or not isinstance(
                    nodo.value, ast.Call):
                continue
            nombre = _nombre_tarea(nodo.value.func, alias_modulo,
                                   alias_funcion)
            if nombre:
                resultado.hallazgos.append(Hallazgo(
                    "tareas", _relativa(root, ruta), nodo.lineno,
                    f"{nombre} sin referencia: el event loop puede recolectar "
                    "la tarea (P1.34)", "media"))
    return resultado


def ejecutar(root: Path, permitidos: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    """Ejecuta todos los gates y devuelve un informe serializable."""
    modulos, sintaxis = cargar_modulos(root)
    gates = [
        sintaxis,
        revisar_imports(root, modulos, permitidos),
        revisar_silencios(root, modulos),
        revisar_duplicados(root, modulos),
        revisar_tareas(root, modulos),
    ]
    total = sum(len(gate.hallazgos) for gate in gates)
    return {
        "root": str(root),
        "archivos_python": len(archivos_python(root)),
        "gates": [gate.a_dict() for gate in gates],
        "total_hallazgos": total,
        "ok": total == 0,
        "evidencia": EvidenceKind.VERIFIED_REAL.value,
    }


def imprimir(informe: Dict[str, Any]) -> None:
    print(f"PREFLIGHT (offline, read-only): {informe['root']}")
    print(f"Python: {informe['archivos_python']} archivos | "
          f"evidencia: {EvidenceKind(informe['evidencia']).marcador} "
          "observación estática, sin ejecutar el código")
    for gate in informe["gates"]:
        estado = "OK" if gate["ok"] else "FAIL"
        print(f"  [{estado}] {gate['nombre']}: "
              f"{len(gate['hallazgos'])} hallazgos")
        for hallazgo in gate["hallazgos"]:
            marca = EvidenceKind(hallazgo["tipo_evidencia"]).marcador
            print(f"    {marca} {hallazgo['archivo']}:{hallazgo['linea']} "
                  f"{hallazgo['mensaje']}")
    veredicto = "OK" if informe["ok"] else "FAIL"
    print(f"PREFLIGHT: {veredicto} ({informe['total_hallazgos']} hallazgos)")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Preflight determinista y offline del código Python.")
    parser.add_argument(
        "--root", default=str(REPO_ROOT),
        help="directorio raíz a revisar (defecto: raíz de este proyecto)")
    parser.add_argument(
        "--json", action="store_true", help="salida JSON para máquinas")
    parser.add_argument(
        "--allow", action="append", default=[], metavar="MODULO",
        help="módulo de importación permitido sin declarar (repetible)")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"ERROR: no es un directorio: {root}", file=sys.stderr)
        return 2
    try:
        informe = ejecutar(root, permitidos=args.allow)
    except (OSError, UnicodeDecodeError) as exc:
        print(f"ERROR: no se pudo leer el proyecto: "
              f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(informe, ensure_ascii=False, indent=2))
    else:
        imprimir(informe)
    return 0 if informe["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
