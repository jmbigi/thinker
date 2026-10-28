"""Contrato exacto de evaluar_herramientas (R3, clúster de 70 mutantes).

Cubre h1 (manifiestos), h2 (licencia), h3 (señales de CI aisladas), h4
(runner declarado), h5 (licencias PyPI: libres / no libres / no verificables),
h6 (imports: permitidos, first-party y severidad) y h7 (decisiones).
La firma por defecto (con_red=True) se verifica con licencia_pypi mockeada.
"""

import unittest
from unittest.mock import patch

import evaluar_proyecto
from evaluar_proyecto import evaluar_herramientas
from tests.helpers import crear_proyecto

PATCH_LICENCIA = "evaluar_proyecto.licencia_pypi"


def _dim(raiz, con_red=False):
    return evaluar_herramientas(raiz, evaluar_proyecto.analizar_perfil(raiz),
                                con_red=con_red)


class TestHerramientasContrato(unittest.TestCase):
    def test_por_defecto_consulta_licencias_en_pypi(self):
        raiz = crear_proyecto(self, {
            "requirements.txt": "requests==2.31.0\n",
            "app.py": "x = 1\n",
        })
        with patch(PATCH_LICENCIA,
                   return_value={"licencia": "MIT", "libre": True,
                                 "fuente": "PyPI", "error": None}) as mock:
            dim = evaluar_herramientas(raiz,
                                       evaluar_proyecto.analizar_perfil(raiz))
        self.assertTrue(mock.called)
        self.assertIn("h5_licencias_libres", dim.criterios)

    def test_manifiestos_nota_exacta_con_truncado_en_nueve(self):
        raiz = crear_proyecto(self, {
            "Cargo.toml": "", "build.gradle": "", "build.gradle.kts": "",
            "go.mod": "", "package.json": "{}", "pom.xml": "",
            "pyproject.toml": "", "setup.cfg": "", "setup.py": "",
        })
        dim = _dim(raiz)
        self.assertTrue(dim.criterios["h1_manifiesto"])
        self.assertEqual(
            dim.notas,
            ["manifiestos (9): Cargo.toml, build.gradle, build.gradle.kts, "
             "go.mod, package.json, pom.xml, pyproject.toml, setup.cfg…"])

    def test_manifiestos_exactamente_ocho_sin_puntos(self):
        raiz = crear_proyecto(self, {
            "Cargo.toml": "", "build.gradle": "", "go.mod": "",
            "package.json": "{}", "pom.xml": "", "pyproject.toml": "",
            "setup.cfg": "", "setup.py": "",
        })
        nota = _dim(raiz).notas[0]
        self.assertIn("manifiestos (8):", nota)
        self.assertNotIn("…", nota)

    def test_licencia_con_mayuscula_cuenta(self):
        raiz = crear_proyecto(self, {"License": "MIT", "app.py": "x = 1\n"})
        self.assertTrue(_dim(raiz).criterios["h2_licencia"])

    def test_cada_senal_de_ci_basta_por_si_sola(self):
        senales = (".github/workflows/ci.yml", ".gitlab-ci.yml",
                   ".circleci/config.yml", "azure-pipelines.yml",
                   "Jenkinsfile", "scripts/verify.sh", "Makefile", "tox.ini")
        for senal in senales:
            with self.subTest(senal=senal):
                raiz = crear_proyecto(self, {
                    "app.py": "x = 1\n", senal: "x\n"})
                dim = _dim(raiz)
                self.assertTrue(
                    dim.criterios["h3_verificacion_automatizada"], senal)

    def test_sin_ninguna_senal_ci_falla(self):
        raiz = crear_proyecto(self, {"app.py": "x = 1\n"})
        dim = _dim(raiz)
        self.assertFalse(dim.criterios["h3_verificacion_automatizada"])
        self.assertTrue(any(h.criterio == "h3_verificacion_automatizada"
                            for h in dim.hallazgos))

    def test_runner_declarado_por_archivo_nota_exacta(self):
        # Test en la raíz (no en tests/): la convención no detecta comando y
        # gana la rama `runner_extra` (build.sh).
        raiz = crear_proyecto(self, {
            "build.sh": "echo test\n",
            "test_a.py": "def test_a():\n    assert True\n",
        })
        dim = _dim(raiz)
        self.assertTrue(dim.criterios["h4_runner_de_tests_declarado"])
        self.assertEqual(dim.notas, [
            "runner declarado: build.sh "
            "(comando no inspeccionado para ejecución)"])

    def test_tox_y_noxfile_se_detectan_por_deteccion_no_por_runner_extra(self):
        # detectar_comando_tests reconoce tox.ini y noxfile.py siempre, así que
        # la rama `runner_extra` (next) solo puede devolver build.sh — los
        # mutantes sobre tox/noxfile en esa rama son inalcanzables (E6).
        for archivo, origen in (("tox.ini", "tox.ini"),
                                ("noxfile.py", "noxfile.py")):
            with self.subTest(archivo=archivo):
                raiz = crear_proyecto(self, {
                    archivo: "x\n",
                    "test_a.py": "def test_a():\n    assert True\n",
                })
                dim = _dim(raiz)
                self.assertTrue(
                    dim.criterios["h4_runner_de_tests_declarado"])
                self.assertTrue(dim.notas[0].startswith("runner: "), dim.notas)
                self.assertIn(f"({origen})", dim.notas[0])

    def test_h5_dep_libre_es_verde(self):
        raiz = crear_proyecto(self, {
            "requirements.txt": "requests==2.31.0\n", "app.py": "x = 1\n"})
        with patch(PATCH_LICENCIA, return_value={
                "licencia": "MIT", "libre": True, "fuente": "PyPI",
                "error": None}):
            dim = _dim(raiz, con_red=True)
        self.assertTrue(dim.criterios["h5_licencias_libres"])
        self.assertFalse([h for h in dim.hallazgos
                          if h.criterio == "h5_licencias_libres"])

    def test_h5_dep_no_libre_hallazgo_exacto(self):
        raiz = crear_proyecto(self, {
            "requirements.txt": "rara==1.0\notra==2.0\nrequests==2.31.0\n",
            "app.py": "x = 1\n"})
        with patch(PATCH_LICENCIA, side_effect=lambda nombre: {
                "rara": {"licencia": "GPL-3.0", "libre": False,
                         "fuente": "PyPI", "error": None},
                "otra": {"licencia": "AGPL-3.0", "libre": False,
                         "fuente": "PyPI", "error": None},
                "requests": {"licencia": "Apache-2.0", "libre": True,
                             "fuente": "PyPI", "error": None}}[nombre]):
            dim = _dim(raiz, con_red=True)
        self.assertFalse(dim.criterios["h5_licencias_libres"])
        hallazgo = next(h for h in dim.hallazgos
                        if h.criterio == "h5_licencias_libres")
        self.assertEqual(hallazgo.a_dict(), {
            "severidad": "media",
            "descripcion": "Dependencias sin licencia libre declarada: "
                           "rara (GPL-3.0), otra (AGPL-3.0)",
            "evidencia": "PyPI", "tipo_evidencia": "verified-real",
            "criterio": "h5_licencias_libres"})

    def test_h5_error_y_libre_none_van_a_sin_verificar(self):
        raiz = crear_proyecto(self, {
            "requirements.txt": ("rota==1.0\nsinmeta==2.0\nmixta==3.0\n"
                                 "requests==2.31.0\n"),
            "app.py": "x = 1\n"})
        with patch(PATCH_LICENCIA, side_effect=lambda nombre: {
                "rota": {"error": "OSError: x", "libre": None,
                         "licencia": None, "fuente": None},
                "sinmeta": {"error": None, "libre": None,
                            "licencia": None, "fuente": None},
                # Error con licencia conocida: sin_verificar por el error,
                # no por el metadato ausente (aísla la condición OR).
                "mixta": {"error": "OSError: y", "libre": True,
                          "licencia": "MIT", "fuente": "PyPI"},
                "requests": {"licencia": "Apache-2.0", "libre": True,
                             "fuente": "PyPI", "error": None}}[nombre]):
            dim = _dim(raiz, con_red=True)
        self.assertFalse(dim.criterios["h5_licencias_libres"])
        hallazgo = next(h for h in dim.hallazgos
                        if h.criterio == "h5_licencias_libres")
        self.assertEqual(hallazgo.a_dict(), {
            "severidad": "baja",
            "descripcion": "Licencia no verificable en PyPI: "
                           "rota (OSError: x), sinmeta (sin metadato de "
                           "licencia), mixta (OSError: y)",
            "evidencia": "PyPI", "tipo_evidencia": "unverified",
            "criterio": "h5_licencias_libres"})

    def test_h6_import_first_party_no_es_hallazgo(self):
        raiz = crear_proyecto(self, {
            "mi_paquete/__init__.py": "",
            "mi_paquete/helper.py": "def f():\n    return 1\n",
            "app.py": "from mi_paquete import helper\n",
        })
        dim = _dim(raiz)
        self.assertTrue(dim.criterios["h6_imports_declarados"], dim.hallazgos)

    def test_h6_import_en_lock_sin_declarar_es_permitido(self):
        # Módulo de terceros en el lock pero no en requirements.txt: solo lo
        # permite `permitidos = first_party | versiones_lock` (aísla la
        # variable de la mutación, no la heurística local).
        raiz = crear_proyecto(self, {
            "requirements.lock": "rara==1.0\n",
            "app.py": "import rara\n",
        })
        dim = _dim(raiz)
        self.assertTrue(dim.criterios["h6_imports_declarados"], dim.hallazgos)

    def test_h6_import_tercero_sin_declarar_severidad_exacta(self):
        raiz = crear_proyecto(self, {"app.py": "import requests\n"})
        dim = _dim(raiz)
        self.assertFalse(dim.criterios["h6_imports_declarados"])
        hallazgo = next(h for h in dim.hallazgos
                        if h.criterio == "h6_imports_declarados")
        self.assertEqual(hallazgo.severidad, "alta")
        self.assertIn("app.py:1", hallazgo.evidencia)

    def test_h7_decisiones_nota_exacta_con_truncado_en_nueve(self):
        archivos = {f"docs/decision-{i}.md": "x\n" for i in range(1, 10)}
        raiz = crear_proyecto(self, {**archivos, "app.py": "x = 1\n"})
        dim = _dim(raiz)
        self.assertTrue(dim.criterios["h7_decisiones_documentadas"])
        # h7 no añade "…": muestra 8 de 9 (el mutante [:9] mostraría 9).
        self.assertEqual(
            dim.notas[-1],
            "registro de decisiones: docs/decision-1.md, docs/decision-2.md, "
            "docs/decision-3.md, docs/decision-4.md, docs/decision-5.md, "
            "docs/decision-6.md, docs/decision-7.md, docs/decision-8.md")

    def test_h7_ocho_decisiones_sin_puntos(self):
        archivos = {f"docs/decision-{i}.md": "x\n" for i in range(1, 9)}
        raiz = crear_proyecto(self, {**archivos, "app.py": "x = 1\n"})
        nota = _dim(raiz).notas[-1]
        self.assertNotIn("…", nota)


if __name__ == "__main__":
    unittest.main()
