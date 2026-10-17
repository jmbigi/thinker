"""Tests de evaluar_proyecto.py: fixture con defectos plantados y autoevaluación.

Offline: la comprobación de PyPI se desactiva (`con_red=False`) y la fixture es
un proyecto temporal con defectos conocidos. Incluye una prueba de que la
evaluación es READ-ONLY (no escribe en el proyecto evaluado).
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from evaluar_proyecto import evaluar, informe_texto

RAIZ_THINKER = Path(__file__).resolve().parent.parent


class TestEvaluadorDeProyectos(unittest.TestCase):
    def _proyecto(self, archivos):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        raiz = Path(tmp.name)
        for nombre, contenido in archivos.items():
            ruta = raiz / nombre
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_text(contenido, encoding="utf-8")
        return raiz

    def _fixture(self):
        return self._proyecto({
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
        raiz = self._proyecto({
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


class TestEjecucionDeTestsYLicencias(unittest.TestCase):
    """Ejecución opt-in del comando DECLARADO y licencias de dependencias."""

    def _proyecto(self, archivos):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        raiz = Path(tmp.name)
        for nombre, contenido in archivos.items():
            ruta = raiz / nombre
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_text(contenido, encoding="utf-8")
        return raiz

    def test_sin_flag_no_ejecuta_nada_y_lo_declara(self):
        raiz = self._proyecto({
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
        raiz = self._proyecto({
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
        raiz = self._proyecto({
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
        raiz = self._proyecto({
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
        informe = evaluar(self._proyecto({"requirements.txt": "requests==2.31.0\n"}),
                          con_red=False)

        self.assertNotIn("h5_licencias_libres",
                         informe["dimensiones"]["herramientas"]["criterios"])
        self.assertTrue(any("OMITIDAS" in nota
                            for nota in informe["dimensiones"]["herramientas"]["notas"]))

    def test_licencias_libres_verificadas(self):
        with patch("evaluar_proyecto.licencia_pypi",
                   return_value={"licencia": "Apache-2.0", "libre": True}), \
                patch("evaluar_proyecto.ultima_version_pypi", return_value="2.31.0"):
            informe = evaluar(self._proyecto({"requirements.txt": "requests==2.31.0\n"}),
                              con_red=True)

        self.assertTrue(informe["dimensiones"]["herramientas"]
                        ["criterios"]["h5_licencias_libres"])

    def test_dependencia_sin_licencia_libre_se_reporta(self):
        with patch("evaluar_proyecto.licencia_pypi",
                   return_value={"licencia": "Propietaria", "libre": False}), \
                patch("evaluar_proyecto.ultima_version_pypi", return_value="1.0"):
            informe = evaluar(self._proyecto({"requirements.txt": "rara==1.0\n"}),
                              con_red=True)

        herramientas = informe["dimensiones"]["herramientas"]
        self.assertFalse(herramientas["criterios"]["h5_licencias_libres"])
        self.assertTrue(any("Propietaria" in h["descripcion"]
                            for h in herramientas["hallazgos"]))


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

    def test_autoevaluacion_no_escribe_en_el_repo(self):
        antes = {p: p.stat().st_mtime_ns for p in RAIZ_THINKER.rglob("*.py")}

        evaluar(RAIZ_THINKER, con_red=False)

        despues = {p: p.stat().st_mtime_ns for p in RAIZ_THINKER.rglob("*.py")}
        self.assertEqual(antes, despues)


if __name__ == "__main__":
    unittest.main()
