"""Corpus adversario del evaluador: defectos conocidos que no deben reaparecer.

Cada fixture es un repo temporal mínimo que reproduce un fallo real detectado
en la auditoría del Hallazgo 97: paquetes inventados por el parser Poetry,
requirements sueltos aceptados como lockfile y prosa de README convertida en
comando de tests. El contrato es que el evaluador no afirme más de lo que
puede comprobar (P0.1/P0.2).
"""

import unittest

from evaluar_proyecto import evaluar
from tests.helpers import crear_proyecto


class TestCorpusAdversario(unittest.TestCase):
    def _evaluar(self, archivos):
        raiz = crear_proyecto(self, archivos)
        return evaluar(raiz, con_red=False)

    @staticmethod
    def _textos(informe):
        return [h["descripcion"] + h["evidencia"]
                for dim in informe["dimensiones"].values()
                for h in dim["hallazgos"]]

    def test_poetry_version_exacta_no_inventa_paquete(self):
        informe = self._evaluar({
            "pyproject.toml": (
                '[project]\nname = "demo"\nversion = "0.1.0"\n'
                'requires-python = ">=3.11"\n'
                '[tool.poetry.dependencies]\npython = "^3.11"\n'
                'requests = "2.28.0"\n'),
            "app.py": "def f():\n    return 1\n",
            "tests/test_app.py": "def test_f():\n    assert f()\n",
        })

        self.assertTrue(
            informe["dimensiones"]["vigencia"]["criterios"]["v1_dependencias_fijadas"])
        self.assertFalse(any("requests2.28" in texto
                             for texto in self._textos(informe)))

    def test_requirements_sueltos_no_cuentan_como_lock(self):
        informe = self._evaluar({
            "requirements/base.txt": "requests>=2.0\nclick\n",
            "app.py": "import requests\n",
            "tests/test_app.py": "def test_f():\n    assert True\n",
        })

        criterios = informe["dimensiones"]["vigencia"]["criterios"]
        self.assertFalse(criterios["v1_dependencias_fijadas"])
        self.assertFalse(criterios["v2_lockfile"])
        self.assertTrue(any("Dependencias Python sin fijar: requests, click" in t
                            for t in self._textos(informe)))

    def test_prosa_de_readme_no_se_convierte_en_runner(self):
        informe = self._evaluar({
            "app.py": "def f():\n    return 1\n",
            "tests/test_app.py": "def test_f():\n    assert f()\n",
            "README.md": "Usamos un django test runner y detox en iOS.\n",
        })

        notas = informe["dimensiones"]["herramientas"]["notas"]
        self.assertFalse(any("go test" in nota or "tox" in nota
                             for nota in notas))
        self.assertTrue(any("convención" in nota for nota in notas))

    def test_comando_declarado_en_readme_si_se_detecta(self):
        informe = self._evaluar({
            "app.py": "def f():\n    return 1\n",
            "tests/test_app.py": "def test_f():\n    assert f()\n",
            "README.md": "Ejecuta `pytest -q` para las pruebas.\n",
        })

        notas = informe["dimensiones"]["herramientas"]["notas"]
        self.assertTrue(any("pytest -q" in nota and "README.md" in nota
                            for nota in notas), notas)


if __name__ == "__main__":
    unittest.main()
