"""Tests del arnés de mutación separado para evaluador/preflight (R3)."""

import unittest

from scripts.mutacion import (_ignorar, configurar, parsear_resultados)


class TestMutacion(unittest.TestCase):
    def test_configura_preflight_y_evaluador(self):
        texto = (
            "[tool.mutmut]\n"
            'source_paths = ["a.py"]\n'
            "pytest_add_cli_args_test_selection = [\"tests\"]\n")

        preflight = configurar(texto, "preflight")
        self.assertIn('source_paths = ["scripts/preflight.py"]', preflight)
        self.assertIn('"evidence.py"', preflight)
        self.assertIn("tests/test_preflight.py", preflight)
        self.assertIn("test_el_repositorio_real_pasa_su_propio_preflight",
                      preflight)

        evaluar = configurar(texto, "evaluar")
        self.assertIn('source_paths = ["evaluar_proyecto.py"]', evaluar)
        self.assertIn('"scripts"', evaluar)
        self.assertIn("tests/test_evaluador_precision.py", evaluar)
        self.assertIn("TestAutoevaluacionDeThinker", evaluar)

    def test_parsea_estados_y_calcula_tasa(self):
        texto = (
            "scripts.x.f__mutmut_1: killed\n"
            "scripts.x.f__mutmut_2: survived\n"
            "scripts.x.f__mutmut_3: no tests\n"
            "scripts.x.f__mutmut_4: timeout\n")

        resumen = parsear_resultados(texto)

        self.assertEqual(resumen["total"], 4)
        self.assertEqual(resumen["killed"], 1)
        self.assertEqual(resumen["survived"], 1)
        self.assertEqual(resumen["no_tests"], 1)
        self.assertEqual(resumen["timeout"], 1)
        self.assertEqual(resumen["tasa_sin_no_tests"], 0.3333)

    def test_ignorar_no_copia_env_ni_git(self):
        nombres = [".env", ".env.example", ".git", "demo.py", "x.pyc",
                   "pkg.egg-info"]
        ignorados = _ignorar(None, nombres)

        self.assertIn(".env", ignorados)
        self.assertIn(".git", ignorados)
        self.assertIn("x.pyc", ignorados)
        self.assertIn("pkg.egg-info", ignorados)
        self.assertNotIn(".env.example", ignorados)
        self.assertNotIn("demo.py", ignorados)


if __name__ == "__main__":
    unittest.main()
