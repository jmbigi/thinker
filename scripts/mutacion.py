#!/usr/bin/env python3
"""Campaña de mutación separada para evaluador/preflight (R3).

Copia el proyecto a un temporal (sin `.env`, `.git`, artefactos ni cachés),
ajusta `[tool.mutmut]` para mutar solo el objetivo y ejecuta `mutmut`. No borra
el temporal: imprime su ruta para poder triajar los supervivientes.

Uso:
    python3 scripts/mutacion.py --objetivo preflight [--json] [--timeout 1200]
"""

import argparse
import collections
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
IGNORAR = {
    ".git", ".env", "mutants", "dist", "build", ".venv", "venv",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache",
    ".coverage", "htmlcov", ".mutmut-cache",
}
OBJETIVOS = {
    "preflight": {
        "source_paths": ["scripts/preflight.py"],
        "also_copy": ["evidence.py"],
        "seleccion": [
            "tests/test_preflight.py",
            "--deselect=tests/test_preflight.py::TestPreflight::"
            "test_el_repositorio_real_pasa_su_propio_preflight",
        ],
    },
    "evaluar": {
        "source_paths": ["evaluar_proyecto.py"],
        "also_copy": ["evidence.py", "scripts"],
        "seleccion": [
            "tests/test_evaluar_proyecto.py",
            "tests/test_evaluador_corpus.py",
            "tests/test_evaluador_precision.py",
            "--deselect=tests/test_evaluar_proyecto.py::"
            "TestAutoevaluacionDeThinker",
            "--deselect=tests/test_evaluar_proyecto.py::"
            "TestCoberturaDeRamasDelEvaluador::"
            "test_informe_texto_renderiza_requisitos_sintesis_e_investigacion",
        ],
    },
}


def _ignorar(_directorio, nombres):
    return [n for n in nombres
            if n in IGNORAR or n.endswith((".pyc", ".egg-info"))]


def configurar(texto, objetivo):
    """Devuelve el pyproject con source_paths y selección del objetivo."""
    datos = OBJETIVOS[objetivo]
    texto = re.sub(r"source_paths = \[.*?\]",
                   "source_paths = " + json.dumps(datos["source_paths"]),
                   texto, flags=re.S)
    copia = "also_copy = " + json.dumps(datos["also_copy"], indent=4)
    if re.search(r"^also_copy\s*=", texto, re.M):
        texto = re.sub(r"also_copy = \[.*?\]", copia, texto, flags=re.S)
    else:
        texto = texto.replace("[tool.mutmut]\n",
                              "[tool.mutmut]\n" + copia + "\n", 1)
    return re.sub(r"pytest_add_cli_args_test_selection = \[.*?\]",
                  "pytest_add_cli_args_test_selection = "
                  + json.dumps(datos["seleccion"], indent=4),
                  texto, flags=re.S)


def parsear_resultados(texto):
    """Cuenta estados de `mutmut results --all true` y calcula la tasa."""
    estados = collections.Counter()
    for linea in texto.splitlines():
        for estado in ("killed", "survived", "no tests", "timeout",
                       "suspicious", "skipped", "caught by type check"):
            if linea.strip().endswith(": " + estado):
                estados[estado] += 1
    total = sum(estados.values())
    ejecutados = total - estados["no tests"]
    tasa = (estados["killed"] / ejecutados) if ejecutados else None
    return {
        "total": total,
        "killed": estados["killed"],
        "survived": estados["survived"],
        "no_tests": estados["no tests"],
        "timeout": estados["timeout"],
        "suspicious": estados["suspicious"],
        "tasa_sin_no_tests": round(tasa, 4) if tasa is not None else None,
    }


def copiar_proyecto(destino):
    """Copia el árbol de trabajo sin secretos ni artefactos."""
    shutil.copytree(RAIZ, destino, ignore=_ignorar, dirs_exist_ok=True)


def ejecutar(objetivo, timeout=1200):
    destino = Path(tempfile.mkdtemp(prefix=f"mut-{objetivo}-"))
    copiar_proyecto(destino)
    pyproject = destino / "pyproject.toml"
    pyproject.write_text(
        configurar(pyproject.read_text(encoding="utf-8"), objetivo),
        encoding="utf-8")
    proceso = subprocess.run(
        [sys.executable, "-m", "mutmut", "run", "--max-children", "4"],
        cwd=destino, capture_output=True, text=True, timeout=timeout)
    resultados = subprocess.run(
        [sys.executable, "-m", "mutmut", "results", "--all", "true"],
        cwd=destino, capture_output=True, text=True, timeout=120)
    resumen = parsear_resultados(resultados.stdout + resultados.stderr)
    resumen.update({
        "objetivo": objetivo,
        "temporal": str(destino),
        "exit": proceso.returncode,
    })
    return resumen


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--objetivo", choices=sorted(OBJETIVOS), required=True)
    parser.add_argument("--timeout", type=int, default=1200)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        resultado = ejecutar(args.objetivo, args.timeout)
    except subprocess.TimeoutExpired:
        print(f"MUTACIÓN: timeout de {args.timeout}s", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
    else:
        print(f"Mutación {resultado['objetivo']}: {resultado['total']} mutantes, "
              f"{resultado['killed']} muertos, {resultado['survived']} "
              f"supervivientes, {resultado['no_tests']} sin tests")
        print(f"Temporal: {resultado['temporal']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
