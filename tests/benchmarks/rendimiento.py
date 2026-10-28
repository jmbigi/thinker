#!/usr/bin/env python3
"""Benchmark de rendimiento del pipeline con componentes SIMULADOS (offline).

Mide latencia de pared, llamadas al LLM y fuentes recuperadas en tres
escenarios crecientes. No mide calidad ni coste real de tokens (MockLLM no
produce tokens ni red): sirve como línea base reproducible de la mecánica y
como regresión de que el número de llamadas no se dispara.

Uso: python3 -m tests.benchmarks.rendimiento [--json]
"""

import argparse
import json
import time

from deep_research_system import ResearchOrchestrator
from llm_providers import MockLLM
from web_search import MockSearchAPI


class _LLMContador:
    """MockLLM envolviendo y contando llamadas (sin red)."""

    def __init__(self):
        self._llm = MockLLM()
        self.llamadas = 0
        self.model = self._llm.model

    def generate(self, prompt, model=None, **kwargs):
        self.llamadas += 1
        return self._llm.generate(prompt, model=model, **kwargs)


class _BusquedaContadora:
    """MockSearchAPI envolviendo y contando consultas (sin red)."""

    def __init__(self):
        self._api = MockSearchAPI()
        self.queries = []

    def search(self, query, max_results=5):
        self.queries.append(query)
        return self._api.search(query, max_results=max_results)


def medir_escenario(nombre, max_iterations):
    llm = _LLMContador()
    busqueda = _BusquedaContadora()
    inicio = time.monotonic()
    informe, contexto = ResearchOrchestrator(
        llm, busqueda, max_iterations=max_iterations).research(
        "¿Cuál es el estado actual de la fusión nuclear?")
    duracion = time.monotonic() - inicio
    return {
        "escenario": nombre,
        "max_iterations": max_iterations,
        "latencia_s": round(duracion, 3),
        "llamadas_llm": llm.llamadas,
        "fuentes": len(busqueda.queries),
        "caracteres_informe": len(informe),
        "iteraciones_contexto": len(getattr(contexto, "iterations", [])
                                    or getattr(contexto, "history", []) or []),
    }


def ejecutar():
    return {
        "generado": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "modo": "simulado (MockLLM/MockSearchAPI): no mide calidad ni tokens",
        "escenarios": [
            medir_escenario("simple", 1),
            medir_escenario("media", 3),
            medir_escenario("compleja", 5),
        ],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    resultado = ejecutar()
    if args.json:
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
    else:
        print(f"Benchmark de rendimiento ({resultado['modo']})\n")
        for escenario in resultado["escenarios"]:
            print(f"  {escenario['escenario']:9s} "
                  f"latencia {escenario['latencia_s']:7.3f} s | "
                  f"llamadas LLM {escenario['llamadas_llm']:2d} | "
                  f"queries {escenario['fuentes']:2d} | "
                  f"informe {escenario['caracteres_informe']} chars")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
