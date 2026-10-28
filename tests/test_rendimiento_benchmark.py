"""Humo del benchmark de rendimiento (offline): campos presentes y
coherentes; el número de llamadas al LLM crece con las iteraciones."""

import unittest

from tests.benchmarks import rendimiento


class TestBenchmarkRendimiento(unittest.TestCase):
    def test_un_escenario_minimo_produce_metricas_coherentes(self):
        fila = rendimiento.medir_escenario("simple", 1)
        self.assertEqual(fila["escenario"], "simple")
        self.assertGreaterEqual(fila["latencia_s"], 0.0)
        self.assertGreaterEqual(fila["llamadas_llm"], 1)
        self.assertGreater(fila["caracteres_informe"], 0)
        self.assertIn("simulado", rendimiento.ejecutar()["modo"])

    def test_tres_escenarios_y_llamadas_no_decrecientes(self):
        resultado = rendimiento.ejecutar()
        nombres = [e["escenario"] for e in resultado["escenarios"]]
        self.assertEqual(nombres, ["simple", "media", "compleja"])
        llamadas = [e["llamadas_llm"] for e in resultado["escenarios"]]
        self.assertEqual(llamadas, sorted(llamadas))


if __name__ == "__main__":
    unittest.main()
