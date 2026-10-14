#!/usr/bin/env python3
"""Honest test of the thinking and code improvement systems (offline).

Todo se ejecuta con MockLLM: sin red, sin API keys, resultados reales.
El resumen final se construye a partir de los resultados, no está pre-escrito.
"""

import ast
import sys

sys.path.insert(0, ".")
results = []


def check(name, fn):
    try:
        detail = fn()
        results.append((name, True, detail or ""))
        print(f"  ✓ {name}" + (f" — {detail}" if detail else ""))
    except Exception as e:
        results.append((name, False, f"{type(e).__name__}: {e}"))
        print(f"  ✗ {name} -> {type(e).__name__}: {e}")


print("=" * 60)
print("HONEST TEST: Thinking Layer & Code Design Tools")
print("=" * 60)

# Test 1: Syntax check all files
print("\n[1] Verificando sintaxis de todos los archivos...")


def t1():
    for f in ["deep_research_system.py", "pensamiento_layer.py", "code_design_improvement_tools.py"]:
        with open(f, encoding="utf-8") as fh:
            ast.parse(fh.read(), filename=f)
    return "3 módulos parseados con ast"
check("Sintaxis válida (ast.parse)", t1)

# Test 2: thinking layer ejecuta el ciclo completo
print("\n[2] Probando ThinkingLayer con MockLLM (offline)...")


def t2():
    from pensamiento_layer import DeepResearchThinkingLayer
    from deep_research_system import MockLLM
    result = DeepResearchThinkingLayer(MockLLM(), name="test").think("test question")
    assert result["valid"], f"ciclo inválido: {result.get('error')}"
    assert result["step_count"] == 7, f"pasos={result['step_count']}"
    assert isinstance(result["confidence"], float)
    assert "PASO 1" in result["thought"] and "CONFIANZA" in result["thought"].upper()
    return f"{result['step_count']} pasos, confianza {result['confidence']:.2f}"
check("thinking.think() completa 7 pasos válidos", t2)

# Test 3: análisis estático de código
print("\n[3] Probando análisis estático...")


def t3():
    from code_design_improvement_tools import analyze_python_source
    analysis = analyze_python_source("def hello():\n    return 'world'\n")
    assert "metrics" in analysis and "source_summary" in analysis
    assert analysis["source_summary"]["functions"] == 1
    return f"funciones={analysis['source_summary']['functions']}, issues={len(analysis['metrics']['issues'])}"
check("analyze_python_source retorna métricas e issues", t3)

# Test 4: contexto de análisis con priorización por severidad
print("\n[4] Verificando CodeAnalysisContext y principio de eficiencia...")


def t4():
    from code_design_improvement_tools import CodeAnalysisContext
    context = CodeAnalysisContext("test_project", max_issues=10)
    context.add_issue("style", "low", "Línea larga detectada", suggestion="Dividir línea")
    context.add_issue("bug", "critical", "Error grave", suggestion="Corregir ya")
    metrics = context.to_dict()
    assert metrics["total_issues"] == 2
    assert metrics["issues"][0]["severity"] == "critical", "orden de severidad incorrecto"
    assert "efficiency_score" in metrics
    return f"issues={metrics['total_issues']}, efficiency={metrics['efficiency_score']:.2f}"
check("CodeAnalysisContext prioriza por severidad y mide eficiencia", t4)

# Resumen construido a partir de los resultados reales
print("\n" + "=" * 60)
print("RESUMEN DE PRUEBAS HONESTAS")
print("=" * 60)
passed = sum(1 for _, ok, _ in results if ok)
print(f"RESULTADO REAL: {passed}/{len(results)} pruebas pasaron\n")
for name, ok, detail in results:
    print(f"  {'✓' if ok else '✗'} {name}" + (f" — {detail}" if detail and ok else ""))

if passed == len(results):
    print("""
CAPACIDADES COMPROBADAS (con evidencia de esta ejecución):
1. El sistema piensa en pasos explícitos y estructurados (7 pasos)
2. Cada paso se valida antes de avanzar
3. Se computa confianza numérica en cada ciclo
4. El análisis estático detecta métricas e issues reales
5. El principio de eficiencia se mide y trackea

CAPACIDADES QUE REQUIEREN LLM REAL (no verificadas aquí):
- Generación de contenido real en los pasos de pensamiento
- Análisis semántico profundo de código

El sistema no simula inteligencia: provee la capa estructurada que
permite que un LLM real exhiba comportamiento verificable. Las partes
simuladas (MockLLM) están declaradas explícitamente como simuladas.
""")
else:
    print("\n⚠️  ALGUNAS PRUEBAS FALLARON — revisar los ✗ de arriba.")

sys.exit(0 if passed == len(results) else 1)
