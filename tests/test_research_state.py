"""Contratos de persistencia y reanudación del pipeline (offline)."""

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

from deep_research_system import ResearchContext, ResearchOrchestrator
from llm_providers import MockLLM
from research_state import (context_from_state, context_to_state, load_research_state,
                            save_research_state)
from web_search import MockSearchAPI


class _ContadorLLM(MockLLM):
    def __init__(self):
        super().__init__()
        self.calls = 0
        self.extracciones = 0

    def generate(self, prompt, model=None, **kwargs):
        self.calls += 1
        if "Extract factual claims" in prompt:
            self.extracciones += 1
        return super().generate(prompt, model=model, **kwargs)


class _FallaSegundaExtraccion(_ContadorLLM):
    def generate(self, prompt, model=None, **kwargs):
        if "Extract factual claims" in prompt and self.extracciones == 1:
            self.extracciones += 1
            self.calls += 1
            raise RuntimeError("fallo simulado de extracción")
        return super().generate(prompt, model=model, **kwargs)


class _ContadorSearch(MockSearchAPI):
    def __init__(self):
        self.consultas = 0

    def search(self, query, max_results=5):
        self.consultas += 1
        return super().search(query, max_results)


class TestEstado(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ruta = str(Path(self.tmp.name) / "investigacion.json")

    def test_roundtrip_completo_y_permisos(self):
        contexto = ResearchContext("pregunta", 4)
        contexto.decomposed = True
        contexto.subquestions = ["subpregunta"]
        contexto.sources = [{"url": "document://a", "sha256": "abc", "location": "página 1"}]
        contexto.retrieval_cache["subpregunta"] = contexto.sources
        contexto.processed_source_keys.append("fuente")
        contexto.evaluated_claim_keys.append("claim")

        save_research_state(self.ruta, contexto, "informe", completed=True)
        restaurado, report, completed = load_research_state(self.ruta)

        self.assertEqual(restaurado.question, "pregunta")
        self.assertEqual(restaurado.max_iterations, 4)
        self.assertEqual(restaurado.sources[0]["location"], "página 1")
        self.assertEqual(restaurado.retrieval_cache, contexto.retrieval_cache)
        self.assertEqual(restaurado.processed_source_keys, ["fuente"])
        self.assertEqual(restaurado.evaluated_claim_keys, ["claim"])
        self.assertEqual(report, "informe")
        self.assertTrue(completed)
        if os.name == "posix":
            modo = stat.S_IMODE(Path(self.ruta).stat().st_mode)
            self.assertEqual(modo, 0o600)

    def test_esquema_invalido_no_se_ignora(self):
        state = context_to_state(ResearchContext("pregunta"))
        state["schema_version"] = 999
        with self.assertRaisesRegex(RuntimeError, "no soportado"):
            context_from_state(state)
        Path(self.ruta).write_text("{roto", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "No se pudo leer"):
            load_research_state(self.ruta)

    def test_iteration_invalida_no_se_restaura(self):
        for valor in ("0", True, -1, 1.5):
            with self.subTest(valor=valor):
                state = context_to_state(ResearchContext("pregunta"))
                state["iteration"] = valor
                with self.assertRaisesRegex(
                        RuntimeError, "Campo de estado inválido: iteration"):
                    context_from_state(state)

    def test_estado_completado_no_repite_llamadas(self):
        llm = _ContadorLLM()
        report, _ = ResearchOrchestrator(
            llm, MockSearchAPI(), state_path=self.ruta).research("pregunta")
        self.assertGreater(llm.calls, 0)

        segundo_llm = _ContadorLLM()
        segundo_search = _ContadorSearch()
        resumed, contexto = ResearchOrchestrator(
            segundo_llm, segundo_search, state_path=self.ruta).research("pregunta")

        self.assertEqual(resumed, report)
        self.assertEqual(segundo_llm.calls, 0)
        self.assertEqual(segundo_search.consultas, 0)
        self.assertEqual(len(contexto.evaluated_claim_keys), 3)

    def test_fallo_intermedio_reanuda_sin_repetir_fuentes(self):
        llm_fallido = _FallaSegundaExtraccion()
        with self.assertRaisesRegex(RuntimeError, "fallo simulado"):
            ResearchOrchestrator(
                llm_fallido, MockSearchAPI(), state_path=self.ruta).research("pregunta")
        self.assertTrue(Path(self.ruta).exists())

        llm = _ContadorLLM()
        search = _ContadorSearch()
        _, contexto = ResearchOrchestrator(
            llm, search, state_path=self.ruta).research("pregunta")

        self.assertEqual(len(contexto.retrieved_subquestions), 3)
        self.assertEqual(len(contexto.processed_source_keys), 3)
        self.assertEqual(len(contexto.claims), 3)
        self.assertEqual(llm.extracciones, 2)
        self.assertEqual(search.consultas, 1)

    def test_pregunta_distinta_no_sobrescribe_estado(self):
        ResearchOrchestrator(
            MockLLM(), MockSearchAPI(), state_path=self.ruta).research("original")
        contenido = Path(self.ruta).read_text(encoding="utf-8")

        with self.assertRaisesRegex(RuntimeError, "no coincide"):
            ResearchOrchestrator(
                MockLLM(), MockSearchAPI(), state_path=self.ruta).research("otra")

        self.assertEqual(json.loads(contenido), json.loads(Path(self.ruta).read_text()))


if __name__ == "__main__":
    unittest.main()
