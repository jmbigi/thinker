"""Tests del holdout sintético del evaluador (offline)."""

import unittest

from tests.benchmarks.evaluador_holdout import CASOS, evaluar_holdout


class TestEvaluadorHoldout(unittest.TestCase):
    def test_holdout_tiene_casos_y_relaciones(self):
        self.assertEqual(len(CASOS), 6)
        tipos = {tipo for caso in CASOS for tipo in caso["esperado"]}
        self.assertIn("global_min", tipos)
        self.assertIn("global_max", tipos)
        self.assertIn("menor_que", tipos)

    def test_holdout_discrimina_sin_confundir_documentacion(self):
        resultado = evaluar_holdout()
        self.assertEqual(resultado["casos"], 6)
        self.assertEqual(resultado["aprobadas"], resultado["total"])
        por_nombre = {fila["nombre"]: fila for fila in resultado["resultados"]}
        self.assertGreater(por_nombre["completo"]["global"],
                           por_nombre["deficiente"]["global"])
        self.assertGreater(por_nombre["pequeno_completo"]["global"],
                           por_nombre["grande_vacio"]["global"])
        self.assertGreater(por_nombre["completo"]["global"],
                           por_nombre["readme_enganoso"]["global"])


if __name__ == "__main__":
    unittest.main()
