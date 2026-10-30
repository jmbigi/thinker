#!/usr/bin/env python3
"""Políticas de egreso y persistencia cifrada para investigación."""

import json
import os
from dataclasses import dataclass
from typing import Tuple
from urllib.parse import urlparse

from documents import CompositeSearchAPI, FullTextSearchAPI, LocalDocumentSearchAPI
from llm_providers import (BudgetLLM, LLMProvider, MockLLM, OllamaLLM, OpenAILLM)
from mcp_client import MCPSearchAPI
from research_state import (atomic_write_bytes, context_from_state, context_to_state)
from web_search import (MockSearchAPI, SearchAPI, SearXNGSearchAPI, _es_host_publico)

SCOPES = ("public", "local-only", "private-documents")


def normalize_scope(value: str) -> str:
    scope = value.replace("_", "-").lower()
    if scope not in SCOPES:
        raise ValueError(f"Ámbito de privacidad desconocido: {value!r}; usa {SCOPES}")
    return scope


def _host_local(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return False
    return not _es_host_publico(parsed.netloc)


def _validate_llm(provider: LLMProvider, scope: str) -> None:
    if isinstance(provider, BudgetLLM):
        return _validate_llm(provider.provider, scope)
    if scope == "public" or isinstance(provider, MockLLM):
        return
    if isinstance(provider, OllamaLLM):
        if _host_local(provider.base_url):
            return
        raise RuntimeError(f"{scope}: el endpoint Ollama no es local")
    if isinstance(provider, OpenAILLM):
        raise RuntimeError(f"{scope}: proveedor LLM en la nube no permitido")
    base_url = getattr(provider, "base_url", None)
    if base_url and _host_local(base_url):
        return
    raise RuntimeError(f"{scope}: no se puede demostrar que el LLM sea local")


def _validate_search(search: SearchAPI, scope: str) -> None:
    if isinstance(search, (MockSearchAPI, LocalDocumentSearchAPI)):
        return
    if isinstance(search, CompositeSearchAPI):
        for provider in search.providers:
            _validate_search(provider, scope)
        return
    if isinstance(search, FullTextSearchAPI):
        if scope != "public":
            raise RuntimeError(f"{scope}: lectura web full-text no permitida")
        return _validate_search(search.search_api, scope)
    if isinstance(search, SearXNGSearchAPI):
        if scope == "private-documents":
            raise RuntimeError("private-documents: SearXNG reenvía consultas a internet")
        if scope == "local-only" and not _host_local(search.base_url):
            raise RuntimeError("local-only: SearXNG debe tener endpoint local")
        return
    if isinstance(search, MCPSearchAPI):
        if scope != "public":
            raise RuntimeError(f"{scope}: MCP no ofrece garantía de egreso local")
        return
    if scope != "public":
        raise RuntimeError(f"{scope}: buscador web no permitido")


class GuardLLM(LLMProvider):
    """Valida el proveedor al construirlo y conserva su API."""

    def __init__(self, provider: LLMProvider, scope: str):
        self.provider = provider
        self.scope = normalize_scope(scope)
        _validate_llm(provider, self.scope)

    def generate(self, prompt: str, model: str = None, **kwargs) -> str:
        return self.provider.generate(prompt, model=model, **kwargs)


class GuardSearch(SearchAPI):
    """Aplica política al buscador y valida URLs antes de aceptar resultados."""

    def __init__(self, search: SearchAPI, scope: str):
        self._search = search
        self.scope = normalize_scope(scope)
        _validate_search(search, self.scope)

    def search(self, query: str, max_results: int = 5):
        resultados = self._search.search(query, max_results)
        for resultado in resultados:
            url = resultado.get("url", "")
            if url.startswith(("document://", "mcp://")):
                continue
            parsed = urlparse(url)
            if parsed.scheme in ("http", "https") and not _es_host_publico(parsed.netloc):
                raise RuntimeError(f"Resultado con host no público bloqueado: {url}")
        return resultados


@dataclass(frozen=True)
class PrivacyPolicy:
    scope: str

    def __post_init__(self):
        normalize_scope(self.scope)

    def apply(self, llm: LLMProvider, search: SearchAPI) -> Tuple[GuardLLM, GuardSearch]:
        return GuardLLM(llm, self.scope), GuardSearch(search, self.scope)


def _fernet(key=None):
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:
        raise RuntimeError("Cifrado de estado requiere cryptography") from exc
    secreto = key or os.environ.get("THINKER_STATE_KEY")
    if not secreto:
        raise RuntimeError("Cifrado de estado exige THINKER_STATE_KEY")
    return Fernet(secreto.encode("utf-8") if isinstance(secreto, str) else secreto)


def save_encrypted_research_state(path: str, context, report: str = "",
                                  completed: bool = False, key=None) -> None:
    state = context_to_state(context, report, completed)
    datos = json.dumps(state, ensure_ascii=False, sort_keys=True).encode("utf-8")
    atomic_write_bytes(path, _fernet(key).encrypt(datos))


def load_encrypted_research_state(path: str, key=None):
    try:
        from cryptography.fernet import InvalidToken
        with open(path, "rb") as archivo:
            datos = _fernet(key).decrypt(archivo.read())
    except (OSError, InvalidToken) as exc:
        raise RuntimeError("No se pudo descifrar el estado: clave o contenido inválido") from exc
    try:
        state = json.loads(datos.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Estado descifrado inválido") from exc
    contexto = context_from_state(state)
    report = state.get("report", "")
    completed = state.get("completed", False)
    if not isinstance(report, str) or not isinstance(completed, bool):
        raise RuntimeError("Campos report/completed inválidos en el estado")
    return contexto, report, completed
