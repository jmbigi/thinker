#!/usr/bin/env python3
"""
Ejemplo de integración OpenRouter con los sistemas de LLM integrados.

Por defecto es OFFLINE (MockLLM, declarado como simulado): no usa la red
ni gasta saldo. Para llamadas reales a OpenRouter (requiere
OPENROUTER_API_KEY en .env):

    python3 openrouter_integration_demo.py --real

Demuestra:
1. Cargar OPENROUTER_API_KEY del .env (sin imprimirla)
2. Usar OpenRouterLLM (modo --real) o MockLLM (offline)
3. Ejecutar el pensamiento estructurado (7 pasos)
4. Analizar código Python con AST
"""

import os
import sys

from dotenv import load_dotenv

from code_design_improvement_tools import analyze_python_source
from deep_research_system import MockLLM, OpenRouterLLM
from pensamiento_layer import DeepResearchThinkingLayer

REAL_API = "--real" in sys.argv

DEMO_CODE = '''
def calcular_factorial(n):
    """Calcula el factorial de n de manera recursiva."""
    if n <= 1:
        return 1
    else:
        return n * calcular_factorial(n - 1)

# Variable global no usada
GLOBAL_CONST = 999

# Importaciones múltiples en una línea
import os, sys, json, math, re, collections, datetime, uuid

def proceso_principal(datos):
    """Procesa los datos de entrada y devuelve el doble."""
    resultado = []
    for item in datos:
        if item is not None:
            resultado.append(item * 2)
    return resultado

if __name__ == "__main__":
    datos = [1, 2, 3, 4, 5]
    print(calcular_factorial(5))
    print(proceso_principal(datos))
'''


def main():
    print("=" * 70)
    print("EJEMPLO: OpenRouter + Sistemas LLM Integrados")
    print("=" * 70)

    # 1. Cargar .env
    load_dotenv(".env")

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    use_real = REAL_API and bool(api_key)

    if REAL_API and not api_key:
        print("\n⚠️  --real pedido pero OPENROUTER_API_KEY no está en el entorno.")
        print("   Añádela a .env (nunca la escribas en el código).")
        sys.exit(1)

    print("\n[1] ✓ .env cargado"
          + (f" (OPENROUTER_API_KEY presente, {len(api_key)} caracteres)" if api_key
             else " (sin OPENROUTER_API_KEY)"))

    # 2. Proveedor LLM
    if use_real:
        llm = OpenRouterLLM(api_key=api_key)  # modelo gratuito por defecto (:free)
        print("\n[2] Modo --real: llamada REAL a OpenRouter (gasta saldo)...")
    else:
        llm = MockLLM()
        print("\n[2] Modo offline: MockLLM (simulado, sin red). Usa --real para OpenRouter.")

    test_prompt = "¿Cuál es el estado actual de la fusión nuclear y sus perspectivas a 2030?"
    try:
        result = llm.generate(test_prompt)
        print(f"  ✓ generate() exitosa — {len(result)} caracteres")
        print(f"   - Comienza por: {result[:80]}")
    except Exception as e:
        print(f"  ✗ Error en generate(): {type(e).__name__}: {e}")
        sys.exit(1)

    # 3. ThinkingLayer con el mismo proveedor
    print("\n[3] Testing ThinkingLayer (7 pasos estructurados)...")
    try:
        thinking = DeepResearchThinkingLayer(llm_provider=llm, name="openrouter_test")
        result = thinking.think(
            "Analiza los pros y contras de la energía nuclear para un informe de investigación."
        )
        print(f"  ✓ Pasos completados: {result['step_count']}/7")
        print(f"   - Confianza: {result['confidence']:.2f}")
        print(f"   - Válido: {result['valid']}")
    except Exception as e:
        print(f"  ✗ Error: {type(e).__name__}: {e}")
        sys.exit(1)

    # 4. Análisis estático de código Python (no necesita API)
    print("\n[4] Testing Code Analysis (AST + Issue Detection)...")
    try:
        analysis = analyze_python_source(DEMO_CODE)
        metrics = analysis["metrics"]
        issues = metrics["issues"]

        print("  ✓ analyze_python_source exitosa")
        print(f"   - Líneas: {metrics['total_lines']}")
        print(f"   - Funciones: {metrics['total_functions']}")
        print(f"   - Clases: {metrics['total_classes']}")
        print(f"   - Complejidad: {metrics['complexity']}")
        print(f"   - Issues detectados: {len(issues)}")
        print(f"   - Efficiency score: {metrics['efficiency_score']:.2f}")

        if issues:
            print("   - Issues destacados:")
            for issue in issues[:3]:
                print(f"     - [{issue['severity']}] {issue['description']}")
    except Exception as e:
        print(f"  ✗ Error: {type(e).__name__}: {e}")
        sys.exit(1)

    # 5. Resumen final
    print("\n" + "=" * 70)
    print("RESUMEN DEL EJEMPLO")
    print("=" * 70)
    modo = "REAL (OpenRouter)" if use_real else "OFFLINE (MockLLM, simulado)"
    proveedor = f"OpenRouterLLM ({getattr(llm, 'model', 'n/a')})" if use_real else "MockLLM (declarado simulado)"
    print(f"""
Modo de ejecución: {modo}

✓ .env cargado sin exponer la key
✓ Proveedor LLM: {proveedor}
✓ ThinkingLayer ejecuta 7 pasos estructurados
✓ Code Analysis: análisis estático Python con detección de issues
✓ Principio "hacer las cosas de manera eficiente" aplicado

Flujo completo posible:
1. ResearchOrchestrator + OpenRouterLLM → investigación profunda real
2. ThinkingLayer + prompt → reporte estructurado 7 pasos
3. CodeDesignThinker + código Python → plan de refactoring con issues
""")

    print("=" * 70)


if __name__ == "__main__":
    main()
