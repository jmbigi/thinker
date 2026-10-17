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
                           KiloGatewayLLM, OpenAILLM, OpenRouterLLM,
                           ResponseCache, _chat_completion)
from tests.helpers import FakeAPIError, make_chat_client, ok_chat_response


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


if __name__ == "__main__":
    unittest.main()
