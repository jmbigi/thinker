"""Tests de los plugins proveedores (LLM y búsqueda), offline y sin red.

Los constructores reales solo guardan endpoint/timeout (no hacen peticiones) y
los clientes LLM se sustituyen por dobles: ninguna prueba toca la red ni usa
API keys. Se fija el contrato de configuración (`params.max_results`) y que la
dependencia declarada por cada plugin sea la que el código usa de verdad.
"""

import unittest
from unittest.mock import patch

from plugins.interfaces import PluginConfig
from plugins.llm_providers.deepseek_plugin import DeepSeekPlugin
from plugins.llm_providers.openrouter_plugin import OpenRouterPlugin
from plugins.search_providers.duckduckgo_plugin import DuckDuckGoSearchPlugin
from plugins.search_providers.wikipedia_plugin import WikipediaSearchPlugin


class _FakeSearch:
    """Buscador de doble: registra el límite que recibe, sin red."""

    def __init__(self):
        self.limites = []

    def search(self, query, max_results=5):
        self.limites.append(max_results)
        return [{"title": query}]


class TestBusquedaConConfiguracion(unittest.TestCase):
    def _plugin(self, clase, params):
        plugin = clase(PluginConfig(params=params))
        self.assertTrue(plugin.initialize())
        plugin._search = _FakeSearch()
        return plugin

    def test_wikipedia_usa_el_max_results_de_la_configuracion(self):
        plugin = self._plugin(WikipediaSearchPlugin, {"max_results": 2})

        plugin.search("consulta")

        self.assertEqual(plugin._search.limites, [2])
        self.assertEqual(plugin.metadata.usage_count, 1)
        self.assertGreater(plugin.metadata.last_used, 0)

    def test_duckduckgo_usa_el_max_results_de_la_configuracion(self):
        plugin = self._plugin(DuckDuckGoSearchPlugin, {"max_results": 1})

        plugin.search("consulta")

        self.assertEqual(plugin._search.limites, [1])

    def test_sin_parametro_el_defecto_es_cinco(self):
        plugin = self._plugin(WikipediaSearchPlugin, {})

        plugin.search("consulta")

        self.assertEqual(plugin._search.limites, [5])

    def test_un_max_results_explicito_tiene_prioridad(self):
        plugin = self._plugin(WikipediaSearchPlugin, {"max_results": 2})

        plugin.search("consulta", max_results=7)
        plugin.search("consulta", max_results=0)

        self.assertEqual(plugin._search.limites, [7, 0])

    def test_buscar_sin_initialize_es_un_error_explicito(self):
        for clase in (WikipediaSearchPlugin, DuckDuckGoSearchPlugin):
            with self.subTest(plugin=clase.__name__):
                with self.assertRaisesRegex(RuntimeError, "not initialized"):
                    clase().search("consulta")

    def test_dependencias_declaradas_solo_las_que_se_usan(self):
        self.assertEqual(WikipediaSearchPlugin().metadata.dependencies, ["requests"])
        self.assertEqual(DuckDuckGoSearchPlugin().metadata.dependencies, ["requests"])

    def test_origen_de_cada_buscador(self):
        self.assertEqual(WikipediaSearchPlugin().get_source_name(), "Wikipedia")
        self.assertEqual(DuckDuckGoSearchPlugin().get_source_name(), "DuckDuckGo")


class TestProveedoresLLM(unittest.TestCase):
    def test_openrouter_pasa_la_configuracion_y_delega_generate(self):
        with patch("llm_providers.OpenRouterLLM") as cliente:
            cliente.return_value.generate.return_value = "respuesta"
            plugin = OpenRouterPlugin(PluginConfig(params={
                "model": "modelo:free", "use_fallback": False, "max_retries": 7}))

            self.assertTrue(plugin.initialize())
            self.assertEqual(plugin.generate("hola"), "respuesta")

        cliente.assert_called_once_with(model="modelo:free", use_fallback=False)
        self.assertEqual(cliente.return_value.max_retries, 7)
        cliente.return_value.generate.assert_called_once_with("hola", model=None)
        self.assertEqual(plugin.metadata.usage_count, 1)
        self.assertEqual(plugin.estimate_cost("lo que sea"), 0.0)

    def test_openrouter_lista_la_cadena_de_fallback_real(self):
        from llm_providers import OPENROUTER_FALLBACK_CHAIN

        self.assertEqual(OpenRouterPlugin().get_available_models(),
                         OPENROUTER_FALLBACK_CHAIN)

    def test_openrouter_si_falla_initialize_lo_declara(self):
        with patch("llm_providers.OpenRouterLLM", side_effect=RuntimeError("sin key")):
            plugin = OpenRouterPlugin(PluginConfig())

            self.assertFalse(plugin.initialize())
            self.assertEqual(plugin.metadata.error_message, "sin key")
            with self.assertRaisesRegex(RuntimeError, "not initialized"):
                plugin.generate("hola")

    def test_deepseek_pasa_la_configuracion_y_estima_el_coste(self):
        with patch("llm_providers.DeepSeekLLM") as cliente:
            plugin = DeepSeekPlugin(PluginConfig(params={
                "model": "deepseek-chat", "max_retries": 2,
                "base_url": "https://api.deepseek.com/v1"}))

            self.assertTrue(plugin.initialize())
            self.assertEqual(plugin.get_available_models(),
                             ["deepseek-chat", "deepseek-coder", "deepseek-reasoner"])
            # 400 caracteres ≈ 100 tokens de entrada a 0,14 USD/1M.
            self.assertAlmostEqual(plugin.estimate_cost("a" * 400),
                                   (100 / 1_000_000) * 0.14)

        cliente.assert_called_once_with(model="deepseek-chat", max_retries=2,
                                        base_url="https://api.deepseek.com/v1")

    def test_deepseek_generar_sin_initialize_es_un_error_explicito(self):
        with self.assertRaisesRegex(RuntimeError, "not initialized"):
            DeepSeekPlugin().generate("hola")


if __name__ == "__main__":
    unittest.main()
