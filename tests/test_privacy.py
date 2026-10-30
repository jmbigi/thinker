"""Políticas de egreso y cifrado de checkpoints, sin red ni claves externas."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet

from deep_research_system import ResearchContext, ResearchOrchestrator
from documents import FullTextSearchAPI, LocalDocumentSearchAPI
from llm_providers import BudgetLLM, MockLLM, OllamaLLM, OpenRouterLLM
from mcp_client import MCPSearchAPI
from privacy import (GuardSearch, PrivacyPolicy, load_encrypted_research_state,
                     save_encrypted_research_state)
from tests.helpers import StubSearch
from web_search import MockSearchAPI, SearXNGSearchAPI, WikipediaSearchAPI


class _Contador(MockLLM):
    def __init__(self):
        super().__init__()
        self.calls = 0

    def generate(self, prompt, model=None, **kwargs):
        self.calls += 1
        return super().generate(prompt, model=model, **kwargs)


class TestPrivacyPolicy(unittest.TestCase):
    def test_local_only_rechaza_nube_y_web(self):
        with self.assertRaisesRegex(RuntimeError, "nube"):
            PrivacyPolicy("local-only").apply(OpenRouterLLM(), MockSearchAPI())
        with self.assertRaisesRegex(RuntimeError, "buscador web"):
            PrivacyPolicy("local-only").apply(MockLLM(), WikipediaSearchAPI())
        with self.assertRaisesRegex(RuntimeError, "full-text"):
            PrivacyPolicy("local-only").apply(
                MockLLM(), FullTextSearchAPI(MockSearchAPI()))

    def test_local_only_permite_llm_y_documentos_locales(self):
        with tempfile.TemporaryDirectory() as tmp:
            documento = Path(tmp) / "doc.txt"
            documento.write_text("contenido local", encoding="utf-8")
            buscador = LocalDocumentSearchAPI([str(documento)])
            llm, search = PrivacyPolicy("local-only").apply(
                OllamaLLM(base_url="http://localhost:11434"), buscador)
            self.assertEqual(llm.scope, "local-only")
            self.assertEqual(search.scope, "local-only")

    def test_searxng_local_y_private_documents_son_distintos(self):
        searxng = SearXNGSearchAPI("http://localhost:8080", allow_private=True)
        PrivacyPolicy("local-only").apply(MockLLM(), searxng)
        with self.assertRaisesRegex(RuntimeError, "reenvía"):
            PrivacyPolicy("private-documents").apply(MockLLM(), searxng)

    def test_mcp_no_ofrece_garantia_local(self):
        with self.assertRaisesRegex(RuntimeError, "MCP"):
            PrivacyPolicy("private-documents").apply(
                MockLLM(), MCPSearchAPI(["python", "fake.py"]))

    def test_guard_rechaza_url_privada_en_resultado(self):
        guard = GuardSearch(StubSearch([{
            "title": "privado", "url": "http://127.0.0.1/dato", "snippet": "x"}]), "public")
        with self.assertRaisesRegex(RuntimeError, "no público"):
            guard.search("consulta")

    def test_budget_desenvuelve_al_validar(self):
        with self.assertRaisesRegex(RuntimeError, "nube"):
            PrivacyPolicy("local-only").apply(BudgetLLM(OpenRouterLLM(), 1), MockSearchAPI())


class TestEncryptedState(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ruta = str(Path(self.tmp.name) / "estado.bin")
        self.clave = Fernet.generate_key().decode("utf-8")

    def test_cifrado_roundtrip_y_clave_incorrecta(self):
        contexto = ResearchContext("pregunta sensible")
        save_encrypted_research_state(self.ruta, contexto, "informe", True, key=self.clave)
        self.assertNotIn(b"pregunta sensible", Path(self.ruta).read_bytes())

        restaurado, report, completed = load_encrypted_research_state(self.ruta, self.clave)
        self.assertEqual(restaurado.question, "pregunta sensible")
        self.assertEqual(report, "informe")
        self.assertTrue(completed)
        with self.assertRaisesRegex(RuntimeError, "descifrar"):
            load_encrypted_research_state(self.ruta, Fernet.generate_key().decode())

    def test_orquestador_reanuda_estado_cifrado(self):
        with patch.dict(os.environ, {"THINKER_STATE_KEY": self.clave}):
            report, _ = ResearchOrchestrator(
                MockLLM(), MockSearchAPI(), state_path=self.ruta,
                encrypt_state=True).research("pregunta")
            llm = _Contador()
            resumed, _ = ResearchOrchestrator(
                llm, MockSearchAPI(), state_path=self.ruta,
                encrypt_state=True).research("pregunta")
            self.assertEqual(resumed, report)
            self.assertEqual(llm.calls, 0)
        self.assertNotIn(b"SIMULADO por MockLLM", Path(self.ruta).read_bytes())

    def test_falta_clave_es_error_explicito(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "THINKER_STATE_KEY"):
                save_encrypted_research_state(
                    self.ruta, ResearchContext("pregunta"), key=None)


if __name__ == "__main__":
    unittest.main()
