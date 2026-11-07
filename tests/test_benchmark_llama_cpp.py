"""Contrato offline del benchmark de llama.cpp/Ollama/Olla.

No necesita servidores reales: usa un HTTP local mínimo para comprobar el
parseo de tiempos y las rutas de cada backend.
"""

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from scripts import benchmark_llama_cpp as bench


class _Handler(BaseHTTPRequestHandler):
    def _json(self, payload):
        cuerpo = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_POST(self):
        largo = int(self.headers.get("Content-Length", 0))
        self.rfile.read(largo)
        if self.path == "/api/generate":
            self._json({
                "eval_count": 10,
                "eval_duration": 1_000_000_000,
                "total_duration": 2_000_000_000,
            })
        elif self.path == "/olla/proxy/v1/chat/completions":
            self._json({"usage": {"completion_tokens": 10}})
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


class TestBenchmark(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        cls.hilo = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.hilo.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.hilo.join(timeout=2)

    def test_ollama_parsea_tokens_y_ttft(self):
        resultado = bench.OllamaBench(self.base).benchmark(
            "qwen3:8b", "hola", max_tokens=8, n_runs=1)
        self.assertAlmostEqual(resultado.gen_tps, 10.0)
        self.assertAlmostEqual(resultado.ttft_ms, 1000.0)
        self.assertEqual(resultado.backend, "ollama")

    def test_olla_usa_la_ruta_proxy_real(self):
        linea = bench.OllaBench(f"{self.base}/olla/proxy/v1")
        resultado = linea.benchmark("qwen3:8b", "hola", max_tokens=8, n_runs=1)
        self.assertGreater(resultado.gen_tps, 0)
        self.assertEqual(resultado.backend, "olla")

    def test_backend_desconocido_falla(self):
        with self.assertRaises(ValueError):
            bench.run_benchmark("inexistente", "modelo")

    def test_to_dict_conserva_campos(self):
        resultado = bench.BenchmarkResult(backend="ollama", model="m", config={})
        datos = resultado.to_dict()
        self.assertEqual(datos["backend"], "ollama")
        self.assertIn("gen_tps", datos)


if __name__ == "__main__":
    unittest.main()
