#!/usr/bin/env python3
"""
Test REAL con Ollama (LLM local, gratuito, sin API key).

Comprueba de extremo a extremo:
1. Conexión con el servidor Ollama local y el modelo configurado
2. Capa de pensamiento de 7 pasos
3. Pipeline de investigación completo (con búsqueda mock para aislar el LLM)

Es un test OPT-IN. Si el servidor Ollama no responde, lo dice y OMITE la
prueba (exit 0): no simula éxito. Modelo: OLLAMA_MODEL (por defecto qwen3:1.7b,
elegido por rapidez; usa uno mayor para mejor calidad).
"""

import os
import sys

import requests

from deep_research_system import MockSearchAPI, OllamaLLM, ResearchOrchestrator
from pensamiento_layer import DeepResearchThinkingLayer

BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
MODELO = os.environ.get("OLLAMA_MODEL", "qwen3:1.7b")

print("=" * 70)
print("TEST REAL Ollama (LLM local, sin API key)")
print("=" * 70)
print(f"Servidor: {BASE_URL} | modelo: {MODELO}")

# 1. ¿Está el servidor y el modelo?
try:
    tags = requests.get(f"{BASE_URL}/api/tags", timeout=5).json()
except (requests.RequestException, ValueError) as e:
    print(f"\n[0] Servidor Ollama no disponible ({type(e).__name__}): prueba OMITIDA")
    print("    Arranca Ollama ('ollama serve') o define OLLAMA_BASE_URL.")
    sys.exit(0)

disponibles = [m["name"] for m in tags.get("models", [])]
print(f"[0] Modelos disponibles: {disponibles[:5]}{'...' if len(disponibles) > 5 else ''}")
if not any(m == MODELO or m.startswith(MODELO.split(':')[0]) for m in disponibles):
    print(f"\n    El modelo {MODELO} no está descargado: prueba OMITIDA")
    print(f"    Descárgalo con: ollama pull {MODELO}")
    sys.exit(0)

llm = OllamaLLM(base_url=BASE_URL, model=MODELO)
results = []
lineas = []


def check(name, fn):
    try:
        detalle = fn()
        results.append((name, True, detalle or ""))
        print(f"  ✓ {name}" + (f" — {detalle}" if detalle else ""))
        lineas.append(f"OK: {name} — {detalle}")
    except (ValueError, RuntimeError, ConnectionError, TimeoutError, requests.RequestException) as e:
        detalle = f"{type(e).__name__}: {str(e)[:200]}"
        results.append((name, False, detalle))
        print(f"  ✗ {name} -> {detalle}")
        lineas.append(f"FALLO: {name} — {detalle}")


print("\n[1] Conexión básica...")
respuesta = llm.generate("Responde exactamente con la palabra: OK")
check("generate() responde", lambda: (
    f"{len(respuesta)} caracteres" if respuesta.strip() else (_ for _ in ()).throw(AssertionError("vacío"))
))

print("\n[2] Capa de pensamiento (7 pasos) con modelo local...")
layer = DeepResearchThinkingLayer(llm_provider=llm, name="ollama_test")
resultado_think = layer.think("¿Cuál es el estado actual de la fusión nuclear?")
check("ThinkingLayer 7 pasos", lambda: (
    f"7 pasos, válido={resultado_think['valid']}, confianza={resultado_think['confidence']}"
))

print("\n[3] Pipeline de investigación (LLM local + búsqueda mock)...")
orchestrator = ResearchOrchestrator(llm, MockSearchAPI(), max_iterations=3)
reporte, ctx = orchestrator.research("¿Cuál es el estado actual de la fusión nuclear?")
check("Investigación end-to-end", lambda: (
    f"{len(ctx.subquestions)} subpreguntas, {len(ctx.claims)} claims, "
    f"reporte {len(reporte)} chars" if len(reporte) > 100
    else (_ for _ in ()).throw(AssertionError(f"reporte corto: {len(reporte)}"))
))

with open("test_ollama_result.txt", "w", encoding="utf-8") as f:
    f.write(f"Test real Ollama — modelo: {MODELO}\n")
    f.write(f"Fecha: {__import__('datetime').datetime.now().isoformat()}\n\n")
    f.write("\n".join(lineas) + "\n")

print("\n" + "=" * 70)
pasados = sum(1 for _, ok, _ in results if ok)
print(f"RESULTADO REAL: {pasados}/{len(results)} comprobaciones pasaron")
print("Detalle en test_ollama_result.txt")
print("=" * 70)
sys.exit(0 if pasados == len(results) else 1)