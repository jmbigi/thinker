"""Tests de plugins/dashboard.py: métricas, salud y export JSON (offline).

El dashboard se construye sobre un registro temporal y aislado, así que no
depende del estado global ni de la red.
"""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from plugins.dashboard import PluginDashboard
from plugins.interfaces import PluginStatus
from plugins.registry import PluginRegistry
from tests.test_plugin_registry import FAKE_PLUGIN_SRC


class PluginDashboardTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.plugin_dir = self.tmp / "plugins"
        self.plugin_dir.mkdir()
        (self.plugin_dir / "fake_plugins.py").write_text(FAKE_PLUGIN_SRC)

        self.registry = PluginRegistry(
            plugin_dirs=[str(self.plugin_dir)],
            config_path=str(self.tmp / "plugins.yaml"),
        )
        self.assertEqual(self.registry.discover_plugins(), 2)
        self.dashboard = PluginDashboard(registry=self.registry)

    def tearDown(self):
        self._tmp.cleanup()

    def por_nombre(self, metrics):
        return {p["name"]: p for p in metrics.plugins}

    def test_metricas_iniciales(self):
        metrics = self.dashboard.get_metrics()

        self.assertEqual(metrics.total_plugins, 2)
        self.assertEqual(metrics.loaded_plugins, 0)
        self.assertIsNone(metrics.active_llm)
        self.assertIsNone(metrics.active_search)
        self.assertEqual(metrics.total_requests, 0)
        self.assertEqual(metrics.total_errors, 0)

    def test_record_request_y_error_por_plugin(self):
        self.dashboard.record_request("fake_llm")
        self.dashboard.record_request("fake_llm")
        self.dashboard.record_error("fake_llm")

        metrics = self.dashboard.get_metrics()
        self.assertEqual(metrics.total_requests, 2)
        self.assertEqual(metrics.total_errors, 1)
        plugin = self.por_nombre(metrics)["fake_llm"]
        self.assertEqual(plugin["requests"], 2)
        self.assertEqual(plugin["errors"], 1)
        self.assertEqual(plugin["uptime"], 0)  # aún no está cargado

    def test_uptime_solo_cuenta_si_esta_cargado(self):
        self.registry.load_plugin("fake_llm")

        por_nombre = self.por_nombre(self.dashboard.get_metrics())
        self.assertGreater(por_nombre["fake_llm"]["uptime"], 0.0)
        self.assertEqual(por_nombre["fake_core"]["uptime"], 0)

    def test_health_healthy_sin_degradados(self):
        self.registry.load_plugin("fake_llm")

        salud = self.dashboard.health_summary()
        self.assertEqual(salud["status"], "healthy")
        self.assertEqual(salud["healthy_plugins"], 1)
        self.assertEqual(salud["degraded_plugins"], 0)
        self.assertEqual(salud["unloaded_plugins"], 1)
        self.assertEqual(salud["active_llm"], "fake_llm")
        self.assertEqual(salud["error_rate"], 0.0)

    def test_health_degraded_y_tasa_de_error(self):
        self.registry.load_plugin("fake_llm")
        self.registry._plugins["fake_core"].metadata.status = PluginStatus.ERROR
        self.dashboard.record_request("fake_llm")
        self.dashboard.record_error("fake_llm")

        salud = self.dashboard.health_summary()
        self.assertEqual(salud["status"], "degraded")
        self.assertEqual(salud["degraded_plugins"], 1)
        self.assertEqual(salud["total_requests"], 1)
        self.assertEqual(salud["error_rate"], 1.0)

    def test_export_json_es_valido_y_tiene_todas_las_claves(self):
        self.registry.load_plugin("fake_llm")

        datos = json.loads(self.dashboard.export_json())
        for clave in ("timestamp", "total_plugins", "loaded_plugins", "active_llm",
                      "active_search", "total_requests", "total_errors", "plugins"):
            self.assertIn(clave, datos)
        self.assertEqual(datos["loaded_plugins"], 1)

    def test_print_cli_dashboard_muestra_la_tabla(self):
        self.registry.load_plugin("fake_llm")
        self.dashboard.record_request("fake_llm")

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.dashboard.print_cli_dashboard()
        salida = buf.getvalue()

        self.assertIn("PLUGIN SYSTEM DASHBOARD", salida)
        self.assertIn("Total Plugins: 2 | Loaded: 1", salida)
        self.assertIn("fake_llm", salida)
        self.assertIn("Total Requests: 1", salida)

    def test_print_cli_dashboard_sin_plugins(self):
        vacio = PluginDashboard(registry=PluginRegistry(
            plugin_dirs=[str(self.tmp / "sin-plugins")],
            config_path=str(self.tmp / "vacio.yaml"),
        ))

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            vacio.print_cli_dashboard()

        self.assertIn("No plugins discovered.", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
