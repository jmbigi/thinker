"""Concurrencia acotada y fusión determinista del pipeline."""

import tempfile
import threading
import time
import unittest
from pathlib import Path

from deep_research_system import ResearchOrchestrator
from llm_providers import MockLLM
from tests.helpers import StubSearch
from web_search import MockSearchAPI


class _ConcurrentMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.activos = 0
        self.max_activos = 0
        self._concurrencia_lock = threading.Lock()

    def _entrar(self):
        with self._concurrencia_lock:
            self.activos += 1
            self.max_activos = max(self.max_activos, self.activos)
        time.sleep(0.02)

    def _salir(self):
        with self._concurrencia_lock:
            self.activos -= 1


class _ConcurrentLLM(_ConcurrentMixin, MockLLM):
    def __init__(self):
        super().__init__()
        self.extracciones = 0

    def generate(self, prompt, model=None, **kwargs):
        self._entrar()
        try:
            if "Extract factual claims" in prompt:
                self.extracciones += 1
            return super().generate(prompt, model=model, **kwargs)
        finally:
            self._salir()


class _ConcurrentSearch(_ConcurrentMixin, MockSearchAPI):
    def search(self, query, max_results=5):
        self._entrar()
        try:
            return super().search(query, max_results)
        finally:
            self._salir()


class TestParallelResearch(unittest.TestCase):
    def test_paralelo_conserva_resultados_y_orden(self):
        report_seq, seq = ResearchOrchestrator(
            MockLLM(), MockSearchAPI()).research("Energía solar")
        report_par, par = ResearchOrchestrator(
            MockLLM(), MockSearchAPI(), max_workers=2).research("Energía solar")

        self.assertEqual(report_par, report_seq)
        self.assertEqual([s["url"] for s in par.sources],
                         [s["url"] for s in seq.sources])
        self.assertEqual([c["claim"] for c in par.claims],
                         [c["claim"] for c in seq.claims])
        self.assertEqual([e["verdict"] for e in par.evaluations],
                         [e["verdict"] for e in seq.evaluations])
        self.assertEqual(par.retrieved_subquestions, seq.retrieved_subquestions)
        self.assertEqual(par.iteration, seq.iteration)

    def test_concurrencia_real_en_busqueda_y_llm(self):
        llm = _ConcurrentLLM()
        search = _ConcurrentSearch()
        ResearchOrchestrator(llm, search, max_workers=2).research("Energía solar")
        self.assertEqual(search.max_activos, 2)
        self.assertEqual(llm.max_activos, 2)

    def test_fuente_compartida_se_extrae_una_sola_vez(self):
        fuente = {"title": "Misma", "url": "https://example.com/misma",
                  "snippet": "Contenido compartido", "source": "stub"}
        llm = _ConcurrentLLM()
        _, contexto = ResearchOrchestrator(
            llm, StubSearch([fuente]), max_workers=3).research("Pregunta")
        self.assertEqual(llm.extracciones, 1)
        self.assertEqual(len(contexto.claims), 1)
        self.assertEqual(len(contexto.sources), 1)
        self.assertEqual(len(contexto.retrieved_subquestions), 3)

    def test_reanudacion_paralela_no_repite_trabajo(self):
        with tempfile.TemporaryDirectory() as tmp:
            estado = str(Path(tmp) / "estado.json")
            report, _ = ResearchOrchestrator(
                MockLLM(), MockSearchAPI(), max_workers=2,
                state_path=estado).research("Pregunta")
            llm = _ConcurrentLLM()
            search = _ConcurrentSearch()
            resumed, _ = ResearchOrchestrator(
                llm, search, max_workers=2, state_path=estado).research("Pregunta")
            self.assertEqual(resumed, report)
            self.assertEqual(llm.calls if hasattr(llm, "calls") else 0, 0)
            self.assertEqual(search.max_activos, 0)


if __name__ == "__main__":
    unittest.main()
