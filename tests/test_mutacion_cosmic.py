"""Contrato de scripts/mutacion_cosmic.py: la config generada apunta al
módulo real y a la selección de tests de la campaña del evaluador.
La campaña completa (horas) no se ejecuta en tests."""

import unittest
from pathlib import Path

import scripts.mutacion_cosmic as mc

RAIZ = Path(__file__).resolve().parent.parent


class TestMutacionCosmic(unittest.TestCase):
    def test_config_apunta_a_la_copia_del_destino_no_al_repo(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            config = mc.generar_config(Path(tmp))
            texto = config.read_text(encoding="utf-8")
        self.assertIn('module-path = "evaluar_proyecto.py"', texto)
        self.assertNotIn(str(RAIZ), texto)
        self.assertIn("tests/test_evaluar_proyecto.py", texto)
        self.assertIn("tests/test_evaluador_corpus.py", texto)
        self.assertIn("tests/test_evaluador_precision.py", texto)
        self.assertIn('name = "local"', texto)
        self.assertIn("timeout =", texto)

    def test_timeout_configurable_se_refleja(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            config = mc.generar_config(Path(tmp), timeout=12.5)
            self.assertIn("timeout = 12.5", config.read_text(encoding="utf-8"))

    def test_la_seleccion_cubre_los_tres_archivos_de_la_campana(self):
        self.assertEqual(
            set(mc.SELECCION_TESTS.split()),
            {"tests/test_evaluar_proyecto.py",
             "tests/test_evaluador_corpus.py",
             "tests/test_evaluador_precision.py"})


if __name__ == "__main__":
    unittest.main()
