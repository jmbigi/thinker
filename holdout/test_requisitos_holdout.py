"""Holdout del modo --requisitos: parseo y verificación end-to-end."""

import tempfile
import unittest
from pathlib import Path

from evaluar_proyecto import evaluar, parsear_requisitos

REQUISITOS = """## R1: La suite pasa
- Enunciado: El proyecto debe tener un test que pase.
- Criterio de aceptación: test_ok pasa.
- Verificación: test
- Evidencia: tests/test_app.py::test_ok
"""


class TestRequisitosHoldout(unittest.TestCase):
    def test_parsea_y_evalua_requisito(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            (raiz / "tests").mkdir()
            (raiz / "app.py").write_text("def main():\n    return 1\n",
                                        encoding="utf-8")
            (raiz / "tests/test_app.py").write_text(
                "import unittest\n\n\n"
                "class T(unittest.TestCase):\n"
                "    def test_ok(self):\n"
                "        self.assertTrue(True)\n", encoding="utf-8")
            archivo = raiz / "requisitos.md"
            archivo.write_text(REQUISITOS, encoding="utf-8")

            requisitos = parsear_requisitos(archivo)
            self.assertEqual(requisitos[0].id, "R1")

            informe = evaluar(raiz, con_red=False, ejecutar_tests_flag=True,
                              requisitos_path=archivo)
            self.assertEqual(informe["requisitos"]["items"][0]["veredicto"],
                             "CUMPLE")


if __name__ == "__main__":
    unittest.main()
