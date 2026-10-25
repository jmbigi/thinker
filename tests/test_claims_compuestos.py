"""Tests del piloto opt-in de descomposición de claims (R13-C)."""

import unittest

from tests.benchmarks.claims_compuestos import ejecutar


class TestClaimsCompuestos(unittest.TestCase):
    def test_descomposicion_detecta_contradiccion(self):
        resultado = ejecutar()

        self.assertTrue(resultado["mejora"])
        self.assertEqual(resultado["monolitico"]["verdict"], "supported")
        self.assertEqual(resultado["monolitico"]["llamadas"], 1)
        self.assertEqual(resultado["descompuesto"]["verdict"], "contradicted")
        self.assertEqual(resultado["descompuesto"]["llamadas"], 2)
        self.assertEqual(resultado["descompuesto"]["subclaims"], 2)


if __name__ == "__main__":
    unittest.main()
