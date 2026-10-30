"""Contratos de eficiencia orquestada y RAG, sin modelos externos."""

import unittest

from deep_research_system import ResearchOrchestrator
from efficiency import (AdaptiveRouter, CachedLLM, ContextPruner, ExpertRouterLLM,
                        QuantizedVector, SemanticResponseCache, SpeculativeLLM)
from llm_providers import MockLLM
from tests.helpers import StubSearch


class _Contador(MockLLM):
    def __init__(self, respuesta=None):
        super().__init__()
        self.calls = 0
        self.respuesta = respuesta

    def generate(self, prompt, model=None, **kwargs):
        self.calls += 1
        return self.respuesta if self.respuesta is not None else super().generate(prompt, **kwargs)


class TestAdaptiveRouter(unittest.TestCase):
    def test_planes_basic_standard_deep(self):
        router = AdaptiveRouter()
        self.assertEqual(router.plan("¿Qué es solar?").level, "basic")
        comparativa = router.plan("Compara RAG y MCP y analiza sus diferencias")
        self.assertIn(comparativa.level, ("standard", "deep"))
        extensa = "Compara arquitectura, protocolo y algoritmo RAG y MCP y analiza " + "muy " * 50 + "detalladamente"
        profunda = router.plan(extensa)
        self.assertEqual(profunda.level, "deep")
        self.assertTrue(profunda.verificacion_independiente)
        self.assertEqual(profunda.muestras_consenso, 2)
        self.assertTrue(profunda.ncm_residual)
        self.assertTrue(profunda.use_tot)

    def test_orquestador_adaptativo_configura_plan(self):
        pregunta = "Compara arquitectura, protocolo y algoritmo RAG y MCP y analiza " + "muy " * 50 + "detalladamente"
        orchestrator = ResearchOrchestrator.adaptive(
            pregunta, MockLLM(), StubSearch([]))
        self.assertEqual(orchestrator.adaptive_plan.level, "deep")
        self.assertEqual(orchestrator.context.max_iterations, 7)
        self.assertTrue(orchestrator.generator.ncm_residual)


class TestPruningAndVectors(unittest.TestCase):
    def test_pruning_mide_ahorro_y_determinismo(self):
        fuentes = [
            {"title": "A", "url": "a", "snippet": "energía solar paneles " * 30},
            {"title": "B", "url": "b", "snippet": "motor combustión " * 30},
            {"title": "C", "url": "c", "snippet": "solar renovable " * 30},
        ]
        pruner = ContextPruner(max_passages=1, max_chars=200)
        seleccion, metricas = pruner.prune("energía solar", fuentes)
        self.assertEqual(len(seleccion), 1)
        self.assertLess(metricas["output_chars"], metricas["input_chars"])
        self.assertGreater(metricas["savings_ratio"], 0.5)
        self.assertEqual(seleccion, pruner.prune("energía solar", fuentes)[0])

    def test_pruning_integrado_registra_metricas(self):
        fuentes = [
            {"title": "A", "url": "a", "snippet": "energía solar " * 40},
            {"title": "B", "url": "b", "snippet": "motor combustión " * 40},
        ]
        _, contexto = ResearchOrchestrator(
            MockLLM(), StubSearch(fuentes), context_pruner=ContextPruner(max_passages=1)
        ).research("energía solar")
        decisiones = [d for d in contexto.decision_log if d["step"] == "context_pruning"]
        self.assertTrue(decisiones)
        self.assertIn("savings_ratio", decisiones[0]["rationale"])

    def test_cuantizacion_reduce_memoria_y_preserva_direccion(self):
        vector, _ = QuantizedVector.from_text("energía solar renovable", bits=4)
        self.assertLess(vector.memory_bytes()["compressed"], vector.memory_bytes()["float64"])
        self.assertGreater(vector.cosine(vector), 0.99)
        with self.assertRaises(ValueError):
            QuantizedVector([float("nan")], bits=8)


class _ProveedorRespuesta:
    def __init__(self, texto="respuesta"):
        self.texto = texto
        self.calls = 0

    def generate(self, prompt, model=None, **kwargs):
        self.calls += 1
        return self.texto


class TestCacheAndExperts(unittest.TestCase):
    def test_cache_exacta_y_semantica_opt_in(self):
        proveedor = _ProveedorRespuesta()
        cache = SemanticResponseCache(bits=4)
        llm = CachedLLM(proveedor, cache, semantic_threshold=0.9)
        llm.generate("energía solar", model="mock")
        llm.generate("energía solar", model="mock")
        llm.generate("solar   energía", model="mock")
        self.assertEqual(proveedor.calls, 1)
        self.assertEqual(cache.hits_exact, 1)
        self.assertEqual(cache.hits_semantic, 1)
        llm.generate("motor diésel", model="mock")
        self.assertEqual(proveedor.calls, 2)

    def test_expertos_y_speculative(self):
        medico = _ProveedorRespuesta("medical")
        general = _ProveedorRespuesta("general")
        router = ExpertRouterLLM({"medical": (medico, ("salud", "cáncer"))}, general)
        self.assertEqual(router.generate("cáncer y salud"), "medical")
        self.assertEqual(router.generate("otro"), "general")
        self.assertEqual(router.routes, ["medical", "fallback"])

        speculative = SpeculativeLLM(
            _ProveedorRespuesta("borrador"), _ProveedorRespuesta("verificado"))
        self.assertEqual(speculative.generate("tarea"), "verificado")
        self.assertEqual((speculative.drafts, speculative.verifications), (1, 1))


if __name__ == "__main__":
    unittest.main()
