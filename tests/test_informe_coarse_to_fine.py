"""Tests offline del informe coarse-to-fine (inspirado en NCM, opt-in).

No usa red ni API keys: `StubLLM` es un doble SIMULADO y determinista.
"""

import unittest

from deep_research_system import (ReportGenerator, ResearchContext,
                                  ResearchOrchestrator)
from llm_providers import MockLLM
from tests.helpers import StubLLM
from web_search import MockSearchAPI


def contexto():
    ctx = ResearchContext("PREGUNTA")
    ctx.subquestions = ["S1", "S2"]
    ctx.sources = [
        {"title": "Fuente 1", "url": "u1", "snippet": "s1"},
        {"title": "Fuente 2", "url": "u2", "snippet": "s2"},
    ]
    ctx.claims = [{"claim": "c1", "source_url": "u1"},
                  {"claim": "c2", "source_url": "u2"}]
    ctx.evaluations = [{"claim": "c1", "verdict": "supported"},
                       {"claim": "c2", "verdict": "not_addressed"}]
    return ctx


def responder_por_etapas(secciones, contenidos):
    def responder(prompt):
        if "Design the outline" in prompt:
            return secciones
        if "Write the section" in prompt:
            for titulo, contenido in contenidos.items():
                if f'"{titulo}"' in prompt:
                    return contenido
        raise AssertionError(f"prompt inesperado: {prompt[:80]}")
    return responder


class TestInformeCoarseToFine(unittest.TestCase):

    def test_desactivado_una_llamada_y_prompt_original(self):
        llm = StubLLM(lambda p: "informe")

        informe = ReportGenerator(llm).decide(contexto())

        self.assertEqual(informe, "informe")
        self.assertEqual(len(llm.prompts), 1)
        self.assertIn("Generate a comprehensive research report",
                      llm.prompts[0])
        self.assertNotIn("Design the outline", llm.prompts[0])

    def test_activo_genera_esquema_y_una_llamada_por_seccion(self):
        llm = StubLLM(responder_por_etapas(
            '{"secciones": [{"titulo": "Uno"}, {"titulo": "Dos"}]}',
            {"Uno": "Contenido uno [1]", "Dos": "Contenido dos [2]"}))
        ctx = contexto()

        informe = ReportGenerator(llm, coarse_to_fine=True).decide(ctx)

        self.assertEqual(len(llm.prompts), 3)
        self.assertIn("Design the outline", llm.prompts[0])
        self.assertIn('"Uno"', llm.prompts[1])
        self.assertIn('"Dos"', llm.prompts[2])
        self.assertEqual(
            informe,
            "# Research Report: PREGUNTA\n\n"
            "## Uno\n\nContenido uno [1]\n\n"
            "## Dos\n\nContenido dos [2]")
        pasos = [d["step"] for d in ctx.decision_log]
        self.assertEqual(pasos[0], "report_outline")
        self.assertEqual(pasos.count("report_section"), 2)
        self.assertEqual(pasos[-1], "report_generation")
        self.assertEqual(ctx.decision_log[0]["rationale"],
                         "Outline with 2 sections")
        self.assertTrue(ctx.conclusions)

    def test_esquema_con_bloque_markdown_es_valido(self):
        llm = StubLLM(responder_por_etapas(
            '```json\n{"secciones": [{"titulo": "Uno"}]}\n```',
            {"Uno": "Contenido [1]"}))

        informe = ReportGenerator(llm, coarse_to_fine=True).decide(contexto())

        self.assertIn("## Uno", informe)
        self.assertEqual(len(llm.prompts), 2)

    def test_esquema_invalido_cae_a_pasada_unica_registrada(self):
        def responder(prompt):
            if "Design the outline" in prompt:
                return "esto no es JSON"
            return "informe de pasada única"

        llm = StubLLM(responder)
        ctx = contexto()

        informe = ReportGenerator(llm, coarse_to_fine=True).decide(ctx)

        self.assertEqual(informe, "informe de pasada única")
        self.assertEqual(len(llm.prompts), 2)
        self.assertIn("Generate a comprehensive research report",
                      llm.prompts[1])
        fallback = [d for d in ctx.decision_log
                    if d["step"] == "report_outline"][0]
        self.assertEqual(fallback["decision"], "fallback_single_pass")
        self.assertIn("Esquema inválido", fallback["rationale"])
        self.assertNotIn("report_section",
                         [d["step"] for d in ctx.decision_log])

    def test_seccion_vacia_se_marca_sin_inventar_contenido(self):
        llm = StubLLM(responder_por_etapas(
            '{"secciones": [{"titulo": "Uno"}]}', {"Uno": "   "}))
        ctx = contexto()

        informe = ReportGenerator(llm, coarse_to_fine=True).decide(ctx)

        self.assertIn("(No content generated for this section.)", informe)
        seccion = [d for d in ctx.decision_log
                   if d["step"] == "report_section"][0]
        self.assertEqual(seccion["decision"], "empty")
        self.assertEqual(seccion["rationale"], "Section: Uno")

    def test_filtra_claims_de_la_seccion_y_conserva_numeracion(self):
        llm = StubLLM(responder_por_etapas(
            '{"secciones": [{"titulo": "Uno", "claims": ["c1"]}]}',
            {"Uno": "Contenido [1]"}))
        ctx = contexto()

        ReportGenerator(llm, coarse_to_fine=True).decide(ctx)

        prompt = llm.prompts[1]
        self.assertIn("- [supported] c1", prompt)
        self.assertNotIn("c2", prompt)
        self.assertIn("[1] Fuente 1 — u1", prompt)
        self.assertIn("[2] Fuente 2 — u2", prompt)

    def test_limita_a_cinco_secciones_y_lo_declara(self):
        secciones = ", ".join(f'{{"titulo": "S{i}"}}' for i in range(1, 8))
        contenidos = {f"S{i}": f"C{i}" for i in range(1, 8)}
        llm = StubLLM(responder_por_etapas(
            f'{{"secciones": [{secciones}]}}', contenidos))
        ctx = contexto()

        informe = ReportGenerator(llm, coarse_to_fine=True).decide(ctx)

        self.assertEqual(len(llm.prompts), 6)
        self.assertEqual(informe.count("\n## "), 5)
        self.assertEqual(ctx.decision_log[0]["rationale"],
                         "Outline with 5 sections (truncated from 7)")

    def test_normalizacion_rechaza_esquemas_invalidos(self):
        invalidos = [
            [], {"secciones": []}, {"secciones": ["x"]},
            {"secciones": [{}]}, {"secciones": [{"titulo": "  "}]},
            {"secciones": [{"titulo": "T", "claims": "c1"}]},
        ]
        for datos in invalidos:
            with self.subTest(datos=datos):
                with self.assertRaises(ValueError):
                    ReportGenerator._normalizar_secciones(datos)

    def test_orquestador_propaga_el_modo(self):
        apagado = ResearchOrchestrator(MockLLM(), MockSearchAPI())
        encendido = ResearchOrchestrator(
            MockLLM(), MockSearchAPI(), informe_coarse_to_fine=True)

        self.assertFalse(apagado.generator.coarse_to_fine)
        self.assertTrue(encendido.generator.coarse_to_fine)


if __name__ == "__main__":
    unittest.main()
