#!/usr/bin/env python3
"""Persistencia versionada de investigaciones y reanudación idempotente."""

import copy
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Tuple

from deep_research_system import ResearchContext

STATE_SCHEMA_VERSION = 1


def source_key(source: Dict[str, Any]) -> str:
    texto = f"{source.get('url', '')}\x00{source.get('snippet', '')}"
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def claim_key(claim: Dict[str, Any]) -> str:
    url = claim.get("source_id") or claim.get("source_url", "")
    contenido = claim.get("source_key", "")
    texto = f"{url}\x00{contenido}\x00{claim.get('claim', '')}"
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def context_to_state(context: ResearchContext, report: str = "",
                     completed: bool = False) -> Dict[str, Any]:
    """Serializa todo lo necesario para reanudar, no solo el resumen."""
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "question": context.question,
        "max_iterations": context.max_iterations,
        "iteration": context.iteration,
        "decomposed": context.decomposed,
        "subquestions": copy.deepcopy(context.subquestions),
        "sources": copy.deepcopy(context.sources),
        "claims": copy.deepcopy(context.claims),
        "evaluations": copy.deepcopy(context.evaluations),
        "conclusions": copy.deepcopy(context.conclusions),
        "decision_log": copy.deepcopy(context.decision_log),
        "retrieved_subquestions": copy.deepcopy(context.retrieved_subquestions),
        "retrieval_cache": copy.deepcopy(context.retrieval_cache),
        "processed_source_keys": list(context.processed_source_keys),
        "evaluated_claim_keys": list(context.evaluated_claim_keys),
        "duration_seconds": round(time.time() - context.start_time, 3),
        "report": report,
        "completed": completed,
    }


def context_from_state(state: Dict[str, Any]) -> ResearchContext:
    """Restaura un contexto validado; una entrada inválida no se ignora."""
    if not isinstance(state, dict):
        raise RuntimeError("El estado de investigación debe ser un objeto JSON")
    if state.get("schema_version") != STATE_SCHEMA_VERSION:
        raise RuntimeError(
            f"Esquema de estado no soportado: {state.get('schema_version')!r}")
    if not isinstance(state.get("question"), str) or not state["question"].strip():
        raise RuntimeError("El estado no contiene una pregunta válida")
    listas = ("subquestions", "sources", "claims", "evaluations", "conclusions",
              "decision_log", "retrieved_subquestions", "processed_source_keys",
              "evaluated_claim_keys")
    for clave in listas:
        if not isinstance(state.get(clave), list):
            raise RuntimeError(f"Campo de estado inválido: {clave}")
    if not isinstance(state.get("retrieval_cache"), dict):
        raise RuntimeError("Campo de estado inválido: retrieval_cache")
    max_iterations = state.get("max_iterations")
    if not isinstance(max_iterations, int) or isinstance(max_iterations, bool) \
            or max_iterations < 1:
        raise RuntimeError("Campo de estado inválido: max_iterations")

    iteration = state.get("iteration", 0)
    if not isinstance(iteration, int) or isinstance(iteration, bool) or iteration < 0:
        raise RuntimeError("Campo de estado inválido: iteration")

    contexto = ResearchContext(state["question"], max_iterations)
    contexto.iteration = iteration
    contexto.decomposed = bool(state.get("decomposed"))
    contexto.subquestions = copy.deepcopy(state["subquestions"])
    contexto.sources = copy.deepcopy(state["sources"])
    contexto.claims = copy.deepcopy(state["claims"])
    contexto.evaluations = copy.deepcopy(state["evaluations"])
    contexto.conclusions = copy.deepcopy(state["conclusions"])
    contexto.decision_log = copy.deepcopy(state["decision_log"])
    contexto.retrieved_subquestions = copy.deepcopy(state["retrieved_subquestions"])
    contexto.retrieval_cache = copy.deepcopy(state["retrieval_cache"])
    contexto.processed_source_keys = list(state["processed_source_keys"])
    contexto.evaluated_claim_keys = list(state["evaluated_claim_keys"])
    duracion = state.get("duration_seconds", 0.0)
    if not isinstance(duracion, (int, float)) or isinstance(duracion, bool) or duracion < 0:
        raise RuntimeError("Campo de estado inválido: duration_seconds")
    contexto.start_time = time.time() - duracion
    return contexto


def load_research_state(path: str) -> Tuple[ResearchContext, str, bool]:
    ruta = Path(path)
    try:
        state = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"No se pudo leer el estado {ruta}: {exc}") from exc
    contexto = context_from_state(state)
    report = state.get("report", "")
    completed = state.get("completed", False)
    if not isinstance(report, str) or not isinstance(completed, bool):
        raise RuntimeError("Campos report/completed inválidos en el estado")
    return contexto, report, completed


def atomic_write_bytes(path: str, data: bytes) -> None:
    """Escritura atómica con permisos 0600, compartida por JSON y cifrado."""
    ruta = Path(path)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="wb", dir=ruta.parent,
                prefix=f".{ruta.name}.", suffix=".tmp", delete=False) as archivo:
            temporal = Path(archivo.name)
            os.chmod(temporal, 0o600)
            archivo.write(data)
            archivo.flush()
            os.fsync(archivo.fileno())
        os.replace(temporal, ruta)
    finally:
        if temporal is not None and temporal.exists():
            temporal.unlink()


def save_research_state(path: str, context: ResearchContext, report: str = "",
                        completed: bool = False) -> None:
    """Serializa JSON y lo escribe de forma atómica con permisos 0600."""
    state = context_to_state(context, report, completed)
    datos = json.dumps(state, ensure_ascii=False, sort_keys=True).encode("utf-8")
    atomic_write_bytes(path, datos)
