"""Evaluador LLM-as-judge y runner de benchmarks."""

import json
import time
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Callable
from pathlib import Path

from .tasks import BenchmarkTask, BENCHMARK_TASKS
from .rubrics import evaluate_all_dimensions, get_rubrics_for_domain


@dataclass
class BenchmarkResult:
    """Resultado de una tarea de benchmark."""
    task_id: str
    domain: str
    complexity: str
    question: str
    report: str
    evaluation: Dict[str, Any]
    latency_seconds: float
    tokens_estimated: int
    timestamp: str
    metadata: Dict[str, Any]


@dataclass
class BenchmarkSummary:
    """Resumen agregado de benchmark."""
    total_tasks: int
    completed: int
    failed: int
    overall_score: float
    by_domain: Dict[str, Dict[str, float]]
    by_complexity: Dict[str, Dict[str, float]]
    by_dimension: Dict[str, float]
    latency_avg: float
    timestamp: str


class LLMEvaluator:
    """
    Evaluador LLM-as-judge para rúbricas binarias.
    
    Usa un LLM (configurado via proveedor) para evaluar cada criterio
    con prompts calibrados few-shot. Más fiable que heurísticas simples.
    """
    
    def __init__(self, llm_provider, few_shot_examples: int = 3):
        self.llm = llm_provider
        self.few_shot_examples = few_shot_examples
        self._cache = {}
    
    def evaluate_criterion(
        self,
        report: str,
        criterion_id: str,
        criterion_desc: str,
        dimension: str,
        task_question: str,
        expected_keywords: List[str]
    ) -> int:
        """Evalúa un criterio individual: retorna 1 (pass) o 0 (fail)."""
        
        cache_key = f"{criterion_id}:{hash(report[:500])}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        prompt = self._build_judge_prompt(
            report, criterion_id, criterion_desc, dimension,
            task_question, expected_keywords
        )
        
        try:
            response = self.llm.generate(prompt)
            score = self._parse_judge_response(response)
        except Exception:
            score = 0  # Fail safe
        
        self._cache[cache_key] = score
        return score
    
    def _build_judge_prompt(
        self,
        report: str,
        criterion_id: str,
        criterion_desc: str,
        dimension: str,
        task_question: str,
        expected_keywords: List[str]
    ) -> str:
        """Construye prompt para LLM-as-judge."""
        return f"""Eres un evaluador experto de informes de investigación profunda.

TAREA ORIGINAL:
{task_question}

PALABRAS CLAVE ESPERADAS EN ESTA DIMENSIÓN ({dimension}):
{', '.join(expected_keywords) if expected_keywords else 'N/A - criterio transversal'}

CRITERIO A EVALUAR:
{criterion_desc} (ID: {criterion_id})

INFORME A EVALUAR:
{report[:3000]}

INSTRUCCIONES:
- Responde SOLO con "1" (CUMPLE) o "0" (NO CUMPLE)
- Criterio estricto: el informe debe demostrar claramente el criterio
- No des explicaciones, solo el dígito

RESPUESTA (1 o 0):"""
    
    def _parse_judge_response(self, response: str) -> int:
        """Parsea respuesta del juez: busca 1 o 0."""
        response = response.strip()
        if response.startswith("1"):
            return 1
        if response.startswith("0"):
            return 0
        # Buscar primer dígito
        for ch in response:
            if ch in "01":
                return int(ch)
        return 0


def run_benchmark(
    research_function: Callable[[str], Dict[str, Any]],
    tasks: List[BenchmarkTask] = None,
    llm_judge: LLMEvaluator = None,
    output_dir: str = "benchmark_results",
    max_tasks: int = None,
) -> BenchmarkSummary:
    """
    Ejecuta benchmark completo.
    
    Args:
        research_function: Función que toma pregunta y retorna dict con 'report'
        tasks: Lista de tareas (default: todas BENCHMARK_TASKS)
        llm_judge: Evaluador LLM opcional (si None, usa heurísticas)
        output_dir: Directorio para guardar resultados JSON
        max_tasks: Límite opcional de tareas
    
    Returns:
        BenchmarkSummary con resultados agregados
    """
    tasks = tasks or BENCHMARK_TASKS
    if max_tasks:
        tasks = tasks[:max_tasks]
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    results = []
    failed = 0
    
    print(f"\n{'='*60}")
    print(f"BENCHMARK DEEP RESEARCH: {len(tasks)} tareas")
    print(f"{'='*60}")
    
    for i, task in enumerate(tasks, 1):
        print(f"\n[{i}/{len(tasks)}] {task.id} ({task.domain}/{task.complexity})")
        print(f"  Q: {task.question[:80]}...")
        
        start = time.time()
        try:
            result = research_function(task.question)
            latency = time.time() - start
            
            report = result.get("report", "") or result.get("thinking", {}).get("thought", "")
            tokens_est = len(report.split()) * 1.3  # estimación rough
            
            # Evaluar
            if llm_judge:
                evaluation = _evaluate_with_llm_judge(
                    llm_judge, report, task, task.expected_elements
                )
            else:
                evaluation = evaluate_all_dimensions(report, task.expected_elements, domain=task.domain)
            
            bench_result = BenchmarkResult(
                task_id=task.id,
                domain=task.domain,
                complexity=task.complexity,
                question=task.question,
                report=report[:5000],  # truncar para storage
                evaluation=evaluation,
                latency_seconds=round(latency, 2),
                tokens_estimated=int(tokens_est),
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
                metadata=task.metadata,
            )
            results.append(bench_result)
            
            print(f"  ✓ Score: {evaluation['overall_score']:.3f} "
                  f"(IR:{evaluation['dimensions']['information_recall']['score']:.2f} "
                  f"AN:{evaluation['dimensions']['analysis']['score']:.2f} "
                  f"PR:{evaluation['dimensions']['presentation']['score']:.2f}) "
                  f"| {latency:.1f}s")
            
        except Exception as e:
            failed += 1
            print(f"  ✗ ERROR: {e}")
            results.append(BenchmarkResult(
                task_id=task.id,
                domain=task.domain,
                complexity=task.complexity,
                question=task.question,
                report="",
                evaluation={"error": str(e), "overall_score": 0},
                latency_seconds=0,
                tokens_estimated=0,
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
                metadata={"error": True},
            ))
    
    # Guardar resultados individuales
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    results_file = output_path / f"benchmark_results_{timestamp}.json"
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in results], f, indent=2, ensure_ascii=False)
    
    # Calcular summary
    summary = _compute_summary(results)
    summary_file = output_path / f"benchmark_summary_{timestamp}.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(asdict(summary), f, indent=2, ensure_ascii=False)
    
    # Print summary
    _print_summary(summary)
    print(f"\nResultados guardados en: {output_path}")
    
    return summary


def _evaluate_with_llm_judge(
    judge: LLMEvaluator,
    report: str,
    task: BenchmarkTask,
    expected: Dict[str, List[str]]
) -> Dict[str, Any]:
    """Evalúa usando LLM-as-judge para cada criterio (incluye rúbricas dominio)."""
    # Obtener rúbricas específicas del dominio
    domain_rubrics = get_rubrics_for_domain(task.domain)
    
    results = {}
    
    for dimension in ["information_recall", "analysis", "presentation"]:
        rubric = domain_rubrics.get(dimension, [])
        dim_results = {}
        for criterion in rubric:
            score = judge.evaluate_criterion(
                report, criterion.id, criterion.description,
                dimension, task.question, expected.get(dimension, [])
            )
            dim_results[criterion.id] = {
                "criterion": criterion.description,
                "score": score,
                "weight": criterion.weight,
            }
        
        total_weight = sum(c.weight for c in rubric)
        weighted = sum(r["score"] * r["weight"] for r in dim_results.values()) / total_weight if total_weight > 0 else 0
        passed = sum(1 for r in dim_results.values() if r["score"] == 1)
        
        results[dimension] = {
            "score": round(weighted, 3),
            "passed": passed,
            "total": len(dim_results),
            "pass_rate": round(passed / len(dim_results), 3) if dim_results else 0,
            "details": dim_results,
        }
    
    weights = {"information_recall": 0.3, "analysis": 0.4, "presentation": 0.3}
    overall = sum(results[dim]["score"] * weights[dim] for dim in weights)
    
    return {
        "dimensions": results,
        "overall_score": round(overall, 3),
        "weights": weights,
    }


def _compute_summary(results: List[BenchmarkResult]) -> BenchmarkSummary:
    """Calcula resumen agregado."""
    completed = [r for r in results if not r.metadata.get("error")]
    failed = len(results) - len(completed)
    
    if not completed:
        return BenchmarkSummary(
            total_tasks=len(results),
            completed=0,
            failed=failed,
            overall_score=0.0,
            by_domain={},
            by_complexity={},
            by_dimension={},
            latency_avg=0.0,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
        )
    
    # Overall
    overall = sum(r.evaluation.get("overall_score", 0) for r in completed) / len(completed)
    
    # By domain
    by_domain = {}
    for r in completed:
        d = r.domain
        if d not in by_domain:
            by_domain[d] = {"scores": [], "count": 0}
        by_domain[d]["scores"].append(r.evaluation.get("overall_score", 0))
        by_domain[d]["count"] += 1
    
    by_domain = {
        d: {"mean": round(sum(v["scores"])/len(v["scores"]), 3), "count": v["count"]}
        for d, v in by_domain.items()
    }
    
    # By complexity
    by_complexity = {}
    for r in completed:
        c = r.complexity
        if c not in by_complexity:
            by_complexity[c] = {"scores": [], "count": 0}
        by_complexity[c]["scores"].append(r.evaluation.get("overall_score", 0))
        by_complexity[c]["count"] += 1
    
    by_complexity = {
        c: {"mean": round(sum(v["scores"])/len(v["scores"]), 3), "count": v["count"]}
        for c, v in by_complexity.items()
    }
    
    # By dimension
    by_dim = {}
    for dim in ["information_recall", "analysis", "presentation"]:
        scores = [r.evaluation.get("dimensions", {}).get(dim, {}).get("score", 0) for r in completed]
        by_dim[dim] = round(sum(scores)/len(scores), 3) if scores else 0
    
    # Latency
    latency_avg = sum(r.latency_seconds for r in completed) / len(completed)
    
    return BenchmarkSummary(
        total_tasks=len(results),
        completed=len(completed),
        failed=failed,
        overall_score=round(overall, 3),
        by_domain=by_domain,
        by_complexity=by_complexity,
        by_dimension=by_dim,
        latency_avg=round(latency_avg, 2),
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
    )


def _print_summary(summary: BenchmarkSummary):
    """Imprime resumen formateado."""
    print(f"\n{'='*60}")
    print("RESUMEN BENCHMARK")
    print(f"{'='*60}")
    print(f"Tareas totales: {summary.total_tasks} | Completadas: {summary.completed} | Fallidas: {summary.failed}")
    print(f"Score general: {summary.overall_score:.3f}")
    print(f"Latencia media: {summary.latency_avg:.1f}s")
    
    print("\nPor dimensión:")
    for dim, score in summary.by_dimension.items():
        print(f"  {dim}: {score:.3f}")
    
    print("\nPor dominio:")
    for domain, data in summary.by_domain.items():
        print(f"  {domain}: {data['mean']:.3f} (n={data['count']})")
    
    print("\nPor complejidad:")
    for comp, data in summary.by_complexity.items():
        print(f"  {comp}: {data['mean']:.3f} (n={data['count']})")