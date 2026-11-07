"""Contrato offline del plugin Olla (proxy local OpenAI-compatible).

Usa un servidor HTTP local mínimo: no requiere Olla instalado ni red externa.
Verifica las rutas reales de Olla (`/internal/health` y `/olla/proxy/v1/...`).
"""

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from plugins.interfaces import PluginConfig
from plugins.llm_providers.olla_plugin import OllaPlugin


class _Handler(BaseHTTPRequestHandler):
    health_status = 200
    modelos = ["qwen3:8b"]

    def _json(self, status, payload):
        cuerpo = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        if self.path == "/internal/health":
            if self.health_status != 200:
                self._json(self.health_status, {"status": "down"})
            else:
                self._json(200, {"status": "healthy"})
        elif self.path == "/olla/proxy/v1/models":
            self._json(200, {"object": "list", "data": [
                {"id": m, "object": "model"} for m in self.modelos]})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/olla/proxy/v1/chat/completions":
            self._json(404, {"error": "not found"})
            return
        largo = int(self.headers.get("Content-Length", 0))
        cuerpo = json.loads(self.rfile.read(largo) or b"{}")
        self._json(200, {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "created": 0,
            "model": cuerpo.get("model", "qwen3:8b"),
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": "respuesta-olla"},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 1, "completion_tokens": 2,
                      "total_tokens": 3},
        })

    def log_message(self, format, *args):
        pass


class TestOllaPlugin(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        cls.hilo = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.hilo.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.hilo.join(timeout=2)

    def setUp(self):
        _Handler.health_status = 200
        _Handler.modelos = ["qwen3:8b"]
        self.plugin = OllaPlugin(PluginConfig(params={
            "base_url": self.base_url,
            "model": "",
            "timeout": 10,
            "max_retries": 1,
            "use_cache": False,
            "health_check_interval": 0,
        }))

    def test_initialize_lee_el_catalogo_y_genera(self):
        self.assertTrue(self.plugin.initialize(), self.plugin.metadata.error_message)
        self.assertEqual(self.plugin.get_available_models(), ["qwen3:8b"])
        self.assertEqual(self.plugin.generate("hola"), "respuesta-olla")
        self.assertEqual(self.plugin.metadata.usage_count, 1)
        self.assertEqual(self.plugin.estimate_cost("hola"), 0.0)

    def test_health_no_200_falla_de_forma_visible(self):
        _Handler.health_status = 503
        self.assertFalse(self.plugin.initialize())
        self.assertIn("health check", self.plugin.metadata.error_message)

    def test_sin_modelos_y_sin_modelo_configurado_falla(self):
        _Handler.modelos = []
        self.assertFalse(self.plugin.initialize())
        self.assertIn("no anuncia modelos", self.plugin.metadata.error_message)

    def test_olla_inalcanzable_falla_de_forma_visible(self):
        plugin = OllaPlugin(PluginConfig(params={
            "base_url": "http://127.0.0.1:1",
            "timeout": 1,
        }))
        self.assertFalse(plugin.initialize())
        self.assertTrue(plugin.metadata.error_message)


if __name__ == "__main__":
    unittest.main()
