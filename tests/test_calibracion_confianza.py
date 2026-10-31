"""Tests del benchmark de calibración simulada (R14-B)."""

import unittest

from tests.benchmarks.calibracion_confianza import (calcular_brier,
                                                   calcular_ece,
                                                   evaluar,
                                                   tabla_fiabilidad)


class TestCalibracionConfianza(unittest.TestCase):
    def test_brier_conocido(self):
        self.assertAlmostEqual(
            calcular_brier([(0.9, True), (0.1, False)]), 0.01)
        self.assertIsNone(calcular_brier([]))

    def test_ece_conocido(self):
        # 0.9 con acierto y 0.1 con fallo: cada tramo se desvía 0.1 y pesa 0.5.
        self.assertAlmostEqual(
            calcular_ece([(0.9, True), (0.1, False)]), 0.1)
        # Confianza 0.5 con un acierto y un fallo: calibración perfecta en el tramo.
        self.assertAlmostEqual(
            calcular_ece([(0.5, True), (0.5, False)]), 0.0)
        self.assertIsNone(calcular_ece([]))

    def test_tabla_y_declaracion_simulada(self):
        tabla = tabla_fiabilidad([(0.9, True), (0.9, False), (0.1, True)])
        self.assertEqual(sum(fila["n"] for fila in tabla), 3)
        self.assertEqual(tabla[-1]["frecuencia"], 0.5)

        resultado = evaluar()
        self.assertEqual(resultado["casos"], 16)
        self.assertFalse(resultado["calibrada"])
        self.assertIn("no prueban calibración real", resultado["nota"])
        self.assertIsNotNone(resultado["ece"])


if __name__ == "__main__":
    unittest.main()
