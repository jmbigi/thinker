#!/usr/bin/env python3
"""Holdout sintético del evaluador: discriminación entre proyectos completos,
deficientes, engañosos y grandes sin calidad.

No es una validación humana independiente ni una campaña sobre repositorios
reales. Es un conjunto **fijado antes de medir** con relaciones de orden
esperadas; si el evaluador confunde documentación con calidad o tamaño con
calidad, el holdout lo muestra. Las fixtures son sintéticas y se declaran.

Uso:
    python3 -m tests.benchmarks.evaluador_holdout [--json]
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

from evaluar_proyecto import evaluar

BASE_COMPLETA = {
    "demo.py": (
        "import json\n"
        "from functools import lru_cache\n\n\n"
        "@lru_cache(maxsize=8)\n"
        "def f(timeout=5, max_retries=3):\n"
        "    return json.loads('{\"ok\": true}')\n\n\n"
        "def cargar():\n"
        "    import torch\n"
        "    return torch\n\n\n"
        "def main():\n"
        "    return f()\n"
    ),
    "pyproject.toml": (
        '[project]\nname = "demo"\nversion = "0.1.0"\n'
        '[project.scripts]\ndemo = "demo:main"\n'
        '[tool.ruff]\nline-length = 100\n'
    ),
    "README.md": (
        "# Demo\n\nEjecuta `demo.py`. Latencia medida: 1.5 s. "
        "Benchmark local reproducible. # mock declarado\n"
    ),
    "LICENSE": "MIT\n",
    "requirements.txt": "requests==2.31.0\ntorch==2.0.0\n",
    "requirements.lock": (
        "requests==2.31.0 --hash=sha256:abc\n"
        "torch==2.0.0 --hash=sha256:def\n"
    ),
    ".github/workflows/ci.yml": "name: ci\n",
    "Makefile": "test:\n\tpython -m unittest discover -s tests\n",
    "docs/decisiones.md": "# Decisiones\n",
    "tests/test_a.py": (
        "import unittest\nfrom demo import f\n\n\n"
        "class TestA(unittest.TestCase):\n"
        "    def test_f(self):\n"
        "        self.assertTrue(f()['ok'])\n"
    ),
    "tests/test_b.py": (
        "import unittest\nfrom demo import f\n\n\n"
        "class TestB(unittest.TestCase):\n"
        "    def test_f(self):\n"
        "        self.assertEqual(f()['ok'], True)\n"
    ),
}

CASOS = [
    {
        "nombre": "completo",
        "archivos": BASE_COMPLETA,
        "esperado": {"global_min": 0.8},
    },
    {
        "nombre": "deficiente",
        "archivos": {
            "demo.py": "def f():\n    # TODO: arreglar\n    return 1\n",
        },
        "esperado": {"global_max": 0.5},
    },
    {
        "nombre": "readme_enganoso",
        "archivos": {
            "demo.py": "def f():\n    # TODO: arreglar\n    return 1\n",
            "README.md": (
                "# Proyecto excelente\n\nCobertura 100%, tests completos, "
                "CI en la nube y licencia MIT. Ejecuta `demo.py`.\n"
            ),
        },
        "esperado": {"global_max": 0.6, "menor_que": "completo"},
    },
    {
        "nombre": "grande_vacio",
        "archivos": {
            **{f"modulo_{i}.py": f"def f{i}():\n    return {i}\n"
               for i in range(30)},
            "README.md": "# Grande\n",
        },
        "esperado": {"global_max": 0.6, "menor_que": "pequeno_completo"},
    },
    {
        "nombre": "pequeno_completo",
        "archivos": BASE_COMPLETA,
        "esperado": {"global_min": 0.8},
    },
    {
        "nombre": "tests_noop",
        "archivos": {
            **BASE_COMPLETA,
            "tests/test_a.py": (
                "import unittest\n\n\n"
                "class TestA(unittest.TestCase):\n"
                "    def test_f(self):\n"
                "        pass\n"
            ),
            "tests/test_b.py": (
                "import unittest\n\n\n"
                "class TestB(unittest.TestCase):\n"
                "    def test_f(self):\n"
                "        pass\n"
            ),
        },
        "esperado": {"global_max": 0.9, "menor_que": "completo"},
    },
]


def _crear_git(raiz: Path) -> None:
    fecha = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    entorno = {
        **os.environ,
        "GIT_AUTHOR_DATE": fecha, "GIT_COMMITTER_DATE": fecha,
        "GIT_AUTHOR_NAME": "Holdout", "GIT_AUTHOR_EMAIL": "holdout@example.invalid",
        "GIT_COMMITTER_NAME": "Holdout",
        "GIT_COMMITTER_EMAIL": "holdout@example.invalid",
    }
    for comando in (["git", "init", "-q"], ["git", "add", "-A"],
                    ["git", "commit", "-qm", "inicio"]):
        subprocess.run(comando, cwd=raiz, check=True, capture_output=True,
                       env=entorno)


def evaluar_caso(caso: Dict[str, Any]) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        raiz = Path(tmp)
        for nombre, contenido in caso["archivos"].items():
            ruta = raiz / nombre
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_text(contenido, encoding="utf-8")
        _crear_git(raiz)
        informe = evaluar(raiz, con_red=False)
    return {
        "nombre": caso["nombre"],
        "global": informe["global"],
        "cobertura": informe["cobertura"]["ratio_evaluado"],
        "criterios_fallidos": sorted(
            criterio
            for dimension in informe["dimensiones"].values()
            for criterio, ok in dimension["criterios"].items() if not ok
        ),
    }


def evaluar_holdout(casos: List[Dict[str, Any]] = CASOS) -> Dict[str, Any]:
    resultados = [evaluar_caso(caso) for caso in casos]
    por_nombre = {resultado["nombre"]: resultado for resultado in resultados}
    comprobaciones = []
    for caso in casos:
        resultado = por_nombre[caso["nombre"]]
        esperado = caso["esperado"]
        if "global_min" in esperado:
            comprobaciones.append({
                "caso": caso["nombre"],
                "tipo": "global_min",
                "esperado": esperado["global_min"],
                "obtenido": resultado["global"],
                "cumple": (resultado["global"] or 0) >= esperado["global_min"],
            })
        if "global_max" in esperado:
            comprobaciones.append({
                "caso": caso["nombre"],
                "tipo": "global_max",
                "esperado": esperado["global_max"],
                "obtenido": resultado["global"],
                "cumple": (resultado["global"] or 1) <= esperado["global_max"],
            })
        if "menor_que" in esperado:
            otro = por_nombre[esperado["menor_que"]]
            comprobaciones.append({
                "caso": caso["nombre"],
                "tipo": "menor_que",
                "esperado": esperado["menor_que"],
                "obtenido": [resultado["global"], otro["global"]],
                "cumple": (resultado["global"] or 0) < (otro["global"] or 0),
            })
    aprobadas = sum(1 for comprobacion in comprobaciones
                    if comprobacion["cumple"])
    return {
        "casos": len(resultados),
        "resultados": resultados,
        "comprobaciones": comprobaciones,
        "aprobadas": aprobadas,
        "total": len(comprobaciones),
        "exactitud": round(aprobadas / len(comprobaciones), 3)
        if comprobaciones else None,
        "metodo": ("holdout sintético con relaciones de orden; no sustituye "
                   "una evaluación humana independiente ni repositorios reales"),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    resultado = evaluar_holdout()
    if args.json:
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
        return 0
    print(f"HOLDOUT EVALUADOR: {resultado['casos']} casos, "
          f"{resultado['aprobadas']}/{resultado['total']} comprobaciones")
    for fila in resultado["resultados"]:
        print(f"  {fila['nombre']:18s} global={fila['global']:.3f} "
              f"cobertura={fila['cobertura']:.0%} "
              f"fallos={len(fila['criterios_fallidos'])}")
    for comprobacion in resultado["comprobaciones"]:
        marca = "OK" if comprobacion["cumple"] else "NO"
        print(f"  [{marca}] {comprobacion['caso']} {comprobacion['tipo']} "
              f"esperado={comprobacion['esperado']} "
              f"obtenido={comprobacion['obtenido']}")
    print(resultado["metodo"])
    return 0 if resultado["aprobadas"] == resultado["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
