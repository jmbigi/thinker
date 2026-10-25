"""Tests del piloto de verificador barato (R13-B)."""

import unittest

from tests.benchmarks.verificador_barato import ejecutar


class TestVerificadorBarato(unittest.TestCase):
    def test_verificador_separado_y_coste_declarado(self):
        resultado = ejecutar()

        self.assertEqual(resultado["llamadas_generador"], 1)
        self.assertEqual(resultado["llamadas_verificador"], 1)
        self.assertEqual(resultado["coste_extra"], 1)
        self.assertEqual(resultado["independencia"], "proveedor-distinto")
        self.assertEqual(resultado["verificador"], "verificador-barato")
        self.assertEqual(resultado["generador"], "generador-grande")
        self.assertIn("simulados", resultado["nota"])


if __name__ == "__main__":
    unittest.main()
