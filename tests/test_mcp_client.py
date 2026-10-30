"""Pruebas del cliente MCP con servidores locales simulados, sin red."""

import sys
import tempfile
import unittest
from pathlib import Path

from mcp_client import MCPStdioClient, MCPSearchAPI


_SERVIDOR = r'''
import json
import sys
import time

MODO = "MODO_PLACEHOLDER"

def enviar(mensaje):
    sys.stdout.write(json.dumps(mensaje) + "\n")
    sys.stdout.flush()

for linea in sys.stdin:
    mensaje = json.loads(linea)
    metodo = mensaje.get("method")
    if MODO == "sleep" and metodo == "initialize":
        time.sleep(5)
    if metodo == "initialize":
        enviar({"jsonrpc": "2.0", "id": mensaje["id"], "result": {
            "protocolVersion": "1900-01-01" if MODO == "version" else "2025-06-18",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "fake", "version": "1"},
        }})
    elif metodo == "tools/list":
        enviar({"jsonrpc": "2.0", "id": mensaje["id"], "result": {
            "tools": [{"name": "search", "description": "fake"}]}})
    elif metodo == "tools/call":
        if MODO == "error":
            enviar({"jsonrpc": "2.0", "id": mensaje["id"], "result": {
                "isError": True, "content": [{"type": "text", "text": "fallo"}]}})
        elif MODO == "big":
            enviar({"jsonrpc": "2.0", "id": mensaje["id"], "result": {
                "structuredContent": {"results": [{"title": "x" * 5000}]}}})
        else:
            enviar({"jsonrpc": "2.0", "id": mensaje["id"], "result": {
                "structuredContent": {"results": [
                    {"title": "A", "url": "https://example.com/a", "snippet": "Solar"},
                    {"title": "B", "url": "http://127.0.0.1/b", "snippet": "Privado"},
                ]}}})
'''


class TestMCP(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)

    def _comando(self, modo="ok"):
        ruta = self.raiz / f"{modo}.py"
        ruta.write_text(_SERVIDOR.replace("MODO_PLACEHOLDER", modo), encoding="utf-8")
        return [sys.executable, str(ruta)]

    def test_busqueda_estructurada_y_validacion_urls(self):
        api = MCPSearchAPI(self._comando(), timeout=2)
        resultados = api.search("solar", 5)
        self.assertEqual(len(resultados), 1)
        self.assertEqual(resultados[0]["url"], "https://example.com/a")
        self.assertEqual(resultados[0]["source"], "mcp")

    def test_allowlist_y_listado_herramientas(self):
        with MCPStdioClient(self._comando(), timeout=2, allowed_tools={"search"}) as cliente:
            self.assertEqual(len(cliente.list_tools()), 1)
            with self.assertRaises(PermissionError):
                cliente.call_tool("delete_all", {})
            with self.assertRaises(RuntimeError):
                cliente.initialize()

    def test_version_no_soportada_cierra_proceso(self):
        with self.assertRaisesRegex(RuntimeError, "no soportada"):
            with MCPStdioClient(self._comando("version"), timeout=2):
                pass

    def test_timeout_es_fallo_acotado(self):
        with self.assertRaises(TimeoutError):
            with MCPStdioClient(self._comando("sleep"), timeout=0.05):
                pass

    def test_limite_de_salida(self):
        with self.assertRaisesRegex(RuntimeError, "demasiado grande|transporte"):
            with MCPStdioClient(self._comando("big"), timeout=2, max_output_bytes=100):
                pass

    def test_is_error_se_eleva(self):
        with MCPStdioClient(self._comando("error"), timeout=2) as cliente:
            with self.assertRaisesRegex(RuntimeError, "isError"):
                cliente.call_tool("search", {})

    def test_comando_no_es_shell(self):
        with self.assertRaises(TypeError):
            with MCPStdioClient("python fake.py && borrar"):
                pass


if __name__ == "__main__":
    unittest.main()
