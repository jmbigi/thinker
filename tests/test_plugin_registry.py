"""Tests del subsistema de plugins: descubrimiento, config y ciclo de vida.

Todo offline y determinista (P1.21/regla propia 6): los plugins de prueba se
escriben en directorios temporales y los reales que se ejercitan son los
simulados (`mock_llm`, `mock_search`), que no usan red ni API keys.
"""

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path

from plugins.interfaces import PluginConfig
from plugins.registry import PluginRegistry

REPO_ROOT = Path(__file__).resolve().parent.parent

# Plugin de prueba SIMULADO: dos clases concretas (una LLM y una Core).
FAKE_PLUGIN_SRC = '''
from plugins.interfaces import (CorePlugin, LLMProviderPlugin, PluginMetadata,
                                PluginType)


class FakeLLM(LLMProviderPlugin):
    def _get_metadata(self):
        return PluginMetadata(
            name="fake_llm",
            version="9.9.9",
            plugin_type=PluginType.LLM_PROVIDER,
            description="proveedor falso para tests",
        )

    def generate(self, prompt, model=None, **kwargs):
        self.metadata.usage_count += 1
        return "fake:" + prompt

    def get_available_models(self):
        return ["fake-1"]

    def estimate_cost(self, prompt, model=None):
        return 0.0


class FakeCore(CorePlugin):
    def _get_metadata(self):
        return PluginMetadata(
            name="fake_core",
            version="1.0.0",
            plugin_type=PluginType.CORE,
            description="plugin de nucleo falso",
        )

    def get_hooks(self):
        return {"pre_research": lambda *a, **k: "hook-ejecutado"}
'''


class PluginRegistryTestCase(unittest.TestCase):
    """Base con un directorio temporal de plugins y una config YAML por test."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.plugin_dir = self.tmp / "plugins"
        self.plugin_dir.mkdir()
        self.config_path = self.tmp / "plugins.yaml"
        (self.plugin_dir / "fake_plugins.py").write_text(FAKE_PLUGIN_SRC)

    def tearDown(self):
        self._tmp.cleanup()

    def write_config(self, text: str) -> None:
        self.config_path.write_text(text)

    def make_registry(self) -> PluginRegistry:
        return PluginRegistry(
            plugin_dirs=[str(self.plugin_dir)],
            config_path=str(self.config_path),
        )

    def discovered_registry(self) -> PluginRegistry:
        registry = self.make_registry()
        self.assertEqual(registry.discover_plugins(), 2)
        return registry


class TestDescubrimiento(PluginRegistryTestCase):
    def test_descubre_las_clases_concretas_del_directorio(self):
        registry = self.discovered_registry()
        nombres = sorted(p["name"] for p in registry.list_plugins())
        self.assertEqual(nombres, ["fake_core", "fake_llm"])

    def test_no_crea_directorios_inexistentes(self):
        inexistente = self.tmp / "no-existe"
        registry = PluginRegistry(
            plugin_dirs=[str(inexistente)],
            config_path=str(self.config_path),
        )
        self.assertEqual(registry.discover_plugins(), 0)
        self.assertFalse(inexistente.exists())


class TestRutasPorDefectoDelRegistro(unittest.TestCase):
    """Las rutas por defecto se resuelven respecto al PAQUETE, no al CWD:
    descubrir plugins debe funcionar igual desde cualquier directorio."""

    def test_los_defaults_descubren_lo_mismo_desde_otro_cwd(self):
        referencia = PluginRegistry().discover_plugins()
        self.assertGreaterEqual(referencia, 1)  # el test no es trivial (0==0)

        with tempfile.TemporaryDirectory() as otro:
            cwd_original = os.getcwd()
            os.chdir(otro)
            try:
                desde_otro_cwd = PluginRegistry().discover_plugins()
            finally:
                os.chdir(cwd_original)

        self.assertEqual(desde_otro_cwd, referencia)

    def test_avisa_si_ningun_directorio_existe(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry = PluginRegistry(
                plugin_dirs=[str(Path(tmp) / "inexistente")],
                config_path=str(Path(tmp) / "plugins.yaml"),
            )
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(registry.discover_plugins(), 0)
        self.assertIn("no existe ningún directorio de plugins",
                      err.getvalue())


class TestConfiguracionYaml(PluginRegistryTestCase):
    def test_archivo_ausente_usa_los_valores_por_defecto(self):
        registry = self.discovered_registry()
        self.assertNotEqual(registry.load_all(), {})
        self.assertEqual(registry.get_plugin("fake_llm") is not None, True)

    def test_enabled_false_impide_que_load_all_cargue_el_plugin(self):
        self.write_config(
            "plugins:\n"
            "  fake_llm:\n"
            "    enabled: false\n"
        )
        registry = self.discovered_registry()
        resultados = registry.load_all()

        self.assertNotIn("fake_llm", resultados)
        self.assertIsNone(registry.get_plugin("fake_llm"))
        self.assertIn("fake_core", resultados)

    def test_enabled_true_carga_el_plugin(self):
        self.write_config(
            "plugins:\n"
            "  fake_llm:\n"
            "    enabled: true\n"
        )
        registry = self.discovered_registry()
        resultados = registry.load_all()

        self.assertTrue(resultados["fake_llm"])
        self.assertIsNotNone(registry.get_plugin("fake_llm"))

    def test_la_carga_explicita_ignora_enabled_false(self):
        self.write_config(
            "plugins:\n"
            "  fake_llm:\n"
            "    enabled: false\n"
        )
        registry = self.discovered_registry()

        self.assertTrue(registry.load_plugin("fake_llm"))
        self.assertIsNotNone(registry.get_plugin("fake_llm"))

    def test_priority_y_params_se_fusionan_desde_el_archivo(self):
        self.write_config(
            "plugins:\n"
            "  fake_llm:\n"
            "    priority: 42\n"
            "    params:\n"
            "      model: modelo-x\n"
        )
        registry = self.discovered_registry()
        self.assertTrue(registry.load_plugin("fake_llm"))

        config = registry.get_plugin("fake_llm").config
        self.assertEqual(config.priority, 42)
        self.assertEqual(config.params, {"model": "modelo-x"})

    def test_config_ilegible_eleva_error_en_vez_de_ignorarse(self):
        self.write_config("plugins: [esto no es yaml valido\n")
        registry = self.discovered_registry()

        with self.assertRaises(RuntimeError) as ctx:
            registry.load_all()
        self.assertIn("configuración de plugins", str(ctx.exception))

    def test_config_ilegible_marca_error_al_cargar_un_plugin(self):
        self.write_config("plugins: [esto no es yaml valido\n")
        registry = self.discovered_registry()

        self.assertFalse(registry.load_plugin("fake_llm"))

    def test_reload_relee_los_cambios_del_yaml(self):
        self.write_config(
            "plugins:\n"
            "  fake_llm:\n"
            "    params:\n"
            "      model: uno\n"
        )
        registry = self.discovered_registry()
        self.assertTrue(registry.load_plugin("fake_llm"))
        self.assertEqual(registry.get_plugin("fake_llm").config.params["model"],
                         "uno")

        self.write_config(
            "plugins:\n"
            "  fake_llm:\n"
            "    params:\n"
            "      model: dos\n"
        )
        self.assertTrue(registry.reload_plugin("fake_llm"))
        self.assertEqual(registry.get_plugin("fake_llm").config.params["model"],
                         "dos")

    def test_reload_conserva_el_override_pasado_por_codigo(self):
        self.write_config(
            "plugins:\n"
            "  fake_llm:\n"
            "    params:\n"
            "      model: archivo\n"
        )
        registry = self.discovered_registry()
        self.assertTrue(registry.load_plugin(
            "fake_llm", PluginConfig(params={"model": "runtime"})))

        self.write_config(
            "plugins:\n"
            "  fake_llm:\n"
            "    params:\n"
            "      model: nuevo\n"
        )
        self.assertTrue(registry.reload_plugin("fake_llm"))

        self.assertEqual(registry.get_plugin("fake_llm").config.params["model"],
                         "runtime")

    def test_config_con_raiz_que_no_es_mapa_falla_con_motivo(self):
        self.write_config("- uno\n- dos\n")
        registry = self.discovered_registry()

        self.assertFalse(registry.load_plugin("fake_llm"))
        error = next(p for p in registry.list_plugins()
                     if p["name"] == "fake_llm")["error_message"]
        self.assertIn("debe ser un mapa", error)


class TestConfiguracionToml(PluginRegistryTestCase):
    def setUp(self):
        super().setUp()
        self.config_path = self.tmp / "plugins.toml"
        self.write_config(
            "[plugins.fake_llm]\n"
            "enabled = true\n"
            "[plugins.fake_llm.params]\n"
            "model = \"modelo-toml\"\n"
        )

    def test_lee_toml_con_stdlib_sin_dependencia_extra(self):
        registry = self.discovered_registry()

        self.assertTrue(registry.load_plugin("fake_llm"))
        self.assertEqual(
            registry.get_plugin("fake_llm").config.params["model"],
            "modelo-toml")

class TestCicloDeVida(PluginRegistryTestCase):
    def test_load_unload_reload(self):
        registry = self.discovered_registry()

        self.assertTrue(registry.load_plugin("fake_llm"))
        instancia = registry.get_plugin("fake_llm")
        self.assertIsNotNone(instancia)

        self.assertTrue(registry.unload_plugin("fake_llm"))
        self.assertIsNone(registry.get_plugin("fake_llm"))

        self.assertTrue(registry.reload_plugin("fake_llm"))
        self.assertIsNot(registry.get_plugin("fake_llm"), instancia)

    def test_estado_reportado_tras_cargar_y_descargar(self):
        registry = self.discovered_registry()
        registry.load_plugin("fake_llm")

        por_nombre = {p["name"]: p for p in registry.list_plugins()}
        self.assertEqual(por_nombre["fake_llm"]["status"], "loaded")
        self.assertGreater(por_nombre["fake_llm"]["load_time"], 0.0)
        self.assertEqual(por_nombre["fake_core"]["status"], "unloaded")

        registry.unload_plugin("fake_llm")
        por_nombre = {p["name"]: p for p in registry.list_plugins()}
        self.assertEqual(por_nombre["fake_llm"]["status"], "unloaded")

    def test_redescubrir_no_descarta_el_plugin_cargado(self):
        registry = self.discovered_registry()
        self.assertTrue(registry.load_plugin("fake_llm"))
        instancia = registry.get_plugin("fake_llm")

        registry.discover_plugins()

        self.assertIs(registry.get_plugin("fake_llm"), instancia)

    def test_plugin_inexistente_devuelve_false(self):
        registry = self.discovered_registry()
        self.assertFalse(registry.load_plugin("no-existe"))
        self.assertFalse(registry.unload_plugin("no-existe"))

    def test_carga_idempotente(self):
        registry = self.discovered_registry()
        self.assertTrue(registry.load_plugin("fake_llm"))
        primera = registry.get_plugin("fake_llm")

        self.assertTrue(registry.load_plugin("fake_llm"))
        self.assertIs(registry.get_plugin("fake_llm"), primera)

    def test_proveedor_activo_por_tipo(self):
        registry = self.discovered_registry()
        registry.load_all()

        self.assertEqual(registry.get_active_llm().metadata.name, "fake_llm")
        self.assertFalse(registry.set_active_llm("fake_core"))
        self.assertFalse(registry.set_active_search("no-existe"))

    def test_genera_con_el_plugin_cargado(self):
        registry = self.discovered_registry()
        registry.load_plugin("fake_llm")

        self.assertEqual(registry.get_plugin("fake_llm").generate("hola"), "fake:hola")

    def test_shutdown_all_descarga_todo(self):
        registry = self.discovered_registry()
        registry.load_all()
        registry.shutdown_all()

        self.assertIsNone(registry.get_plugin("fake_llm"))
        self.assertIsNone(registry.get_plugin("fake_core"))


class TestHooks(PluginRegistryTestCase):
    def test_hook_se_registra_al_cargar_y_se_retira_al_descargar(self):
        registry = self.discovered_registry()
        registry.load_plugin("fake_core")

        self.assertEqual(registry.trigger_hook("pre_research"), ["hook-ejecutado"])

        registry.unload_plugin("fake_core")
        self.assertEqual(registry.trigger_hook("pre_research"), [])

    def test_hooks_no_registrados_devuelven_lista_vacia(self):
        registry = self.discovered_registry()
        registry.load_plugin("fake_core")
        self.assertEqual(registry.trigger_hook("post_report"), [])


class TestPluginsRealesOffline(unittest.TestCase):
    """Los plugins simulados reales deben cargar y ejecutar sin red."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.config_path = str(Path(self._tmp.name) / "sin-config.yaml")

    def tearDown(self):
        self._tmp.cleanup()

    def make_registry(self):
        return PluginRegistry(
            plugin_dirs=[
                str(REPO_ROOT / "plugins" / "llm_providers"),
                str(REPO_ROOT / "plugins" / "search_providers"),
            ],
            config_path=self.config_path,
        )

    def test_mock_llm_carga_y_genera_offline(self):
        registry = self.make_registry()
        registry.discover_plugins()

        self.assertTrue(registry.load_plugin("mock_llm"))
        respuesta = registry.get_plugin("mock_llm").generate("Responde: OK")
        self.assertIn("simulad", respuesta.lower())

    def test_mock_search_carga_y_busca_offline(self):
        registry = self.make_registry()
        registry.discover_plugins()

        self.assertTrue(registry.load_plugin("mock_search"))
        resultados = registry.get_plugin("mock_search").search("consulta", max_results=2)
        self.assertEqual(len(resultados), 2)
        self.assertIn("url", resultados[0])

    def test_mock_search_respeta_params_max_results(self):
        """El mock sigue el contrato común de SearchProviderPlugin:
        `params.max_results` fija el límite por defecto (antes lo ignoraba y,
        con params max_results=2, devolvía 3 resultados)."""
        from plugins.search_providers.mock_search_plugin import MockSearchPlugin

        plugin = MockSearchPlugin(PluginConfig(params={"max_results": 2}))
        self.assertTrue(plugin.initialize())

        self.assertEqual(len(plugin.search("consulta")), 2)
        self.assertEqual(len(plugin.search("consulta", max_results=4)), 4)

        por_defecto = MockSearchPlugin()
        self.assertTrue(por_defecto.initialize())
        self.assertEqual(len(por_defecto.search("consulta")), 5)

    def test_load_all_sin_config_carga_los_simulados(self):
        registry = self.make_registry()
        registry.discover_plugins()
        resultados = registry.load_all()

        self.assertTrue(resultados.get("mock_llm"))
        self.assertTrue(resultados.get("mock_search"))

    def test_dashboard_agrega_estado_de_los_plugins(self):
        registry = self.make_registry()
        registry.discover_plugins()
        registry.load_plugin("mock_llm")

        datos = registry.get_dashboard_data()
        self.assertEqual(datos["total_plugins"], len(registry.list_plugins()))
        self.assertEqual(datos["active_llm"], "mock_llm")
        self.assertGreaterEqual(datos["loaded_plugins"], 1)


if __name__ == "__main__":
    unittest.main()
