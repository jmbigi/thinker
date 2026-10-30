#!/usr/bin/env python3
"""Benchmarks externos: DeepResearch Bench y atribución claim→pasaje.

DRB usa el formato oficial id/prompt/article. Las rúbricas locales NO sustituyen
a RACE/FACT oficiales. MockLLM ejercita el protocolo, no mide calidad real.
"""

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List

from deep_research_system import EvidenceEvaluator, ResearchContext, ResearchOrchestrator
from llm_providers import MockLLM, OllamaLLM, OpenRouterLLM
from tests.benchmarks import run_benchmark
from tests.benchmarks.factual import MAPA_ESPERADO, metricas
from tests.benchmarks.tasks import BenchmarkTask
from web_search import MockSearchAPI, WikipediaSearchAPI

CATEGORIAS = tuple(MAPA_ESPERADO)
DOMINIOS = {
    "Science & Technology": "science_tech",
    "Health": "medicine",
    "Finance & Business": "economics",
    "Crime & Law": "law_policy",
}


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    registros = []
    ruta = Path(path)
    try:
        lineas = ruta.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise RuntimeError(f"No se pudo leer el dataset {ruta}: {exc}") from exc
    for numero, linea in enumerate(lineas, start=1):
        if not linea.strip():
            continue
        try:
            registro = json.loads(linea)
        except json.JSONDecodeError as exc:
            raise ValueError(f"JSONL inválido en {ruta}:{numero}: {exc}") from exc
        if not isinstance(registro, dict):
            raise ValueError(f"Se esperaba un objeto en {ruta}:{numero}")
        registros.append(registro)
    if not registros:
        raise ValueError(f"Dataset vacío: {ruta}")
    return registros


def load_drb_tasks(path: str, max_tasks: int = None) -> List[BenchmarkTask]:
    registros = load_jsonl(path)
    tareas = []
    for registro in registros:
        if not isinstance(registro.get("prompt"), str) or not registro["prompt"].strip():
            raise ValueError(f"Tarea DRB sin prompt válido: {registro.get('id')!r}")
        if "id" not in registro:
            raise ValueError("Tarea DRB sin id")
        topic = str(registro.get("topic", "external"))
        tareas.append(BenchmarkTask(
            id=str(registro["id"]),
            domain=DOMINIOS.get(topic, "external"),
            complexity="expert",
            question=registro["prompt"],
            expected_elements={},
            metadata={
                "topic": topic,
                "language": registro.get("language", "unknown"),
                "external": "DeepResearch Bench",
            },
        ))
    return tareas[:max_tasks] if max_tasks else tareas


def load_attribution_cases(path: str) -> List[Dict[str, Any]]:
    casos = []
    for registro in load_jsonl(path):
        claim = registro.get("claim")
        passage = registro.get("passage", registro.get("fuente"))
        expected = registro.get("expected", registro.get("categoria"))
        if not isinstance(claim, str) or not claim.strip():
            raise ValueError(f"Caso de atribución sin claim: {registro.get('id')!r}")
        if not isinstance(passage, str) or not passage.strip():
            raise ValueError(f"Caso de atribución sin passage: {registro.get('id')!r}")
        if expected not in CATEGORIAS:
            raise ValueError(f"Veredicto esperado inválido: {expected!r}")
        casos.append({**registro, "claim": claim, "fuente": passage,
                      "categoria": expected})
    return casos


def evaluar_atribucion(casos: Iterable[Dict[str, Any]], llm=None) -> Dict[str, Any]:
    simulado = llm is None
    llm = llm or MockLLM()
    evaluador = EvidenceEvaluator(llm)
    detalle = []
    for indice, caso in enumerate(casos, start=1):
        contexto = ResearchContext(caso["claim"])
        contexto.sources.append({
            "title": "Pasaje externo",
            "url": caso.get("url", f"external://{indice}"),
            "snippet": caso["fuente"],
            "sha256": caso.get("sha256", ""),
            "location": caso.get("location", "dataset externo"),
        })
        evaluacion = evaluador.decide(
            contexto, {"claim": caso["claim"], "source_url": contexto.sources[0]["url"]})
        esperado = MAPA_ESPERADO[caso["categoria"]]
        detalle.append({
            "id": str(caso.get("id", indice)),
            "categoria": caso["categoria"],
            "claim": caso["claim"],
            "esperado": esperado,
            "veredicto": evaluacion.get("verdict", "not_addressed"),
            "confidence": float(evaluacion.get("confidence", 0.0) or 0.0),
            "url": contexto.sources[0]["url"],
        })
    veredictos = [item["veredicto"] for item in detalle]
    return {
        "modo": "simulado (MockLLM): no mide calidad real" if simulado
        else f"real ({getattr(llm, 'model', '?')})",
        "metricas": metricas(veredictos, detalle),
        "detalle": detalle,
    }


def run_drb(tareas: List[BenchmarkTask], research_function, output_dir: str) -> Dict[str, Any]:
    """Ejecuta tareas y emite también el JSONL crudo aceptado por DRB."""
    articulos = {}

    def envolver(pregunta):
        resultado = research_function(pregunta)
        articulos[pregunta] = resultado.get("report", "")
        return resultado

    resumen = run_benchmark(
        research_function=envolver,
        tasks=tareas,
        llm_judge=None,
        output_dir=output_dir,
    )
    destino = Path(output_dir)
    ruta = destino / f"raw_data_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"
    with ruta.open("w", encoding="utf-8") as archivo:
        for tarea in tareas:
            archivo.write(json.dumps({
                "id": tarea.id,
                "prompt": tarea.question,
                "article": articulos.get(tarea.question, ""),
            }, ensure_ascii=False) + "\n")
    return {
        "summary": asdict(resumen),
        "raw_data": str(ruta),
        "official_race_fact": False,
        "nota": "Rúbricas locales; ejecutar el evaluador oficial para RACE/FACT",
    }


def _proveedor(nombre: str, model: str = None):
    if nombre == "mock":
        return MockLLM(model=model or "mock-llm"), MockSearchAPI()
    if nombre == "openrouter":
        return OpenRouterLLM(model=model), WikipediaSearchAPI()
    if nombre == "ollama":
        return OllamaLLM(model=model or "qwen3:1.7b"), WikipediaSearchAPI()
    raise ValueError(f"Proveedor desconocido: {nombre}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dataset", required=True, help="dataset JSONL externo")
    parser.add_argument("--kind", choices=("drb", "attribution"), required=True)
    parser.add_argument("--provider", choices=("mock", "openrouter", "ollama"), default="mock")
    parser.add_argument("--model")
    parser.add_argument("--max-tasks", type=int)
    parser.add_argument("--output", default="benchmark_results")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.max_tasks is not None and args.max_tasks < 1:
        parser.error("--max-tasks debe ser >= 1")

    llm, search = _proveedor(args.provider, args.model)
    if args.kind == "attribution":
        casos = load_attribution_cases(args.dataset)
        if args.max_tasks:
            casos = casos[:args.max_tasks]
        resultado = evaluar_atribucion(casos, None if args.provider == "mock" else llm)
    else:
        tareas = load_drb_tasks(args.dataset, args.max_tasks)
        def investigar(pregunta):
            report, context = ResearchOrchestrator(llm, search).research(pregunta)
            return {"report": report, "context": context}
        import contextlib
        with contextlib.redirect_stdout(sys.stderr):
            resultado = run_drb(tareas, investigar, args.output)
        if args.provider == "mock":
            resultado["modo"] = "simulado (MockLLM/MockSearchAPI): no mide calidad real"
    if args.json:
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
