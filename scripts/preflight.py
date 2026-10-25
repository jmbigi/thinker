#!/usr/bin/env python3
"""Preflight determinista, offline y read-only para el código Python.

Comprueba, con AST y sin ejecutar el código analizado:

1. **sintaxis**: todos los ``*.py`` parsean.
2. **imports**: cada import de terceros está declarado en el manifiesto
   (``requirements.txt``/``pyproject.toml``); stdlib y módulos locales no
   necesitan declaración. Exenciones (no se exigen en el manifiesto): imports
   bajo ``TYPE_CHECKING`` o ``if __name__ == "__main__"``, imports dentro de
   ``try/except ImportError`` (dependencia opcional) e imports bajo flags
   ``has_*`` (opcional ya detectada en tiempo de ejecución).
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
import configparser
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
    ".eggs", ".nox",
    # Scripts locales de depuración: no forman parte del proyecto (.gitignore).
    "_local_debug",
}
# Directorios generados que no siempre llevan el nombre exacto: entornos
# virtuales con sufijo (`.venv-docs`, `venv-old`) y temporales de pytest.
PREFIJOS_GENERADOS = (".venv", "venv-", "pytest-of-")
SUFIJOS_GENERADOS = (".egg-info",)


def es_parte_ignorada(parte: str, nombres: Iterable[str] = IGNORAR) -> bool:
    """True si un componente de ruta es un directorio generado o ignorado.

    ``nombres`` permite al evaluador aportar su propio conjunto sin duplicar
    la regla de prefijos/sufijos. ``exe`` no se ignora: puede ser código real.
    """
    nombre = parte.lower()
    return (nombre in nombres
            or any(nombre.startswith(prefijo) for prefijo in PREFIJOS_GENERADOS)
            or any(nombre.endswith(sufijo) for sufijo in SUFIJOS_GENERADOS))


# Nombres de distribución que no coinciden con el módulo que se importa.
ALIAS_IMPORTACION = {
    "dotenv": "python-dotenv",
    "yaml": "pyyaml",
    "opentelemetry": "opentelemetry-api",
    "pydantic_core": "pydantic-core",
    "github": "pygithub",
    "git": "gitpython",
    "slugify": "python-slugify",
    "_pytest": "pytest",
    "attr": "attrs",
    "openssl": "pyopenssl",
    "dateutil": "python-dateutil",
    "annotated_types": "annotated-types",
    # pywin32 expone módulos de nivel superior que no se llaman pywin32.
    "win32api": "pywin32",
    "win32con": "pywin32",
    "win32gui": "pywin32",
    "win32com": "pywin32",
    "pythoncom": "pywin32",
    "pywintypes": "pywin32",
    # Distribuciones con un import package distinto del nombre en PyPI.
    "PIL": "pillow",
    "docx": "python-docx",
    "pptx": "python-pptx",
}
# Módulos de la stdlib que aún no existen en el Python que ejecuta el gate
# (p. ej. annotationlib en 3.14): no son dependencias de terceros.
STDLIB_FUTURA = {"annotationlib"}
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
    """Hallazgos y warnings de una comprobación concreta."""

    nombre: str
    hallazgos: List[Hallazgo] = field(default_factory=list)
    advertencias: List[Hallazgo] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.hallazgos

    def a_dict(self) -> Dict[str, Any]:
        return {
            "nombre": self.nombre,
            "ok": self.ok,
            "hallazgos": [h.a_dict() for h in self.hallazgos],
            "advertencias": [h.a_dict() for h in self.advertencias],
        }


def archivos_python(root: Path) -> List[Path]:
    """Archivos ``*.py`` bajo ``root``, excluyendo directorios generados."""
    return sorted(
        p for p in root.rglob("*.py")
        if not any(es_parte_ignorada(parte)
                   for parte in p.relative_to(root).parts))


def _relativa(root: Path, ruta: Path) -> str:
    return ruta.relative_to(root).as_posix()


def _normalizar(nombre: str) -> str:
    return re.sub(r"[-_.]+", "-", nombre).strip().lower()


def cargar_modulos(root: Path,
                   archivos: Optional[Iterable[Path]] = None
                   ) -> Tuple[Dict[Path, ast.Module], ResultadoGate]:
    """Parsea cada archivo una sola vez; un error de sintaxis es un hallazgo.

    ``archivos`` permite al evaluador limitar el gate AST al código de
    producción de un paquete (sin tests/docs/ejemplos).
    """
    resultado = ResultadoGate("sintaxis")
    modulos: Dict[Path, ast.Module] = {}
    objetivo = sorted(archivos) if archivos is not None else archivos_python(root)
    for ruta in objetivo:
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


def _leer_requisitos(archivo: Path, vistos: Set[Path]) -> Set[str]:
    """Nombres de un requirements, siguiendo ``-r`` sin ciclos."""
    archivo = archivo.resolve()
    if archivo in vistos or not archivo.is_file():
        return set()
    vistos.add(archivo)
    nombres: Set[str] = set()
    try:
        texto = archivo.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return nombres
    for linea in texto.splitlines():
        limpia = linea.split("#", 1)[0].strip()
        include = re.match(r"^(?:-r|--requirement)\s+(.+)$", limpia)
        if include:
            nombres.update(_leer_requisitos(
                archivo.parent / include.group(1).strip(), vistos))
            continue
        nombre = _nombre_requisito(linea)
        if nombre:
            nombres.add(_normalizar(nombre))
    return nombres


def _nombres_de_lista(items: Any) -> Set[str]:
    nombres = set()
    if not isinstance(items, list):
        return nombres
    for item in items:
        if isinstance(item, str):
            nombre = _nombre_requisito(item)
            if nombre:
                nombres.add(_normalizar(nombre))
    return nombres


def _nombres_setup(valor: Any) -> Set[str]:
    """Nombres de dependencias en listas/dicts de setup.py (no las claves)."""
    nombres: Set[str] = set()
    if isinstance(valor, dict):
        for lista in valor.values():
            nombres.update(_nombres_setup(lista))
    elif isinstance(valor, (list, tuple)):
        for item in valor:
            if isinstance(item, str):
                nombre = _nombre_requisito(item)
                if nombre:
                    nombres.add(_normalizar(nombre))
    return nombres


def dependencias_declaradas(root: Path) -> Tuple[Set[str], List[Hallazgo]]:
    """Dependencias directas declaradas en TODOS los manifiestos Python.

    Cubre pyproject (PEP 621, PEP 735, Poetry/PDM), requirements anidados con
    ``-r``, setup.cfg y setup.py. Los tests/docs que importan dependencias de
    desarrollo dejan de ser falsos positivos de h6.
    """
    declaradas: Set[str] = set()
    hallazgos: List[Hallazgo] = []
    vistos_req: Set[Path] = set()

    for archivo in sorted(p for p in root.rglob("*")
                          if p.is_file() and not any(
                              es_parte_ignorada(parte)
                              for parte in p.relative_to(root).parts)):
        nombre = archivo.name.lower()
        relativa = _relativa(root, archivo)
        es_requisitos = bool(re.match(r"requirements.*\.(txt|in)$", nombre)) or (
            archivo.parent.name.lower() == "requirements"
            and archivo.suffix.lower() in (".txt", ".in"))
        if es_requisitos:
            declaradas.update(_leer_requisitos(archivo, vistos_req))
        elif nombre == "pyproject.toml":
            try:
                datos = tomllib.loads(archivo.read_text(encoding="utf-8"))
            except (tomllib.TOMLDecodeError, OSError) as exc:
                hallazgos.append(Hallazgo(
                    "imports", relativa, 0,
                    f"TOML inválido, no se pueden verificar dependencias: {exc}",
                    "alta"))
                continue
            proyecto = datos.get("project")
            if isinstance(proyecto, dict):
                declaradas.update(_nombres_de_lista(
                    proyecto.get("dependencies", [])))
                opcionales = proyecto.get("optional-dependencies", {})
                if isinstance(opcionales, dict):
                    for lista in opcionales.values():
                        declaradas.update(_nombres_de_lista(lista))
            grupos = datos.get("dependency-groups")
            if isinstance(grupos, dict):
                for lista in grupos.values():
                    declaradas.update(_nombres_de_lista(lista))
            herramientas = datos.get("tool")
            if isinstance(herramientas, dict):
                poesia = herramientas.get("poetry", {})
                if isinstance(poesia, dict):
                    for seccion in ("dependencies", "dev-dependencies"):
                        bloque = poesia.get(seccion, {})
                        if isinstance(bloque, dict):
                            declaradas.update(_normalizar(k) for k in bloque
                                              if str(k).lower() != "python")
                    grupos_poesia = poesia.get("group", {})
                    if isinstance(grupos_poesia, dict):
                        for grupo in grupos_poesia.values():
                            if isinstance(grupo, dict):
                                bloque = grupo.get("dependencies", {})
                                if isinstance(bloque, dict):
                                    declaradas.update(
                                        _normalizar(k) for k in bloque)
                pdm = herramientas.get("pdm", {})
                if isinstance(pdm, dict) and isinstance(
                        pdm.get("dev-dependencies"), dict):
                    for lista in pdm["dev-dependencies"].values():
                        declaradas.update(_nombres_de_lista(lista))
        elif nombre == "setup.cfg":
            parser = configparser.ConfigParser()
            try:
                parser.read_string(archivo.read_text(encoding="utf-8"))
            except (configparser.Error, OSError) as exc:
                hallazgos.append(Hallazgo(
                    "imports", relativa, 0,
                    f"setup.cfg inválido, no se pueden verificar dependencias: "
                    f"{exc}", "alta"))
                continue
            for seccion, clave in (("options", "install_requires"),
                                   ("options", "tests_require")):
                if parser.has_option(seccion, clave):
                    for linea in parser.get(seccion, clave).splitlines():
                        nombre_dep = _nombre_requisito(linea)
                        if nombre_dep:
                            declaradas.add(_normalizar(nombre_dep))
            if parser.has_section("options.extras_require"):
                for valor in parser["options.extras_require"].values():
                    for linea in valor.splitlines():
                        nombre_dep = _nombre_requisito(linea)
                        if nombre_dep:
                            declaradas.add(_normalizar(nombre_dep))
        elif nombre == "setup.py":
            try:
                texto = archivo.read_text(encoding="utf-8")
            except OSError as exc:
                hallazgos.append(Hallazgo(
                    "imports", relativa, 0,
                    f"setup.py ilegible, no se pueden verificar dependencias: "
                    f"{exc}", "alta"))
                continue
            try:
                arbol = ast.parse(texto)
            except SyntaxError:
                arbol = None
            if arbol is not None:
                for nodo in ast.walk(arbol):
                    if not isinstance(nodo, ast.Call):
                        continue
                    for kw in nodo.keywords:
                        if kw.arg not in ("install_requires", "tests_require",
                                          "extras_require"):
                            continue
                        try:
                            valor = ast.literal_eval(kw.value)
                        except (ValueError, TypeError):
                            valor = None
                        if valor is not None:
                            declaradas.update(_nombres_setup(valor))
    return declaradas, hallazgos


def modulos_locales(root: Path) -> Set[str]:
    """Módulos importables del propio proyecto (incluye layout ``src/``).

    Ruff y la convención de packaging consideran primera parte tanto la raíz
    como ``src/``; ignorar ``src/`` convertía ``import flask`` en un import de
    terceros sin declarar en proyectos con ese layout.
    """
    locales = {p.stem for p in root.glob("*.py")}
    for base in (root, root / "src"):
        if not base.is_dir():
            continue
        for directorio in base.iterdir():
            if not directorio.is_dir() or directorio.name in IGNORAR:
                continue
            if (directorio / "__init__.py").exists() \
                    or any(directorio.glob("*.py")):
                locales.add(directorio.name)
    for archivo in archivos_python(root):
        # Módulos de primer nivel en src/lib anidados de monorepos (Hypothesis
        # tiene hypothesis/src/_hypothesis_globals.py).
        if archivo.parent.name in ("src", "lib"):
            locales.add(archivo.stem)
        actual, ultimo = archivo.parent, None
        while actual != root and (actual / "__init__.py").exists():
            ultimo, actual = actual, actual.parent
        if ultimo is not None:
            locales.add(ultimo.name)
    return locales


def _import_declarado(modulo: str, stdlib: Set[str], locales: Set[str],
                      declaradas: Set[str], permitidos: Set[str]) -> bool:
    if modulo in stdlib or modulo in STDLIB_FUTURA or modulo in locales:
        return True
    normalizado = _normalizar(ALIAS_IMPORTACION.get(modulo, modulo))
    return (normalizado in declaradas or modulo in permitidos
            or normalizado in permitidos)


def _nombre_excepcion(nodo: Any) -> str:
    if isinstance(nodo, ast.Name):
        return nodo.id
    if isinstance(nodo, ast.Tuple):
        return ",".join(_nombre_excepcion(item) for item in nodo.elts)
    return ""


def _lineas_import_opcional(arbol: ast.Module) -> Set[int]:
    """Líneas de imports dentro de ``try: import ... except ImportError``."""
    lineas: Set[int] = set()
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Try):
            continue
        captura_import = any(
            nombre in ("ImportError", "ModuleNotFoundError")
            for handler in nodo.handlers
            for nombre in _nombre_excepcion(handler.type).split(","))
        if not captura_import:
            continue
        for sentencia in list(nodo.body) + list(nodo.orelse):
            for sub in ast.walk(sentencia):
                if isinstance(sub, (ast.Import, ast.ImportFrom)):
                    lineas.add(sub.lineno)
    return lineas


def _lineas_condicionales(arbol: ast.Module) -> Set[int]:
    """Imports bajo flags ``has_*`` (dependencia opcional ya detectada)."""
    lineas: Set[int] = set()
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.If) \
                or not isinstance(nodo.test, ast.Name) \
                or not nodo.test.id.startswith("has_"):
            continue
        for sentencia in nodo.body:
            for sub in ast.walk(sentencia):
                if isinstance(sub, (ast.Import, ast.ImportFrom)):
                    lineas.add(sub.lineno)
    return lineas


def _es_type_checking(nodo: Any) -> bool:
    return (isinstance(nodo, ast.Name) and nodo.id == "TYPE_CHECKING") \
        or (isinstance(nodo, ast.Attribute) and nodo.attr == "TYPE_CHECKING")


def _es_main(nodo: Any) -> bool:
    if not isinstance(nodo, ast.Compare) or len(nodo.ops) != 1 \
            or not isinstance(nodo.left, ast.Name) or nodo.left.id != "__name__":
        return False
    return isinstance(nodo.comparators[0], ast.Constant) \
        and nodo.comparators[0].value == "__main__"


def _lineas_no_runtime(arbol: ast.Module) -> Set[int]:
    """Imports de ``TYPE_CHECKING`` y de ``if __name__ == '__main__'``."""
    lineas: Set[int] = set()
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.If) \
                or not (_es_type_checking(nodo.test) or _es_main(nodo.test)):
            continue
        for sentencia in nodo.body:
            for sub in ast.walk(sentencia):
                if isinstance(sub, (ast.Import, ast.ImportFrom)):
                    lineas.add(sub.lineno)
    return lineas


def revisar_imports(root: Path, modulos: Dict[Path, ast.Module],
                    permitidos: Optional[Iterable[str]] = None,
                    ignorar_opcionales: bool = False) -> ResultadoGate:
    resultado = ResultadoGate("imports")
    declaradas, hallazgos_manifiesto = dependencias_declaradas(root)
    resultado.hallazgos.extend(hallazgos_manifiesto)
    stdlib = set(sys.stdlib_module_names)
    locales = modulos_locales(root)
    locales_por_directorio: Dict[Path, Set[str]] = {}
    permitidos_norm = {_normalizar(m) for m in (permitidos or ())}
    vistos: Set[Tuple[Path, str]] = set()

    for ruta, arbol in sorted(modulos.items()):
        directorio = ruta.parent
        if directorio not in locales_por_directorio:
            # `tools/a.py` puede importar `tools/helper.py` por nombre, sin
            # paquete ni manifiesto: es local por contexto, no dependencia.
            hermanos = {p.stem for p in directorio.glob("*.py")}
            hermanos |= {p.parent.name
                         for p in directorio.glob("*/__init__.py")}
            locales_por_directorio[directorio] = locales | hermanos
        locales_archivo = locales_por_directorio[directorio]
        opcionales = _lineas_no_runtime(arbol)
        if ignorar_opcionales:
            opcionales |= _lineas_import_opcional(arbol)
            opcionales |= _lineas_condicionales(arbol)
        for nodo in ast.walk(arbol):
            importados: List[Tuple[str, int]] = []
            if isinstance(nodo, ast.Import):
                importados = [(alias.name.split(".")[0], nodo.lineno)
                              for alias in nodo.names]
            elif (isinstance(nodo, ast.ImportFrom) and nodo.level == 0
                  and nodo.module):
                importados = [(nodo.module.split(".")[0], nodo.lineno)]
            for modulo, linea in importados:
                if linea in opcionales:
                    continue
                clave = (ruta, modulo)
                if clave in vistos:
                    continue
                vistos.add(clave)
                if _import_declarado(modulo, stdlib, locales_archivo,
                                     declaradas, permitidos_norm):
                    continue
                resultado.hallazgos.append(Hallazgo(
                    "imports", _relativa(root, ruta), linea,
                    f"import no declarado: {modulo}", "alta"))
    return resultado


_MARCA_SILENCIO = re.compile(
    r"#\s*noqa:\s*silent\s*:\s*(?P<motivo>.+?)\s*$")


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
        try:
            lineas = ruta.read_text(encoding="utf-8").splitlines()
        except OSError:
            lineas = []
        for nodo in ast.walk(arbol):
            if not (isinstance(nodo, ast.ExceptHandler)
                    and _cuerpo_silencioso(nodo.body)):
                continue
            texto = lineas[nodo.lineno - 1] if 0 < nodo.lineno <= len(lineas) else ""
            coincidencia = _MARCA_SILENCIO.search(texto)
            motivo = coincidencia.group("motivo").strip() if coincidencia else ""
            if len(motivo) >= 3:
                resultado.advertencias.append(Hallazgo(
                    "silencios", _relativa(root, ruta), nodo.lineno,
                    f"silencio aceptado (warning): {motivo}", "baja"))
            else:
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
    total_advertencias = sum(len(gate.advertencias) for gate in gates)
    return {
        "root": str(root),
        "archivos_python": len(archivos_python(root)),
        "gates": [gate.a_dict() for gate in gates],
        "total_hallazgos": total,
        "total_advertencias": total_advertencias,
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
              f"{len(gate['hallazgos'])} hallazgos, "
              f"{len(gate.get('advertencias', []))} warnings")
        for hallazgo in gate["hallazgos"]:
            marca = EvidenceKind(hallazgo["tipo_evidencia"]).marcador
            print(f"    {marca} {hallazgo['archivo']}:{hallazgo['linea']} "
                  f"{hallazgo['mensaje']}")
        for advertencia in gate.get("advertencias", []):
            marca = EvidenceKind(advertencia["tipo_evidencia"]).marcador
            print(f"    {marca} WARNING {advertencia['archivo']}:"
                  f"{advertencia['linea']} {advertencia['mensaje']}")
    veredicto = "OK" if informe["ok"] else "FAIL"
    print(f"PREFLIGHT: {veredicto} ({informe['total_hallazgos']} hallazgos, "
          f"{informe.get('total_advertencias', 0)} warnings)")


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
    parser.add_argument(
        "--ignorar", action="append", default=[], metavar="DIRECTORIO",
        help="directorio a excluir del análisis (repetible)")
    args = parser.parse_args(argv)

    IGNORAR.update(args.ignorar)
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
