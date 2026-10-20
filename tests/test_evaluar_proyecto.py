"""Tests de evaluar_proyecto.py: fixture con defectos plantados y autoevaluación.

Offline: la comprobación de PyPI se desactiva (`con_red=False`) y la fixture es
un proyecto temporal con defectos conocidos. Incluye una prueba de que la
evaluación es READ-ONLY (no escribe en el proyecto evaluado).
"""

import unittest
from pathlib import Path
from unittest.mock import patch

from evaluar_proyecto import evaluar, informe_texto
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

        informe = evaluar(raiz, con_red=False, ejecutar_tests_flag=True)

        nota = next(n for n in informe["dimensiones"]["calidad"]["notas"]
                    if n.startswith("suite:"))
        self.assertIn("make test", nota)

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


class TestAutoevaluacionDeThinker(unittest.TestCase):
    """thinker se evalúa a sí mismo (offline): 6 dimensiones y sin sorpresas."""

    def test_thinker_pasa_su_propia_evaluacion(self):
        informe = evaluar(RAIZ_THINKER, con_red=False)

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
