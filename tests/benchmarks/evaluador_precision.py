#!/usr/bin/env python3
"""Benchmark offline de precisión/recall del evaluador (R4).

Casos sintéticos con un criterio objetivo y un resultado esperado (hallazgo
presente/ausente). No sustituye una campaña sobre proyectos reales: mide que el
detector no haya involucionado y hace explícita la cobertura (5 criterios, no
los 29 del rubric).

Uso:
    python3 tests/benchmarks/evaluador_precision.py [--json]
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from evaluar_proyecto import evaluar  # noqa: E402

# Cada caso declara un criterio objetivo. Los demás hallazgos se ignoran: el
# benchmark mide el criterio, no la limpieza global de la fixture.
CASOS = [
    {
        "nombre": "h2_sin_licencia",
        "criterio": "h2_licencia",
        "esperado": True,
        "archivos": {
            "demo.py": "def f():\n    return 1\n",
            "pyproject.toml": '[project]\nname = "demo"\nversion = "0.1.0"\n',
        },
    },
    {
        "nombre": "h2_con_licencia",
        "criterio": "h2_licencia",
        "esperado": False,
        "archivos": {
            "demo.py": "def f():\n    return 1\n",
            "pyproject.toml": '[project]\nname = "demo"\nversion = "0.1.0"\n',
            "LICENSE": "MIT\n",
        },
    },
    {
        "nombre": "c5_test_noop",
        "criterio": "c5_tests_con_aserciones",
        "esperado": True,
        "archivos": {
            "demo.py": "def f():\n    return 1\n",
            "tests/test_x.py": (
                "import unittest\n\n\n"
                "class TestX(unittest.TestCase):\n"
                "    def test_a(self):\n"
                "        pass\n"),
        },
    },
    {
        "nombre": "c5_test_con_asercion",
        "criterio": "c5_tests_con_aserciones",
        "esperado": False,
        "archivos": {
            "demo.py": "def f():\n    return 1\n",
            "tests/test_x.py": (
                "import unittest\n\n\n"
                "class TestX(unittest.TestCase):\n"
                "    def test_a(self):\n"
                "        self.assertEqual(f(), 1)\n"),
        },
    },
    {
        "nombre": "f3_todo_en_produccion",
        "criterio": "f3_sin_deuda_declarada",
        "esperado": True,
        "archivos": {
            "demo.py": "def f():\n    # TODO: arreglar\n    return 1\n",
            "pyproject.toml": '[project]\nname = "demo"\nversion = "0.1.0"\n',
        },
    },
    {
        "nombre": "f3_sin_todo",
        "criterio": "f3_sin_deuda_declarada",
        "esperado": False,
        "archivos": {
            "demo.py": "def f():\n    return 1\n",
            "pyproject.toml": '[project]\nname = "demo"\nversion = "0.1.0"\n',
        },
    },
    {
        "nombre": "c3_silencio_except_pass",
        "criterio": "c3_sin_silencios",
        "esperado": True,
        "archivos": {
            "demo.py": ("def f():\n"
                        "    try:\n"
                        "        return 1\n"
                        "    except Exception:\n"
                        "        pass\n"),
            "pyproject.toml": '[project]\nname = "demo"\nversion = "0.1.0"\n',
        },
    },
    {
        "nombre": "c3_sin_silencios",
        "criterio": "c3_sin_silencios",
        "esperado": False,
        "archivos": {
            "demo.py": "def f():\n    return 1\n",
            "pyproject.toml": '[project]\nname = "demo"\nversion = "0.1.0"\n',
        },
    },
    {
        "nombre": "h6_import_sin_declarar",
        "criterio": "h6_imports_declarados",
        "esperado": True,
        "archivos": {
            "demo.py": "import requests\n\n\ndef f():\n    return requests\n",
            "pyproject.toml": '[project]\nname = "demo"\nversion = "0.1.0"\n',
        },
    },
    {
        "nombre": "h6_import_declarado",
        "criterio": "h6_imports_declarados",
        "esperado": False,
        "archivos": {
            "demo.py": "import requests\n\n\ndef f():\n    return requests\n",
            "requirements.txt": "requests==2.31.0\n",
        },
    },
    {
        "nombre": "c2_sin_linter",
        "criterio": "c2_linter_configurado",
        "esperado": True,
        "archivos": {
            "demo.py": "def f():\n    return 1\n",
            "pyproject.toml": '[project]\nname = "demo"\nversion = "0.1.0"\n',
        },
    },
    {
        "nombre": "c2_con_ruff",
        "criterio": "c2_linter_configurado",
        "esperado": False,
        "archivos": {
            "demo.py": "def f():\n    return 1\n",
            "pyproject.toml": ('[project]\nname = "demo"\nversion = "0.1.0"\n'
                               '[tool.ruff]\nline-length = 100\n'),
        },
    },
    {
        "nombre": "v2_sin_lock",
        "criterio": "v2_lockfile",
        "esperado": True,
        "archivos": {
            "demo.py": "def f():\n    return 1\n",
            "requirements.txt": "requests==2.31.0\n",
        },
    },
    {
        "nombre": "v2_con_lock",
        "criterio": "v2_lockfile",
        "esperado": False,
        "archivos": {
            "demo.py": "def f():\n    return 1\n",
            "requirements.txt": "requests==2.31.0\n",
            "requirements.lock": "requests==2.31.0 --hash=sha256:abc\n",
        },
    },
    {
        "nombre": "h3_sin_ci",
        "criterio": "h3_verificacion_automatizada",
        "esperado": True,
        "archivos": {
            "demo.py": "def f():\n    return 1\n",
            "pyproject.toml": '[project]\nname = "demo"\nversion = "0.1.0"\n',
        },
    },
    {
        "nombre": "h3_con_ci",
        "criterio": "h3_verificacion_automatizada",
        "esperado": False,
        "archivos": {
            "demo.py": "def f():\n    return 1\n",
            "pyproject.toml": '[project]\nname = "demo"\nversion = "0.1.0"\n',
            ".github/workflows/ci.yml": "name: ci\n",
        },
    },
    {
        "nombre": "h1_sin_manifiesto",
        "criterio": "h1_manifiesto",
        "esperado": True,
        "archivos": {
            "demo.py": "def f():\n    return 1\n",
        },
    },
    {
        "nombre": "h1_con_manifiesto",
        "criterio": "h1_manifiesto",
        "esperado": False,
        "archivos": {
            "demo.py": "def f():\n    return 1\n",
            "pyproject.toml": '[project]\nname = "demo"\nversion = "0.1.0"\n',
        },
    },
]


def calcular_metricas(esperados, predichos):
    """TP/FP/FN y precision/recall; ``None`` si no hay denominador."""
    tp = sum(1 for esperado, predicho in zip(esperados, predichos)
             if esperado and predicho)
    fp = sum(1 for esperado, predicho in zip(esperados, predichos)
             if not esperado and predicho)
    fn = sum(1 for esperado, predicho in zip(esperados, predichos)
             if esperado and not predicho)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    return {"tp": tp, "fp": fp, "fn": fn,
            "precision": precision, "recall": recall}


def _tiene_hallazgo(informe, criterio):
    return any(h["criterio"] == criterio
               for dimension in informe["dimensiones"].values()
               for h in dimension["hallazgos"])


def evaluar_corpus(casos=None):
    """Ejecuta los casos y devuelve métricas por criterio y globales."""
    casos = CASOS if casos is None else casos
    resultados = []
    for caso in casos:
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            for nombre, contenido in caso["archivos"].items():
                ruta = raiz / nombre
                ruta.parent.mkdir(parents=True, exist_ok=True)
                ruta.write_text(contenido, encoding="utf-8")
            informe = evaluar(raiz, con_red=False)
        predicho = _tiene_hallazgo(informe, caso["criterio"])
        resultados.append({
            "caso": caso["nombre"],
            "criterio": caso["criterio"],
            "esperado": caso["esperado"],
            "predicho": predicho,
        })

    criterios = sorted({r["criterio"] for r in resultados})
    por_criterio = {}
    for criterio in criterios:
        propios = [r for r in resultados if r["criterio"] == criterio]
        por_criterio[criterio] = calcular_metricas(
            [r["esperado"] for r in propios],
            [r["predicho"] for r in propios])
    global_ = calcular_metricas(
        [r["esperado"] for r in resultados],
        [r["predicho"] for r in resultados])
    return {
        "casos": len(resultados),
        "criterios": len(criterios),
        "criterios_objetivo": criterios,
        "resultados": resultados,
        "por_criterio": por_criterio,
        "global": global_,
        "cobertura": (
            f"{len(criterios)} criterios objetivo de 29 posibles; "
            "no es una campaña sobre proyectos reales"),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true",
                        help="salida JSON en vez de tabla")
    args = parser.parse_args(argv)
    resultado = evaluar_corpus()
    if args.json:
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
        return 0
    print(f"BENCHMARK EVALUADOR: {resultado['casos']} casos, "
          f"{resultado['criterios']} criterios")
    print(f"{'criterio':35} {'TP':>3} {'FP':>3} {'FN':>3} "
          f"{'precision':>10} {'recall':>8}")
    for criterio, metrica in resultado["por_criterio"].items():
        precision = "-" if metrica["precision"] is None \
            else f"{metrica['precision']:.2f}"
        recall = "-" if metrica["recall"] is None \
            else f"{metrica['recall']:.2f}"
        print(f"{criterio:35} {metrica['tp']:>3} {metrica['fp']:>3} "
              f"{metrica['fn']:>3} {precision:>10} {recall:>8}")
    global_ = resultado["global"]
    print(f"{'GLOBAL':35} {global_['tp']:>3} {global_['fp']:>3} "
          f"{global_['fn']:>3} "
          f"{global_['precision']:.2f} {global_['recall']:.2f}")
    print("Cobertura:", resultado["cobertura"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
