"""Tests puros del piloto de Brier real (R14-C); sin red."""

import unittest

from tests.benchmarks.calibracion_real import (calcular_brier,
                                              tabla_fiabilidad)


class TestCalibracionReal(unittest.TestCase):
    def test_brier(self):
        self.assertAlmostEqual(
            calcular_brier([0.9, 0.1], [True, False]), 0.01)
        self.assertIsNone(calcular_brier([], []))

    def test_tabla(self):
        filas = tabla_fiabilidad([0.95, 0.9, 0.1], [True, False, False])
        self.assertEqual(sum(f["n"] for f in filas), 3)
        self.assertEqual(filas[-1]["frecuencia"], 0.5)


if __name__ == "__main__":
    unittest.main()
