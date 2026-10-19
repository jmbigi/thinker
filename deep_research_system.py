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
import re
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from web_search import (DuckDuckGoSearchAPI, MockSearchAPI, SearchAPI,  # noqa: F401
                        WikipediaSearchAPI, formulate_query)
from llm_providers import (DEFAULT_FREE_MODEL, KiloGatewayLLM,  # noqa: F401
                           LLMProvider, MockLLM, OllamaLLM, OpenAILLM,
                           OpenRouterLLM, TRANSIENT_STATUS, _chat_completion)


class ResearchContext:
    """Context object holding research state, sources, and decisions."""

    def __init__(self, question: str, max_iterations: int = 5):
        self.question = question
        self.max_iterations = max_iterations
        self.iteration = 0
        self.decomposed = False
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
            "decomposed": self.decomposed,
            "iterations": self.iteration,
            "subquestions": self.subquestions,
            "num_sources": len(self.sources),
            "num_claims": len(self.claims),
            "num_evaluations": len(self.evaluations),
            "num_conclusions": len(self.conclusions),
            "decisions": len(self.decision_log),
            "duration_seconds": round(time.time() - self.start_time, 3),
        }


class DecisionEngine(ABC):
    """Abstract base class for decision-making components."""

    @abstractmethod
    def decide(self, context: ResearchContext) -> Any:
        pass  # pragma: no cover - cuerpo abstracto, nunca se ejecuta


class QuestionDecomposer(DecisionEngine):
    """Decomposes the research question into sub-questions using LLM reasoning."""

    def __init__(self, llm_provider):
        self.llm_provider = llm_provider

    def decide(self, context: ResearchContext) -> List[str]:
        if not context.decomposed:
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
            context.decomposed = True
            context.add_decision("question_decomposition", "decompose",
                                 f"Generated {len(context.subquestions)} sub-questions")
            return context.subquestions
        return context.subquestions


class RelevanceJudge:
    """Evaluador ligero de relevancia de la recuperación (tipo CRAG).

    Referencia: arXiv:2401.15884 (Corrective RAG). Pregunta al LLM si los
    resultados de una consulta son relevantes para la subpregunta. Devuelve un
    float 0-1, o `None` si el juez no responde JSON válido (el llamador decide:
    aquí se documenta y se acepta la evidencia — fail-open, nunca silencioso).
    """

    def __init__(self, llm_provider):
        self.llm_provider = llm_provider

    def evaluar(self, subquestion: str,
                resultados: List[Dict[str, Any]]) -> Optional[float]:
        muestras = "\n".join(
            f"- {r.get('title', '')}: {r.get('snippet', '')[:150]}"
            for r in resultados[:3])
        prompt = f"""Evalúa si estos resultados de búsqueda son RELEVANTES para la
subpregunta. Responde SOLO JSON: {{"relevancia": 0-1, "motivo": "..."}}

Subpregunta: {subquestion}

Resultados:
{muestras}"""
        try:
            datos = _parse_json_response(self.llm_provider.generate(prompt))
            if not isinstance(datos, dict):
                raise json.JSONDecodeError("se esperaba un objeto JSON",
                                           str(datos), 0)
            return float(datos.get("relevancia", 0))
        except (json.JSONDecodeError, TypeError, ValueError):
            return None


class SourceRetriever(DecisionEngine):
    """Retrieves sources for sub-questions using web search or document search.

    Con `evaluador_relevancia` (opt-in) aplica la acción correctiva de CRAG:
    si los resultados de una consulta puntúan por debajo de `umbral_relevancia`
    y quedan candidatas, se reformula la consulta en vez de aceptar ruido.
    """

    def __init__(self, search_api, evaluador_relevancia=None,
                 umbral_relevancia: float = 0.5):
        self.search_api = search_api
        self.evaluador_relevancia = evaluador_relevancia
        self.umbral_relevancia = umbral_relevancia

    def _relevante(self, context: ResearchContext, subquestion: str,
                   candidatos: List[Dict[str, Any]]) -> bool:
        """Sin evaluador, todo es relevante; con él, se consulta al juez."""
        if self.evaluador_relevancia is None:
            return True
        puntuacion = self.evaluador_relevancia.evaluar(subquestion, candidatos)
        if puntuacion is None:
            context.add_decision("source_retrieval", "crag_sin_juez",
                                 "El juez de relevancia no devolvió JSON: se "
                                 "acepta la evidencia (fail-open, registrado)")
            return True
        return puntuacion >= self.umbral_relevancia

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
        if not queries:
            context.add_decision("source_retrieval", "no_results",
                                 "Sin consulta posible (subpregunta vacía)")
            return []

        results: List[Dict[str, Any]] = []
        query = queries[0]
        for posicion, query in enumerate(queries):
            candidatos = self.search_api.search(query)
            if candidatos:
                relevante = self._relevante(context, subquestion, candidatos)
                if relevante or posicion >= len(queries) - 1:
                    if not relevante:
                        context.add_decision(
                            "source_retrieval", "crag_aceptar",
                            "Relevancia baja pero no quedan candidatas: se "
                            "acepta lo recuperado")
                    results = candidatos
                    break
                context.add_decision(
                    "source_retrieval", "crag_reformular",
                    f"Resultados poco relevantes para '{query[:40]}'; "
                    f"se reformula la consulta")
                continue
            if posicion < len(queries) - 1:
                context.add_decision("source_retrieval", "requery",
                                     f"Sin resultados para '{query[:40]}'; "
                                     f"se amplía la consulta")
            else:
                # Última candidata: no se promete una ampliación que ya no existe.
                context.add_decision("source_retrieval", "no_results",
                                     f"Sin resultados tras {len(queries)} "
                                     f"consultas para: {subquestion[:50]}")

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
        # Decodificador por posición en vez de regex codiciosa: con varios
        # bloques ("{mal} luego [bien]") la regex tomaba del primer `{` al
        # último `]` y fallaba; así se devuelve el primer JSON decodificable.
        decoder = json.JSONDecoder()

        def _decodifica_en(posicion: int) -> Any:
            """Primer JSON válido que empieza en `posicion`, o None."""
            try:
                return decoder.raw_decode(text[posicion:])[0]
            except json.JSONDecodeError:
                return None

        for i, ch in enumerate(text):
            if ch in "[{":
                obj = _decodifica_en(i)
                if obj is not None:
                    return obj
        raise


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
    """Evaluates claims against evidence and assesses credibility.

    Con `verificacion_independiente=True` añade una segunda pasada tipo CoVe
    (arXiv:2309.11495): el mismo claim se evalúa contra las fuentes que NO lo
    originaron, para detectar confirmaciones circulares (el evaluador normal
    mira los snippets que produjeron el claim). Cuesta una llamada extra por
    claim: está desactivado por defecto.

    Separación generador/verificador: `llm_verificador` permite que la pasada
    independiente use OTRO proveedor, distinto del que generó y evaluó. La
    independencia real se declara por claim (`independencia`:
    "proveedor-distinto" | "mismo-proveedor"): sin verificador separado (o con
    el mismo objeto) la pasada se ejecuta igual, pero queda declarada como
    degradada —nunca se finge una independencia que no existe.

    Consenso por muestreo (piloto): `muestras_consenso > 1` repite la
    evaluación del claim ese número de veces y declara `consenso_muestreo`
    (`acuerdo` y veredictos por muestra). Si los veredictos divergen, marca
    `discrepancia_muestreo` y lo registra en el `decision_log` para revisión
    humana: una respuesta que cambia entre muestras es señal de alucinación o
    de juicio inestable. Coste declarado: `muestras_consenso - 1` llamadas
    extra por claim. Con 1 (defecto) el comportamiento es el original.
    """

    def __init__(self, llm_provider, verificacion_independiente: bool = False,
                 llm_verificador=None, muestras_consenso: int = 1):
        self.llm_provider = llm_provider
        self.verificacion_independiente = verificacion_independiente
        self.llm_verificador = llm_verificador
        if not isinstance(muestras_consenso, int) or isinstance(muestras_consenso, bool) \
                or muestras_consenso < 1:
            raise ValueError("muestras_consenso debe ser un entero >= 1")
        self.muestras_consenso = muestras_consenso

    @staticmethod
    def _prompt_evaluacion(claim: Dict[str, Any], fuentes: List[Dict[str, Any]]) -> str:
        source_parts = ""
        for i, s in enumerate(fuentes):
            source_parts += (f"Source {i+1}: {s.get('title', 'Unknown')}: "
                             f"{s.get('snippet', '')[:200]}\n")

        return f"""Evaluate this claim against the provided sources. Determine:
1. Is the claim supported, contradicted, or not addressed?
2. What is the overall credibility score (0-1) of the supporting sources?
3. Are there contradictions from other sources?

Claim: {claim.get("claim", "")}
{source_parts}

Return ONLY JSON (no markdown fences, no extra text):
{{"verdict": "supported|contradicted|not_addressed", "credibility": 0-1, "confidence": 0-1, "reasoning": "..."}}"""

    def decide(self, context: ResearchContext, claim: Dict[str, Any]) -> Dict[str, Any]:
        evaluation = self._evaluar(context, claim)
        if self.verificacion_independiente:
            evaluation["verificacion_independiente"] = self._evaluar_independiente(
                context, claim, evaluation.get("verdict", "not_addressed"))
        return evaluation

    @staticmethod
    def _normalizar_credibilidad(valor: Any) -> Tuple[float, Optional[str]]:
        """Convierte la credibilidad a float en [0, 1] sin tumbar el pipeline.

        Los modelos reales devuelven a veces `"0.75"` (string), `null` u otro
        formato; formatear `{credibility:.2f}` sobre eso elevaba un ValueError
        no capturado y abortaba `research()` (P1.19: se normaliza y se sigue).
        """
        try:
            numero = float(valor)
        except (TypeError, ValueError):
            return 0.0, str(valor)
        return min(max(numero, 0.0), 1.0), None

    @staticmethod
    def _nombre_proveedor(proveedor: Any) -> str:
        """Nombre estable del proveedor para declararlo en los resultados."""
        modelo = getattr(proveedor, "model", None)
        return modelo if isinstance(modelo, str) and modelo else type(proveedor).__name__

    def _es_verificador_distinto(self) -> bool:
        """Independencia real: el verificador es OTRO objeto, no el generador."""
        return (self.llm_verificador is not None
                and self.llm_verificador is not self.llm_provider)

    def _evaluar(self, context: ResearchContext, claim: Dict[str, Any]) -> Dict[str, Any]:
        relevant_sources = [
            s for s in context.sources
            if s.get("url") == claim.get("source_url")
        ]

        if not relevant_sources:
            relevant_sources = context.sources[:3]

        response = self.llm_provider.generate(
            self._prompt_evaluacion(claim, relevant_sources))
        try:
            evaluation = _parse_json_response(response)
            if not isinstance(evaluation, dict):
                raise json.JSONDecodeError("se esperaba un objeto JSON", str(evaluation), 0)
            credibility, valor_invalido = self._normalizar_credibilidad(
                evaluation.get("credibility", 0))
            evaluation["credibility"] = credibility
            if valor_invalido is not None:
                # Trazabilidad del valor original no numérico (null, "alto"...).
                evaluation["credibility_raw"] = valor_invalido
            evaluation["claim"] = claim.get("claim", "")
            evaluation["source_url"] = claim.get("source_url", "")
            evaluation["evaluated_at"] = time.time()
            context.evaluations.append(evaluation)
            verdict = evaluation.get("verdict", "not_addressed")
            context.add_decision("evidence_evaluation", "evaluate",
                                 f"Verdict: {verdict}, Credibility: {credibility:.2f}")
            if self.muestras_consenso > 1:
                self._consolidar_consenso(context, evaluation, claim,
                                          relevant_sources)
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
            if self.muestras_consenso > 1:
                self._consolidar_consenso(context, eval_result, claim,
                                          relevant_sources)
            return eval_result

    def _consolidar_consenso(self, context: ResearchContext,
                             evaluation: Dict[str, Any],
                             claim: Dict[str, Any],
                             fuentes: List[Dict[str, Any]]) -> None:
        """Muestreo adicional del MISMO prompt: veredictos divergentes = señal.

        Una evaluación que cambia entre muestras idénticas delata un juicio
        inestable o alucinado; se marca `discrepancia_muestreo` y se registra
        en el `decision_log` para revisión humana (nunca en silencio).
        """
        veredictos = [evaluation.get("verdict", "not_addressed")]
        for _ in range(self.muestras_consenso - 1):
            try:
                datos = _parse_json_response(self.llm_provider.generate(
                    self._prompt_evaluacion(claim, fuentes)))
                veredicto = (datos.get("verdict", "not_addressed")
                             if isinstance(datos, dict) else "not_addressed")
            except (json.JSONDecodeError, TypeError):
                veredicto = "not_addressed"
                evaluation["consenso_parse_fallo"] = True  # declarado
            veredictos.append(veredicto)

        acuerdo = all(veredicto == veredictos[0] for veredicto in veredictos)
        evaluation["consenso_muestreo"] = {
            "muestras": self.muestras_consenso,
            "llamadas_extra": self.muestras_consenso - 1,
            "verdicts": veredictos,
            "acuerdo": acuerdo,
        }
        if not acuerdo:
            evaluation["discrepancia_muestreo"] = True
            context.add_decision(
                "sampling_consensus", "discrepancia",
                f"Veredictos divergentes: {', '.join(veredictos)} — "
                "el claim queda marcado para revisión humana")
        else:
            context.add_decision(
                "sampling_consensus", "acuerdo",
                f"{self.muestras_consenso}/{self.muestras_consenso} muestras "
                f"coinciden: {veredictos[0]}")

    def _evaluar_independiente(self, context: ResearchContext, claim: Dict[str, Any],
                               verdict_principal: str) -> Optional[Dict[str, Any]]:
        """Segunda pasada CoVe contra fuentes que NO originaron el claim.

        Devuelve `None` (y lo registra) si no hay fuentes alternativas: no se
        inventa una verificación sin evidencia distinta que mirar. La pasada
        usa el verificador separado si lo hay y declara la independencia real
        ("proveedor-distinto" | "mismo-proveedor").
        """
        # Origen verificado por el pipeline (`source_id` lo fija el extractor
        # con la URL real de la fuente); `source_url` es solo lo que dijo el
        # modelo y puede faltar o venir mal, re-incluyendo la fuente original.
        origen = claim.get("source_id") or claim.get("source_url")
        alternativas = [s for s in context.sources
                        if s.get("url") and s.get("url") != origen]
        if not alternativas:
            context.add_decision("independent_verification", "skip",
                                 "Sin fuentes alternativas para verificar el claim")
            return None

        distinto = self._es_verificador_distinto()
        verificador = self.llm_verificador if distinto else self.llm_provider
        independencia = "proveedor-distinto" if distinto else "mismo-proveedor"
        declaracion = {
            "independencia": independencia,
            "verificador": self._nombre_proveedor(verificador),
            "generador": self._nombre_proveedor(self.llm_provider),
        }

        response = verificador.generate(
            self._prompt_evaluacion(claim, alternativas[:3]))
        try:
            datos = _parse_json_response(response)
            if not isinstance(datos, dict):
                raise json.JSONDecodeError("se esperaba un objeto JSON", str(datos), 0)
        except (json.JSONDecodeError, TypeError):
            return {**declaracion,
                    "verdict": "not_addressed", "credibility": 0.0,
                    "confidence": 0.0, "verdict_principal": verdict_principal,
                    "contested": False, "fuentes_alternativas": len(alternativas),
                    "error": "Failed to parse evaluation"}

        verdict = datos.get("verdict", "not_addressed")
        contested = (verdict != verdict_principal) and (verdict != "not_addressed")
        context.add_decision("independent_verification", "verify",
                             f"[{independencia}] Independiente: {verdict} vs principal: "
                             f"{verdict_principal} -> "
                             f"{'contestado' if contested else 'coincide'}")
        return {**declaracion,
                "verdict": verdict,
                "credibility": datos.get("credibility", 0),
                "confidence": datos.get("confidence", 0),
                "verdict_principal": verdict_principal,
                "contested": contested,
                "fuentes_alternativas": len(alternativas)}


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

        # Grounding: el informe debe poder citar lo recuperado. Sin fuentes ni
        # claims en el prompt, el modelo inventaría las citas exigidas (P0.2).
        fuentes_txt = ""
        for i, s in enumerate(context.sources, 1):
            fuentes_txt += (f"[{i}] {s.get('title', 'Untitled')} — {s.get('url', '')}\n"
                            f"    {s.get('snippet', '')[:200]}\n")
        if not fuentes_txt:
            fuentes_txt = "(no sources retrieved)\n"

        veredicto_por_claim = {e.get("claim", ""): e.get("verdict", "not_addressed")
                               for e in context.evaluations}
        claims_txt = ""
        for c in context.claims:
            texto_claim = c.get("claim", "")
            veredicto = veredicto_por_claim.get(texto_claim, "not evaluated")
            origen = c.get("source_id") or c.get("source_url") or "unknown"
            claims_txt += f"- [{veredicto}] {texto_claim[:200]} (source: {origen})\n"
        if not claims_txt:
            claims_txt = "(no claims extracted)\n"

        prompt = f"""Generate a comprehensive research report for: {context.question}

Use ONLY the retrieved sources and evaluated claims below as evidence. Cite
sources as [n] matching their numbers. If the evidence is insufficient for a
statement, say so instead of inventing it.

Retrieved sources:
{fuentes_txt}
Evaluated claims:
{claims_txt}
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

    def __init__(self, llm_provider, search_api, max_iterations: int = 5,
                 verificacion_independiente: bool = False, llm_rapido=None,
                 llm_verificador=None, muestras_consenso: int = 1,
                 evaluador_relevancia: bool = False,
                 umbral_relevancia: float = 0.5):
        """Monta el pipeline.

        `llm_rapido` (enrutado por tarea): si se pasa, descompone y extrae con
        él —tareas estructuradas— y reserva `llm_provider` para evaluar y
        redactar. `evaluador_relevancia=True` activa el juez CRAG en la
        recuperación (una llamada extra por consulta con resultados).
        `llm_verificador` (separación generador/verificador): proveedor para la
        pasada CoVe con `verificacion_independiente=True`. Si es None o el
        mismo objeto que el generador, la pasada corre igual pero se declara
        como `mismo-proveedor` (independencia degradada, nunca silenciosa).
        `muestras_consenso` (>1): repite la evaluación de cada claim para
        detectar veredictos divergentes (ver `EvidenceEvaluator`).
        """
        self.llm = llm_provider
        self.llm_rapido = llm_rapido or llm_provider
        self.search = search_api
        self.context = ResearchContext("pending", max_iterations)
        self.decomposer = QuestionDecomposer(self.llm_rapido)
        juez = RelevanceJudge(self.llm_rapido) if evaluador_relevancia else None
        self.retriever = SourceRetriever(search_api, evaluador_relevancia=juez,
                                         umbral_relevancia=umbral_relevancia)
        self.extractor = ClaimExtractor(self.llm_rapido)
        self.evaluator = EvidenceEvaluator(
            llm_provider, verificacion_independiente=verificacion_independiente,
            llm_verificador=llm_verificador,
            muestras_consenso=muestras_consenso)
        self.generator = ReportGenerator(llm_provider)

    def research(self, question: str) -> Tuple[str, ResearchContext]:
        """Execute the full research pipeline."""
        self.context = ResearchContext(question, self.context.max_iterations)

        # Step 1: Decompose question
        subquestions = self.decomposer.decide(self.context)
        if not subquestions:
            return "Could not decompose research question", self.context

        # `max_iterations` limita de verdad el bucle (antes era un parámetro
        # decorativo): cada subpregunta consume una iteración de recuperación.
        if len(subquestions) > self.context.max_iterations:
            self.context.add_decision(
                "iteration_limit", "truncate",
                f"Se procesan {self.context.max_iterations} de "
                f"{len(subquestions)} subpreguntas (max_iterations)")
            subquestions = subquestions[: self.context.max_iterations]
            self.context.subquestions = subquestions

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


# Los proveedores de búsqueda viven en web_search.py:
#   MockSearchAPI (offline/simulado), WikipediaSearchAPI y DuckDuckGoSearchAPI
#   (reales, sin API key). Se importan arriba.


# CLI principal
def main():
    print("=== Deep Research Decision-Making System ===\n")
    print("This system implements autonomous decision-making for deep research.")
    print("It decomposes questions, retrieves evidence, evaluates claims,")
    print("and generates structured reports with citations.\n")

    # Modo demo offline (ayuda): componentes simulados, sin red ni API keys.
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