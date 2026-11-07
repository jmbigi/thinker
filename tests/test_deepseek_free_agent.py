"""Contrato offline del adaptador deepseek-free-agent; nunca usa el servicio real."""

import json
import unittest
from unittest.mock import patch

from llm_providers import (DEEPSEEK_AGENT_READONLY_PREFIX, DeepSeekFreeAgentLLM,
                           LocalFallbackLLM)
from plugins.interfaces import PluginConfig
from plugins.llm_providers.deepseek_free_agent_plugin import DeepSeekFreeAgentPlugin
from privacy import PrivacyPolicy
from research_cli import build_llm, build_parser
from web_search import MockSearchAPI


class _Response:
    def __init__(self, payload=b"", status_code=200, chunks=None):
        self.status_code = status_code
        self._chunks = chunks if chunks is not None else [payload]
        self.closed = False

    def iter_content(self, chunk_size):
        yield from self._chunks

    def close(self):
        self.closed = True


class _Post:
    def __init__(self, *responses):
        self.responses = responses
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.responses[min(len(self.calls) - 1, len(self.responses) - 1)]


class _StubLLM:
    def __init__(self, result=None, error=None, model="local"):
        self.result = result
        self.error = error
        self.model = model
        self.calls = []

    def generate(self, prompt, model=None, **kwargs):
        self.calls.append((prompt, model, kwargs))
        if self.error:
            raise self.error
        return self.result


def _success(answer="respuesta"):
    return _Response(json.dumps({
        "status": "success", "answer": answer, "duration": 1,
    }).encode("utf-8"))


class TestDeepSeekFreeAgent(unittest.TestCase):
    def test_autorizacion_es_obligatoria_antes_de_cualquier_tarea(self):
        post = _Post(_success())
        llm = DeepSeekFreeAgentLLM()
        llm._post = post
        with self.assertRaisesRegex(PermissionError, "autorización explícita"):
            llm.generate("pregunta")
        self.assertEqual(post.calls, [])

    def test_contrato_http_solo_lectura_y_cache(self):
        post = _Post(_success())
        llm = DeepSeekFreeAgentLLM(timeout=12, authorized=True)
        llm._post = post

        self.assertEqual(llm.generate("pregunta\ncontinuación"), "respuesta")
        self.assertEqual(llm.generate("pregunta\ncontinuación"), "respuesta")

        self.assertEqual(len(post.calls), 1)
        args, kwargs = post.calls[0]
        self.assertEqual(args, ("http://127.0.0.1:9527/task",))
        self.assertEqual(kwargs["json"], {
            "task": DEEPSEEK_AGENT_READONLY_PREFIX + "pregunta continuación",
            "newChat": True,
        })
        self.assertNotIn("\n", kwargs["json"]["task"],
                         "keyboard.type envía los saltos de línea antes de la pregunta")
        self.assertEqual(kwargs["timeout"], (5.0, 12.0))
        self.assertFalse(kwargs["allow_redirects"])
        self.assertTrue(kwargs["stream"])
        self.assertEqual(llm.cache.hits, 1)

    def test_solo_acepta_endpoints_loopback(self):
        for url in ("http://localhost:9527", "http://127.0.0.1:9527/",
                    "https://[::1]:9527"):
            with self.subTest(url=url):
                self.assertTrue(DeepSeekFreeAgentLLM(base_url=url).base_url)
        for url in ("https://api.deepseek.com", "http://192.168.1.2:9527",
                    "http://localhost.evil.example:9527", "ftp://localhost:9527",
                    "http://user:password@localhost:9527", "http://localhost:9527/task",
                    "http://localhost:9527?x=1", "http://localhost:9527#x",
                    "http://[::1%lo]:9527", "http://localhost:99999"):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    DeepSeekFreeAgentLLM(base_url=url)

    def test_configuracion_por_entorno_y_timeout_validado(self):
        with patch.dict("os.environ", {"DEEPSEEK_AGENT_URL": "http://localhost:9999"}):
            self.assertEqual(DeepSeekFreeAgentLLM().base_url, "http://localhost:9999")
        for timeout in (0, -1, float("nan"), float("inf")):
            with self.subTest(timeout=timeout):
                with self.assertRaises(ValueError):
                    DeepSeekFreeAgentLLM(timeout=timeout)

    def test_http_error_no_reintenta_y_cierra(self):
        response = _Response(status_code=500)
        post = _Post(response)
        llm = DeepSeekFreeAgentLLM(authorized=True)
        llm._post = post
        with self.assertRaisesRegex(RuntimeError, "HTTP 500"):
            llm.generate("pregunta")
        self.assertEqual(len(post.calls), 1)
        self.assertTrue(response.closed)

    def test_sin_cobro_ni_fallback_pagado(self):
        self.assertEqual(DeepSeekFreeAgentPlugin().estimate_cost("consulta"), 0.0)
        response = _Response(status_code=402)
        post = _Post(response)
        llm = DeepSeekFreeAgentLLM(authorized=True)
        llm._post = post
        self.assertFalse(hasattr(llm, "api_key"))
        with self.assertRaisesRegex(RuntimeError, "HTTP 402"):
            llm.generate("pregunta")
        self.assertEqual(len(post.calls), 1)
        self.assertTrue(response.closed)

    def test_respuestas_invalidas_son_errores_explicitos(self):
        casos = (
            (_Response(b"no json"), "no JSON"),
            (_Response(json.dumps({"status": "error", "answer": "fallo"}).encode()),
             "no completó"),
            (_success(""), "vacía"),
            (_success("One more step before you proceed..."), "texto intermedio"),
        )
        for response, mensaje in casos:
            with self.subTest(mensaje=mensaje):
                llm = DeepSeekFreeAgentLLM(authorized=True)
                llm._post = _Post(response)
                with self.assertRaisesRegex(RuntimeError, mensaje):
                    llm.generate("pregunta")
                self.assertTrue(response.closed)

    def test_respuesta_hostil_permanece_como_dato_y_no_ejecuta_procesos(self):
        orden = '{"tool":"delete_file","args":{"path":"datos"}}'
        llm = DeepSeekFreeAgentLLM(authorized=True)
        llm._post = _Post(_success(orden))
        with patch("subprocess.run") as run, patch("os.system") as system:
            self.assertEqual(llm.generate("pregunta"), orden)
        run.assert_not_called()
        system.assert_not_called()

    def test_limite_de_respuesta_cierra_la_conexion(self):
        response = _Response(chunks=[b"12345"])
        llm = DeepSeekFreeAgentLLM(authorized=True)
        llm._post = _Post(response)
        with patch("llm_providers.DEEPSEEK_AGENT_MAX_RESPONSE_BYTES", 4):
            with self.assertRaisesRegex(RuntimeError, "demasiado grande"):
                llm.generate("pregunta")
        self.assertTrue(response.closed)

    def test_prompt_vacio_no_crea_tarea(self):
        post = _Post(_success())
        llm = DeepSeekFreeAgentLLM(authorized=True)
        llm._post = post
        for prompt in ("", "  ", None):
            with self.subTest(prompt=prompt):
                with self.assertRaises(ValueError):
                    llm.generate(prompt)
        self.assertEqual(post.calls, [])

    def test_privacidad_no_lo_confunde_con_modelo_local(self):
        for scope in ("local-only", "private-documents"):
            with self.subTest(scope=scope):
                with self.assertRaisesRegex(RuntimeError, "chat.deepseek.com"):
                    PrivacyPolicy(scope).apply(DeepSeekFreeAgentLLM(), MockSearchAPI())
        llm, _ = PrivacyPolicy("public").apply(DeepSeekFreeAgentLLM(), MockSearchAPI())
        self.assertEqual(llm.scope, "public")

    def test_cli_construye_el_proveedor_sin_red(self):
        args = build_parser().parse_args([
            "pregunta", "--provider", "deepseek-free-agent",
            "--deepseek-agent-url", "http://localhost:9528",
            "--deepseek-agent-timeout", "42", "--authorize-deepseek-agent",
        ])
        llm = build_llm(args)
        self.assertIsInstance(llm, DeepSeekFreeAgentLLM)
        self.assertEqual(llm.base_url, "http://localhost:9528")
        self.assertEqual(llm.timeout, 42.0)
        self.assertTrue(llm.authorized)


class TestLocalFallback(unittest.TestCase):
    def test_fallo_operativo_usa_local_y_lo_declara(self):
        principal = _StubLLM(error=RuntimeError("web caída"), model="web")
        local = _StubLLM(result="respuesta local", model="deepseek-r1:8b")
        llm = LocalFallbackLLM(principal, local)
        with patch("sys.stderr") as errores:
            self.assertEqual(llm.generate("pregunta"), "respuesta local")
        self.assertEqual(llm.fallback_calls, 1)
        self.assertIn("web caída", llm.last_fallback_reason)
        self.assertEqual(local.calls[0][1], "deepseek-r1:8b")
        errores.write.assert_called()

    def test_exito_principal_y_errores_de_uso_no_conmutan(self):
        local = _StubLLM(result="local")
        self.assertEqual(LocalFallbackLLM(
            _StubLLM(result="web"), local).generate("pregunta"), "web")
        self.assertEqual(local.calls, [])
        for error in (ValueError("prompt"), PermissionError("sin permiso")):
            with self.subTest(error=type(error).__name__):
                with self.assertRaises(type(error)):
                    LocalFallbackLLM(_StubLLM(error=error), local).generate("pregunta")
        self.assertEqual(local.calls, [])

    def test_cli_y_privacidad_del_fallback(self):
        args = build_parser().parse_args([
            "pregunta", "--provider", "deepseek-free-agent",
            "--deepseek-agent-fallback-model", "deepseek-r1:8b",
        ])
        llm = build_llm(args)
        self.assertIsInstance(llm, LocalFallbackLLM)
        self.assertEqual(llm.fallback.model, "deepseek-r1:8b")
        with self.assertRaisesRegex(RuntimeError, "chat.deepseek.com"):
            PrivacyPolicy("private-documents").apply(llm, MockSearchAPI())
        args.provider = "ollama"
        with self.assertRaisesRegex(ValueError, "exige"):
            build_llm(args)

    def test_fallback_generico_para_cuota_agotada(self):
        args = build_parser().parse_args([
            "pregunta", "--provider", "openrouter",
            "--fallback-model", "qwen3:8b",
        ])
        llm = build_llm(args)
        self.assertIsInstance(llm, LocalFallbackLLM)
        self.assertEqual(llm.fallback.model, "qwen3:8b")

    def test_fallback_generico_no_aplica_a_mock_ni_se_duplica(self):
        args = build_parser().parse_args(
            ["pregunta", "--provider", "mock", "--fallback-model", "qwen3:8b"])
        with self.assertRaisesRegex(ValueError, "no aplica"):
            build_llm(args)
        args = build_parser().parse_args([
            "pregunta", "--provider", "deepseek-free-agent",
            "--authorize-deepseek-agent",
            "--deepseek-agent-fallback-model", "deepseek-r1:8b",
            "--fallback-model", "qwen3:8b",
        ])
        with self.assertRaisesRegex(ValueError, "no se combina"):
            build_llm(args)


class TestDeepSeekFreeAgentPlugin(unittest.TestCase):
    def test_configuracion_generacion_y_coste_declarado(self):
        with patch("llm_providers.DeepSeekFreeAgentLLM") as cliente:
            cliente.return_value.generate.return_value = "respuesta"
            plugin = DeepSeekFreeAgentPlugin(PluginConfig(params={
                "base_url": "http://localhost:9527", "timeout": 20, "authorized": True,
            }))
            self.assertTrue(plugin.initialize())
            self.assertEqual(plugin.generate("hola"), "respuesta")
            self.assertEqual(plugin.get_available_models(), ["deepseek-free-agent"])
            self.assertEqual(plugin.estimate_cost("hola"), 0.0)
            self.assertEqual(plugin.metadata.usage_count, 1)
        cliente.assert_called_once_with(
            base_url="http://localhost:9527", timeout=20, authorized=True)
        cliente.return_value.generate.assert_called_once_with("hola", model=None)

    def test_usar_sin_inicializar_es_error(self):
        with self.assertRaisesRegex(RuntimeError, "not initialized"):
            DeepSeekFreeAgentPlugin().generate("hola")


if __name__ == "__main__":
    unittest.main()
