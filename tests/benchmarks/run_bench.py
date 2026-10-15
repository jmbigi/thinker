#!/usr/bin/env python3
"""CLI para ejecutar benchmarks de Deep Research."""

import argparse
import sys
import os
from dotenv import load_dotenv

# Añadir path del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv(".env")

from tests.benchmarks import run_benchmark, LLMEvaluator, list_tasks, get_domains, get_complexities  # noqa: E402
from deep_research_system import MockLLM, MockSearchAPI, ResearchOrchestrator, OpenRouterLLM  # noqa: E402
from pensamiento_layer import DeepResearchThinkingLayer, ResearchOrchestratorWithThinking  # noqa: E402

try:
    from llm_providers import DeepSeekLLM
except ImportError:
    DeepSeekLLM = None


def build_research_function(use_tot: bool = False, provider="mock"):
    """Construye la función de investigación para el benchmark."""
    
    if provider == "mock":
        llm = MockLLM()
        search = MockSearchAPI()
    elif provider == "openrouter":
        llm = OpenRouterLLM(use_fallback=True)
        search = MockSearchAPI()
    elif provider == "deepseek":
        if DeepSeekLLM is None:
            raise ValueError("DeepSeekLLM no disponible")
        llm = DeepSeekLLM()
        search = MockSearchAPI()
    else:
        raise ValueError(f"Proveedor desconocido: {provider}. Opciones: mock, openrouter, deepseek")
    
    thinking = DeepResearchThinkingLayer(llm_provider=llm, name="bench")
    orchestrator = ResearchOrchestratorWithThinking(llm, search, thinking)
    
    def research_fn(question: str) -> dict:
        if use_tot:
            # Usar modo ToT
            thinking_result = thinking.think_tot(question, branch_factor=2, beam_width=2)
            # Luego pipeline real (simplificado para benchmark)
            report, context = ResearchOrchestrator(llm, search).research(question)
            return {"report": report, "thinking": thinking_result, "context": context}
        else:
            # Modo lineal estándar
            result = orchestrator.research_with_thinking(question)
            return {"report": result.get("report", ""), "thinking": result.get("thinking", {}), "context": result.get("context")}
    
    return research_fn


def main():
    parser = argparse.ArgumentParser(description="Deep Research Benchmark Runner")
    parser.add_argument("--domain", choices=get_domains(), help="Filtrar por dominio")
    parser.add_argument("--complexity", choices=get_complexities(), help="Filtrar por complejidad")
    parser.add_argument("--max-tasks", type=int, help="Máximo número de tareas")
    parser.add_argument("--tot", action="store_true", help="Usar Tree of Thoughts")
    parser.add_argument("--output", default="benchmark_results", help="Directorio de salida")
    parser.add_argument("--list", action="store_true", help="Listar tareas disponibles")
    parser.add_argument("--provider", default="mock", choices=["mock", "openrouter", "deepseek"], help="Proveedor LLM")
    
    args = parser.parse_args()
    
    if args.list:
        tasks = list_tasks(args.domain, args.complexity)
        print(f"{'ID':<30} {'Dominio':<15} {'Complejidad':<12} Pregunta")
        print("-" * 100)
        for t in tasks:
            print(f"{t.id:<30} {t.domain:<15} {t.complexity:<12} {t.question[:60]}...")
        print(f"\nTotal: {len(tasks)} tareas")
        return
    
    # Filtrar tareas
    tasks = list_tasks(args.domain, args.complexity)
    if args.max_tasks:
        tasks = tasks[:args.max_tasks]
    
    if not tasks:
        print("No hay tareas que coincidan con los filtros")
        return
    
    print(f"Ejecutando benchmark: {len(tasks)} tareas")
    print(f"Modo: {'ToT' if args.tot else 'Lineal'} | Proveedor: {args.provider}")
    
    # Construir función de investigación
    research_fn = build_research_function(use_tot=args.tot, provider=args.provider)
    
    # Evaluador (heurístico por defecto, LLM-as-judge opcional)
    llm_judge = None
    if args.provider != "mock":
        if args.provider == "openrouter":
            llm = OpenRouterLLM(use_fallback=True)
        elif args.provider == "deepseek":
            if DeepSeekLLM is not None:
                llm = DeepSeekLLM()
            else:
                llm = MockLLM()
        else:
            llm = MockLLM()
        llm_judge = LLMEvaluator(llm)
    
    # Ejecutar
    run_benchmark(
        research_function=research_fn,
        tasks=tasks,
        llm_judge=llm_judge,
        output_dir=args.output,
    )


if __name__ == "__main__":
    main()