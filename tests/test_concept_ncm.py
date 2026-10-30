"""Contratos de jerarquía residual NCM, sin modelo neural ni red."""

import threading
import time
import unittest

from concept_ncm import ResidualConceptGenerator
from deep_research_system import ReportGenerator, ResearchContext


class _LLMConceptos:
    def __init__(self, paralelo=False, duplicado=False):
        self.paralelo = paralelo
        self.duplicado = duplicado
        self.activos = 0
        self.max_activos = 0
        self.prompts = []
        self._lock = threading.Lock()

    def generate(self, prompt, model=None, **kwargs):
        with self._lock:
            self.activos += 1
            self.max_activos = max(self.max_activos, self.activos)
            self.prompts.append(prompt)
        if self.paralelo:
            time.sleep(0.03)
        try:
            if "Write the section" in prompt:
                titulo = prompt.split('"')[1]
                if titulo == "Fallo":
                    raise RuntimeError("fallo simulado")
                return f"## {titulo}\n\nContenido base [1]"
            if "Add ONLY the missing evidence" in prompt:
                return "Contenido base [1]" if self.duplicado else "Evidencia residual [1]"
            raise AssertionError("Prompt inesperado")
        finally:
            with self._lock:
                self.activos -= 1


class _LLMSinResidual:
    def generate(self, prompt, model=None, **kwargs):
        if "Write the section" in prompt:
            return "energia solar renovable [1]"
        raise AssertionError("No debió pedir refinamiento")


class TestConceptNCM(unittest.TestCase):
    def setUp(self):
        self.contexto = ResearchContext("Energía")
        self.contexto.sources = [{"title": "Fuente", "url": "https://example.com"}]
        self.secciones = [
            {"titulo": "Solar", "subpregunta": "solar",
             "claims": ["energia solar renovable"]},
            {"titulo": "Viento", "subpregunta": "viento", "claims": []},
        ]
        self.generador = ReportGenerator(None)

    def _generar(self, llm, workers=2):
        return ResidualConceptGenerator(llm, max_workers=workers).generate(
            self.contexto, self.secciones, "[1] Fuente", 
            "- [supported] energia solar renovable (source: 1)\n",
            self.generador._prompt_seccion, self.generador._sin_encabezado_repetido)

    def test_paralelo_y_secuencial_reconstruyen_igual(self):
        secuencial = self._generar(_LLMConceptos(), workers=1)
        paralelo = self._generar(_LLMConceptos(paralelo=True), workers=2)
        self.assertEqual(secuencial.report, paralelo.report)
        self.assertGreaterEqual(paralelo.traces[1]["workers"], 1)
        self.assertIn("Evidencia residual", paralelo.report)
        self.assertEqual([t["level"] for t in paralelo.traces], [0, 1, 1, 2, 2, 3])
        self.assertTrue(all(t["content_hash"] for t in paralelo.traces))

    def test_concurrencia_real_acotada(self):
        resultado = self._generar(_LLMConceptos(paralelo=True), workers=2)
        self.assertGreaterEqual(resultado.generated_sections, 1)
        llm = _LLMConceptos(paralelo=True)
        self._generar(llm, workers=2)
        self.assertEqual(llm.max_activos, 2)

    def test_sin_residual_no_llama_refinamiento(self):
        resultado = self._generar(_LLMSinResidual(), workers=1)
        self.assertIn("sin_residual", [t["status"] for t in resultado.traces])
        self.assertNotIn("Evidencia residual", resultado.report)

    def test_error_de_seccion_queda_aislado(self):
        self.secciones[1]["titulo"] = "Fallo"
        resultado = self._generar(_LLMConceptos(), workers=1)
        self.assertEqual(resultado.generated_sections, 1)
        self.assertIn("No content generated", resultado.report)
        self.assertIn("error", [t["status"] for t in resultado.traces])

    def test_refinamiento_duplicado_no_se_anade(self):
        resultado = self._generar(_LLMConceptos(duplicado=True), workers=1)
        self.assertIn("duplicado", [t["status"] for t in resultado.traces])
        self.assertEqual(resultado.report.count("Contenido base"), 2)

    def test_workers_invalidos(self):
        with self.assertRaises(ValueError):
            ResidualConceptGenerator(_LLMConceptos(), max_workers=0)


if __name__ == "__main__":
    unittest.main()
