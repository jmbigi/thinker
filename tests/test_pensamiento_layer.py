"""Tests offline de pensamiento_layer.py (LLM y búsqueda SIMULADOS)."""

import contextlib
import io
import unittest

import pensamiento_layer as pl
from deep_research_system import MockLLM
from pensamiento_layer import (DeepResearchThinkingLayer,
                               ResearchOrchestratorWithThinking, ThinkingLayer)
from tests.helpers import StubLLM
from thinking_engine import StepThinkingEngine
from web_search import MockSearchAPI

CLAVES_RESULTADO = {"thought", "decision", "confidence", "valid",
                    "invalid_steps", "steps", "step_count", "error"}


class TestDeepResearchThinkingLayer(unittest.TestCase):
    def test_alias_thinking_layer(self):
        self.assertIs(ThinkingLayer, StepThinkingEngine)

    def test_ciclo_completo_valido_con_mock_llm(self):
        layer = DeepResearchThinkingLayer(MockLLM())
        self.assertEqual(layer.max_steps, 7)
        result = layer.think("¿Fusión nuclear en 2030?")

        self.assertTrue(CLAVES_RESULTADO <= set(result))
        self.assertTrue(result["valid"])
        self.assertEqual(result["step_count"], 7)
        self.assertEqual(result["invalid_steps"], [])
        self.assertIsNone(result["error"])
        self.assertEqual(result["confidence"], 1.0)
        self.assertEqual(result["decision"], "decision_from_synthesis")
        self.assertEqual(
            [name for name, _ in result["steps"]],
            ["analysis", "plan", "search_strategy", "search_results",
             "claim_extraction", "evidence_eval", "synthesis"],
        )
        self.assertIn("CAPA DE PENSAMIENTO", result["thought"])
        self.assertIn("PASO 1 - ANÁLISIS", result["thought"])
        self.assertIn("PASOS COMPLETADOS: 7/7", result["thought"])

    def test_llm_cadena_vacia_falla_en_analysis_con_todas_las_claves(self):
        # Regresión del KeyError corregido: la rama inválida debe devolver
        # exactamente las mismas claves que el camino feliz.
        layer = DeepResearchThinkingLayer(StubLLM(lambda p: ""))
        result = layer.think("pregunta")

        self.assertTrue(CLAVES_RESULTADO <= set(result))
        self.assertFalse(result["valid"])
        self.assertEqual(result["invalid_steps"], ["analysis"])
        self.assertEqual(result["step_count"], 1)
        self.assertEqual(result["confidence"], 0.0)
        self.assertEqual(result["error"], "Paso inválido: analysis")
        self.assertIn("REVISAR", result["thought"])

    def test_fallo_en_paso_intermedio_detiene_el_ciclo(self):
        def responder(prompt):
            return "contenido válido y sustancial" if "PASO 1" in prompt else ""

        layer = DeepResearchThinkingLayer(StubLLM(responder))
        result = layer.think("pregunta")
        self.assertFalse(result["valid"])
        self.assertEqual(result["invalid_steps"], ["plan"])
        self.assertEqual(result["step_count"], 2)

    def test_validate_step_compat(self):
        layer = DeepResearchThinkingLayer(MockLLM())
        self.assertTrue(layer._validate_step("contenido suficientemente largo"))
        self.assertFalse(layer._validate_step(""))


class TestResearchOrchestratorWithThinking(unittest.TestCase):
    def test_investigacion_completa_offline(self):
        layer = DeepResearchThinkingLayer(MockLLM())
        orchestrator = ResearchOrchestratorWithThinking(
            MockLLM(), MockSearchAPI(), layer)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            result = orchestrator.research_with_thinking("¿Fusión nuclear?")

        self.assertEqual(result["question"], "¿Fusión nuclear?")
        self.assertEqual(result["total_thinking_steps"], 7)
        # Delega en el pipeline REAL: fuentes, claims y evaluaciones las
        # produce ResearchOrchestrator, no heurísticas locales.
        self.assertGreater(len(result["sources"]), 0)
        self.assertGreater(len(result["claims"]), 0)
        self.assertEqual(len(result["claims"]), len(result["evaluations"]))
        self.assertTrue(result["report"])
        self.assertIs(result["context"].sources, result["sources"])
        self.assertIs(orchestrator.results, result)
        self.assertIn("INVESTIGACIÓN COMPLETADA", buffer.getvalue())

    def test_pensamiento_invalido_devuelve_error_sin_buscar(self):
        layer = DeepResearchThinkingLayer(StubLLM(lambda p: ""))
        search = MockSearchAPI()
        orchestrator = ResearchOrchestratorWithThinking(
            MockLLM(), search, layer)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            result = orchestrator.research_with_thinking("pregunta")

        self.assertIn("error", result)
        self.assertIn("no válido", result["error"])
        self.assertEqual(result["thinking"]["invalid_steps"], ["analysis"])

    def test_ya_no_existen_heuristicas_simuladas(self):
        """Regresión: se eliminaron las heurísticas simuladas del orquestador."""
        orchestrator = ResearchOrchestratorWithThinking(
            MockLLM(), MockSearchAPI(), DeepResearchThinkingLayer(MockLLM()))
        for metodo in ("_extract_claims_with_thought",
                       "_evaluate_evidence_with_thought",
                       "_synthesize_with_thought"):
            self.assertFalse(hasattr(orchestrator, metodo),
                             f"sigue existiendo el método simulado {metodo}")


class TestMain(unittest.TestCase):
    def test_main_offline_completa(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            pl.main()
        salida = buffer.getvalue()
        # Verificar modo lineal
        self.assertIn("RESULTADO MODO LINEAL", salida)
        self.assertIn("Pasos ejecutados: 7", salida)
        self.assertIn("Válido: True", salida)
        # Verificar modo ToT
        self.assertIn("RESULTADO MODO ToT", salida)
        self.assertIn("Nodos explorados:", salida)
        self.assertIn("Score mejor:", salida)


if __name__ == "__main__":
    unittest.main()
