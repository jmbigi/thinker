"""Tests offline de deep_research_system.py.

Sin red ni API keys: `openai.OpenAI` y `requests` se mockean; los LLM de
apoyo son dobles SIMULADOS (ver tests/helpers.py).
"""

import contextlib
import io
import json
import os
import unittest
from unittest.mock import patch

import deep_research_system as drs
from deep_research_system import (DEFAULT_FREE_MODEL, ClaimExtractor,
                                  DecisionEngine, EvidenceEvaluator,
                                  KiloGatewayLLM, LLMProvider, MockLLM,
                                  OllamaLLM, OpenAILLM, OpenRouterLLM,
                                  QuestionDecomposer, ReportGenerator,
                                  ResearchContext, ResearchOrchestrator,
                                  SourceRetriever, _chat_completion,
                                  _parse_json_response)
from tests.helpers import (FakeAPIError, StubLLM, StubSearch,
                           make_chat_client, ok_chat_response)
from web_search import MockSearchAPI


class TestParseJsonResponse(unittest.TestCase):
    def test_json_limpio_objeto_y_array(self):
        self.assertEqual(_parse_json_response('{"a": 1}'), {"a": 1})
        self.assertEqual(_parse_json_response('[1, 2, 3]'), [1, 2, 3])

    def test_json_en_bloque_markdown(self):
        self.assertEqual(
            _parse_json_response('```json\n{"a": 1}\n```'), {"a": 1}
        )
        self.assertEqual(_parse_json_response('```\n{"a": 1}\n```'), {"a": 1})

    def test_json_rodeado_de_prosa(self):
        texto = 'Claro, aquí está: {"a": 1, "b": [2]} Espero que sirva.'
        self.assertEqual(_parse_json_response(texto), {"a": 1, "b": [2]})

    def test_texto_sin_json_eleva_decode_error(self):
        with self.assertRaises(json.JSONDecodeError):
            _parse_json_response("esto no contiene JSON en absoluto")

    def test_llaves_sin_json_valido_eleva_decode_error(self):
        with self.assertRaises(json.JSONDecodeError):
            _parse_json_response("{esto parece json pero no lo es}")


class TestChatCompletion(unittest.TestCase):
    def test_reintenta_error_502_y_luego_devuelve(self):
        client = make_chat_client([
            FakeAPIError("Bad Gateway", status_code=502),
            ok_chat_response("contenido final"),
        ])
        stderr = io.StringIO()
        with patch("deep_research_system.time.sleep") as mock_sleep, \
                contextlib.redirect_stderr(stderr):
            result = _chat_completion(client, "modelo-x", "hola", 3, "TestLLM")
        self.assertEqual(result, "contenido final")
        self.assertEqual(len(client.calls), 2)
        mock_sleep.assert_called_once()
        self.assertIn("reintento", stderr.getvalue())
        self.assertEqual(client.calls[0]["model"], "modelo-x")
        self.assertEqual(
            client.calls[0]["messages"], [{"role": "user", "content": "hola"}]
        )

    def test_agota_reintentos_y_eleva_el_ultimo_error(self):
        client = make_chat_client([
            FakeAPIError("Bad Gateway", status_code=502),
            FakeAPIError("Bad Gateway", status_code=502),
            FakeAPIError("Bad Gateway", status_code=502),
        ])
        stderr = io.StringIO()
        with patch("deep_research_system.time.sleep") as mock_sleep, \
                contextlib.redirect_stderr(stderr):
            with self.assertRaises(FakeAPIError):
                _chat_completion(client, "m", "p", 3, "TestLLM")
        self.assertEqual(len(client.calls), 3)
        self.assertEqual(mock_sleep.call_count, 2)

    def test_error_401_no_reintenta(self):
        client = make_chat_client([
            FakeAPIError("Unauthorized", status_code=401),
            ok_chat_response("nunca se alcanza"),
        ])
        with patch("deep_research_system.time.sleep") as mock_sleep:
            with self.assertRaises(FakeAPIError):
                _chat_completion(client, "m", "p", 3, "TestLLM")
        self.assertEqual(len(client.calls), 1)
        mock_sleep.assert_not_called()

    def test_error_de_red_sin_status_reintenta(self):
        client = make_chat_client([
            ConnectionError("sin conexión"),
            ok_chat_response("tras la caída"),
        ])
        with patch("deep_research_system.time.sleep"), \
                contextlib.redirect_stderr(io.StringIO()):
            result = _chat_completion(client, "m", "p", 3, "TestLLM")
        self.assertEqual(result, "tras la caída")
        self.assertEqual(len(client.calls), 2)

    def test_contenido_none_devuelve_cadena_vacia(self):
        client = make_chat_client([ok_chat_response(None)])
        result = _chat_completion(client, "m", "p", 1, "TestLLM")
        self.assertEqual(result, "")


class TestLLMProviders(unittest.TestCase):
    def test_llm_provider_es_abstracto(self):
        with self.assertRaises(TypeError):
            LLMProvider()

    def test_openai_sin_key_eleva_value_error(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            llm = OpenAILLM(api_key="")
            with self.assertRaises(ValueError) as cm:
                llm.generate("hola")
        self.assertIn("API key required", str(cm.exception))

    def test_openai_generate_con_cliente_mockeado(self):
        client = make_chat_client([ok_chat_response("respuesta openai")])
        with patch("openai.OpenAI", return_value=client) as mock_openai:
            llm = OpenAILLM(api_key="clave-ficticia-de-test", model="modelo-test")
            result = llm.generate("prompt de prueba")
        self.assertEqual(result, "respuesta openai")
        mock_openai.assert_called_once_with(
            api_key="clave-ficticia-de-test", base_url=None
        )
        self.assertEqual(client.calls[0]["model"], "modelo-test")

    def test_openai_kwargs_sobreescriben_key_y_base_url(self):
        client = make_chat_client([ok_chat_response("ok")])
        with patch("openai.OpenAI", return_value=client) as mock_openai:
            llm = OpenAILLM(api_key="clave-ficticia-de-test")
            llm.generate("p", api_key="otra-clave-ficticia",
                         base_url="https://ejemplo.invalid/v1")
        mock_openai.assert_called_once_with(
            api_key="otra-clave-ficticia", base_url="https://ejemplo.invalid/v1"
        )

    def test_openrouter_usa_modelo_gratuito_por_defecto(self):
        env = {k: v for k, v in os.environ.items() if k != "OPENROUTER_MODEL"}
        with patch.dict(os.environ, env, clear=True):
            llm = OpenRouterLLM(api_key="clave-ficticia-de-test")
        self.assertEqual(llm.model, DEFAULT_FREE_MODEL)
        self.assertTrue(llm.model.endswith(":free"))
        self.assertEqual(llm.base_url, "https://openrouter.ai/api/v1")

    def test_modelo_por_defecto_es_gratuito_y_esta_en_la_cadena(self):
        """Coherencia entre el defecto y la cadena de fallback (Hallazgo 42)."""
        from llm_providers import OPENROUTER_FALLBACK_CHAIN

        self.assertTrue(DEFAULT_FREE_MODEL.endswith(":free"))
        self.assertIn(DEFAULT_FREE_MODEL, OPENROUTER_FALLBACK_CHAIN)
        self.assertEqual(OPENROUTER_FALLBACK_CHAIN[0], DEFAULT_FREE_MODEL)

    def test_openrouter_modelo_sobreescribible_por_entorno(self):
        with patch.dict(os.environ, {"OPENROUTER_MODEL": "proveedor/modelo-x:free"}):
            llm = OpenRouterLLM(api_key="clave-ficticia-de-test")
        self.assertEqual(llm.model, "proveedor/modelo-x:free")

    def test_openrouter_key_desde_entorno(self):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "clave-ficticia-de-test"}):
            llm = OpenRouterLLM()
        self.assertEqual(llm.api_key, "clave-ficticia-de-test")

    def test_openrouter_fallback_salta_modelo_con_error_no_transitorio(self):
        from llm_providers import OPENROUTER_FALLBACK_CHAIN

        client = make_chat_client([
            FakeAPIError("modelo caído", status_code=404),
            ok_chat_response("respuesta del segundo modelo"),
        ])
        with patch("openai.OpenAI", return_value=client):
            llm = OpenRouterLLM(api_key="clave-ficticia-de-test", model="modelo-a:free")
            salida = llm.generate("p")

        self.assertEqual(salida, "respuesta del segundo modelo")
        self.assertEqual([c["model"] for c in client.calls],
                         ["modelo-a:free", OPENROUTER_FALLBACK_CHAIN[0]])

    def test_openrouter_429_agota_reintentos_y_salta_de_modelo(self):
        client = make_chat_client(
            [FakeAPIError("rate limit", status_code=429)] * 3
            + [ok_chat_response("respuesta del siguiente modelo")]
        )
        with patch("openai.OpenAI", return_value=client), \
                patch("deep_research_system.time.sleep"):
            llm = OpenRouterLLM(api_key="clave-ficticia-de-test", model="modelo-a:free")
            salida = llm.generate("p")

        self.assertEqual(salida, "respuesta del siguiente modelo")
        self.assertEqual(len(client.calls), 4)  # 3 reintentos + 1 modelo nuevo

    def test_openrouter_fallback_agotado_eleva_el_ultimo_error(self):
        from llm_providers import OPENROUTER_FALLBACK_CHAIN

        intentos = len(OPENROUTER_FALLBACK_CHAIN)
        client = make_chat_client([FakeAPIError("no", status_code=404)] * intentos)
        with patch("openai.OpenAI", return_value=client):
            llm = OpenRouterLLM(api_key="clave-ficticia-de-test")
            with self.assertRaises(FakeAPIError):
                llm.generate("p")

        self.assertEqual(len(client.calls), intentos)

    def test_openrouter_sin_fallback_usa_solo_el_modelo_configurado(self):
        client = make_chat_client([FakeAPIError("no", status_code=404)])
        with patch("openai.OpenAI", return_value=client):
            llm = OpenRouterLLM(api_key="clave-ficticia-de-test", use_fallback=False)
            with self.assertRaises(FakeAPIError):
                llm.generate("p")

        self.assertEqual(len(client.calls), 1)

    def test_openrouter_modelo_explicito_no_usa_fallback(self):
        client = make_chat_client([ok_chat_response("ok")])
        with patch("openai.OpenAI", return_value=client):
            llm = OpenRouterLLM(api_key="clave-ficticia-de-test")
            llm.generate("p", model="otro/modelo:free")

        self.assertEqual([c["model"] for c in client.calls], ["otro/modelo:free"])

    def test_kilo_sin_key_eleva_value_error(self):
        with patch.dict(os.environ, {"KILO_API_KEY": ""}):
            llm = KiloGatewayLLM(api_key="")
            with self.assertRaises(ValueError) as cm:
                llm.generate("hola")
        self.assertIn("Kilo API key required", str(cm.exception))

    def test_kilo_generate_con_cliente_mockeado(self):
        client = make_chat_client([ok_chat_response("respuesta kilo")])
        with patch("openai.OpenAI", return_value=client) as mock_openai:
            llm = KiloGatewayLLM(api_key="clave-ficticia-de-test")
            result = llm.generate("prompt kilo")
        self.assertEqual(result, "respuesta kilo")
        mock_openai.assert_called_once_with(
            api_key="clave-ficticia-de-test",
            base_url="https://api.kilo.ai/api/gateway",
        )
        self.assertEqual(client.calls[0]["model"], "anthropic/claude-sonnet-4")

    def test_ollama_generate_con_requests_mockeado(self):
        resp = type("R", (), {})()
        resp.raise_for_status = lambda: None
        resp.json = lambda: {"response": "texto ollama"}
        with patch("requests.post", return_value=resp) as mock_post:
            llm = OllamaLLM()
            result = llm.generate("prompt ollama")
        self.assertEqual(result, "texto ollama")
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "http://localhost:11434/api/generate")
        self.assertEqual(kwargs["json"]["model"], "llama3.2")
        self.assertFalse(kwargs["json"]["stream"])

    def test_ollama_error_http_se_propaga(self):
        import requests as real_requests

        resp = type("R", (), {})()
        def boom():
            raise real_requests.HTTPError("500")
        resp.raise_for_status = boom
        resp.json = lambda: {}
        with patch("requests.post", return_value=resp):
            with self.assertRaises(real_requests.HTTPError):
                OllamaLLM().generate("p")


class TestMockLLM(unittest.TestCase):
    def test_rama_descomposicion(self):
        out = MockLLM().generate("Decompose this into 3-5 specific sub-questions")
        lineas = [line for line in out.split("\n") if line.strip()]
        self.assertEqual(len(lineas), 3)

    def test_rama_extraccion_claims_devuelve_json_array(self):
        out = MockLLM().generate("Extract factual claims from this text snippet")
        claims = json.loads(out)
        self.assertIsInstance(claims, list)
        self.assertIn("claim", claims[0])

    def test_rama_evaluacion_devuelve_json_objeto(self):
        out = MockLLM().generate("Evaluate this claim against the sources")
        evaluation = json.loads(out)
        self.assertEqual(evaluation["verdict"], "supported")

    def test_rama_informe_declara_simulacion(self):
        out = MockLLM().generate("Generate a comprehensive research report")
        self.assertIn("SIMULADO", out)

    def test_rama_paso_n(self):
        out = MockLLM().generate("PASO 3 - ESTRATEGIA: ...")
        data = json.loads(out)
        self.assertEqual(data["paso"], 3)

    def test_rama_fallback(self):
        out = MockLLM().generate("prompt sin patrón conocido")
        self.assertIn("simulada", out.lower())


class TestResearchContext(unittest.TestCase):
    def test_add_decision_y_to_dict(self):
        ctx = ResearchContext("pregunta", max_iterations=2)
        ctx.add_decision("paso", "decidir", "porque sí")
        self.assertEqual(len(ctx.decision_log), 1)
        entrada = ctx.decision_log[0]
        self.assertEqual(entrada["step"], "paso")
        self.assertEqual(entrada["decision"], "decidir")
        self.assertEqual(entrada["iteration"], 0)
        resumen = ctx.to_dict()
        self.assertEqual(resumen["question"], "pregunta")
        self.assertEqual(resumen["decisions"], 1)
        self.assertEqual(resumen["num_claims"], 0)


class TestDecisionEngines(unittest.TestCase):
    def test_decision_engine_es_abstracto(self):
        with self.assertRaises(TypeError):
            DecisionEngine()

    def test_decomposer_limpia_numeracion_y_vinetas(self):
        llm = StubLLM(lambda p: "1. Primera pregunta\n- Segunda pregunta\n"
                                "• Tercera pregunta\n2) Cuarta pregunta\n\n")
        ctx = ResearchContext("q")
        subs = QuestionDecomposer(llm).decide(ctx)
        self.assertEqual(subs, ["Primera pregunta", "Segunda pregunta",
                                "Tercera pregunta", "Cuarta pregunta"])
        self.assertEqual(ctx.decision_log[0]["step"], "question_decomposition")

    def test_decomposer_recorta_a_cinco(self):
        llm = StubLLM(lambda p: "\n".join(f"Pregunta {i}" for i in range(7)))
        subs = QuestionDecomposer(llm).decide(ResearchContext("q"))
        self.assertEqual(len(subs), 5)

    def test_decomposer_no_recalcula_si_ya_descompuso(self):
        # El contrato ya no depende del contador de iteraciones (vestigial):
        # ahora lo indica el flag explícito `decomposed`.
        llm = StubLLM(lambda p: "única")
        ctx = ResearchContext("q")
        ctx.iteration = 3
        ctx.decomposed = True
        ctx.subquestions = ["ya calculada"]
        subs = QuestionDecomposer(llm).decide(ctx)
        self.assertEqual(subs, ["ya calculada"])
        self.assertEqual(llm.prompts, [])

    def test_decomposer_marca_el_contexto_como_descompuesto(self):
        llm = StubLLM(lambda p: "una pregunta")
        ctx = ResearchContext("q")
        self.assertFalse(ctx.decomposed)
        QuestionDecomposer(llm).decide(ctx)
        self.assertTrue(ctx.decomposed)
        self.assertTrue(ctx.to_dict()["decomposed"])

    def test_retriever_agrega_fuentes_y_una_decision(self):
        search = StubSearch([
            {"title": "T1", "url": "u1", "snippet": "s1", "source": "mock"},
            {"title": "T2", "url": "u2"},
        ])
        ctx = ResearchContext("q")
        results = SourceRetriever(search).decide(ctx, "subpregunta")
        self.assertEqual(len(results), 2)
        self.assertEqual(ctx.iteration, 1)
        self.assertEqual(len(ctx.sources), 2)
        self.assertEqual(ctx.sources[0]["related_to"], "subpregunta")
        self.assertEqual(ctx.sources[0]["query_used"], "subpregunta")
        self.assertEqual(ctx.sources[1]["snippet"], "")
        # una decisión "retrieve" por llamada, con el recuento de fuentes
        self.assertEqual(len(ctx.decision_log), 1)
        self.assertEqual(ctx.decision_log[0]["decision"], "retrieve")
        self.assertIn("2 fuentes nuevas", ctx.decision_log[0]["rationale"])

    def test_retriever_amplia_consulta_si_no_hay_resultados(self):
        class EmptyThenResultsSearch:
            def __init__(self):
                self.queries = []

            def search(self, query, max_results=5):
                self.queries.append(query)
                if len(self.queries) == 1:
                    return []
                return [{"title": "T", "url": "u", "snippet": "s",
                         "source": "stub"}]

        search = EmptyThenResultsSearch()
        ctx = ResearchContext("fusión nuclear")
        SourceRetriever(search).decide(ctx, "¿Cuál es el estado actual?")
        # consultas candidatas ancladas al tema: la primera (formulada) queda
        # vacía → requery; la segunda (solo anclas) devuelve resultados
        self.assertEqual(search.queries[0], "fusión nuclear estado")
        self.assertEqual(search.queries[1], "fusión nuclear")
        decisions = [d["decision"] for d in ctx.decision_log]
        self.assertEqual(decisions, ["requery", "retrieve"])
        self.assertEqual(ctx.sources[0]["query_used"], "fusión nuclear")

    def test_retriever_deduplica_urls_ya_conocidas(self):
        search = StubSearch([
            {"title": "T1", "url": "u1", "snippet": "s1", "source": "mock"},
            {"title": "T2", "url": "u2", "snippet": "s2", "source": "mock"},
        ])
        ctx = ResearchContext("q")
        ctx.sources.append({"url": "u1"})
        SourceRetriever(search).decide(ctx, "subpregunta")
        urls = [s["url"] for s in ctx.sources]
        self.assertEqual(urls, ["u1", "u2"])
        self.assertIn("1 fuentes nuevas", ctx.decision_log[0]["rationale"])

    def test_extractor_exito_agrega_source_id(self):
        llm = StubLLM(lambda p: '[{"claim": "c1", "confidence": 0.5, '
                                '"source_url": "u"}]')
        ctx = ResearchContext("q")
        claims = ClaimExtractor(llm).decide(ctx, {"url": "u1", "snippet": "s"})
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0]["source_id"], "u1")
        self.assertIn("extracted_at", claims[0])
        self.assertEqual(ctx.decision_log[0]["decision"], "extract")

    def test_extractor_json_no_array_falla_y_registra(self):
        llm = StubLLM(lambda p: '{"claim": "no es un array"}')
        ctx = ResearchContext("q")
        claims = ClaimExtractor(llm).decide(ctx, {"url": "u1", "snippet": "s"})
        self.assertEqual(claims, [])
        self.assertEqual(ctx.claims, [])
        self.assertEqual(ctx.decision_log[0]["decision"], "fail")

    def test_extractor_texto_no_json_falla_sin_reventar(self):
        llm = StubLLM(lambda p: "texto libre sin json")
        ctx = ResearchContext("q")
        self.assertEqual(ClaimExtractor(llm).decide(ctx, {"url": "u"}), [])
        self.assertEqual(ctx.decision_log[0]["decision"], "fail")

    def test_extractor_array_con_elementos_no_dict_falla(self):
        llm = StubLLM(lambda p: '["solo texto", 42]')
        ctx = ResearchContext("q")
        self.assertEqual(ClaimExtractor(llm).decide(ctx, {"url": "u"}), [])
        self.assertEqual(ctx.decision_log[0]["decision"], "fail")

    def test_evaluator_exito(self):
        llm = StubLLM(lambda p: '{"verdict": "supported", "credibility": 0.9, '
                                '"confidence": 0.8, "reasoning": "ok"}')
        ctx = ResearchContext("q")
        ctx.sources.append({"url": "u1", "title": "T", "snippet": "s"})
        ev = EvidenceEvaluator(llm).decide(
            ctx, {"claim": "algo", "source_url": "u1"})
        self.assertEqual(ev["verdict"], "supported")
        self.assertEqual(ev["claim"], "algo")
        self.assertEqual(ctx.evaluations[0]["credibility"], 0.9)
        self.assertIn("0.90", ctx.decision_log[0]["rationale"])

    def test_evaluator_respuesta_invalida_devuelve_not_addressed(self):
        llm = StubLLM(lambda p: "no json")
        ctx = ResearchContext("q")
        ev = EvidenceEvaluator(llm).decide(
            ctx, {"claim": "algo", "source_url": "u1"})
        self.assertEqual(ev["verdict"], "not_addressed")
        self.assertEqual(ev["credibility"], 0.0)
        self.assertEqual(len(ctx.evaluations), 1)

    def test_report_generator_extrae_conclusiones(self):
        llm = StubLLM(lambda p: "# Título\n\n## Sección A\n\ntexto\n\n"
                                "## Sección B\n\nmás\n\n## Sección C\n\nfin\n")
        ctx = ResearchContext("q")
        ctx.claims.append({"claim": "c1", "source_url": "u"})
        ctx.evaluations.append({"claim": "c1", "verdict": "supported"})
        ctx.evaluations.append({"claim": "c2", "verdict": "contradicted"})
        report = ReportGenerator(llm).decide(ctx)
        self.assertTrue(report.startswith("# Título"))
        self.assertEqual(len(ctx.conclusions), 3)
        self.assertEqual(ctx.decision_log[0]["step"], "report_generation")

    def test_report_generator_informe_sin_secciones(self):
        llm = StubLLM(lambda p: "informe plano sin encabezados")
        ctx = ResearchContext("q")
        ReportGenerator(llm).decide(ctx)
        self.assertEqual(len(ctx.conclusions), 1)


class TestResearchOrchestrator(unittest.TestCase):
    def test_pipeline_completo_con_mocks(self):
        orchestrator = ResearchOrchestrator(MockLLM(), MockSearchAPI(),
                                            max_iterations=3)
        report, ctx = orchestrator.research("¿Estado de la fusión nuclear?")
        self.assertIn("SIMULADO", report)
        self.assertEqual(len(ctx.subquestions), 3)
        self.assertEqual(len(ctx.claims), 3)
        self.assertTrue(
            all(e["verdict"] == "supported" for e in ctx.evaluations)
        )
        resumen = ctx.to_dict()
        self.assertEqual(resumen["num_claims"], 3)
        self.assertGreater(resumen["decisions"], 0)

    def test_max_iterations_limita_las_subpreguntas_procesadas(self):
        """El parámetro limita de verdad (antes era decorativo)."""
        orchestrator = ResearchOrchestrator(MockLLM(), MockSearchAPI(),
                                            max_iterations=2)
        _, ctx = orchestrator.research("¿Estado de la fusión nuclear?")

        # MockLLM descompone en 3 subpreguntas: solo se procesan 2
        self.assertEqual(len(ctx.subquestions), 2)
        self.assertEqual(ctx.iteration, 2)
        recortes = [d for d in ctx.decision_log if d["step"] == "iteration_limit"]
        self.assertEqual(len(recortes), 1)
        self.assertEqual(recortes[0]["decision"], "truncate")

    def test_max_iterations_suficiente_no_recorta(self):
        orchestrator = ResearchOrchestrator(MockLLM(), MockSearchAPI(),
                                            max_iterations=5)
        _, ctx = orchestrator.research("¿Estado de la fusión nuclear?")

        self.assertEqual(len(ctx.subquestions), 3)
        recortes = [d for d in ctx.decision_log if d["step"] == "iteration_limit"]
        self.assertEqual(recortes, [])

    def test_pregunta_no_descomponible(self):
        orchestrator = ResearchOrchestrator(StubLLM(lambda p: ""),
                                            MockSearchAPI())
        report, ctx = orchestrator.research("pregunta")
        self.assertEqual(report, "Could not decompose research question")
        self.assertEqual(ctx.subquestions, [])

    def test_llm_no_json_no_revienta_y_registra_fail(self):
        def responder(prompt):
            if "decompose this into" in prompt.lower():
                return "sub pregunta uno\nsub pregunta dos"
            return "texto libre que no es JSON"

        orchestrator = ResearchOrchestrator(StubLLM(responder), MockSearchAPI())
        report, ctx = orchestrator.research("pregunta de prueba")
        self.assertEqual(report, "texto libre que no es JSON")
        self.assertEqual(ctx.claims, [])
        fails = [d for d in ctx.decision_log if d["decision"] == "fail"]
        self.assertTrue(fails)
        self.assertTrue(all(d["step"] == "claim_extraction" for d in fails))


class TestMain(unittest.TestCase):
    def test_main_offline_completa(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            drs.main()
        salida = buffer.getvalue()
        self.assertIn("RESEARCH CONTEXT SUMMARY", salida)
        self.assertIn("SIMULADO", salida)
        self.assertIn("End of Research Session", salida)


if __name__ == "__main__":
    unittest.main()
