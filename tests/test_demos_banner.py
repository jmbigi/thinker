"""Los demos offline deben declarar lo simulado EN LA SALIDA, no solo en
comentarios del código (regla propia 4: lo simulado se declara explícitamente).
"""

import contextlib
import importlib
import io
import unittest

DEMOS = ("deep_research_system", "pensamiento_layer",
         "code_design_improvement_tools")


class TestBannerSimuladoEnDemos(unittest.TestCase):
    def _salida_demo(self, modulo):
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            importlib.import_module(modulo).main()
        return buf.getvalue()

    def test_cada_demo_abre_con_el_aviso_de_resultados_simulados(self):
        for modulo in DEMOS:
            with self.subTest(modulo=modulo):
                salida = self._salida_demo(modulo)
                self.assertTrue(
                    salida.startswith("*** MODO DEMO OFFLINE — "
                                      "RESULTADOS SIMULADOS ***"),
                    f"{modulo}: el aviso debe ser lo primero impreso")
                self.assertIn("MockLLM", salida)

    def test_el_aviso_nombra_la_limitacion(self):
        for modulo in DEMOS:
            with self.subTest(modulo=modulo):
                salida = self._salida_demo(modulo)
                self.assertIn("sin red", salida.splitlines()[1])
                self.assertIn("nada de lo producido es investigación",
                              salida)
                self.assertIn("real ni evidencia verificada", salida)


if __name__ == "__main__":
    unittest.main()
