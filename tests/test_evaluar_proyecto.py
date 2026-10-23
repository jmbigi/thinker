"""Tests de evaluar_proyecto.py: fixture con defectos plantados y autoevaluación.

Offline: la comprobación de PyPI se desactiva (`con_red=False`) y la fixture es
un proyecto temporal con defectos conocidos. Incluye una prueba de que la
evaluación es READ-ONLY (no escribe en el proyecto evaluado).
"""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evaluar_proyecto import (archivos_python, detectar_comando_tests, evaluar,
                              informe_texto, main)
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
        self.assertIn("GLOBAL:", texto)

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


if __name__ == "__main__":
    unittest.main()
