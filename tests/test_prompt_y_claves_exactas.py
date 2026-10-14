"""Tests de igualdad estricta sobre prompts y claves (contra mutantes vivos).

Las pruebas de mutación mostraron supervivientes del tipo: clave renombrada
("confidence" -> "CONFIDENCE"), valor por defecto cambiado ("" -> "XXXX",
'Unknown' -> None), comparación invertida ("in" -> "not in") y piezas de
plantilla alteradas. Asertar el valor COMPLETO los mata.
"""

import json
import unittest

from code_design_improvement_tools import CodeImprovementOrchestrator
from deep_research_system import (ClaimExtractor, EvidenceEvaluator,
                                  MockLLM, ResearchContext)
from tests.helpers import StubLLM


class TestMockLLMIgualdadEstricta(unittest.TestCase):

    def setUp(self):
        self.llm = MockLLM()

    def test_claims_dict_completo(self):
        self.assertEqual(json.loads(self.llm.generate("Extract factual claims x")), [{
            "claim": "Afirmación simulada extraída del snippet por MockLLM",
            "confidence": 0.7,
            "source_url": "https://example.com/mock-source",
        }])

    def test_evaluacion_dict_completo(self):
        self.assertEqual(json.loads(self.llm.generate("Evaluate this claim x")), {
            "verdict": "supported",
            "credibility": 0.75,
            "confidence": 0.7,
            "reasoning": "Evaluación simulada por MockLLM (offline, sin modelo real)",
        })

    def test_paso_dict_completo(self):
        self.assertEqual(json.loads(self.llm.generate("PASO 3 - ALGO")), {
            "paso": 3,
            "contenido": "Respuesta simulada por MockLLM para el paso 3",
            "confianza": 0.7,
            "nota": "Salida offline determinista, sin modelo real",
        })

    def test_descomposicion_lista_completa(self):
        self.assertEqual(self.llm.generate("Decompose this into 3-5").split("\n"), [
            "¿Cuáles son los avances recientes documentados sobre el tema?",
            "¿Qué fuentes primarias describen el estado actual?",
            "¿Qué limitaciones, riesgos e incertidumbres se reportan?",
        ])

    def test_informe_markdown_completo(self):
        informe = self.llm.generate("Generate a comprehensive research report now")
        self.assertTrue(informe.startswith("# Informe de investigación (SIMULADO por MockLLM)\n\n"))
        self.assertIn("## Resumen ejecutivo\n\n", informe)
        self.assertIn("## Hallazgos\n\n", informe)
        self.assertIn("## Conclusiones\n\n", informe)
        self.assertTrue(informe.endswith("para obtener contenido genuino.\n"))

    def test_precedencia_de_ramas_documentada(self):
        # Un prompt con ambos marcadores cae en la PRIMERA rama evaluada
        # (descomposición), no en la de claims: la precedencia es real y fija.
        salida = self.llm.generate("extract factual claims (no decompose this into parts)")
        self.assertEqual(salida.split("\n")[0],
                         "¿Cuáles son los avances recientes documentados sobre el tema?")


class TestEvidenceEvaluatorPromptExacto(unittest.TestCase):

    def _prompt(self, fuentes, claim):
        llm = StubLLM(lambda p: '{"verdict": "supported", "credibility": 1.0, "confidence": 1.0, "reasoning": "r"}')
        ctx = ResearchContext("q")
        ctx.sources = fuentes
        EvidenceEvaluator(llm).decide(ctx, claim)
        return llm.prompts[0]

    def test_bloque_de_fuentes_exacto(self):
        prompt = self._prompt(
            [{"url": "u1", "title": "T1", "snippet": "s1"},
             {"url": "u2", "title": "T2", "snippet": "s2"}],
            {"claim": "C", "source_url": None})
        self.assertIn("Source 1: T1: s1\nSource 2: T2: s2\n\n\n", prompt)
        self.assertNotIn("XXXX", prompt)

    def test_fuente_sin_titulo_usa_unknown(self):
        prompt = self._prompt([{"url": "u1", "snippet": "s"}], {"claim": "C"})
        self.assertIn("Source 1: Unknown: s\n", prompt)
        self.assertNotIn("None", prompt)

    def test_claim_ausente_no_renderiza_none(self):
        prompt = self._prompt([{"url": "u1", "title": "T", "snippet": "s"}], {})
        self.assertIn("\nClaim: \n", prompt)
        self.assertNotIn("Claim: None", prompt)

    def test_plantilla_final_exacta(self):
        prompt = self._prompt([{"url": "u1", "title": "T", "snippet": "s"}],
                              {"claim": "C"})
        self.assertTrue(prompt.startswith(
            "Evaluate this claim against the provided sources. Determine:\n"
            "1. Is the claim supported, contradicted, or not addressed?\n"
            "2. What is the overall credibility score (0-1) of the supporting sources?\n"
            "3. Are there contradictions from other sources?\n\nClaim: C\n"))
        self.assertTrue(prompt.endswith(
            'Return ONLY JSON (no markdown fences, no extra text):\n'
            '{"verdict": "supported|contradicted|not_addressed", "credibility": 0-1, '
            '"confidence": 0-1, "reasoning": "..."}'))


class TestClaimExtractorPromptExacto(unittest.TestCase):

    def test_prompt_completo(self):
        llm = StubLLM(lambda p: "[]")
        ClaimExtractor(llm).decide(ResearchContext("q"),
                                   {"url": "u", "snippet": "SNIP"})
        self.assertEqual(llm.prompts[0], (
            "Extract factual claims from this text snippet. For each claim, provide:\n"
            "1. The claim statement\n"
            "2. A confidence score (0-1) based on how well-supported it appears\n"
            "3. The source URL it came from\n\n"
            "Snippet: SNIP\n\n"
            'Return ONLY a JSON array (no markdown fences, no extra text) with fields:\n'
            '"claim", "confidence", "source_url"\n'))


class TestReportLinesIgualdadEstricta(unittest.TestCase):

    def test_lista_completa_de_lineas(self):
        orquestador = CodeImprovementOrchestrator(
            CodeDesignThinkerStub(), source_code="")
        orquestador.results = {
            "total_thinking_steps": 7,
            "efficiency_principle": "Hacer las cosas de manera eficiente",
            "project_metrics": {
                "total_issues": 1,
                "efficiency_score": 0.03,
                "issues": [{"severity": "medium", "description": "D",
                            "suggestion": "S"}],
            },
            "selection": {"decision": "d", "confidence": 0.5},
            "implementation_plan": {"steps": [("analysis", "contenido"), ("plan", "otro")]},
            "validation_criteria": {"decision": "v", "confidence": 0.25},
        }
        self.assertEqual(orquestador.report_lines(), [
            "# Análisis y Mejora de Proyecto de Código",
            "",
            "## Resumen Ejecutivo",
            "- **Pasos de pensamiento**: 7",
            "- **Problemas identificados**: 1",
            "- **Score de eficiencia**: 0.03",
            "- **Principio rector**: Hacer las cosas de manera eficiente",
            "",
            "## Problemas Detectados",
            "- **[MEDIUM]** D",
            "  - Sugerencia: S",
            "",
            "## Decisiones de Diseño",
            "- **Enfoque seleccionado**: d",
            "- **Confianza**: 0.5",
            "",
            "## Plan de Implementación",
            "1. contenido",
            "2. otro",
            "",
            "## Criterios de Validación",
            "- **Decisión de validación**: v",
            "- **Confianza**: 0.25",
            "",
            "---",
            "*Generado por sistema de diseño de código con capa de pensamiento estructurado*",
            "*Pasos deliberados: 7/7*",
        ])


class CodeDesignThinkerStub:
    """Doble mínimo: `report_lines` no usa el motor, sólo `self.results`."""

    step_count = 7


if __name__ == "__main__":
    unittest.main()
