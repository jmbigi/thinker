"""Pruebas de regresión para FlywheelGatewayLLM.

Aseguran que el provider usa /v1/responses (OpenAI Responses API) en lugar
de /v1/chat/completions, que no está soportado por el gateway (devuelve
AUTH_REQUIRED 401). Todo offline, sin red ni API keys.
"""

import os
import unittest
from unittest.mock import Mock, patch

from llm_providers import FlywheelGatewayLLM


def _respuesta_responses_api(texto: str) -> dict:
    """Construye un dict con el formato de respuesta de la Responses API."""
    return {
        "output": [
            {
                "type": "message",
                "content": [{"type": "text", "text": texto}],
            }
        ]
    }


def _mock_response(payload: dict, status_code: int = 200):
    """Crea un Mock que simula la respuesta HTTP de requests.post."""
    mock = Mock()
    mock.status_code = status_code
    mock.raise_for_status.return_value = None
    mock.json.return_value = payload
    return mock


class TestFlywheelGatewayLlm(unittest.TestCase):
    """Verificaciones de contratos offline para FlywheelGatewayLLM."""

    def test_usa_responses_no_chat_completions(self):
        """generate llama a /v1/responses y no a /v1/chat/completions."""
        with patch("requests.post") as post:
            post.return_value = _mock_response(_respuesta_responses_api("ok"))
            llm = FlywheelGatewayLLM(api_key="fwk_test", model="openrouter/test-model")
            llm.generate("Hola")

        self.assertEqual(post.call_count, 1)
        # requests.post se llama con url como primer argumento posicional
        url = post.call_args.args[0]
        self.assertIn("/responses", url,
                      f"Debe llamar a /v1/responses pero fue a {url}")
        self.assertNotIn("/chat/completions", url,
                         "No debe llamar a /v1/chat/completions (401 AUTH_REQUIRED)")

    def test_payload_responses_api_format(self):
        """El payload usa 'input' (Responses API), no 'messages' (Chat API)."""
        with patch("requests.post") as post:
            post.return_value = _mock_response(_respuesta_responses_api("ok"))
            llm = FlywheelGatewayLLM(api_key="fwk_test", model="openrouter/test-model")
            llm.generate("Hola, ¿cómo estás?")

        # requests.post se llama con json= como kwarg
        payload = post.call_args.kwargs["json"]
        self.assertIn("input", payload)
        self.assertNotIn("messages", payload,
                         "El formato Responses API usa 'input', no 'messages'")

    def test_extrae_texto_de_responses(self):
        """_extraer_texto obtiene el texto de output[].content[].text."""
        data = _respuesta_responses_api("Texto extraído de gateway")
        self.assertEqual(FlywheelGatewayLLM._extraer_texto(data),
                         "Texto extraído de gateway")

    def test_fallback_a_choices(self):
        """Fallback a formato chat completions si output no está presente."""
        data = {"choices": [{"message": {"content": "Fallback texto"}}]}
        self.assertEqual(FlywheelGatewayLLM._extraer_texto(data), "Fallback texto")

    def test_falta_clave_lanza_valueerror(self):
        """Sin clave, generate eleva ValueError con mensaje claro."""
        with patch.dict(os.environ, {"FLYWHEEL_GATEWAY_KEY": ""}, clear=True):
            llm = FlywheelGatewayLLM(api_key="", model="test")
            with self.assertRaises(ValueError) as ctx:
                llm.generate("hola")
        self.assertIn("Falta la clave del Flywheel Gateway", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()