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
from llm_providers import DeepSeekLLM
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

    def test_varios_bloques_devuelve_el_primer_json_decodificable(self):
        texto = 'Primero {no json} y después [1, {"a": 2}] final'
        self.assertEqual(_parse_json_response(texto), [1, {"a": 2}])


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

    def test_openrouter_no_hereda_la_clave_de_openai(self):
        """Regresión de seguridad: sin clave propia NO debe usar OPENAI_API_KEY."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "",
                                     "OPENAI_API_KEY": "clave-de-openai-ficticia"}):
            llm = OpenRouterLLM()
        self.assertEqual(llm.api_key, "")

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

    def test_openrouter_recuerda_el_modelo_que_funciona(self):
        from llm_providers import OPENROUTER_FALLBACK_CHAIN

        client = make_chat_client([
            FakeAPIError("modelo caído", status_code=404),
            ok_chat_response("ok en el segundo"),
            ok_chat_response("ok directo"),
        ])
        with patch("openai.OpenAI", return_value=client):
            llm = OpenRouterLLM(api_key="clave-ficticia-de-test", model="modelo-a:free")
            llm.generate("p1")
            llm.generate("p2")

        self.assertEqual(llm.model, OPENROUTER_FALLBACK_CHAIN[0])
        self.assertEqual([c["model"] for c in client.calls],
                         ["modelo-a:free", OPENROUTER_FALLBACK_CHAIN[0],
                          OPENROUTER_FALLBACK_CHAIN[0]])

    def test_openrouter_error_de_red_sin_status_no_hace_fallback(self):
        client = make_chat_client(
            [FakeAPIError("caída de red sin status")] * 3)
        with patch("openai.OpenAI", return_value=client), \
                patch("deep_research_system.time.sleep"):
            llm = OpenRouterLLM(api_key="clave-ficticia-de-test")
            with self.assertRaises(FakeAPIError):
                llm.generate("p")

        # Se reintenta el mismo modelo y se eleva; NO se prueba el siguiente
        # (un fallo de red no justifica cambiar de modelo).
        self.assertEqual(len(client.calls), 3)
        self.assertEqual({c["model"] for c in client.calls}, {llm.model})

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

    def test_kilo_cache_y_timeout_como_las_rutas_openai(self):
        client = make_chat_client([ok_chat_response("respuesta kilo")])
        with patch("openai.OpenAI", return_value=client):
            llm = KiloGatewayLLM(api_key="clave-ficticia-de-test")
            llm.generate("mismo prompt")
            llm.generate("mismo prompt")

        self.assertEqual(len(client.calls), 1)
        self.assertEqual(llm.cache.hits, 1)
        self.assertEqual(client.calls[0]["timeout"], 60.0)

    def test_kilo_sin_cache_hace_dos_llamadas(self):
        client = make_chat_client([ok_chat_response("uno"), ok_chat_response("dos")])
        with patch("openai.OpenAI", return_value=client):
            llm = KiloGatewayLLM(api_key="clave-ficticia-de-test", use_cache=False)
            llm.generate("mismo prompt")
            llm.generate("mismo prompt")

        self.assertEqual(len(client.calls), 2)
        self.assertIsNone(llm.cache)

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


class TestDeepSeekLLM(unittest.TestCase):
    """`DeepSeekLLM`: su constructor no tenía ningún test (21 mutantes sin ejecutar).

    Ningún assert usa claves reales del entorno: se fijan valores ficticios o
    vacíos, para que un fallo NUNCA imprima una clave (P0.6).
    """

    SIN_CLAVES = {"DEEPSEEK_API_KEY": "", "OPENAI_API_KEY": ""}

    def test_valores_por_defecto(self):
        with patch.dict(os.environ, self.SIN_CLAVES):
            llm = DeepSeekLLM()

        self.assertEqual(llm.model, "deepseek-chat")
        self.assertEqual(llm.base_url, "https://api.deepseek.com/v1")
        self.assertEqual(llm.max_retries, 3)
        self.assertEqual(llm.api_key, "")

    def test_no_hereda_la_clave_de_openai(self):
        """Regresión de seguridad: sin clave propia NO debe usar OPENAI_API_KEY.

        `OpenAILLM.__init__` cae a OPENAI_API_KEY si la clave es vacía; en un
        cliente de otro proveedor eso enviaría la clave de OpenAI a un tercero.
        """
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "",
                                     "OPENAI_API_KEY": "clave-de-openai-ficticia"}):
            llm = DeepSeekLLM()

        self.assertEqual(llm.api_key, "")

    def test_key_desde_entorno(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "clave-ficticia-de-test"}):
            llm = DeepSeekLLM()

        self.assertEqual(llm.api_key, "clave-ficticia-de-test")

    def test_parametros_explicitos_ganan(self):
        llm = DeepSeekLLM(api_key="otra-clave-ficticia", model="deepseek-reasoner",
                          base_url="https://ejemplo.invalid/v1", max_retries=7)

        self.assertEqual(llm.api_key, "otra-clave-ficticia")
        self.assertEqual(llm.model, "deepseek-reasoner")
        self.assertEqual(llm.base_url, "https://ejemplo.invalid/v1")
        self.assertEqual(llm.max_retries, 7)

    def test_sin_key_eleva_value_error_al_generar(self):
        with patch.dict(os.environ, self.SIN_CLAVES):
            llm = DeepSeekLLM(api_key="")
            with self.assertRaises(ValueError):
                llm.generate("hola")


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

    def test_salidas_exactas_de_cada_rama(self):
        llm = MockLLM()
        self.assertEqual(
            llm.generate("Decompose this into parts"),
            "¿Cuáles son los avances recientes documentados sobre el tema?\n"
            "¿Qué fuentes primarias describen el estado actual?\n"
            "¿Qué limitaciones, riesgos e incertidumbres se reportan?")
        self.assertEqual(
            llm.generate("Extract factual claims now"),
            '[{"claim": "Afirmación simulada extraída del snippet por MockLLM", '
            '"confidence": 0.7, "source_url": "https://example.com/mock-source"}]')
        self.assertEqual(
            llm.generate("Evaluate this claim now"),
            '{"verdict": "supported", "credibility": 0.75, "confidence": 0.7, '
            '"reasoning": "Evaluación simulada por MockLLM (offline, sin modelo real)"}')
        self.assertEqual(
            llm.generate("Eres un evaluador experto de calidad"),
            '{"relevance": 8, "depth": 8, "coherence": 8, "reasoning": 8, '
            '"brief_justification": "Evaluación simulada por MockLLM (offline)"}')
        self.assertEqual(
            llm.generate("PASO 7 - X"),
            '{"paso": 7, "contenido": "Respuesta simulada por MockLLM para el '
            'paso 7", "confianza": 0.7, "nota": "Salida offline determinista, '
            'sin modelo real"}')
        self.assertEqual(
            llm.generate("Generate a comprehensive research report"),
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
            "para obtener contenido genuino.\n")
        self.assertEqual(
            llm.generate("otra cosa"),
            "Respuesta simulada por MockLLM (offline): el prompt no "
            "corresponde a un patrón conocido.")


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

    def test_evaluator_credibilidad_string_se_normaliza_sin_abortar(self):
        llm = StubLLM(lambda p: '{"verdict": "supported", "credibility": "0.75", '
                                '"confidence": 0.7, "reasoning": "ok"}')
        ctx = ResearchContext("q")

        ev = EvidenceEvaluator(llm).decide(ctx, {"claim": "algo", "source_url": "u"})

        self.assertEqual(ev["credibility"], 0.75)   # antes: ValueError y aborto
        self.assertEqual(len(ctx.evaluations), 1)
        self.assertEqual(len(ctx.decision_log), 1)
        self.assertIn("0.75", ctx.decision_log[0]["rationale"])

    def test_evaluator_credibilidad_null_no_duplica_la_evaluacion(self):
        llm = StubLLM(lambda p: '{"verdict": "supported", "credibility": null, '
                                '"confidence": 0.7, "reasoning": "ok"}')
        ctx = ResearchContext("q")

        ev = EvidenceEvaluator(llm).decide(ctx, {"claim": "algo", "source_url": "u"})

        self.assertEqual(ev["credibility"], 0.0)
        self.assertEqual(ev["credibility_raw"], "None")
        self.assertEqual(len(ctx.evaluations), 1)   # antes: 2 por el TypeError
        self.assertEqual(len(ctx.decision_log), 1)  # antes: 0

    def test_evaluator_credibilidad_se_acota_y_no_numerica_es_cero(self):
        casos = [("1.5", 1.0, None), ("-0.2", 0.0, None), ("alta", 0.0, "alta")]
        for bruta, esperada, raw in casos:
            with self.subTest(bruta=bruta):
                llm = StubLLM(lambda p, b=bruta: (
                    '{"verdict": "supported", "credibility": "%s", '
                    '"confidence": 0.5, "reasoning": "ok"}' % b))
                ctx = ResearchContext("q")

                ev = EvidenceEvaluator(llm).decide(ctx, {"claim": "c"})

                self.assertEqual(ev["credibility"], esperada)
                if raw is None:
                    self.assertNotIn("credibility_raw", ev)
                else:
                    self.assertEqual(ev["credibility_raw"], raw)

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


class TestMotoresConAsercionesExactas(unittest.TestCase):
    """Aserciones exactas sobre prompts, contadores y decisiones (matan mutantes).

    Los tests anteriores comprobaban el «camino feliz» en grande; estos fijan
    los valores concretos que los mutantes cambian sin que nadie lo note.
    """

    def _contexto_con_fuentes(self, n=2, snippet="snip"):
        ctx = ResearchContext("¿pregunta?")
        for i in range(n):
            ctx.sources.append({"url": f"u{i}", "title": f"T{i}",
                                "snippet": snippet})
        return ctx

    # --- EvidenceEvaluator -------------------------------------------------
    def test_evaluator_prompt_lleva_solo_las_fuentes_del_claim(self):
        llm = StubLLM(lambda p: '{"verdict": "supported", "credibility": 0.5, '
                                '"confidence": 0.5, "reasoning": "r"}')
        ctx = self._contexto_con_fuentes(3)

        EvidenceEvaluator(llm).decide(ctx, {"claim": "algo", "source_url": "u1"})

        prompt = llm.prompts[0]
        self.assertIn("Source 1: T1: snip", prompt)
        self.assertNotIn("T0", prompt)
        self.assertNotIn("T2", prompt)
        self.assertIn("Claim: algo", prompt)

    def test_evaluator_sin_fuente_propia_usa_las_tres_primeras(self):
        llm = StubLLM(lambda p: '{"verdict": "supported", "credibility": 0.5, '
                                '"confidence": 0.5, "reasoning": "r"}')
        ctx = self._contexto_con_fuentes(5)

        EvidenceEvaluator(llm).decide(ctx, {"claim": "algo", "source_url": "otra"})

        prompt = llm.prompts[0]
        self.assertIn("Source 3: T2: snip", prompt)
        self.assertNotIn("T3", prompt)

    def test_evaluator_trunca_el_snippet_a_200(self):
        llm = StubLLM(lambda p: '{"verdict": "supported", "credibility": 0.5, '
                                '"confidence": 0.5, "reasoning": "r"}')
        ctx = ResearchContext("q")
        ctx.sources.append({"url": "u0", "title": "T",
                            "snippet": "x" * 250})

        EvidenceEvaluator(llm).decide(ctx, {"claim": "c", "source_url": "u0"})

        self.assertIn("x" * 200 + "\n", llm.prompts[0])
        self.assertNotIn("x" * 201, llm.prompts[0])

    def test_evaluator_anota_claim_url_y_marca_tiempo(self):
        llm = StubLLM(lambda p: '{"verdict": "contradicted", "credibility": 0.25, '
                                '"confidence": 0.5, "reasoning": "r"}')
        ctx = self._contexto_con_fuentes(1)

        ev = EvidenceEvaluator(llm).decide(ctx, {"claim": "c1", "source_url": "u0"})

        self.assertEqual(ev["claim"], "c1")
        self.assertEqual(ev["source_url"], "u0")
        self.assertIsInstance(ev["evaluated_at"], float)
        self.assertIs(ctx.evaluations[0], ev)
        self.assertEqual(ctx.decision_log[0]["decision"], "evaluate")
        self.assertEqual(ctx.decision_log[0]["rationale"],
                         "Verdict: contradicted, Credibility: 0.25")

    def test_evaluator_sin_credibilidad_usa_cero(self):
        llm = StubLLM(lambda p: '{"verdict": "supported"}')
        ctx = self._contexto_con_fuentes(1)

        EvidenceEvaluator(llm).decide(ctx, {"claim": "c", "source_url": "u0"})

        self.assertEqual(ctx.decision_log[0]["rationale"],
                         "Verdict: supported, Credibility: 0.00")

    def test_evaluator_json_no_objeto_usa_el_fallo_exacto(self):
        llm = StubLLM(lambda p: "[1, 2, 3]")
        ctx = self._contexto_con_fuentes(1)

        ev = EvidenceEvaluator(llm).decide(ctx, {"claim": "c", "source_url": "u0"})

        self.assertEqual(ev, {
            "verdict": "not_addressed",
            "credibility": 0.0,
            "confidence": 0.0,
            "reasoning": "Failed to parse evaluation",
            "claim": "c",
            "source_url": "u0",
            "evaluated_at": ev["evaluated_at"],
        })
        self.assertIs(ctx.evaluations[0], ev)

    # --- SourceRetriever ---------------------------------------------------
    def test_retriever_prueba_las_candidatas_en_orden(self):
        search = StubSearch([])
        ctx = ResearchContext("¿pregunta?")
        retriever = SourceRetriever(search)

        retriever.decide(ctx, "subpregunta concreta")

        consultas = search.queries
        self.assertEqual(len(consultas), len(set(consultas)))
        self.assertEqual(consultas[-1], "subpregunta concreta")
        self.assertEqual(ctx.decision_log[-1]["decision"], "retrieve")
        self.assertEqual(ctx.decision_log[-1]["rationale"],
                         "0 fuentes nuevas para: subpregunta concreta")

    def test_retriever_registra_cada_reintento_y_el_agotamiento(self):
        search = StubSearch([])
        ctx = ResearchContext("¿pregunta?")
        retriever = SourceRetriever(search)

        retriever.decide(ctx, "subpregunta")

        decisiones = [d["decision"] for d in ctx.decision_log]
        # un requery por cada candidata con próxima oportunidad...
        self.assertEqual(decisiones.count("requery"), len(search.queries) - 1)
        # ...y un aviso honesto cuando ya no queda ninguna (no "se amplía")
        self.assertEqual(decisiones[-2], "no_results")
        self.assertEqual(decisiones[-1], "retrieve")
        self.assertIn("Sin resultados tras", ctx.decision_log[-2]["rationale"])

    def test_retriever_con_subpregunta_vacia_no_revienta(self):
        search = StubSearch([])
        ctx = ResearchContext("")

        devueltos = SourceRetriever(search).decide(ctx, "")

        self.assertEqual(devueltos, [])
        self.assertEqual(search.queries, [])
        self.assertEqual(ctx.decision_log[0]["decision"], "no_results")

    def test_retriever_usa_la_consulta_que_dio_resultados(self):
        class BuscadorConSegundaOportunidad:
            def __init__(self):
                self.queries = []

            def search(self, query, max_results=5):
                self.queries.append(query)
                if len(self.queries) < 2:
                    return []
                return [{"title": "T", "url": "u", "snippet": "s"}]

        search = BuscadorConSegundaOportunidad()
        ctx = ResearchContext("¿pregunta?")

        SourceRetriever(search).decide(ctx, "subpregunta")

        self.assertEqual(ctx.sources[0]["query_used"], search.queries[1])
        self.assertEqual(ctx.sources[0]["related_to"], "subpregunta")
        self.assertEqual(ctx.sources[0]["source"], "unknown")
        self.assertEqual(ctx.decision_log[-1]["decision"], "retrieve")

    def test_retriever_trunca_a_cinco_fuentes_pero_devuelve_todo(self):
        resultados = [{"title": f"T{i}", "url": f"u{i}", "snippet": "s"}
                      for i in range(7)]

        class BuscadorCompleto:
            """Devuelve todos los resultados (StubSearch recortaría a 5)."""

            def search(self, query, max_results=5):
                return resultados

        ctx = ResearchContext("q")

        devueltos = SourceRetriever(BuscadorCompleto()).decide(ctx, "sub")

        self.assertEqual(len(devueltos), 7)
        self.assertEqual(len(ctx.sources), 5)
        self.assertEqual(ctx.sources[4]["url"], "u4")

    def test_retriever_deduplica_por_url_solo_si_hay_url(self):
        ctx = ResearchContext("q")
        ctx.sources.append({"url": "u0", "title": "ya", "snippet": "s"})
        resultados = [
            {"title": "repe", "url": "u0", "snippet": "s"},
            {"title": "nueva", "url": "u1", "snippet": "s"},
            {"title": "sin url 1", "snippet": "s"},
            {"title": "sin url 2", "snippet": "s"},
        ]

        SourceRetriever(StubSearch(resultados)).decide(ctx, "sub")

        urls = [s["url"] for s in ctx.sources]
        self.assertEqual(urls, ["u0", "u1", "", ""])
        self.assertEqual(ctx.decision_log[-1]["rationale"],
                         "3 fuentes nuevas para: sub")

    def test_retriever_campos_por_defecto_de_un_resultado_pobre(self):
        ctx = ResearchContext("q")

        SourceRetriever(StubSearch([{"url": "u1"}])).decide(ctx, "sub")

        self.assertEqual(ctx.sources[0]["title"], "")
        self.assertEqual(ctx.sources[0]["snippet"], "")
        self.assertTrue(ctx.sources[0]["retrieved_at"] > 0)

    # --- ClaimExtractor ----------------------------------------------------
    def test_extractor_prompt_trunca_el_snippet_a_500(self):
        llm = StubLLM(lambda p: "[]")
        ctx = ResearchContext("q")

        ClaimExtractor(llm).decide(ctx, {"url": "u", "snippet": "y" * 600})

        self.assertIn("y" * 500 + "\n", llm.prompts[0])
        self.assertNotIn("y" * 501, llm.prompts[0])

    def test_extractor_anota_url_y_devuelve_la_misma_lista(self):
        llm = StubLLM(lambda p: '[{"claim": "c1", "confidence": 0.4, '
                                '"source_url": "interna"}]')
        ctx = ResearchContext("q")

        claims = ClaimExtractor(llm).decide(ctx, {"url": "u-real", "snippet": "s"})

        self.assertEqual(claims[0]["source_id"], "u-real")
        self.assertEqual(claims[0]["source_url"], "interna")
        self.assertIsInstance(claims[0]["extracted_at"], float)
        self.assertIs(ctx.claims[0], claims[0])
        self.assertEqual(ctx.decision_log[0]["step"], "claim_extraction")
        self.assertEqual(ctx.decision_log[0]["decision"], "extract")

    def test_extractor_fallo_registra_la_decision_y_devuelve_vacio(self):
        llm = StubLLM(lambda p: '{"no": "es un array"}')
        ctx = ResearchContext("q")

        claims = ClaimExtractor(llm).decide(ctx, {"url": "u", "snippet": "s"})

        self.assertEqual(claims, [])
        self.assertEqual(ctx.claims, [])
        self.assertEqual(ctx.decision_log[0]["decision"], "fail")
        self.assertEqual(ctx.decision_log[0]["rationale"],
                         "Failed to parse LLM response")

    # --- ReportGenerator ---------------------------------------------------
    def test_report_generator_prompt_lleva_los_contadores_exactos(self):
        llm = StubLLM(lambda p: "informe")
        ctx = ResearchContext("¿q?")
        ctx.claims.extend([{"claim": "c1"}, {"claim": "c2"}, {"claim": "c3"}])
        ctx.evaluations.extend([{"claim": "c1", "verdict": "supported"},
                                {"claim": "c2", "verdict": "contradicted"}])
        ctx.sources.append({"url": "u"})

        ReportGenerator(llm).decide(ctx)

        prompt = llm.prompts[0]
        self.assertIn("- Total claims extracted: 3", prompt)
        self.assertIn("- Supported: 1", prompt)
        self.assertIn("- Contradictions: 1", prompt)
        self.assertIn("- Uncertain/Unsupported: 2", prompt)
        self.assertIn("- Total sources retrieved: 1", prompt)
        self.assertIn("Evidence evaluations: 2", prompt)

    def test_report_generator_prompt_incluye_fuentes_y_claims_evaluados(self):
        llm = StubLLM(lambda p: "informe")
        ctx = ResearchContext("¿q?")
        ctx.sources.append({
            "title": "Fuente Unica", "url": "https://fuente-unica.example/x",
            "snippet": "Dato unico 12345"})
        ctx.claims.append({"claim": "Dato unico 12345",
                           "source_id": "https://fuente-unica.example/x"})
        ctx.evaluations.append({"claim": "Dato unico 12345",
                                "verdict": "supported", "credibility": 0.9})

        ReportGenerator(llm).decide(ctx)

        prompt = llm.prompts[0]
        self.assertIn("[1] Fuente Unica — https://fuente-unica.example/x", prompt)
        self.assertIn("Dato unico 12345", prompt)
        self.assertIn("[supported] Dato unico 12345", prompt)
        self.assertIn("(source: https://fuente-unica.example/x)", prompt)

    def test_report_generator_prompt_sin_fuentes_lo_declara(self):
        llm = StubLLM(lambda p: "informe")
        ctx = ResearchContext("¿q?")

        ReportGenerator(llm).decide(ctx)

        prompt = llm.prompts[0]
        self.assertIn("(no sources retrieved)", prompt)
        self.assertIn("(no claims extracted)", prompt)

    def test_report_generator_trunca_las_conclusiones_a_100(self):
        llm = StubLLM(lambda p: "# T\n\n## S\n\n" + "x" * 150 + "\n")
        ctx = ResearchContext("q")

        ReportGenerator(llm).decide(ctx)

        ultima = ctx.conclusions[-1]
        self.assertEqual(len(ultima["section"]), 100)
        self.assertGreater(ultima["length"], 100)
        self.assertEqual(ctx.decision_log[0]["decision"], "generate")

    def test_report_generator_usa_solo_las_tres_ultimas_secciones(self):
        informe = "\n".join(f"## S{i}\n\ntexto {i}\n" for i in range(5))
        ctx = ResearchContext("q")

        ReportGenerator(StubLLM(lambda p: informe)).decide(ctx)

        self.assertEqual(len(ctx.conclusions), 3)

    # --- ResearchContext y decomposer --------------------------------------
    def test_context_to_dict_exacto(self):
        ctx = ResearchContext("¿q?", max_iterations=4)
        ctx.subquestions = ["a", "b"]
        ctx.sources.append({"url": "u"})
        ctx.claims.extend([{}, {}])
        ctx.evaluations.append({})
        ctx.conclusions.append({})
        ctx.add_decision("paso", "decidir")

        resumen = ctx.to_dict()
        self.assertIsInstance(resumen.pop("duration_seconds"), float)
        self.assertEqual(resumen, {
            "question": "¿q?",
            "decomposed": False,
            "iterations": 0,
            "subquestions": ["a", "b"],
            "num_sources": 1,
            "num_claims": 2,
            "num_evaluations": 1,
            "num_conclusions": 1,
            "decisions": 1,
        })

    def test_add_decision_guarda_la_iteracion_actual(self):
        ctx = ResearchContext("q")
        ctx.iteration = 3

        ctx.add_decision("paso", "decidir", "porque sí")

        entrada = ctx.decision_log[0]
        self.assertEqual(set(entrada), {"step", "decision", "rationale",
                                        "timestamp", "iteration"})
        self.assertEqual(entrada["iteration"], 3)
        self.assertIsInstance(entrada["timestamp"], float)

    def test_decomposer_prompt_incluye_la_pregunta(self):
        llm = StubLLM(lambda p: "una subpregunta")

        QuestionDecomposer(llm).decide(ResearchContext("¿pregunta exacta?"))

        self.assertIn("¿pregunta exacta?", llm.prompts[0])
        self.assertIn("Decompose this into", llm.prompts[0])

    # --- Orquestador -------------------------------------------------------
    def test_orchestrator_extrae_como_maximo_tres_fuentes_por_subpregunta(self):
        llamadas = []

        def responder(prompt):
            if "Decompose this into" in prompt:
                llamadas.append("decompose")
                return "subpregunta uno"
            if "Extract factual claims" in prompt:
                llamadas.append("extract")
                return '[{"claim": "c", "confidence": 0.5, "source_url": "u"}]'
            if "Evaluate this claim" in prompt:
                llamadas.append("evaluate")
                return ('{"verdict": "supported", "credibility": 0.5, '
                        '"confidence": 0.5, "reasoning": "r"}')
            return "informe"

        search = StubSearch([{"title": f"T{i}", "url": f"u{i}", "snippet": "s"}
                             for i in range(5)])
        _, ctx = ResearchOrchestrator(StubLLM(responder), search).research("q")

        self.assertEqual(llamadas.count("decompose"), 1)
        self.assertEqual(llamadas.count("extract"), 3)
        self.assertEqual(llamadas.count("evaluate"), 3)
        self.assertEqual(ctx.iteration, 1)

    def test_orchestrator_init_guarda_los_motores(self):
        llm, search = MockLLM(), MockSearchAPI()
        orchestrator = ResearchOrchestrator(llm, search, max_iterations=2)

        self.assertIs(orchestrator.llm, llm)
        self.assertIs(orchestrator.search, search)
        self.assertEqual(orchestrator.context.max_iterations, 2)
        self.assertIsInstance(orchestrator.decomposer, QuestionDecomposer)
        self.assertIsInstance(orchestrator.retriever, SourceRetriever)
        self.assertIsInstance(orchestrator.extractor, ClaimExtractor)
        self.assertIsInstance(orchestrator.evaluator, EvidenceEvaluator)
        self.assertIsInstance(orchestrator.generator, ReportGenerator)


class TestFidelidadYVerificacionIndependiente(unittest.TestCase):
    """Métrica de fidelidad (RAGAS-like) y segunda pasada CoVe (opt-in)."""

    def _llm(self, respuestas):
        cola = list(respuestas)

        def responder(prompt):
            return cola.pop(0) if cola else "{}"

        return StubLLM(responder)

    def _contexto(self):
        ctx = ResearchContext("q")
        ctx.sources.extend([{"url": "u0", "title": "T0", "snippet": "s0"},
                            {"url": "u1", "title": "T1", "snippet": "s1"}])
        return ctx

    # --- CoVe -------------------------------------------------------------
    def test_json_que_no_es_objeto_en_verificacion_independiente(self):
        llm = self._llm(['{"verdict": "supported", "credibility": 0.9}',
                         "[1, 2]"])

        ev = EvidenceEvaluator(llm, verificacion_independiente=True).decide(
            self._contexto(), {"claim": "c", "source_url": "u0"})

        info = ev["verificacion_independiente"]
        self.assertEqual(info["verdict"], "not_addressed")
        self.assertEqual(info["verdict_principal"], "supported")
        self.assertFalse(info["contested"])
        self.assertEqual(info["error"], "Failed to parse evaluation")

    def test_verificacion_desactivada_por_defecto_hace_una_llamada(self):
        llm = self._llm(['{"verdict": "supported", "credibility": 0.9}'])

        ev = EvidenceEvaluator(llm).decide(self._contexto(),
                                           {"claim": "c", "source_url": "u0"})

        self.assertEqual(len(llm.prompts), 1)
        self.assertNotIn("verificacion_independiente", ev)

    def test_activa_mira_fuentes_alternativas_y_marca_contestado(self):
        llm = self._llm(['{"verdict": "supported", "credibility": 0.9}',
                         '{"verdict": "contradicted", "credibility": 0.2}'])

        ev = EvidenceEvaluator(llm, verificacion_independiente=True).decide(
            self._contexto(), {"claim": "c", "source_url": "u0"})

        self.assertIn("T1", llm.prompts[1])
        self.assertNotIn("T0", llm.prompts[1])
        info = ev["verificacion_independiente"]
        self.assertEqual(info["verdict"], "contradicted")
        self.assertEqual(info["verdict_principal"], "supported")
        self.assertTrue(info["contested"])
        self.assertEqual(info["fuentes_alternativas"], 1)

    def test_origen_por_source_id_cuando_falta_source_url(self):
        """El origen fiable es `source_id` (URL real del pipeline): si el
        modelo no aportó `source_url`, la fuente original NO debe colarse en la
        verificación independiente (antes se re-incluía)."""
        llm = self._llm(['{"verdict": "supported", "credibility": 0.9}',
                         '{"verdict": "supported", "credibility": 0.8}'])

        ev = EvidenceEvaluator(llm, verificacion_independiente=True).decide(
            self._contexto(), {"claim": "c", "source_id": "u0"})

        self.assertIn("T1", llm.prompts[1])
        self.assertNotIn("T0", llm.prompts[1])
        self.assertEqual(ev["verificacion_independiente"]["fuentes_alternativas"], 1)

    def test_resultado_y_registro_exactos(self):
        llm = self._llm(['{"verdict": "supported", "credibility": 0.75, '
                         '"confidence": 0.6, "reasoning": "r"}'])
        ctx = self._contexto()

        ev = EvidenceEvaluator(llm).decide(ctx, {"claim": "c", "source_url": "u1"})

        sin_ts = {k: v for k, v in ev.items() if k != "evaluated_at"}
        self.assertEqual(sin_ts, {
            "verdict": "supported", "credibility": 0.75, "confidence": 0.6,
            "reasoning": "r", "claim": "c", "source_url": "u1"})
        self.assertIsInstance(ev["evaluated_at"], float)
        self.assertEqual(ctx.evaluations, [ev])
        self.assertEqual(ctx.decision_log[-1]["step"], "evidence_evaluation")
        self.assertEqual(ctx.decision_log[-1]["decision"], "evaluate")
        self.assertEqual(ctx.decision_log[-1]["rationale"],
                         "Verdict: supported, Credibility: 0.75")
        self.assertIn("T1", llm.prompts[0])
        self.assertNotIn("T0", llm.prompts[0])

    def test_sin_fuente_coincidente_usa_las_tres_primeras(self):
        llm = self._llm(['{"verdict": "not_addressed", "credibility": 0}'])
        ctx = ResearchContext("q")
        ctx.sources.extend([{"url": f"u{i}", "title": f"T{i}", "snippet": "s"}
                            for i in range(4)])

        EvidenceEvaluator(llm).decide(ctx, {"claim": "c", "source_url": "nada"})

        prompt = llm.prompts[0]
        for titulo in ("T0", "T1", "T2"):
            self.assertIn(titulo, prompt)
        self.assertNotIn("T3", prompt)

    def test_limita_la_verificacion_a_tres_alternativas(self):
        ctx = ResearchContext("q")
        ctx.sources.extend([{"url": f"u{i}", "title": f"T{i}", "snippet": "s"}
                            for i in range(6)])
        llm = self._llm(['{"verdict": "supported", "credibility": 0.9}',
                         '{"verdict": "not_addressed", "credibility": 0.1}'])

        ev = EvidenceEvaluator(llm, verificacion_independiente=True).decide(
            ctx, {"claim": "c", "source_url": "u0"})

        prompt = llm.prompts[1]
        for titulo in ("T1", "T2", "T3"):
            self.assertIn(titulo, prompt)
        for titulo in ("T0", "T4", "T5"):
            self.assertNotIn(titulo, prompt)
        self.assertEqual(ev["verificacion_independiente"], {
            "verdict": "not_addressed", "credibility": 0.1, "confidence": 0,
            "verdict_principal": "supported", "contested": False,
            "fuentes_alternativas": 5,
            "independencia": "mismo-proveedor",
            "verificador": "StubLLM", "generador": "StubLLM"})

    def test_sin_alternativas_registra_motivo_exacto(self):
        ctx = ResearchContext("q")
        ctx.sources.append({"url": "u0", "title": "T0", "snippet": "s"})
        llm = self._llm(['{"verdict": "supported", "credibility": 0.9}'])

        ev = EvidenceEvaluator(llm, verificacion_independiente=True).decide(
            ctx, {"claim": "c", "source_url": "u0"})

        self.assertIsNone(ev["verificacion_independiente"])
        self.assertEqual(len(llm.prompts), 1)
        self.assertEqual(ctx.decision_log[-1]["step"],
                         "independent_verification")
        self.assertEqual(ctx.decision_log[-1]["decision"], "skip")
        self.assertEqual(ctx.decision_log[-1]["rationale"],
                         "Sin fuentes alternativas para verificar el claim")

    def test_registra_la_decision_de_verificacion(self):
        llm = self._llm(['{"verdict": "supported", "credibility": 0.9}',
                         '{"verdict": "contradicted", "credibility": 0.2}'])
        ctx = self._contexto()

        EvidenceEvaluator(llm, verificacion_independiente=True).decide(
            ctx, {"claim": "c", "source_url": "u0"})

        verificaciones = [d for d in ctx.decision_log
                          if d["step"] == "independent_verification"]
        self.assertEqual(len(verificaciones), 1)
        self.assertIn("contestado", verificaciones[0]["rationale"])

    def test_coincidencia_no_marca_contestado(self):
        llm = self._llm(['{"verdict": "supported", "credibility": 0.9}',
                         '{"verdict": "supported", "credibility": 0.8}'])
        ctx = self._contexto()

        ev = EvidenceEvaluator(llm, verificacion_independiente=True).decide(
            ctx, {"claim": "c", "source_url": "u0"})

        self.assertFalse(ev["verificacion_independiente"]["contested"])
        self.assertIn("coincide", ctx.decision_log[-1]["rationale"])

    def test_no_addressed_no_cuenta_como_contestado(self):
        llm = self._llm(['{"verdict": "supported", "credibility": 0.9}',
                         '{"verdict": "not_addressed", "credibility": 0.0}'])

        ev = EvidenceEvaluator(llm, verificacion_independiente=True).decide(
            self._contexto(), {"claim": "c", "source_url": "u0"})

        self.assertFalse(ev["verificacion_independiente"]["contested"])

    def test_sin_fuentes_alternativas_no_inventa_verificacion(self):
        llm = self._llm(['{"verdict": "supported", "credibility": 0.9}'])
        ctx = ResearchContext("q")
        ctx.sources.append({"url": "u0", "title": "T0", "snippet": "s0"})

        ev = EvidenceEvaluator(llm, verificacion_independiente=True).decide(
            ctx, {"claim": "c", "source_url": "u0"})

        self.assertEqual(len(llm.prompts), 1)
        self.assertIsNone(ev["verificacion_independiente"])
        self.assertEqual(ctx.decision_log[-1]["decision"], "skip")

    def test_independiente_sin_json_no_marca_contestado(self):
        llm = self._llm(['{"verdict": "supported", "credibility": 0.9}', "no json"])

        ev = EvidenceEvaluator(llm, verificacion_independiente=True).decide(
            self._contexto(), {"claim": "c", "source_url": "u0"})

        info = ev["verificacion_independiente"]
        self.assertFalse(info["contested"])
        self.assertEqual(info["error"], "Failed to parse evaluation")

    def test_verificador_distinto_usa_otro_proveedor_y_lo_declara(self):
        llm = self._llm(['{"verdict": "supported", "credibility": 0.9}'])
        verificador = self._llm(['{"verdict": "contradicted", "credibility": 0.1}'])
        ctx = self._contexto()

        ev = EvidenceEvaluator(llm, verificacion_independiente=True,
                               llm_verificador=verificador).decide(
            ctx, {"claim": "c", "source_url": "u0"})

        self.assertEqual(len(llm.prompts), 1)          # solo la evaluación principal
        self.assertEqual(len(verificador.prompts), 1)  # la CoVe va al verificador
        info = ev["verificacion_independiente"]
        self.assertEqual(info["independencia"], "proveedor-distinto")
        self.assertEqual(info["verificador"], "StubLLM")
        self.assertEqual(info["generador"], "StubLLM")
        self.assertTrue(info["contested"])
        self.assertIn("[proveedor-distinto]", ctx.decision_log[-1]["rationale"])

    def test_verificador_igual_al_generador_se_declara_mismo_proveedor(self):
        llm = self._llm(['{"verdict": "supported", "credibility": 0.9}',
                         '{"verdict": "supported", "credibility": 0.8}'])
        ctx = self._contexto()

        ev = EvidenceEvaluator(llm, verificacion_independiente=True,
                               llm_verificador=llm).decide(
            ctx, {"claim": "c", "source_url": "u0"})

        self.assertEqual(len(llm.prompts), 2)
        info = ev["verificacion_independiente"]
        self.assertEqual(info["independencia"], "mismo-proveedor")
        self.assertIn("[mismo-proveedor]", ctx.decision_log[-1]["rationale"])

    def test_sin_verificador_separado_la_cove_se_declara_mismo_proveedor(self):
        llm = self._llm(['{"verdict": "supported", "credibility": 0.9}',
                         '{"verdict": "supported", "credibility": 0.8}'])
        ctx = self._contexto()

        ev = EvidenceEvaluator(llm, verificacion_independiente=True).decide(
            ctx, {"claim": "c", "source_url": "u0"})

        info = ev["verificacion_independiente"]
        self.assertEqual(info["independencia"], "mismo-proveedor")
        self.assertIn("[mismo-proveedor]", ctx.decision_log[-1]["rationale"])

    def test_orchestrator_pasa_el_flag(self):
        con = ResearchOrchestrator(MockLLM(), MockSearchAPI(),
                                   verificacion_independiente=True)
        sin = ResearchOrchestrator(MockLLM(), MockSearchAPI())

        self.assertTrue(con.evaluator.verificacion_independiente)
        self.assertFalse(sin.evaluator.verificacion_independiente)

    def test_orchestrator_acepta_verificador_separado(self):
        verificador = MockLLM(model="verificador-mock")

        orquestador = ResearchOrchestrator(
            MockLLM(), MockSearchAPI(), verificacion_independiente=True,
            llm_verificador=verificador)

        self.assertIs(orquestador.evaluator.llm_verificador, verificador)
        self.assertTrue(orquestador.evaluator._es_verificador_distinto())

    # --- Fidelidad --------------------------------------------------------
    def test_fidelidad_cifras_respaldadas_y_no(self):
        from tests.benchmarks.rubrics import evaluar_fidelidad

        informe = "El reactor alcanzó 150 millones de grados y 1.234 segundos."
        fuentes = ["Se lograron 150 millones de grados en el experimento.",
                   "La duración fue de 1234 segundos según el informe."]

        resultado = evaluar_fidelidad(informe, fuentes)

        self.assertEqual(resultado["fidelidad"], 1.0)
        self.assertEqual(resultado["cifras_informe"], 2)
        self.assertEqual(resultado["sin_respaldo"], [])

    def test_fidelidad_detecta_cifra_inventada(self):
        from tests.benchmarks.rubrics import evaluar_fidelidad

        resultado = evaluar_fidelidad("Se logró un 99.9% de eficiencia.",
                                      ["La eficiencia fue alta."])

        self.assertEqual(resultado["fidelidad"], 0.0)
        self.assertEqual(resultado["sin_respaldo"], ["99.9"])

    def test_fidelidad_sin_cifras_es_uno(self):
        from tests.benchmarks.rubrics import evaluar_fidelidad

        resultado = evaluar_fidelidad("Informe sin números.", ["Fuente sin números."])

        self.assertEqual(resultado["fidelidad"], 1.0)
        self.assertEqual(resultado["cifras_informe"], 0)

    def test_fidelidad_sin_fuentes_detecta_todo_sin_respaldo(self):
        from tests.benchmarks.rubrics import evaluar_fidelidad

        resultado = evaluar_fidelidad("Cita el 42 y el 7.", [])

        self.assertEqual(resultado["fidelidad"], 0.0)
        self.assertEqual(sorted(resultado["sin_respaldo"]), ["42", "7"])


class TestRoutingPorTarea(unittest.TestCase):
    """`llm_rapido`: descompone y extrae el rápido; evalúa y redacta el principal."""

    def test_sin_llm_rapido_todo_usa_el_principal(self):
        principal = StubLLM(lambda p: "x")

        orchestrator = ResearchOrchestrator(principal, MockSearchAPI())

        self.assertIs(orchestrator.llm_rapido, principal)
        self.assertIs(orchestrator.decomposer.llm_provider, principal)
        self.assertIs(orchestrator.evaluator.llm_provider, principal)

    def test_con_llm_rapido_se_reparten_las_tareas(self):
        principal, rapido = StubLLM(lambda p: "x"), StubLLM(lambda p: "y")

        orchestrator = ResearchOrchestrator(principal, MockSearchAPI(),
                                            llm_rapido=rapido)

        self.assertIs(orchestrator.decomposer.llm_provider, rapido)
        self.assertIs(orchestrator.extractor.llm_provider, rapido)
        self.assertIs(orchestrator.evaluator.llm_provider, principal)
        self.assertIs(orchestrator.generator.llm_provider, principal)

    def test_pipeline_con_routing_reparte_las_llamadas(self):
        def responder_rapido(prompt):
            if "Decompose this into" in prompt:
                return "subpregunta uno"
            return '[{"claim": "c", "confidence": 0.5, "source_url": "u"}]'

        def responder_principal(prompt):
            if "Evaluate this claim" in prompt:
                return ('{"verdict": "supported", "credibility": 0.5, '
                        '"confidence": 0.5, "reasoning": "r"}')
            return "informe"

        rapido = StubLLM(responder_rapido)
        principal = StubLLM(responder_principal)
        orchestrator = ResearchOrchestrator(
            principal,
            StubSearch([{"title": "T", "url": "u", "snippet": "s"}]),
            llm_rapido=rapido)

        orchestrator.research("q")

        self.assertTrue(any("Decompose this into" in p for p in rapido.prompts))
        self.assertTrue(any("Extract factual claims" in p for p in rapido.prompts))
        self.assertTrue(any("Evaluate this claim" in p for p in principal.prompts))
        self.assertTrue(any("Generate a comprehensive research report" in p
                            for p in principal.prompts))
        self.assertFalse(any("Evaluate this claim" in p for p in rapido.prompts))


class JuezFijo:
    """Evaluador de relevancia de prueba (SIMULADO): puntuaciones en cola."""

    def __init__(self, puntuaciones):
        self.puntuaciones = list(puntuaciones)
        self.llamadas = 0

    def evaluar(self, subquestion, resultados):
        self.llamadas += 1
        return self.puntuaciones.pop(0) if self.puntuaciones else None


class TestEvaluadorDeRelevanciaCrag(unittest.TestCase):
    """Acción correctiva de CRAG: con relevancia baja se reformula la consulta."""

    RESULTADOS = [{"title": "T", "url": "u", "snippet": "s"}]

    def test_sin_juez_una_sola_consulta_y_sin_decisiones_crag(self):
        search = StubSearch(self.RESULTADOS)
        ctx = ResearchContext("q")

        SourceRetriever(search).decide(ctx, "sub")

        self.assertEqual(len(search.queries), 1)
        self.assertFalse(any("crag" in d["decision"] for d in ctx.decision_log))

    def test_juez_alto_acepta_la_primera_consulta(self):
        search = StubSearch(self.RESULTADOS)
        juez = JuezFijo([0.9])
        ctx = ResearchContext("q")

        SourceRetriever(search, evaluador_relevancia=juez).decide(ctx, "sub")

        self.assertEqual(len(search.queries), 1)
        self.assertEqual(juez.llamadas, 1)
        self.assertEqual(ctx.sources[0]["query_used"], search.queries[0])

    def test_juez_bajo_reformula_y_usa_la_siguiente(self):
        search = StubSearch(self.RESULTADOS)
        juez = JuezFijo([0.1, 0.9])
        ctx = ResearchContext("q")

        SourceRetriever(search, evaluador_relevancia=juez).decide(ctx, "sub")

        self.assertEqual(len(search.queries), 2)
        self.assertEqual(ctx.sources[0]["query_used"], search.queries[1])
        reformulaciones = [d for d in ctx.decision_log
                           if d["decision"] == "crag_reformular"]
        self.assertEqual(len(reformulaciones), 1)

    def test_umbral_configurable(self):
        search = StubSearch(self.RESULTADOS)
        juez = JuezFijo([0.4, 0.9])
        ctx = ResearchContext("q")

        SourceRetriever(search, evaluador_relevancia=juez,
                        umbral_relevancia=0.3).decide(ctx, "sub")

        self.assertEqual(len(search.queries), 1)

    def test_ultima_candidata_con_relevancia_baja_se_acepta_y_registra(self):
        search = StubSearch(self.RESULTADOS)
        juez = JuezFijo([0.1] * 10)
        ctx = ResearchContext("q")

        SourceRetriever(search, evaluador_relevancia=juez).decide(ctx, "sub")

        self.assertEqual(len(search.queries), 2)          # candidatas únicas
        self.assertEqual(len(ctx.sources), 1)             # no descarta evidencia
        aceptaciones = [d for d in ctx.decision_log
                        if d["decision"] == "crag_aceptar"]
        self.assertEqual(len(aceptaciones), 1)

    def test_juez_roto_no_descarta_evidencia_y_lo_registra(self):
        search = StubSearch(self.RESULTADOS)
        juez = JuezFijo([None])
        ctx = ResearchContext("q")

        SourceRetriever(search, evaluador_relevancia=juez).decide(ctx, "sub")

        self.assertEqual(len(search.queries), 1)
        self.assertEqual(len(ctx.sources), 1)
        sin_juez = [d for d in ctx.decision_log if d["decision"] == "crag_sin_juez"]
        self.assertEqual(len(sin_juez), 1)
        self.assertIn("fail-open", sin_juez[0]["rationale"])

    def test_relevance_judge_real_con_json_y_sin_json(self):
        from deep_research_system import RelevanceJudge

        con_json = RelevanceJudge(StubLLM(lambda p: '{"relevancia": 0.8}'))
        sin_json = RelevanceJudge(StubLLM(lambda p: "no json"))

        self.assertEqual(con_json.evaluar("sub", self.RESULTADOS), 0.8)
        self.assertIsNone(sin_json.evaluar("sub", self.RESULTADOS))

    def test_relevance_judge_json_que_no_es_objeto_devuelve_none(self):
        from deep_research_system import RelevanceJudge

        juez = RelevanceJudge(StubLLM(lambda p: "[0.8]"))

        self.assertIsNone(juez.evaluar("sub", self.RESULTADOS))

    def test_relevance_judge_prompt_incluye_subpregunta_y_titulos(self):
        from deep_research_system import RelevanceJudge

        llm = StubLLM(lambda p: '{"relevancia": 0.5}')
        RelevanceJudge(llm).evaluar("mi subpregunta", self.RESULTADOS)

        self.assertIn("mi subpregunta", llm.prompts[0])
        self.assertIn("T", llm.prompts[0])

    def test_orchestrator_activa_el_juez_por_flag(self):
        con = ResearchOrchestrator(MockLLM(), MockSearchAPI(),
                                   evaluador_relevancia=True)
        sin = ResearchOrchestrator(MockLLM(), MockSearchAPI())

        self.assertIsNotNone(con.retriever.evaluador_relevancia)
        self.assertIsNone(sin.retriever.evaluador_relevancia)
        self.assertEqual(con.retriever.umbral_relevancia, 0.5)


class TestReportGeneratorExacto(unittest.TestCase):
    def _ctx(self):
        ctx = ResearchContext("Q")
        ctx.subquestions = ["S1"]
        ctx.sources = [{"title": "T", "url": "https://x", "snippet": "detalle"}]
        ctx.claims = [{"claim": "C1", "source_id": "https://x"},
                      {"claim": "C2"}]
        ctx.evaluations = [{"claim": "C1", "verdict": "supported"},
                           {"claim": "C2", "verdict": "contradicted"}]
        return ctx

    def test_prompt_exacto(self):
        llm = StubLLM(lambda p: "# R")
        ctx = self._ctx()

        report = ReportGenerator(llm).decide(ctx)

        self.assertEqual(report, "# R")
        self.assertEqual(llm.prompts[0], (
            "Generate a comprehensive research report for: Q\n"
            "\n"
            "Use ONLY the retrieved sources and evaluated claims below as evidence. Cite\n"
            "sources as [n] matching their numbers. If the evidence is insufficient for a\n"
            "statement, say so instead of inventing it.\n"
            "\n"
            "Retrieved sources:\n"
            "[1] T — https://x\n"
            "    detalle\n"
            "\n"
            "Evaluated claims:\n"
            "- [supported] C1 (source: https://x)\n"
            "- [contradicted] C2 (source: unknown)\n"
            "\n"
            "Structure:\n"
            "1. Executive Summary (2-3 paragraphs)\n"
            "2. Findings (organized by sub-question from: ['S1'])\n"
            "3. Evidence Assessment (supported claims with source citations, contradictions, uncertainties)\n"
            "4. Conclusions (what can be definitively stated, what remains uncertain)\n"
            "5. Limitations and Research Gaps\n"
            "\n"
            "Claim data:\n"
            "- Total claims extracted: 2\n"
            "- Supported: 1\n"
            "- Contradictions: 1\n"
            "- Uncertain/Unsupported: 1\n"
            "\n"
            "Source data:\n"
            "- Total sources retrieved: 1\n"
            "\n"
            "Evidence evaluations: 2\n"
            "\n"
            "Generate the full report in markdown format with proper citations [1], [2] etc.\n"
            "matching the sources retrieved. Be factual and acknowledge uncertainties."))
        self.assertEqual(ctx.decision_log[-1]["step"], "report_generation")
        self.assertEqual(ctx.decision_log[-1]["decision"], "generate")
        self.assertEqual(ctx.decision_log[-1]["rationale"],
                         "Report generated with 1 conclusion sections")

    def test_contexto_vacio_usa_marcadores(self):
        ctx = ResearchContext("Q")
        llm = StubLLM(lambda p: "r")

        ReportGenerator(llm).decide(ctx)

        prompt = llm.prompts[0]
        self.assertIn("(no sources retrieved)\n", prompt)
        self.assertIn("(no claims extracted)\n", prompt)
        self.assertIn("- Total claims extracted: 0", prompt)
        self.assertIn("- Total sources retrieved: 0", prompt)

    def test_extrae_las_tres_ultimas_secciones_con_truncado(self):
        report = ("# A\ntexto A\n\n## B\ntexto B\n\n## C\n" + "c" * 150
                  + "\n\n## D\ntexto D\n")

        concl = ReportGenerator(StubLLM(lambda p: "r"))._extract_conclusions(
            report)

        self.assertEqual([c["section"] for c in concl],
                         ["B\ntexto B\n", "C\n" + "c" * 98, "D\ntexto D\n"])
        self.assertEqual([c["length"] for c in concl], [10, 153, 10])


class TestCRAGMotivosExactos(unittest.TestCase):
    def test_requery_reformulacion_y_aceptacion(self):
        class Buscador:
            def __init__(self):
                self.queries = []

            def search(self, query, max_results=5):
                self.queries.append(query)
                if len(self.queries) == 1:
                    return []
                return [{"title": "T", "url": f"u{len(self.queries)}",
                         "snippet": "s"}]

        class Juez:
            def evaluar(self, subquestion, resultados):
                return 0.1

        search = Buscador()
        ctx = ResearchContext("fusión nuclear")

        SourceRetriever(search, evaluador_relevancia=Juez()).decide(
            ctx, "¿Cuál es el estado actual?")

        rationales = [d["rationale"] for d in ctx.decision_log]
        self.assertEqual(rationales[0],
                         f"Sin resultados para '{search.queries[0][:40]}'; "
                         f"se amplía la consulta")
        self.assertEqual(rationales[1],
                         f"Resultados poco relevantes para "
                         f"'{search.queries[1][:40]}'; se reformula la consulta")
        self.assertEqual(rationales[2],
                         "Relevancia baja pero no quedan candidatas: se "
                         "acepta lo recuperado")
        self.assertEqual(rationales[3], "1 fuentes nuevas para: "
                                        "¿Cuál es el estado actual?")

    def test_ultima_consulta_sin_resultados_registra_no_results(self):
        class Vacio:
            def __init__(self):
                self.queries = []

            def search(self, query, max_results=5):
                self.queries.append(query)
                return []

        ctx = ResearchContext("fusión nuclear")

        SourceRetriever(Vacio()).decide(ctx, "¿Cuál es el estado actual?")

        sin_resultados = [d for d in ctx.decision_log
                          if d["decision"] == "no_results"]
        self.assertEqual(len(sin_resultados), 1)
        self.assertEqual(
            sin_resultados[0]["rationale"],
            "Sin resultados tras 3 consultas para: ¿Cuál es el estado actual?")


class TestPromptsExactos(unittest.TestCase):
    """Prompts EXACTOS de los evaluadores nuevos.

    Un prompt de ~600 caracteres genera decenas de mutantes de fragmento: solo
    una aserción del texto completo los mata (misma técnica que
    `tests/test_prompt_y_claves_exactas.py`).
    """

    def test_prompt_de_evaluacion_exacto(self):
        prompt = EvidenceEvaluator._prompt_evaluacion(
            {"claim": "el reactor alcanzó 150 millones de grados"},
            [{"title": "Paper X", "snippet": "detalle del experimento"}])

        self.assertEqual(prompt, """Evaluate this claim against the provided sources. Determine:
1. Is the claim supported, contradicted, or not addressed?
2. What is the overall credibility score (0-1) of the supporting sources?
3. Are there contradictions from other sources?

Claim: el reactor alcanzó 150 millones de grados
Source 1: Paper X: detalle del experimento


Return ONLY JSON (no markdown fences, no extra text):
{"verdict": "supported|contradicted|not_addressed", "credibility": 0-1, "confidence": 0-1, "reasoning": "..."}""")

    def test_prompt_de_evaluacion_sin_fuentes_ni_claim(self):
        prompt = EvidenceEvaluator._prompt_evaluacion({}, [])

        self.assertIn("Claim: \n\n\nReturn ONLY JSON", prompt)

    def test_prompt_trunca_snippet_a_200_y_titulo_por_defecto(self):
        prompt = EvidenceEvaluator._prompt_evaluacion(
            {"claim": "c"}, [{"snippet": "a" * 200 + "b" * 50}])

        self.assertIn("Source 1: Unknown: " + "a" * 200 + "\n", prompt)
        self.assertNotIn("b" * 50, prompt)

    def test_prompt_del_juez_de_relevancia_exacto(self):
        from deep_research_system import RelevanceJudge

        llm = StubLLM(lambda p: '{"relevancia": 0.7}')
        RelevanceJudge(llm).evaluar("mi subpregunta",
                                    [{"title": "T", "snippet": "s"}])

        self.assertEqual(llm.prompts[0], """Evalúa si estos resultados de búsqueda son RELEVANTES para la
subpregunta. Responde SOLO JSON: {"relevancia": 0-1, "motivo": "..."}

Subpregunta: mi subpregunta

Resultados:
- T: s""")

    def test_el_juez_trunca_el_snippet_a_150(self):
        from deep_research_system import RelevanceJudge

        llm = StubLLM(lambda p: '{"relevancia": 0.7}')
        RelevanceJudge(llm).evaluar("sub", [{"title": "T", "snippet": "z" * 200}])

        self.assertIn("z" * 150, llm.prompts[0])
        self.assertNotIn("z" * 151, llm.prompts[0])


if __name__ == "__main__":
    unittest.main()
