#!/usr/bin/env python3
"""Benchmark offline de precisión/recall del evaluador (R4).

Casos sintéticos con un criterio objetivo y un resultado esperado (hallazgo
presente/ausente). No sustituye una campaña sobre proyectos reales: mide que el
detector no haya involucionado y hace explícita la cobertura (16 de los 29
criterios del rubric; los 13 restantes se declaran N/A en el informe).

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
    {
        "nombre": "f2_readme_roto",
        "criterio": "f2_readme_vs_realidad",
        "esperado": True,
        "archivos": {
            "demo.py": "def f():\n    return 1\n",
            "README.md": "# Demo\n\nEjecuta `inexistente.py`.\n",
        },
    },
    {
        "nombre": "f2_readme_ok",
        "criterio": "f2_readme_vs_realidad",
        "esperado": False,
        "archivos": {
            "demo.py": "def f():\n    return 1\n",
            "README.md": "# Demo\n\nEjecuta `demo.py`.\n",
        },
    },
    {
        "nombre": "f4_un_solo_test",
        "criterio": "f4_tests_de_varios_modulos",
        "esperado": True,
        "archivos": {
            "demo.py": "def f():\n    return 1\n",
            "tests/test_a.py": (
                "import unittest\n\n\n"
                "class T(unittest.TestCase):\n"
                "    def test_a(self):\n"
                "        self.assertEqual(f(), 1)\n"),
        },
    },
    {
        "nombre": "f4_dos_modulos",
        "criterio": "f4_tests_de_varios_modulos",
        "esperado": False,
        "archivos": {
            "demo.py": "def f():\n    return 1\n",
            "tests/test_a.py": (
                "import unittest\n\n\n"
                "class T(unittest.TestCase):\n"
                "    def test_a(self):\n"
                "        self.assertEqual(f(), 1)\n"),
            "tests/test_b.py": (
                "import unittest\n\n\n"
                "class U(unittest.TestCase):\n"
                "    def test_b(self):\n"
                "        self.assertEqual(f(), 1)\n"),
        },
    },
    {
        "nombre": "v1_sin_fijar",
        "criterio": "v1_dependencias_fijadas",
        "esperado": True,
        "archivos": {
            "demo.py": "def f():\n    return 1\n",
            "requirements.txt": "requests>=2.0\n",
        },
    },
    {
        "nombre": "v1_fijado",
        "criterio": "v1_dependencias_fijadas",
        "esperado": False,
        "archivos": {
            "demo.py": "def f():\n    return 1\n",
            "requirements.txt": "requests==2.31.0\n",
        },
    },
    {
        "nombre": "c1_sin_tests",
        "criterio": "c1_suite_de_tests",
        "esperado": True,
        "archivos": {
            "demo.py": "def f():\n    return 1\n",
            "pyproject.toml": '[project]\nname = "demo"\nversion = "0.1.0"\n',
        },
    },
    {
        "nombre": "c1_con_tests",
        "criterio": "c1_suite_de_tests",
        "esperado": False,
        "archivos": {
            "demo.py": "def f():\n    return 1\n",
            "tests/test_a.py": (
                "import unittest\n\n\n"
                "class T(unittest.TestCase):\n"
                "    def test_a(self):\n"
                "        self.assertEqual(f(), 1)\n"),
        },
    },
    {
        "nombre": "h7_sin_registro",
        "criterio": "h7_decisiones_documentadas",
        "esperado": True,
        "archivos": {
            "demo.py": "def f():\n    return 1\n",
            "pyproject.toml": '[project]\nname = "demo"\nversion = "0.1.0"\n',
        },
    },
    {
        "nombre": "h7_con_registro",
        "criterio": "h7_decisiones_documentadas",
        "esperado": False,
        "archivos": {
            "demo.py": "def f():\n    return 1\n",
            "pyproject.toml": '[project]\nname = "demo"\nversion = "0.1.0"\n',
            "docs/decisiones.md": "# Decisiones\n",
        },
    },

    {
        "nombre": "trampa_h6_import_en_docs",
        "criterio": "h6_imports_declarados",
        "esperado": False,
        "archivos": {
            "demo.py": "def f():\n    return 1\n",
            "README.md": "```python\nimport requests\n```\n",
        },
    },
    {
        "nombre": "trampa_h6_import_opcional",
        "criterio": "h6_imports_declarados",
        "esperado": False,
        "archivos": {
            "demo.py": ("try:\n"
                        "    import requests\n"
                        "except ImportError:\n"
                        "    pass\n"),
            "pyproject.toml": '[project]\nname = "demo"\nversion = "0.1.0"\n',
        },
    },
    {
        "nombre": "trampa_c3_except_con_return",
        "criterio": "c3_sin_silencios",
        "esperado": False,
        "archivos": {
            "demo.py": ("def f():\n"
                        "    try:\n"
                        "        return 1\n"
                        "    except Exception:\n"
                        "        return 0\n"),
        },
    },
    {
        "nombre": "trampa_f3_todo_en_tests",
        "criterio": "f3_sin_deuda_declarada",
        "esperado": False,
        "archivos": {
            "demo.py": "def f():\n    return 1\n",
            "tests/test_x.py": "# TODO: esto es un test, no producción\n",
        },
    },
    {
        "nombre": "trampa_c5_helper_sin_assert",
        "criterio": "c5_tests_con_aserciones",
        "esperado": False,
        "archivos": {
            "demo.py": "def f():\n    return 1\n",
            "tests/test_x.py": ("import unittest\n"
                                "from demo import f\n\n\n"
                                "class T(unittest.TestCase):\n"
                                "    def test_a(self):\n"
                                "        f()\n"),
        },
    },
    {
        "nombre": "c4_pocos_tests_para_el_codigo",
        "criterio": "c4_tests_sobre_codigo_30pct",
        "esperado": True,
        "archivos": {
            "demo.py": ("def f():\n"
                        "    return 1\n\n"
                        "def g():\n"
                        "    return 2\n\n"
                        "def h():\n"
                        "    return 3\n\n"
                        "def i():\n"
                        "    return 4\n"),
            "tests/test_x.py": "x = 1\n",
        },
    },
    {
        "nombre": "c4_suficientes_tests",
        "criterio": "c4_tests_sobre_codigo_30pct",
        "esperado": False,
        "archivos": {
            "demo.py": "def f():\n    return 1\n",
            "tests/test_x.py": ("import unittest\n"
                                "from demo import f\n\n\n"
                                "class T(unittest.TestCase):\n"
                                "    def test_a(self):\n"
                                "        self.assertEqual(f(), 1)\n"),
        },
    },
    {
        "nombre": "h4_tests_sin_runner",
        "criterio": "h4_runner_de_tests_declarado",
        "esperado": True,
        "archivos": {
            "demo.py": "def f():\n    return 1\n",
            "test_app.py": ("def test_a():\n"
                            "    assert 1 == 1\n"),
        },
    },
    {
        "nombre": "h4_con_build_sh",
        "criterio": "h4_runner_de_tests_declarado",
        "esperado": False,
        "archivos": {
            "demo.py": "def f():\n    return 1\n",
            "test_app.py": ("def test_a():\n"
                            "    assert 1 == 1\n"),
            "build.sh": "#!/bin/sh\npython3 -m unittest\n",
        },
    },

]


CRITERIOS_FUERA_DE_BENCHMARK = {
    "f1_puntos_de_entrada": "requiere un punto de entrada real o perfil de aplicación",
    "v3_actividad_reciente": "requiere historial git con fechas reales",
    "v4_dependencias_al_dia": "requiere consultar PyPI (red)",
    "h5_licencias_libres": "requiere consultar metadatos de licencias (red)",
    "i1_cachea_trabajo_repetido": "requiere un proyecto con LLM declarado",
    "i2_timeouts_explicitos": "requiere un proyecto con LLM declarado",
    "i3_reintentos_con_limite": "requiere un proyecto con LLM declarado",
    "i4_valida_respuestas": "requiere un proyecto con LLM declarado",
    "i5_declara_lo_simulado": "requiere un proyecto con LLM declarado",
    "i6_metricas_propias": "requiere un proyecto con LLM declarado",
    "e1_import_perezoso_de_pesadas": "requiere un proyecto con LLM declarado",
    "e2_carga_unica_de_modelos": "requiere un proyecto con LLM declarado",
    "e3_mediciones_documentadas": "requiere un proyecto con LLM declarado y métricas",
}


def cobertura_de_criterios(casos=None):
    """Devuelve medidos, N/A y el total base de 29 criterios."""
    casos = CASOS if casos is None else casos
    medidos = sorted({c["criterio"] for c in casos})
    no_medidos = sorted(CRITERIOS_FUERA_DE_BENCHMARK)
    return {
        "medidos": medidos,
        "no_medidos": no_medidos,
        "total_base": len(medidos) + len(no_medidos),
        "solapados": sorted(set(medidos) & set(no_medidos)),
    }


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
