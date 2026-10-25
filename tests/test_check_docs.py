"""Tests del gate de documentación (`scripts/check_docs.py`).

Fixtures temporales: un repo coherente y variantes con una sola discrepancia,
para probar que el gate falla por el motivo correcto y no por ruido.
"""

import contextlib
import io
import unittest

from scripts.check_docs import main, verificar
from tests.helpers import crear_proyecto

TRES_TESTS = ("import unittest\n\n\n"
              "class TestDemo(unittest.TestCase):\n"
              "    def test_a(self):\n        pass\n\n"
              "    def test_b(self):\n        pass\n\n"
              "    def test_c(self):\n        pass\n")


class TestCheckDocs(unittest.TestCase):
    def _repo(self, **cambios):
        archivos = {
            "AGENTS.md": "# Reglas\n\n- Plataformas verificadas: **3/3 en ambos**.\n",
            "docs/EVALUACIONES.md": (
                "### Autoevaluación\n\n"
                "**Actualización 2026-10-23**\n"
                "Suite **3/3** en Linux.\n"),
            "docs/PUBLICACION.md": "`thinker-research 0.1.0` publicado.\n",
            "pyproject.toml": '[project]\nname = "demo"\nversion = "0.1.0"\n',
            "requirements.txt": "requests==2.0.0\nopenai>=1.0,<3\n",
            "requirements.lock": "requests==2.0.0\nopenai==2.5.0\n",
            "tests/test_demo.py": TRES_TESTS,
        }
        archivos.update(cambios)
        return crear_proyecto(self, archivos)

    def test_repo_coherente_sin_problemas(self):
        self.assertEqual(verificar(self._repo()), [])

    def test_cifra_de_tests_desactualizada_en_agents(self):
        raiz = self._repo(**{
            "AGENTS.md": ". Plataformas verificadas: **4/4 en ambos**.\n"})

        problemas = verificar(raiz)

        self.assertTrue(any("AGENTS.md declara 4 tests y hay 3" in p
                            for p in problemas), problemas)

    def test_cifra_de_la_suite_desactualizada_en_evaluaciones(self):
        raiz = self._repo(**{"docs/EVALUACIONES.md": (
            "**Actualización 2026-10-23**\nSuite **4/4** en Linux.\n")})

        problemas = verificar(raiz)

        self.assertTrue(any("EVALUACIONES.md declara 4 tests y hay 3" in p
                            for p in problemas), problemas)

    def test_pin_distinto_entre_requirements_y_lock(self):
        raiz = self._repo(**{"requirements.lock": "requests==1.9.0\nopenai==2.5.0\n"})

        problemas = verificar(raiz)

        self.assertTrue(any("requests==2.0.0" in p and "1.9.0" in p
                            for p in problemas), problemas)

    def test_version_del_lock_fuera_del_rango_declarado(self):
        raiz = self._repo(**{"requirements.lock": "requests==2.0.0\nopenai==3.5.0\n"})

        problemas = verificar(raiz)

        self.assertTrue(any("openai del lock (3.5.0)" in p
                            for p in problemas), problemas)

    def test_version_no_publicada(self):
        raiz = self._repo(**{"pyproject.toml": (
            '[project]\nname = "demo"\nversion = "0.1.1"\n')})

        problemas = verificar(raiz)

        self.assertTrue(any("versión 0.1.1" in p for p in problemas), problemas)

    def test_publicacion_con_formato_de_estado(self):
        raiz = self._repo(**{
            "docs/PUBLICACION.md": "> Estado: **versión `0.1.0` publicada en "
                                   "TestPyPI y PyPI**.\n"})

        self.assertEqual(verificar(raiz), [])

    def test_sin_vineta_de_plataformas_es_no_verificable(self):
        raiz = self._repo(**{"AGENTS.md": "# Reglas sin cifras\n"})

        with self.assertRaises(ValueError):
            verificar(raiz)

    def test_main_devuelve_1_con_discrepancias_y_0_si_cuadra(self):
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            codigo = main([str(self._repo())])
        self.assertEqual(codigo, 0, salida.getvalue())

        salida_rota = io.StringIO()
        with contextlib.redirect_stdout(salida_rota):
            codigo_roto = main([str(self._repo(**{
                "AGENTS.md": ". Plataformas verificadas: **9/9 en ambos**.\n"}))])
        self.assertEqual(codigo_roto, 1)
        self.assertIn("DOCS: 1 discrepancia", salida_rota.getvalue())

    def test_cifra_de_mutacion_de_readme_debe_cuadrar_con_agents(self):
        agents = ("# Reglas\n\n- Plataformas verificadas: **3/3 en ambos**.\n"
                  "- La mutación global es 95,2% (3635/3819; 184 supervivientes).\n")
        readme = ("La suite mata el **95,2%** de los mutantes de `mutmut` "
                  "(3635/3819; 184 supervivientes).\n")
        self.assertEqual(verificar(self._repo(**{
            "AGENTS.md": agents, "README.md": readme})), [])

        problemas = verificar(self._repo(**{
            "AGENTS.md": agents,
            "README.md": readme.replace("95,2", "94,7")
                               .replace("3635", "3581")
                               .replace("3819", "3780")}))
        self.assertTrue(any("README.md declara mutación" in p
                            for p in problemas), problemas)

        sin_agents = verificar(self._repo(**{
            "AGENTS.md": "# Reglas\n\n- Plataformas verificadas: **3/3 en ambos**.\n",
            "README.md": readme}))
        self.assertTrue(any("AGENTS.md no tiene la cifra vigente" in p
                            for p in sin_agents), sin_agents)

        sin_readme = verificar(self._repo(**{
            "AGENTS.md": agents, "README.md": "# README sin cifra\n"}))
        self.assertTrue(any("README.md no declara la cifra de mutación" in p
                            for p in sin_readme), sin_readme)

    def test_main_devuelve_2_si_no_puede_verificar(self):
        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            codigo = main([str(self._repo(**{
                "AGENTS.md": "# sin cifras\n"}))])

        self.assertEqual(codigo, 2)
        self.assertIn("no verificable", error.getvalue())


if __name__ == "__main__":
    unittest.main()
