#!/usr/bin/env python3
"""
Deep Research Decision-Making System
=====================================

A complete LLM-powered research agent that makes autonomous decisions about
research planning, source retrieval, evidence evaluation, and report generation.

Implements the architecture from the guide: question decomposition, iterative
search, claim verification, and structured report generation with citations.
"""

import json
import os
import random
import re
import sys
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple

from web_search import (DuckDuckGoSearchAPI, MockSearchAPI, SearchAPI,  # noqa: F401
                        WikipediaSearchAPI, formulate_query)


class ResearchContext:
    """Context object holding research state, sources, and decisions."""

    def __init__(self, question: str, max_iterations: int = 5):
        self.question = question
        self.max_iterations = max_iterations
        self.iteration = 0
        self.subquestions: List[str] = []
        self.sources: List[Dict[str, Any]] = []
        self.claims: List[Dict[str, Any]] = []
        self.evaluations: List[Dict[str, Any]] = []
        self.conclusions: List[Dict[str, Any]] = []
        self.decision_log: List[Dict[str, Any]] = []
        self.start_time = time.time()

    def add_decision(self, step: str, decision: str, rationale: str = ""):
        self.decision_log.append({
            "step": step,
            "decision": decision,
            "rationale": rationale,
            "timestamp": time.time(),
            "iteration": self.iteration
        })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "iterations": self.iteration,
            "subquestions": self.subquestions,
            "num_sources": len(self.sources),
            "num_claims": len(self.claims),
            "num_evaluations": len(self.evaluations),
            "num_conclusions": len(self.conclusions),
            "decisions": len(self.decision_log)
        }


class DecisionEngine(ABC):
    """Abstract base class for decision-making components."""

    @abstractmethod
    def decide(self, context: ResearchContext) -> Any:
        pass


class QuestionDecomposer(DecisionEngine):
    """Decomposes the research question into sub-questions using LLM reasoning."""

    def __init__(self, llm_provider):
        self.llm_provider = llm_provider

    def decide(self, context: ResearchContext) -> List[str]:
        if context.iteration == 0:
            prompt = f"""Research Question: {context.question}

Decompose this into 3-5 specific sub-questions that, if answered, would
completely address the original question. Focus on different aspects or
perspectives. Return only the sub-questions, one per line, no numbering or bullets."""

            response = self.llm_provider.generate(prompt)
            # Los modelos reales suelen añadir numeración/bullets o viñetas:
            # se limpian para quedarnos con el texto de la sub-pregunta.
            subquestions = []
            for line in response.split("\n"):
                cleaned = re.sub(r"^\s*(?:[-*\u2022\u2013]|\d+[.)])\s*", "", line).strip()
                if cleaned:
                    subquestions.append(cleaned)
            context.subquestions = subquestions[:5]
            context.add_decision("question_decomposition", "decompose",
                                 f"Generated {len(context.subquestions)} sub-questions")
            return context.subquestions
        return context.subquestions


class SourceRetriever(DecisionEngine):
    """Retrieves sources for sub-questions using web search or document search."""

    def __init__(self, search_api):
        self.search_api = search_api

    def decide(self, context: ResearchContext, subquestion: str) -> List[Dict[str, Any]]:
        context.iteration += 1

        # Los buscadores por palabras clave no entienden preguntas largas:
        # se formula la consulta anclada al tema (términos de la pregunta
        # original) y, si no hay resultados, se amplía progresivamente.
        # Cada reintento se registra (nunca en silencio).
        anchors = formulate_query(context.question, 3).split()
        candidatas = [
            formulate_query(subquestion, 4, anchor_terms=anchors),
            formulate_query(subquestion, 6, anchor_terms=anchors),
            " ".join(anchors),
            subquestion.strip(),
        ]
        queries = [q for q in dict.fromkeys(candidatas) if q]

        results: List[Dict[str, Any]] = []
        query = queries[0]
        for query in queries:
            results = self.search_api.search(query)
            if results:
                break
            context.add_decision("source_retrieval", "requery",
                                 f"Sin resultados para '{query[:40]}'; "
                                 f"se amplía la consulta")

        known_urls = {s.get("url") for s in context.sources}
        added = 0
        for result in results[:5]:
            url = result.get("url", "")
            if url and url in known_urls:
                continue  # no repetir fuentes ya recuperadas
            known_urls.add(url)
            source = {
                "title": result.get("title", ""),
                "url": url,
                "snippet": result.get("snippet", ""),
                "source": result.get("source", "unknown"),
                "retrieved_at": time.time(),
                "related_to": subquestion,
                "query_used": query,
            }
            context.sources.append(source)
            added += 1

        context.add_decision("source_retrieval", "retrieve",
                             f"{added} fuentes nuevas para: {subquestion[:50]}")

        return results


def _parse_json_response(response: str) -> Any:
    """Extrae JSON de una respuesta LLM tolerando bloques markdown.

    Los modelos reales suelen envolver el JSON en ```json ... ``` o añadir
    texto alrededor. Eleva json.JSONDecodeError si no hay JSON válido.
    """
    text = response.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"[\[{].*[\]}]", text, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


class ClaimExtractor(DecisionEngine):
    """Extracts claims from retrieved sources for verification."""

    def __init__(self, llm_provider):
        self.llm_provider = llm_provider

    def decide(self, context: ResearchContext, source: Dict[str, Any]) -> List[Dict[str, Any]]:
        prompt = f"""Extract factual claims from this text snippet. For each claim, provide:
1. The claim statement
2. A confidence score (0-1) based on how well-supported it appears
3. The source URL it came from

Snippet: {source.get("snippet", "")[:500]}

Return ONLY a JSON array (no markdown fences, no extra text) with fields:
"claim", "confidence", "source_url"
"""

        response = self.llm_provider.generate(prompt)
        try:
            claims = _parse_json_response(response)
            if not isinstance(claims, list):
                raise json.JSONDecodeError("se esperaba un array JSON", str(claims), 0)
            for claim in claims:
                claim["source_id"] = source.get("url", "unknown")
                claim["extracted_at"] = time.time()
            context.claims.extend(claims)
            context.add_decision("claim_extraction", "extract",
                                 f"Extracted {len(claims)} claims from {source.get('url', 'unknown')}")
            return claims
        except (json.JSONDecodeError, TypeError):
            context.add_decision("claim_extraction", "fail",
                                 "Failed to parse LLM response")
            return []


class EvidenceEvaluator(DecisionEngine):
    """Evaluates claims against evidence and assesses credibility."""

    def __init__(self, llm_provider):
        self.llm_provider = llm_provider

    def decide(self, context: ResearchContext, claim: Dict[str, Any]) -> Dict[str, Any]:
        relevant_sources = [
            s for s in context.sources
            if s.get("url") == claim.get("source_url")
        ]

        if not relevant_sources:
            relevant_sources = context.sources[:3]

        source_parts = ""
        for i, s in enumerate(relevant_sources):
            source_parts += f"Source {i+1}: {s.get('title', 'Unknown')}: {s.get('snippet', '')[:200]}\n"

        prompt = f"""Evaluate this claim against the provided sources. Determine:
1. Is the claim supported, contradicted, or not addressed?
2. What is the overall credibility score (0-1) of the supporting sources?
3. Are there contradictions from other sources?

Claim: {claim.get("claim", "")}
{source_parts}

Return ONLY JSON (no markdown fences, no extra text):
{{"verdict": "supported|contradicted|not_addressed", "credibility": 0-1, "confidence": 0-1, "reasoning": "..."}}"""

        response = self.llm_provider.generate(prompt)
        try:
            evaluation = _parse_json_response(response)
            if not isinstance(evaluation, dict):
                raise json.JSONDecodeError("se esperaba un objeto JSON", str(evaluation), 0)
            evaluation["claim"] = claim.get("claim", "")
            evaluation["source_url"] = claim.get("source_url", "")
            evaluation["evaluated_at"] = time.time()
            context.evaluations.append(evaluation)
            verdict = evaluation.get("verdict", "not_addressed")
            credibility = evaluation.get("credibility", 0)
            context.add_decision("evidence_evaluation", "evaluate",
                                 f"Verdict: {verdict}, Credibility: {credibility:.2f}")
            return evaluation
        except (json.JSONDecodeError, TypeError):
            eval_result = {
                "verdict": "not_addressed",
                "credibility": 0.0,
                "confidence": 0.0,
                "reasoning": "Failed to parse evaluation",
                "claim": claim.get("claim", ""),
                "source_url": claim.get("source_url", ""),
                "evaluated_at": time.time()
            }
            context.evaluations.append(eval_result)
            return eval_result


class ReportGenerator(DecisionEngine):
    """Generates the final research report with citations and structure."""

    def __init__(self, llm_provider):
        self.llm_provider = llm_provider

    def decide(self, context: ResearchContext) -> str:
        supported_claims = [c for c in context.claims if any(
            e.get("verdict") == "supported" for e in context.evaluations
            if e.get("claim") == c.get("claim"))]

        contradictions = [e for e in context.evaluations if e.get("verdict") == "contradicted"]

        uncertain = [c for c in context.claims if not any(
            e.get("verdict") == "supported" for e in context.evaluations
            if e.get("claim") == c.get("claim"))]

        prompt = f"""Generate a comprehensive research report for: {context.question}

Structure:
1. Executive Summary (2-3 paragraphs)
2. Findings (organized by sub-question from: {context.subquestions})
3. Evidence Assessment (supported claims with source citations, contradictions, uncertainties)
4. Conclusions (what can be definitively stated, what remains uncertain)
5. Limitations and Research Gaps

Claim data:
- Total claims extracted: {len(context.claims)}
- Supported: {len(supported_claims)}
- Contradictions: {len(contradictions)}
- Uncertain/Unsupported: {len(uncertain)}

Source data:
- Total sources retrieved: {len(context.sources)}

Evidence evaluations: {len(context.evaluations)}

Generate the full report in markdown format with proper citations [1], [2] etc.
matching the sources retrieved. Be factual and acknowledge uncertainties."""

        report = self.llm_provider.generate(prompt)
        context.conclusions = self._extract_conclusions(report)
        context.add_decision("report_generation", "generate",
                             f"Report generated with {len(context.conclusions)} conclusion sections")
        return report

    def _extract_conclusions(self, report: str) -> List[Dict[str, Any]]:
        sections = re.split(r'\n#+\s*', report)
        conclusions = []
        for section in sections[-3:] if len(sections) >= 3 else sections:
            if section.strip():
                conclusions.append({"section": section[:100], "length": len(section)})
        return conclusions


class ResearchOrchestrator:
    """Orchestrates the complete research process with decision-making."""

    def __init__(self, llm_provider, search_api, max_iterations: int = 5):
        self.llm = llm_provider
        self.search = search_api
        self.context = ResearchContext("pending", max_iterations)
        self.decomposer = QuestionDecomposer(llm_provider)
        self.retriever = SourceRetriever(search_api)
        self.extractor = ClaimExtractor(llm_provider)
        self.evaluator = EvidenceEvaluator(llm_provider)
        self.generator = ReportGenerator(llm_provider)

    def research(self, question: str) -> Tuple[str, ResearchContext]:
        """Execute the full research pipeline."""
        self.context = ResearchContext(question, self.context.max_iterations)

        # Step 1: Decompose question
        subquestions = self.decomposer.decide(self.context)
        if not subquestions:
            return "Could not decompose research question", self.context

        # Step 2: For each subquestion, retrieve sources and extract claims
        for sq in subquestions:
            results = self.retriever.decide(self.context, sq)
            for result in results[:3]:
                self.extractor.decide(self.context, {
                    "url": result.get("url", ""),
                    "snippet": result.get("snippet", "")
                })

        # Step 3: Evaluate all claims against evidence
        for claim in self.context.claims[:]:
            self.evaluator.decide(self.context, claim)

        # Step 4: Generate final report
        report = self.generator.decide(self.context)

        return report, self.context


# LLM Provider Interface
class LLMProvider(ABC):
    """Interface for LLM providers (Ollama, OpenAI, etc.)."""

    @abstractmethod
    def generate(self, prompt: str, model: str = "llama3.2") -> str:
        pass


# Errores transitorios de proveedor que justifican reintento (P1.34)
TRANSIENT_STATUS = {429, 500, 502, 503, 504}


def _chat_completion(client, model: str, prompt: str, max_retries: int, label: str) -> str:
    """Llama al endpoint de chat con reintentos y backoff exponencial + jitter.

    Reintenta solo errores transitorios (5xx, 429, red/timeout), informando
    cada reintento por stderr. Al agotar los intentos eleva el último error
    (fallo ruidoso, nunca silencioso). P1.34/P1.19.
    """
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content or ""
        except Exception as exc:  # noqa: BLE001 - se reeleva tras agotar
            last_error = exc
            status = getattr(exc, "status_code", None)
            transient = status is None or status in TRANSIENT_STATUS
            if attempt >= max_retries or not transient:
                raise
            delay = (2 ** attempt) + random.uniform(0, 1)
            print(f"[{label}] error transitorio ({status or type(exc).__name__}); "
                  f"reintento {attempt}/{max_retries - 1} en {delay:.1f}s",
                  file=sys.stderr)
            time.sleep(delay)
    raise last_error


# OpenAI-compatible implementation (openai>=1.0 SDK)
class OpenAILLM(LLMProvider):
    """Cliente para la API de OpenAI o cualquier endpoint compatible.

    La API key se toma del argumento `api_key`, de kwargs en `generate()`,
    o de las variables de entorno OPENAI_API_KEY / OPENROUTER_API_KEY.
    """

    def __init__(self, api_key: str = None, model: str = "gpt-4o-mini",
                 base_url: str = None, max_retries: int = 3):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model
        self.base_url = base_url
        self.max_retries = max_retries

    def generate(self, prompt: str, model: str = None, **kwargs) -> str:
        key = kwargs.pop("api_key", None) or self.api_key
        base_url = kwargs.pop("base_url", None) or self.base_url
        if not key:
            raise ValueError(
                "OpenAI API key required. Provide api_key or set OPENAI_API_KEY."
            )
        from openai import OpenAI
        client = OpenAI(api_key=key, base_url=base_url)
        return _chat_completion(client, model or self.model, prompt,
                                self.max_retries, "OpenAILLM")


# OpenRouter implementation (endpoint compatible con OpenAI)
# Modelo gratuito por defecto (verificado 2026-10-14 con llamada real).
# Se puede sobreescribir con la variable de entorno OPENROUTER_MODEL.
DEFAULT_FREE_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"


class OpenRouterLLM(OpenAILLM):
    """Cliente para OpenRouter (https://openrouter.ai/api/v1).

    Usa OPENROUTER_API_KEY del entorno si no se pasa `api_key`.
    Modelo por defecto: OPENROUTER_MODEL si está definido, si no un modelo
    GRATUITO (`:free`, coste 0). Modelos con formato "proveedor/modelo".
    """

    def __init__(self, api_key: str = None, model: str = None,
                 base_url: str = "https://openrouter.ai/api/v1"):
        super().__init__(
            api_key=api_key or os.environ.get("OPENROUTER_API_KEY", ""),
            model=model or os.environ.get("OPENROUTER_MODEL", DEFAULT_FREE_MODEL),
            base_url=base_url,
        )


# Ollama implementation (local)
class OllamaLLM(LLMProvider):
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.2"):
        self.base_url = base_url
        self.model = model

    def generate(self, prompt: str, model: str = None, **kwargs) -> str:
        import requests
        url = f"{self.base_url}/api/generate"
        payload = {"model": model or self.model, "prompt": prompt, "stream": False}
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        return response.json().get("response", "")


# Kilo AI Gateway implementation (unified API with BYOK)
class KiloGatewayLLM(LLMProvider):
    """Conecta al Kilo AI Gateway para acceder a cientos de modelos con una sola key.

    Base URL: https://api.kilo.ai/api/gateway
    Características:
    - BYOK (Bring Your Own Key): usa tu propia API key de proveedores
    - Acceso a cientos de modelos (Anthropic, OpenAI, Google, Mistral, etc.)
    - API compatible con OpenAI: mismo formato de petición
    - Tracking de uso y costos
    """

    def __init__(self, api_key: str = None, model: str = None,
                 base_url: str = "https://api.kilo.ai/api/gateway",
                 max_retries: int = 3):
        self.api_key = api_key or os.environ.get("KILO_API_KEY", "")
        self.model = model or "anthropic/claude-sonnet-4"
        self.base_url = base_url
        self.max_retries = max_retries

    def generate(self, prompt: str, model: str = None, **kwargs) -> str:
        key = kwargs.pop("api_key", None) or self.api_key
        if not key:
            raise ValueError(
                "Kilo API key required for KiloGatewayLLM. "
                "Provide api_key parameter or set KILO_API_KEY environment variable."
            )
        from openai import OpenAI
        client = OpenAI(api_key=key, base_url=self.base_url)
        return _chat_completion(client, model or self.model, prompt,
                                self.max_retries, "KiloGatewayLLM")


# Mock LLM for offline demos and tests
class MockLLM(LLMProvider):
    """LLM determinista y offline para demos y tests.

    SIMULADO: no realiza llamadas de red ni usa un modelo real. Devuelve
    respuestas fijas según el tipo de prompt recibido, con el formato que
    cada componente espera (JSON para extractores/evaluadores, texto para
    descomposición e informes).
    """

    def __init__(self, model: str = "mock-llm"):
        self.model = model

    def generate(self, prompt: str, model: str = None, **kwargs) -> str:
        p = prompt.lower()

        if "decompose this into" in p:
            return "\n".join([
                "¿Cuáles son los avances recientes documentados sobre el tema?",
                "¿Qué fuentes primarias describen el estado actual?",
                "¿Qué limitaciones, riesgos e incertidumbres se reportan?",
            ])

        if "extract factual claims" in p:
            return json.dumps([{
                "claim": "Afirmación simulada extraída del snippet por MockLLM",
                "confidence": 0.7,
                "source_url": "https://example.com/mock-source",
            }], ensure_ascii=False)

        if "evaluate this claim" in p:
            return json.dumps({
                "verdict": "supported",
                "credibility": 0.75,
                "confidence": 0.7,
                "reasoning": "Evaluación simulada por MockLLM (offline, sin modelo real)",
            }, ensure_ascii=False)

        if "generate a comprehensive research report" in p:
            return (
                "# Informe de investigación (SIMULADO por MockLLM)\n\n"
                "## Resumen ejecutivo\n\n"
                "Este informe fue generado offline por MockLLM, sin modelo real ni "
                "llamadas de red. Sirve para verificar que el pipeline completo "
                "(descomposición, recuperación, extracción, evaluación y reporte) "
                "funciona de extremo a extremo.\n\n"
                "## Hallazgos\n\n"
                "Los hallazgos reales requieren configurar un proveedor LLM "
                "(OpenAILLM, OpenRouterLLM, KiloGatewayLLM u OllamaLLM).\n\n"
                "## Conclusiones\n\n"
                "Pipeline verificado. Sustituir MockLLM por un proveedor real "
                "para obtener contenido genuino.\n"
            )

        paso = re.search(r"paso (\d)", p)
        if paso:
            n = paso.group(1)
            return json.dumps({
                "paso": int(n),
                "contenido": f"Respuesta simulada por MockLLM para el paso {n}",
                "confianza": 0.7,
                "nota": "Salida offline determinista, sin modelo real",
            }, ensure_ascii=False)

        return ("Respuesta simulada por MockLLM (offline): "
                "el prompt no corresponde a un patrón conocido.")


# Los proveedores de búsqueda viven en web_search.py:
#   MockSearchAPI (offline/simulado), WikipediaSearchAPI y DuckDuckGoSearchAPI
#   (reales, sin API key). Se importan arriba.


# Demo/CLI entry point
def main():
    print("=== Deep Research Decision-Making System ===\n")
    print("This system implements autonomous decision-making for deep research.")
    print("It decomposes questions, retrieves evidence, evaluates claims,")
    print("and generates structured reports with citations.\n")

    # Demo offline con componentes simulados (sin red ni API keys).
    # Para una investigación real, sustituir por un proveedor real:
    #   llm = OpenRouterLLM()   # requiere OPENROUTER_API_KEY en el entorno
    #   llm = OllamaLLM()       # requiere Ollama corriendo en localhost:11434
    llm = MockLLM()
    search = MockSearchAPI()
    orchestrator = ResearchOrchestrator(llm, search, max_iterations=3)

    question = "¿Cuál es el estado actual de la fusión nuclear?"
    print(f"Research question: {question}\n")
    print("=" * 60)

    report, context = orchestrator.research(question)

    print("\n" + "=" * 60)
    print("RESEARCH CONTEXT SUMMARY")
    print("=" * 60)
    summary = context.to_dict()
    for key, value in summary.items():
        print(f"  {key}: {value}")

    print("\n" + "=" * 60)
    print("EXECUTED DECISIONS")
    print("=" * 60)
    for decision in context.decision_log:
        print(f"  Iter {decision['iteration']} | {decision['step']}: {decision['decision']}")
        if decision['rationale']:
            print(f"    Razón: {decision['rationale']}")

    print("\n" + "=" * 60)
    print("REPORT EXCERPT (first 500 chars)")
    print("=" * 60)
    print(report[:500] if report else "No report generated")

    print("\n" + "=" * 60)
    print("HARDWARE RECOMMENDATIONS (from guide)")
    print("=" * 60)
    print("""- Portable without dedicated GPU: Start with 3B-4B model
- GPU with 12-16 GB VRAM: Supports 7B-14B quantized models
- Mac Apple Silicon: Unified memory useful for local models
- Costs: Inference, search limits, GPU/hosting, maintenance""")

    print("\n" + "=" * 60)
    print("PRIVACY & SECURITY")
    print("=" * 60)
    print("""- Verify licenses of code, models, and datasets
- Use virtual environment or container isolation
- Do not provide personal credentials to third-party code
- Limit file, network, and command execution permissions
- Treat retrieved web pages as untrusted content""")

    print("\n=== End of Research Session ===")


if __name__ == "__main__":
    main()