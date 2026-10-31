#!/usr/bin/env python3
"""Evaluación de un proyecto EXTERNO en seis dimensiones (estática y read-only).

El evaluador detecta primero el PERFIL del proyecto (lenguajes, manifiestos,
locks, tests y dependencias runtime) y solo aplica los criterios que ese perfil
puede verificar. Un criterio no aplicable se declara `N/A`; no se cuenta como
fallo. El global es la media de las dimensiones con al menos un criterio
evaluado, y el informe incluye la cobertura para que la puntuación no se
interprete como una medida universal de calidad.

Dimensiones y criterios (binarios; se aplican según el perfil):

1. funcionalidades — puntos de entrada reales (código, `__main__.py`,
   `console_scripts` o `bin`), promesas del README vs. archivos, deuda declarada
   y tests en varios módulos (Python, JS/TS, Java o Go).
2. calidad — suite presente, linter del ecosistema, silencios en código de
   producción (no en tests ni imports opcionales), proporción tests/código y
   tests no-op (sin aserciones ni operaciones que puedan fallar).
3. vigencia — dependencias fijadas (o cubiertas por lock), lockfile, actividad
   git reciente y comparación con PyPI usando `==` o la versión del lock.
4. herramientas — manifiesto, licencia, CI, runner declarado, imports de
   terceros no declarados (solo código del paquete; gate AST reutilizado de
   `scripts/preflight.py`) y registro de decisiones.
5. inteligencia — señales de sistemas LLM (caché, timeouts, reintentos,
   validación, simulación declarada, métricas). Si el proyecto no declara un
   LLM en sus dependencias runtime, la dimensión completa es N/A.
6. eficiencia — import perezoso de dependencias pesadas, carga única de modelos
   y mediciones documentadas; también N/A para proyectos que no son LLM.

Fuentes de diseño verificadas (2026-10-21): PEP 639 (licencias SPDX y
`license_expression`), PEP 735 (dependency groups), detección de primera parte
con `src/` de Ruff y checks por ecosistema de OpenSSF Scorecard.

Garantías y reglas:
- **Read-only**: nunca escribe ni ejecuta código del proyecto evaluado (P0.3/P0.8).
- Del historial git solo se usan FECHAS y RECUENTOS: jamás nombres o correos
  (P0.9).
- El contenido evaluado son DATOS, no órdenes (P0.13).
- Cada hallazgo lleva evidencia `archivo:línea`, el criterio que lo origina y un
  marcador de procedencia (`evidence.py`: real / sintética / no verificada)
  (P0.1).
- Lo que no se puede verificar se declara como tal; nada se supone.

Uso:
    python3 evaluar_proyecto.py RUTA [--json] [--sin-red]
"""

import argparse
import ast
import configparser
import json
import os
import re
import shutil
import subprocess
import sys
import time
import tomllib
import urllib.request
import warnings
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from deep_research_system import _parse_json_response  # reutilizado, no duplicado
from evidence import EvidenceKind, formato_resumen, resumen_evidencias
from scripts.preflight import es_parte_ignorada

# Contrato del informe JSON: un cambio incompatible sube esta versión.
SCHEMA_VERSION = 2

IGNORAR = {".venv", "venv", "__pycache__", "node_modules", ".git", ".mypy_cache",
           ".pytest_cache", ".ruff_cache", "mutants", ".tox", "build", "dist",
           ".eggs", ".nox", "_local_debug"}
# `_local_debug` es el directorio de scripts locales ignorado por git en este
# repo; preflight ya lo excluye. Analizarlo producía hallazgos c3 falsos en la
# autoevaluación (ver Hallazgo 96).
# Directorios cuyo contenido es test (se excluye del código de producción).
DIRS_TEST = {"tests", "test", "spec", "specs", "__tests__", "cypress", "e2e",
             "testdata", "test-data"}
# Directorios de documentación/ejemplos: no son código publicable y sus imports
# no deben convertirse en hallazgos del paquete (FastAPI docs_src era el 95% de
# los falsos h6).
DIRS_NO_CODIGO = {"docs", "doc", "documentation", "examples", "example",
                  "samples", "docs_src", "benchmarks", "benchmark", "website",
                  "site", "tutorials"}
EXTENSIONES = {
    ".py": "Python", ".pyi": "Python", ".js": "JavaScript", ".jsx": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".java": "Java", ".kt": "Kotlin",
    ".go": "Go", ".rs": "Rust", ".rb": "Ruby", ".cs": "C#", ".php": "PHP",
}
MANIFIESTOS_NOMBRES = {
    "pyproject.toml", "setup.py", "setup.cfg", "pipfile", "package.json",
    "build.gradle", "build.gradle.kts", "pom.xml", "cargo.toml", "go.mod",
}
LOCKS_NOMBRES = {
    "requirements.lock", "uv.lock", "poetry.lock", "pipfile.lock", "pdm.lock",
    "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "gradle.lockfile",
    "cargo.lock", "go.sum", "packages.lock.json",
}
PESADAS = ("paddle", "torch", "tensorflow", "playwright", "openpyxl", "pandas",
           "pypdfium2", "python-docx", "docx", "transformers", "sentence-transformers",
           "vllm", "llama-cpp-python", "accelerate", "datasets")
MODELOS = ("torch", "tensorflow", "transformers", "sentence-transformers", "vllm",
           "llama-cpp-python", "accelerate", "paddle")
MARCAS_LLM = ("openai", "anthropic", "langchain", "llama-index", "llamaindex",
              "transformers", "torch", "tensorflow", "ollama", "pydantic-ai",
              "google-genai", "mistralai", "cohere", "sentence-transformers",
              "vllm", "llama-cpp-python", "huggingface-hub", "litellm")
MARCAS_WEB = ("flask", "django", "fastapi", "starlette", "aiohttp", "tornado",
              "bottle", "pyramid", "sanic", "quart")
DIMENSIONES = ("funcionalidades", "calidad", "vigencia", "herramientas",
               "inteligencia", "eficiencia")
PRIORIDAD_AMBITO = {"runtime": 0, "opcional": 1, "test": 2, "dev": 3, "docs": 4}


@dataclass
class Hallazgo:
    """Un hallazgo con su evidencia (archivo:línea o comando)."""
    severidad: str          # alta | media | baja
    descripcion: str
    evidencia: str = ""
    tipo_evidencia: EvidenceKind = EvidenceKind.VERIFIED_REAL
    criterio: str = ""       # criterio que lo origina (para no mezclar el plan)

    def a_dict(self) -> Dict[str, Any]:
        return {
            "severidad": self.severidad,
            "descripcion": self.descripcion,
            "evidencia": self.evidencia,
            "tipo_evidencia": self.tipo_evidencia.value,
            "criterio": self.criterio,
        }


@dataclass
class Dimension:
    nombre: str
    criterios: Dict[str, bool] = field(default_factory=dict)
    hallazgos: List[Hallazgo] = field(default_factory=list)
    notas: List[str] = field(default_factory=list)
    no_aplica: List[Dict[str, str]] = field(default_factory=list)

    @property
    def puntuacion(self) -> Optional[float]:
        # Sin criterios aplicables no hay puntuación: 0.0 fingiría un fallo.
        if not self.criterios:
            return None
        return round(sum(self.criterios.values()) / len(self.criterios), 3)

    def no_aplicable(self, criterio: str, motivo: str) -> None:
        self.no_aplica.append({"criterio": criterio, "motivo": motivo})

    def a_dict(self) -> Dict[str, Any]:
        return {
            "puntuacion": self.puntuacion,
            "evaluado": bool(self.criterios),
            "criterios": self.criterios,
            "no_aplica": self.no_aplica,
            "hallazgos": [h.a_dict() for h in self.hallazgos],
            "notas": self.notas,
        }


@dataclass
class Requisito:
    """Requisito declarado por el usuario y su evidencia esperada.

    El parser no adivina: los campos obligatorios ausentes son un error. Un
    requisito sin método verificable se declara `NO VERIFICABLE`, nunca se
    promociona por su redacción.
    """

    id: str
    titulo: str
    enunciado: str
    criterio: str
    origen: str
    verificacion: str = ""
    evidencia: str = ""
    tags: List[str] = field(default_factory=list)
    avisos: List[str] = field(default_factory=list)

    def a_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "titulo": self.titulo,
            "origen": self.origen,
            "enunciado": self.enunciado,
            "criterio": self.criterio,
            "verificacion": self.verificacion,
            "evidencia": self.evidencia,
            "tags": list(self.tags),
            "avisos": list(self.avisos),
        }


@dataclass
class Perfil:
    """Lo que el proyecto declara y lo que se puede analizar sin ejecutarlo."""
    ruta: Path
    py: List[Path]
    codigo_py: List[Path]
    tests_py: List[Path]
    codigo: List[Path]
    tests: List[Path]
    lenguajes: Dict[str, int]
    manifiestos: List[Path]
    locks: List[Path]
    deps: List[Dict[str, str]]
    first_party: Set[str]
    es_llm: bool
    es_web: bool
    pesadas: List[str]
    versiones_lock: Dict[str, str]

    @property
    def deps_python(self) -> List[Dict[str, str]]:
        return [d for d in self.deps if d.get("ecosistema", "python") == "python"]

    @property
    def deps_runtime_python(self) -> List[Dict[str, str]]:
        # requirements.txt de documentación en un proyecto Java/JS no son
        # dependencias runtime del proyecto. En un proyecto solo-Python (o una
        # fixture mínima con requirements) sí se evaluan.
        if not self.codigo_py and any(
                lenguaje != "Python" for lenguaje in self.lenguajes):
            return []
        return [d for d in self.deps_python if d.get("ambito") == "runtime"]

    @property
    def codigo_paquete(self) -> List[Path]:
        """Código publicable: fuera scripts de build/tooling y setup.py."""
        no_paquete = {"scripts", "script", "tooling", "extras", "bin",
                      "contrib", "benchmarks", "docs_src"}
        return [p for p in self.codigo_py
                if p.name != "setup.py"
                and not any(parte.lower() in no_paquete
                            for parte in p.relative_to(self.ruta).parts[:-1])]

    def a_dict(self) -> Dict[str, Any]:
        return {
            "lenguajes": self.lenguajes,
            "manifiestos": [p.relative_to(self.ruta).as_posix()
                            for p in self.manifiestos],
            "locks": [p.relative_to(self.ruta).as_posix() for p in self.locks],
            "dependencias": len(self.deps),
            "dependencias_python_runtime": [d["nombre"] for d in self.deps_runtime_python],
            "es_llm": self.es_llm,
            "es_web": self.es_web,
            "pesadas": self.pesadas,
        }


def archivos_python(ruta: Path) -> List[Path]:
    # Solo se ignoran directorios DENTRO del proyecto evaluado: mirar las
    # partes absolutas excluía proyectos alojados en un directorio padre
    # llamado `build`, `dist` o `venv` (0 archivos, informe vacío).
    return sorted(p for p in ruta.rglob("*.py")
                  if not any(es_parte_ignorada(parte, IGNORAR)
                             for parte in p.relative_to(ruta).parts))


def leer(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _es_test(ruta: Path, archivo: Path) -> bool:
    rel = archivo.relative_to(ruta)
    partes = [parte.lower() for parte in rel.parts[:-1]]
    nombre = archivo.name.lower()
    if any(parte in DIRS_TEST for parte in partes):
        return True
    if nombre.startswith("test_") or nombre.endswith("_test.py"):
        return True
    if ".test." in nombre or ".spec." in nombre or ".cy." in nombre:
        return True
    if nombre.endswith("_test.go"):
        return True
    return "src/test/" in rel.as_posix().lower()


def _es_no_codigo(ruta: Path, archivo: Path) -> bool:
    partes = [parte.lower() for parte in archivo.relative_to(ruta).parts[:-1]]
    return any(parte in DIRS_NO_CODIGO for parte in partes)


def _es_manifiesto(archivo: Path) -> bool:
    nombre = archivo.name.lower()
    if nombre in MANIFIESTOS_NOMBRES:
        return True
    if nombre.endswith(".lock"):
        return False
    if re.match(r"requirements.*\.(txt|in)$", nombre):
        return True
    # pip-compile también usa requirements/tools.txt, requirements/test.in...
    return archivo.parent.name.lower() == "requirements" \
        and archivo.suffix.lower() in (".txt", ".in")


def _es_lock(archivo: Path) -> bool:
    if archivo.name.lower() in LOCKS_NOMBRES:
        return True
    # pip-compile deja el lock resuelto en requirements/*.txt. Los .in son
    # entradas sin resolver y no cuentan como lock. Un requirements/*.txt con
    # líneas sin fijar (`requests>=2.0`) TAMPOCO es un lock: tratarlo como tal
    # afirmaba reproducibilidad falsa (P0.1). Solo cuenta si la mayoría de sus
    # líneas de requisitos están fijadas (`==` o `--hash=`).
    if archivo.parent.name.lower() != "requirements" \
            or archivo.suffix.lower() != ".txt" \
            or archivo.name.lower().endswith(".in"):
        return False
    requisitos = [linea for linea in
                  (ln.split("#", 1)[0].strip() for ln in leer(archivo).splitlines())
                  if linea and not linea.startswith("-")]
    if not requisitos:
        return False
    fijadas = sum(1 for linea in requisitos if "==" in linea or "--hash=" in linea)
    return fijadas * 2 > len(requisitos)


def _modulos_propios(ruta: Path, py: List[Path]) -> Set[str]:
    """Nombres de primera parte, incluyendo layout ``src/`` y subpaquetes."""
    nombres = {p.stem for p in ruta.glob("*.py")}
    for base in (ruta, ruta / "src"):
        if not base.is_dir():
            continue
        for directorio in base.iterdir():
            if not directorio.is_dir() or directorio.name in IGNORAR:
                continue
            if (directorio / "__init__.py").exists() \
                    or any(directorio.glob("*.py")):
                nombres.add(directorio.name)
    for archivo in py:
        actual, ultimo = archivo.parent, None
        while actual != ruta and (actual / "__init__.py").exists():
            ultimo, actual = actual, actual.parent
        if ultimo is not None:
            nombres.add(ultimo.name)
    return nombres


def _detectar_llm(deps: List[Dict[str, str]]) -> bool:
    runtime = {d["nombre"].lower() for d in deps
               if d.get("ecosistema", "python") == "python"
               and d.get("ambito") == "runtime"}
    return any(marca in runtime or any(marca in nombre for nombre in runtime)
               for marca in MARCAS_LLM)


def _detectar_web(deps: List[Dict[str, str]]) -> bool:
    runtime = {d["nombre"].lower() for d in deps
               if d.get("ambito") == "runtime"}
    return any(marca == nombre for nombre in runtime for marca in MARCAS_WEB)


def analizar_perfil(ruta: Path) -> Perfil:
    """Perfil determinista y read-only del proyecto (sin ejecutar su código)."""
    py = archivos_python(ruta)
    lenguajes: Counter = Counter()
    codigo, tests = [], []
    for archivo in ruta.rglob("*"):
        if not archivo.is_file():
            continue
        if any(es_parte_ignorada(parte, IGNORAR) for parte in archivo.relative_to(ruta).parts):
            continue
        lenguaje = EXTENSIONES.get(archivo.suffix.lower())
        if not lenguaje or _es_no_codigo(ruta, archivo):
            continue
        lenguajes[lenguaje] += 1
        (tests if _es_test(ruta, archivo) else codigo).append(archivo)
    manifiestos = sorted(p for p in ruta.rglob("*")
                         if p.is_file() and _es_manifiesto(p)
                         and not any(es_parte_ignorada(parte, IGNORAR)
                                     for parte in p.relative_to(ruta).parts))
    locks = sorted(p for p in ruta.rglob("*")
                   if p.is_file() and _es_lock(p)
                   and not _es_no_codigo(ruta, p)
                   and not any(es_parte_ignorada(parte, IGNORAR)
                               for parte in p.relative_to(ruta).parts))
    deps = _dependencias(ruta)
    pesadas = sorted({d["nombre"] for d in deps
                      if any(marca in d["nombre"] for marca in PESADAS)})
    return Perfil(
        ruta=ruta, py=py,
        codigo_py=[p for p in codigo if p.suffix == ".py"],
        tests_py=[p for p in tests if p.suffix == ".py"],
        codigo=sorted(codigo), tests=sorted(tests),
        lenguajes=dict(sorted(lenguajes.items())),
        manifiestos=manifiestos, locks=locks, deps=deps,
        first_party=_modulos_propios(ruta, py),
        es_llm=_detectar_llm(deps) and bool(py),
        es_web=_detectar_web(deps) and bool(py),
        pesadas=pesadas, versiones_lock=_versiones_lock(ruta),
    )


def _nombre_excepcion(nodo) -> str:
    if isinstance(nodo, ast.Name):
        return nodo.id
    if isinstance(nodo, ast.Tuple):
        return ",".join(_nombre_excepcion(item) for item in nodo.elts)
    return ""


def _cuerpo_silencio(cuerpo: List[ast.stmt]) -> bool:
    return bool(cuerpo) and all(
        isinstance(nodo, (ast.Pass, ast.Continue, ast.Break))
        or (isinstance(nodo, ast.Expr) and isinstance(nodo.value, ast.Constant)
            and nodo.value.value is Ellipsis)
        for nodo in cuerpo)


def _try_contiene_imports(nodo: ast.Try) -> bool:
    """True si el ``try`` intenta importar algo (posible dependencia opcional)."""
    return any(isinstance(sub, (ast.Import, ast.ImportFrom))
               for item in nodo.body for sub in ast.walk(item))


def lineas_silenciosas(arbol: ast.AST) -> List[int]:
    """Líneas de ``except`` que silencian, con dos exclusiones honestas.

    - Los tests no se analizan en c3 (el llamador filtra): silenciar allí suele
      ser deliberado.
    - Un ``try: import x except ImportError: pass`` es un import OPCIONAL, no
      un error tragado: se excluye. El resto de ``except: pass/continue`` sigue
      siendo un hallazgo (P1.26).

    Recibe el árbol ya parseado: el único llamador (c3) parsea cada archivo
    una vez para su check de sintaxis y reutiliza ese árbol (los archivos con
    ``SyntaxError`` se declaran aparte y no llegan aquí).
    """
    padres = {hijo: padre for padre in ast.walk(arbol)
              for hijo in ast.iter_child_nodes(padre)}
    sospechosas = []
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.ExceptHandler) or not _cuerpo_silencio(nodo.body):
            continue
        padre = padres.get(nodo)
        if isinstance(padre, ast.Try) and _try_contiene_imports(padre) \
                and any(nombre in ("ImportError", "ModuleNotFoundError")
                        for nombre in _nombre_excepcion(nodo.type).split(",")):
            continue
        sospechosas.append(nodo.lineno)
    return sospechosas


_MARCA_SILENCIO = re.compile(
    r"#\s*noqa:\s*silent\s*:\s*(?P<motivo>.+?)\s*$")


def clasificar_silencios(arbol: ast.AST,
                         fuente: str) -> Tuple[List[int], List[Tuple[int, str]]]:
    """Separa silencios no marcados de los aceptados con motivo (R6).

    La marca `# noqa: silent: motivo` solo vale en la línea del ``except`` y
    exige un motivo de al menos 3 caracteres. Los aceptados se reportan como
    warnings; nunca desaparecen del informe.
    """
    lineas = fuente.splitlines()
    silencios, aceptados = [], []
    for numero in lineas_silenciosas(arbol):
        texto = lineas[numero - 1] if 0 < numero <= len(lineas) else ""
        coincidencia = _MARCA_SILENCIO.search(texto)
        motivo = coincidencia.group("motivo").strip() if coincidencia else ""
        if len(motivo) >= 3:
            aceptados.append((numero, motivo))
        else:
            silencios.append(numero)
    return silencios, aceptados


def _tiene_asercion(funcion) -> bool:
    """True si la función contiene una aserción real (assert, self.assert*,
    pytest.raises/warns). Las aserciones dentro de `with pytest.raises(...)`
    cuentan: el `Call` a `raises` está en el árbol de la función."""
    for nodo in ast.walk(funcion):
        if isinstance(nodo, ast.Assert):
            return True
        if isinstance(nodo, ast.Call):
            func = nodo.func
            nombre = func.attr if isinstance(func, ast.Attribute) \
                else getattr(func, "id", "")
            if nombre.startswith("assert") or nombre in ("raises", "warns"):
                return True
    return False


# Llamadas puras que no pueden fallar con argumentos literales. Un test que
# solo imprime 1+1 sigue siendo no-op; una llamada a un helper sí puede fallar.
_LLAMADAS_PURAS = {"print", "len", "str", "int", "float", "bool", "list",
                   "dict", "set", "tuple", "range", "enumerate", "zip",
                   "sorted", "sum", "min", "max", "abs", "repr", "isinstance",
                   "issubclass", "round", "format"}


def _puede_fallar(funcion) -> bool:
    """True si el test hace algo observable que puede lanzar/fallar.

    Es deliberadamente CONSERVADOR: ante la duda, no se marca el test. Así se
    eliminan los falsos positivos de tests que delegan en helpers, usan
    fixtures/context managers, comprueban excepciones sin ``assert`` o son
    property tests con ``@given``/``@example``.
    """
    if getattr(funcion, "decorator_list", []):
        return True
    for nodo in ast.walk(funcion):
        if isinstance(nodo, ast.Call):
            if isinstance(nodo.func, ast.Name) and nodo.func.id in _LLAMADAS_PURAS:
                continue
            return True
        if isinstance(nodo, (ast.Attribute, ast.Subscript, ast.Await, ast.With,
                             ast.AsyncWith, ast.Raise, ast.Yield, ast.YieldFrom)):
            return True
    return False


def _funciones_test(arbol: ast.Module):
    """Tests de nivel de módulo y métodos de clases Test*, sin anidar helpers.

    Devuelve ``(función, clase)``; la clase permite saber si el test depende de
    ``setUp`` (que puede fallar aunque el cuerpo del test esté vacío).
    """
    for nodo in arbol.body:
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and nodo.name.startswith("test"):
            yield nodo, None
        elif isinstance(nodo, ast.ClassDef):
            bases = {getattr(base, "id", getattr(base, "attr", ""))
                     for base in nodo.bases}
            if not (nodo.name.startswith("Test") or "TestCase" in bases):
                continue
            for hijo in nodo.body:
                if isinstance(hijo, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                        and hijo.name.startswith("test"):
                    yield hijo, nodo


def tests_sin_aserciones(ruta: Path,
                         modulos_test: List[Path]) -> Tuple[List[str], List[str]]:
    """Tests no-op: sin aserción NI operación que pueda fallar.

    Un test que solo hace ``pass`` o ``print(1+1)`` no puede fallar y no es un
    test (regla propia 4). Un test que llama a un helper, usa un fixture o
    espera una excepción SÍ puede fallar: no se marca. Devuelve también los
    archivos que no parsean para declararlo (P1.26).
    """
    debiles, con_error = [], []
    for p in modulos_test:
        try:
            arbol = ast.parse(leer(p), filename=str(p))
        except SyntaxError as exc:
            con_error.append(f"{p.relative_to(ruta).as_posix()}:{exc.lineno or 0}")
            continue
        for nodo, clase in _funciones_test(arbol):
            depende_de_setup = clase is not None and any(
                isinstance(hijo, (ast.FunctionDef, ast.AsyncFunctionDef))
                and hijo.name in ("setUp", "setUpClass", "asyncSetUp")
                for hijo in clase.body)
            if not depende_de_setup and not _tiene_asercion(nodo) \
                    and not _puede_fallar(nodo):
                debiles.append(f"{p.relative_to(ruta).as_posix()}:{nodo.lineno}")
    return debiles, con_error


def _constante_verdadera(nodo) -> bool:
    """True si el nodo es una constante Python con valor verdadero."""
    return isinstance(nodo, ast.Constant) and bool(nodo.value)


def _comparacion_constante_verdadera(compare) -> bool:
    """True si una comparación de constantes es una tautología que pasa."""
    if len(compare.ops) != 1:
        return False
    try:
        izquierda = ast.literal_eval(compare.left)
        derecha = ast.literal_eval(compare.comparators[0])
    except (ValueError, TypeError):
        return False
    op = compare.ops[0]
    if isinstance(op, ast.Eq):
        return izquierda == derecha
    if isinstance(op, ast.NotEq):
        return izquierda != derecha
    if isinstance(op, ast.Lt):
        return izquierda < derecha
    if isinstance(op, ast.LtE):
        return izquierda <= derecha
    if isinstance(op, ast.Gt):
        return izquierda > derecha
    if isinstance(op, ast.GtE):
        return izquierda >= derecha
    return False


def _llamada_aserion_debil(nodo) -> bool:
    """True para ``assertTrue(True)``, ``assertEqual(1, 1)`` y similares."""
    if not isinstance(nodo, ast.Call) or not nodo.args:
        return False
    funcion = nodo.func
    nombre = funcion.attr if isinstance(funcion, ast.Attribute) \
        else getattr(funcion, "id", "")
    primero = nodo.args[0]
    if nombre in ("assertTrue", "assertFalse") \
            and isinstance(primero, ast.Constant):
        return bool(primero.value) if nombre == "assertTrue" \
            else not bool(primero.value)
    if nombre == "assertEqual" and len(nodo.args) >= 2 \
            and all(isinstance(arg, ast.Constant) for arg in nodo.args[:2]):
        return nodo.args[0].value == nodo.args[1].value
    if nombre == "assertIsNone" and isinstance(primero, ast.Constant):
        return primero.value is None
    if nombre == "assertIsNotNone" and isinstance(primero, ast.Constant):
        return primero.value is not None
    return False


def _nodo_aserion_debil(nodo) -> bool:
    if isinstance(nodo, ast.Assert):
        if _constante_verdadera(nodo.test):
            return True
        return isinstance(nodo.test, ast.Compare) \
            and _comparacion_constante_verdadera(nodo.test)
    return _llamada_aserion_debil(nodo)


def aserciones_debiles(ruta: Path,
                       modulos_test: List[Path]) -> Tuple[List[str], List[str]]:
    """Aserciones que no pueden fallar por construcción (R7).

    Señal informativa, separada de c5 (que mide tests no-op). Es conservadora:
    solo marca constantes verdaderas, comparaciones de constantes que pasan y
    ``assertTrue/assertFalse/assertEqual`` con literales. No marca variables,
    helpers ni property tests. Devuelve también los archivos con error de
    sintaxis para declararlos.
    """
    marcas, con_error = [], []
    for p in modulos_test:
        try:
            arbol = ast.parse(leer(p), filename=str(p))
        except SyntaxError as exc:
            con_error.append(f"{p.relative_to(ruta).as_posix()}:{exc.lineno or 0}")
            continue
        for nodo, _ in _funciones_test(arbol):
            for hijo in ast.walk(nodo):
                if _nodo_aserion_debil(hijo):
                    marcas.append(f"{p.relative_to(ruta).as_posix()}:{hijo.lineno}")
                    break
    return marcas, con_error


def _git(ruta: Path, *args: str) -> Optional[str]:
    """Ejecuta git SOLO con argumentos de fecha/recuento (nunca autores)."""
    try:
        salida = subprocess.run(["git", "-C", str(ruta), *args],
                                capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return salida.stdout.strip() if salida.returncode == 0 else None


# --- Dimensiones -----------------------------------------------------------

def _tiene_punto_entrada(ruta: Path, perfil: Perfil) -> List[str]:
    """Puntos de entrada reales, sin ejecutar: código, scripts o bin."""
    encontrados = []
    for p in perfil.codigo_py:
        texto = leer(p)
        if p.name == "__main__.py" or re.search(
                r"if\s+__name__\s*==\s*['\"]__main__['\"]", texto):
            encontrados.append(p.relative_to(ruta).as_posix())
    for p in perfil.codigo:
        texto = leer(p)
        if p.suffix == ".java" and re.search(r"static\s+void\s+main\s*\(", texto):
            encontrados.append(p.relative_to(ruta).as_posix())
        elif p.suffix == ".go" and re.search(r"(?m)^func\s+main\s*\(", texto):
            encontrados.append(p.relative_to(ruta).as_posix())
    for p in perfil.manifiestos:
        texto = leer(p)
        nombre = p.name.lower()
        if nombre == "pyproject.toml" and re.search(
                r"(?m)^\[(?:project|tool\.poetry)\.scripts\]", texto):
            encontrados.append(f"{p.relative_to(ruta)} ([project.scripts])")
        elif nombre == "setup.cfg" and "console_scripts" in texto:
            encontrados.append(f"{p.relative_to(ruta)} (console_scripts)")
        elif nombre == "package.json":
            try:
                datos = json.loads(texto)
            except json.JSONDecodeError as exc:
                warnings.warn(f"{p}: JSON inválido ({exc}); no se inspecciona",
                              RuntimeWarning, stacklevel=2)
                continue
            if datos.get("bin") or datos.get("main"):
                encontrados.append(f"{p.relative_to(ruta)} (bin/main)")
    return sorted(set(encontrados))


def evaluar_funcionalidades(ruta: Path, perfil: Perfil) -> Dimension:
    dim = Dimension("funcionalidades")
    entradas = _tiene_punto_entrada(ruta, perfil)
    if perfil.codigo and entradas:
        dim.criterios["f1_puntos_de_entrada"] = True
        dim.notas.append(f"{len(entradas)} puntos de entrada: "
                         + ", ".join(entradas[:5]))
    elif perfil.codigo:
        # Una biblioteca sin CLI no incumple f1: el criterio solo se evalúa si
        # el proyecto declara o contiene un punto de entrada.
        dim.no_aplicable("f1_puntos_de_entrada",
                         "sin CLI/entrypoint declarado (proyecto tipo biblioteca)")
    else:
        dim.no_aplicable("f1_puntos_de_entrada", "sin archivos de código")

    readme = next((ruta / nombre for nombre in
                   ("README.md", "README.rst", "README.txt")
                   if (ruta / nombre).exists()), None)
    if perfil.codigo_py:
        existentes = set()
        for p in perfil.py:
            existentes.add(p.name)
            existentes.add(p.relative_to(ruta).as_posix())
        prometidos = set(re.findall(r"`([A-Za-z0-9_./-]+\.py)`",
                                    leer(readme))) if readme else set()
        faltan = sorted(n for n in prometidos
                        if n not in existentes
                        and not any(e.endswith("/" + n) for e in existentes))
        dim.criterios["f2_readme_vs_realidad"] = bool(readme) and not faltan
        if not readme:
            dim.hallazgos.append(Hallazgo(
                "media", "Sin README.md/.rst/.txt", str(ruta),
                criterio="f2_readme_vs_realidad"))
        for nombre in faltan:
            dim.hallazgos.append(Hallazgo(
                "alta", f"El README promete {nombre} y no existe",
                "README.md", criterio="f2_readme_vs_realidad"))
    else:
        dim.no_aplicable("f2_readme_vs_realidad",
                         "sin código Python: no hay referencias .py que contrastar")

    if perfil.codigo_py:
        deuda = []
        for p in perfil.codigo_py:
            for i, linea in enumerate(leer(p).splitlines(), 1):
                if "#" not in linea:
                    continue
                comentario = linea.split("#", 1)[1]
                # "TODO REAL" es el nombre de una regla de dominio en algunos
                # proyectos (no una marca de deuda): se excluye.
                if re.search(r"\b(TODO|FIXME|XXX)\b", comentario) \
                        and "TODO REAL" not in comentario:
                    deuda.append(f"{p.relative_to(ruta)}:{i}")
        dim.criterios["f3_sin_deuda_declarada"] = not deuda
        if deuda:
            dim.hallazgos.append(Hallazgo(
                "baja", f"{len(deuda)} marcas TODO/FIXME/XXX en código de "
                        "producción", ", ".join(deuda[:5]),
                criterio="f3_sin_deuda_declarada"))
    else:
        dim.no_aplicable("f3_sin_deuda_declarada",
                         "sin código Python analizable")

    if perfil.codigo:
        dim.criterios["f4_tests_de_varios_modulos"] = len(perfil.tests) > 1
        dim.notas.append(f"{len(perfil.tests)} archivos de test "
                         f"({', '.join(sorted({p.suffix for p in perfil.tests})) or 'sin tests'})")
        if len(perfil.tests) <= 1:
            dim.hallazgos.append(Hallazgo(
                "baja", f"Solo {len(perfil.tests)} archivo(s) de test: la "
                        "cobertura por módulos no se puede distribuir",
                "código del proyecto", criterio="f4_tests_de_varios_modulos"))
    else:
        dim.no_aplicable("f4_tests_de_varios_modulos", "sin código")
    return dim


def detectar_comando_tests(ruta: Path) -> Optional[Dict[str, Any]]:
    """Comando de tests DECLARADO por el proyecto (nunca adivinado).

    Cubre los ecosistemas que el perfil puede detectar y registra el origen.
    Un ``package.json`` con el script de error de npm no se considera runner.
    """
    makefile = ruta / "Makefile"
    if makefile.exists() and re.search(r"^test:", leer(makefile), re.M) \
            and shutil.which("make"):
        return {"comando": ["make", "test"], "origen": "Makefile (target test)"}
    # Sin `make` disponible (p. ej. Windows), se sigue buscando el runner
    # Python declarado o la convención de tests/ en vez de fallar con
    # FileNotFoundError.

    # La coincidencia se ancla al inicio del comando (inicio de línea o tras
    # backtick, con `\b` implícito en cada token) y la captura se limita a
    # tokens del comando: sin ese ancla, "django test runner" producía el
    # comando basura ['go', 'test', 'runner', 'o', 'detox.'] y "detox en iOS"
    # producía ['tox', 'en', 'iOS.'].
    token = r"[\w./:=+@*-]+"
    patrones = (
        rf"(python3? -m (?:unittest|pytest)(?:\s+{token})*)",
        rf"(pytest(?:\s+{token})*)",
        rf"(npm (?:run )?test(?:\s+{token})*)",
        rf"((?:\./)?gradlew? test(?:\s+{token})*)",
        rf"(mvn(?:w)? test(?:\s+{token})*)",
        rf"(go test(?:\s+{token})*)",
        rf"(cargo test(?:\s+{token})*)",
        rf"(tox(?:\s+{token})*)",
    )
    for candidato in list((ruta / "scripts").glob("*.sh")) + [
            ruta / "README.md", ruta / "AGENTS.md", ruta / "README.rst"]:
        if not candidato.exists():
            continue
        texto = leer(candidato)
        for patron in patrones:
            m = re.search(r"(?:^|(?<=`))[ \t]*" + patron, texto, re.M)
            if m:
                comando = m.group(1).split()
                if comando[0] in ("python", "python3"):
                    # Usar el intérprete que ejecuta el evaluador evita
                    # depender de un `python3` ausente o roto en Windows.
                    comando[0] = sys.executable
                return {"comando": comando,
                        "origen": f"{candidato.relative_to(ruta)}"}

    paquete = ruta / "package.json"
    if paquete.exists():
        try:
            datos = json.loads(leer(paquete))
        except json.JSONDecodeError:
            datos = {}
        script = str((datos.get("scripts") or {}).get("test", "")).strip()
        if script and "no test specified" not in script.lower() \
                and not script.lower().startswith("echo"):
            return {"comando": ["npm", "test"],
                    "origen": "package.json (scripts.test)"}

    if (ruta / "gradlew").exists() and any(
            (ruta / nombre).exists()
            for nombre in ("build.gradle", "build.gradle.kts")):
        return {"comando": ["./gradlew", "test"], "origen": "gradlew + build.gradle"}
    if (ruta / "pom.xml").exists():
        return {"comando": ["mvn", "test"], "origen": "pom.xml"}
    if (ruta / "go.mod").exists():
        return {"comando": ["go", "test", "./..."], "origen": "go.mod"}
    if (ruta / "Cargo.toml").exists():
        return {"comando": ["cargo", "test"], "origen": "Cargo.toml"}
    if (ruta / "tox.ini").exists():
        return {"comando": ["tox"], "origen": "tox.ini"}
    if (ruta / "noxfile.py").exists():
        return {"comando": ["nox"], "origen": "noxfile.py"}

    if (ruta / "tests").is_dir() and any((ruta / "tests").glob("test_*.py")):
        return {"comando": [sys.executable, "-m", "unittest", "discover",
                            "-s", "tests"],
                "origen": "convención: existe tests/"}
    return None


def _linter_configurado(perfil: Perfil) -> Tuple[bool, str]:
    """Linter del ecosistema, con el archivo que lo declara."""
    textos = {p: leer(p) for p in perfil.manifiestos}
    for p, texto in textos.items():
        nombre = p.name.lower()
        if nombre == "pyproject.toml" and re.search(
                r"(?m)^\[tool\.(ruff|flake8|pylint|pydocstyle)", texto):
            return True, p.relative_to(perfil.ruta).as_posix()
        if nombre in ("setup.cfg", ".flake8", ".pylintrc") and re.search(
                r"ruff|flake8|pylint", texto):
            return True, p.relative_to(perfil.ruta).as_posix()
        if nombre == "package.json" and re.search(
                r'"(?:eslint|biome|prettier)"', texto):
            return True, p.relative_to(perfil.ruta).as_posix()
        if nombre in ("build.gradle", "build.gradle.kts", "pom.xml") and re.search(
                r"checkstyle|spotless|pmd|spotbugs|eslint", texto, re.I):
            return True, p.relative_to(perfil.ruta).as_posix()
    for patron in (".ruff.toml", "ruff.toml", ".eslintrc*", "eslint.config.*",
                   ".flake8", ".pylintrc"):
        for p in perfil.ruta.glob(patron):
            return True, p.relative_to(perfil.ruta).as_posix()
    return False, ""


def _preexec_limites(cpu_segundos: Optional[int]):
    """Devuelve un preexec_fn POSIX que acota la CPU del proceso evaluado.

    En Windows devuelve None (no hay `resource`; el `timeout` de subprocess
    sigue acotando el tiempo total). Declarado en `ejecutar_tests`.
    """
    if os.name != "posix":
        return None
    try:
        import resource
    except ImportError:  # pragma: no cover - POSIX sin resource no existe
        return None

    def _aplicar():
        if cpu_segundos is not None:
            resource.setrlimit(resource.RLIMIT_CPU,
                               (cpu_segundos, cpu_segundos))

    return _aplicar


def ejecutar_tests(ruta: Path, timeout: int = 900,
                   limite_cpu_s: Optional[int] = None) -> Dict[str, Any]:
    """Ejecuta el comando de tests declarado (opt-in explícito, P0.8).

    Es lo ÚNICO que ejecuta código del proyecto evaluado y solo se hace con
    `--ejecutar-tests`. Sin shell (`shell=False`), con timeout y salida
    capturada. En POSIX se añade además un límite de CPU al subproceso
    (`limite_cpu_s`, por defecto `timeout + 60`): el timeout acota el tiempo
    de pared, pero un proceso que ignore la señal de terminación sigue
    consumiendo CPU hasta el kill. No hay límite de memoria por defecto:
    `RLIMIT_AS` rompería suites legítimas que mapean bibliotecas grandes.
    """
    deteccion = detectar_comando_tests(ruta)
    if deteccion is None:
        return {"ejecutado": False,
                "motivo": "no se encontró un comando de tests declarado"}
    if limite_cpu_s is None:
        limite_cpu_s = timeout + 60

    inicio = time.monotonic()
    try:
        proceso = subprocess.run(deteccion["comando"], cwd=str(ruta),
                                 capture_output=True, text=True, timeout=timeout,
                                 shell=False,
                                 preexec_fn=_preexec_limites(limite_cpu_s))
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ejecutado": True, "comando": " ".join(deteccion["comando"]),
                "origen": deteccion["origen"], "error": type(exc).__name__,
                "detalle": str(exc)[:200]}
    duracion = round(time.monotonic() - inicio, 1)
    salida = (proceso.stdout or "") + (proceso.stderr or "")
    resumen = re.search(r"^Ran (\d+) tests?", salida, re.M)
    return {
        "ejecutado": True,
        "comando": " ".join(deteccion["comando"]),
        "origen": deteccion["origen"],
        "codigo": proceso.returncode,
        "ok": proceso.returncode == 0,
        "tests": int(resumen.group(1)) if resumen else None,
        "resumen": next((linea for linea in reversed(salida.splitlines())
                         if linea.startswith(("OK", "FAILED"))), ""),
        "duracion_s": duracion,
    }


def evaluar_calidad(ruta: Path, perfil: Perfil,
                    ejecutar: bool = False,
                    resultado_tests: Optional[Dict[str, Any]] = None) -> Dimension:
    dim = Dimension("calidad")
    lineas_codigo = sum(len(leer(p).splitlines()) for p in perfil.codigo)
    lineas_test = sum(len(leer(p).splitlines()) for p in perfil.tests)
    dim.notas.append(f"{lineas_test} líneas de test / {lineas_codigo} de código")

    if perfil.codigo:
        dim.criterios["c1_suite_de_tests"] = bool(perfil.tests)
        if not perfil.tests:
            dim.hallazgos.append(Hallazgo(
                "alta", "Sin suite de tests: los cambios no tienen red de "
                        "seguridad", "código del proyecto",
                criterio="c1_suite_de_tests"))
    else:
        dim.no_aplicable("c1_suite_de_tests", "sin código")

    if ejecutar:
        resultado = (resultado_tests if resultado_tests is not None
                     else ejecutar_tests(ruta))
        if not resultado.get("ejecutado") or resultado.get("error"):
            motivo = resultado.get("motivo") or (
                f"{resultado.get('error')}: {resultado.get('detalle', '')}")
            dim.notas.append(f"suite NO ejecutada: {motivo} "
                             f"({resultado.get('comando', 'sin comando')})")
            dim.no_aplicable("c1b_suite_pasa", "runner no disponible")
        else:
            resumen = resultado.get("resumen") or (
                f"código de salida {resultado.get('codigo', '?')}")
            dim.notas.append(f"suite: {resumen}"
                             f" ({resultado.get('comando', 'sin comando')}, "
                             f"{resultado.get('duracion_s', '?')}s)")
            dim.criterios["c1b_suite_pasa"] = bool(resultado.get("ok"))
            if not resultado.get("ok"):
                dim.hallazgos.append(Hallazgo(
                    "alta", f"La suite NO pasa: {resumen}",
                    resultado.get("comando", "?"), criterio="c1b_suite_pasa"))
    else:
        dim.notas.append("suite NO ejecutada (sin --ejecutar-tests): no verificado")

    if perfil.codigo:
        linter, fuente = _linter_configurado(perfil)
        dim.criterios["c2_linter_configurado"] = linter
        if linter:
            dim.notas.append(f"linter: {fuente}")
        else:
            dim.hallazgos.append(Hallazgo(
                "media", "Sin linter configurado (ruff/flake8/pylint, eslint, "
                        "checkstyle/spotless)", "manifiestos/raíz",
                criterio="c2_linter_configurado"))
    else:
        dim.no_aplicable("c2_linter_configurado", "sin código")

    if perfil.codigo_paquete:
        silencios = []
        aceptados = []
        con_error = []
        for p in perfil.codigo_paquete:
            fuente = leer(p)
            try:
                arbol = ast.parse(fuente, filename=str(p))
            except SyntaxError as exc:
                con_error.append(f"{p.relative_to(ruta).as_posix()}:"
                                 f"{exc.lineno or 0}")
                continue
            relativa = p.relative_to(ruta).as_posix()
            no_marcados, marcados = clasificar_silencios(arbol, fuente)
            for linea in no_marcados:
                silencios.append(f"{relativa}:{linea}")
            for linea, motivo in marcados:
                aceptados.append((f"{relativa}:{linea}", motivo))
        dim.criterios["c3_sin_silencios"] = not silencios
        dim.notas.append(f"c3 sobre {len(perfil.codigo_paquete)} archivos de "
                         "producción; tests/scripts excluidos")
        if silencios:
            dim.notas.append(f"silencios detectados: {len(silencios)}")
        if aceptados:
            dim.notas.append(f"silencios aceptados (warning): {len(aceptados)}")
        if con_error:
            dim.notas.append("código con error de sintaxis (no evaluable en c3): "
                             + ", ".join(con_error))
        for marca in silencios:
            dim.hallazgos.append(Hallazgo(
                "media", "`except` con `pass`/`continue` en producción (P1.26)",
                marca, criterio="c3_sin_silencios"))
        for marca, motivo in aceptados:
            dim.hallazgos.append(Hallazgo(
                "baja", f"Silencio aceptado (warning): {motivo}", marca,
                criterio="c3_sin_silencios"))
    else:
        dim.no_aplicable("c3_sin_silencios", "sin código Python de producción")

    if perfil.codigo and lineas_codigo:
        proporcion = lineas_test / lineas_codigo
        dim.criterios["c4_tests_sobre_codigo_30pct"] = proporcion >= 0.3
        dim.notas.append(f"proporción test/código: {proporcion:.2f}")
        if proporcion < 0.3:
            dim.hallazgos.append(Hallazgo(
                "media", f"Proporción test/código {proporcion:.2f} < 0.30",
                "código y tests", criterio="c4_tests_sobre_codigo_30pct"))
    else:
        dim.no_aplicable("c4_tests_sobre_codigo_30pct", "sin código medible")

    if perfil.tests_py:
        debiles, con_error = tests_sin_aserciones(ruta, perfil.tests_py)
        dim.criterios["c5_tests_con_aserciones"] = not debiles
        dim.notas.append(f"c5 sobre {len(perfil.tests_py)} archivos de test Python")
        if debiles:
            dim.notas.append(f"tests no-op: {len(debiles)}")
        if con_error:
            dim.notas.append("tests con error de sintaxis (no evaluables en c5): "
                             + ", ".join(con_error))
        for marca in debiles:
            dim.hallazgos.append(Hallazgo(
                "media", "Test no-op: sin aserciones ni operaciones que puedan "
                         "fallar (regla propia 4)", marca,
                criterio="c5_tests_con_aserciones"))
    else:
        dim.no_aplicable("c5_tests_con_aserciones",
                         "sin archivos de test Python analizables")
    return dim


_REQUISITO = re.compile(
    r"^(?P<nombre>[A-Za-z0-9][A-Za-z0-9._-]*)"
    r"(?:\[[^\]]*\])?"
    r"\s*(?P<operador>===|==|~=|!=|<=|>=|<|>)?"
    r"\s*(?P<version>[0-9][^\s,;]*)?")


def _clave_nombre(nombre: str) -> str:
    """Clave PEP 503: mayúsculas, ``_`` y ``.`` equivalen a ``-``."""
    return re.sub(r"[-_.]+", "-", nombre.strip().lower())


def _parsear_requisito(linea: str, origen: str = "",
                       ambito: str = "runtime",
                       ecosistema: str = "python") -> Optional[Dict[str, str]]:
    """Dependencia PEP 508 de una línea; ``None`` si no es un paquete PyPI.

    Las directivas de pip (``-r``, ``-e``, ``--index-url``, ``--hash``), las
    URLs, las rutas y las referencias directas (``pkg @ url``) NO son paquetes
    con versión: tratarlas como tales inventaba dependencias llamadas ``-r`` o
    ``--index-url`` y hacía fallar la vigencia y las licencias.
    """
    linea = linea.split("#", 1)[0].strip()
    if not linea:
        return None
    if linea.startswith("-") or "@" in linea:
        return None
    if re.match(r"(?i)^(?:https?://|git\+|file:|\.{0,2}/|~/)", linea):
        return None
    if linea.lower().endswith((".whl", ".tar.gz", ".zip")):
        return None
    coincidencia = _REQUISITO.match(linea)
    if coincidencia is None:
        return None
    operador = coincidencia.group("operador") or ""
    version = coincidencia.group("version") or ""
    return {"nombre": coincidencia.group("nombre").lower(),
            "operador": operador, "version": version,
            "origen": origen, "ambito": ambito,
            "ecosistema": ecosistema,
            "fijada": operador == "==" and bool(version)}


def _ambito_requirements(archivo: Path, ruta: Path) -> str:
    nombre = archivo.name.lower()
    try:
        partes = [parte.lower() for parte in archivo.relative_to(ruta).parts[:-1]]
    except ValueError:
        partes = []
    if any(parte in DIRS_NO_CODIGO for parte in partes):
        return "docs"
    if any(parte in DIRS_TEST for parte in partes):
        return "test"
    if any(marca in nombre for marca in ("doc", "sphinx", "mkdocs")):
        return "docs"
    if "test" in nombre:
        return "test"
    if any(marca in nombre for marca in ("dev", "lint", "type", "ci",
                                          "bench", "check")):
        return "dev"
    if nombre in ("base.txt", "main.txt", "runtime.txt", "prod.txt",
                  "production.txt"):
        return "runtime"
    # requirements.txt en la raíz (o junto a un manifiesto de paquete) es runtime.
    if nombre == "requirements.txt" and (
            archivo.parent == ruta
            or (archivo.parent / "pyproject.toml").exists()
            or (archivo.parent / "setup.py").exists()):
        return "runtime"
    return "dev"


def _leer_requirements(archivo: Path, ruta: Path,
                       vistos: Optional[Set[Path]] = None) -> List[Dict[str, str]]:
    if vistos is None:
        vistos = set()
    archivo = archivo.resolve()
    if archivo in vistos or not archivo.is_file():
        return []
    vistos.add(archivo)
    ambito = _ambito_requirements(archivo, ruta)
    origen = archivo.relative_to(ruta).as_posix() \
        if archivo.is_relative_to(ruta) else str(archivo)
    deps = []
    for linea in leer(archivo).splitlines():
        limpia = linea.split("#", 1)[0].strip()
        if not limpia:
            continue
        include = re.match(r"^(?:-r|--requirement)\s+(.+)$", limpia)
        if include:
            objetivo = (archivo.parent / include.group(1).strip()).resolve()
            deps.extend(_leer_requirements(objetivo, ruta, vistos))
            continue
        dep = _parsear_requisito(linea, origen, ambito)
        if dep:
            deps.append(dep)
    return deps


def _agregar_items(deps: List[Dict[str, str]], items: Any, origen: str,
                   ambito: str) -> None:
    if not isinstance(items, list):
        return
    for item in items:
        if not isinstance(item, str):
            continue
        dep = _parsear_requisito(item, origen, ambito)
        if dep:
            deps.append(dep)


def _dependencias_pyproject(texto: str,
                            origen: str = "pyproject.toml") -> List[Dict[str, str]]:
    """Dependencias de ``pyproject.toml``: PEP 621, PEP 735 y Poetry/PDM.

    Las listas de herramientas ajenas a ``[project]`` no se interpretan como
    dependencias del proyecto. Los grupos de dependencias (PEP 735) se incluyen
    con su ámbito (dev/test/docs) para no confundirlos con runtime.
    """
    try:
        datos = tomllib.loads(texto)
    except tomllib.TOMLDecodeError:
        datos = None
    if not isinstance(datos, dict):
        bloque = re.search(r"^dependencies\s*=\s*\[(.*?)\]", texto, re.M | re.S)
        if bloque is None:
            return []
        return [dep for item in re.findall(r'["\']([^"\']+)["\']', bloque.group(1))
                for dep in [_parsear_requisito(item, origen)] if dep]

    deps: List[Dict[str, str]] = []
    proyecto = datos.get("project")
    if isinstance(proyecto, dict):
        _agregar_items(deps, proyecto.get("dependencies"), origen, "runtime")
        opcionales = proyecto.get("optional-dependencies")
        if isinstance(opcionales, dict):
            for grupo, items in opcionales.items():
                nombre = str(grupo).lower()
                ambito = "docs" if "doc" in nombre else \
                    ("test" if "test" in nombre else
                     ("dev" if "dev" in nombre else
                      ("runtime" if nombre in ("runtime", "main", "prod")
                       else "opcional")))
                _agregar_items(deps, items, origen, ambito)
    grupos = datos.get("dependency-groups")
    if isinstance(grupos, dict):
        for grupo, items in grupos.items():
            nombre = str(grupo).lower()
            ambito = "runtime" if nombre in ("runtime", "main", "prod") else \
                ("docs" if "doc" in nombre else
                 ("test" if "test" in nombre else "dev"))
            _agregar_items(deps, items, origen, ambito)

    poesia = datos.get("tool", {}).get("poetry", {}) if isinstance(datos.get("tool"), dict) else {}
    if isinstance(poesia, dict):
        runtime = poesia.get("dependencies")
        if isinstance(runtime, dict):
            for nombre, especificacion in runtime.items():
                if str(nombre).lower() == "python":
                    continue
                if isinstance(especificacion, str):
                    _agregar_items(deps, [_requisito_poetry(str(nombre),
                                                            especificacion)],
                                   origen, "runtime")
                elif isinstance(especificacion, dict):
                    version = especificacion.get("version", "")
                    _agregar_items(deps, [_requisito_poetry(str(nombre),
                                                            str(version))],
                                   origen, "runtime")
        grupos_poesia = poesia.get("group")
        if isinstance(grupos_poesia, dict):
            for grupo, contenido in grupos_poesia.items():
                if not isinstance(contenido, dict):
                    continue
                nombre = str(grupo).lower()
                ambito = "docs" if "doc" in nombre else \
                    ("test" if "test" in nombre else "dev")
                for dep_nombre, especificacion in \
                        (contenido.get("dependencies") or {}).items():
                    if isinstance(especificacion, str):
                        _agregar_items(deps, [_requisito_poetry(
                            str(dep_nombre), especificacion)], origen, ambito)
                    elif isinstance(especificacion, dict):
                        _agregar_items(deps, [_requisito_poetry(
                            str(dep_nombre),
                            str(especificacion.get("version", "")))],
                            origen, ambito)
    return deps


def _requisito_poetry(nombre: str, version: str) -> str:
    """Línea PEP 508 aproximada desde una especificación Poetry.

    Poetry admite la versión exacta a secas (``requests = "2.28.0"``); si se
    concatenaba tal cual, ``_REQUISITO`` absorbía los dígitos en el nombre e
    inventaba el paquete ``requests2.28.0`` (P0.2), que con red se consultaba
    en PyPI. Sin operador conocido al inicio (``^``, ``~``, ``>``, ``<``,
    ``=``, ``!``) se trata como versión exacta (``==``).
    """
    if version and not version.startswith(("^", "~", ">", "<", "=", "!")):
        version = f"=={version}"
    return f"{nombre}{version}"


def _dependencias_setup_cfg(archivo: Path, ruta: Path) -> List[Dict[str, str]]:
    parser = configparser.ConfigParser()
    try:
        parser.read_string(leer(archivo))
    except configparser.Error:
        return []
    origen = archivo.relative_to(ruta).as_posix()
    deps: List[Dict[str, str]] = []
    if parser.has_section("options"):
        for clave in ("install_requires", "tests_require"):
            valor = parser.get("options", clave, fallback="")
            ambito = "runtime" if clave == "install_requires" else "dev"
            _agregar_items(deps, [linea.strip() for linea in valor.splitlines()
                                  if linea.strip()], origen, ambito)
    if parser.has_section("options.extras_require"):
        for grupo, valor in parser.items("options.extras_require"):
            ambito = "docs" if "doc" in grupo.lower() else \
                ("test" if "test" in grupo.lower() else "opcional")
            _agregar_items(deps, [linea.strip() for linea in valor.splitlines()
                                  if linea.strip()], origen, ambito)
    return deps


def _literales_lista(nodo: ast.AST) -> List[str]:
    if not isinstance(nodo, (ast.List, ast.Tuple)):
        return []
    return [elemento.value for elemento in nodo.elts
            if isinstance(elemento, ast.Constant)
            and isinstance(elemento.value, str)]


def _dependencias_setup_py(archivo: Path, ruta: Path) -> List[Dict[str, str]]:
    """Lee ``setup(...)`` con AST (sin ejecutarlo); no confunde claves de extras."""
    try:
        arbol = ast.parse(leer(archivo), filename=str(archivo))
    except SyntaxError:
        return []
    origen = archivo.relative_to(ruta).as_posix()
    deps: List[Dict[str, str]] = []
    for nodo in ast.walk(arbol):
        if not isinstance(nodo, ast.Call) \
                or not isinstance(nodo.func, ast.Name) \
                or nodo.func.id != "setup":
            continue
        for palabra in nodo.keywords:
            if palabra.arg in ("install_requires", "tests_require"):
                ambito = "runtime" if palabra.arg == "install_requires" else "dev"
                _agregar_items(deps, _literales_lista(palabra.value),
                               origen, ambito)
            elif palabra.arg == "extras_require" \
                    and isinstance(palabra.value, ast.Dict):
                for valor in palabra.value.values:
                    _agregar_items(deps, _literales_lista(valor),
                                   origen, "opcional")
    return deps


def _dependencias_package_json(archivo: Path, ruta: Path) -> List[Dict[str, str]]:
    try:
        datos = json.loads(leer(archivo))
    except (json.JSONDecodeError, TypeError) as exc:
        warnings.warn(f"{archivo}: JSON inválido ({exc}); dependencias npm no leídas",
                      RuntimeWarning, stacklevel=2)
        return []
    origen = archivo.relative_to(ruta).as_posix()
    deps: List[Dict[str, str]] = []
    for seccion, ambito in (("dependencies", "runtime"),
                            ("devDependencies", "dev"),
                            ("peerDependencies", "opcional")):
        bloque = datos.get(seccion)
        if not isinstance(bloque, dict):
            continue
        for nombre, especificacion in bloque.items():
            texto = str(especificacion)
            coincidencia = re.match(r"([~^<>=]*)\s*([0-9][^\s,;]*)", texto)
            deps.append({
                "nombre": str(nombre).lower(),
                "operador": coincidencia.group(1) if coincidencia else "",
                "version": coincidencia.group(2) if coincidencia else "",
                "origen": origen, "ambito": ambito, "ecosistema": "npm",
                "fijada": bool(coincidencia) and
                coincidencia.group(1) == "" and bool(coincidencia.group(2)),
            })
    return deps


def _dependencias(ruta: Path) -> List[Dict[str, str]]:
    """Dependencias directas de TODOS los manifiestos, con ámbito y origen.

    Cubre ``requirements*.txt`` (incluidos subdirectorios y ``-r``), todos los
    ``pyproject.toml`` (incluidos monorepos), ``setup.cfg``/``setup.py`` y
    ``package.json``. Los locks no son manifiestos: se leen aparte para resolver
    rangos. Una misma dependencia se cuenta una vez, prefiriendo runtime y la
    declaración fijada.
    """
    deps: List[Dict[str, str]] = []
    vistos_req: Set[Path] = set()
    for archivo in sorted(p for p in ruta.rglob("*")
                          if p.is_file() and not any(
                              es_parte_ignorada(parte, IGNORAR)
                              for parte in p.relative_to(ruta).parts)):
        nombre = archivo.name.lower()
        es_requisitos = bool(re.match(r"requirements.*\.(txt|in)$", nombre)) or (
            archivo.parent.name.lower() == "requirements"
            and archivo.suffix.lower() in (".txt", ".in"))
        if es_requisitos:
            deps.extend(_leer_requirements(archivo, ruta, vistos_req))
        elif nombre == "pyproject.toml":
            deps.extend(_dependencias_pyproject(
                leer(archivo), archivo.relative_to(ruta).as_posix()))
        elif nombre == "setup.cfg":
            deps.extend(_dependencias_setup_cfg(archivo, ruta))
        elif nombre == "setup.py":
            deps.extend(_dependencias_setup_py(archivo, ruta))
        elif nombre == "package.json":
            deps.extend(_dependencias_package_json(archivo, ruta))
    unicas: Dict[Tuple[str, str], Dict[str, str]] = {}
    for dep in deps:
        clave = (dep.get("ecosistema", "python"), _clave_nombre(dep["nombre"]))
        previa = unicas.get(clave)
        if previa is None:
            unicas[clave] = dep
            continue
        prioridad_dep = PRIORIDAD_AMBITO.get(dep.get("ambito", "runtime"), 9)
        prioridad_previa = PRIORIDAD_AMBITO.get(previa.get("ambito", "runtime"), 9)
        mejor_ambito = prioridad_dep < prioridad_previa
        # Una versión fijada de desarrollo no debe tapar la declaración runtime
        # (Hypothesis declara sortedcontainers runtime y tools.txt la fija).
        mejor_fijada = dep.get("fijada") and not previa.get("fijada") \
            and prioridad_dep <= prioridad_previa
        if mejor_ambito or mejor_fijada:
            unicas[clave] = dep
    return list(unicas.values())


def _versiones_lock(ruta: Path) -> Dict[str, str]:
    """Versiones resueltas por los locks (solo datos; nunca se ejecuta nada)."""
    versiones: Dict[str, str] = {}

    def _toml_lock(archivo: Path) -> None:
        try:
            datos = tomllib.loads(leer(archivo))
        except tomllib.TOMLDecodeError:
            return
        paquetes = datos.get("package", [])
        for paquete in paquetes if isinstance(paquetes, list) else []:
            if not isinstance(paquete, dict) or not paquete.get("name") \
                    or not paquete.get("version"):
                continue
            fuente = paquete.get("source")
            # El propio proyecto aparece como editable en uv.lock; no se
            # compara consigo mismo contra PyPI.
            if isinstance(fuente, dict) and fuente.get("editable"):
                continue
            versiones[_clave_nombre(str(paquete["name"]))] = \
                str(paquete["version"])

    for archivo in ruta.rglob("*"):
        if not archivo.is_file() or any(es_parte_ignorada(parte, IGNORAR)
                                        for parte in archivo.relative_to(ruta).parts):
            continue
        nombre = archivo.name.lower()
        if nombre in ("uv.lock", "poetry.lock", "pdm.lock"):
            _toml_lock(archivo)
        elif nombre == "pipfile.lock":
            try:
                datos = json.loads(leer(archivo))
            except json.JSONDecodeError as exc:
                warnings.warn(f"{archivo}: lock JSON inválido ({exc})",
                              RuntimeWarning, stacklevel=2)
                continue
            for seccion in ("default", "develop"):
                contenido = datos.get(seccion) or {}
                if not isinstance(contenido, dict):
                    warnings.warn(
                        f"{archivo}: lock JSON inválido "
                        f"(sección {seccion} no es un objeto)",
                        RuntimeWarning, stacklevel=2)
                    continue
                for paquete, detalle in contenido.items():
                    if isinstance(detalle, dict) and detalle.get("version"):
                        versiones[_clave_nombre(paquete)] = \
                            str(detalle["version"]).lstrip("=")
        elif nombre == "package-lock.json":
            try:
                datos = json.loads(leer(archivo))
            except json.JSONDecodeError as exc:
                warnings.warn(f"{archivo}: lock JSON inválido ({exc})",
                              RuntimeWarning, stacklevel=2)
                continue
            paquetes = datos.get("packages") or {}
            if not isinstance(paquetes, dict):
                warnings.warn(
                    f"{archivo}: lock JSON inválido "
                    "(sección packages no es un objeto)",
                    RuntimeWarning, stacklevel=2)
                continue
            for clave, detalle in paquetes.items():
                if not isinstance(detalle, dict) or not detalle.get("version"):
                    continue
                paquete = clave.rsplit("node_modules/", 1)[-1]
                if paquete:
                    versiones[_clave_nombre(paquete)] = str(detalle["version"])
        elif nombre.endswith(".lock") or (
                archivo.parent.name.lower() == "requirements"
                and archivo.suffix.lower() == ".txt"):
            for linea in leer(archivo).splitlines():
                dep = _parsear_requisito(linea)
                if dep and dep["operador"] == "==" and dep["version"]:
                    versiones[_clave_nombre(dep["nombre"])] = dep["version"]
    return versiones


def ultima_version_pypi(nombre: str, timeout: int = 15) -> Dict[str, Any]:
    """Última versión publicada; si falla, el MOTIVO va en `error` (no se oculta)."""
    try:
        with urllib.request.urlopen(f"https://pypi.org/pypi/{nombre}/json",
                                    timeout=timeout) as respuesta:
            return {"version": json.load(respuesta)["info"]["version"], "error": ""}
    except Exception as exc:  # noqa: BLE001 - el motivo se declara en el informe
        return {"version": None, "error": f"{type(exc).__name__}: {exc}"}


_LOCKS_PYTHON = {"requirements.lock", "uv.lock", "poetry.lock", "pipfile.lock",
                 "pdm.lock"}
_LOCKS_NPM = {"package-lock.json", "pnpm-lock.yaml", "yarn.lock"}


def _es_lock_python(archivo: Path) -> bool:
    return archivo.name.lower() in _LOCKS_PYTHON or (
        archivo.parent.name.lower() == "requirements"
        and archivo.suffix.lower() == ".txt")


def evaluar_vigencia(ruta: Path, perfil: Perfil,
                     con_red: bool) -> Dimension:
    dim = Dimension("vigencia")
    deps_python = perfil.deps_runtime_python
    deps_npm = [d for d in perfil.deps if d.get("ecosistema") == "npm"]
    locks_python = [p for p in perfil.locks if _es_lock_python(p)]
    locks_npm = [p for p in perfil.locks if p.name.lower() in _LOCKS_NPM]

    if deps_python:
        sin_fijar = [d["nombre"] for d in deps_python
                     if d.get("operador") != "==" or not d.get("version")]
        dim.criterios["v1_dependencias_fijadas"] = not sin_fijar or bool(locks_python)
        if sin_fijar and not locks_python:
            dim.hallazgos.append(Hallazgo(
                "media", f"Dependencias Python sin fijar: {', '.join(sin_fijar)}",
                "manifiestos Python", criterio="v1_dependencias_fijadas"))
        elif sin_fijar:
            dim.notas.append("rangos Python cubiertos por lockfile")
    else:
        dim.no_aplicable("v1_dependencias_fijadas",
                         "sin dependencias Python runtime")

    ecosistemas = []
    if deps_python:
        ecosistemas.append(("python", locks_python))
    if deps_npm:
        ecosistemas.append(("npm", locks_npm))
    if ecosistemas:
        faltan = [nombre for nombre, locks in ecosistemas if not locks]
        dim.criterios["v2_lockfile"] = not faltan
        dim.notas.append("locks: " + (", ".join(
            p.relative_to(ruta).as_posix() for p in perfil.locks) or "ninguno"))
        if faltan:
            dim.hallazgos.append(Hallazgo(
                "media", f"Sin lockfile para: {', '.join(faltan)} "
                        "(instalación no reproducible)", str(ruta),
                criterio="v2_lockfile"))
    else:
        dim.no_aplicable("v2_lockfile", "sin dependencias runtime detectadas")

    fecha = _git(ruta, "log", "-1", "--format=%ad", "--date=short")
    if not fecha:
        dim.no_aplicable("v3_actividad_reciente",
                         "sin historial git: no se puede medir actividad")
        dim.notas.append("sin git: actividad no evaluable")
    else:
        commits = _git(ruta, "rev-list", "--count", "HEAD")
        recientes = _git(ruta, "log", "--since=180 days ago", "--oneline")
        n_recientes = len(recientes.splitlines()) if recientes else 0
        dim.criterios["v3_actividad_reciente"] = n_recientes > 0
        dim.notas.append(f"último commit: {fecha}; commits totales: "
                         f"{commits or '?'}; últimos 180 días: {n_recientes}")
        if not n_recientes:
            dim.hallazgos.append(Hallazgo(
                "baja", "Sin commits en los últimos 180 días", f"git: {fecha}",
                criterio="v3_actividad_reciente"))

    if not deps_python:
        dim.no_aplicable("v4_dependencias_al_dia",
                         "sin dependencias Python runtime que comparar")
        return dim
    if not con_red:
        dim.notas.append("comprobación PyPI OMITIDA (--sin-red): no verificado")
        dim.no_aplicable("v4_dependencias_al_dia",
                         "comparación PyPI omitida (--sin-red): no verificada")
        return dim

    atrasadas, no_verificadas = [], []
    verificadas = 0
    for d in deps_python:
        version = d["version"] if d.get("operador") == "==" and d.get("version") \
            else perfil.versiones_lock.get(_clave_nombre(d["nombre"]), "")
        if not version:
            continue
        verificadas += 1
        consulta = ultima_version_pypi(d["nombre"])
        if consulta["error"]:
            no_verificadas.append(f"{d['nombre']} ({consulta['error']})")
            continue
        if consulta["version"] != version:
            atrasadas.append(f"{d['nombre']} {version} -> {consulta['version']}")
    if verificadas == 0:
        # Cero comparaciones no es "al día": el bucle no consultó PyPI. Un
        # manifiesto solo con rangos y sin lock no permite verificar nada.
        dim.criterios["v4_dependencias_al_dia"] = False
        dim.notas.append("sin versiones (== o lock) que comparar: no verificado")
        dim.hallazgos.append(Hallazgo(
            "baja", "No se pudo comprobar la vigencia: no hay versiones "
            "fijadas (==) ni resueltas por lock", "manifiestos/locks",
            EvidenceKind.UNVERIFIED, criterio="v4_dependencias_al_dia"))
        return dim
    if verificadas < len(deps_python):
        dim.notas.append(f"comparadas {verificadas}/{len(deps_python)} dependencias: "
                         "las que no tienen versión no se pueden comparar")
    # "No se pudo comprobar" NO es "está al día": el criterio exige verificación.
    dim.criterios["v4_dependencias_al_dia"] = not atrasadas and not no_verificadas
    for marca in atrasadas:
        dim.hallazgos.append(Hallazgo("media", f"Dependencia atrasada: {marca}",
                                      "PyPI (pypi.org/pypi)", criterio="v4_dependencias_al_dia"))
    if no_verificadas:
        dim.hallazgos.append(Hallazgo(
            "baja", "No se pudo comprobar en PyPI: " + "; ".join(no_verificadas),
            "PyPI", EvidenceKind.UNVERIFIED, criterio="v4_dependencias_al_dia"))
    return dim


LICENCIAS_LIBRES = ("mit", "bsd", "apache", "gpl", "lgpl", "mpl", "isc",
                    "unlicense", "cc0", "psf", "zlib", "python software",
                    "bsd-2-clause", "bsd-3-clause", "apache-2.0", "mpl-2.0",
                    "psf-2.0", "python-2.0", "cc0-1.0", "0bsd")


def _es_licencia_libre(texto: str) -> Optional[bool]:
    """Decide licencias libres por texto/expresión SPDX, sin inventar.

    PEP 639 hizo que PyPI publique ``license_expression``; los clasificadores
    OSI siguen existiendo pero ya no deben añadirse nuevos. Se aceptan ambos.

    Una expresión mixta que combina licencias libres conocidas con
    ``LicenseRef-`` (p. ej. ``MIT AND LicenseRef-X``) NO es «no libre»: la
    parte conocida es libre pero la referencia no se puede verificar, así que
    se devuelve ``None`` (no verificable), como manda licencia_pypi.
    """
    normalizado = (texto or "").lower()
    if not normalizado or "unknown" in normalizado:
        return False
    if "proprietary" in normalizado:
        return False
    libre_conocida = any(marca in normalizado for marca in LICENCIAS_LIBRES)
    if "licenseref-" in normalizado:
        return None if libre_conocida else False
    return libre_conocida


def licencia_pypi(nombre: str, timeout: int = 15) -> Dict[str, Any]:
    """Licencia declarada en PyPI; si falla, el MOTIVO va en `error`.

    Orden de lectura (PEP 639): ``license_expression`` > clasificador OSI >
    campo ``license`` en texto libre. Si no hay dato, ``libre`` es ``None``:
    "no verificado" no es "no libre" ni "libre".
    """
    try:
        with urllib.request.urlopen(f"https://pypi.org/pypi/{nombre}/json",
                                    timeout=timeout) as respuesta:
            info = json.load(respuesta)["info"]
    except Exception as exc:  # noqa: BLE001 - el motivo se declara en el informe
        return {"licencia": "desconocida", "libre": None, "fuente": "",
                "error": f"{type(exc).__name__}: {exc}"}
    expresion = (info.get("license_expression") or "").strip()
    if expresion:
        return {"licencia": expresion[:80], "libre": _es_licencia_libre(expresion),
                "fuente": "license_expression", "error": ""}
    aprobada = next((c for c in info.get("classifiers", [])
                     if c.startswith("License :: OSI Approved")), "")
    if aprobada:
        return {"licencia": aprobada.split("::")[-1].strip(), "libre": True,
                "fuente": "classifier", "error": ""}
    texto = ((info.get("license") or "").strip().splitlines() or [""])[0][:80]
    if not texto or texto.lower() in ("unknown", "none", "see license",
                                      "see license file") \
            or texto.lower().startswith(("http://", "https://")):
        return {"licencia": "desconocida", "libre": None, "fuente": "",
                "error": ""}
    return {"licencia": texto, "libre": _es_licencia_libre(texto),
            "fuente": "license", "error": ""}


def licencias_no_runtime(perfil: Perfil, con_red: bool) -> List[Dict[str, Any]]:
    """Licencias informativas de dependencias no runtime (R10).

    No se mezclan con `h5_licencias_libres`, que sigue midiendo solo runtime.
    Sin red, o si PyPI no da metadato, cada entrada se declara `unverified`
    con su motivo; no se inventa una licencia.
    """
    entradas: List[Dict[str, Any]] = []
    vistos = set()
    for dep in perfil.deps_python:
        if dep.get("ambito") == "runtime":
            continue
        nombre = dep.get("nombre", "")
        if not nombre or nombre in vistos:
            continue
        vistos.add(nombre)
        entrada: Dict[str, Any] = {
            "nombre": nombre,
            "ambito": dep.get("ambito", "opcional"),
            "origen": dep.get("origen", ""),
            "version": dep.get("version", ""),
            "operador": dep.get("operador", ""),
            "licencia": None,
            "libre": None,
            "fuente": "",
            "procedencia": "unverified",
        }
        if con_red:
            info = licencia_pypi(nombre)
            entrada["licencia"] = info.get("licencia")
            entrada["libre"] = info.get("libre")
            entrada["fuente"] = info.get("fuente") or "PyPI"
            if info.get("error"):
                entrada["error"] = info["error"]
            elif info.get("libre") is not None:
                entrada["procedencia"] = "real"
        else:
            entrada["fuente"] = "no consultada (--sin-red)"
        entradas.append(entrada)
    return entradas


def _registro_decisiones(ruta: Path, perfil: Perfil) -> List[str]:
    """Documentos de decisiones/ADR/changelog, en cualquier subdirectorio."""
    claves = ("adr", "decision", "changelog", "changes", "history",
              "release-notes", "releasenotes", "lecciones")
    extensiones = {".md", ".rst", ".txt", ".adoc"}
    fuentes = []
    for archivo in ruta.rglob("*"):
        if not archivo.is_file() or archivo.suffix.lower() not in extensiones:
            continue
        if any(es_parte_ignorada(parte, IGNORAR) for parte in archivo.relative_to(ruta).parts):
            continue
        nombre = archivo.name.lower()
        if any(clave in nombre for clave in claves):
            fuentes.append(archivo.relative_to(ruta).as_posix())
    if any("decision_log" in leer(p) for p in perfil.codigo_py):
        fuentes.append("decision_log en código")
    return sorted(set(fuentes))


def evaluar_herramientas(ruta: Path, perfil: Perfil,
                         con_red: bool = True) -> Dimension:
    dim = Dimension("herramientas")
    manifiestos = [p.relative_to(ruta).as_posix() for p in perfil.manifiestos]
    if manifiestos:
        dim.criterios["h1_manifiesto"] = True
        dim.notas.append(f"manifiestos ({len(manifiestos)}): "
                         + ", ".join(manifiestos[:8])
                         + ("…" if len(manifiestos) > 8 else ""))
    else:
        dim.criterios["h1_manifiesto"] = False
        dim.hallazgos.append(Hallazgo(
            "alta", "Sin manifiesto de dependencias", str(ruta),
            criterio="h1_manifiesto"))

    licencia = [p.name for p in ruta.iterdir()
                if p.is_file() and re.match(r"(LICEN[CS]E|COPYING)", p.name, re.I)]
    dim.criterios["h2_licencia"] = bool(licencia)
    if not licencia:
        dim.hallazgos.append(Hallazgo(
            "alta", "Sin archivo de licencia: el uso/reutilización queda sin "
                    "términos (P1.18)", str(ruta), criterio="h2_licencia"))

    ci = bool(list(ruta.glob(".github/workflows/*"))) or \
        (ruta / ".gitlab-ci.yml").exists() or \
        (ruta / ".circleci/config.yml").exists() or \
        (ruta / "azure-pipelines.yml").exists() or \
        (ruta / "Jenkinsfile").exists() or \
        bool(list((ruta / "scripts").glob("*verif*"))) or (ruta / "Makefile").exists() \
        or (ruta / "tox.ini").exists()
    if perfil.codigo:
        dim.criterios["h3_verificacion_automatizada"] = ci
        if not ci:
            dim.hallazgos.append(Hallazgo(
                "media", "Sin CI ni script de verificación local", str(ruta),
                criterio="h3_verificacion_automatizada"))
    else:
        dim.no_aplicable("h3_verificacion_automatizada", "sin código")

    deteccion = detectar_comando_tests(ruta)
    runner_extra = next((p for p in (ruta / "build.sh", ruta / "tox.ini",
                                     ruta / "noxfile.py") if p.exists()), None)
    if perfil.tests:
        dim.criterios["h4_runner_de_tests_declarado"] = bool(
            deteccion or runner_extra)
        if deteccion:
            dim.notas.append(f"runner: {' '.join(deteccion['comando'])} "
                             f"({deteccion['origen']})")
        elif runner_extra:
            dim.notas.append(f"runner declarado: {runner_extra.name} "
                             "(comando no inspeccionado para ejecución)")
        else:
            dim.hallazgos.append(Hallazgo(
                "media", "Tests presentes pero sin comando de ejecución declarado",
                "manifiestos/README", criterio="h4_runner_de_tests_declarado"))
    else:
        dim.no_aplicable("h4_runner_de_tests_declarado", "sin tests detectados")

    # Licencias de las dependencias Python runtime (P1.18). Las de desarrollo
    # no se mezclan con el runtime; se declara el ámbito.
    deps = perfil.deps_runtime_python
    if not deps:
        dim.no_aplicable("h5_licencias_libres",
                         "sin dependencias Python runtime")
    elif not con_red:
        dim.notas.append("licencias de dependencias OMITIDAS (--sin-red)")
        dim.no_aplicable("h5_licencias_libres",
                         "licencias de dependencias OMITIDAS (--sin-red)")
    else:
        sin_verificar, no_libres = [], []
        for dep in deps:
            info = licencia_pypi(dep["nombre"])
            if info.get("error") or info.get("libre") is None:
                motivo = info.get("error") or "sin metadato de licencia"
                sin_verificar.append(f"{dep['nombre']} ({motivo})")
            elif info["libre"] is False:
                no_libres.append(f"{dep['nombre']} ({info['licencia']})")
        dim.criterios["h5_licencias_libres"] = not no_libres and not sin_verificar
        dim.notas.append(f"licencias consultadas en PyPI: {len(deps)} "
                         f"(runtime; {len(perfil.deps_python) - len(deps)} de "
                         "desarrollo/opcionales excluidas)")
        if no_libres:
            dim.hallazgos.append(Hallazgo(
                "media", f"Dependencias sin licencia libre declarada: "
                         f"{', '.join(no_libres)}", "PyPI",
                criterio="h5_licencias_libres"))
        if sin_verificar:
            dim.hallazgos.append(Hallazgo(
                "baja", f"Licencia no verificable en PyPI: "
                        f"{', '.join(sin_verificar)}", "PyPI",
                EvidenceKind.UNVERIFIED, criterio="h5_licencias_libres"))

    # Imports de terceros sin declarar: SOLO código de producción del paquete.
    # Tests, docs, ejemplos y benchmarks no son API publicada; sus imports no
    # se convierten en hallazgos (FastAPI docs_src era el 95% de los falsos
    # positivos). Se reutiliza el gate AST de scripts/preflight.py.
    if perfil.codigo_paquete:
        from scripts.preflight import cargar_modulos, revisar_imports
        permitidos = set(perfil.first_party) | set(perfil.versiones_lock)
        modulos, _ = cargar_modulos(ruta, archivos=perfil.codigo_paquete)
        no_declarados = revisar_imports(ruta, modulos, permitidos=permitidos,
                                        ignorar_opcionales=True).hallazgos
        dim.criterios["h6_imports_declarados"] = not no_declarados
        dim.notas.append(f"h6 sobre {len(perfil.codigo_paquete)} archivos de "
                         "producción (tests/docs/scripts excluidos)")
        if no_declarados:
            dim.notas.append(f"imports de terceros sin declarar: {len(no_declarados)}")
        for hallazgo in no_declarados:
            dim.hallazgos.append(Hallazgo(
                "alta", f"Import de terceros sin declarar: {hallazgo.mensaje}",
                f"{hallazgo.archivo}:{hallazgo.linea}",
                criterio="h6_imports_declarados"))
    else:
        dim.no_aplicable("h6_imports_declarados",
                         "sin código Python de producción")

    # Señal estructural (NO veredicto): el proyecto registra sus decisiones.
    fuentes = _registro_decisiones(ruta, perfil)
    dim.criterios["h7_decisiones_documentadas"] = bool(fuentes)
    if fuentes:
        dim.notas.append("registro de decisiones: " + ", ".join(fuentes[:8]))
    else:
        dim.hallazgos.append(Hallazgo(
            "baja", "Sin registro de decisiones (ADR/decision_log/CHANGELOG): "
                    "el porqué de las decisiones no es consultable", str(ruta),
            criterio="h7_decisiones_documentadas"))
    return dim


def evaluar_inteligencia(ruta: Path, perfil: Perfil) -> Dimension:
    dim = Dimension("inteligencia")
    if not perfil.es_llm:
        for clave in ("i1_cachea_trabajo_repetido", "i2_timeouts_explicitos",
                      "i3_reintentos_con_limite", "i4_valida_respuestas",
                      "i5_declara_lo_simulado", "i6_metricas_propias"):
            dim.no_aplicable(clave, "el proyecto no declara un LLM en "
                                    "dependencias runtime")
        dim.notas.append("dimensión N/A: señales específicas de sistemas LLM")
        return dim

    texto = "\n".join(leer(p) for p in perfil.codigo_py)
    dim.criterios["i1_cachea_trabajo_repetido"] = bool(
        re.search(r"\b(lru_cache|@cache|caché|cache\[|_cache)\b", texto))
    dim.criterios["i2_timeouts_explicitos"] = bool(
        re.search(r"timeout\s*=", texto))
    dim.criterios["i3_reintentos_con_limite"] = bool(
        re.search(r"(max_retries|reintent|backoff|retry)", texto, re.I))
    dim.criterios["i4_valida_respuestas"] = bool(
        re.search(r"json\.loads|JSONDecodeError|_parse_", texto))
    dim.criterios["i5_declara_lo_simulado"] = bool(
        re.search(r"(simulad|mock)", texto, re.I))
    dim.criterios["i6_metricas_propias"] = bool(
        re.search(r"(benchmark|rúbrica|rubrica|metric|medición|medicion)", texto, re.I))

    for clave, nombre in (("i1_cachea_trabajo_repetido", "caché"),
                          ("i2_timeouts_explicitos", "timeouts explícitos"),
                          ("i3_reintentos_con_limite", "reintentos con límite"),
                          ("i4_valida_respuestas", "validación de respuestas"),
                          ("i5_declara_lo_simulado", "declaración de lo simulado"),
                          ("i6_metricas_propias", "métricas propias")):
        if not dim.criterios[clave]:
            dim.hallazgos.append(Hallazgo(
                "baja", f"Sin señal de {nombre}", "código de producción",
                criterio=clave))
    return dim


def evaluar_eficiencia(ruta: Path, perfil: Perfil) -> Dimension:
    dim = Dimension("eficiencia")
    if not perfil.es_llm:
        for clave in ("e1_import_perezoso_de_pesadas",
                      "e2_carga_unica_de_modelos",
                      "e3_mediciones_documentadas"):
            dim.no_aplicable(clave, "el proyecto no declara un LLM en "
                                    "dependencias runtime")
        dim.notas.append("dimensión N/A: señales específicas de sistemas LLM")
        return dim

    texto_perezoso = 0
    cargas_unicas = 0
    for p in perfil.codigo_py:
        contenido = leer(p)
        lineas = contenido.splitlines()
        for m in re.finditer(r"^\s+import |^\s+from ", contenido, re.M):
            inicio = contenido[:m.start()].count("\n")
            cabecera = "\n".join(lineas[:inicio])
            linea = lineas[inicio] if inicio < len(lineas) else ""
            if any(pesada in linea for pesada in PESADAS) \
                    and "def " in cabecera:
                texto_perezoso += 1
        cargas_unicas += len(re.findall(r"(create_model|cargar_modelo|_load_model)",
                                        contenido))

    if perfil.pesadas:
        dim.criterios["e1_import_perezoso_de_pesadas"] = texto_perezoso > 0
        dim.notas.append(f"imports perezosos detectados: {texto_perezoso}")
        if not texto_perezoso:
            dim.hallazgos.append(Hallazgo(
                "media", "Dependencia pesada importada al cargar el módulo "
                        "(no de forma perezosa)", "código de producción",
                criterio="e1_import_perezoso_de_pesadas"))
    else:
        dim.no_aplicable("e1_import_perezoso_de_pesadas",
                         "sin dependencias pesadas declaradas")

    if any(marca in perfil.pesadas for marca in MODELOS):
        dim.criterios["e2_carga_unica_de_modelos"] = cargas_unicas > 0
        dim.notas.append(f"llamadas de carga de modelo: {cargas_unicas}")
        if not cargas_unicas:
            dim.hallazgos.append(Hallazgo(
                "media", "Sin señal de carga única/reutilizada de modelos "
                        "(create_model/cargar_modelo/_load_model)",
                "código de producción", criterio="e2_carga_unica_de_modelos"))
    else:
        dim.no_aplicable("e2_carga_unica_de_modelos",
                         "el proyecto usa API LLM, no carga modelos locales")

    docs = [p for p in ruta.rglob("*")
            if p.is_file() and p.suffix.lower() in (".md", ".rst")
            and not any(es_parte_ignorada(parte, IGNORAR) for parte in p.relative_to(ruta).parts)]
    mediciones = any(re.search(r"\b\d+(\.\d+)?\s*(s|seg|MB|GB|min)\b", leer(d))
                     for d in docs)
    dim.criterios["e3_mediciones_documentadas"] = mediciones
    if not mediciones:
        dim.hallazgos.append(Hallazgo(
            "baja", "Sin mediciones reales (tiempo/RAM) en la documentación "
                    "(*.md/*.rst) del repositorio",
            "*.md|*.rst del repositorio",
            criterio="e3_mediciones_documentadas"))

    dim.notas.append("sin medición en vivo: no se ejecuta código del proyecto "
                     "evaluado (P0.8)")
    return dim


# --- Mejoras propuestas: cada una nace de una métrica y trae su verificación --

MEJORAS: Dict[str, Dict[str, str]] = {
    "f1_puntos_de_entrada": {
        "prioridad": "baja",
        "propuesta": "Exponer un punto de entrada ejecutable (CLI)",
        "metrica": "hay módulos con `main()` y `if __name__ == \"__main__\"`"},
    "f2_readme_vs_realidad": {
        "prioridad": "alta",
        "propuesta": "Alinear README y código: implementar o retirar lo prometido",
        "metrica": "cada `archivo.py` citado en el README existe"},
    "f3_sin_deuda_declarada": {
        "prioridad": "baja",
        "propuesta": "Cerrar o priorizar las marcas TODO/FIXME/XXX de producción",
        "metrica": "0 marcas TODO/FIXME/XXX en el código de producción"},
    "f4_tests_de_varios_modulos": {
        "prioridad": "media",
        "propuesta": "Cubrir con tests los módulos que hoy no tienen ninguno",
        "metrica": "nº de archivos de test del ecosistema > 1"},
    "c1_suite_de_tests": {
        "prioridad": "alta",
        "propuesta": "Crear una suite de tests ejecutable",
        "metrica": "`python3 -m unittest discover` devuelve OK"},
    "c2_linter_configurado": {
        "prioridad": "media",
        "propuesta": "Configurar un linter (p. ej. ruff) y dejarlo en 0 avisos",
        "metrica": "`ruff check .` sale con código 0"},
    "c3_sin_silencios": {
        "prioridad": "alta",
        "propuesta": "Sustituir los `except` con `pass`/`continue` por error "
                     "reportado o re-elevado (P1.26)",
        "metrica": "0 coincidencias del patrón except+pass/continue"},
    "c4_tests_sobre_codigo_30pct": {
        "prioridad": "media",
        "propuesta": "Acercar la proporción test/código al 30% o justificar la "
                     "excepción por escrito",
        "metrica": "líneas de test / líneas de código >= 0,30"},
    "v1_dependencias_fijadas": {
        "prioridad": "media",
        "propuesta": "Fijar las versiones runtime (==) o cubrirlas con un lock",
        "metrica": "0 dependencias runtime sin versión exacta ni lock"},
    "v2_lockfile": {
        "prioridad": "media",
        "propuesta": "Generar un lockfile por ecosistema e instalar desde él",
        "metrica": "cada ecosistema con dependencias tiene su lockfile"},
    "v3_actividad_reciente": {
        "prioridad": "baja",
        "propuesta": "Mantener actividad o declarar el proyecto como inactivo",
        "metrica": ">= 1 commit en los últimos 180 días"},
    "v4_dependencias_al_dia": {
        "prioridad": "media",
        "propuesta": "Verificar en PyPI las versiones fijadas o resueltas por "
                     "lock y actualizar las atrasadas",
        "metrica": "ninguna versión resuelta por detrás de la última publicada"},
    "h1_manifiesto": {
        "prioridad": "alta",
        "propuesta": "Declarar las dependencias en un manifiesto del ecosistema",
        "metrica": "existe pyproject.toml, setup.cfg, package.json o build.gradle"},
    "h2_licencia": {
        "prioridad": "alta",
        "propuesta": "Añadir un archivo de licencia: sin él no hay términos de uso",
        "metrica": "existe LICENSE/COPYING"},
    "h3_verificacion_automatizada": {
        "prioridad": "media",
        "propuesta": "Añadir CI local (script de verificación) o remota",
        "metrica": "existe scripts/*verif*, Makefile o .github/workflows"},
    "h4_runner_de_tests_declarado": {
        "prioridad": "baja",
        "propuesta": "Declarar el comando de tests (Makefile, README, "
                     "package.json, Gradle/Maven o tox/nox)",
        "metrica": "el comando de la suite aparece en un archivo del proyecto"},
    "i1_cachea_trabajo_repetido": {
        "prioridad": "media",
        "propuesta": "Cachear trabajo repetido (respuestas o cómputo idéntico)",
        "metrica": "existe caché y se puede medir su tasa de aciertos"},
    "i2_timeouts_explicitos": {
        "prioridad": "alta",
        "propuesta": "Poner timeout explícito en toda llamada de red (P1.34)",
        "metrica": "cada cliente de red declara timeout y es configurable"},
    "i3_reintentos_con_limite": {
        "prioridad": "media",
        "propuesta": "Reintentar solo errores transitorios, con límite y backoff",
        "metrica": "existe max_retries/backoff y un test que agote los intentos"},
    "i4_valida_respuestas": {
        "prioridad": "alta",
        "propuesta": "Validar las respuestas externas antes de usarlas",
        "metrica": "el parseo falla de forma ruidosa (excepción) y hay test de ello"},
    "i5_declara_lo_simulado": {
        "prioridad": "media",
        "propuesta": "Declarar explícitamente lo simulado/mock (regla propia 4)",
        "metrica": "lo simulado aparece marcado como simulado en código y docs"},
    "i6_metricas_propias": {
        "prioridad": "media",
        "propuesta": "Medir lo que produce el sistema (benchmark o rúbrica propia)",
        "metrica": "existe un benchmark/rúbrica ejecutable y su salida se conserva"},
    "e1_import_perezoso_de_pesadas": {
        "prioridad": "media",
        "propuesta": "Importar perezosamente las dependencias pesadas (dentro de "
                     "la función que las usa)",
        "metrica": "el import pesado no ocurre al importar el módulo"},
    "e2_carga_unica_de_modelos": {
        "prioridad": "media",
        "propuesta": "Cargar cada modelo una sola vez (daemon o caché de proceso)",
        "metrica": "una sola carga por proceso, verificada en ejecución"},
    "e3_mediciones_documentadas": {
        "prioridad": "baja",
        "propuesta": "Documentar mediciones reales (tiempo/RAM/coste) por ruta",
        "metrica": "docs/ contiene cifras medidas con su fecha"},
    "c1b_suite_pasa": {
        "prioridad": "alta",
        "propuesta": "Dejar la suite en verde: ningún test puede fallar",
        "metrica": "el comando de tests declarado devuelve código 0"},
    "h5_licencias_libres": {
        "prioridad": "media",
        "propuesta": "Declarar o sustituir las dependencias cuya licencia libre "
                     "no se puede verificar en PyPI",
        "metrica": "todas las dependencias runtime declaran license_expression "
                   "SPDX, clasificador OSI o licencia libre verificable"},
    "h6_imports_declarados": {
        "prioridad": "alta",
        "propuesta": "Declarar en el manifiesto cada import de terceros del "
                     "código de producción o eliminar el import",
        "metrica": "0 imports de terceros sin declarar en el paquete "
                   "(tests/docs/opcionales excluidos)"},
    "h7_decisiones_documentadas": {
        "prioridad": "baja",
        "propuesta": "Registrar las decisiones (ADR, decision_log o CHANGELOG) "
                     "para que el porqué sea consultable",
        "metrica": "existe un registro de decisiones en docs/ o en el código"},
    "c5_tests_con_aserciones": {
        "prioridad": "alta",
        "propuesta": "Eliminar tests no-op o añadirles una aserción/operación "
                     "verificable: un test que no puede fallar no es un test",
        "metrica": "0 funciones test_* sin aserción ni operación que pueda fallar"},
}


# Criterios que dependen de otro (se proponen en secuencia, no sueltos).
SECUENCIA = {
    "v2_lockfile": 2,          # después de fijar versiones (v1)
    "h4_runner_de_tests_declarado": 2,
    "e2_carga_unica_de_modelos": 2,
}


def _esfuerzo(n_sitios: int) -> str:
    """Esfuerzo estimado por número de sitios afectados (declarado, no oculto)."""
    if n_sitios <= 1:
        return "bajo"
    if n_sitios <= 10:
        return "medio"
    return "alto"


def proponer_mejoras(informe: Dict[str, Any]) -> List[Dict[str, str]]:
    """Plan de mejora DERIVADO de las métricas del informe.

    Cada propuesta usa SOLO los hallazgos de su criterio. Antes se reutilizaba
    la evidencia de toda la dimensión y h5/h6/h7 acababan citando los mismos
    855 sitios de FastAPI: una recomendación irrelevante con apariencia de
    medición. `datos_medidos` declara cuántos hallazgos y evidencias la respaldan.
    """
    propuestas = []
    for nombre, datos in informe["dimensiones"].items():
        for criterio, ok in datos["criterios"].items():
            if ok:
                continue
            plan = MEJORAS.get(criterio)
            if plan is None:
                continue
            hallazgos = [h for h in datos["hallazgos"]
                         if h.get("criterio") == criterio and h.get("evidencia")]
            evidencias = [h["evidencia"] for h in hallazgos]
            propuestas.append({
                "dimension": nombre,
                "criterio": criterio,
                "prioridad": plan["prioridad"],
                "propuesta": plan["propuesta"],
                "metrica": plan["metrica"],
                "sitios": len(evidencias),
                "esfuerzo": _esfuerzo(len(evidencias)),
                "secuencia": SECUENCIA.get(criterio, 1),
                "datos_medidos": {"hallazgos": len(hallazgos),
                                  "evidencias": len(evidencias)},
                "evidencia": evidencias[:5],
            })
    orden = {"alta": 0, "media": 1, "baja": 2}
    propuestas.sort(key=lambda p: (orden.get(p["prioridad"], 3), p["secuencia"],
                                   {"bajo": 0, "medio": 1, "alto": 2}[p["esfuerzo"]],
                                   p["criterio"]))
    return propuestas


def plan_texto(informe: Dict[str, Any]) -> List[str]:
    """Resumen del plan: cuántas propuestas por prioridad y el orden de trabajo."""
    propuestas = informe.get("mejoras", [])
    if not propuestas:
        return ["Plan de mejora: nada que proponer (todos los criterios cumplen)."]
    conteo: Dict[str, int] = {}
    for p in propuestas:
        conteo[p["prioridad"]] = conteo.get(p["prioridad"], 0) + 1
    resumen = ", ".join(f"{n} {prioridad}" for prioridad, n in
                        sorted(conteo.items(),
                               key=lambda x: {"alta": 0, "media": 1, "baja": 2}[x[0]]))
    return [f"Plan de mejora: {len(propuestas)} propuestas ({resumen}); "
            f"ordenadas por prioridad, secuencia y esfuerzo."]


# --- Síntesis con LLM (opt-in): lo que el plan mecánico no ve ----------------

PROMPT_SINTESIS = """Eres un ingeniero de software senior. Con SOLO la evidencia
medida que se te da (no inventes archivos, métricas, APIs ni líneas), propón
mejoras de FONDO que un plan mecánico por criterios no vería: diseño, estructura,
algoritmos, eficiencia o riesgos del proyecto.

Si algo no se puede decidir con la evidencia medida, NO lo inventes: formúlalo
como pregunta abierta (se investigará después).

Responde SOLO un objeto JSON con estas dos claves:
{"propuestas": [{"dimension": "funcionalidades|calidad|vigencia|herramientas|inteligencia|eficiencia",
                 "propuesta": "acción concreta",
                 "por_que": "razón breve",
                 "evidencia": "archivo:línea o medición tomada del informe",
                 "como_verificar": "métrica que la cerraría"}],
 "preguntas_abiertas": ["qué no puedes decidir sin más información"]}

Máximo 5 propuestas, ordenadas por impacto.

INFORME MEDIDO:"""


def investigar_preguntas(preguntas: List[str], search_api,
                         max_por_pregunta: int = 2) -> List[Dict[str, Any]]:
    """Resuelve las dudas declaradas por el modelo con búsqueda real y citada.

    Reutiliza `web_search` (Wikipedia/DuckDuckGo, sin API key). Cada hallazgo
    lleva su URL para poder verificarlo; si la búsqueda falla o no devuelve nada,
    se declara (nunca se rellena con texto inventado).
    """
    from web_search import formulate_query

    hallazgos = []
    for pregunta in preguntas:
        try:
            resultados = search_api.search(formulate_query(pregunta, 5))
        except Exception as exc:  # noqa: BLE001 - se declara el fallo
            hallazgos.append({"pregunta": pregunta,
                              "error": f"{type(exc).__name__}: {exc}"})
            continue
        fuentes = [{"titulo": r.get("title", ""), "url": r.get("url", "")}
                   for r in resultados[:max_por_pregunta]]
        hallazgos.append({"pregunta": pregunta, "fuentes": fuentes,
                          "sin_resultados": not fuentes})
    return hallazgos


def _puntuacion_texto(valor: Optional[float], decimales: int = 2) -> str:
    return "N/A" if valor is None else f"{valor:.{decimales}f}"


def _digesto(informe: Dict[str, Any], max_hallazgos: int = 20) -> str:
    """Resumen del informe medido para el prompt (solo datos del propio informe)."""
    lineas = [f"ruta: {informe['ruta']}",
              f"python: {informe['archivos_python']} archivos / "
              f"{informe['lineas_python']} líneas"]
    cobertura = informe.get("cobertura", {})
    lineas.append(f"cobertura: {cobertura.get('criterios_evaluados', '?')} "
                  f"criterios evaluados, "
                  f"{cobertura.get('criterios_no_aplicables', '?')} N/A "
                  f"(nivel {cobertura.get('nivel', '?')})")
    for nombre, datos in informe["dimensiones"].items():
        fallos = [c for c, ok in datos["criterios"].items() if not ok]
        lineas.append(f"- {nombre}: {_puntuacion_texto(datos['puntuacion'])} | "
                      f"fallos: {fallos or '—'}")
        for h in datos["hallazgos"][:max_hallazgos]:
            marca = EvidenceKind(h["tipo_evidencia"]).marcador
            lineas.append(f"    {marca} ({h['severidad']}) "
                          f"{h['descripcion'][:110]} — {h['evidencia']}")
        for nota in datos["notas"]:
            lineas.append(f"    · {nota}")
    return "\n".join(lineas)


def sintetizar_con_llm(informe: Dict[str, Any], llm) -> Dict[str, Any]:
    """Genera propuestas con un LLM a partir del informe medido (opt-in).

    Control anti-invención (mecánico): cada propuesta se marca `con_respaldo`
    solo si su campo `evidencia` aparece en la evidencia medida del informe. Las
    que no lo tengan se conservan pero quedan marcadas: son juicio, no medición.
    """
    evidencia_medida = " ".join(
        [h["evidencia"] for d in informe["dimensiones"].values()
         for h in d["hallazgos"]]
        + [n for d in informe["dimensiones"].values() for n in d["notas"]]
        + [informe["ruta"]])

    respuesta = llm.generate(PROMPT_SINTESIS + "\n" + _digesto(informe))
    datos = _parse_json_response(respuesta)
    if isinstance(datos, dict):
        crudas = datos.get("propuestas", [])
        preguntas = [str(p) for p in datos.get("preguntas_abiertas", [])]
    elif isinstance(datos, list):          # contrato antiguo: solo propuestas
        crudas, preguntas = datos, []
    else:
        raise ValueError("La síntesis debe ser un objeto o array JSON")
    if not isinstance(crudas, list):
        raise ValueError("`propuestas` debe ser una lista")

    propuestas = []
    for item in crudas:
        if not isinstance(item, dict):
            continue
        propuesta = {
            "dimension": str(item.get("dimension", "")),
            "propuesta": str(item.get("propuesta", "")),
            "por_que": str(item.get("por_que", "")),
            "evidencia": str(item.get("evidencia", "")),
            "como_verificar": str(item.get("como_verificar", "")),
        }
        clave = propuesta["evidencia"].split()[0] if propuesta["evidencia"] else ""
        propuesta["con_respaldo"] = bool(clave) and clave in evidencia_medida
        propuestas.append(propuesta)

    return {"modelo": getattr(llm, "model", "?"),
            "propuestas": propuestas,
            "preguntas_abiertas": preguntas,
            "sin_respaldo": sum(1 for p in propuestas if not p["con_respaldo"])}


_CABECERA_REQ = re.compile(
    r"^##\s+(?:(?P<id>(?:[A-Za-z]{1,6}[-_.]?\d+|\d+(?:\.\d+)*))"
    r"\s*[:—–-]\s+)?(?P<titulo>.+?)\s*$")
_CAMPO_REQ = re.compile(r"^\s*[-*]\s+(?P<clave>[^:]+?)\s*:\s*(?P<valor>.+?)\s*$")

_CAMPOS_REQUISITO = {
    "enunciado": "enunciado", "statement": "enunciado",
    "requisito": "enunciado",
    "criterio": "criterio", "criterio de aceptacion": "criterio",
    "acceptance": "criterio", "acceptance criteria": "criterio",
    "verificacion": "verificacion", "verification": "verificacion",
    "metodo": "verificacion", "method": "verificacion",
    "evidencia": "evidencia", "evidence": "evidencia",
    "tags": "tags", "tag": "tags",
    "notas": "notas", "notes": "notas",
}

_METODOS_VERIFICACION = {
    "test": "test", "prueba": "test", "pruebas": "test", "pytest": "test",
    "archivo": "archivo", "file": "archivo", "codigo": "archivo",
    "tag": "tag", "etiqueta": "tag", "marca": "tag",
    "manual": "manual", "humano": "manual", "revision": "manual",
    "formal": "formal", "propiedad": "formal", "proof": "formal",
    "demostracion": "formal",
}

_TERMINOS_VAGOS = (
    "facil", "facilmente", "rapido", "rapidamente", "adecuad", "optim",
    "amigable", "robusto", "etc", "varios", "algunos", "mejorar",
    "eficiente", "suficiente", "apropiad",
)


def _normalizar_texto(texto: str) -> str:
    """Minúsculas, sin acentos y con espacios colapsados (claves y términos)."""
    return " ".join(texto.lower().translate(
        str.maketrans("áéíóúüñ", "aeiouun")).split())


def parsear_requisitos(archivo: Path) -> List[Requisito]:
    """Lee el Markdown estructurado de requisitos; falla con línea, no adivina.

    Formato: ``## ID: título`` y campos ``- Clave: valor``. Un campo
    obligatorio ausente o duplicado es un ``ValueError`` con su línea; nunca se
    convierte en un veredicto silencioso. Los bloques de código se ignoran.
    """
    try:
        texto = leer(archivo)
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"No se pudo leer {archivo}: {exc}") from exc

    requisitos: List[Requisito] = []
    actual: Optional[Dict[str, Any]] = None
    ultimo_campo: Optional[str] = None
    ids: Set[str] = set()
    en_bloque = False

    def cerrar() -> None:
        nonlocal actual, ultimo_campo
        if actual is None:
            return
        faltan = [campo for campo in ("enunciado", "criterio")
                  if not actual[campo]]
        if faltan:
            raise ValueError(
                f"{archivo}:{actual['linea']}: requisito {actual['id']} sin "
                + " ni ".join(f"`{campo}`" for campo in faltan))
        requisitos.append(Requisito(
            id=actual["id"], titulo=actual["titulo"],
            enunciado=actual["enunciado"], criterio=actual["criterio"],
            origen=f"{archivo.name}:{actual['linea']}",
            verificacion=actual["verificacion"], evidencia=actual["evidencia"],
            tags=actual["tags"], avisos=actual["avisos"]))
        actual = None
        ultimo_campo = None

    for numero, linea in enumerate(texto.splitlines(), 1):
        if linea.strip().startswith("```"):
            en_bloque = not en_bloque
            continue
        if en_bloque:
            continue
        if not linea.strip():
            ultimo_campo = None
            continue
        cabecera = _CABECERA_REQ.match(linea)
        if cabecera:
            cerrar()
            ultimo_campo = None
            titulo = cabecera.group("titulo").strip()
            id_ = cabecera.group("id") or f"R{len(requisitos) + 1}"
            if id_ in ids:
                raise ValueError(
                    f"{archivo}:{numero}: ID de requisito duplicado: {id_}")
            ids.add(id_)
            actual = {
                "id": id_, "titulo": titulo, "linea": numero,
                "enunciado": "", "criterio": "", "verificacion": "",
                "evidencia": "", "tags": [], "avisos": [],
            }
            if not cabecera.group("id"):
                actual["avisos"].append(
                    "ID autogenerado; usa '## ID: título' para un ID estable")
            continue
        if actual is None:
            continue
        campo = _CAMPO_REQ.match(linea)
        if not campo:
            # Continuación indentada de un enunciado/criterio multilínea; el
            # resto de prosa cierra el campo para no concatenar sin control.
            if (ultimo_campo in ("enunciado", "criterio")
                    and linea[:1].isspace()):
                actual[ultimo_campo] = (
                    f"{actual[ultimo_campo]} {linea.strip()}").strip()
            else:
                ultimo_campo = None
            continue
        clave = _normalizar_texto(campo.group("clave"))
        valor = campo.group("valor").strip()
        destino = _CAMPOS_REQUISITO.get(clave)
        if destino is None:
            actual["avisos"].append(
                f"línea {numero}: campo no reconocido: "
                f"{campo.group('clave').strip()}")
            ultimo_campo = None
            continue
        if destino == "tags":
            actual["tags"].extend(
                tag.strip() for tag in valor.split(",") if tag.strip())
            ultimo_campo = None
            continue
        if destino == "notas":
            actual["avisos"].append(f"línea {numero}: {valor}")
            ultimo_campo = None
            continue
        if destino == "verificacion":
            if actual["verificacion"]:
                raise ValueError(
                    f"{archivo}:{numero}: campo duplicado en requisito "
                    f"{actual['id']}: verificación")
            metodo = _METODOS_VERIFICACION.get(_normalizar_texto(valor))
            if metodo is None:
                raise ValueError(
                    f"{archivo}:{numero}: método de verificación no "
                    f"reconocido: {valor!r}")
            actual["verificacion"] = metodo
            ultimo_campo = None
            continue
        if actual[destino]:
            raise ValueError(
                f"{archivo}:{numero}: campo duplicado en requisito "
                f"{actual['id']}: {campo.group('clave').strip()}")
        actual[destino] = valor
        ultimo_campo = destino if destino in ("enunciado", "criterio") else None

    cerrar()
    if not requisitos:
        raise ValueError(
            f"{archivo}: no se encontró ningún requisito "
            "('## ID: título' + '- Enunciado:' + '- Criterio de aceptación:')")
    return requisitos


def _texto_legible(ruta: Path, archivo: Path) -> str:
    try:
        return archivo.relative_to(ruta).as_posix()
    except ValueError:
        return str(archivo)


def _resolver_evidencia(ruta: Path, texto: str) -> Optional[Path]:
    """Resuelve una ruta de evidencia SOLO si queda dentro del proyecto."""
    limpio = texto.strip().strip("`'\"")
    if not limpio:
        return None
    candidato = Path(limpio)
    if not candidato.is_absolute():
        candidato = ruta / candidato
    try:
        candidato = candidato.resolve()
        candidato.relative_to(ruta.resolve())
    except (OSError, ValueError):
        return None
    return candidato


def _test_existe(archivo: Path, nombre: str) -> Optional[bool]:
    """Busca una función de test Python por nombre; None si no se puede leer."""
    try:
        arbol = ast.parse(leer(archivo), filename=str(archivo))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return None
    buscado = nombre.split("::")[-1].split("[", 1)[0].strip()
    return any(
        isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef))
        and nodo.name == buscado for nodo in ast.walk(arbol))


def _buscar_tag(perfil: Perfil, tag: str,
                avisos: Optional[List[str]] = None) -> str:
    """Devuelve ``archivo:línea`` del primer tag encontrado, o cadena vacía.

    Un archivo ilegible no se omite en silencio: se registra en ``avisos`` y la
    búsqueda continúa (P1.19/P1.26).
    """
    if not tag:
        return ""
    vistos: Set[Path] = set()
    for archivo in perfil.codigo + perfil.tests:
        if archivo in vistos:
            continue
        vistos.add(archivo)
        try:
            texto = leer(archivo)
        except (OSError, UnicodeDecodeError) as exc:
            if avisos is not None:
                avisos.append(
                    f"no se pudo leer {_texto_legible(perfil.ruta, archivo)}: "
                    f"{type(exc).__name__}")
            continue
        for numero, linea in enumerate(texto.splitlines(), 1):
            if tag in linea:
                return f"{_texto_legible(perfil.ruta, archivo)}:{numero}"
    return ""


def _avisos_criterio(criterio: str) -> List[str]:
    """Heurística declarada: avisa de criterios poco medibles, no los absuelve."""
    normalizado = _normalizar_texto(criterio)
    avisos = []
    if len(criterio.strip()) < 10:
        avisos.append("criterio demasiado corto para ser medible")
    vagos = [termino for termino in _TERMINOS_VAGOS if termino in normalizado]
    if vagos:
        avisos.append("criterio con términos vagos: " + ", ".join(vagos))
    return avisos


def _verificar_test(ruta: Path, req: Requisito,
                    resultado_tests: Optional[Dict[str, Any]]):
    if not req.evidencia:
        return ("NO VERIFICABLE", "método 'test' sin evidencia declarada", "",
                EvidenceKind.UNVERIFIED)
    partes = req.evidencia.strip().strip("`'\"").split("::")
    archivo = _resolver_evidencia(ruta, partes[0].strip())
    test_nombre = "::".join(partes[1:]).strip()
    if archivo is None:
        return ("NO VERIFICABLE",
                "evidencia fuera del proyecto o no resoluble", req.evidencia,
                EvidenceKind.UNVERIFIED)
    legible = _texto_legible(ruta, archivo)
    if not archivo.is_file():
        return ("NO CUMPLE", "la evidencia declarada no es un archivo",
                legible, EvidenceKind.VERIFIED_REAL)
    if not test_nombre:
        return ("CUBIERTO", "archivo de test declarado, sin test concreto",
                legible, EvidenceKind.VERIFIED_REAL)
    if archivo.suffix != ".py":
        return ("CUBIERTO",
                "test declarado en lenguaje no Python: no validado "
                "estáticamente", legible, EvidenceKind.VERIFIED_REAL)
    existe = _test_existe(archivo, test_nombre)
    if existe is None:
        return ("NO VERIFICABLE", "no se pudo analizar el archivo de test",
                legible, EvidenceKind.UNVERIFIED)
    if not existe:
        return ("NO CUMPLE",
                f"el test {test_nombre!r} no existe en el archivo", legible,
                EvidenceKind.VERIFIED_REAL)
    if resultado_tests is None:
        return ("CUBIERTO",
                "test declarado; suite no ejecutada (--ejecutar-tests)",
                legible, EvidenceKind.VERIFIED_REAL)
    if not resultado_tests.get("ejecutado") or resultado_tests.get("error"):
        motivo = (resultado_tests.get("motivo")
                  or resultado_tests.get("error")
                  or "suite no ejecutada")
        return ("CUBIERTO", f"test declarado; {motivo}", legible,
                EvidenceKind.UNVERIFIED)
    if not resultado_tests.get("ok"):
        return ("NO CUMPLE", "la suite falló; el test declarado no pasa",
                legible, EvidenceKind.VERIFIED_REAL)
    return ("CUMPLE", "suite completa verde (test declarado, no aislado)",
            legible, EvidenceKind.VERIFIED_REAL)


def _verificar_archivo(ruta: Path, req: Requisito):
    if not req.evidencia:
        return ("NO VERIFICABLE", "método 'archivo' sin evidencia declarada",
                "", EvidenceKind.UNVERIFIED)
    archivo = _resolver_evidencia(ruta, req.evidencia)
    if archivo is None:
        return ("NO VERIFICABLE",
                "evidencia fuera del proyecto o no resoluble", req.evidencia,
                EvidenceKind.UNVERIFIED)
    legible = _texto_legible(ruta, archivo)
    if not archivo.is_file():
        return ("NO CUMPLE", "la evidencia declarada no es un archivo",
                legible, EvidenceKind.VERIFIED_REAL)
    return ("CUBIERTO", "archivo presente; no prueba comportamiento", legible,
            EvidenceKind.VERIFIED_REAL)


def _verificar_formal(ruta: Path, req: Requisito):
    if not req.evidencia:
        return ("NO VERIFICABLE", "método 'formal' sin evidencia declarada",
                "", EvidenceKind.UNVERIFIED)
    archivo = _resolver_evidencia(ruta, req.evidencia)
    if archivo is None:
        return ("NO VERIFICABLE",
                "evidencia fuera del proyecto o no resoluble", req.evidencia,
                EvidenceKind.UNVERIFIED)
    legible = _texto_legible(ruta, archivo)
    if not archivo.is_file():
        return ("NO CUMPLE", "la evidencia declarada no es un archivo",
                legible, EvidenceKind.VERIFIED_REAL)
    return ("CUBIERTO", "artefacto formal declarado; no re-ejecutado",
            legible, EvidenceKind.VERIFIED_REAL)


def _verificar_tag(perfil: Perfil, req: Requisito):
    tag = req.evidencia.strip().strip("`'\"") or (req.tags[0] if req.tags else "")
    if not tag:
        return ("NO VERIFICABLE", "método 'tag' sin etiqueta declarada", "",
                EvidenceKind.UNVERIFIED)
    ubicacion = _buscar_tag(perfil, tag, req.avisos)
    if ubicacion:
        return ("CUBIERTO", f"tag {tag!r} encontrado en código o tests",
                ubicacion, EvidenceKind.VERIFIED_REAL)
    return ("NO CUMPLE", f"tag {tag!r} no encontrado en código ni tests",
            tag, EvidenceKind.VERIFIED_REAL)


def _verificar_requisito(ruta: Path, perfil: Perfil, req: Requisito,
                         resultado_tests: Optional[Dict[str, Any]]):
    if not req.verificacion:
        return ("NO VERIFICABLE", "sin método de verificación declarado", "",
                EvidenceKind.UNVERIFIED)
    if req.verificacion == "manual":
        return ("NO VERIFICABLE",
                "verificación manual: requiere revisión humana", "",
                EvidenceKind.UNVERIFIED)
    if req.verificacion == "test":
        return _verificar_test(ruta, req, resultado_tests)
    if req.verificacion == "archivo":
        return _verificar_archivo(ruta, req)
    if req.verificacion == "tag":
        return _verificar_tag(perfil, req)
    if req.verificacion == "formal":
        return _verificar_formal(ruta, req)
    return ("NO VERIFICABLE", f"método no soportado: {req.verificacion}", "",
            EvidenceKind.UNVERIFIED)


def verificar_requisitos(ruta: Path, perfil: Perfil,
                         requisitos: List[Requisito], archivo: Path,
                         resultado_tests: Optional[Dict[str, Any]] = None
                         ) -> Dict[str, Any]:
    """Contrasta requisitos contra evidencia estática y, opt-in, la suite.

    No toca el GLOBAL de las seis dimensiones: devuelve un informe aparte.
    ``CUMPLE`` solo se emite con la suite ejecutada y verde; ``CUBIERTO``
    declara evidencia estática y nunca se presenta como cumplimiento.
    """
    items = []
    resumen = {"cumple": 0, "cubierto": 0, "no_cumple": 0,
               "no_verificable": 0}
    claves = {"CUMPLE": "cumple", "CUBIERTO": "cubierto",
              "NO CUMPLE": "no_cumple", "NO VERIFICABLE": "no_verificable"}
    for req in requisitos:
        veredicto, motivo, observada, tipo = _verificar_requisito(
            ruta, perfil, req, resultado_tests)
        item = req.a_dict()
        item.update({
            "veredicto": veredicto,
            "motivo": motivo,
            "evidencia_observada": observada,
            "tipo_evidencia": tipo.value,
            "avisos": list(req.avisos) + _avisos_criterio(req.criterio),
        })
        items.append(item)
        resumen[claves[veredicto]] += 1

    no_verificado = []
    if resumen["cubierto"]:
        no_verificado.append(
            f"{resumen['cubierto']} requisito(s) CUBIERTO(S): evidencia "
            "estática declarada, no comportamiento verificado")
    if resumen["no_verificable"]:
        no_verificado.append(
            f"{resumen['no_verificable']} requisito(s) NO VERIFICABLE(S): "
            "revisar criterio o método")
    return {
        "archivo": _texto_legible(ruta, archivo),
        "total": len(items),
        "resumen": resumen,
        "afecta_global": False,
        "nota": "CUMPLE exige suite verde; CUBIERTO es solo evidencia "
                "estática; no afecta al GLOBAL",
        "items": items,
        "no_verificado": no_verificado,
    }


def evaluar(ruta: Path, con_red: bool = True,
            ejecutar_tests_flag: bool = False, llm=None,
            investigar: bool = False, search_api=None,
            requisitos_path: Optional[Path] = None) -> Dict[str, Any]:
    """Evalúa un proyecto y devuelve el informe completo (sin escribir nada).

    `ejecutar_tests_flag` es un opt-in EXPLÍCITO: es lo único que ejecuta código
    del proyecto evaluado (P0.8), siempre con el comando que el propio proyecto
    declara. `requisitos_path` activa el informe aparte de requisitos; no
    altera el GLOBAL de las seis dimensiones.
    """
    if not ruta.is_dir():
        raise ValueError(f"No es un directorio: {ruta}")
    if requisitos_path is not None:
        requisitos_path = Path(requisitos_path)
    requisitos = parsear_requisitos(requisitos_path) if requisitos_path else None
    perfil = analizar_perfil(ruta)
    py = perfil.py
    resultado_tests = ejecutar_tests(ruta) if ejecutar_tests_flag else None
    licencias_extra = licencias_no_runtime(perfil, con_red)
    dimensiones = [
        evaluar_funcionalidades(ruta, perfil),
        evaluar_calidad(ruta, perfil, ejecutar_tests_flag, resultado_tests),
        evaluar_vigencia(ruta, perfil, con_red),
        evaluar_herramientas(ruta, perfil, con_red),
        evaluar_inteligencia(ruta, perfil),
        evaluar_eficiencia(ruta, perfil),
    ]
    marcas_debiles, _ = aserciones_debiles(perfil.ruta, perfil.tests_py)
    if marcas_debiles:
        calidad = next((d for d in dimensiones if d.nombre == "calidad"), None)
        if calidad is not None:
            calidad.notas.append(
                f"aserciones débiles (informativas, no fallo): "
                f"{len(marcas_debiles)}; c5 no mide la fuerza de la suite")
    puntuaciones = [d.puntuacion for d in dimensiones
                    if d.puntuacion is not None]
    global_ = round(sum(puntuaciones) / len(puntuaciones), 3) \
        if puntuaciones else None
    no_verificado = []
    if not ejecutar_tests_flag:
        no_verificado.append(
            "la suite de tests NO se ejecuta (usa --ejecutar-tests para "
            "verificarla; P0.8: ejecutar código ajeno es opt-in)")
    if not con_red:
        no_verificado.append("versiones y licencias de dependencias no "
                             "consultadas (--sin-red)")
    no_aplicables = sum(len(d.no_aplica) for d in dimensiones)
    nota_no_aplicables = ""
    if no_aplicables:
        # N/A no es "no verificado": es un criterio que el perfil no puede
        # aplicar. Se declara en cobertura, no se suma a la evidencia no
        # verificada (antes inflaba [UNVERIFIED] sin ningún fallo real).
        nota_no_aplicables = (
            f"{no_aplicables} criterios declarados N/A por el perfil: no se "
            "cuentan como fallos (ver cobertura)")
    if not perfil.lenguajes:
        no_verificado.append("sin archivos de código detectados: cobertura vacía")
    requisitos_informe = None
    if requisitos is not None:
        requisitos_informe = verificar_requisitos(
            ruta, perfil, requisitos, requisitos_path, resultado_tests)
        no_verificado.extend(requisitos_informe["no_verificado"])
    tipos_evidencia = [h.tipo_evidencia for d in dimensiones
                       for h in d.hallazgos]
    tipos_evidencia.extend([EvidenceKind.UNVERIFIED] * len(no_verificado))
    evaluados = sum(len(d.criterios) for d in dimensiones)
    total_criterios = evaluados + no_aplicables
    ratio = round(evaluados / total_criterios, 3) if total_criterios else 0.0
    no_python = sorted(leng for leng in perfil.lenguajes
                       if leng.lower() not in ("python", "py"))
    comparable = ratio >= 0.8
    motivo_no_comparable = ""
    if not comparable:
        motivo_no_comparable = f"cobertura {ratio:.0%} < 80%"
        if no_python:
            motivo_no_comparable += (
                f"; {', '.join(no_python)} solo recibe señales genéricas")
    cobertura = {
        "criterios_evaluados": evaluados,
        "criterios_no_aplicables": no_aplicables,
        "ratio_evaluado": ratio,
        "nivel": "alta" if ratio >= 0.8 else ("media" if ratio >= 0.5 else "baja"),
        "comparable": comparable,
        "motivo_no_comparable": motivo_no_comparable,
        "nota_lenguajes": (
            f"Python: AST y criterios nativos; {', '.join(no_python)}: sin AST "
            "ni paridad, solo señales genéricas" if no_python
            else "Python: AST y criterios nativos"),
        "dimensiones_evaluadas": [d.nombre for d in dimensiones
                                  if d.puntuacion is not None],
        "dimensiones_no_aplicables": [d.nombre for d in dimensiones
                                      if d.puntuacion is None],
        "lenguajes": perfil.lenguajes,
        "nota_no_aplicables": nota_no_aplicables,
    }
    informe = {
        "schema_version": SCHEMA_VERSION,
        "ruta": str(ruta),
        "archivos_python": len(py),
        "lineas_python": sum(len(leer(p).splitlines()) for p in py),
        "perfil": perfil.a_dict(),
        "cobertura": cobertura,
        "dependencias": perfil.deps,
        "licencias_no_runtime": licencias_extra,
        "aserciones_debiles": marcas_debiles,
        "dimensiones": {d.nombre: d.a_dict() for d in dimensiones},
        "global": global_,
        "global_nota": "media de criterios aplicables: no es comparable entre "
                       "proyectos con coberturas distintas; revisar `cobertura`",
        "no_verificado": no_verificado,
        "evidencia": resumen_evidencias(tipos_evidencia),
    }
    informe["mejoras"] = proponer_mejoras(informe)
    if requisitos_informe is not None:
        informe["requisitos"] = requisitos_informe
    if llm is not None:
        informe["sintesis_llm"] = sintetizar_con_llm(informe, llm)
        preguntas = informe["sintesis_llm"]["preguntas_abiertas"]
        if investigar and preguntas:
            if search_api is None:
                from web_search import WikipediaSearchAPI
                search_api = WikipediaSearchAPI()
            informe["investigacion"] = investigar_preguntas(preguntas, search_api)
    return informe


def _etiqueta_global(cobertura: Dict[str, Any]) -> str:
    """Rótulo honesto: no llamar GLOBAL a una cobertura no comparable (R5)."""
    return "GLOBAL" if cobertura.get("comparable", True) \
        else "GLOBAL NO COMPARABLE"


def informe_texto(informe: Dict[str, Any]) -> List[str]:
    cobertura = informe.get("cobertura", {})
    lineas = [f"EVALUACIÓN DE PROYECTO (read-only): {informe['ruta']}",
              f"Python: {informe['archivos_python']} archivos / "
              f"{informe['lineas_python']} líneas",
              f"Cobertura: {cobertura.get('criterios_evaluados', '?')} criterios "
              f"evaluados, {cobertura.get('criterios_no_aplicables', '?')} N/A "
              f"(nivel {cobertura.get('nivel', '?')}); lenguajes: "
              f"{', '.join(cobertura.get('lenguajes', {})) or 'ninguno'}",
              ""]
    for nombre, datos in informe["dimensiones"].items():
        lineas.append(f"== {nombre.upper()} — "
                      f"{_puntuacion_texto(datos['puntuacion'])} ==")
        for criterio, ok in datos["criterios"].items():
            lineas.append(f"  [{'OK ' if ok else 'NO '}] {criterio}")
        for item in datos.get("no_aplica", []):
            lineas.append(f"  [N/A] {item['criterio']}: {item['motivo']}")
        for h in datos["hallazgos"]:
            marca = EvidenceKind(h["tipo_evidencia"]).marcador
            lineas.append(f"  {marca} ({h['severidad']}) {h['descripcion']} — {h['evidencia']}")
        for nota in datos["notas"]:
            lineas.append(f"  · {nota}")
        lineas.append("")
    lineas.append(f"{_etiqueta_global(cobertura)}: "
                  f"{_puntuacion_texto(informe['global'], 3)} "
                  f"(cobertura {cobertura.get('nivel', '?')}, "
                  f"{cobertura.get('ratio_evaluado', 0):.0%} de criterios)")
    if not cobertura.get("comparable", True):
        lineas.append(f"Aviso: {cobertura.get('motivo_no_comparable', '')}")
    if cobertura.get("nota_lenguajes"):
        lineas.append(f"Lenguajes: {cobertura['nota_lenguajes']}")
    lineas.append(f"Nota: {informe.get('global_nota', '')}")
    lineas.append(f"Evidencia: {formato_resumen(informe['evidencia'])}")
    extras = informe.get("licencias_no_runtime", [])
    if extras:
        lineas.append("")
        lineas.append("== LICENCIAS NO RUNTIME (informativas; no puntúan h5) ==")
        for item in extras:
            licencia = item.get("licencia") or "no verificable"
            lineas.append(f"  - {item['nombre']} [{item['ambito']}] {licencia} "
                          f"({item['procedencia']})")
    debiles = informe.get("aserciones_debiles", [])
    if debiles:
        lineas.append("")
        lineas.append("== ASERCIONES DÉBILES (informativas; no cambian c5) ==")
        for marca in debiles:
            lineas.append(f"  - {marca}")
    if "requisitos" in informe:
        reqs = informe["requisitos"]
        lineas.append("")
        lineas.append(f"== REQUISITOS ({reqs['archivo']}) — {reqs['total']} ==")
        for item in reqs["items"]:
            lineas.append(f"  [{item['veredicto']}] {item['id']} — "
                          f"{item['titulo']}")
            lineas.append(f"      criterio: {item['criterio']}")
            if item.get("evidencia_observada"):
                lineas.append(f"      evidencia: {item['evidencia_observada']}")
            lineas.append(f"      motivo: {item['motivo']}")
            for aviso in item.get("avisos", []):
                lineas.append(f"      aviso: {aviso}")
        resumen = reqs["resumen"]
        lineas.append(
            f"  Resumen: {resumen['cumple']} CUMPLE | "
            f"{resumen['cubierto']} CUBIERTO | "
            f"{resumen['no_cumple']} NO CUMPLE | "
            f"{resumen['no_verificable']} NO VERIFICABLE")
        lineas.append(f"  Nota: {reqs['nota']}")
    lineas.append("")
    lineas.extend(plan_texto(informe))
    lineas.append("== MEJORAS PROPUESTAS (por prioridad, con su verificación) ==")
    for m in informe["mejoras"]:
        lineas.append(f"  [{m['prioridad']:>5}] {m['dimension']}: {m['propuesta']}")
        lineas.append(f"          sitios: {m['sitios']} | esfuerzo: {m['esfuerzo']}")
        lineas.append(f"          verificación: {m['metrica']}")
    if "sintesis_llm" in informe:
        sintesis = informe["sintesis_llm"]
        lineas.append("")
        lineas.append(f"== PROPUESTAS DEL MODELO ({sintesis['modelo']}) — juicio, no "
                      f"medición; sin respaldo medido: {sintesis['sin_respaldo']} ==")
        for propuesta in sintesis["propuestas"]:
            marca = "con respaldo medido" if propuesta["con_respaldo"] else "SIN RESPALDO"
            lineas.append(f"  [{propuesta['dimension']}] {propuesta['propuesta']} "
                          f"({marca})")
            lineas.append(f"          por qué: {propuesta['por_que']}")
            lineas.append(f"          evidencia citada: {propuesta['evidencia']}")
            lineas.append(f"          verificación: {propuesta['como_verificar']}")
        if sintesis["preguntas_abiertas"]:
            lineas.append(f"  Preguntas abiertas (lo que el modelo declara NO saber): "
                          f"{len(sintesis['preguntas_abiertas'])}")
            for pregunta in sintesis["preguntas_abiertas"]:
                lineas.append(f"    · {pregunta}")
    if "investigacion" in informe:
        lineas.append("")
        lineas.append("== INVESTIGACIÓN DE LAS DUDAS (fuentes citadas, verificables) ==")
        for hallazgo in informe["investigacion"]:
            lineas.append(f"  ? {hallazgo['pregunta']}")
            if hallazgo.get("error"):
                lineas.append(f"    ERROR: {hallazgo['error']}")
            elif hallazgo.get("sin_resultados"):
                lineas.append("    sin resultados (se declara, no se inventa)")
            for fuente in hallazgo.get("fuentes", []):
                lineas.append(f"    - {fuente['titulo']}: {fuente['url']}")
    lineas.append("")
    nota_na = cobertura.get("nota_no_aplicables")
    if nota_na:
        lineas.append("No aplicable: " + nota_na)
    lineas.append("No verificado: " + "; ".join(informe["no_verificado"]))
    return lineas


def cargar_entorno_llm(dotenv_path: Optional[Path] = None) -> None:
    """Carga `.env` solo para los modos opt-in que llaman a un proveedor real.

    El resto del evaluador sigue siendo offline: no lee `.env` ni toca la red
    salvo que se pida `--sintesis-llm` o `--investigar`. El parámetro existe
    para poder probar la carga sin depender del `.env` real del repositorio.
    """
    from dotenv import load_dotenv

    load_dotenv(dotenv_path or (Path.cwd() / ".env"))


def main(argv: List[str] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evalúa un proyecto externo en 6 dimensiones (read-only).")
    parser.add_argument("ruta", help="ruta del proyecto a evaluar")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--sin-red", action="store_true",
                        help="omite la comprobación de versiones y licencias en PyPI")
    parser.add_argument("--ignorar", action="append", default=[],
                        metavar="DIRECTORIO",
                        help="directorio a excluir del análisis (repetible)")
    parser.add_argument("--ejecutar-tests", action="store_true",
                        help="EJECUTA el comando de tests declarado por el proyecto "
                             "(opt-in explícito: es lo único que corre código "
                             "ajeno, P0.8)")
    parser.add_argument("--requisitos", metavar="ARCHIVO", default=None,
                        help="verifica una lista de requisitos en Markdown "
                             "estructurado (opt-in, read-only; ver "
                             "docs/REQUISITOS.md)")
    parser.add_argument("--sintesis-llm", action="store_true",
                        help="pide a un LLM propuestas de FONDO a partir del informe "
                             "medido (opt-in; requiere key y red; coste 0 con :free)")
    parser.add_argument("--modelo", default=None,
                        help="modelo para la síntesis (defecto: el gratuito del proyecto)")
    parser.add_argument("--investigar", action="store_true",
                        help="resuelve las dudas del modelo con búsqueda real y cita "
                             "las fuentes (implica --sintesis-llm; requiere red)")
    args = parser.parse_args(argv)

    IGNORAR.update(args.ignorar)
    requisitos_path = None
    if args.requisitos:
        requisitos_path = Path(args.requisitos).resolve()
        if not requisitos_path.is_file():
            print(f"ERROR: no existe el archivo de requisitos: "
                  f"{requisitos_path}", file=sys.stderr)
            return 2

    llm = None
    if args.sintesis_llm or args.investigar:
        try:
            cargar_entorno_llm()
        except ImportError:
            print("ERROR: --sintesis-llm/--investigar requiere python-dotenv "
                  "para leer .env", file=sys.stderr)
            return 2
        if not os.environ.get("OPENROUTER_API_KEY"):
            print("ERROR: --sintesis-llm/--investigar requiere "
                  "OPENROUTER_API_KEY (en .env o en el entorno)",
                  file=sys.stderr)
            return 2
        from llm_providers import OpenRouterLLM
        llm = OpenRouterLLM(model=args.modelo) if args.modelo else OpenRouterLLM()

    try:
        informe = evaluar(Path(args.ruta).resolve(), con_red=not args.sin_red,
                          ejecutar_tests_flag=args.ejecutar_tests, llm=llm,
                          investigar=args.investigar,
                          requisitos_path=requisitos_path)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(informe, ensure_ascii=False, indent=2))
    else:
        print("\n".join(informe_texto(informe)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
