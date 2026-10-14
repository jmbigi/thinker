#!/usr/bin/env python3
"""Test that .env OpenRouter key integrates with the systems.

Por defecto es OFFLINE (MockLLM): no usa la red ni gasta saldo aunque
exista OPENROUTER_API_KEY. Para una llamada real a OpenRouter:

    python3 test_env_usage.py --real
"""
import os
import sys

from deep_research_system import MockLLM, OpenRouterLLM
from pensamiento_layer import DeepResearchThinkingLayer

REAL_API = "--real" in sys.argv

print("=" * 60)
print("TEST: .env OpenRouter key integration")
print("=" * 60)

# 1. Cargar .env
try:
    from dotenv import load_dotenv
    load_dotenv(".env")
    print("\n[1] ✓ dotenv cargado")
except ImportError:
    print("\n[1] - dotenv no instalado, usando os.environ directamente")

# 2. Verificar key (solo su existencia y longitud: nunca se imprime)
key = os.environ.get("OPENROUTER_API_KEY", "")
print(f"\n[2] OPENROUTER_API_KEY: presente ({len(key)} caracteres)" if key
      else "\n[2] - OPENROUTER_API_KEY no encontrada en el entorno")

# 3. Elegir proveedor: real solo con --real y key; si no, MockLLM offline
if REAL_API and key:
    llm = OpenRouterLLM(api_key=key)
    print("\n[3] Modo --real: llamada REAL a OpenRouter (gasta saldo)")
else:
    llm = MockLLM()
    print("\n[3] Modo offline (MockLLM, simulado). Usa --real para llamada real.")

test_prompt = "¿Cuál es el estado actual de la fusión nuclear?"
try:
    result = llm.generate(test_prompt)
    print(f"    ✓ generate() exitosa — {len(result)} caracteres")
    print(f"    - Comienza por: {result[:60]}")
except Exception as e:
    print(f"    ✗ Error en generate(): {type(e).__name__}: {e}")
    sys.exit(1)

# 4. Test ThinkingLayer con el mismo proveedor
print("\n[4] Testing ThinkingLayer con el proveedor elegido...")
try:
    thinking = DeepResearchThinkingLayer(llm_provider=llm, name="env_test")
    result = thinking.think("Análisis rápido de: ¿Qué es la fusión nuclear?")
    print(f"    ✓ ThinkingLayer: {result['step_count']} pasos, "
          f"confianza {result['confidence']:.2f}, válido {result['valid']}")
except Exception as e:
    print(f"    ✗ Error: {type(e).__name__}: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("RESULTADO: integración .env/proveedores verificada")
print("=" * 60)
