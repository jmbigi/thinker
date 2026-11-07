"""Contrato offline del proveedor Free AI Gateway (ia.forthtrade.com).

Sin red ni API key real. Verifica construcción, selección de clave del gateway
(sin caer a OPENAI_API_KEY ajena), mensajes de error y wiring de CLI/plugin.
"""

import os
import unittest
from unittest.mock import patch

from llm_providers import ForthtradeGatewayLLM
from plugins.interfaces import PluginConfig
from plugins.llm_providers.forthtrade_plugin import ForthtradeGatewayPlugin
from research_cli import build_llm, build_parser


class TestForthtradeGateway(unittest.TestCase):
    def test_defaults_y_base_url(self):
        with patch.dict(os.environ, {}, clear=True):
            llm = ForthtradeGatewayLLM()
        self.assertEqual(llm.base_url, "https://ia.forthtrade.com/v1")
        self.assertEqual(llm.model, "auto")
        self.assertEqual(llm.api_key, "")

    def test_acepta_claves_gateway_sin_usar_openai(self):
        for var in ("FT_AI_API_KEY", "API_KEY", "FREE_AI_API_KEY", "GATEWAY_API_KEY"):
            with self.subTest(var=var), patch.dict(
                    os.environ, {"OPENAI_API_KEY": "openai-no-usar", var: "gw"}, clear=True):
                llm = ForthtradeGatewayLLM()
                self.assertEqual(llm.api_key, "gw")
                self.assertEqual(llm.base_url, "https://ia.forthtrade.com/v1")

    def test_sin_key_falla_con_mensaje_claro(self):
        with patch.dict(os.environ, {}, clear=True):
            llm = ForthtradeGatewayLLM()
            with self.assertRaises(ValueError) as ctx:
                llm.generate("hola")
        self.assertIn("OpenAI API key required", str(ctx.exception))

    def test_plugin_configura_y_estima(self):
        with patch("llm_providers.ForthtradeGatewayLLM") as cls:
            cls.return_value.generate.return_value = "ok"
            plugin = ForthtradeGatewayPlugin(PluginConfig(params={
                "model": "auto", "max_retries": 2, "timeout": 15.0}))
            self.assertTrue(plugin.initialize())
            self.assertEqual(plugin.generate("hola"), "ok")
            self.assertEqual(plugin.estimate_cost("hola"), 0.0)
        cls.assert_called_once_with(model="auto", base_url=None, max_retries=2,
                                    timeout=15.0, use_cache=True)

    def test_cli_provider_forthtrade(self):
        args = build_parser().parse_args(["--provider", "forthtrade", "--model", "auto", "q"])
        with patch.dict(os.environ, {"FT_AI_API_KEY": "gw"}, clear=True):
            llm = build_llm(args)
        self.assertIsInstance(llm, ForthtradeGatewayLLM)
        self.assertEqual(llm.model, "auto")
        self.assertEqual(llm.base_url, "https://ia.forthtrade.com/v1")


if __name__ == "__main__":
    unittest.main()
