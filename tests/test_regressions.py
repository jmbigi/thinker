"""Tests de regresión para bugs reales ya corregidos (P1.20).

Cada test aquí corresponde a un hallazgo de docs/LECCIONES-APRENDIDAS.md:
si el bug reaparece, el test falla.
"""

import unittest

from code_design_improvement_tools import CodeAnalysisContext, CodeDesignThinker
from pensamiento_layer import DeepResearchThinkingLayer
from tests.helpers import StubLLM


class TestContratoDeResultadoDelCiclo(unittest.TestCase):
    """Hallazgos 13 y 22: todas las ramas deben devolver las MISMAS claves.

    Un camino de error con forma distinta provoca `KeyError` en el consumidor.
    """

    CLAVES = {"thought", "decision", "confidence", "valid", "invalid_steps",
              "steps", "step_count"}

    def test_pensamiento_rama_invalida_tiene_todas_las_claves(self):
        layer = DeepResearchThinkingLayer(StubLLM(lambda _: ""))
        result = layer.think("pregunta")
        self.assertFalse(result["valid"])
        self.assertEqual(result["invalid_steps"], ["analysis"])
        self.assertTrue(self.CLAVES <= set(result))

    def test_code_design_rama_invalida_tiene_todas_las_claves(self):
        thinker = CodeDesignThinker(name="t", llm_provider=StubLLM(lambda _: ""))
        result = thinker.decide(CodeAnalysisContext("proyecto"), "código")
        self.assertFalse(result["valid"])
        self.assertEqual(result["invalid_steps"], ["analysis"])
        self.assertTrue(self.CLAVES <= set(result),
                        f"faltan claves: {self.CLAVES - set(result)}")


class TestConsultaDeBusqueda(unittest.TestCase):
    """Hallazgos 18 y 19: la pregunta natural no sirve como consulta."""

    def test_formulate_query_quita_palabras_vacias(self):
        from web_search import formulate_query
        q = formulate_query("¿Cuál es el estado actual de la fusión nuclear?")
        self.assertNotIn("cuál", q)
        self.assertIn("fusión", q)

    def test_anclas_mantienen_el_tema_en_subpreguntas_largas(self):
        from web_search import formulate_query
        subpregunta = ("¿Cuáles son los logros experimentales más recientes en "
                       "términos de ganancia de energía y confinamiento de plasma?")
        q = formulate_query(subpregunta, 4, anchor_terms=["fusión", "nuclear"])
        self.assertTrue(q.startswith("fusión nuclear"), q)


if __name__ == "__main__":
    unittest.main()
