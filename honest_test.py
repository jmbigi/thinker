#!/usr/bin/env python3
"""Honest test: verificación real de los sistemas integrados (offline).

Cada test ejecuta de verdad y reporta PASS/FAIL según evidencia.
Sin red ni API keys: usa MockLLM. Sale con código 1 si algo falla.
"""
import ast
import sys

sys.path.insert(0, '.')
results = []


def check(name, fn):
    try:
        fn()
        results.append((name, True, ""))
        print(f"PASS: {name}")
    except Exception as e:
        results.append((name, False, f"{type(e).__name__}: {e}"))
        print(f"FAIL: {name} -> {type(e).__name__}: {e}")


def t1():
    for f in ["deep_research_system.py", "pensamiento_layer.py", "code_design_improvement_tools.py"]:
        with open(f, encoding="utf-8") as fh:
            ast.parse(fh.read(), filename=f)
check("1. Sintaxis válida en los 3 módulos", t1)


def t2():
    from deep_research_system import (OpenAILLM, OpenRouterLLM, OllamaLLM,
                                      KiloGatewayLLM, MockLLM, MockSearchAPI,
                                      ResearchOrchestrator)
    from pensamiento_layer import DeepResearchThinkingLayer
    from code_design_improvement_tools import CodeDesignThinker, analyze_python_source
    assert all(x is not None for x in (
        OpenAILLM, OpenRouterLLM, OllamaLLM, KiloGatewayLLM, MockLLM,
        MockSearchAPI, ResearchOrchestrator, DeepResearchThinkingLayer,
        CodeDesignThinker, analyze_python_source))
check("2. Imports de clases principales", t2)


def t3():
    from deep_research_system import MockLLM, MockSearchAPI, ResearchOrchestrator
    report, ctx = ResearchOrchestrator(MockLLM(), MockSearchAPI()).research("pregunta de prueba")
    assert report and "Informe" in report, "reporte vacío"
    assert ctx.subquestions, "sin subpreguntas"
    assert ctx.claims, "sin claims extraídos"
    assert ctx.evaluations, "sin evaluaciones"
check("3. Pipeline de investigación end-to-end (MockLLM)", t3)


def t4():
    from pensamiento_layer import DeepResearchThinkingLayer
    from deep_research_system import MockLLM
    r = DeepResearchThinkingLayer(MockLLM()).think("¿pregunta de prueba?")
    assert r["valid"] and r["step_count"] == 7, f"ciclo inválido: {r.get('error')}"
check("4. ThinkingLayer ejecuta 7 pasos válidos", t4)


def t5():
    from code_design_improvement_tools import analyze_python_source
    a = analyze_python_source("import os, sys\n\ndef f():\n    return 1\n")
    assert a["source_summary"]["functions"] == 1
    assert any("importaciones múltiples" in i["description"] for i in a["metrics"]["issues"]), \
        "no detectó la importación múltiple"
check("5. Análisis estático detecta issues reales", t5)


def t6():
    import os
    assert os.path.exists(".env"), ".env no encontrado"
check("6. .env presente (contenido NO inspeccionado, P0.6)", t6)


print("\n" + "=" * 50)
passed = sum(1 for _, ok, _ in results if ok)
print(f"RESULTADO HONESTO: {passed}/{len(results)} tests pasaron")
for name, ok, err in results:
    print(f"  {'✓' if ok else '✗'} {name}" + (f" — {err}" if err else ""))
sys.exit(0 if passed == len(results) else 1)
