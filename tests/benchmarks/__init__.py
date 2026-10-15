"""Benchmarks de evaluación para Deep Research - Framework tipo DeepResearch Bench 2026."""

from .tasks import BENCHMARK_TASKS, get_task, list_tasks, get_domains, get_complexities
from .rubrics import evaluate_all_dimensions, evaluate_dimension, ALL_RUBRICS
from .evaluator import LLMEvaluator, run_benchmark, BenchmarkResult, BenchmarkSummary

__all__ = [
    "BENCHMARK_TASKS",
    "get_task",
    "list_tasks",
    "get_domains",
    "get_complexities",
    "evaluate_all_dimensions",
    "evaluate_dimension",
    "ALL_RUBRICS",
    "LLMEvaluator",
    "run_benchmark",
    "BenchmarkResult",
    "BenchmarkSummary",
]