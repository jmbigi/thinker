"""Tests de evaluar_proyecto.py: fixture con defectos plantados y autoevaluación.

Offline: la comprobación de PyPI se desactiva (`con_red=False`) y la fixture es
un proyecto temporal con defectos conocidos. Incluye una prueba de que la
evaluación es READ-ONLY (no escribe en el proyecto evaluado).
"""

import tempfile
import unittest
from pathlib import Path

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
