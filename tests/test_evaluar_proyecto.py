"""Tests de evaluar_proyecto.py: fixture con defectos plantados y autoevaluación.

Offline: la comprobación de PyPI se desactiva (`con_red=False`) y la fixture es
un proyecto temporal con defectos conocidos. Incluye una prueba de que la
evaluación es READ-ONLY (no escribe en el proyecto evaluado).
"""

import contextlib
import io
import json
import os
import tempfile
import unittest
import warnings
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

import evaluar_proyecto
from evaluar_proyecto import (archivos_python, detectar_comando_tests, ejecutar_tests,
                              evaluar, informe_texto, main, parsear_requisitos)
from tests.helpers import crear_proyecto

RAIZ_THINKER = Path(__file__).resolve().parent.parent


class TestEvaluadorDeProyectos(unittest.TestCase):
    def _fixture(self):
        return crear_proyecto(self, {
            "app.py": ("def main():\n"
                       "    return 1\n\n"
                       "if __name__ == '__main__':\n"
                       "    main()\n"),
            "leer.py": ("import requests\n\n\n"
                        "def bajar(url):\n"
                        "    try:\n"
                        "        return requests.get(url, timeout=5)\n"
                        "    except Exception:\n"
                        "        pass\n"),
            "requirements.txt": "requests==2.31.0\npandas\n",
            "README.md": "Documenta `app.py`; promete `fantasma.py`.\n",
            "tests/test_app.py": "def test_algo():\n    pass\n",
        })

    def test_detecta_los_defectos_plantados(self):
        informe = evaluar(self._fixture(), con_red=False)
        dims = informe["dimensiones"]

        self.assertFalse(dims["funcionalidades"]["criterios"]["f2_readme_vs_realidad"])
        self.assertTrue(any("fantasma.py" in h["descripcion"]
                            for h in dims["funcionalidades"]["hallazgos"]))

        self.assertFalse(dims["calidad"]["criterios"]["c3_sin_silencios"])
        self.assertTrue(any("leer.py:7" in h["evidencia"]
                            for h in dims["calidad"]["hallazgos"]))
        self.assertTrue(any("silencios detectados: 1" in nota
                            for nota in dims["calidad"]["notas"]))

        # La fixture planta un test sin aserciones (`def test_algo(): pass`).
        self.assertFalse(dims["calidad"]["criterios"]["c5_tests_con_aserciones"])
        self.assertTrue(any("tests/test_app.py:1" in h["evidencia"]
                            for h in dims["calidad"]["hallazgos"]))

        self.assertFalse(dims["vigencia"]["criterios"]["v1_dependencias_fijadas"])
        self.assertTrue(any("pandas" in h["descripcion"]
                            for h in dims["vigencia"]["hallazgos"]))

        self.assertFalse(dims["herramientas"]["criterios"]["h2_licencia"])

    def test_cada_mejora_trae_su_metrica_y_prioridad(self):
        informe = evaluar(self._fixture(), con_red=False)

        self.assertTrue(informe["mejoras"])
        for mejora in informe["mejoras"]:
            self.assertIn(mejora["prioridad"], ("alta", "media", "baja"))
            self.assertTrue(mejora["propuesta"])
            self.assertTrue(mejora["metrica"])
        prioridades = [m["prioridad"] for m in informe["mejoras"]]
        self.assertEqual(prioridades, sorted(prioridades, key=lambda p:
                                             {"alta": 0, "media": 1, "baja": 2}[p]))
        self.assertTrue(any(m["prioridad"] == "alta"
                            and "licencia" in m["propuesta"].lower()
                            for m in informe["mejoras"]))

    def test_las_propuestas_se_cuantifican_y_ordenan_por_esfuerzo(self):
        informe = evaluar(self._fixture(), con_red=False)

        for mejora in informe["mejoras"]:
            self.assertIn(mejora["esfuerzo"], ("bajo", "medio", "alto"))
            self.assertGreaterEqual(mejora["sitios"], 0)
            self.assertGreaterEqual(mejora["secuencia"], 1)
            self.assertIsInstance(mejora["datos_medidos"], dict)

        altas = [m for m in informe["mejoras"] if m["prioridad"] == "alta"]
        esfuerzos = [{"bajo": 0, "medio": 1, "alto": 2}[m["esfuerzo"]]
                     for m in altas]
        self.assertEqual(esfuerzos, sorted(esfuerzos))

    def test_el_lockfile_se_propone_despues_de_fijar_versiones(self):
        raiz = crear_proyecto(self, {
            "requirements.txt": "pandas\n",
            "app.py": "x = 1\n",
        })

        criterios = [m["criterio"] for m in evaluar(raiz, con_red=False)["mejoras"]]

        self.assertIn("v1_dependencias_fijadas", criterios)
        self.assertIn("v2_lockfile", criterios)
        self.assertLess(criterios.index("v1_dependencias_fijadas"),
                        criterios.index("v2_lockfile"))

    def test_plan_texto_resume_por_prioridad(self):
        from evaluar_proyecto import plan_texto

        resumen = "\n".join(plan_texto(evaluar(self._fixture(), con_red=False)))

        self.assertIn("Plan de mejora:", resumen)
        self.assertIn("alta", resumen)

    def test_sintesis_llm_marca_el_respaldo_de_cada_propuesta(self):
        from evaluar_proyecto import sintetizar_con_llm
        from tests.helpers import StubLLM

        respuesta = ('{"propuestas": [{"dimension": "calidad", "propuesta": "unificar", '
                     '"por_que": "x", "evidencia": "requirements.txt", '
                     '"como_verificar": "y"}, '
                     '{"dimension": "calidad", "propuesta": "inventada", '
                     '"por_que": "x", "evidencia": "otro/archivo.py:1", '
                     '"como_verificar": "y"}], '
                     '"preguntas_abiertas": ["¿está mantenida la dependencia?"]}')

        sintesis = sintetizar_con_llm(evaluar(self._fixture(), con_red=False),
                                      StubLLM(lambda p: respuesta))

        self.assertEqual(len(sintesis["propuestas"]), 2)
        self.assertTrue(sintesis["propuestas"][0]["con_respaldo"])
        self.assertFalse(sintesis["propuestas"][1]["con_respaldo"])
        self.assertEqual(sintesis["sin_respaldo"], 1)
        self.assertEqual(sintesis["preguntas_abiertas"],
                         ["¿está mantenida la dependencia?"])

    def test_sintesis_llm_acepta_el_contrato_antiguo_de_array(self):
        from evaluar_proyecto import sintetizar_con_llm
        from tests.helpers import StubLLM

        respuesta = '[{"propuesta": "p", "evidencia": "requirements.txt"}]'

        sintesis = sintetizar_con_llm(evaluar(self._fixture(), con_red=False),
                                      StubLLM(lambda p: respuesta))

        self.assertEqual(len(sintesis["propuestas"]), 1)
        self.assertEqual(sintesis["preguntas_abiertas"], [])

    def test_investigar_preguntas_cita_fuentes_y_declara_fallos(self):
        from evaluar_proyecto import investigar_preguntas
        from tests.helpers import StubSearch

        search = StubSearch([{"title": "Doc oficial", "url": "https://ejemplo.invalid/d"}])
        con_fuentes = investigar_preguntas(["¿cuál es la práctica recomendada?"], search)
        self.assertEqual(con_fuentes[0]["fuentes"],
                         [{"titulo": "Doc oficial", "url": "https://ejemplo.invalid/d"}])
        self.assertFalse(con_fuentes[0]["sin_resultados"])

        class BuscadorRoto:
            def search(self, query, max_results=5):
                raise RuntimeError("sin red")

        con_error = investigar_preguntas(["¿y esto?"], BuscadorRoto())
        self.assertIn("RuntimeError", con_error[0]["error"])

    def test_sintesis_llm_sin_array_eleva_value_error(self):
        from evaluar_proyecto import sintetizar_con_llm
        from tests.helpers import StubLLM

        with self.assertRaises(ValueError):
            sintetizar_con_llm(evaluar(self._fixture(), con_red=False),
                               StubLLM(lambda p: "no json"))

    def test_sintesis_llm_ignora_elementos_que_no_son_objetos(self):
        from evaluar_proyecto import sintetizar_con_llm
        from tests.helpers import StubLLM

        respuesta = '["texto suelto", {"propuesta": "ok", "evidencia": ""}]'

        sintesis = sintetizar_con_llm(evaluar(self._fixture(), con_red=False),
                                      StubLLM(lambda p: respuesta))

        self.assertEqual(len(sintesis["propuestas"]), 1)
        self.assertFalse(sintesis["propuestas"][0]["con_respaldo"])

    def test_evaluar_con_llm_incluye_la_sintesis_y_sin_llm_no(self):
        from tests.helpers import StubLLM

        raiz = self._fixture()
        respuesta = ('[{"dimension": "calidad", "propuesta": "p", "por_que": "q", '
                     '"evidencia": "requirements.txt", "como_verificar": "v"}]')
        llm = StubLLM(lambda p: respuesta)

        con = evaluar(raiz, con_red=False, llm=llm)
        sin = evaluar(raiz, con_red=False)

        self.assertIn("sintesis_llm", con)
        self.assertNotIn("sintesis_llm", sin)
        self.assertIn("INFORME MEDIDO", llm.prompts[0])
        self.assertIn(str(raiz), llm.prompts[0])

    def test_error_de_red_se_declara_con_su_motivo(self):
        import urllib.error
        from unittest.mock import patch

        from evaluar_proyecto import licencia_pypi, ultima_version_pypi

        with patch("evaluar_proyecto.urllib.request.urlopen",
                   side_effect=urllib.error.URLError("sin ruta al host")):
            licencia = licencia_pypi("x")
            version = ultima_version_pypi("x")

        self.assertIn("URLError", licencia["error"])
        self.assertIn("URLError", version["error"])
        self.assertIsNone(version["version"])
        self.assertFalse(licencia["libre"])

    def test_dependencia_no_verificable_falla_v4_y_declara_el_motivo(self):
        import urllib.error
        from unittest.mock import patch

        raiz = crear_proyecto(self, {"requirements.txt": "requests==2.31.0\n"})

        with patch("evaluar_proyecto.urllib.request.urlopen",
                   side_effect=urllib.error.URLError("sin red")):
            informe = evaluar(raiz, con_red=True)

        vigencia = informe["dimensiones"]["vigencia"]
        self.assertFalse(vigencia["criterios"]["v4_dependencias_al_dia"])
        self.assertTrue(any("URLError" in h["descripcion"]
                            for h in vigencia["hallazgos"]))

    def test_no_cambia_el_proyecto_evaluado(self):
        raiz = self._fixture()
        antes = {p: p.stat().st_mtime_ns for p in raiz.rglob("*")}

        evaluar(raiz, con_red=False)

        despues = {p: p.stat().st_mtime_ns for p in raiz.rglob("*")}
        self.assertEqual(antes, despues)

    def test_informe_texto_incluye_dimensiones_mejoras_y_no_verificado(self):
        texto = "\n".join(informe_texto(evaluar(self._fixture(), con_red=False)))

        for dimension in ("FUNCIONALIDADES", "CALIDAD", "VIGENCIA",
                          "HERRAMIENTAS", "INTELIGENCIA", "EFICIENCIA"):
            self.assertIn(dimension, texto)
        self.assertIn("MEJORAS PROPUESTAS", texto)
        self.assertIn("verificación:", texto)
        self.assertIn("No verificado:", texto)

    def test_ruta_inexistente_eleva_value_error(self):
        with self.assertRaises(ValueError):
            evaluar(Path("/ruta/que/no/existe"), con_red=False)

    def test_cli_sin_red_imprime_el_informe(self):
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            codigo = main([str(self._fixture()), "--sin-red"])

        texto = salida.getvalue()
        self.assertEqual(codigo, 0)
        self.assertIn("EVALUACIÓN DE PROYECTO", texto)
        self.assertIn("GLOBAL NO COMPARABLE", texto)

    def test_cli_con_ruta_inexistente_devuelve_codigo_2(self):
        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            codigo = main(["/ruta/que/no/existe"])

        self.assertEqual(codigo, 2)
        self.assertIn("ERROR:", error.getvalue())

    def test_archivos_python_no_excluye_el_proyecto_por_un_padre_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp) / "build" / "proyecto"
            (raiz / "pkg").mkdir(parents=True)
            (raiz / "pkg" / "app.py").write_text("x = 1\n")
            (raiz / "build").mkdir()
            (raiz / "build" / "generado.py").write_text("y = 2\n")

            encontrados = archivos_python(raiz)

        self.assertEqual([p.name for p in encontrados], ["app.py"])


class TestDependenciasDelEvaluador(unittest.TestCase):
    """Parseo de manifiestos: directivas de pip y bloques ajenos a [project]."""

    def test_requirements_ignora_directivas_urls_y_referencias(self):
        from evaluar_proyecto import _dependencias

        raiz = crear_proyecto(self, {
            "requirements.txt": (
                "-r base.txt\n"
                "--index-url https://pypi.org/simple\n"
                "-e .\n"
                "https://example.com/pkg.whl\n"
                "paquete @ https://example.com/paquete.whl\n"
                "requests[socks]==2.31.0\n"
                "pandas>=2\n"),
        })

        deps = _dependencias(raiz)

        self.assertEqual(
            [(d["nombre"], d["operador"], d["version"]) for d in deps],
            [("requests", "==", "2.31.0"), ("pandas", ">=", "2")])

    def test_pyproject_lee_project_dependencies_y_no_listas_de_herramientas(self):
        from evaluar_proyecto import _dependencias

        raiz = crear_proyecto(self, {
            "pyproject.toml": (
                "[tool.herramienta]\n"
                "dependencies = ['falsa==1.0']\n\n"
                "[project]\n"
                "name = 'x'\n"
                "version = '0.1.0'\n"
                "dependencies = [\n"
                "  'requests[socks]>=2.31',\n"
                '  "PyYAML==6.0.3",\n'
                "]\n"),
        })

        deps = _dependencias(raiz)

        self.assertEqual([d["nombre"] for d in deps], ["requests", "pyyaml"])
        self.assertEqual(deps[0]["operador"], ">=")
        self.assertEqual(deps[1]["operador"], "==")

    def test_version_vacia_no_cuenta_como_fijada(self):
        raiz = crear_proyecto(self, {"requirements.txt": "requests==\n"})

        vigencia = evaluar(raiz, con_red=False)["dimensiones"]["vigencia"]

        self.assertFalse(vigencia["criterios"]["v1_dependencias_fijadas"])

    def test_v4_sin_versiones_fijadas_ni_lock_no_finge_haber_comprobado(self):
        raiz = crear_proyecto(self, {
            "requirements.txt": "pandas>=2\nrequests\n",
        })

        with patch("evaluar_proyecto.ultima_version_pypi") as pypi, \
                patch("evaluar_proyecto.licencia_pypi",
                      return_value={"licencia": "MIT", "libre": True,
                                    "error": ""}):
            informe = evaluar(raiz, con_red=True)

        pypi.assert_not_called()
        vigencia = informe["dimensiones"]["vigencia"]
        self.assertFalse(vigencia["criterios"]["v4_dependencias_al_dia"])
        self.assertTrue(any("sin versiones (== o lock)" in nota
                            for nota in vigencia["notas"]))
        self.assertTrue(any(h["tipo_evidencia"] == "unverified"
                            for h in vigencia["hallazgos"]))

    def test_v4_usa_la_version_resuelta_por_uv_lock(self):
        raiz = crear_proyecto(self, {
            "pyproject.toml": ("[project]\n"
                               "name = 'x'\n"
                               "version = '0.1.0'\n"
                               "dependencies = ['requests>=2.31']\n"),
            "uv.lock": ("[[package]]\n"
                        "name = 'requests'\n"
                        "version = '2.31.0'\n"),
        })

        with patch("evaluar_proyecto.ultima_version_pypi",
                   return_value={"version": "2.31.0", "error": ""}) as pypi, \
                patch("evaluar_proyecto.licencia_pypi",
                      return_value={"licencia": "Apache-2.0", "libre": True,
                                    "error": ""}):
            informe = evaluar(raiz, con_red=True)

        pypi.assert_called_once_with("requests")
        self.assertTrue(informe["dimensiones"]["vigencia"]
                        ["criterios"]["v4_dependencias_al_dia"])

    def test_poetry_version_exacta_no_inventa_paquete(self):
        """Poetry admite `requests = "2.28.0"` (versión exacta a secas):
        concatenarla tal cual creaba el paquete ficticio `requests2.28.0`
        (P0.2), que con red se habría consultado en PyPI."""
        from evaluar_proyecto import _dependencias

        raiz = crear_proyecto(self, {
            "pyproject.toml": (
                "[tool.poetry]\n"
                "name = 'x'\n\n"
                "[tool.poetry.dependencies]\n"
                "python = '^3.11'\n"
                "requests = '2.28.0'\n"
                "click = '^8.1'\n"
                "rich = '~13.7'\n\n"
                "[tool.poetry.group.dev.dependencies]\n"
                "pytest = '8.0.0'\n"),
        })

        deps = {d["nombre"]: d for d in _dependencias(raiz)}

        self.assertNotIn("requests2.28.0", deps)
        self.assertEqual((deps["requests"]["operador"], deps["requests"]["version"]),
                         ("==", "2.28.0"))
        self.assertTrue(deps["requests"]["fijada"])
        self.assertEqual(deps["click"]["nombre"], "click")
        self.assertEqual(deps["rich"]["nombre"], "rich")
        self.assertEqual((deps["pytest"]["operador"], deps["pytest"]["version"]),
                         ("==", "8.0.0"))
        self.assertNotIn("python", deps)

    def test_requirements_txt_solo_es_lock_si_esta_fijado(self):
        """Un requirements/*.txt con líneas sin fijar (`requests>=2.0`) NO es
        un lock: tratarlo como tal afirmaba reproducibilidad falsa (P0.1).
        Solo cuenta si la mayoría de requisitos tienen `==` o `--hash=`."""
        from evaluar_proyecto import _es_lock

        raiz = crear_proyecto(self, {
            "requirements/fijado.txt": ("requests==2.31.0 \\\n"
                                        "    --hash=sha256:aaaa\n"
                                        "click==8.1.7\n"),
            "requirements/sin_fijar.txt": "requests>=2.0\nclick\n",
            "requirements/a_medias.txt": "requests==2.31.0\nclick\n",
        })

        self.assertTrue(_es_lock(raiz / "requirements" / "fijado.txt"))
        self.assertFalse(_es_lock(raiz / "requirements" / "sin_fijar.txt"))
        self.assertFalse(_es_lock(raiz / "requirements" / "a_medias.txt"))


class TestCriteriosAnadidos(unittest.TestCase):
    """h6 (imports declarados), c5 (tests con aserciones) y h7 (decisiones)."""

    def test_h6_detecta_import_de_terceros_sin_declarar(self):
        raiz = crear_proyecto(self, {
            "app.py": "import numpy\n\n\ndef main():\n    return numpy\n",
            "requirements.txt": "requests==2.31.0\n",
        })

        herramientas = evaluar(raiz, con_red=False)["dimensiones"]["herramientas"]

        self.assertFalse(herramientas["criterios"]["h6_imports_declarados"])
        self.assertTrue(any("app.py:1" in h["evidencia"] and "numpy" in h["descripcion"]
                            for h in herramientas["hallazgos"]))
        self.assertTrue(any(m["criterio"] == "h6_imports_declarados"
                            for m in evaluar(raiz, con_red=False)["mejoras"]))

    def test_h6_pasa_con_el_import_declarado(self):
        raiz = crear_proyecto(self, {
            "app.py": "import numpy\n",
            "requirements.txt": "numpy==1.26.0\n",
        })

        herramientas = evaluar(raiz, con_red=False)["dimensiones"]["herramientas"]

        self.assertTrue(herramientas["criterios"]["h6_imports_declarados"])

    def test_h6_reconoce_modulos_de_pywin32(self):
        raiz = crear_proyecto(self, {
            "app.py": "import win32api\n",
            "pyproject.toml": ('[project]\nname = "x"\nversion = "0.1.0"\n'
                               'dependencies = ["pywin32"]\n'),
        })

        herramientas = evaluar(raiz, con_red=False)["dimensiones"]["herramientas"]

        self.assertTrue(herramientas["criterios"]["h6_imports_declarados"])

    def test_h6_reconoce_pil_docx_y_pptx(self):
        raiz = crear_proyecto(self, {
            "app.py": "import PIL\nimport docx\nimport pptx\n",
            "pyproject.toml": ('[project]\nname = "x"\nversion = "0.1.0"\n'
                               'dependencies = ["pillow", "python-docx", '
                               '"python-pptx"]\n'),
        })

        herramientas = evaluar(raiz, con_red=False)["dimensiones"]["herramientas"]

        self.assertTrue(herramientas["criterios"]["h6_imports_declarados"])

    def test_archivos_python_ignora_venvs_y_temporales(self):
        raiz = crear_proyecto(self, {
            "app.py": "x = 1\n",
            ".venv-docs/a.py": "x = 1\n",
            "venv-old/b.py": "x = 1\n",
            "pytest-of-1/c.py": "x = 1\n",
            "paquete.egg-info/d.py": "x = 1\n",
            "exe/e.py": "x = 1\n",
        })

        nombres = [p.relative_to(raiz).as_posix()
                   for p in archivos_python(raiz)]

        self.assertEqual(nombres, ["app.py", "exe/e.py"])

    def test_cli_ignorar_excluye_directorio(self):
        raiz = crear_proyecto(self, {
            "app.py": "x = 1\n",
            "exe/malo.py": ("try:\n"
                            "    x = 1\n"
                            "except Exception:\n"
                            "    pass\n"),
        })
        antes = set(evaluar_proyecto.IGNORAR)
        try:
            salida = io.StringIO()
            with contextlib.redirect_stdout(salida):
                codigo = main([str(raiz), "--sin-red", "--json",
                               "--ignorar", "exe"])
            datos = json.loads(salida.getvalue())
        finally:
            evaluar_proyecto.IGNORAR.clear()
            evaluar_proyecto.IGNORAR.update(antes)

        self.assertEqual(codigo, 0)
        self.assertEqual(datos["archivos_python"], 1)

    def test_h6_stdlib_y_modulos_locales_no_necesitan_declaracion(self):
        raiz = crear_proyecto(self, {
            "app.py": "import json\nimport helper\n",
            "helper.py": "X = 1\n",
        })

        herramientas = evaluar(raiz, con_red=False)["dimensiones"]["herramientas"]

        self.assertTrue(herramientas["criterios"]["h6_imports_declarados"])

    def test_c5_test_con_asserts_o_raises_pasa(self):
        raiz = crear_proyecto(self, {
            "tests/test_bien.py": ("import unittest\n\n\n"
                                   "class T(unittest.TestCase):\n"
                                   "    def test_uno(self):\n"
                                   "        self.assertEqual(1, 1)\n"
                                   "    def test_dos(self):\n"
                                   "        with self.assertRaises(ValueError):\n"
                                   "            raise ValueError\n"),
        })

        calidad = evaluar(raiz, con_red=False)["dimensiones"]["calidad"]

        self.assertTrue(calidad["criterios"]["c5_tests_con_aserciones"])

    def test_c5_test_vacio_o_sin_asercion_falla_con_evidencia(self):
        raiz = crear_proyecto(self, {
            "tests/test_debil.py": ("def test_vacio():\n"
                                    "    pass\n\n\n"
                                    "def test_imprime():\n"
                                    "    print(1 + 1)\n"),
        })

        calidad = evaluar(raiz, con_red=False)["dimensiones"]["calidad"]

        self.assertFalse(calidad["criterios"]["c5_tests_con_aserciones"])
        evidencias = [h["evidencia"] for h in calidad["hallazgos"]]
        self.assertTrue(any("tests/test_debil.py:1" in e for e in evidencias))
        self.assertTrue(any("tests/test_debil.py:5" in e for e in evidencias))

    def test_h7_sin_registro_de_decisiones_falla(self):
        raiz = crear_proyecto(self, {"app.py": "x = 1\n"})

        herramientas = evaluar(raiz, con_red=False)["dimensiones"]["herramientas"]

        self.assertFalse(herramientas["criterios"]["h7_decisiones_documentadas"])
        self.assertTrue(any("registro de decisiones" in h["descripcion"]
                            for h in herramientas["hallazgos"]))

    def test_h7_con_doc_de_lecciones_o_decision_log_pasa(self):
        con_doc = crear_proyecto(self, {"app.py": "x = 1\n",
                                        "docs/LECCIONES.md": "# lecciones\n"})
        con_log = crear_proyecto(self, {"app.py": "decision_log = []\n"})

        self.assertTrue(evaluar(con_doc, con_red=False)["dimensiones"]["herramientas"]
                        ["criterios"]["h7_decisiones_documentadas"])
        self.assertTrue(evaluar(con_log, con_red=False)["dimensiones"]["herramientas"]
                        ["criterios"]["h7_decisiones_documentadas"])


class TestEjecucionDeTestsYLicencias(unittest.TestCase):
    """Ejecución opt-in del comando DECLARADO y licencias de dependencias."""

    def test_sin_flag_no_ejecuta_nada_y_lo_declara(self):
        raiz = crear_proyecto(self, {
            "tests/test_que_escribe.py": (
                "import unittest\n\n\n"
                "class T(unittest.TestCase):\n"
                "    def test_escribe(self):\n"
                "        open('escrito.txt', 'w').write('x')\n"),
        })

        informe = evaluar(raiz, con_red=False)

        self.assertNotIn("c1b_suite_pasa",
                         informe["dimensiones"]["calidad"]["criterios"])
        self.assertFalse((raiz / "escrito.txt").exists())
        self.assertTrue(any("--ejecutar-tests" in n
                            for n in informe["no_verificado"]))

    def test_ejecuta_la_suite_declarada_y_la_reporta(self):
        raiz = crear_proyecto(self, {
            "tests/test_ok.py": ("import unittest\n\n\n"
                                 "class T(unittest.TestCase):\n"
                                 "    def test_ok(self):\n"
                                 "        self.assertTrue(True)\n"),
        })

        informe = evaluar(raiz, con_red=False, ejecutar_tests_flag=True)
        calidad = informe["dimensiones"]["calidad"]

        self.assertTrue(calidad["criterios"]["c1b_suite_pasa"])
        self.assertTrue(any("unittest" in nota for nota in calidad["notas"]))

    def test_suite_que_falla_es_hallazgo_alto(self):
        raiz = crear_proyecto(self, {
            "tests/test_mal.py": ("import unittest\n\n\n"
                                  "class T(unittest.TestCase):\n"
                                  "    def test_falla(self):\n"
                                  "        self.assertEqual(1, 2)\n"),
        })

        informe = evaluar(raiz, con_red=False, ejecutar_tests_flag=True)

        self.assertFalse(informe["dimensiones"]["calidad"]["criterios"]["c1b_suite_pasa"])
        self.assertTrue(any(h["severidad"] == "alta" and "NO pasa" in h["descripcion"]
                            for h in informe["dimensiones"]["calidad"]["hallazgos"]))
        self.assertTrue(any(m["criterio"] == "c1b_suite_pasa"
                            for m in informe["mejoras"]))

    def test_el_target_del_makefile_tiene_prioridad(self):
        raiz = crear_proyecto(self, {
            "Makefile": "test:\n\tpython3 -m unittest discover -s tests -q\n",
            "tests/test_ok.py": ("import unittest\n\n\n"
                                 "class T(unittest.TestCase):\n"
                                 "    def test_ok(self):\n"
                                 "        self.assertTrue(True)\n"),
        })

        with patch("evaluar_proyecto.shutil.which", return_value="/usr/bin/make"):
            deteccion = detectar_comando_tests(raiz)

        self.assertEqual(deteccion["comando"], ["make", "test"])
        self.assertIn("Makefile", deteccion["origen"])

    def test_prosa_con_nombres_de_runners_no_es_comando(self):
        """Regresión (auditoría 2026-10-23): "django test runner" producía el
        comando basura ['go','test','runner','o','detox.'] y "detox en iOS"
        producía ['tox','en','iOS.']. La prosa NO es un comando declarado."""
        raiz = crear_proyecto(self, {
            "README.md": ("Este proyecto usa el django test runner o detox.\n"
                          "Para dispositivos: detox en iOS.\n"),
        })

        self.assertIsNone(detectar_comando_tests(raiz))

    def test_comandos_validos_en_readme_siguen_detectandose(self):
        raiz = crear_proyecto(self, {
            "README.md": "Ejecuta las pruebas:\n\n    go test ./...\n",
        })

        deteccion = detectar_comando_tests(raiz)

        self.assertEqual(deteccion["comando"], ["go", "test", "./..."])
        self.assertEqual(deteccion["origen"], "README.md")

    def test_pytest_declarado_en_readme_se_detecta(self):
        raiz = crear_proyecto(self, {
            "README.md": "Tests: `pytest -q`\n",
        })

        deteccion = detectar_comando_tests(raiz)

        self.assertEqual(deteccion["comando"], ["pytest", "-q"])

    def test_sin_make_usa_el_runner_python_disponible(self):
        raiz = crear_proyecto(self, {
            "Makefile": "test:\n\tpython3 -m unittest discover -s tests -q\n",
            "tests/test_ok.py": ("import unittest\n\n\n"
                                 "class T(unittest.TestCase):\n"
                                 "    def test_ok(self):\n"
                                 "        self.assertTrue(True)\n"),
        })

        with patch("evaluar_proyecto.shutil.which", return_value=None):
            informe = evaluar(raiz, con_red=False, ejecutar_tests_flag=True)

        calidad = informe["dimensiones"]["calidad"]
        self.assertTrue(calidad["criterios"]["c1b_suite_pasa"])
        self.assertTrue(any("unittest" in nota for nota in calidad["notas"]))

    def test_licencias_omitidas_sin_red(self):
        informe = evaluar(crear_proyecto(self, {"requirements.txt": "requests==2.31.0\n"}),
                          con_red=False)

        self.assertNotIn("h5_licencias_libres",
                         informe["dimensiones"]["herramientas"]["criterios"])
        self.assertTrue(any("OMITIDAS" in nota
                            for nota in informe["dimensiones"]["herramientas"]["notas"]))

    def test_licencias_libres_verificadas(self):
        with patch("evaluar_proyecto.licencia_pypi",
                   return_value={"licencia": "Apache-2.0", "libre": True}), \
                patch("evaluar_proyecto.ultima_version_pypi",
                      return_value={"version": "2.31.0", "error": ""}):
            informe = evaluar(crear_proyecto(self, {"requirements.txt": "requests==2.31.0\n"}),
                              con_red=True)

        self.assertTrue(informe["dimensiones"]["herramientas"]
                        ["criterios"]["h5_licencias_libres"])

    def test_dependencia_sin_licencia_libre_se_reporta(self):
        with patch("evaluar_proyecto.licencia_pypi",
                   return_value={"licencia": "Propietaria", "libre": False}), \
                patch("evaluar_proyecto.ultima_version_pypi",
                      return_value={"version": "1.0", "error": ""}):
            informe = evaluar(crear_proyecto(self, {"requirements.txt": "rara==1.0\n"}),
                              con_red=True)

        herramientas = informe["dimensiones"]["herramientas"]
        self.assertFalse(herramientas["criterios"]["h5_licencias_libres"])
        self.assertTrue(any("Propietaria" in h["descripcion"]
                            for h in herramientas["hallazgos"]))

    def test_licencias_no_runtime_se_reportan_fuera_del_score(self):
        raiz = crear_proyecto(self, {
            "pyproject.toml": (
                '[project]\nname = "demo"\nversion = "0.1.0"\n'
                'dependencies = ["requests==2.31.0"]\n'
                '[project.optional-dependencies]\n'
                'dev = ["pytest==8.0.0"]\n'),
            "demo.py": "import requests\n",
        })

        def fake_licencia(nombre, timeout=15):
            if nombre == "requests":
                return {"licencia": "Apache-2.0", "libre": True,
                        "fuente": "license_expression", "error": ""}
            return {"licencia": "Propietaria", "libre": False,
                    "fuente": "license", "error": ""}

        with patch("evaluar_proyecto.licencia_pypi", side_effect=fake_licencia), \
                patch("evaluar_proyecto.ultima_version_pypi",
                      return_value={"version": "2.31.0", "error": ""}):
            informe = evaluar(raiz, con_red=True)

        self.assertTrue(informe["dimensiones"]["herramientas"]
                        ["criterios"]["h5_licencias_libres"])
        extra = {entrada["nombre"]: entrada
                 for entrada in informe["licencias_no_runtime"]}
        self.assertEqual(extra["pytest"]["ambito"], "dev")
        self.assertFalse(extra["pytest"]["libre"])
        self.assertEqual(extra["pytest"]["procedencia"], "real")
        self.assertIn("LICENCIAS NO RUNTIME", "\n".join(informe_texto(informe)))

    def test_licencias_no_runtime_sin_red_son_unverified(self):
        raiz = crear_proyecto(self, {
            "pyproject.toml": (
                '[project]\nname = "demo"\nversion = "0.1.0"\n'
                'dependencies = ["requests==2.31.0"]\n'
                '[project.optional-dependencies]\n'
                'dev = ["pytest==8.0.0"]\n'),
            "demo.py": "import requests\n",
        })

        informe = evaluar(raiz, con_red=False)

        extra = {entrada["nombre"]: entrada
                 for entrada in informe["licencias_no_runtime"]}
        self.assertIsNone(extra["pytest"]["libre"])
        self.assertEqual(extra["pytest"]["procedencia"], "unverified")
        self.assertIn("--sin-red", extra["pytest"]["fuente"])
        self.assertNotIn("h5_licencias_libres",
                         informe["dimensiones"]["herramientas"]["criterios"])

    def test_hallazgo_no_verificado_lleva_marcador(self):
        with patch("evaluar_proyecto.ultima_version_pypi",
                   return_value={"version": "", "error": "timeout"}), \
                patch("evaluar_proyecto.licencia_pypi",
                      return_value={"licencia": "MIT", "libre": True,
                                    "error": ""}):
            informe = evaluar(
                crear_proyecto(self, {"requirements.txt": "requests==2.31.0\n"}),
                con_red=True)

        vigencia = informe["dimensiones"]["vigencia"]
        hallazgo = next(h for h in vigencia["hallazgos"]
                        if "No se pudo comprobar" in h["descripcion"])
        self.assertEqual(hallazgo["tipo_evidencia"], "unverified")
        self.assertGreaterEqual(informe["evidencia"]["unverified"], 1)
        self.assertGreater(informe["evidencia"]["verified-real"], 0)
        self.assertIn("[UNVERIFIED]", "\n".join(informe_texto(informe)))


class TestMejorasV2(unittest.TestCase):
    """Regresiones del audit 2026-10-21: menos falsos positivos, más cobertura."""

    def test_h6_ignora_docs_tests_y_ejemplos(self):
        raiz = crear_proyecto(self, {
            "pkg/__init__.py": "",
            "pkg/app.py": "import numpy\n",
            "tests/test_app.py": "import pandas\n",
            "docs_src/example.py": "import yaml\n",
            "requirements.txt": "numpy==1.26.0\n",
        })

        herramientas = evaluar(raiz, con_red=False)["dimensiones"]["herramientas"]

        self.assertTrue(herramientas["criterios"]["h6_imports_declarados"])
        descripciones = " ".join(h["descripcion"] for h in herramientas["hallazgos"])
        self.assertNotIn("pandas", descripciones)
        self.assertNotIn("yaml", descripciones)

    def test_h6_ignora_import_opcional_y_type_checking(self):
        raiz = crear_proyecto(self, {
            "pkg/__init__.py": "",
            "pkg/app.py": (
                "from typing import TYPE_CHECKING\n"
                "if TYPE_CHECKING:\n"
                "    import pandas\n"
                "try:\n"
                "    import yaml\n"
                "except ImportError:\n"
                "    yaml = None\n"),
        })

        herramientas = evaluar(raiz, con_red=False)["dimensiones"]["herramientas"]

        self.assertTrue(herramientas["criterios"]["h6_imports_declarados"])
        self.assertFalse(any("pandas" in h["descripcion"]
                             or "yaml" in h["descripcion"]
                             for h in herramientas["hallazgos"]))

    def test_h6_reconoce_layout_src_y_pyproject_anidado(self):
        raiz = crear_proyecto(self, {
            "src/mipkg/__init__.py": "",
            "src/mipkg/app.py": "from mipkg.helper import X\n",
            "src/mipkg/helper.py": "X = 1\n",
            "pyproject.toml": ("[project]\n"
                               "name = 'mipkg'\n"
                               "version = '0.1.0'\n"
                               "dependencies = []\n"),
        })

        herramientas = evaluar(raiz, con_red=False)["dimensiones"]["herramientas"]

        self.assertTrue(herramientas["criterios"]["h6_imports_declarados"])

    def test_h6_lee_setup_cfg(self):
        raiz = crear_proyecto(self, {
            "app.py": "import numpy\n",
            "setup.cfg": ("[options]\n"
                          "install_requires =\n"
                          "    numpy==1.26.0\n"),
        })

        herramientas = evaluar(raiz, con_red=False)["dimensiones"]["herramientas"]

        self.assertTrue(herramientas["criterios"]["h6_imports_declarados"])

    def test_licencia_pypi_prefiere_license_expression_de_pep639(self):
        from evaluar_proyecto import licencia_pypi

        class Respuesta:
            def __enter__(self):
                return io.BytesIO(json.dumps({"info": {
                    "license_expression": "MIT OR Apache-2.0",
                    "license": "",
                    "classifiers": [],
                }}).encode())

            def __exit__(self, *args):
                return False

        with patch("evaluar_proyecto.urllib.request.urlopen",
                   return_value=Respuesta()):
            info = licencia_pypi("x")

        self.assertTrue(info["libre"])
        self.assertEqual(info["fuente"], "license_expression")
        self.assertIn("MIT", info["licencia"])

    def test_licencia_pypi_unknown_no_es_no_libre(self):
        from evaluar_proyecto import licencia_pypi

        class Respuesta:
            def __enter__(self):
                return io.BytesIO(json.dumps({"info": {
                    "license_expression": "",
                    "license": "",
                    "classifiers": [],
                }}).encode())

            def __exit__(self, *args):
                return False

        with patch("evaluar_proyecto.urllib.request.urlopen",
                   return_value=Respuesta()):
            info = licencia_pypi("x")

        self.assertIsNone(info["libre"])

    def test_licencia_spdx_mixta_con_licenseref_es_no_verificable(self):
        """`MIT AND LicenseRef-X` mezcla una licencia libre conocida con una
        referencia no verificable: no es «no libre», es None (antes se
        clasificaba entera como no libre)."""
        from evaluar_proyecto import _es_licencia_libre

        self.assertIsNone(_es_licencia_libre("MIT AND LicenseRef-X"))
        self.assertIsNone(_es_licencia_libre("Apache-2.0 OR LicenseRef-Prop"))
        self.assertFalse(_es_licencia_libre("LicenseRef-X"))
        self.assertFalse(_es_licencia_libre("Proprietary"))
        self.assertTrue(_es_licencia_libre("MIT OR Apache-2.0"))

    def test_c5_no_marca_endpoint_anidado_ni_helper(self):
        raiz = crear_proyecto(self, {
            "tests/test_api.py": (
                "def test_endpoint(app):\n"
                "    def endpoint():\n"
                "        return 1\n"
                "    app.get('/')\n"),
            "tests/test_helper.py": (
                "def helper(x):\n"
                "    assert x == 1\n\n"
                "def test_helper():\n"
                "    helper(1)\n"),
            "tests/test_prop.py": (
                "from hypothesis import given, strategies as st\n\n"
                "@given(st.integers())\n"
                "def test_prop(x):\n"
                "    pass\n"),
        })

        calidad = evaluar(raiz, con_red=False)["dimensiones"]["calidad"]

        self.assertTrue(calidad["criterios"]["c5_tests_con_aserciones"])
        self.assertFalse(any(h["criterio"] == "c5_tests_con_aserciones"
                             for h in calidad["hallazgos"]))

    def test_c5_marca_pass_no_op(self):
        raiz = crear_proyecto(self, {
            "tests/test_vacio.py": "def test_nada():\n    pass\n",
        })

        calidad = evaluar(raiz, con_red=False)["dimensiones"]["calidad"]

        self.assertFalse(calidad["criterios"]["c5_tests_con_aserciones"])
        self.assertTrue(any("Test no-op" in h["descripcion"]
                            for h in calidad["hallazgos"]))

    def test_c3_ignora_import_opcional_y_tests(self):
        raiz = crear_proyecto(self, {
            "pkg/__init__.py": "",
            "pkg/app.py": ("try:\n"
                           "    import yaml\n"
                           "    X = yaml.safe_load('')\n"
                           "except ImportError:\n"
                           "    pass\n"),
            "tests/test_silencio.py": ("try:\n"
                                       "    import x\n"
                                       "except Exception:\n"
                                       "    pass\n"),
        })

        calidad = evaluar(raiz, con_red=False)["dimensiones"]["calidad"]

        self.assertTrue(calidad["criterios"]["c3_sin_silencios"])

    def test_c3_ignora_scripts_locales_de_depuracion(self):
        raiz = crear_proyecto(self, {
            "app.py": "def main():\n    return 1\n",
            "_local_debug/check.py": ("try:\n"
                                      "    import x\n"
                                      "except Exception:\n"
                                      "    pass\n"),
        })

        calidad = evaluar(raiz, con_red=False)["dimensiones"]["calidad"]

        self.assertTrue(calidad["criterios"]["c3_sin_silencios"])
        self.assertFalse(any("_local_debug" in h["evidencia"]
                             for h in calidad["hallazgos"]))
        self.assertNotIn("check.py",
                         [p.name for p in archivos_python(raiz)])

    def test_dependencias_lee_requirements_anidado_y_pep735(self):
        from evaluar_proyecto import _dependencias

        raiz = crear_proyecto(self, {
            "requirements/test.in": "pytest==8.0.0\n",
            "pyproject.toml": ("[project]\n"
                               "name = 'x'\n"
                               "version = '0.1.0'\n"
                               "dependencies = ['requests>=2']\n"
                               "[project.optional-dependencies]\n"
                               "docs = ['sphinx>=7']\n"
                               "[dependency-groups]\n"
                               "test = ['pytest>=8']\n"),
        })

        deps = {(d["nombre"], d["ambito"]) for d in _dependencias(raiz)}

        self.assertIn(("requests", "runtime"), deps)
        self.assertIn(("sphinx", "docs"), deps)
        self.assertIn(("pytest", "test"), deps)

    def test_proyecto_js_no_se_puntua_por_criterios_python(self):
        raiz = crear_proyecto(self, {
            "package.json": json.dumps({
                "name": "x",
                "main": "src/index.js",
                "scripts": {"test": "node --test"},
                "devDependencies": {"eslint": "^8.0.0"},
            }),
            "package-lock.json": json.dumps({
                "lockfileVersion": 3,
                "packages": {"": {}, "node_modules/eslint": {"version": "8.0.0"}},
            }),
            "src/index.js": ("export function suma(a, b) {\n"
                             "  return a + b;\n"
                             "}\n"),
            "test/a.test.js": ("import { suma } from '../src/index.js';\n"
                               "assert.equal(suma(1, 2), 3);\n"
                               "assert.equal(suma(2, 2), 4);\n"),
            "test/b.test.js": ("import { suma } from '../src/index.js';\n"
                               "assert.equal(suma(0, 0), 0);\n"
                               "assert.equal(suma(-1, 1), 0);\n"),
            "LICENSE": "MIT\n",
            "README.md": "# x\n",
            ".github/workflows/ci.yml": "name: CI\n",
        })

        informe = evaluar(raiz, con_red=False)
        dims = informe["dimensiones"]

        self.assertIsNone(dims["inteligencia"]["puntuacion"])
        self.assertIsNone(dims["eficiencia"]["puntuacion"])
        self.assertEqual(dims["calidad"]["criterios"].get("c1_suite_de_tests"), True)
        self.assertEqual(dims["calidad"]["criterios"].get("c2_linter_configurado"), True)
        self.assertEqual(dims["vigencia"]["criterios"].get("v2_lockfile"), True)
        self.assertNotIn("c3_sin_silencios", dims["calidad"]["criterios"])
        self.assertNotIn("c5_tests_con_aserciones", dims["calidad"]["criterios"])
        self.assertNotIn("h6_imports_declarados", dims["herramientas"]["criterios"])
        self.assertNotIn("v1_dependencias_fijadas", dims["vigencia"]["criterios"])
        self.assertIsNotNone(informe["global"])
        self.assertGreater(informe["cobertura"]["criterios_no_aplicables"], 0)

    def test_h7_acepta_changes_rst_y_history_anidado(self):
        raiz = crear_proyecto(self, {
            "app.py": "x = 1\n",
            "CHANGES.rst": "Cambios\n",
            "docs/HISTORY.md": "Historial\n",
        })

        herramientas = evaluar(raiz, con_red=False)["dimensiones"]["herramientas"]

        self.assertTrue(herramientas["criterios"]["h7_decisiones_documentadas"])

    def test_f1_acepta_comillas_simples_y_entrypoint(self):
        raiz = crear_proyecto(self, {
            "app.py": ("def main():\n"
                       "    return 1\n\n"
                       "if __name__ == '__main__':\n"
                       "    main()\n"),
        })

        funcionalidades = evaluar(raiz, con_red=False)["dimensiones"]["funcionalidades"]

        self.assertTrue(funcionalidades["criterios"]["f1_puntos_de_entrada"])

    def test_f1_sin_cli_es_no_aplica_en_una_biblioteca(self):
        raiz = crear_proyecto(self, {"lib.py": "X = 1\n"})

        funcionalidades = evaluar(raiz, con_red=False)["dimensiones"]["funcionalidades"]

        self.assertNotIn("f1_puntos_de_entrada", funcionalidades["criterios"])
        self.assertTrue(any(item["criterio"] == "f1_puntos_de_entrada"
                            for item in funcionalidades["no_aplica"]))

    def test_h4_detecta_npm_test_y_build_sh(self):
        js = crear_proyecto(self, {
            "package.json": json.dumps({"scripts": {"test": "node --test"}}),
            "test/a.test.js": "assert.equal(1, 1);\n",
        })
        sh = crear_proyecto(self, {
            "build.sh": "#!/bin/sh\n",
            "tests/test_x.py": "def test_x():\n    assert 1 == 1\n",
        })

        self.assertTrue(evaluar(js, con_red=False)["dimensiones"]["herramientas"]
                        ["criterios"]["h4_runner_de_tests_declarado"])
        self.assertTrue(evaluar(sh, con_red=False)["dimensiones"]["herramientas"]
                        ["criterios"]["h4_runner_de_tests_declarado"])

    def test_plan_usa_la_evidencia_de_su_criterio(self):
        raiz = crear_proyecto(self, {
            "pkg/__init__.py": "",
            "pkg/app.py": "import numpy\n",
        })

        mejoras = evaluar(raiz, con_red=False)["mejoras"]
        h6 = next(m for m in mejoras if m["criterio"] == "h6_imports_declarados")
        h7 = next(m for m in mejoras if m["criterio"] == "h7_decisiones_documentadas")

        self.assertNotEqual(h6["evidencia"], h7["evidencia"])
        self.assertTrue(all("app.py" in e for e in h6["evidencia"]))
        self.assertTrue(all("app.py" not in e for e in h7["evidencia"]))
        self.assertEqual(h6["datos_medidos"]["hallazgos"], len(h6["evidencia"]))


class TestEntornoLLMOptIn(unittest.TestCase):
    """--sintesis-llm/--investigar cargan .env sin afectar al modo offline."""

    def test_carga_dotenv_desde_la_ruta_indicada(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / ".env"
            ruta.write_text("OPENROUTER_API_KEY=clave-de-prueba\n",
                            encoding="utf-8")
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("OPENROUTER_API_KEY", None)
                evaluar_proyecto.cargar_entorno_llm(ruta)
                self.assertEqual(os.environ.get("OPENROUTER_API_KEY"),
                                 "clave-de-prueba")

    def test_sin_key_falla_antes_de_llamar_al_evaluador(self):
        with patch.object(evaluar_proyecto, "cargar_entorno_llm"), \
                patch.object(evaluar_proyecto, "evaluar") as evaluar_mock, \
                patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}):
            error = io.StringIO()
            with contextlib.redirect_stderr(error):
                codigo = main([".", "--sintesis-llm", "--sin-red"])

        self.assertEqual(codigo, 2)
        self.assertIn("OPENROUTER_API_KEY", error.getvalue())
        evaluar_mock.assert_not_called()

    def test_investigar_solo_tambien_exige_key(self):
        with patch.object(evaluar_proyecto, "cargar_entorno_llm"), \
                patch.object(evaluar_proyecto, "evaluar") as evaluar_mock, \
                patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}):
            error = io.StringIO()
            with contextlib.redirect_stderr(error):
                codigo = main([".", "--sin-red", "--investigar"])

        self.assertEqual(codigo, 2)
        self.assertIn("OPENROUTER_API_KEY", error.getvalue())
        evaluar_mock.assert_not_called()


class TestEjecutarTestsAcotado(unittest.TestCase):
    def test_cwd_es_el_proyecto_evaluado(self):
        with tempfile.TemporaryDirectory() as d, \
                patch.object(evaluar_proyecto, "detectar_comando_tests",
                             return_value={"comando": ["true"], "origen": "x"}), \
                patch.object(evaluar_proyecto.subprocess, "run") as run:
            run.return_value = SimpleNamespace(
                returncode=0, stdout="Ran 1 test in 0.1s\nOK", stderr="")
            resultado = ejecutar_tests(Path(d))

        self.assertTrue(resultado["ejecutado"])
        self.assertEqual(run.call_args.kwargs["cwd"], d)


class TestSinRedNoTocaPyPI(unittest.TestCase):
    """--sin-red y con_red=False no deben consultar PyPI (red)."""

    def _proyecto(self):
        return crear_proyecto(self, {
            "app.py": "import requests\n\n\ndef f():\n    return requests\n",
            "requirements.txt": "requests==2.31.0\n",
        })

    def test_evaluar_con_red_false_no_consulta(self):
        raiz = self._proyecto()
        with patch.object(evaluar_proyecto, "ultima_version_pypi",
                          side_effect=AssertionError("red")), \
                patch.object(evaluar_proyecto, "licencia_pypi",
                             side_effect=AssertionError("red")):
            informe = evaluar(raiz, con_red=False)

        self.assertEqual(informe["schema_version"], 2)

    def test_main_sin_red_no_consulta(self):
        raiz = self._proyecto()
        salida = io.StringIO()
        with patch.object(evaluar_proyecto, "ultima_version_pypi",
                          side_effect=AssertionError("red")), \
                patch.object(evaluar_proyecto, "licencia_pypi",
                             side_effect=AssertionError("red")):
            with contextlib.redirect_stdout(salida):
                codigo = main([str(raiz), "--sin-red", "--json"])

        self.assertEqual(codigo, 0)
        self.assertIn("schema_version", json.loads(salida.getvalue()))


class TestAutoevaluacionDeThinker(unittest.TestCase):
    """thinker se evalúa a sí mismo (offline): 6 dimensiones y sin sorpresas."""

    def test_thinker_pasa_su_propia_evaluacion(self):
        informe = evaluar(RAIZ_THINKER, con_red=False)

        self.assertEqual(informe["schema_version"], 2)
        self.assertEqual(set(informe["dimensiones"]),
                         {"funcionalidades", "calidad", "vigencia",
                          "herramientas", "inteligencia", "eficiencia"})
        dims = informe["dimensiones"]
        # Lo que thinker exige a otros proyectos y ya cumple:
        self.assertTrue(dims["herramientas"]["criterios"]["h2_licencia"])
        self.assertTrue(dims["vigencia"]["criterios"]["v2_lockfile"])
        self.assertTrue(dims["calidad"]["criterios"]["c2_linter_configurado"])
        self.assertTrue(dims["inteligencia"]["criterios"]["i1_cachea_trabajo_repetido"])
        self.assertTrue(dims["inteligencia"]["criterios"]["i2_timeouts_explicitos"])
        # Los criterios añadidos (2026-10-20) también se exigen a uno mismo:
        self.assertTrue(dims["herramientas"]["criterios"]["h6_imports_declarados"])
        self.assertTrue(dims["herramientas"]["criterios"]["h7_decisiones_documentadas"])
        self.assertTrue(dims["calidad"]["criterios"]["c5_tests_con_aserciones"])

    def test_autoevaluacion_no_escribe_en_el_repo(self):
        antes = {p: p.stat().st_mtime_ns for p in RAIZ_THINKER.rglob("*.py")}

        evaluar(RAIZ_THINKER, con_red=False)

        despues = {p: p.stat().st_mtime_ns for p in RAIZ_THINKER.rglob("*.py")}
        self.assertEqual(antes, despues)

    def test_resumen_de_evidencia_declara_lo_no_verificado(self):
        informe = evaluar(RAIZ_THINKER, con_red=False)

        self.assertEqual(set(informe["evidencia"]), {
            "verified-real", "verified-synthetic", "unverified"})
        self.assertGreaterEqual(informe["evidencia"]["unverified"], 2)
        for datos in informe["dimensiones"].values():
            for hallazgo in datos["hallazgos"]:
                self.assertIn(hallazgo["tipo_evidencia"],
                              {"verified-real", "verified-synthetic",
                               "unverified"})
        texto = "\n".join(informe_texto(informe))
        self.assertIn("[VERIFIED-REAL]", texto)
        self.assertIn("[UNVERIFIED]", texto)

    def test_criterios_na_no_se_cuentan_como_no_verificados(self):
        informe = evaluar(RAIZ_THINKER, con_red=False)

        self.assertIn("N/A", informe["cobertura"]["nota_no_aplicables"])
        self.assertFalse(any("N/A" in nota for nota in informe["no_verificado"]))
        self.assertEqual(informe["evidencia"]["unverified"],
                         len(informe["no_verificado"]))
        self.assertIn("No aplicable:",
                      "\n".join(informe_texto(informe)))


class TestRequisitos(unittest.TestCase):
    """Modo --requisitos: parser estricto, evidencia estática y suite opt-in."""

    REQ_BASE = (
        "## R1: Login válido\n"
        "- Enunciado: El sistema debe permitir login.\n"
        "- Criterio de aceptación: Con credenciales válidas se crea una sesión.\n"
        "- Verificación: test\n"
        "- Evidencia: tests/test_app.py::test_ok\n")

    def _proyecto(self, requisitos, archivos=None):
        base = {
            "app.py": "def main():\n    return 1\n# req~login~1\n",
            "tests/test_app.py": ("import unittest\n\n\n"
                                  "class T(unittest.TestCase):\n"
                                  "    def test_ok(self):\n"
                                  "        self.assertTrue(True)\n"),
            "requisitos.md": requisitos,
        }
        if archivos:
            base.update(archivos)
        return crear_proyecto(self, base)

    def _evaluar(self, raiz, **kwargs):
        return evaluar(raiz, con_red=False,
                       requisitos_path=raiz / "requisitos.md", **kwargs)

    def _item(self, informe, indice=0):
        return informe["requisitos"]["items"][indice]

    def test_parsea_campos_y_autogenera_id(self):
        raiz = crear_proyecto(self, {"requisitos.md": (
            "# Requisitos\n\n## Login válido\n"
            "- Enunciado: El sistema debe permitir login.\n"
            "- Criterio de aceptación: Con credenciales válidas hay sesión.\n"
            "- Verificación: test\n"
            "- Evidencia: tests/test_app.py::test_ok\n"
            "- Tags: req~login~1, req~sesion~2\n")})

        requisitos = parsear_requisitos(raiz / "requisitos.md")

        self.assertEqual(requisitos[0].id, "R1")
        self.assertEqual(requisitos[0].verificacion, "test")
        self.assertEqual(requisitos[0].tags, ["req~login~1", "req~sesion~2"])
        self.assertTrue(any("ID autogenerado" in a for a in requisitos[0].avisos))

    def test_falta_criterio_es_error_con_linea(self):
        raiz = crear_proyecto(self, {"requisitos.md": (
            "## R1: Sin criterio\n- Enunciado: Algo.\n"
            "- Verificación: manual\n")})

        with self.assertRaisesRegex(ValueError, r"requisitos\.md:\d+.*criterio"):
            parsear_requisitos(raiz / "requisitos.md")

    def test_metodo_desconocido_es_error(self):
        raiz = crear_proyecto(self, {"requisitos.md": (
            "## R1: Método raro\n- Enunciado: Algo.\n"
            "- Criterio de aceptación: Algo medible.\n"
            "- Verificación: telepatía\n")})

        with self.assertRaisesRegex(
                ValueError, "método de verificación no reconocido"):
            parsear_requisitos(raiz / "requisitos.md")

    def test_id_duplicado_es_error(self):
        raiz = crear_proyecto(self, {"requisitos.md": (
            "## R1: Uno\n- Enunciado: A.\n- Criterio de aceptación: B.\n\n"
            "## R1: Dos\n- Enunciado: C.\n- Criterio de aceptación: D.\n")})

        with self.assertRaisesRegex(ValueError, "duplicado"):
            parsear_requisitos(raiz / "requisitos.md")

    def test_test_inexistente_es_no_cumple(self):
        raiz = self._proyecto(
            "## R1: Logout\n- Enunciado: Debe existir logout.\n"
            "- Criterio de aceptación: test_logout pasa.\n"
            "- Verificación: test\n"
            "- Evidencia: tests/test_app.py::test_logout\n")

        item = self._item(self._evaluar(raiz))

        self.assertEqual(item["veredicto"], "NO CUMPLE")
        self.assertIn("no existe", item["motivo"])

    def test_tag_encontrado_y_ausente(self):
        raiz = self._proyecto(
            "## R1: Tag presente\n- Enunciado: Login.\n"
            "- Criterio de aceptación: El tag req~login~1 existe.\n"
            "- Verificación: tag\n- Tags: req~login~1\n\n"
            "## R2: Tag ausente\n- Enunciado: Logout.\n"
            "- Criterio de aceptación: El tag req~logout~1 existe.\n"
            "- Verificación: tag\n- Tags: req~logout~1\n")

        informe = self._evaluar(raiz)

        self.assertEqual(self._item(informe, 0)["veredicto"], "CUBIERTO")
        self.assertEqual(self._item(informe, 1)["veredicto"], "NO CUMPLE")

    def test_sin_flag_es_cubierto_y_con_suite_verde_es_cumple(self):
        raiz = self._proyecto(self.REQ_BASE)

        sin = self._evaluar(raiz)
        con = self._evaluar(raiz, ejecutar_tests_flag=True)

        self.assertEqual(self._item(sin)["veredicto"], "CUBIERTO")
        self.assertIn("suite no ejecutada", self._item(sin)["motivo"])
        self.assertEqual(self._item(con)["veredicto"], "CUMPLE")
        self.assertIn("suite completa verde", self._item(con)["motivo"])

    def test_suite_roja_es_no_cumple(self):
        raiz = self._proyecto(self.REQ_BASE, {
            "tests/test_app.py": ("import unittest\n\n\n"
                                  "class T(unittest.TestCase):\n"
                                  "    def test_ok(self):\n"
                                  "        self.assertEqual(1, 2)\n")})

        item = self._item(self._evaluar(raiz, ejecutar_tests_flag=True))

        self.assertEqual(item["veredicto"], "NO CUMPLE")
        self.assertIn("suite falló", item["motivo"])

    def test_manual_y_sin_metodo_son_no_verificables(self):
        raiz = self._proyecto(
            "## R1: Manual\n- Enunciado: Accesibilidad.\n"
            "- Criterio de aceptación: Revisión manual.\n"
            "- Verificación: manual\n\n"
            "## R2: Sin método\n- Enunciado: Algo.\n"
            "- Criterio de aceptación: Algo medible.\n")

        informe = self._evaluar(raiz)

        self.assertEqual(self._item(informe, 0)["veredicto"], "NO VERIFICABLE")
        self.assertEqual(self._item(informe, 1)["veredicto"], "NO VERIFICABLE")

    def test_criterio_vago_genera_aviso(self):
        raiz = self._proyecto(
            "## R1: Vago\n- Enunciado: Debe ser fácil.\n"
            "- Criterio de aceptación: Fácil de usar.\n"
            "- Verificación: archivo\n- Evidencia: app.py\n")

        item = self._item(self._evaluar(raiz))

        self.assertEqual(item["veredicto"], "CUBIERTO")
        self.assertTrue(any("términos vagos" in a for a in item["avisos"]))

    def test_archivo_y_formal_presentes_son_cubiertos(self):
        raiz = self._proyecto(
            "## R1: Archivo\n- Enunciado: Módulo.\n"
            "- Criterio de aceptación: app.py existe.\n"
            "- Verificación: archivo\n- Evidencia: app.py\n\n"
            "## R2: Formal\n- Enunciado: Prueba.\n"
            "- Criterio de aceptación: prueba.lean existe.\n"
            "- Verificación: formal\n- Evidencia: prueba.lean\n",
            {"prueba.lean": "theorem x : True := trivial\n"})

        informe = self._evaluar(raiz)

        self.assertEqual(self._item(informe, 0)["veredicto"], "CUBIERTO")
        self.assertEqual(self._item(informe, 1)["veredicto"], "CUBIERTO")

    def test_evidencia_fuera_del_proyecto_no_se_lee(self):
        with tempfile.TemporaryDirectory() as fuera:
            evidencia = Path(fuera) / "fuera.txt"
            evidencia.write_text("SECRETO-QUE-NO-DEBE-SALIR", encoding="utf-8")
            raiz = self._proyecto(
                "## R1: Fuera\n- Enunciado: Algo.\n"
                "- Criterio de aceptación: El archivo externo existe.\n"
                "- Verificación: archivo\n"
                f"- Evidencia: {evidencia}\n")

            informe = self._evaluar(raiz)
            item = self._item(informe)

            self.assertEqual(item["veredicto"], "NO VERIFICABLE")
            self.assertIn("fuera del proyecto", item["motivo"])
            self.assertNotIn("SECRETO-QUE-NO-DEBE-SALIR",
                             json.dumps(informe, ensure_ascii=False))

    def test_no_afecta_al_global_y_la_suite_se_ejecuta_una_vez(self):
        raiz = self._proyecto(self.REQ_BASE)

        sin = evaluar(raiz, con_red=False)
        con = self._evaluar(raiz)
        self.assertEqual(sin["global"], con["global"])
        self.assertFalse(con["requisitos"]["afecta_global"])

        with patch("evaluar_proyecto.ejecutar_tests",
                   wraps=evaluar_proyecto.ejecutar_tests) as ejecutada:
            con_suite = self._evaluar(raiz, ejecutar_tests_flag=True)

        self.assertEqual(ejecutada.call_count, 1)
        self.assertEqual(self._item(con_suite)["veredicto"], "CUMPLE")

    def test_cli_requisitos_texto_y_json(self):
        raiz = self._proyecto(self.REQ_BASE)

        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            codigo = main([str(raiz), "--sin-red", "--requisitos",
                           str(raiz / "requisitos.md")])
        self.assertEqual(codigo, 0)
        self.assertIn("== REQUISITOS", salida.getvalue())
        self.assertIn("CUBIERTO", salida.getvalue())

        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            codigo = main([str(raiz), "--sin-red", "--json", "--requisitos",
                           str(raiz / "requisitos.md")])
        datos = json.loads(salida.getvalue())
        self.assertEqual(codigo, 0)
        self.assertEqual(datos["schema_version"], 2)
        self.assertIn("requisitos", datos)
        self.assertEqual(datos["requisitos"]["items"][0]["veredicto"], "CUBIERTO")

    def test_cli_requisitos_inexistente_devuelve_2(self):
        raiz = self._proyecto(self.REQ_BASE)

        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            codigo = main([str(raiz), "--requisitos",
                           str(raiz / "no-existe.md")])

        self.assertEqual(codigo, 2)
        self.assertIn("no existe el archivo de requisitos", error.getvalue())

    def test_test_sin_evidencia_es_no_verificable(self):
        raiz = self._proyecto(
            "## R1: Sin evidencia\n- Enunciado: Algo.\n"
            "- Criterio de aceptación: Algo medible.\n"
            "- Verificación: test\n")

        item = self._item(self._evaluar(raiz))

        self.assertEqual(item["veredicto"], "NO VERIFICABLE")
        self.assertIn("sin evidencia", item["motivo"])

    def test_criterio_multilinea_se_conserva(self):
        raiz = crear_proyecto(self, {"requisitos.md": (
            "## R1: Multilínea\n"
            "- Enunciado: El sistema debe permitir login.\n"
            "- Criterio de aceptación: Con credenciales válidas se crea una "
            "sesión\n  y se devuelve 200.\n"
            "- Verificación: archivo\n- Evidencia: app.py\n")})

        requisitos = parsear_requisitos(raiz / "requisitos.md")

        self.assertEqual(
            requisitos[0].criterio,
            "Con credenciales válidas se crea una sesión y se devuelve 200.")


class TestCoberturaDeRamasDelEvaluador(unittest.TestCase):
    """Ramas de parseo y renderizado que no dependen de red ni del repo."""

    def test_setup_py_lee_runtime_dev_y_extras(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp)
            (ruta / "setup.py").write_text(
                "from setuptools import setup\n"
                "setup(install_requires=['requests==2.0'],\n"
                "      tests_require=['pytest>=7'],\n"
                "      extras_require={'docs': ['sphinx==7.0']})\n",
                encoding="utf-8")

            deps = evaluar_proyecto._dependencias_setup_py(
                ruta / "setup.py", ruta)

        por_nombre = {dep["nombre"]: dep for dep in deps}
        self.assertEqual(por_nombre["requests"]["ambito"], "runtime")
        self.assertEqual(por_nombre["pytest"]["ambito"], "dev")
        self.assertEqual(por_nombre["sphinx"]["ambito"], "opcional")

    def test_versiones_lock_lee_uv_pipfile_package_lock_y_texto(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp)
            (ruta / "uv.lock").write_text(
                '[[package]]\nname = "requests"\nversion = "2.34.2"\n\n'
                '[[package]]\nname = "propio"\nversion = "0.1.0"\n'
                'source = { editable = "." }\n', encoding="utf-8")
            (ruta / "Pipfile.lock").write_text(json.dumps({
                "default": {"flask": {"version": "==3.0.0"}},
                "develop": {"pytest": {"version": "==8.0.0"}},
            }), encoding="utf-8")
            (ruta / "package-lock.json").write_text(json.dumps({
                "packages": {"": {"name": "x"},
                             "node_modules/react": {"version": "18.2.0"}},
            }), encoding="utf-8")
            (ruta / "custom.lock").write_text("numpy==2.0.0\n# comentario\n",
                                              encoding="utf-8")
            (ruta / "poetry.lock").write_text("esto no es toml [",
                                              encoding="utf-8")

            versiones = evaluar_proyecto._versiones_lock(ruta)

        self.assertEqual(versiones["requests"], "2.34.2")
        self.assertEqual(versiones["flask"], "3.0.0")
        self.assertEqual(versiones["pytest"], "8.0.0")
        self.assertEqual(versiones["react"], "18.2.0")
        self.assertEqual(versiones["numpy"], "2.0.0")
        self.assertNotIn("propio", versiones)

    def test_versiones_lock_avisa_json_invalido(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp)
            (ruta / "Pipfile.lock").write_text("{invalido", encoding="utf-8")
            (ruta / "package-lock.json").write_text("{invalido",
                                                    encoding="utf-8")

            with warnings.catch_warnings(record=True) as capturados:
                warnings.simplefilter("always")
                versiones = evaluar_proyecto._versiones_lock(ruta)

        self.assertEqual(versiones, {})
        self.assertEqual(len(capturados), 2)
        self.assertTrue(all("lock JSON inválido" in str(w.message)
                            for w in capturados))

    def test_parsear_requisito_y_ambito_requirements(self):
        from evaluar_proyecto import _ambito_requirements, _parsear_requisito

        for linea in ("-r base.txt", "--index-url https://pypi.org/simple",
                      "https://example.test/pkg.whl", "git+https://example.test/x",
                      "pkg @ https://example.test/x", "pkg.whl", "pkg.tar.gz"):
            self.assertIsNone(_parsear_requisito(linea), linea)

        dep = _parsear_requisito("requests==2.31.0", "requirements.txt")
        self.assertEqual(dep["nombre"], "requests")
        self.assertEqual(dep["ambito"], "runtime")
        self.assertTrue(dep["fijada"])

        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp)
            casos = {
                "docs/requirements.txt": "docs",
                "tests/requirements.txt": "test",
                "requirements-dev.txt": "dev",
                "requirements.txt": "runtime",
                "base.txt": "runtime",
                "sub/requirements.txt": "dev",
            }
            for relativo, esperado in casos.items():
                archivo = ruta / relativo
                archivo.parent.mkdir(parents=True, exist_ok=True)
                archivo.write_text("", encoding="utf-8")
                self.assertEqual(_ambito_requirements(archivo, ruta), esperado,
                                 relativo)

    def test_dependencias_pyproject_toml_invalido_extrae_lista(self):
        deps = evaluar_proyecto._dependencias_pyproject(
            '[project\n'
            'dependencies = ["requests==2.0", "pytest>=7"]\n')
        self.assertEqual({dep["nombre"] for dep in deps}, {"requests", "pytest"})
        self.assertTrue(all(dep["ambito"] == "runtime" for dep in deps))

    def test_detectar_comando_tests_en_manifiestos_no_python(self):
        casos = [
            ({"package.json": '{"scripts": {"test": "pytest"}}'}, "npm"),
            ({"gradlew": "", "build.gradle": ""}, "./gradlew"),
            ({"pom.xml": "<project/>"}, "mvn"),
            ({"go.mod": "module demo"}, "go"),
            ({"Cargo.toml": "[package]\nname='demo'\n"}, "cargo"),
            ({"tox.ini": "[tox]"}, "tox"),
            ({"noxfile.py": ""}, "nox"),
        ]
        for archivos, esperado in casos:
            with tempfile.TemporaryDirectory() as tmp:
                ruta = Path(tmp)
                for nombre, contenido in archivos.items():
                    (ruta / nombre).write_text(contenido, encoding="utf-8")
                resultado = detectar_comando_tests(ruta)
            self.assertIsNotNone(resultado, archivos)
            self.assertEqual(resultado["comando"][0], esperado, archivos)

    def test_leer_y_nombre_excepcion_ramas(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp)
            self.assertEqual(evaluar_proyecto.leer(ruta / "no-existe.txt"), "")

        arbol = evaluar_proyecto.ast.parse(
            "try:\n    pass\nexcept (ValueError, TypeError):\n    pass\n")
        manejador = next(n for n in evaluar_proyecto.ast.walk(arbol)
                         if isinstance(n, evaluar_proyecto.ast.ExceptHandler))
        self.assertEqual(evaluar_proyecto._nombre_excepcion(manejador.type),
                         "ValueError,TypeError")
        self.assertEqual(
            evaluar_proyecto._nombre_excepcion(
                evaluar_proyecto.ast.Constant(value=1)), "")

    def test_informe_texto_renderiza_requisitos_sintesis_e_investigacion(self):
        informe = evaluar(RAIZ_THINKER, con_red=False)
        informe["requisitos"] = {
            "archivo": "requisitos.md", "total": 1,
            "items": [{"veredicto": "CUBIERTO", "id": "R1",
                       "titulo": "Login", "criterio": "sesión",
                       "evidencia_observada": "app.py", "motivo": "existe",
                       "avisos": ["aviso de prueba"]}],
            "resumen": {"cumple": 0, "cubierto": 1, "no_cumple": 0,
                        "no_verificable": 0},
            "nota": "CUBIERTO no es CUMPLE",
        }
        informe["sintesis_llm"] = {
            "modelo": "modelo-de-prueba", "sin_respaldo": 1,
            "propuestas": [{"dimension": "calidad", "propuesta": "Propuesta",
                            "con_respaldo": False, "por_que": "porque",
                            "evidencia": "evidencia", "como_verificar": "ver"}],
            "preguntas_abiertas": ["¿Queda algo?"],
        }
        informe["investigacion"] = [
            {"pregunta": "p1", "error": "sin red"},
            {"pregunta": "p2", "sin_resultados": True,
             "fuentes": [{"titulo": "T", "url": "https://ejemplo.test"}]},
        ]

        texto = "\n".join(informe_texto(informe))

        self.assertIn("== REQUISITOS (requisitos.md) — 1 ==", texto)
        self.assertIn("aviso: aviso de prueba", texto)
        self.assertIn("CUBIERTO no es CUMPLE", texto)
        self.assertIn("PROPUESTAS DEL MODELO (modelo-de-prueba)", texto)
        self.assertIn("SIN RESPALDO", texto)
        self.assertIn("¿Queda algo?", texto)
        self.assertIn("ERROR: sin red", texto)
        self.assertIn("sin resultados (se declara, no se inventa)", texto)
        self.assertIn("https://ejemplo.test", texto)

    def test_sintesis_sin_python_dotenv_devuelve_2(self):
        with patch.object(evaluar_proyecto, "cargar_entorno_llm",
                          side_effect=ImportError), \
                patch.object(evaluar_proyecto, "evaluar") as evaluar_mock:
            error = io.StringIO()
            with contextlib.redirect_stderr(error):
                codigo = main([".", "--sintesis-llm", "--sin-red"])

        self.assertEqual(codigo, 2)
        self.assertIn("python-dotenv", error.getvalue())
        evaluar_mock.assert_not_called()


class TestAsercionesDebiles(unittest.TestCase):
    """R7: señal informativa separada de c5 (tests no-op)."""

    def test_detecta_constantes_y_no_toca_c5(self):
        raiz = crear_proyecto(self, {
            "demo.py": "def sumar(a, b):\n    return a + b\n",
            "tests/test_weak.py": (
                "import unittest\n\n\n"
                "class TestWeak(unittest.TestCase):\n"
                "    def test_assert_true(self):\n"
                "        assert True\n\n"
                "    def test_assert_true_method(self):\n"
                "        self.assertTrue(True)\n\n"
                "    def test_equal(self):\n"
                "        self.assertEqual(1, 1)\n\n"
                "    def test_falla(self):\n"
                "        self.assertEqual(1, 2)\n\n"
                "    def test_variable(self):\n"
                "        valor = 1\n"
                "        self.assertEqual(valor, 1)\n"),
        })

        informe = evaluar(raiz, con_red=False)

        self.assertTrue(informe["dimensiones"]["calidad"]
                        ["criterios"]["c5_tests_con_aserciones"])
        self.assertEqual(len(informe["aserciones_debiles"]), 3)
        self.assertIn("ASERCIONES DÉBILES", "\n".join(informe_texto(informe)))

    def test_no_marca_variables_helpers_ni_noop(self):
        raiz = crear_proyecto(self, {
            "demo.py": ("def sumar(a, b):\n    return a + b\n\n"
                        "def helper():\n    return 1\n"),
            "tests/test_ok.py": (
                "import unittest\n\n"
                "from demo import helper, sumar\n\n\n"
                "class TestOk(unittest.TestCase):\n"
                "    def test_variable(self):\n"
                "        valor = sumar(1, 2)\n"
                "        self.assertEqual(valor, 3)\n\n"
                "    def test_helper(self):\n"
                "        self.assertEqual(helper(), 1)\n\n"
                "    def test_property(self):\n"
                "        valor = 1\n"
                "        assert valor == 1\n\n"
                "    def test_noop(self):\n"
                "        pass\n"),
        })

        informe = evaluar(raiz, con_red=False)

        self.assertEqual(informe["aserciones_debiles"], [])
        self.assertFalse(informe["dimensiones"]["calidad"]
                         ["criterios"]["c5_tests_con_aserciones"])


class TestComparabilidadR5(unittest.TestCase):
    """R5: una cobertura baja no se presenta como GLOBAL comparable."""

    def test_java_baja_no_es_comparable(self):
        raiz = crear_proyecto(self, {
            "pom.xml": "<project></project>\n",
            "src/main/java/Demo.java": "class Demo {}\n",
        })

        informe = evaluar(raiz, con_red=False)

        cobertura = informe["cobertura"]
        self.assertFalse(cobertura["comparable"])
        self.assertIn("cobertura", cobertura["motivo_no_comparable"])
        self.assertIn("Java", cobertura["nota_lenguajes"])
        texto = "\n".join(informe_texto(informe))
        self.assertIn("GLOBAL NO COMPARABLE", texto)
        self.assertIn("Aviso:", texto)

    def test_etiqueta_global(self):
        self.assertEqual(
            evaluar_proyecto._etiqueta_global({"comparable": True}), "GLOBAL")
        self.assertEqual(
            evaluar_proyecto._etiqueta_global({"comparable": False}),
            "GLOBAL NO COMPARABLE")


class TestSilenciosR6(unittest.TestCase):
    """R6: la marca con motivo es un warning; sin marca sigue fallando c3."""

    def _fixture(self, except_line):
        return crear_proyecto(self, {
            "demo.py": (
                "def f():\n"
                "    try:\n"
                "        return 1\n"
                f"    {except_line}\n"
                "        pass\n"),
        })

    def test_silencio_marcado_es_warning_y_c3_pasa(self):
        raiz = self._fixture(
            "except Exception:  # noqa: silent: limpieza temporal")
        informe = evaluar(raiz, con_red=False)
        calidad = informe["dimensiones"]["calidad"]

        self.assertTrue(calidad["criterios"]["c3_sin_silencios"])
        self.assertTrue(any(h["severidad"] == "baja"
                            and "Silencio aceptado" in h["descripcion"]
                            for h in calidad["hallazgos"]))
        texto = "\n".join(informe_texto(informe))
        self.assertIn("Silencio aceptado (warning)", texto)

    def test_silencio_sin_marca_falla_c3(self):
        raiz = self._fixture("except Exception:")
        informe = evaluar(raiz, con_red=False)

        self.assertFalse(informe["dimensiones"]["calidad"]
                         ["criterios"]["c3_sin_silencios"])

    def test_marca_sin_motivo_no_acepta(self):
        raiz = self._fixture("except Exception:  # noqa: silent:")
        informe = evaluar(raiz, con_red=False)

        self.assertFalse(informe["dimensiones"]["calidad"]
                         ["criterios"]["c3_sin_silencios"])


class TestInformeTextoContrato(unittest.TestCase):
    """Contrato exacto del render: secciones, etiquetas, marcas y orden."""

    def test_render_completo(self):
        informe = {
            "ruta": "/tmp/demo", "archivos_python": 2, "lineas_python": 20,
            "cobertura": {
                "criterios_evaluados": 5, "criterios_no_aplicables": 1,
                "nivel": "alta", "lenguajes": {"Python": 2},
                "comparable": False, "motivo_no_comparable": "cobertura 50%",
                "nota_lenguajes": "Python: AST y criterios nativos",
                "nota_no_aplicables": "1 N/A por perfil",
                "ratio_evaluado": 0.5},
            "dimensiones": {
                "calidad": {
                    "puntuacion": 0.5,
                    "criterios": {"c1": True, "c2": False},
                    "no_aplica": [{"criterio": "v4", "motivo": "sin red"}],
                    "hallazgos": [{
                        "tipo_evidencia": "verified-real",
                        "severidad": "alta", "descripcion": "Silencio",
                        "evidencia": "app.py:1"}],
                    "notas": ["nota de calidad"]}},
            "global": 0.75, "global_nota": "nota global",
            "evidencia": {"verified-real": 2, "verified-synthetic": 0,
                          "unverified": 0},
            "licencias_no_runtime": [{
                "nombre": "pytest", "ambito": "dev", "licencia": "MIT",
                "procedencia": "real"}],
            "aserciones_debiles": ["test_x.py:1 assert True"],
            "requisitos": {
                "archivo": "req.md", "total": 1,
                "items": [{
                    "veredicto": "CUBIERTO", "id": "R1", "titulo": "Login",
                    "criterio": "sesión", "evidencia_observada": "app.py",
                    "motivo": "existe", "avisos": ["aviso"]}],
                "resumen": {"cumple": 0, "cubierto": 1, "no_cumple": 0,
                            "no_verificable": 0},
                "nota": "CUBIERTO no es CUMPLE"},
            "sintesis_llm": {
                "modelo": "m", "sin_respaldo": 1,
                "propuestas": [{
                    "dimension": "calidad", "propuesta": "P",
                    "con_respaldo": False, "por_que": "pq",
                    "evidencia": "ev", "como_verificar": "ver"}],
                "preguntas_abiertas": ["¿Q?"]},
            "investigacion": [
                {"pregunta": "p1", "error": "sin red"},
                {"pregunta": "p2", "sin_resultados": True,
                 "fuentes": [{"titulo": "T", "url": "https://x.test"}]}],
            "mejoras": [{
                "prioridad": "alta", "dimension": "calidad",
                "propuesta": "Mejorar", "sitios": 2, "esfuerzo": "bajo",
                "metrica": "test"}],
            "no_verificado": ["red"],
        }

        self.assertEqual(informe_texto(informe), [
            "EVALUACIÓN DE PROYECTO (read-only): /tmp/demo",
            "Python: 2 archivos / 20 líneas",
            "Cobertura: 5 criterios evaluados, 1 N/A (nivel alta); "
            "lenguajes: Python",
            "",
            "== CALIDAD — 0.50 ==",
            "  [OK ] c1",
            "  [NO ] c2",
            "  [N/A] v4: sin red",
            "  [VERIFIED-REAL] (alta) Silencio — app.py:1",
            "  · nota de calidad",
            "",
            "GLOBAL NO COMPARABLE: 0.750 (cobertura alta, 50% de criterios)",
            "Aviso: cobertura 50%",
            "Lenguajes: Python: AST y criterios nativos",
            "Nota: nota global",
            "Evidencia: [VERIFIED-REAL] 2 | [VERIFIED-SYNTHETIC] 0 | "
            "[UNVERIFIED] 0",
            "",
            "== LICENCIAS NO RUNTIME (informativas; no puntúan h5) ==",
            "  - pytest [dev] MIT (real)",
            "",
            "== ASERCIONES DÉBILES (informativas; no cambian c5) ==",
            "  - test_x.py:1 assert True",
            "",
            "== REQUISITOS (req.md) — 1 ==",
            "  [CUBIERTO] R1 — Login",
            "      criterio: sesión",
            "      evidencia: app.py",
            "      motivo: existe",
            "      aviso: aviso",
            "  Resumen: 0 CUMPLE | 1 CUBIERTO | 0 NO CUMPLE | "
            "0 NO VERIFICABLE",
            "  Nota: CUBIERTO no es CUMPLE",
            "",
            "Plan de mejora: 1 propuestas (1 alta); ordenadas por prioridad, "
            "secuencia y esfuerzo.",
            "== MEJORAS PROPUESTAS (por prioridad, con su verificación) ==",
            "  [ alta] calidad: Mejorar",
            "          sitios: 2 | esfuerzo: bajo",
            "          verificación: test",
            "",
            "== PROPUESTAS DEL MODELO (m) — juicio, no medición; sin respaldo "
            "medido: 1 ==",
            "  [calidad] P (SIN RESPALDO)",
            "          por qué: pq",
            "          evidencia citada: ev",
            "          verificación: ver",
            "  Preguntas abiertas (lo que el modelo declara NO saber): 1",
            "    · ¿Q?",
            "",
            "== INVESTIGACIÓN DE LAS DUDAS (fuentes citadas, verificables) ==",
            "  ? p1",
            "    ERROR: sin red",
            "  ? p2",
            "    sin resultados (se declara, no se inventa)",
            "    - T: https://x.test",
            "",
            "No aplicable: 1 N/A por perfil",
            "No verificado: red",
        ])

    def test_render_minimo_usa_fallbacks(self):
        informe = {
            "ruta": "x", "archivos_python": 0, "lineas_python": 0,
            "cobertura": {}, "dimensiones": {}, "global": None,
            "global_nota": "", "evidencia": {}, "mejoras": [],
            "no_verificado": [],
        }

        self.assertEqual(informe_texto(informe), [
            "EVALUACIÓN DE PROYECTO (read-only): x",
            "Python: 0 archivos / 0 líneas",
            "Cobertura: ? criterios evaluados, ? N/A (nivel ?); "
            "lenguajes: ninguno",
            "",
            "GLOBAL: N/A (cobertura ?, 0% de criterios)",
            "Nota: ",
            "Evidencia: [VERIFIED-REAL] 0 | [VERIFIED-SYNTHETIC] 0 | "
            "[UNVERIFIED] 0",
            "",
            "Plan de mejora: nada que proponer (todos los criterios cumplen).",
            "== MEJORAS PROPUESTAS (por prioridad, con su verificación) ==",
            "",
            "No verificado: ",
        ])


class TestDetectarComandoTestsContrato(unittest.TestCase):
    """Contrato exacto del runner declarado y de su origen."""

    def _detectar(self, archivos, which=None):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp)
            for nombre, contenido in archivos.items():
                destino = ruta / nombre
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_text(contenido, encoding="utf-8")
            with patch.object(
                    evaluar_proyecto.shutil, "which",
                    side_effect=which or (lambda nombre: (
                        "/usr/bin/make" if nombre == "make" else None))):
                return detectar_comando_tests(ruta)

    def test_manifiestos_y_origenes_exactos(self):
        interprete = evaluar_proyecto.sys.executable
        casos = [
            ({"Makefile": "# comandos\ntest:\n\tpython3 -m pytest\n"},
             {"comando": ["make", "test"],
              "origen": "Makefile (target test)"}),
            ({"scripts/pruebas.sh": "python3 -m pytest -q\n"},
             {"comando": [interprete, "-m", "pytest", "-q"],
              "origen": "scripts/pruebas.sh"}),
            ({"README.md": "```\npytest -q\n```\n"},
             {"comando": ["pytest", "-q"], "origen": "README.md"}),
            ({"AGENTS.md": "npm test\n"},
             {"comando": ["npm", "test"], "origen": "AGENTS.md"}),
            ({"README.rst": "mvn test\n"},
             {"comando": ["mvn", "test"], "origen": "README.rst"}),
            ({"package.json": '{"scripts": {"test": "node test.js"}}'},
             {"comando": ["npm", "test"],
              "origen": "package.json (scripts.test)"}),
            ({"gradlew": "", "build.gradle": ""},
             {"comando": ["./gradlew", "test"],
              "origen": "gradlew + build.gradle"}),
            ({"pom.xml": "<project/>"},
             {"comando": ["mvn", "test"], "origen": "pom.xml"}),
            ({"go.mod": "module demo"},
             {"comando": ["go", "test", "./..."], "origen": "go.mod"}),
            ({"Cargo.toml": "[package]\nname='demo'\n"},
             {"comando": ["cargo", "test"], "origen": "Cargo.toml"}),
            ({"tox.ini": "[tox]"},
             {"comando": ["tox"], "origen": "tox.ini"}),
            ({"noxfile.py": "x = 1\n"},
             {"comando": ["nox"], "origen": "noxfile.py"}),
            ({"tests/test_x.py": "x = 1\n"},
             {"comando": [interprete, "-m", "unittest", "discover",
                          "-s", "tests"],
              "origen": "convención: existe tests/"}),
        ]
        for archivos, esperado in casos:
            with self.subTest(archivos=archivos):
                self.assertEqual(self._detectar(archivos), esperado)

    def test_sin_runner_o_script_no_valido_devuelve_none(self):
        casos = [
            {"demo.py": "x = 1\n"},
            {"package.json": '{"scripts": {"test": "no test specified"}}'},
            {"package.json": '{"scripts": {"test": "No Test Specified"}}'},
            {"package.json": '{"scripts": {"test": "echo hola"}}'},
            {"package.json": '{"scripts": {"test": "ECHO hola"}}'},
            {"package.json": "{}"},
            {"package.json": "{roto"},
        ]
        for archivos in casos:
            with self.subTest(archivos=archivos):
                self.assertIsNone(self._detectar(archivos))

    def test_makefile_sin_binario_make_cae_a_la_convencion(self):
        interprete = evaluar_proyecto.sys.executable
        resultado = self._detectar(
            {"Makefile": "test:\n\tpython3 -m pytest\n",
             "tests/test_x.py": "x = 1\n"},
            which=lambda _nombre: None)

        self.assertEqual(resultado, {
            "comando": [interprete, "-m", "unittest", "discover", "-s",
                        "tests"],
            "origen": "convención: existe tests/"})


class TestDimensionesContrato(unittest.TestCase):
    """Contrato exacto de herramientas/calidad: criterios, hallazgos y notas."""

    def test_herramientas_proyecto_completo(self):
        raiz = crear_proyecto(self, {
            "pyproject.toml": ('[project]\nname = "demo"\nversion = "0.1.0"\n'
                               'dependencies = ["requests"]\n'),
            "LICENSE": "MIT\n",
            "pkg/__init__.py": "",
            "pkg/app.py": "import requests\n\n\ndef f():\n    return requests\n",
            "tests/test_app.py": "def test_f():\n    assert 1 == 1\n",
        })
        perfil = evaluar_proyecto.analizar_perfil(raiz)

        dimension = evaluar_proyecto.evaluar_herramientas(
            raiz, perfil, con_red=False)

        self.assertEqual(dimension.a_dict(), {
            "puntuacion": 0.667, "evaluado": True,
            "criterios": {"h1_manifiesto": True, "h2_licencia": True,
                          "h3_verificacion_automatizada": False,
                          "h4_runner_de_tests_declarado": True,
                          "h6_imports_declarados": True,
                          "h7_decisiones_documentadas": False},
            "no_aplica": [{"criterio": "h5_licencias_libres",
                           "motivo": "licencias de dependencias OMITIDAS "
                                     "(--sin-red)"}],
            "hallazgos": [
                {"severidad": "media",
                 "descripcion": "Sin CI ni script de verificación local",
                 "evidencia": str(raiz), "tipo_evidencia": "verified-real",
                 "criterio": "h3_verificacion_automatizada"},
                {"severidad": "baja",
                 "descripcion": "Sin registro de decisiones (ADR/decision_log/"
                                "CHANGELOG): el porqué de las decisiones no es "
                                "consultable",
                 "evidencia": str(raiz), "tipo_evidencia": "verified-real",
                 "criterio": "h7_decisiones_documentadas"}],
            "notas": [
                "manifiestos (1): pyproject.toml",
                f"runner: {evaluar_proyecto.sys.executable} -m unittest "
                "discover -s tests (convención: existe tests/)",
                "licencias de dependencias OMITIDAS (--sin-red)",
                "h6 sobre 2 archivos de producción "
                "(tests/docs/scripts excluidos)"]})

    def test_herramientas_sin_manifiesto_ni_licencia(self):
        raiz = crear_proyecto(self, {
            "demo.py": "def f():\n    return 1\n",
            "test_demo.py": "def test_f():\n    assert 1 == 1\n",
        })
        perfil = evaluar_proyecto.analizar_perfil(raiz)

        dimension = evaluar_proyecto.evaluar_herramientas(
            raiz, perfil, con_red=False)

        self.assertEqual(dimension.a_dict(), {
            "puntuacion": 0.167, "evaluado": True,
            "criterios": {"h1_manifiesto": False, "h2_licencia": False,
                          "h3_verificacion_automatizada": False,
                          "h4_runner_de_tests_declarado": False,
                          "h6_imports_declarados": True,
                          "h7_decisiones_documentadas": False},
            "no_aplica": [{"criterio": "h5_licencias_libres",
                           "motivo": "sin dependencias Python runtime"}],
            "hallazgos": [
                {"severidad": "alta",
                 "descripcion": "Sin manifiesto de dependencias",
                 "evidencia": str(raiz), "tipo_evidencia": "verified-real",
                 "criterio": "h1_manifiesto"},
                {"severidad": "alta",
                 "descripcion": "Sin archivo de licencia: el uso/reutilización "
                                "queda sin términos (P1.18)",
                 "evidencia": str(raiz), "tipo_evidencia": "verified-real",
                 "criterio": "h2_licencia"},
                {"severidad": "media",
                 "descripcion": "Sin CI ni script de verificación local",
                 "evidencia": str(raiz), "tipo_evidencia": "verified-real",
                 "criterio": "h3_verificacion_automatizada"},
                {"severidad": "media",
                 "descripcion": "Tests presentes pero sin comando de ejecución "
                                "declarado",
                 "evidencia": "manifiestos/README",
                 "tipo_evidencia": "verified-real",
                 "criterio": "h4_runner_de_tests_declarado"},
                {"severidad": "baja",
                 "descripcion": "Sin registro de decisiones (ADR/decision_log/"
                                "CHANGELOG): el porqué de las decisiones no es "
                                "consultable",
                 "evidencia": str(raiz), "tipo_evidencia": "verified-real",
                 "criterio": "h7_decisiones_documentadas"}],
            "notas": ["h6 sobre 1 archivos de producción "
                      "(tests/docs/scripts excluidos)"]})

    def test_calidad_proyecto_con_silencio(self):
        raiz = crear_proyecto(self, {
            "demo.py": ("def f():\n    try:\n        return 1\n"
                        "    except Exception:\n        pass\n"),
            "tests/test_demo.py": ("from demo import f\n\n"
                                   "def test_f():\n    assert f() == 1\n"),
            "pyproject.toml": "[tool.ruff]\nline-length = 100\n",
        })
        perfil = evaluar_proyecto.analizar_perfil(raiz)

        dimension = evaluar_proyecto.evaluar_calidad(raiz, perfil)

        self.assertEqual(dimension.a_dict(), {
            "puntuacion": 0.8, "evaluado": True,
            "criterios": {"c1_suite_de_tests": True,
                          "c2_linter_configurado": True,
                          "c3_sin_silencios": False,
                          "c4_tests_sobre_codigo_30pct": True,
                          "c5_tests_con_aserciones": True},
            "no_aplica": [],
            "hallazgos": [{
                "severidad": "media",
                "descripcion": "`except` con `pass`/`continue` en producción "
                               "(P1.26)",
                "evidencia": "demo.py:4", "tipo_evidencia": "verified-real",
                "criterio": "c3_sin_silencios"}],
            "notas": ["4 líneas de test / 5 de código",
                      "suite NO ejecutada (sin --ejecutar-tests): no verificado",
                      "linter: pyproject.toml",
                      "c3 sobre 1 archivos de producción; tests/scripts excluidos",
                      "silencios detectados: 1",
                      "proporción test/código: 0.80",
                      "c5 sobre 1 archivos de test Python"]})

    def test_calidad_sin_codigo(self):
        raiz = crear_proyecto(self, {"README.md": "# Demo\n"})
        perfil = evaluar_proyecto.analizar_perfil(raiz)

        dimension = evaluar_proyecto.evaluar_calidad(raiz, perfil)

        self.assertEqual(dimension.a_dict(), {
            "puntuacion": None, "evaluado": False, "criterios": {},
            "no_aplica": [
                {"criterio": "c1_suite_de_tests", "motivo": "sin código"},
                {"criterio": "c2_linter_configurado", "motivo": "sin código"},
                {"criterio": "c3_sin_silencios",
                 "motivo": "sin código Python de producción"},
                {"criterio": "c4_tests_sobre_codigo_30pct",
                 "motivo": "sin código medible"},
                {"criterio": "c5_tests_con_aserciones",
                 "motivo": "sin archivos de test Python analizables"}],
            "hallazgos": [],
            "notas": ["0 líneas de test / 0 de código",
                      "suite NO ejecutada (sin --ejecutar-tests): no verificado"]})


class TestDependenciasPyprojectContrato(unittest.TestCase):
    """Contrato exacto de ámbitos y versiones del parser de pyproject."""

    def test_pep621_poetry_pdm_y_grupos(self):
        texto = (
            '[project]\nname = "demo"\nversion = "0.1.0"\n'
            'dependencies = ["requests>=2", "flask==3.0"]\n'
            '[project.optional-dependencies]\n'
            'dev = ["pytest>=8"]\ntest = ["coverage"]\n'
            'docs = ["sphinx"]\nruntime = ["uvicorn"]\notros = ["x"]\n'
            '[dependency-groups]\n'
            'dev = ["black"]\ntest = ["mypy"]\ndocs = ["mkdocs"]\n'
            '[tool.poetry.dependencies]\n'
            'python = "^3.11"\ndjango = "^4.2"\n'
            'numpy = {version = "1.26"}\n'
            '[tool.poetry.group.dev.dependencies]\nruff = "^0.1"\n'
            '[tool.poetry.group.test.dependencies]\ntox = "^4"\n')

        deps = evaluar_proyecto._dependencias_pyproject(texto)

        self.assertEqual([
            (d["nombre"], d["ambito"], d["operador"], d["version"],
             d["fijada"], d["origen"], d["ecosistema"]) for d in deps], [
            ("requests", "runtime", ">=", "2", False, "pyproject.toml", "python"),
            ("flask", "runtime", "==", "3.0", True, "pyproject.toml", "python"),
            ("pytest", "dev", ">=", "8", False, "pyproject.toml", "python"),
            ("coverage", "test", "", "", False, "pyproject.toml", "python"),
            ("sphinx", "docs", "", "", False, "pyproject.toml", "python"),
            ("uvicorn", "runtime", "", "", False, "pyproject.toml", "python"),
            ("x", "opcional", "", "", False, "pyproject.toml", "python"),
            ("black", "dev", "", "", False, "pyproject.toml", "python"),
            ("mypy", "test", "", "", False, "pyproject.toml", "python"),
            ("mkdocs", "docs", "", "", False, "pyproject.toml", "python"),
            ("django", "runtime", "", "", False, "pyproject.toml", "python"),
            ("numpy", "runtime", "==", "1.26", True, "pyproject.toml", "python"),
            ("ruff", "dev", "", "", False, "pyproject.toml", "python"),
            ("tox", "test", "", "", False, "pyproject.toml", "python")])


class TestVigenciaContrato(unittest.TestCase):
    """Contrato exacto de vigencia: criterios, N/A, notas y hallazgos."""

    def test_sin_dependencias(self):
        raiz = crear_proyecto(self, {"README.md": "# x\n"})
        perfil = evaluar_proyecto.analizar_perfil(raiz)

        dimension = evaluar_proyecto.evaluar_vigencia(
            raiz, perfil, con_red=False)

        self.assertEqual(dimension.a_dict(), {
            "puntuacion": None, "evaluado": False, "criterios": {},
            "no_aplica": [
                {"criterio": "v1_dependencias_fijadas",
                 "motivo": "sin dependencias Python runtime"},
                {"criterio": "v2_lockfile",
                 "motivo": "sin dependencias runtime detectadas"},
                {"criterio": "v3_actividad_reciente",
                 "motivo": "sin historial git: no se puede medir actividad"},
                {"criterio": "v4_dependencias_al_dia",
                 "motivo": "sin dependencias Python runtime que comparar"}],
            "hallazgos": [], "notas": ["sin git: actividad no evaluable"]})

    def test_fijadas_con_lock(self):
        raiz = crear_proyecto(self, {
            "requirements.txt": "requests==2.31.0\n",
            "requirements.lock": "requests==2.31.0\n"})
        perfil = evaluar_proyecto.analizar_perfil(raiz)

        dimension = evaluar_proyecto.evaluar_vigencia(
            raiz, perfil, con_red=False)

        self.assertEqual(dimension.a_dict(), {
            "puntuacion": 1.0, "evaluado": True,
            "criterios": {"v1_dependencias_fijadas": True,
                          "v2_lockfile": True},
            "no_aplica": [
                {"criterio": "v3_actividad_reciente",
                 "motivo": "sin historial git: no se puede medir actividad"},
                {"criterio": "v4_dependencias_al_dia",
                 "motivo": "comparación PyPI omitida (--sin-red): no verificada"}],
            "hallazgos": [],
            "notas": ["locks: requirements.lock",
                      "sin git: actividad no evaluable",
                      "comprobación PyPI OMITIDA (--sin-red): no verificado"]})

    def test_sin_fijar_ni_lock(self):
        raiz = crear_proyecto(self, {
            "requirements.txt": "requests>=2.0\n"})
        perfil = evaluar_proyecto.analizar_perfil(raiz)

        dimension = evaluar_proyecto.evaluar_vigencia(
            raiz, perfil, con_red=False)

        self.assertEqual(dimension.a_dict(), {
            "puntuacion": 0.0, "evaluado": True,
            "criterios": {"v1_dependencias_fijadas": False,
                          "v2_lockfile": False},
            "no_aplica": [
                {"criterio": "v3_actividad_reciente",
                 "motivo": "sin historial git: no se puede medir actividad"},
                {"criterio": "v4_dependencias_al_dia",
                 "motivo": "comparación PyPI omitida (--sin-red): no verificada"}],
            "hallazgos": [
                {"severidad": "media",
                 "descripcion": "Dependencias Python sin fijar: requests",
                 "evidencia": "manifiestos Python",
                 "tipo_evidencia": "verified-real",
                 "criterio": "v1_dependencias_fijadas"},
                {"severidad": "media",
                 "descripcion": "Sin lockfile para: python "
                                "(instalación no reproducible)",
                 "evidencia": str(raiz), "tipo_evidencia": "verified-real",
                 "criterio": "v2_lockfile"}],
            "notas": ["locks: ninguno", "sin git: actividad no evaluable",
                      "comprobación PyPI OMITIDA (--sin-red): no verificado"]})


class TestEficienciaFuncionalidadesContrato(unittest.TestCase):
    """Contrato exacto de las dimensiones eficiencia y funcionalidades."""

    def test_eficiencia_sin_llm(self):
        raiz = crear_proyecto(self, {"README.md": "# x\n"})
        perfil = evaluar_proyecto.analizar_perfil(raiz)

        dimension = evaluar_proyecto.evaluar_eficiencia(raiz, perfil)

        self.assertEqual(dimension.a_dict(), {
            "puntuacion": None, "evaluado": False, "criterios": {},
            "no_aplica": [
                {"criterio": "e1_import_perezoso_de_pesadas",
                 "motivo": "el proyecto no declara un LLM en dependencias "
                           "runtime"},
                {"criterio": "e2_carga_unica_de_modelos",
                 "motivo": "el proyecto no declara un LLM en dependencias "
                           "runtime"},
                {"criterio": "e3_mediciones_documentadas",
                 "motivo": "el proyecto no declara un LLM en dependencias "
                           "runtime"}],
            "hallazgos": [],
            "notas": ["dimensión N/A: señales específicas de sistemas LLM"]})

    def test_funcionalidades_sin_codigo(self):
        raiz = crear_proyecto(self, {"README.md": "# x\n"})
        perfil = evaluar_proyecto.analizar_perfil(raiz)

        dimension = evaluar_proyecto.evaluar_funcionalidades(raiz, perfil)

        self.assertEqual(dimension.a_dict(), {
            "puntuacion": None, "evaluado": False, "criterios": {},
            "no_aplica": [
                {"criterio": "f1_puntos_de_entrada",
                 "motivo": "sin archivos de código"},
                {"criterio": "f2_readme_vs_realidad",
                 "motivo": "sin código Python: no hay referencias .py que "
                           "contrastar"},
                {"criterio": "f3_sin_deuda_declarada",
                 "motivo": "sin código Python analizable"},
                {"criterio": "f4_tests_de_varios_modulos",
                 "motivo": "sin código"}],
            "hallazgos": [], "notas": []})

    def test_funcionalidades_biblioteca_con_deuda(self):
        raiz = crear_proyecto(self, {
            "pkg/__init__.py": "",
            "pkg/mod.py": "def f():\n    # TODO: x\n    return 1\n",
            "tests/test_a.py": "def test_a():\n    assert 1\n",
            "tests/test_b.py": "def test_b():\n    assert 2\n",
            "README.md": "# x\n"})
        perfil = evaluar_proyecto.analizar_perfil(raiz)

        dimension = evaluar_proyecto.evaluar_funcionalidades(raiz, perfil)

        self.assertEqual(dimension.a_dict(), {
            "puntuacion": 0.667, "evaluado": True,
            "criterios": {"f2_readme_vs_realidad": True,
                          "f3_sin_deuda_declarada": False,
                          "f4_tests_de_varios_modulos": True},
            "no_aplica": [{"criterio": "f1_puntos_de_entrada",
                           "motivo": "sin CLI/entrypoint declarado "
                                     "(proyecto tipo biblioteca)"}],
            "hallazgos": [{
                "severidad": "baja",
                "descripcion": "1 marcas TODO/FIXME/XXX en código de producción",
                "evidencia": "pkg/mod.py:2", "tipo_evidencia": "verified-real",
                "criterio": "f3_sin_deuda_declarada"}],
            "notas": ["2 archivos de test (.py)"]})

    def test_funcionalidades_cli_un_test(self):
        raiz = crear_proyecto(self, {
            "pyproject.toml": ('[project]\nname="x"\nversion="0.1.0"\n'
                               '[project.scripts]\nx="x:main"\n'),
            "x.py": "def main():\n    return 0\n",
            "tests/test_x.py": "def test_x():\n    assert 1\n",
            "README.md": "# x\n"})
        perfil = evaluar_proyecto.analizar_perfil(raiz)

        dimension = evaluar_proyecto.evaluar_funcionalidades(raiz, perfil)

        self.assertEqual(dimension.a_dict(), {
            "puntuacion": 0.75, "evaluado": True,
            "criterios": {"f1_puntos_de_entrada": True,
                          "f2_readme_vs_realidad": True,
                          "f3_sin_deuda_declarada": True,
                          "f4_tests_de_varios_modulos": False},
            "no_aplica": [],
            "hallazgos": [{
                "severidad": "baja",
                "descripcion": "Solo 1 archivo(s) de test: la cobertura por "
                               "módulos no se puede distribuir",
                "evidencia": "código del proyecto",
                "tipo_evidencia": "verified-real",
                "criterio": "f4_tests_de_varios_modulos"}],
            "notas": ["1 puntos de entrada: pyproject.toml ([project.scripts])",
                      "1 archivos de test (.py)"]})

    def test_herramientas_ci_y_changelog(self):
        raiz = crear_proyecto(self, {
            "LICENSE": "MIT\n", "Makefile": "test:\n\tpython -m unittest\n",
            "CHANGELOG.md": "# x\n"})
        perfil = evaluar_proyecto.analizar_perfil(raiz)

        dimension = evaluar_proyecto.evaluar_herramientas(
            raiz, perfil, con_red=False)

        self.assertEqual(dimension.a_dict(), {
            "puntuacion": 0.667, "evaluado": True,
            "criterios": {"h1_manifiesto": False, "h2_licencia": True,
                          "h7_decisiones_documentadas": True},
            "no_aplica": [
                {"criterio": "h3_verificacion_automatizada",
                 "motivo": "sin código"},
                {"criterio": "h4_runner_de_tests_declarado",
                 "motivo": "sin tests detectados"},
                {"criterio": "h5_licencias_libres",
                 "motivo": "sin dependencias Python runtime"},
                {"criterio": "h6_imports_declarados",
                 "motivo": "sin código Python de producción"}],
            "hallazgos": [{
                "severidad": "alta",
                "descripcion": "Sin manifiesto de dependencias",
                "evidencia": str(raiz), "tipo_evidencia": "verified-real",
                "criterio": "h1_manifiesto"}],
            "notas": ["registro de decisiones: CHANGELOG.md"]})

    def test_calidad_sin_suite_ni_linter(self):
        raiz = crear_proyecto(self, {"demo.py": "def f():\n    return 1\n"})
        perfil = evaluar_proyecto.analizar_perfil(raiz)

        dimension = evaluar_proyecto.evaluar_calidad(raiz, perfil)

        self.assertEqual(dimension.a_dict(), {
            "puntuacion": 0.25, "evaluado": True,
            "criterios": {"c1_suite_de_tests": False,
                          "c2_linter_configurado": False,
                          "c3_sin_silencios": True,
                          "c4_tests_sobre_codigo_30pct": False},
            "no_aplica": [{"criterio": "c5_tests_con_aserciones",
                           "motivo": "sin archivos de test Python analizables"}],
            "hallazgos": [
                {"severidad": "alta",
                 "descripcion": "Sin suite de tests: los cambios no tienen "
                                "red de seguridad",
                 "evidencia": "código del proyecto",
                 "tipo_evidencia": "verified-real",
                 "criterio": "c1_suite_de_tests"},
                {"severidad": "media",
                 "descripcion": "Sin linter configurado (ruff/flake8/pylint, "
                                "eslint, checkstyle/spotless)",
                 "evidencia": "manifiestos/raíz",
                 "tipo_evidencia": "verified-real",
                 "criterio": "c2_linter_configurado"},
                {"severidad": "media",
                 "descripcion": "Proporción test/código 0.00 < 0.30",
                 "evidencia": "código y tests",
                 "tipo_evidencia": "verified-real",
                 "criterio": "c4_tests_sobre_codigo_30pct"}],
            "notas": ["0 líneas de test / 2 de código",
                      "suite NO ejecutada (sin --ejecutar-tests): no verificado",
                      "c3 sobre 1 archivos de producción; tests/scripts excluidos",
                      "proporción test/código: 0.00"]})


class TestMasRamasDelEvaluador(unittest.TestCase):
    """Silencios aceptados, h5/h6, vigencia con red y licencias PyPI."""

    def test_calidad_silencio_aceptado_y_sintaxis(self):
        raiz = crear_proyecto(self, {
            "pkg/__init__.py": "",
            "pkg/a.py": ("def f():\n    try:\n        return 1\n"
                         "    except Exception:  # noqa: silent: motivo\n"
                         "        pass\n"),
            "pkg/b.py": "def f(:\n",
            "tests/test_a.py": "def test_a():\n    assert 1\n",
            "pyproject.toml": "[tool.ruff]\nline-length=100\n"})
        perfil = evaluar_proyecto.analizar_perfil(raiz)

        dimension = evaluar_proyecto.evaluar_calidad(raiz, perfil)

        self.assertEqual(dimension.a_dict(), {
            "puntuacion": 1.0, "evaluado": True,
            "criterios": {"c1_suite_de_tests": True,
                          "c2_linter_configurado": True,
                          "c3_sin_silencios": True,
                          "c4_tests_sobre_codigo_30pct": True,
                          "c5_tests_con_aserciones": True},
            "no_aplica": [],
            "hallazgos": [{
                "severidad": "baja",
                "descripcion": "Silencio aceptado (warning): motivo",
                "evidencia": "pkg/a.py:4", "tipo_evidencia": "verified-real",
                "criterio": "c3_sin_silencios"}],
            "notas": [
                "2 líneas de test / 6 de código",
                "suite NO ejecutada (sin --ejecutar-tests): no verificado",
                "linter: pyproject.toml",
                "c3 sobre 3 archivos de producción; tests/scripts excluidos",
                "silencios aceptados (warning): 1",
                "código con error de sintaxis (no evaluable en c3): pkg/b.py:1",
                "proporción test/código: 0.33",
                "c5 sobre 1 archivos de test Python"]})

    def test_calidad_suite_ejecutada_falla(self):
        raiz = crear_proyecto(self, {
            "pkg/__init__.py": "",
            "pkg/a.py": "def f():\n    return 1\n",
            "tests/test_a.py": "def test_a():\n    assert 1\n",
            "pyproject.toml": "[tool.ruff]\n"})
        perfil = evaluar_proyecto.analizar_perfil(raiz)
        resultado = {"ejecutado": True, "ok": False, "codigo": 1,
                     "resumen": "1 failed",
                     "comando": ["python", "-m", "pytest"],
                     "duracion_s": 1.2}

        dimension = evaluar_proyecto.evaluar_calidad(
            raiz, perfil, ejecutar=True, resultado_tests=resultado)

        self.assertEqual(dimension.a_dict(), {
            "puntuacion": 0.833, "evaluado": True,
            "criterios": {"c1_suite_de_tests": True, "c1b_suite_pasa": False,
                          "c2_linter_configurado": True,
                          "c3_sin_silencios": True,
                          "c4_tests_sobre_codigo_30pct": True,
                          "c5_tests_con_aserciones": True},
            "no_aplica": [],
            "hallazgos": [{
                "severidad": "alta", "descripcion": "La suite NO pasa: 1 failed",
                "evidencia": ["python", "-m", "pytest"],
                "tipo_evidencia": "verified-real",
                "criterio": "c1b_suite_pasa"}],
            "notas": [
                "2 líneas de test / 2 de código",
                "suite: 1 failed (['python', '-m', 'pytest'], 1.2s)",
                "linter: pyproject.toml",
                "c3 sobre 2 archivos de producción; tests/scripts excluidos",
                "proporción test/código: 1.00",
                "c5 sobre 1 archivos de test Python"]})

    def test_herramientas_import_sin_declarar(self):
        raiz = crear_proyecto(self, {
            "pyproject.toml": '[project]\nname="x"\nversion="0.1.0"\n',
            "pkg/__init__.py": "", "pkg/app.py": "import requests\n",
            "tests/test_a.py": "def test_a():\n    assert 1\n"})
        perfil = evaluar_proyecto.analizar_perfil(raiz)

        dimension = evaluar_proyecto.evaluar_herramientas(
            raiz, perfil, con_red=False)

        d = dimension.a_dict()
        self.assertEqual(d["criterios"]["h6_imports_declarados"], False)
        self.assertEqual(d["notas"][-1], "imports de terceros sin declarar: 1")
        self.assertIn("pkg/app.py:1", [h["evidencia"] for h in d["hallazgos"]])
        self.assertIn("Import de terceros sin declarar: import no declarado: "
                      "requests", [h["descripcion"] for h in d["hallazgos"]])

    def test_herramientas_h5_con_licencia_no_libre(self):
        raiz = crear_proyecto(self, {
            "pyproject.toml": ('[project]\nname="x"\nversion="0.1.0"\n'
                               'dependencies=["requests","flask"]\n'),
            "LICENSE": "MIT\n", "pkg/__init__.py": "",
            "pkg/app.py": "import requests\n",
            "tests/test_a.py": "def test_a():\n    assert 1\n"})
        perfil = evaluar_proyecto.analizar_perfil(raiz)

        def side(nombre):
            if nombre == "requests":
                return {"licencia": "MIT", "libre": True,
                        "fuente": "license_expression", "error": ""}
            return {"licencia": "propietaria", "libre": False,
                    "fuente": "license", "error": ""}

        with patch("evaluar_proyecto.licencia_pypi", side_effect=side):
            dimension = evaluar_proyecto.evaluar_herramientas(
                raiz, perfil, con_red=True)

        d = dimension.a_dict()
        self.assertEqual(d["criterios"]["h5_licencias_libres"], False)
        self.assertIn("Dependencias sin licencia libre declarada: flask "
                      "(propietaria)",
                      [h["descripcion"] for h in d["hallazgos"]])
        self.assertIn("licencias consultadas en PyPI: 2 (runtime; 0 de "
                      "desarrollo/opcionales excluidas)", d["notas"])

    def test_vigencia_con_red_marca_atrasada(self):
        raiz = crear_proyecto(self, {
            "requirements.txt": "requests==2.0\n",
            "requirements.lock": "requests==2.0\n"})
        perfil = evaluar_proyecto.analizar_perfil(raiz)

        with patch("evaluar_proyecto.ultima_version_pypi",
                   return_value={"version": "2.31.0", "error": ""}):
            dimension = evaluar_proyecto.evaluar_vigencia(
                raiz, perfil, con_red=True)

        self.assertEqual(dimension.a_dict(), {
            "puntuacion": 0.667, "evaluado": True,
            "criterios": {"v1_dependencias_fijadas": True,
                          "v2_lockfile": True,
                          "v4_dependencias_al_dia": False},
            "no_aplica": [{"criterio": "v3_actividad_reciente",
                           "motivo": "sin historial git: no se puede medir "
                                     "actividad"}],
            "hallazgos": [{
                "severidad": "media",
                "descripcion": "Dependencia atrasada: requests 2.0 -> 2.31.0",
                "evidencia": "PyPI (pypi.org/pypi)",
                "tipo_evidencia": "verified-real",
                "criterio": "v4_dependencias_al_dia"}],
            "notas": ["locks: requirements.lock",
                      "sin git: actividad no evaluable"]})

    def test_licencia_pypi_ramas(self):
        class Respuesta(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        casos = [
            ({"license_expression": "MIT"},
             {"licencia": "MIT", "libre": True, "fuente": "license_expression",
              "error": ""}),
            ({"classifiers": ["License :: OSI Approved :: MIT License"]},
             {"licencia": "MIT License", "libre": True,
              "fuente": "classifier", "error": ""}),
            ({"license": "Apache-2.0"},
             {"licencia": "Apache-2.0", "libre": True, "fuente": "license",
              "error": ""}),
            ({"license": "unknown"},
             {"licencia": "desconocida", "libre": None, "fuente": "",
              "error": ""}),
        ]
        for info, esperado in casos:
            with self.subTest(info=info):
                cuerpo = json.dumps({"info": info}).encode()
                with patch("evaluar_proyecto.urllib.request.urlopen",
                           return_value=Respuesta(cuerpo)):
                    self.assertEqual(
                        evaluar_proyecto.licencia_pypi("x"), esperado)

        with patch("evaluar_proyecto.urllib.request.urlopen",
                   side_effect=OSError("boom")):
            self.assertEqual(
                evaluar_proyecto.licencia_pypi("x"),
                {"licencia": "desconocida", "libre": None, "fuente": "",
                 "error": "OSError: boom"})

    def test_licencias_no_runtime_sin_y_con_red(self):
        raiz = crear_proyecto(self, {
            "pyproject.toml": ('[project]\nname="x"\nversion="0.1.0"\n'
                               '[project.optional-dependencies]\n'
                               'dev=["pytest>=8"]\n')})
        perfil = evaluar_proyecto.analizar_perfil(raiz)
        base = {"nombre": "pytest", "ambito": "dev",
                "origen": "pyproject.toml", "version": "8",
                "operador": ">=", "licencia": None, "libre": None,
                "fuente": "no consultada (--sin-red)",
                "procedencia": "unverified"}

        self.assertEqual(
            evaluar_proyecto.licencias_no_runtime(perfil, False), [base])

        with patch("evaluar_proyecto.licencia_pypi",
                   return_value={"licencia": "MIT", "libre": True,
                                 "fuente": "license_expression", "error": ""}):
            con_red = evaluar_proyecto.licencias_no_runtime(perfil, True)
        self.assertEqual(con_red, [{**base, "licencia": "MIT", "libre": True,
                                    "fuente": "license_expression",
                                    "procedencia": "real"}])


class TestParserEjecutarEInteligencia(unittest.TestCase):
    """Contrato de requisitos, runner de tests y dimensión inteligencia."""

    def test_parsear_requisitos_completo(self):
        raiz = crear_proyecto(self, {"requisitos.md": (
            "## R1: Login\n- Enunciado: El usuario inicia sesión.\n"
            "  Con correo y clave.\n- Criterio: La sesión dura 1 hora.\n"
            "- Verificación: test\n- Evidencia: tests/test_login.py\n"
            "- Tags: auth, login\n- Notas: revisar con seguridad\n"
            "- Campo raro: x\n\n"
            "## R2: Logout\n- Enunciado: El usuario cierra sesión.\n"
            "- Criterio de aceptación: La sesión se invalida.\n"
            "- Verificación: manual\n")})

        requisitos = parsear_requisitos(raiz / "requisitos.md")

        self.assertEqual([vars(r) for r in requisitos], [
            {"id": "R1", "titulo": "Login",
             "enunciado": "El usuario inicia sesión. Con correo y clave.",
             "criterio": "La sesión dura 1 hora.",
             "origen": "requisitos.md:1", "verificacion": "test",
             "evidencia": "tests/test_login.py",
             "tags": ["auth", "login"],
             "avisos": ["línea 8: revisar con seguridad",
                        "línea 9: campo no reconocido: Campo raro"]},
            {"id": "R2", "titulo": "Logout",
             "enunciado": "El usuario cierra sesión.",
             "criterio": "La sesión se invalida.",
             "origen": "requisitos.md:11", "verificacion": "manual",
             "evidencia": "", "tags": [], "avisos": []}])

    def test_inteligencia_sin_llm(self):
        raiz = crear_proyecto(self, {"README.md": "# x\n"})
        perfil = evaluar_proyecto.analizar_perfil(raiz)

        dimension = evaluar_proyecto.evaluar_inteligencia(raiz, perfil)

        self.assertEqual(dimension.a_dict(), {
            "puntuacion": None, "evaluado": False, "criterios": {},
            "no_aplica": [
                {"criterio": f"i{n}_{nombre}",
                 "motivo": "el proyecto no declara un LLM en dependencias "
                           "runtime"}
                for n, nombre in enumerate((
                    "cachea_trabajo_repetido", "timeouts_explicitos",
                    "reintentos_con_limite", "valida_respuestas",
                    "declara_lo_simulado", "metricas_propias"), 1)],
            "hallazgos": [],
            "notas": ["dimensión N/A: señales específicas de sistemas LLM"]})

    def test_ejecutar_tests_sin_runner(self):
        raiz = crear_proyecto(self, {"README.md": "# x\n"})

        with patch("evaluar_proyecto.detectar_comando_tests",
                   return_value=None):
            self.assertEqual(
                evaluar_proyecto.ejecutar_tests(raiz),
                {"ejecutado": False,
                 "motivo": "no se encontró un comando de tests declarado"})

    def test_ejecutar_tests_con_runner(self):
        raiz = crear_proyecto(self, {"README.md": "# x\n"})
        proceso = SimpleNamespace(
            returncode=0, stdout="Ran 5 tests in 0.1s\n\nOK\n", stderr="")

        with patch("evaluar_proyecto.detectar_comando_tests",
                   return_value={"comando": ["python", "-m", "unittest"],
                                 "origen": "convención"}), \
                patch("evaluar_proyecto.subprocess.run",
                      return_value=proceso) as ejecutar, \
                patch("evaluar_proyecto.time.monotonic",
                      side_effect=[100.0, 101.2]):
            resultado = evaluar_proyecto.ejecutar_tests(raiz)

        self.assertEqual(resultado, {
            "ejecutado": True, "comando": "python -m unittest",
            "origen": "convención", "codigo": 0, "ok": True, "tests": 5,
            "resumen": "OK", "duracion_s": 1.2})
        self.assertEqual(ejecutar.call_args.args[0],
                         ["python", "-m", "unittest"])
        self.assertFalse(ejecutar.call_args.kwargs["shell"])


class TestParsersDependenciasYLinter(unittest.TestCase):
    """Contrato exacto de setup.cfg, package.json, agregador y linter."""

    def test_setup_cfg_completo(self):
        raiz = crear_proyecto(self, {"setup.cfg": (
            "[options]\ninstall_requires =\n    requests>=2\n"
            "    flask==3.0\ntests_require =\n    pytest>=8\n"
            "[options.extras_require]\ndocs =\n    sphinx\n"
            "test =\n    coverage\notros =\n    rich\n")})

        deps = evaluar_proyecto._dependencias_setup_cfg(
            raiz / "setup.cfg", raiz)

        self.assertEqual([
            (d["nombre"], d["ambito"], d["operador"], d["version"],
             d["fijada"], d["origen"], d["ecosistema"]) for d in deps], [
            ("requests", "runtime", ">=", "2", False, "setup.cfg", "python"),
            ("flask", "runtime", "==", "3.0", True, "setup.cfg", "python"),
            ("pytest", "dev", ">=", "8", False, "setup.cfg", "python"),
            ("sphinx", "docs", "", "", False, "setup.cfg", "python"),
            ("coverage", "test", "", "", False, "setup.cfg", "python"),
            ("rich", "opcional", "", "", False, "setup.cfg", "python")])

    def test_package_json_completo(self):
        raiz = crear_proyecto(self, {"package.json": (
            '{"dependencies":{"react":"^18.2.0","left-pad":"1.3.0"},'
            '"devDependencies":{"typescript":"~5.0"},'
            '"peerDependencies":{"react-dom":">=18"}}')})

        deps = evaluar_proyecto._dependencias_package_json(
            raiz / "package.json", raiz)

        self.assertEqual([
            (d["nombre"], d["ambito"], d["operador"], d["version"],
             d["fijada"], d["origen"], d["ecosistema"]) for d in deps], [
            ("react", "runtime", "^", "18.2.0", False, "package.json", "npm"),
            ("left-pad", "runtime", "", "1.3.0", True, "package.json", "npm"),
            ("typescript", "dev", "~", "5.0", False, "package.json", "npm"),
            ("react-dom", "opcional", ">=", "18", False, "package.json",
             "npm")])

    def test_agregador_dependencias(self):
        raiz = crear_proyecto(self, {
            "setup.cfg": ("[options]\ninstall_requires =\n    requests>=2\n"
                          "    flask==3.0\ntests_require =\n    pytest>=8\n"
                          "[options.extras_require]\ndocs =\n    sphinx\n"
                          "test =\n    coverage\notros =\n    rich\n"),
            "package.json": ('{"dependencies":{"react":"^18.2.0",'
                             '"left-pad":"1.3.0"},'
                             '"devDependencies":{"typescript":"~5.0"},'
                             '"peerDependencies":{"react-dom":">=18"}}'),
            "requirements.txt": "requests>=2\n",
            "pyproject.toml": ('[project]\nname="x"\nversion="0.1.0"\n'
                               '[tool.ruff]\n')})

        deps = evaluar_proyecto._dependencias(raiz)

        self.assertEqual([
            (d["nombre"], d["ambito"], d["operador"], d["version"],
             d["fijada"], d["origen"], d["ecosistema"]) for d in deps], [
            ("react", "runtime", "^", "18.2.0", False, "package.json", "npm"),
            ("left-pad", "runtime", "", "1.3.0", True, "package.json", "npm"),
            ("typescript", "dev", "~", "5.0", False, "package.json", "npm"),
            ("react-dom", "opcional", ">=", "18", False, "package.json",
             "npm"),
            ("requests", "runtime", ">=", "2", False, "requirements.txt",
             "python"),
            ("flask", "runtime", "==", "3.0", True, "setup.cfg", "python"),
            ("pytest", "dev", ">=", "8", False, "setup.cfg", "python"),
            ("sphinx", "docs", "", "", False, "setup.cfg", "python"),
            ("coverage", "test", "", "", False, "setup.cfg", "python"),
            ("rich", "opcional", "", "", False, "setup.cfg", "python")])

    def test_linter_configurado_por_archivo(self):
        casos = {
            "pyproject.toml": "[tool.ruff]\n",
            "setup.cfg": "[flake8]\nmax-line-length=100\n",
            ".ruff.toml": "line-length = 100\n",
            ".eslintrc.json": '{"extends": "eslint:recommended"}\n',
        }
        for nombre, contenido in casos.items():
            with self.subTest(nombre=nombre):
                raiz = crear_proyecto(self, {nombre: contenido})
                perfil = evaluar_proyecto.analizar_perfil(raiz)
                self.assertEqual(evaluar_proyecto._linter_configurado(perfil),
                                 (True, nombre))

        raiz = crear_proyecto(self, {"README.md": "# x\n"})
        perfil = evaluar_proyecto.analizar_perfil(raiz)
        self.assertEqual(evaluar_proyecto._linter_configurado(perfil),
                         (False, ""))


class TestPuntosDeEntradaYMain(unittest.TestCase):
    """Detección de entrypoints y contrato de la CLI."""

    def test_puntos_de_entrada_python_java_go_y_manifiestos(self):
        raiz = crear_proyecto(self, {
            "pkg/__init__.py": "", "pkg/__main__.py": "print('x')\n",
            "app.py": ("def main():\n    pass\n"
                       "if __name__ == '__main__':\n    main()\n"),
            "Main.java": "class Main { public static void main(String[] a) {} }\n",
            "main.go": "package main\nfunc main() {}\n",
            "pyproject.toml": ('[project]\nname="x"\nversion="0.1.0"\n'
                               '[project.scripts]\nx="x:main"\n'),
            "package.json": '{"bin":{"x":"cli.js"},"main":"index.js"}\n'})
        perfil = evaluar_proyecto.analizar_perfil(raiz)

        self.assertEqual(evaluar_proyecto._tiene_punto_entrada(raiz, perfil), [
            "Main.java", "app.py", "main.go", "package.json (bin/main)",
            "pkg/__main__.py", "pyproject.toml ([project.scripts])"])

    def test_sin_puntos_de_entrada(self):
        raiz = crear_proyecto(self, {"lib.py": "def f():\n    return 1\n"})
        perfil = evaluar_proyecto.analizar_perfil(raiz)

        self.assertEqual(evaluar_proyecto._tiene_punto_entrada(raiz, perfil), [])

    def test_main_json_llama_evaluar_y_serializa(self):
        salida = io.StringIO()
        with patch("evaluar_proyecto.evaluar",
                   return_value={"b": 2, "a": 1}) as evaluar_mock:
            with contextlib.redirect_stdout(salida):
                codigo = main(["proyecto", "--json", "--sin-red"])

        self.assertEqual(codigo, 0)
        self.assertEqual(json.loads(salida.getvalue()), {"b": 2, "a": 1})
        evaluar_mock.assert_called_once()
        self.assertFalse(evaluar_mock.call_args.kwargs["con_red"])
        self.assertEqual(evaluar_mock.call_args.args[0],
                         Path("proyecto").resolve())

    def test_main_requisitos_inexistentes(self):
        error = io.StringIO()
        with contextlib.redirect_stderr(error):
            codigo = main(["proyecto", "--requisitos", "/no/existe.md"])

        self.assertEqual(codigo, 2)
        self.assertIn("no existe el archivo de requisitos", error.getvalue())


class TestEficienciaLLMContrato(unittest.TestCase):
    """Contrato exacto de eficiencia en un proyecto que declara LLM."""

    def test_eficiencia_llm_con_import_perezoso_y_mediciones(self):
        raiz = crear_proyecto(self, {
            "pyproject.toml": ('[project]\nname="x"\nversion="0.1.0"\n'
                               'dependencies=["openai","torch"]\n'),
            "app.py": ("def f():\n    import torch\n    return torch\n\n"
                       "modelo = create_model()\n"),
            "README.md": "Tiempo 1.2 s y RAM 300 MB\n",
        })
        perfil = evaluar_proyecto.analizar_perfil(raiz)

        dimension = evaluar_proyecto.evaluar_eficiencia(raiz, perfil)

        self.assertEqual(dimension.a_dict(), {
            "puntuacion": 1.0, "evaluado": True,
            "criterios": {"e1_import_perezoso_de_pesadas": True,
                          "e2_carga_unica_de_modelos": True,
                          "e3_mediciones_documentadas": True},
            "no_aplica": [], "hallazgos": [],
            "notas": ["imports perezosos detectados: 1",
                      "llamadas de carga de modelo: 1",
                      "sin medición en vivo: no se ejecuta código del proyecto "
                      "evaluado (P0.8)"]})

    def test_eficiencia_llm_sin_perezoso_ni_mediciones(self):
        raiz = crear_proyecto(self, {
            "pyproject.toml": ('[project]\nname="x"\nversion="0.1.0"\n'
                               'dependencies=["torch"]\n'),
            "app.py": "import torch\n",
            "README.md": "# x\n",
        })
        perfil = evaluar_proyecto.analizar_perfil(raiz)

        dimension = evaluar_proyecto.evaluar_eficiencia(raiz, perfil)

        self.assertEqual(dimension.a_dict(), {
            "puntuacion": 0.0, "evaluado": True,
            "criterios": {"e1_import_perezoso_de_pesadas": False,
                          "e2_carga_unica_de_modelos": False,
                          "e3_mediciones_documentadas": False},
            "no_aplica": [],
            "hallazgos": [
                {"severidad": "media",
                 "descripcion": "Dependencia pesada importada al cargar el "
                                "módulo (no de forma perezosa)",
                 "evidencia": "código de producción",
                 "tipo_evidencia": "verified-real",
                 "criterio": "e1_import_perezoso_de_pesadas"},
                {"severidad": "media",
                 "descripcion": "Sin señal de carga única/reutilizada de "
                                "modelos (create_model/cargar_modelo/"
                                "_load_model)",
                 "evidencia": "código de producción",
                 "tipo_evidencia": "verified-real",
                 "criterio": "e2_carga_unica_de_modelos"},
                {"severidad": "baja",
                 "descripcion": "Sin mediciones reales (tiempo/RAM) en la "
                                "documentación (*.md/*.rst) del repositorio",
                 "evidencia": "*.md|*.rst del repositorio",
                 "tipo_evidencia": "verified-real",
                 "criterio": "e3_mediciones_documentadas"}],
            "notas": ["imports perezosos detectados: 0",
                      "llamadas de carga de modelo: 0",
                      "sin medición en vivo: no se ejecuta código del proyecto "
                      "evaluado (P0.8)"]})


class TestSintesisContrato(unittest.TestCase):
    """Contrato exacto de la síntesis LLM y de su control anti-invención."""

    def _fixture(self):
        return crear_proyecto(self, {
            "app.py": "import requests\n",
            "requirements.txt": "requests==2.31.0\n"})

    def test_sintesis_campos_respaldo_y_modelo(self):
        from evaluar_proyecto import sintetizar_con_llm
        from tests.helpers import StubLLM

        respuesta = ('{"propuestas": [{"dimension": "calidad", '
                     '"propuesta": "unificar", "por_que": "x", '
                     '"evidencia": "requirements.txt", "como_verificar": "y"}, '
                     '{"dimension": "vigencia", "propuesta": "fijar", '
                     '"por_que": "z", "evidencia": "", "como_verificar": "w"}], '
                     '"preguntas_abiertas": [123, "¿y esto?"]}')
        informe = evaluar(self._fixture(), con_red=False)

        sintesis = sintetizar_con_llm(informe, StubLLM(lambda p: respuesta))

        self.assertEqual(sintesis, {
            "modelo": "?",
            "propuestas": [
                {"dimension": "calidad", "propuesta": "unificar",
                 "por_que": "x", "evidencia": "requirements.txt",
                 "como_verificar": "y", "con_respaldo": True},
                {"dimension": "vigencia", "propuesta": "fijar",
                 "por_que": "z", "evidencia": "", "como_verificar": "w",
                 "con_respaldo": False}],
            "preguntas_abiertas": ["123", "¿y esto?"],
            "sin_respaldo": 1})

    def test_sintesis_propuestas_no_lista_es_error(self):
        from evaluar_proyecto import sintetizar_con_llm
        from tests.helpers import StubLLM

        with self.assertRaisesRegex(ValueError, "propuestas"):
            sintetizar_con_llm(
                evaluar(self._fixture(), con_red=False),
                StubLLM(lambda p: '{"propuestas": "x"}'))


class TestMainRamas(unittest.TestCase):
    """Ramas de main que no estaban cubiertas: LLM, tests, requisitos y texto."""

    def test_main_sintesis_llm_y_modelo(self):
        with patch.object(evaluar_proyecto, "cargar_entorno_llm"), \
                patch.dict(os.environ, {"OPENROUTER_API_KEY": "k"}), \
                patch("llm_providers.OpenRouterLLM") as clase_llm, \
                patch.object(evaluar_proyecto, "evaluar",
                             return_value={"x": 1}) as evaluar_mock:
            codigo = main([".", "--sintesis-llm", "--modelo", "m", "--json"])

        self.assertEqual(codigo, 0)
        clase_llm.assert_called_once_with(model="m")
        self.assertIs(evaluar_mock.call_args.kwargs["llm"],
                      clase_llm.return_value)
        self.assertFalse(evaluar_mock.call_args.kwargs["investigar"])

    def test_main_investigar_y_ejecutar_tests(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md") as archivo:
            archivo.write("## R1: x\n- Enunciado: y\n- Criterio: z\n")
            archivo.flush()
            with patch.object(evaluar_proyecto, "cargar_entorno_llm"), \
                    patch.dict(os.environ, {"OPENROUTER_API_KEY": "k"}), \
                    patch("llm_providers.OpenRouterLLM"), \
                    patch.object(evaluar_proyecto, "evaluar",
                                 return_value={"x": 1}) as evaluar_mock:
                codigo = main([".", "--investigar", "--ejecutar-tests",
                               "--requisitos", archivo.name, "--json"])

        self.assertEqual(codigo, 0)
        self.assertTrue(evaluar_mock.call_args.kwargs["investigar"])
        self.assertTrue(evaluar_mock.call_args.kwargs["ejecutar_tests_flag"])
        self.assertEqual(evaluar_mock.call_args.kwargs["requisitos_path"],
                         Path(archivo.name).resolve())

    def test_main_texto_imprime_informe_texto(self):
        salida = io.StringIO()
        with patch.object(evaluar_proyecto, "evaluar",
                          return_value={"x": 1}), \
                patch.object(evaluar_proyecto, "informe_texto",
                             return_value=["linea1", "linea2"]):
            with contextlib.redirect_stdout(salida):
                codigo = main([".", "--sin-red"])

        self.assertEqual(codigo, 0)
        self.assertEqual(salida.getvalue(), "linea1\nlinea2\n")

    def test_main_sin_dotenv_devuelve_dos(self):
        error = io.StringIO()
        with patch.object(evaluar_proyecto, "cargar_entorno_llm",
                          side_effect=ImportError), \
                patch.object(evaluar_proyecto, "evaluar") as evaluar_mock:
            with contextlib.redirect_stderr(error):
                codigo = main([".", "--sintesis-llm"])

        self.assertEqual(codigo, 2)
        self.assertIn("python-dotenv", error.getvalue())
        evaluar_mock.assert_not_called()


class TestAmbitoVerificarYCobertura(unittest.TestCase):
    """Ámbito de requirements, contrato de _verificar_test y cobertura."""

    def test_ambito_requirements_por_ruta_y_nombre(self):
        raiz = crear_proyecto(self, {
            "requirements.txt": "requests==2\n",
            "requirements-dev.txt": "pytest\n",
            "requirements-docs.txt": "sphinx\n",
            "docs/requirements.txt": "sphinx\n",
            "tests/requirements.txt": "pytest\n",
            "prod.txt": "requests==2\n",
            "sub/requirements.txt": "x\n",
        })
        esperado = {
            "requirements.txt": "runtime",
            "requirements-dev.txt": "dev",
            "requirements-docs.txt": "docs",
            "docs/requirements.txt": "docs",
            "tests/requirements.txt": "test",
            "prod.txt": "runtime",
            "sub/requirements.txt": "dev",
        }
        for nombre, ambito in esperado.items():
            with self.subTest(nombre=nombre):
                self.assertEqual(
                    evaluar_proyecto._ambito_requirements(
                        raiz / nombre, raiz), ambito)

    def test_verificar_test_ramas(self):
        raiz = crear_proyecto(self, {
            "tests/test_x.py": "def test_x():\n    assert True\n",
            "tests/test_x.txt": "no es python\n",
            "tests/test_otro.py": "def test_otro():\n    assert True\n",
        })
        req = SimpleNamespace
        verificar = evaluar_proyecto._verificar_test
        sin = evaluar_proyecto.EvidenceKind.UNVERIFIED
        real = evaluar_proyecto.EvidenceKind.VERIFIED_REAL

        self.assertEqual(
            verificar(raiz, req(evidencia=""), None),
            ("NO VERIFICABLE", "método 'test' sin evidencia declarada", "",
             sin))
        self.assertEqual(
            verificar(raiz, req(evidencia="../fuera.py::test_x"), None),
            ("NO VERIFICABLE",
             "evidencia fuera del proyecto o no resoluble",
             "../fuera.py::test_x", sin))
        self.assertEqual(
            verificar(raiz, req(evidencia="tests/no_existe.py::test_x"), None),
            ("NO CUMPLE", "la evidencia declarada no es un archivo",
             "tests/no_existe.py", real))
        self.assertEqual(
            verificar(raiz, req(evidencia="tests/test_x.py"), None),
            ("CUBIERTO", "archivo de test declarado, sin test concreto",
             "tests/test_x.py", real))
        self.assertEqual(
            verificar(raiz, req(evidencia="tests/test_x.txt::test_x"), None),
            ("CUBIERTO",
             "test declarado en lenguaje no Python: no validado "
             "estáticamente", "tests/test_x.txt", real))
        self.assertEqual(
            verificar(raiz, req(evidencia="tests/test_otro.py::test_x"), None),
            ("NO CUMPLE", "el test 'test_x' no existe en el archivo",
             "tests/test_otro.py", real))
        self.assertEqual(
            verificar(raiz, req(evidencia="tests/test_x.py::test_x"), None),
            ("CUBIERTO", "test declarado; suite no ejecutada "
                         "(--ejecutar-tests)", "tests/test_x.py", real))
        self.assertEqual(
            verificar(raiz, req(evidencia="tests/test_x.py::test_x"),
                     {"ejecutado": False, "motivo": "sin runner"}),
            ("CUBIERTO", "test declarado; sin runner", "tests/test_x.py", sin))
        self.assertEqual(
            verificar(raiz, req(evidencia="tests/test_x.py::test_x"),
                     {"ejecutado": True, "ok": False}),
            ("NO CUMPLE", "la suite falló; el test declarado no pasa",
             "tests/test_x.py", real))
        self.assertEqual(
            verificar(raiz, req(evidencia="tests/test_x.py::test_x"),
                     {"ejecutado": True, "ok": True}),
            ("CUMPLE", "suite completa verde (test declarado, no aislado)",
             "tests/test_x.py", real))

    def test_verificar_test_contrato_exacto_bordes(self):
        """Bordes exactos de _verificar_test (R3: 16 mutantes supervivientes)."""
        raiz = crear_proyecto(self, {
            "tests/test_x.py": "def test_x():\n    assert True\n",
            "tests/test_roto.py": "def test_roto(:\n",
        })
        req = SimpleNamespace
        verificar = evaluar_proyecto._verificar_test
        sin = evaluar_proyecto.EvidenceKind.UNVERIFIED
        real = evaluar_proyecto.EvidenceKind.VERIFIED_REAL

        # Las comillas/backticks de los bordes se eliminan antes de dividir
        self.assertEqual(
            verificar(raiz, req(evidencia="`tests/test_x.py::test_x`"), None),
            ("CUBIERTO", "test declarado; suite no ejecutada "
                         "(--ejecutar-tests)", "tests/test_x.py", real))
        # El juego de caracteres eliminados es exactamente ` ' " (sin "X")
        self.assertEqual(
            verificar(raiz, req(evidencia="tests/test_x.py::test_xX"), None),
            ("NO CUMPLE", "el test 'test_xX' no existe en el archivo",
             "tests/test_x.py", real))
        # El nombre del test conserva los "::" internos al unir partes
        self.assertEqual(
            verificar(raiz,
                      req(evidencia="tests/test_x.py::test_x::extra"), None),
            ("NO CUMPLE", "el test 'test_x::extra' no existe en el archivo",
             "tests/test_x.py", real))
        # Archivo de test no analizable (error de sintaxis): NO VERIFICABLE
        self.assertEqual(
            verificar(raiz, req(evidencia="tests/test_roto.py::test_x"), None),
            ("NO VERIFICABLE", "no se pudo analizar el archivo de test",
             "tests/test_roto.py", sin))
        # Un error de suite se reporta aunque haya ejecución
        self.assertEqual(
            verificar(raiz, req(evidencia="tests/test_x.py::test_x"),
                      {"ejecutado": True, "error": "boom"}),
            ("CUBIERTO", "test declarado; boom", "tests/test_x.py", sin))
        # Motivo vacío cae al error; sin motivo ni error, al genérico
        self.assertEqual(
            verificar(raiz, req(evidencia="tests/test_x.py::test_x"),
                      {"ejecutado": False, "motivo": "",
                       "error": "cayo el runner"}),
            ("CUBIERTO", "test declarado; cayo el runner", "tests/test_x.py",
             sin))
        self.assertEqual(
            verificar(raiz, req(evidencia="tests/test_x.py::test_x"),
                      {"ejecutado": False}),
            ("CUBIERTO", "test declarado; suite no ejecutada",
             "tests/test_x.py", sin))

    def test_cobertura_exacta_de_proyecto_sin_codigo(self):
        raiz = crear_proyecto(self, {"requirements.txt": "requests==2\n"})

        informe = evaluar(raiz, con_red=False)

        self.assertEqual(informe["cobertura"], {
            "criterios_evaluados": 5,
            "criterios_no_aplicables": 24,
            "ratio_evaluado": 0.172,
            "nivel": "baja",
            "comparable": False,
            "motivo_no_comparable": "cobertura 17% < 80%",
            "nota_lenguajes": "Python: AST y criterios nativos",
            "dimensiones_evaluadas": ["vigencia", "herramientas"],
            "dimensiones_no_aplicables": ["funcionalidades", "calidad",
                                          "inteligencia", "eficiencia"],
            "lenguajes": {},
            "nota_no_aplicables": "24 criterios declarados N/A por el perfil: "
                                  "no se cuentan como fallos (ver cobertura)"})


class TestLocksDepsFuncionalidadesRunner(unittest.TestCase):
    """Contrato de locks, dedupe, funcionalidades y errores del runner."""

    def test_versiones_lock_en_todos_los_formatos(self):
        raiz = crear_proyecto(self, {
            "uv.lock": ('[[package]]\nname="a"\nversion="1.0"\n'
                        '[[package]]\nname="self"\nversion="9"\n'
                        'source={editable=true}\n'
                        '[[package]]\nname="b"\nversion="2.0"\n'),
            "Pipfile.lock": ('{"default":{"foo":{"version":"==3.1"}},'
                             '"develop":{"bar":{"version":"==4.2"}}}'),
            "package-lock.json": ('{"packages":{'
                                  '"node_modules/react":{"version":"18.2.0"},'
                                  '"node_modules/a/node_modules/react-dom":'
                                  '{"version":"18.0.0"}}}'),
            "poetry.lock": '[[package]]\nname="poetry-pkg"\nversion="5.0"\n',
            "pdm.lock": '[[package]]\nname="pdm-pkg"\nversion="6.0"\n',
            "custom.lock": "x==7.0\n",
        })

        self.assertEqual(evaluar_proyecto._versiones_lock(raiz), {
            "a": "1.0", "b": "2.0", "bar": "4.2", "foo": "3.1",
            "pdm-pkg": "6.0", "poetry-pkg": "5.0", "react": "18.2.0",
            "react-dom": "18.0.0", "x": "7.0"})

    def test_dependencias_dedupe_y_prioridad(self):
        raiz = crear_proyecto(self, {
            "pyproject.toml": ('[project]\nname="x"\nversion="0.1.0"\n'
                               'dependencies=["requests>=2","flask"]\n'
                               '[project.optional-dependencies]\n'
                               'dev=["requests==2.31"]\n'),
            "requirements.txt": "requests==2.31.0\n",
            "package.json": ('{"dependencies":{"requests":"^1.0",'
                             '"react":"18.2.0"}}'),
        })

        deps = evaluar_proyecto._dependencias(raiz)

        self.assertEqual([
            (d["nombre"], d["ecosistema"], d["ambito"], d["version"],
             d["fijada"], d["origen"]) for d in deps], [
            ("requests", "npm", "runtime", "1.0", False, "package.json"),
            ("react", "npm", "runtime", "18.2.0", True, "package.json"),
            ("requests", "python", "runtime", "2.31.0", True,
             "requirements.txt"),
            ("flask", "python", "runtime", "", False, "pyproject.toml")])

    def test_funcionalidades_sin_readme_todo_real_y_sin_tests(self):
        raiz = crear_proyecto(self, {
            "pkg/__init__.py": "",
            "pkg/mod.py": ("def f():\n"
                           "    # TODO REAL: regla de dominio\n"
                           "    # TODO: deuda\n"
                           "    return 1\n"),
        })
        perfil = evaluar_proyecto.analizar_perfil(raiz)

        dimension = evaluar_proyecto.evaluar_funcionalidades(raiz, perfil)

        self.assertEqual(dimension.a_dict(), {
            "puntuacion": 0.0, "evaluado": True,
            "criterios": {"f2_readme_vs_realidad": False,
                          "f3_sin_deuda_declarada": False,
                          "f4_tests_de_varios_modulos": False},
            "no_aplica": [{"criterio": "f1_puntos_de_entrada",
                           "motivo": "sin CLI/entrypoint declarado "
                                     "(proyecto tipo biblioteca)"}],
            "hallazgos": [
                {"severidad": "media",
                 "descripcion": "Sin README.md/.rst/.txt",
                 "evidencia": str(raiz), "tipo_evidencia": "verified-real",
                 "criterio": "f2_readme_vs_realidad"},
                {"severidad": "baja",
                 "descripcion": "1 marcas TODO/FIXME/XXX en código de "
                                "producción",
                 "evidencia": "pkg/mod.py:3", "tipo_evidencia": "verified-real",
                 "criterio": "f3_sin_deuda_declarada"},
                {"severidad": "baja",
                 "descripcion": "Solo 0 archivo(s) de test: la cobertura por "
                                "módulos no se puede distribuir",
                 "evidencia": "código del proyecto",
                 "tipo_evidencia": "verified-real",
                 "criterio": "f4_tests_de_varios_modulos"}],
            "notas": ["0 archivos de test (sin tests)"]})

    def test_ejecutar_tests_oserror(self):
        raiz = crear_proyecto(self, {"README.md": "# x\n"})
        with patch("evaluar_proyecto.detectar_comando_tests",
                   return_value={"comando": ["python", "-m", "unittest"],
                                 "origen": "x"}), \
                patch("evaluar_proyecto.subprocess.run",
                      side_effect=OSError("boom")):
            self.assertEqual(
                evaluar_proyecto.ejecutar_tests(raiz),
                {"ejecutado": True, "comando": "python -m unittest",
                 "origen": "x", "error": "OSError", "detalle": "boom"})

    def test_ejecutar_tests_timeout(self):
        raiz = crear_proyecto(self, {"README.md": "# x\n"})
        expirado = evaluar_proyecto.subprocess.TimeoutExpired("x", 1)
        with patch("evaluar_proyecto.detectar_comando_tests",
                   return_value={"comando": ["x"], "origen": "y"}), \
                patch("evaluar_proyecto.subprocess.run",
                      side_effect=expirado):
            resultado = evaluar_proyecto.ejecutar_tests(raiz)

        self.assertTrue(resultado["ejecutado"])
        self.assertEqual(resultado["error"], "TimeoutExpired")
        self.assertEqual(resultado["comando"], "x")

    def test_ejecutar_tests_suite_roja_y_sin_ran(self):
        raiz = crear_proyecto(self, {"README.md": "# x\n"})
        proceso = SimpleNamespace(
            returncode=1, stdout="FAILED (failures=1)\n", stderr="")

        with patch("evaluar_proyecto.detectar_comando_tests",
                   return_value={"comando": ["python", "-m", "unittest"],
                                 "origen": "x"}), \
                patch("evaluar_proyecto.subprocess.run",
                      return_value=proceso), \
                patch("evaluar_proyecto.time.monotonic",
                      side_effect=[10.0, 10.0]):
            resultado = evaluar_proyecto.ejecutar_tests(raiz)

        self.assertEqual(resultado, {
            "ejecutado": True, "comando": "python -m unittest",
            "origen": "x", "codigo": 1, "ok": False, "tests": None,
            "resumen": "FAILED (failures=1)", "duracion_s": 0.0})


class TestDigestoCalidadErrorYH5(unittest.TestCase):
    """Contrato del digesto, errores de suite y h5 no verificable."""

    def test_digesto_minimo_exacto(self):
        informe = {
            "ruta": "/p", "archivos_python": 2, "lineas_python": 10,
            "cobertura": {"criterios_evaluados": 3,
                          "criterios_no_aplicables": 1, "nivel": "media"},
            "dimensiones": {"calidad": {
                "puntuacion": 0.5,
                "criterios": {"c1": True, "c2": False},
                "hallazgos": [{"tipo_evidencia": "verified-real",
                               "severidad": "alta",
                               "descripcion": "x" * 120,
                               "evidencia": "a.py:1"}],
                "notas": ["n1"]}},
        }

        self.assertEqual(evaluar_proyecto._digesto(informe), "\n".join([
            "ruta: /p", "python: 2 archivos / 10 líneas",
            "cobertura: 3 criterios evaluados, 1 N/A (nivel media)",
            "- calidad: 0.50 | fallos: ['c2']",
            "    [VERIFIED-REAL] (alta) " + "x" * 110 + " — a.py:1",
            "    · n1"]))

    def test_calidad_error_ejecutado_y_sin_ejecutar(self):
        raiz = crear_proyecto(self, {"app.py": "def f():\n    return 1\n"})
        perfil = evaluar_proyecto.analizar_perfil(raiz)

        con_error = evaluar_proyecto.evaluar_calidad(
            raiz, perfil, ejecutar=True,
            resultado_tests={"ejecutado": True, "error": "boom",
                             "detalle": "x", "comando": "cmd"})
        self.assertEqual(
            con_error.a_dict()["notas"][1], "suite NO ejecutada: boom: x (cmd)")
        self.assertEqual(con_error.a_dict()["no_aplica"][0],
                         {"criterio": "c1b_suite_pasa",
                          "motivo": "runner no disponible"})

        sin_runner = evaluar_proyecto.evaluar_calidad(
            raiz, perfil, ejecutar=True,
            resultado_tests={"ejecutado": False, "motivo": "sin runner",
                             "comando": "cmd"})
        self.assertEqual(
            sin_runner.a_dict()["notas"][1],
            "suite NO ejecutada: sin runner (cmd)")

    def test_herramientas_h5_no_verificable(self):
        raiz = crear_proyecto(self, {
            "pyproject.toml": ('[project]\nname="x"\nversion="0.1.0"\n'
                               'dependencies=["requests"]\n'),
            "LICENSE": "MIT\n", "pkg/__init__.py": "",
            "pkg/app.py": "def f():\n    return 1\n",
            "tests/test_a.py": "def test_a():\n    assert 1\n"})
        perfil = evaluar_proyecto.analizar_perfil(raiz)

        with patch("evaluar_proyecto.licencia_pypi",
                   return_value={"licencia": "desconocida", "libre": None,
                                 "fuente": "", "error": "OSError: x"}):
            dimension = evaluar_proyecto.evaluar_herramientas(
                raiz, perfil, con_red=True)

        datos = dimension.a_dict()
        self.assertFalse(datos["criterios"]["h5_licencias_libres"])
        self.assertEqual(datos["hallazgos"][1], {
            "severidad": "baja",
            "descripcion": "Licencia no verificable en PyPI: requests "
                           "(OSError: x)",
            "evidencia": "PyPI", "tipo_evidencia": "unverified",
            "criterio": "h5_licencias_libres"})


if __name__ == "__main__":
    unittest.main()
