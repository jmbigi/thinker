"""Contrato común de los proveedores LLM (offline: clientes dobles, sin red).

Cada proveedor debe exponer `generate` y `model`; los OpenAI-compatibles
normalizan igual los errores (no transitorio = 1 intento; transitorio = agota
`max_retries` y eleva el último); Ollama no reintenta y no usa caché; MockLLM
es determinista y no depende del entorno.
"""

import os
import unittest
from unittest.mock import patch

from llm_providers import (DeepSeekLLM, KiloGatewayLLM, MockLLM, OllamaLLM,
                           OpenAILLM, OpenRouterLLM)
from tests.helpers import FakeAPIError, make_chat_client, ok_chat_response


def _openai_compatibles():
    return [OpenAILLM, DeepSeekLLM, KiloGatewayLLM]


class TestInterfazComun(unittest.TestCase):
    def test_todos_exponen_generate_y_model(self):
        proveedores = [MockLLM(), OllamaLLM()] + [
            clase(api_key="k") for clase in _openai_compatibles()]
        proveedores.append(OpenRouterLLM(api_key="k", use_fallback=False))
        for proveedor in proveedores:
            with self.subTest(proveedor=type(proveedor).__name__):
                self.assertTrue(callable(proveedor.generate))
                self.assertIsInstance(proveedor.model, str)
                self.assertTrue(proveedor.model)

    def test_deepseek_es_un_openai_compatible(self):
        self.assertTrue(issubclass(DeepSeekLLM, OpenAILLM))


class TestErroresNormalizados(unittest.TestCase):
    def test_error_no_transitorio_no_se_reintenta(self):
        for clase in _openai_compatibles():
            with self.subTest(proveedor=clase.__name__):
                cliente = make_chat_client([FakeAPIError("no", status_code=404)])
                llm = clase(api_key="k")
                with patch("openai.OpenAI", return_value=cliente):
                    with self.assertRaises(FakeAPIError):
                        llm.generate("hola")
                self.assertEqual(len(cliente.calls), 1)

    def test_error_transitorio_agota_reintentos_y_eleva_el_ultimo(self):
        for clase in _openai_compatibles():
            with self.subTest(proveedor=clase.__name__):
                cliente = make_chat_client(
                    [FakeAPIError("503-1", status_code=503),
                     FakeAPIError("503-2", status_code=503),
                     FakeAPIError("503-3", status_code=503)])
                llm = clase(api_key="k", max_retries=3)
                with patch("openai.OpenAI", return_value=cliente), \
                        patch("time.sleep"):
                    with self.assertRaises(FakeAPIError) as ctx:
                        llm.generate("hola")
                self.assertEqual(str(ctx.exception), "503-3")
                self.assertEqual(len(cliente.calls), 3)


class TestOllamaSinReintentos(unittest.TestCase):
    def test_una_sola_llamada_y_respuesta_sin_response_es_vacia(self):
        with patch("requests.post") as post:
            post.return_value.json.return_value = {}
            self.assertEqual(OllamaLLM().generate("hola"), "")
        self.assertEqual(post.call_count, 1)
        assert post.call_args.kwargs["timeout"] > 0

    def test_devuelve_el_campo_response(self):
        with patch("requests.post") as post:
            post.return_value.json.return_value = {"response": "eco"}
            self.assertEqual(OllamaLLM().generate("hola"), "eco")


class TestMockDeterminista(unittest.TestCase):
    def test_dos_llamadas_iguales_y_sin_entorno(self):
        llm = MockLLM()
        with patch.dict(os.environ, {}, clear=True):
            primera = llm.generate("decompose this into sub-questions")
            segunda = llm.generate("decompose this into sub-questions")
        self.assertEqual(primera, segunda)
        self.assertTrue(primera)

    def test_una_respuesta_correcta_no_reintenta(self):
        cliente = make_chat_client([ok_chat_response("hola")])
        llm = OpenAILLM(api_key="k")
        with patch("openai.OpenAI", return_value=cliente):
            self.assertEqual(llm.generate("p"), "hola")
        self.assertEqual(len(cliente.calls), 1)


if __name__ == "__main__":
    unittest.main()
