"""Tests del registro de métricas de calidad (offline, sin escribir docs)."""

import unittest

from scripts.metricas_calidad import recolectar


class TestMetricasCalidad(unittest.TestCase):
    def test_informe_declara_metodo_y_limites(self):
        informe = recolectar(con_cobertura=False)
        self.assertEqual(informe["schema_version"], 1)
        self.assertIn("commit", informe)
        metricas = informe["metricas"]
        for nombre in ("tests_estaticos", "evaluador_precision",
                       "evaluador_holdout", "rag", "calibracion",
                       "rendimiento"):
            self.assertIn(nombre, metricas)
            self.assertIn("metodo", metricas[nombre])
            self.assertIn("no_prueba", metricas[nombre])

    def test_valores_en_rango(self):
        metricas = recolectar(con_cobertura=False)["metricas"]
        self.assertGreater(metricas["tests_estaticos"]["valor"], 1000)
        precision = metricas["evaluador_precision"]
        for clave in ("precision", "recall", "f1", "accuracy"):
            self.assertGreaterEqual(precision[clave], 0.0)
            self.assertLessEqual(precision[clave], 1.0)
        holdout = metricas["evaluador_holdout"]
        self.assertEqual(holdout["aprobadas"], holdout["total"])
        for valor in metricas["rag"]["metricas"].values():
            self.assertGreaterEqual(valor, 0.0)
            self.assertLessEqual(valor, 1.0)
        self.assertFalse(metricas["calibracion"]["calibrada"])


if __name__ == "__main__":
    unittest.main()
