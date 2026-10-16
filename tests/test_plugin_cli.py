"""Tests de plugins/cli.py: comandos de gestión, offline.

El registro global se sustituye por uno temporal (plugins de prueba + los
buscadores reales simulados `mock_search`), de modo que cada test es
independiente y no toca el estado global del módulo.
"""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from plugins import cli
from plugins.registry import PluginRegistry
from tests.test_plugin_registry import FAKE_PLUGIN_SRC

REPO_ROOT = Path(__file__).resolve().parent.parent


def _cuenta_plugins(directorio: Path) -> int:
    return len([f for f in directorio.glob("*.py") if not f.name.startswith("__")])


class TestPluginCli(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.plugin_dir = self.tmp / "plugins"
        self.plugin_dir.mkdir()
        (self.plugin_dir / "fake_plugins.py").write_text(FAKE_PLUGIN_SRC)

        self.search_dir = REPO_ROOT / "plugins" / "search_providers"
        self.expected_count = 2 + _cuenta_plugins(self.search_dir)

        self.registry = PluginRegistry(
            plugin_dirs=[str(self.plugin_dir), str(self.search_dir)],
            config_path=str(self.tmp / "plugins.yaml"),
        )
        patcher = patch.object(cli, "plugin_registry", self.registry)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmp.cleanup)

    def run_cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(argv)
        return code, out.getvalue(), err.getvalue()

    def test_discover(self):
        code, out, _ = self.run_cli(["discover"])

        self.assertEqual(code, 0)
        self.assertIn(f"Discovered {self.expected_count} plugins", out)
        self.assertEqual(len(self.registry.list_plugins()), self.expected_count)

    def test_list_tabla(self):
        code, out, _ = self.run_cli(["list"])

        self.assertEqual(code, 0)
        self.assertIn("fake_llm", out)
        self.assertIn("mock_search", out)

    def test_list_json(self):
        code, out, _ = self.run_cli(["list", "--json"])

        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(out)), self.expected_count)

    def test_list_filtrado_por_tipo(self):
        code, out, _ = self.run_cli(["list", "--type", "llm_provider", "--json"])
        datos = json.loads(out)

        self.assertEqual(code, 0)
        self.assertEqual([p["name"] for p in datos], ["fake_llm"])
        self.assertTrue(all(p["type"] == "llm_provider" for p in datos))

    def test_list_sin_plugins(self):
        vacio = PluginRegistry(plugin_dirs=[str(self.tmp / "sin-plugins")],
                               config_path=str(self.tmp / "vacio.yaml"))
        with patch.object(cli, "plugin_registry", vacio):
            code, out, _ = self.run_cli(["list"])

        self.assertEqual(code, 0)
        self.assertIn("No plugins found.", out)

    def test_load_reload_unload(self):
        code, out, _ = self.run_cli(["load", "fake_llm"])
        self.assertEqual(code, 0)
        self.assertIn("Load fake_llm: OK", out)

        code, out, _ = self.run_cli(["reload", "fake_llm"])
        self.assertEqual(code, 0)
        self.assertIn("Reload fake_llm: OK", out)

        code, out, _ = self.run_cli(["unload", "fake_llm"])
        self.assertEqual(code, 0)
        self.assertIn("Unload fake_llm: OK", out)
        self.assertIsNone(self.registry.get_plugin("fake_llm"))

    def test_load_all_carga_los_simulados(self):
        code, out, _ = self.run_cli(["load", "--all"])

        self.assertEqual(code, 0)
        self.assertIn("fake_llm: OK", out)
        self.assertIn("mock_search: OK", out)

    def test_load_inexistente_devuelve_1(self):
        code, out, _ = self.run_cli(["load", "no-existe"])

        self.assertEqual(code, 1)
        self.assertIn("FAILED", out)

    def test_load_sin_nombre_es_error_de_uso(self):
        code, _, err = self.run_cli(["load"])

        self.assertEqual(code, 1)
        self.assertIn("plugin name required", err)

    def test_unload_sin_nombre_lo_rechaza_argparse(self):
        """`unload` exige el nombre posicional: argparse sale con código 2."""
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                cli.main(["unload"])

        self.assertEqual(ctx.exception.code, 2)

    def test_set_active_llm_y_rechazo_por_tipo(self):
        self.run_cli(["load", "fake_llm"])

        code, out, _ = self.run_cli(["set-active", "llm", "fake_llm"])
        self.assertEqual(code, 0)
        self.assertIn("Active LLM: fake_llm OK", out)
        self.assertIs(self.registry.get_active_llm(),
                      self.registry.get_plugin("fake_llm"))

        code, out, _ = self.run_cli(["set-active", "search", "fake_llm"])
        self.assertEqual(code, 1)
        self.assertIn("FAILED", out)

    def test_test_plugin_llm(self):
        self.run_cli(["load", "fake_llm"])

        code, out, _ = self.run_cli(["test", "fake_llm", "--prompt", "hola"])
        self.assertEqual(code, 0)
        self.assertIn("Response: fake:hola", out)

    def test_test_plugin_busqueda(self):
        self.run_cli(["load", "mock_search"])

        code, out, _ = self.run_cli(["test", "mock_search", "--prompt", "consulta"])
        self.assertEqual(code, 0)
        self.assertIn("example.com", out)

    def test_test_plugin_no_cargado(self):
        code, _, err = self.run_cli(["test", "fake_llm"])

        self.assertEqual(code, 1)
        self.assertIn("Plugin not loaded", err)

    def test_test_plugin_de_nucleo_no_es_probable(self):
        self.run_cli(["load", "fake_core"])

        code, _, err = self.run_cli(["test", "fake_core"])
        self.assertEqual(code, 1)
        self.assertIn("not testable", err)

    def test_dashboard_y_health(self):
        self.run_cli(["load", "fake_llm"])

        code, out, _ = self.run_cli(["dashboard"])
        self.assertEqual(code, 0)
        self.assertIn("PLUGIN SYSTEM DASHBOARD", out)

        code, out, _ = self.run_cli(["dashboard", "--json"])
        self.assertEqual(code, 0)
        self.assertIn("total_plugins", json.loads(out))

        code, out, _ = self.run_cli(["health"])
        self.assertEqual(code, 0)
        self.assertIn("Status:", out)

        code, out, _ = self.run_cli(["health", "--json"])
        self.assertEqual(code, 0)
        self.assertIn("error_rate", json.loads(out))


if __name__ == "__main__":
    unittest.main()
