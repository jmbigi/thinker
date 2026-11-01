"""Corpus adversario del evaluador: defectos conocidos que no deben reaparecer.

Cada fixture es un repo temporal mínimo que reproduce un fallo real detectado
en la auditoría del Hallazgo 97: paquetes inventados por el parser Poetry,
requirements sueltos aceptados como lockfile y prosa de README convertida en
comando de tests. El contrato es que el evaluador no afirme más de lo que
puede comprobar (P0.1/P0.2).
"""

import unittest
import warnings

from evaluar_proyecto import _dependencias_pyproject, _requisito_poetry, evaluar
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

    def test_poetry_caret_tilde_y_comodin_conservan_restricciones(self):
        casos = {
            "^1.2.3": ">=1.2.3,<2.0.0", "^1.2": ">=1.2,<2.0.0",
            "^1": ">=1,<2.0.0", "^0.2.3": ">=0.2.3,<0.3.0",
            "^0.0.3": ">=0.0.3,<0.0.4", "^0.0": ">=0.0,<0.1.0",
            "^0": ">=0,<1.0.0", "~1.2.3": ">=1.2.3,<1.3.0",
            "~1.2": ">=1.2,<1.3.0", "~1": ">=1,<2.0.0",
            "~0.0.3": ">=0.0.3,<0.1.0", "2.28.0": "==2.28.0",
            "1.*": "==1.*", "*": "", ">=1.2,<1.5": ">=1.2,<1.5",
            "<2.0": "<2.0", "==2.28.0": "==2.28.0", "!=1.2": "!=1.2",
            "~=1.2": "~=1.2", "^0.0.0": ">=0.0.0,<0.0.1",
            "^1.2.3a1": ">=1.2.3a1,<2.0.0", "~1.2.3.4": ">=1.2.3.4,<1.2.4.0",
            " ^1.2 ": ">=1.2,<2.0.0",
        }
        for version, esperado in casos.items():
            with self.subTest(version=version):
                self.assertEqual(_requisito_poetry("pkg", version), f"pkg{esperado}")

        deps = _dependencias_pyproject(
            '[tool.poetry.dependencies]\n'
            'django = "^4.2"\nrich = "~13.7"\ncualquiera = "*"\n')
        self.assertEqual({
            d["nombre"]: (d["operador"], d["version"]) for d in deps
        }, {"django": (">=", "4.2"), "rich": (">=", "13.7"),
            "cualquiera": ("", "")})

    def test_poetry_restriccion_invalida_advierte(self):
        for version in ("^abc", "~abc", "^1.2.*"):
            with self.subTest(version=version):
                with warnings.catch_warnings(record=True) as capturados:
                    warnings.simplefilter("always")
                    self.assertEqual(_requisito_poetry("pkg", version), f"pkg{version}")
                self.assertEqual(len(capturados), 1)
                self.assertEqual(
                    str(capturados[0].message),
                    f"Restricción Poetry no válida en pkg: {version!r}; "
                    "se conserva sin traducir")
                self.assertIs(capturados[0].category, UserWarning)
        with warnings.catch_warnings(record=True) as validos:
            warnings.simplefilter("always")
            self.assertEqual(_requisito_poetry("pkg", "~=1.2"), "pkg~=1.2")
        self.assertEqual(validos, [])

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
