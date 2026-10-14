#!/usr/bin/env python3
"""
Test REAL de OpenRouter con la key del .env (modelo GRATUITO).

Hace llamadas reales al modelo gratuito por defecto
(`nvidia/nemotron-3-super-120b-a12b:free`, coste 0) y verifica de extremo
a extremo:
1. Conexión con OpenRouterLLM (key desde .env, nunca se imprime)
2. Pipeline de investigación completo (pensamiento + extracción + evaluación)
3. Capa de pensamiento de 7 pasos

Es un test OPT-IN: gasta tiempo de red, pero no dinero (modelos :free).
Reporta éxito o error real; nunca simula.

Requiere: OPENROUTER_API_KEY en .env. Sobreescribir modelo: OPENROUTER_MODEL.
"""

import os
import re
import sys

from dotenv import load_dotenv

from deep_research_system import MockSearchAPI, OpenRouterLLM, ResearchOrchestrator
from pensamiento_layer import DeepResearchThinkingLayer

load_dotenv(".env")
api_key = os.environ.get("OPENROUTER_API_KEY", "")
if not api_key:
    print("❌ CRITICAL: no hay OPENROUTER_API_KEY en el entorno (.env).")
    sys.exit(1)


def _sanitizar(texto: str) -> str:
    """No escribir identificadores de cuenta en los logs (P0.9)."""
    texto = re.sub(r"'user_id':\s*'[^']*'", "'user_id': '<oculto>'", texto)
    return texto[:300]

llm = OpenRouterLLM()
print("=" * 70)
print("TEST REAL OpenRouter (modelo gratuito)")
print("=" * 70)
print(f"Modelo: {llm.model}")
print(f"Key presente: sí ({len(api_key)} caracteres, no se imprime)")

results = []
lineas_resultado = []


def check(name, fn):
    try:
        detail = fn()
        results.append((name, True, detail or ""))
        print(f"  ✓ {name}" + (f" — {detail}" if detail else ""))
        lineas_resultado.append(f"OK: {name} — {detail}")
    except Exception as e:
        detalle = _sanitizar(f"{type(e).__name__}: {e}")
        results.append((name, False, detalle))
        print(f"  ✗ {name} -> {detalle}")
        lineas_resultado.append(f"FALLO: {name} — {detalle}")


print("\n[1] Conexión básica con el modelo gratuito...")


def t1():
    respuesta = llm.generate("Responde exactamente con la palabra: OK", model=llm.model)
    assert respuesta.strip(), "respuesta vacía"
    return f"{len(respuesta)} caracteres"
check("generate() responde", t1)

print("\n[2] Capa de pensamiento (7 pasos) con modelo real...")


def t2():
    thinking = DeepResearchThinkingLayer(llm_provider=llm, name="real_test")
    r = thinking.think("¿Cuál es el estado actual de la fusión nuclear?")
    assert r["step_count"] == 7, f"pasos={r['step_count']}"
    assert r["valid"], f"pasos inválidos: {r.get('invalid_steps')}"
    return f"7 pasos, válido={r['valid']}, confianza={r['confidence']}"
check("ThinkingLayer 7 pasos", t2)

print("\n[3] Pipeline de investigación completo (LLM real + búsqueda mock)...")


def t3():
    orch = ResearchOrchestrator(llm, MockSearchAPI(), max_iterations=3)
    report, ctx = orch.research("¿Cuál es el estado del desarrollo de la fusión nuclear?")
    assert report and len(report) > 200, f"reporte demasiado corto: {len(report)}"
    assert ctx.subquestions, "sin subpreguntas"
    assert ctx.claims, "sin claims extraídos por el modelo"
    return (f"{len(ctx.subquestions)} subpreguntas, {len(ctx.claims)} claims, "
            f"{len(ctx.evaluations)} evaluaciones, reporte {len(report)} chars")
check("Investigación end-to-end", t3)

with open("test_openrouter_result.txt", "w", encoding="utf-8") as f:
    f.write(f"Test real OpenRouter — modelo: {llm.model}\n")
    f.write(f"Fecha: {__import__('datetime').datetime.now().isoformat()}\n")
    f.write("(No se escribe la API key, P0.6)\n\n")
    f.write("\n".join(lineas_resultado) + "\n")

print("\n" + "=" * 70)
passed = sum(1 for _, ok, _ in results if ok)
print(f"RESULTADO REAL: {passed}/{len(results)} comprobaciones pasaron")
print("Detalle guardado en test_openrouter_result.txt (sin la key)")
print("=" * 70)
sys.exit(0 if passed == len(results) else 1)
