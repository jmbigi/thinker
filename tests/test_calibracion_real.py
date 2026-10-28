"""Tests puros del piloto de Brier real (R14-C); sin red."""

import unittest

from tests.benchmarks.calibracion_real import (calcular_brier,
                                              brier_con_intervalo,
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

    def test_ic_bootstrap_es_determinista_y_contiene_el_brier(self):
        confianzas = [0.9, 0.8, 0.7, 0.95, 0.3, 0.2]
        aciertos = [True, True, False, True, False, False]
        primero = brier_con_intervalo(confianzas, aciertos)
        segundo = brier_con_intervalo(confianzas, aciertos)
        self.assertEqual(primero, segundo)  # misma semilla, mismo resultado
        brier = calcular_brier(confianzas, aciertos)
        self.assertAlmostEqual(primero["brier"], round(brier, 4))
        self.assertLessEqual(primero["ic95"][0], brier)
        self.assertGreaterEqual(primero["ic95"][1], brier)
        self.assertEqual(primero["n"], 6)

    def test_ic_ancho_con_muestra_pequena(self):
        # Dos pares con error muy distinto: el bootstrap debe abarcar desde
        # «los dos buenos» hasta «los dos malos» — nunca un intervalo falso
        # de precisión.
        resultado = brier_con_intervalo([0.99, 0.5], [False, True])
        amplitud = resultado["ic95"][1] - resultado["ic95"][0]
        self.assertGreater(amplitud, 0.1)

    def test_sin_datos_no_hay_intervalo(self):
        self.assertIsNone(brier_con_intervalo([], []))


if __name__ == "__main__":
    unittest.main()
