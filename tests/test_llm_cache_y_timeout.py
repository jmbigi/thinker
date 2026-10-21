"""Tests del timeout explícito y la caché de respuestas (eficiencia medida).

Referencias: `docs/REFERENCIAS-IA.md` (propuestas 1 y 2). Todo offline: el
cliente del SDK se sustituye por un doble y no hay red.
"""

import contextlib
import io
import os
import unittest
from unittest.mock import call, patch

from llm_providers import (DEFAULT_TIMEOUT, OPENROUTER_FALLBACK_CHAIN,
                           DeepSeekLLM, KiloGatewayLLM, MockLLM, OllamaLLM,
                           OpenAILLM, OpenRouterLLM, ResponseCache,
                           _chat_completion)
from tests.helpers import FakeAPIError, make_chat_client, ok_chat_response


def _entorno_sin(*variables):
    """Copia del entorno SIN las variables dadas (para probar el caso ausente)."""
    return {k: v for k, v in os.environ.items() if k not in variables}


class TestResponseCache(unittest.TestCase):
    def test_guarda_devuelve_y_cuenta_aciertos(self):
        cache = ResponseCache()

        self.assertIsNone(cache.get("modelo", "prompt"))
        cache.set("modelo", "prompt", "respuesta")

        self.assertEqual(cache.get("modelo", "prompt"), "respuesta")
        self.assertEqual(cache.hits, 1)
        self.assertEqual(len(cache.entradas), 1)

    def test_la_clave_distingue_modelo_y_prompt(self):
        cache = ResponseCache()
        cache.set("modelo-a", "prompt", "uno")

        self.assertIsNone(cache.get("modelo-b", "prompt"))
        self.assertIsNone(cache.get("modelo-a", "otro prompt"))
        self.assertEqual(cache.hits, 0)

    def test_respuesta_vacia_se_distingue_de_ausencia(self):
        cache = ResponseCache()
        cache.set("modelo", "prompt", "")

        self.assertEqual(cache.get("modelo", "prompt"), "")
        self.assertEqual(cache.hits, 1)

    def test_los_hits_se_acumulan_en_aciertos_sucesivos(self):
        cache = ResponseCache()
        cache.set("modelo", "p1", "uno")
        cache.set("modelo", "p2", "dos")

        cache.get("modelo", "p1")
        cache.get("modelo", "p2")

        self.assertEqual(cache.hits, 2)


class TestCacheEnElCliente(unittest.TestCase):
    def _llm(self, **kwargs):
        return OpenAILLM(api_key="clave-ficticia-de-test", **kwargs)

    def test_prompt_repetido_no_vuelve_a_la_red(self):
        cliente = make_chat_client([ok_chat_response("hola")])
        llm = self._llm()

        with patch("openai.OpenAI", return_value=cliente):
            primera = llm.generate("mismo prompt")
            segunda = llm.generate("mismo prompt")

        self.assertEqual(primera, "hola")
        self.assertEqual(segunda, "hola")
        self.assertEqual(len(cliente.calls), 1)
        self.assertEqual(llm.cache.hits, 1)

    def test_prompts_distintos_van_a_la_red(self):
        cliente = make_chat_client([ok_chat_response("uno"), ok_chat_response("dos")])
        llm = self._llm()

        with patch("openai.OpenAI", return_value=cliente):
            llm.generate("p1")
            llm.generate("p2")

        self.assertEqual(len(cliente.calls), 2)
        self.assertEqual(llm.cache.hits, 0)

    def test_modelos_distintos_no_comparten_entrada(self):
        cliente = make_chat_client([ok_chat_response("uno"), ok_chat_response("dos")])
        llm = self._llm()

        with patch("openai.OpenAI", return_value=cliente):
            llm.generate("p", model="modelo-a")
            llm.generate("p", model="modelo-b")

        self.assertEqual(len(cliente.calls), 2)

    def test_cache_desactivada(self):
        cliente = make_chat_client([ok_chat_response("hola"), ok_chat_response("hola")])
        llm = self._llm(use_cache=False)

        with patch("openai.OpenAI", return_value=cliente):
            llm.generate("mismo prompt")
            llm.generate("mismo prompt")

        self.assertEqual(len(cliente.calls), 2)
        self.assertIsNone(llm.cache)

    def test_los_errores_no_se_cachean(self):
        cliente = make_chat_client([
            FakeAPIError("caído", status_code=404),
            ok_chat_response("ahora sí"),
        ])
        llm = self._llm()

        with patch("openai.OpenAI", return_value=cliente):
            with self.assertRaises(FakeAPIError):
                llm.generate("p")
            salida = llm.generate("p")

        self.assertEqual(salida, "ahora sí")
        self.assertEqual(len(cliente.calls), 2)
        self.assertEqual(llm.cache.hits, 0)

    def test_cliente_reutilizado_entre_llamadas(self):
        cliente = make_chat_client([ok_chat_response("uno"), ok_chat_response("dos")])
        llm = self._llm()

        with patch("openai.OpenAI", return_value=cliente) as fabrica:
            llm.generate("p1")
            llm.generate("p2")

        self.assertEqual(len(cliente.calls), 2)
        self.assertEqual(fabrica.call_count, 1)

    def test_cliente_distinto_por_clave_y_base_url(self):
        cliente = make_chat_client([ok_chat_response("uno"), ok_chat_response("dos")])
        llm = self._llm()

        with patch("openai.OpenAI", return_value=cliente) as fabrica:
            llm.generate("p", base_url="https://uno.invalid/v1")
            llm.generate("p", base_url="https://dos.invalid/v1")

        self.assertEqual(fabrica.call_count, 2)

    def test_la_cache_es_por_instancia(self):
        cliente = make_chat_client([ok_chat_response("uno"), ok_chat_response("dos")])

        with patch("openai.OpenAI", return_value=cliente):
            self._llm().generate("p")
            self._llm().generate("p")

        self.assertEqual(len(cliente.calls), 2)


class TestTimeoutExplicito(unittest.TestCase):
    def test_timeout_por_defecto_es_60_y_llega_a_la_peticion(self):
        cliente = make_chat_client([ok_chat_response("ok")])
        llm = OpenAILLM(api_key="clave-ficticia-de-test")

        with patch("openai.OpenAI", return_value=cliente):
            llm.generate("p")

        self.assertEqual(DEFAULT_TIMEOUT, 60.0)
        self.assertEqual(llm.timeout, 60.0)
        self.assertEqual(cliente.calls[0]["timeout"], 60.0)

    def test_timeout_configurable(self):
        cliente = make_chat_client([ok_chat_response("ok")])
        llm = OpenAILLM(api_key="clave-ficticia-de-test", timeout=2.5)

        with patch("openai.OpenAI", return_value=cliente):
            llm.generate("p")

        self.assertEqual(cliente.calls[0]["timeout"], 2.5)

    def test_chat_completion_rechaza_max_retries_invalido(self):
        cliente = make_chat_client([])

        with self.assertRaises(ValueError):
            _chat_completion(cliente, "modelo", "p", 0, "Test")
        self.assertEqual(cliente.calls, [])

    def test_chat_completion_usa_la_cache_inyectada(self):
        cache = ResponseCache()
        cliente = make_chat_client([ok_chat_response("ok")])

        _chat_completion(cliente, "modelo", "p", 3, "Test", cache=cache)
        segunda = _chat_completion(cliente, "modelo", "p", 3, "Test", cache=cache)

        self.assertEqual(segunda, "ok")
        self.assertEqual(len(cliente.calls), 1)
        self.assertEqual(cache.hits, 1)


class TestReintentosExactos(unittest.TestCase):
    def test_mensajes_y_esperas_exactas(self):
        cliente = make_chat_client([
            FakeAPIError("caído", status_code=429),
            FakeAPIError("caído", status_code=429),
            ok_chat_response("ok"),
        ])
        errores = io.StringIO()
        with patch("llm_providers.random.uniform", return_value=0.0), \
                patch("llm_providers.time.sleep") as dormir, \
                contextlib.redirect_stderr(errores):
            salida = _chat_completion(cliente, "modelo", "p", 3, "Test")

        self.assertEqual(salida, "ok")
        self.assertEqual(len(cliente.calls), 3)
        self.assertEqual([c["model"] for c in cliente.calls], ["modelo"] * 3)
        self.assertEqual([c["timeout"] for c in cliente.calls], [60.0] * 3)
        self.assertEqual(dormir.call_args_list, [call(2.0), call(4.0)])
        self.assertEqual(
            errores.getvalue().splitlines(),
            ["[Test] error transitorio (429); reintento 1/2 en 2.0s",
             "[Test] error transitorio (429); reintento 2/2 en 4.0s"])

    def test_agota_reintentos_y_eleva_el_ultimo(self):
        cliente = make_chat_client([FakeAPIError("caído", status_code=503)] * 3)
        with patch("llm_providers.time.sleep"):
            with self.assertRaises(FakeAPIError):
                _chat_completion(cliente, "m", "p", 3, "Test")

        self.assertEqual(len(cliente.calls), 3)

    def test_no_reintenta_error_no_transitorio(self):
        cliente = make_chat_client([
            FakeAPIError("no", status_code=404),
            ok_chat_response("no debería llegar"),
        ])
        with self.assertRaises(FakeAPIError):
            _chat_completion(cliente, "m", "p", 3, "Test")

        self.assertEqual(len(cliente.calls), 1)

    def test_error_sin_status_reintenta_y_eleva(self):
        cliente = make_chat_client([FakeAPIError("red caída")] * 2)
        errores = io.StringIO()
        with patch("llm_providers.time.sleep"), \
                contextlib.redirect_stderr(errores):
            with self.assertRaises(FakeAPIError):
                _chat_completion(cliente, "m", "p", 2, "Test")

        self.assertEqual(len(cliente.calls), 2)
        self.assertIn("error transitorio (FakeAPIError)", errores.getvalue())


class TestConstructoresExactos(unittest.TestCase):
    def test_openai_valores_por_defecto(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            llm = OpenAILLM()

        self.assertEqual(llm.api_key, "")
        self.assertEqual(llm.model, "gpt-4o-mini")
        self.assertIsNone(llm.base_url)
        self.assertEqual(llm.max_retries, 3)
        self.assertEqual(llm.timeout, 60.0)
        self.assertTrue(llm.use_cache)
        self.assertIsInstance(llm.cache, ResponseCache)
        self.assertEqual(llm._clientes, {})

    def test_openai_sin_cache(self):
        llm = OpenAILLM(api_key="x", use_cache=False)

        self.assertIsNone(llm.cache)

    def test_kilo_valores_por_defecto(self):
        with patch.dict(os.environ, {"KILO_API_KEY": ""}):
            llm = KiloGatewayLLM()

        self.assertEqual(llm.api_key, "")
        self.assertEqual(llm.model, "anthropic/claude-sonnet-4")
        self.assertEqual(llm.base_url, "https://api.kilo.ai/api/gateway")
        self.assertEqual(llm.max_retries, 3)
        self.assertEqual(llm.timeout, 60.0)
        self.assertTrue(llm.use_cache)
        self.assertIsInstance(llm.cache, ResponseCache)
        self.assertEqual(llm._clientes, {})

    def test_openrouter_cadena_y_flag(self):
        llm = OpenRouterLLM(api_key="x")

        self.assertIs(llm._fallback_chain, OPENROUTER_FALLBACK_CHAIN)
        self.assertTrue(llm._use_fallback)
        self.assertEqual(llm.base_url, "https://openrouter.ai/api/v1")
        self.assertFalse(
            OpenRouterLLM(api_key="x", use_fallback=False)._use_fallback)


class TestBackoffYJitter(unittest.TestCase):
    def test_value_error_mensaje_exacto(self):
        cliente = make_chat_client([])

        with self.assertRaises(ValueError) as cm:
            _chat_completion(cliente, "modelo", "p", 0, "Test")

        self.assertEqual(str(cm.exception),
                         "max_retries debe ser >= 1 (recibido 0)")

    def test_el_jitter_se_suma_al_backoff(self):
        cliente = make_chat_client([FakeAPIError("caído", status_code=429),
                                    ok_chat_response("ok")])

        with patch("llm_providers.random.uniform", return_value=0.5), \
                patch("llm_providers.time.sleep") as dormir:
            salida = _chat_completion(cliente, "modelo", "p", 3, "Test")

        self.assertEqual(salida, "ok")
        self.assertEqual(dormir.call_args_list, [call(2.5)])

    def test_backoff_exponencial_en_el_tercer_reintento(self):
        cliente = make_chat_client([FakeAPIError("caído", status_code=429)] * 3
                                   + [ok_chat_response("ok")])

        with patch("llm_providers.random.uniform", return_value=0.0), \
                patch("llm_providers.time.sleep") as dormir:
            salida = _chat_completion(cliente, "modelo", "p", 4, "Test")

        self.assertEqual(salida, "ok")
        self.assertEqual(dormir.call_args_list, [call(2.0), call(4.0), call(8.0)])

    def test_jitter_uniforme_entre_0_y_1(self):
        cliente = make_chat_client([FakeAPIError("caído", status_code=429),
                                    ok_chat_response("ok")])

        with patch("llm_providers.random.uniform", return_value=0.0) as azar, \
                patch("llm_providers.time.sleep"):
            _chat_completion(cliente, "modelo", "p", 3, "Test")

        self.assertEqual(azar.call_args_list, [call(0, 1)])


class TestEtiquetaDelProveedorEnStderr(unittest.TestCase):
    def _stderr_de_reintento(self, llm):
        cliente = make_chat_client([FakeAPIError("caído", status_code=429),
                                    ok_chat_response("ok")])
        errores = io.StringIO()
        with patch("openai.OpenAI", return_value=cliente), \
                patch("llm_providers.random.uniform", return_value=0.0), \
                patch("llm_providers.time.sleep"), \
                contextlib.redirect_stderr(errores):
            salida = llm.generate("p")

        self.assertEqual(salida, "ok")
        return errores.getvalue()

    def test_openai_etiqueta_exacta(self):
        llm = OpenAILLM(api_key="clave-ficticia-de-test")

        self.assertIn("[OpenAILLM] error transitorio (429); reintento 1/2 en 2.0s",
                      self._stderr_de_reintento(llm))

    def test_kilo_etiqueta_exacta(self):
        llm = KiloGatewayLLM(api_key="clave-ficticia-de-test")

        self.assertIn("[KiloGatewayLLM] error transitorio (429); reintento 1/2 en 2.0s",
                      self._stderr_de_reintento(llm))


class TestClavesDesdeEntorno(unittest.TestCase):
    """Ningún assert usa claves reales: valores ficticios o vacíos (P0.6)."""

    def test_openai_sin_variable_clave_vacia(self):
        with patch.dict(os.environ, _entorno_sin("OPENAI_API_KEY"), clear=True):
            llm = OpenAILLM()

        self.assertEqual(llm.api_key, "")

    def test_openai_key_desde_entorno(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "clave-ficticia-de-test"}):
            llm = OpenAILLM()

        self.assertEqual(llm.api_key, "clave-ficticia-de-test")

    def test_openrouter_sin_variable_clave_vacia(self):
        with patch.dict(os.environ, _entorno_sin("OPENROUTER_API_KEY"), clear=True):
            llm = OpenRouterLLM()

        self.assertEqual(llm.api_key, "")

    def test_kilo_sin_variable_clave_vacia(self):
        with patch.dict(os.environ, _entorno_sin("KILO_API_KEY"), clear=True):
            llm = KiloGatewayLLM()

        self.assertEqual(llm.api_key, "")

    def test_kilo_key_desde_entorno(self):
        with patch.dict(os.environ, {"KILO_API_KEY": "clave-ficticia-de-test"}):
            llm = KiloGatewayLLM()

        self.assertEqual(llm.api_key, "clave-ficticia-de-test")

    def test_deepseek_sin_variable_clave_vacia(self):
        with patch.dict(os.environ,
                        _entorno_sin("DEEPSEEK_API_KEY", "OPENAI_API_KEY"),
                        clear=True):
            llm = DeepSeekLLM()

        self.assertEqual(llm.api_key, "")


class TestMensajesDeErrorExactos(unittest.TestCase):
    def test_openai_sin_key_mensaje_exacto(self):
        with patch.dict(os.environ, _entorno_sin("OPENAI_API_KEY"), clear=True):
            llm = OpenAILLM()
            with self.assertRaises(ValueError) as cm:
                llm.generate("hola")

        self.assertEqual(str(cm.exception),
                         "OpenAI API key required. "
                         "Provide api_key or set OPENAI_API_KEY.")

    def test_kilo_sin_key_mensaje_exacto(self):
        with patch.dict(os.environ, _entorno_sin("KILO_API_KEY"), clear=True):
            llm = KiloGatewayLLM()
            with self.assertRaises(ValueError) as cm:
                llm.generate("hola")

        self.assertEqual(str(cm.exception),
                         "Kilo API key required for KiloGatewayLLM. "
                         "Provide api_key parameter or set KILO_API_KEY "
                         "environment variable.")


class TestKiloGenerateDetalle(unittest.TestCase):
    def test_api_key_kwarg_sobreescribe_la_del_cliente(self):
        cliente = make_chat_client([ok_chat_response("ok")])
        llm = KiloGatewayLLM(api_key="clave-del-cliente")

        with patch("openai.OpenAI", return_value=cliente) as fabrica:
            llm.generate("p", api_key="clave-en-kwargs")

        fabrica.assert_called_once_with(
            api_key="clave-en-kwargs",
            base_url="https://api.kilo.ai/api/gateway")

    def test_el_prompt_llega_al_cliente(self):
        cliente = make_chat_client([ok_chat_response("ok")])
        llm = KiloGatewayLLM(api_key="clave-ficticia-de-test")

        with patch("openai.OpenAI", return_value=cliente):
            llm.generate("prompt kilo")

        self.assertEqual(cliente.calls[0]["messages"],
                         [{"role": "user", "content": "prompt kilo"}])

    def test_timeout_configurable_llega_a_la_peticion(self):
        cliente = make_chat_client([ok_chat_response("ok")])
        llm = KiloGatewayLLM(api_key="clave-ficticia-de-test", timeout=2.5)

        with patch("openai.OpenAI", return_value=cliente):
            llm.generate("p")

        self.assertEqual(cliente.calls[0]["timeout"], 2.5)


class TestOpenRouterGenerateDetalle(unittest.TestCase):
    def test_modelo_explicito_pasa_prompt_y_kwargs(self):
        cliente = make_chat_client([ok_chat_response("ok")])
        llm = OpenRouterLLM(api_key="clave-ficticia-de-test")

        with patch("openai.OpenAI", return_value=cliente) as fabrica:
            llm.generate("prompt explicito", model="otro/modelo:free",
                         api_key="otra-clave-ficticia")

        fabrica.assert_called_once_with(
            api_key="otra-clave-ficticia",
            base_url="https://openrouter.ai/api/v1")
        self.assertEqual(cliente.calls[0]["messages"],
                         [{"role": "user", "content": "prompt explicito"}])
        self.assertEqual(cliente.calls[0]["model"], "otro/modelo:free")

    def test_sin_fallback_pasa_prompt_y_kwargs(self):
        cliente = make_chat_client([ok_chat_response("ok")])
        llm = OpenRouterLLM(api_key="clave-ficticia-de-test", use_fallback=False)

        with patch("openai.OpenAI", return_value=cliente) as fabrica:
            llm.generate("prompt sin fallback", api_key="otra-clave-ficticia")

        fabrica.assert_called_once_with(
            api_key="otra-clave-ficticia",
            base_url="https://openrouter.ai/api/v1")
        self.assertEqual(cliente.calls[0]["messages"],
                         [{"role": "user", "content": "prompt sin fallback"}])
        self.assertEqual(cliente.calls[0]["model"], llm.model)

    def test_fallback_pasa_los_kwargs(self):
        cliente = make_chat_client([ok_chat_response("ok")])
        llm = OpenRouterLLM(api_key="clave-ficticia-de-test")

        with patch("openai.OpenAI", return_value=cliente) as fabrica:
            llm.generate("p", api_key="otra-clave-ficticia")

        fabrica.assert_called_once_with(
            api_key="otra-clave-ficticia",
            base_url="https://openrouter.ai/api/v1")

    def test_primer_modelo_ok_no_imprime_nada(self):
        cliente = make_chat_client([ok_chat_response("ok")])
        llm = OpenRouterLLM(api_key="clave-ficticia-de-test")
        errores = io.StringIO()

        with patch("openai.OpenAI", return_value=cliente), \
                contextlib.redirect_stderr(errores):
            llm.generate("p")

        self.assertEqual(errores.getvalue(), "")

    def test_fallback_anuncia_el_modelo_en_stderr(self):
        cliente = make_chat_client([FakeAPIError("no", status_code=404),
                                    ok_chat_response("ok")])
        llm = OpenRouterLLM(api_key="clave-ficticia-de-test",
                            model="modelo-a:free")
        errores = io.StringIO()

        with patch("openai.OpenAI", return_value=cliente), \
                contextlib.redirect_stderr(errores):
            salida = llm.generate("p")

        self.assertEqual(salida, "ok")
        self.assertIn("[OpenRouterLLM] Fallback a modelo: "
                      + OPENROUTER_FALLBACK_CHAIN[0], errores.getvalue())

    def test_error_sin_atributo_status_eleva_el_original(self):
        cliente = make_chat_client([ConnectionError("red caída")] * 3)
        llm = OpenRouterLLM(api_key="clave-ficticia-de-test")

        with patch("openai.OpenAI", return_value=cliente), \
                patch("llm_providers.time.sleep"):
            with self.assertRaises(ConnectionError):
                llm.generate("p")

        self.assertEqual(len(cliente.calls), 3)

    def test_430_no_transitorio_hace_fallback(self):
        cliente = make_chat_client([FakeAPIError("no", status_code=430),
                                    ok_chat_response("ok")])
        llm = OpenRouterLLM(api_key="clave-ficticia-de-test",
                            model="modelo-a:free")

        with patch("openai.OpenAI", return_value=cliente):
            salida = llm.generate("p")

        self.assertEqual(salida, "ok")
        self.assertEqual([c["model"] for c in cliente.calls],
                         ["modelo-a:free", OPENROUTER_FALLBACK_CHAIN[0]])

    def test_501_hace_fallback(self):
        cliente = make_chat_client([FakeAPIError("no", status_code=501),
                                    ok_chat_response("ok")])
        llm = OpenRouterLLM(api_key="clave-ficticia-de-test",
                            model="modelo-a:free")

        with patch("openai.OpenAI", return_value=cliente):
            salida = llm.generate("p")

        self.assertEqual(salida, "ok")
        self.assertEqual([c["model"] for c in cliente.calls],
                         ["modelo-a:free", OPENROUTER_FALLBACK_CHAIN[0]])

    def test_505_hace_fallback(self):
        cliente = make_chat_client([FakeAPIError("no", status_code=505),
                                    ok_chat_response("ok")])
        llm = OpenRouterLLM(api_key="clave-ficticia-de-test",
                            model="modelo-a:free")

        with patch("openai.OpenAI", return_value=cliente):
            salida = llm.generate("p")

        self.assertEqual(salida, "ok")
        self.assertEqual([c["model"] for c in cliente.calls],
                         ["modelo-a:free", OPENROUTER_FALLBACK_CHAIN[0]])

    def test_502_tras_agotar_reintentos_eleva_sin_fallback(self):
        cliente = make_chat_client([FakeAPIError("no", status_code=502)] * 3
                                   + [ok_chat_response("no debería llegar")])
        llm = OpenRouterLLM(api_key="clave-ficticia-de-test",
                            model="modelo-a:free")

        with patch("openai.OpenAI", return_value=cliente), \
                patch("llm_providers.time.sleep"):
            with self.assertRaises(FakeAPIError):
                llm.generate("p")

        self.assertEqual(len(cliente.calls), 3)

    def test_503_tras_agotar_reintentos_eleva_sin_fallback(self):
        cliente = make_chat_client([FakeAPIError("no", status_code=503)] * 3
                                   + [ok_chat_response("no debería llegar")])
        llm = OpenRouterLLM(api_key="clave-ficticia-de-test",
                            model="modelo-a:free")

        with patch("openai.OpenAI", return_value=cliente), \
                patch("llm_providers.time.sleep"):
            with self.assertRaises(FakeAPIError):
                llm.generate("p")

        self.assertEqual(len(cliente.calls), 3)


class TestOllamaGenerateDetalle(unittest.TestCase):
    def _respuesta(self, payload):
        resp = type("R", (), {})()
        resp.raise_for_status = lambda: None
        resp.json = lambda: payload
        return resp

    def test_payload_y_timeout_exactos(self):
        with patch("requests.post",
                   return_value=self._respuesta({"response": "texto"})) as post:
            salida = OllamaLLM().generate("prompt ollama")

        self.assertEqual(salida, "texto")
        post.assert_called_once_with(
            "http://localhost:11434/api/generate",
            json={"model": "llama3.2", "prompt": "prompt ollama",
                  "stream": False},
            timeout=120)

    def test_sin_campo_response_devuelve_cadena_vacia(self):
        with patch("requests.post", return_value=self._respuesta({})):
            salida = OllamaLLM().generate("p")

        self.assertEqual(salida, "")


class TestMockLLMDetalle(unittest.TestCase):
    def test_model_por_defecto_y_personalizado(self):
        self.assertEqual(MockLLM().model, "mock-llm")
        self.assertEqual(MockLLM(model="otro-modelo").model, "otro-modelo")

    def test_json_de_claims_no_escapa_unicode(self):
        self.assertIn("Afirmación simulada",
                      MockLLM().generate("extract factual claims"))

    def test_json_de_evaluacion_no_escapa_unicode(self):
        self.assertIn("Evaluación simulada",
                      MockLLM().generate("evaluate this claim"))

    def test_json_de_evaluador_experto_no_escapa_unicode(self):
        self.assertIn("Evaluación simulada",
                      MockLLM().generate("evaluador experto"))


if __name__ == "__main__":
    unittest.main()
