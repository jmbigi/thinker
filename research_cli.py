#!/usr/bin/env python3
"""CLI real de investigación; sin argumentos conserva la demo offline previa."""

import argparse
import json
import os
import shlex
import sys
from pathlib import Path

from deep_research_system import ResearchOrchestrator
from documents import CompositeSearchAPI, FullTextSearchAPI, LocalDocumentSearchAPI
from llm_providers import (BudgetLLM, DeepSeekFreeAgentLLM, KiloGatewayLLM,
                           LocalFallbackLLM, MockLLM, OllamaLLM, OpenAILLM,
                           OpenRouterLLM)
from mcp_client import MCPSearchAPI
from research_state import context_to_state
from web_search import (ArxivSearchAPI, DuckDuckGoSearchAPI, MockSearchAPI,
                        PubMedSearchAPI, SemanticScholarSearchAPI, SearXNGSearchAPI,
                        WikipediaSearchAPI)


def _entero_positivo(valor: str) -> int:
    numero = int(valor)
    if numero < 1:
        raise argparse.ArgumentTypeError("debe ser un entero >= 1")
    return numero


def _float_positivo(valor: str) -> float:
    numero = float(valor)
    if numero <= 0:
        raise argparse.ArgumentTypeError("debe ser un número > 0")
    return numero


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="research",
        description="Investiga con evidencia, documentos locales y estado reanudable.")
    parser.add_argument("question", nargs="?", help="pregunta de investigación")
    parser.add_argument("--provider",
                        choices=("mock", "openrouter", "kilo", "forthtrade", "ollama",
                                 "deepseek-free-agent"),
                        default="mock", help="proveedor LLM (defecto: mock offline)")
    parser.add_argument("--model", help="modelo del proveedor")
    parser.add_argument("--ollama-base-url",
                        help="URL base de Ollama (defecto: http://localhost:11434; "
                             "el proxy local usa http://127.0.0.1:11435)")
    parser.add_argument("--ollama-api", choices=("native", "openai"), default="native",
                        help="API de Ollama: nativa /api/generate o compatible OpenAI "
                             "/v1/chat/completions (el proxy local usa openai)")
    parser.add_argument("--deepseek-agent-url",
                        help="URL loopback del agente (o DEEPSEEK_AGENT_URL)")
    parser.add_argument("--deepseek-agent-timeout", type=_float_positivo, default=300.0,
                        help="timeout de lectura del agente en segundos (defecto: 300)")
    parser.add_argument("--authorize-deepseek-agent", action="store_true",
                        help="autoriza egreso a DeepSeek y el riesgo de herramientas externas")
    parser.add_argument("--fallback-model", nargs="?", const="qwen3:8b",
                        help="si el proveedor principal falla (p. ej. cuota 429), "
                             "usa este modelo local de Ollama; opt-in y declarado")
    parser.add_argument("--search", choices=(
        "mock", "wikipedia", "duckduckgo", "local", "searxng", "arxiv",
        "pubmed", "semantic_scholar", "mcp"),
        help="buscador; con documentos y sin esta opción usa solo local")
    parser.add_argument("--documents", action="append", default=[], metavar="RUTA",
                        help="archivo o directorio documental (repetible)")
    parser.add_argument("--searxng-url", help="URL de SearXNG (o variable SEARXNG_URL)")
    parser.add_argument("--allow-private-search", action="store_true",
                        help="permite SearXNG en host privado/localhost (opt-in)")
    parser.add_argument("--mcp-command", help="comando del servidor MCP, sin shell")
    parser.add_argument("--mcp-tool", default="search", help="herramienta MCP permitida")
    parser.add_argument("--mcp-timeout", type=_float_positivo, default=10.0)
    parser.add_argument("--full-text", action="store_true",
                        help="descarga páginas completas en vez de usar solo snippets")
    parser.add_argument("--output", default="-", metavar="ARCHIVO",
                        help="informe de salida; '-' usa stdout")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--json", action="store_true", help="equivalente a --format=json")
    parser.add_argument("--state", metavar="ARCHIVO",
                        help="checkpoint reanudable (contiene fuentes y puede ser sensible)")
    parser.add_argument("--max-iterations", type=_entero_positivo, default=5)
    parser.add_argument("--max-llm-calls", type=_entero_positivo,
                        help="presupuesto por proveedor; al agotarlo falla visiblemente")
    parser.add_argument("--verificacion-independiente", action="store_true",
                        help="activa segunda pasada CoVe (mismo proveedor, declarado)")
    parser.add_argument("--muestras-consenso", type=_entero_positivo, default=1)
    parser.add_argument("--evaluador-relevancia", action="store_true")
    parser.add_argument("--coarse-to-fine", action="store_true")
    parser.add_argument("--ncm-residual", action="store_true",
                        help="conceptos residuales NCM; no es el modelo neural del paper")
    parser.add_argument("--max-workers", type=_entero_positivo, default=1,
                        help="paralelismo acotado dentro de cada nivel")
    parser.add_argument("--privacy", choices=("public", "local-only", "private-documents"),
                        default="public", help="política de egreso aplicada a LLM y buscadores")
    parser.add_argument("--encrypt-state", action="store_true",
                        help="cifra el checkpoint; exige THINKER_STATE_KEY")
    parser.add_argument("--adaptive", action="store_true",
                        help="routing de cómputo/modelos por dificultad heurística declarada")
    parser.add_argument("--prune-context", action="store_true",
                        help="poda RAG por relevancia y presupuesto de contexto")
    parser.add_argument("--context-passages", type=_entero_positivo, default=6)
    parser.add_argument("--context-chars", type=_entero_positivo, default=2400)
    parser.add_argument("--cache", action="store_true", help="caché exacta de prompts")
    parser.add_argument("--cache-bits", type=int, choices=(4, 8), default=8)
    parser.add_argument("--semantic-cache-threshold", type=float,
                        help="activa caché semántica léxica con este umbral 0..1")
    parser.add_argument("--speculative", action="store_true",
                        help="draft-verificación; no decodificación especulativa por tokens")
    parser.add_argument("--draft-model", help="modelo rápido para draft-verificación")
    return parser


def _ollama_llm(args, model):
    """Crea el proveedor Ollama en modo nativo o compatible OpenAI.

    El proxy local (11435) solo implementa el endpoint compatible OpenAI para
    chat; el modo nativo se usa con Ollama directo (11434).
    """
    base_url = getattr(args, "ollama_base_url", None) or "http://localhost:11434"
    model = model or "qwen3:1.7b"
    if getattr(args, "ollama_api", "native") == "openai":
        base = base_url.rstrip("/")
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        return OpenAILLM(api_key="ollama", base_url=base, model=model,
                         max_retries=1, timeout=180.0)
    return OllamaLLM(base_url=base_url, model=model)


def _base_llm(args, model):
    if args.provider == "mock":
        return MockLLM(model=model or "mock-llm")
    if args.provider == "openrouter":
        return OpenRouterLLM(model=model)
    if args.provider == "kilo":
        return KiloGatewayLLM(model=model)
    if args.provider == "forthtrade":
        from llm_providers import ForthtradeGatewayLLM
        return ForthtradeGatewayLLM(model=model)
    if args.provider == "deepseek-free-agent":
        return DeepSeekFreeAgentLLM(
            base_url=args.deepseek_agent_url,
            model=model or "deepseek-free-agent",
            timeout=args.deepseek_agent_timeout,
            authorized=args.authorize_deepseek_agent,
        )
    return _ollama_llm(args, model)


def build_llm(args):
    from efficiency import CachedLLM, SemanticResponseCache, SpeculativeLLM
    llm = _base_llm(args, args.model)
    fallback = getattr(args, "fallback_model", None)
    if fallback:
        if args.provider == "mock":
            raise ValueError("--fallback-model no aplica a --provider mock")
        if args.provider == "deepseek-free-agent":
            # La regla 17 exige elevar el fallo del servicio gratuito; no se
            # enmascara con un modelo local.
            raise ValueError("--fallback-model no aplica a --provider "
                             "deepseek-free-agent: un fallo se eleva")
        llm = LocalFallbackLLM(llm, _ollama_llm(args, fallback))
    if args.speculative:
        llm = SpeculativeLLM(_base_llm(args, args.draft_model or args.model), llm)
    if args.cache:
        llm = CachedLLM(
            llm, SemanticResponseCache(bits=args.cache_bits),
            semantic_threshold=args.semantic_cache_threshold)
    return BudgetLLM(llm, args.max_llm_calls) if args.max_llm_calls else llm


def build_search(args):
    seleccionado = args.search
    if seleccionado is None:
        seleccionado = "local" if args.documents else (
            "mock" if args.provider == "mock" else "wikipedia")
    if seleccionado == "local" and not args.documents:
        raise ValueError("--search=local exige al menos un --documents RUTA")
    if args.full_text and seleccionado == "mock":
        raise ValueError("--full-text no puede usar fuentes ficticias de --search=mock")
    if args.full_text and seleccionado == "local":
        raise ValueError("--full-text no aplica a documentos locales")
    if seleccionado == "mcp" and not args.mcp_command:
        raise ValueError("--search=mcp exige --mcp-command")

    providers = []
    if args.documents:
        providers.append(LocalDocumentSearchAPI(args.documents))
    if seleccionado == "mock":
        providers.append(MockSearchAPI())
    elif seleccionado == "wikipedia":
        providers.append(WikipediaSearchAPI())
    elif seleccionado == "duckduckgo":
        providers.append(DuckDuckGoSearchAPI())
    elif seleccionado == "searxng":
        url = args.searxng_url or os.environ.get("SEARXNG_URL")
        if not url:
            raise ValueError("Define SEARXNG_URL o --searxng-url")
        providers.append(SearXNGSearchAPI(
            url, allow_private=args.allow_private_search))
    elif seleccionado == "arxiv":
        providers.append(ArxivSearchAPI())
    elif seleccionado == "pubmed":
        providers.append(PubMedSearchAPI())
    elif seleccionado == "semantic_scholar":
        providers.append(SemanticScholarSearchAPI())
    elif seleccionado == "mcp":
        comando = shlex.split(args.mcp_command, posix=os.name != "nt")
        if not comando:
            raise ValueError("--mcp-command no puede estar vacío")
        providers.append(MCPSearchAPI(
            comando, tool=args.mcp_tool, timeout=args.mcp_timeout))
    if args.full_text:
        providers[-1] = FullTextSearchAPI(providers[-1])
    return providers[0] if len(providers) == 1 else CompositeSearchAPI(providers)


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.question:
        from deep_research_system import main as demo
        demo()
        return 0
    try:
        llm = build_llm(args)
        search = build_search(args)
        from privacy import PrivacyPolicy
        llm, search = PrivacyPolicy(args.privacy).apply(llm, search)
        if args.provider == "mock":
            print("*** LLM SIMULADO — el informe no constituye investigación real ***",
                  file=sys.stderr)
        print(f"Configuración: provider={args.provider} search={type(search).__name__}",
              file=sys.stderr)
        from efficiency import ContextPruner
        pruner = ContextPruner(
            max_passages=args.context_passages,
            max_chars=args.context_chars) if args.prune_context else None
        if args.adaptive:
            opciones = {
                "evaluador_relevancia": args.evaluador_relevancia,
                "informe_coarse_to_fine": args.coarse_to_fine,
                "max_workers": args.max_workers,
                "state_path": args.state,
                "encrypt_state": args.encrypt_state,
                "context_pruner": pruner,
            }
            if args.ncm_residual:
                opciones["informe_ncm_residual"] = True
            if args.verificacion_independiente:
                opciones["verificacion_independiente"] = True
            if args.muestras_consenso > 1:
                opciones["muestras_consenso"] = args.muestras_consenso
            orchestrator = ResearchOrchestrator.adaptive(
                args.question, llm, search, llm_profundo=llm, **opciones)
            plan = orchestrator.adaptive_plan
            print(f"Plan adaptativo: {plan.level} score={plan.score:.2f} "
                  f"motivos={plan.reasons}", file=sys.stderr)
        else:
            orchestrator = ResearchOrchestrator(
                llm, search,
                max_iterations=args.max_iterations,
                verificacion_independiente=args.verificacion_independiente,
                muestras_consenso=args.muestras_consenso,
                evaluador_relevancia=args.evaluador_relevancia,
                informe_coarse_to_fine=args.coarse_to_fine,
                informe_ncm_residual=args.ncm_residual,
                max_workers=args.max_workers,
                state_path=args.state,
                encrypt_state=args.encrypt_state,
                context_pruner=pruner,
            )
        report, context = orchestrator.research(args.question)
        formato = "json" if args.json else args.format
        if formato == "json":
            contenido = json.dumps(
                context_to_state(context, report, completed=True),
                ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        else:
            contenido = report if report.endswith("\n") else report + "\n"
        if args.output == "-":
            print(contenido, end="")
        else:
            destino = Path(args.output).expanduser()
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(contenido, encoding="utf-8")
            print(f"Informe escrito: {destino}", file=sys.stderr)
        resumen = context.to_dict()
        print(
            f"Completado: {resumen['duration_seconds']}s | fuentes={resumen['num_sources']} "
            f"claims={resumen['num_claims']} evaluaciones={resumen['num_evaluations']} "
            f"decisiones={resumen['decisions']}", file=sys.stderr)
        return 0
    except Exception as exc:
        print(f"ERROR {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
