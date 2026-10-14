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
        self.assertEqual(result["num_search_results"], 1)
        self.assertEqual(result["total_thinking_steps"], 7)
        self.assertEqual(len(result["claims"]), 1)
        self.assertTrue(result["claims"][0]["simulado"])
        # confidence 0.5 del primer claim → por debajo del umbral 0.7
        self.assertEqual(result["evaluations"][0]["verdict"], "not_addressed")
        self.assertIn("conclusiones", result["synthesis"])
        self.assertEqual(result["simulated_steps"],
                         ["claim_extraction", "evidence_evaluation", "synthesis"])
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


class TestHeuristicasSimuladas(unittest.TestCase):
    def setUp(self):
        self.orchestrator = ResearchOrchestratorWithThinking(
            MockLLM(), MockSearchAPI(), DeepResearchThinkingLayer(MockLLM()))

    def test_extract_claims_usa_snippet_o_titulo(self):
        claims = self.orchestrator._extract_claims_with_thought([
            {"title": "Fuente A", "snippet": "  texto del snippet  "},
            {"title": "Fuente B", "snippet": ""},
        ])
        self.assertEqual(claims[0]["claim"], "texto del snippet")
        self.assertEqual(claims[0]["confidence"], 0.5)
        self.assertEqual(claims[1]["claim"], "Contenido de Fuente B")
        self.assertEqual(claims[1]["confidence"], 0.6)
        self.assertTrue(all(c["verificable"] for c in claims))

    def test_extract_claims_recorta_a_200(self):
        claims = self.orchestrator._extract_claims_with_thought([
            {"title": "T", "snippet": "x" * 500},
        ])
        self.assertEqual(len(claims[0]["claim"]), 200)

    def test_evaluate_evidence_umbral_de_confianza(self):
        evaluations = self.orchestrator._evaluate_evidence_with_thought([
            {"claim": "alta", "confidence": 0.9, "source_quality": 0.8},
            {"claim": "baja", "confidence": 0.5, "source_quality": 0.6},
        ])
        self.assertEqual(evaluations[0]["verdict"], "supported")
        self.assertEqual(evaluations[0]["credibility"], 0.72)
        self.assertEqual(evaluations[1]["verdict"], "not_addressed")
        self.assertTrue(all(e["simulado"] for e in evaluations))

    def test_synthesize_cuenta_veredictos(self):
        synthesis = self.orchestrator._synthesize_with_thought([
            {"claim": "a", "verdict": "supported"},
            {"claim": "b", "verdict": "contradicted"},
            {"claim": "c", "verdict": "not_addressed"},
        ])
        self.assertIn("1 claims supported, 1 contradicted",
                      synthesis["conclusiones"][0]["enunciado"])
        self.assertEqual(synthesis["conclusiones"][0]["basada_en"],
                         ["claim_0", "claim_1", "claim_2"])
        self.assertEqual(synthesis["gaps"], ["1 claims sin evaluar"])
        self.assertTrue(synthesis["simulado"])


class TestMain(unittest.TestCase):
    def test_main_offline_completa(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            pl.main()
        salida = buffer.getvalue()
        self.assertIn("RESULTADO DEL PENSAMIENTO ESTRUCTURADO", salida)
        self.assertIn("Pasos ejecutados: 7", salida)
        self.assertIn("Válido: True", salida)


if __name__ == "__main__":
    unittest.main()
