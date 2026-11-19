"""Benchmarks de evaluación para Deep Research - Framework tipo DeepResearch Bench 2026."""

from .evaluator import BenchmarkResult, BenchmarkSummary, LLMEvaluator, run_benchmark
from .rubrics import ALL_RUBRICS, evaluate_all_dimensions, evaluate_dimension
from .tasks import BENCHMARK_TASKS, get_complexities, get_domains, get_task, list_tasks

__all__ = [
    "ALL_RUBRICS",
    "BENCHMARK_TASKS",
    "BenchmarkResult",
    "BenchmarkSummary",
    "LLMEvaluator",
    "evaluate_all_dimensions",
    "evaluate_dimension",
    "get_complexities",
    "get_domains",
    "get_task",
    "list_tasks",
    "run_benchmark",
]