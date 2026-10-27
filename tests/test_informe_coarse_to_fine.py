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
            '{"secciones": [{"titulo": "Uno"}, {"titulo": "Dos"}]}',
            {"Uno": "   ", "Dos": "Contenido [1]"}))
        ctx = contexto()

        informe = ReportGenerator(llm, coarse_to_fine=True).decide(ctx)

        self.assertIn("## Uno\n\n(No content generated for this section.)",
                      informe)
        seccion = [d for d in ctx.decision_log
                   if d["decision"] == "empty"][0]
        self.assertEqual(seccion["step"], "report_section")
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
            {"secciones": [{"titulo": "T", "claims": [1]}]},
            {"secciones": [{"titulo": "T\nX"}]},
            {"secciones": [{"titulo": "T"}, {"titulo": " t "}]},
        ]
        for datos in invalidos:
            with self.subTest(datos=datos):
                with self.assertRaises(ValueError):
                    ReportGenerator._normalizar_secciones(datos)

    def test_claims_del_esquema_inexistentes_se_registran(self):
        llm = StubLLM(responder_por_etapas(
            '{"secciones": [{"titulo": "Uno", "claims": ["fantasma"]}]}',
            {"Uno": "Contenido [1]"}))
        ctx = contexto()

        informe = ReportGenerator(llm, coarse_to_fine=True).decide(ctx)

        aviso = [d for d in ctx.decision_log
                 if d["decision"] == "claims_no_encontrados"][0]
        self.assertEqual(aviso["step"], "report_section")
        self.assertIn("fantasma", aviso["rationale"])
        # No se oculta evidencia: al no encontrar el claim, se usan todos.
        self.assertIn("- [supported] c1", llm.prompts[1])
        self.assertIn("- [not_addressed] c2", llm.prompts[1])
        self.assertIn("## Uno", informe)

    def test_pasada_unica_registra_cita_fuera_de_rango(self):
        llm = StubLLM(lambda p: "Dato [1] y [9]")
        ctx = contexto()

        ReportGenerator(llm).decide(ctx)

        avisos = [d for d in ctx.decision_log
                  if d["step"] == "report_validation"]
        self.assertEqual(len(avisos), 1)
        self.assertEqual(avisos[0]["decision"], "cita_fuera_de_rango")
        self.assertIn("[9]", avisos[0]["rationale"])
        self.assertIn("fuentes disponibles: 2", avisos[0]["rationale"])

    def test_anio_entre_corchetes_no_se_confunde_con_cita(self):
        llm = StubLLM(lambda p: "En [2026] ocurrió el hito")
        ctx = contexto()

        ReportGenerator(llm).decide(ctx)

        self.assertEqual(
            [d for d in ctx.decision_log
             if d["step"] == "report_validation"], [])

    def test_seccion_con_citas_validas_no_genera_avisos(self):
        llm = StubLLM(responder_por_etapas(
            '{"secciones": [{"titulo": "Uno"}]}',
            {"Uno": "Contenido [1] y [2]"}))
        ctx = contexto()

        ReportGenerator(llm, coarse_to_fine=True).decide(ctx)

        self.assertEqual(
            [d for d in ctx.decision_log
             if d["step"] == "report_validation"], [])
        self.assertEqual(
            [d for d in ctx.decision_log
             if d["decision"] == "sin_citas"], [])

    def test_seccion_sin_citas_se_registra(self):
        llm = StubLLM(responder_por_etapas(
            '{"secciones": [{"titulo": "Uno"}]}',
            {"Uno": "Contenido sin citas"}))
        ctx = contexto()

        ReportGenerator(llm, coarse_to_fine=True).decide(ctx)

        aviso = [d for d in ctx.decision_log
                 if d["decision"] == "sin_citas"][0]
        self.assertEqual(aviso["step"], "report_section")
        self.assertEqual(aviso["rationale"], "Section: Uno")

    def test_seccion_con_cita_fuera_de_rango_se_registra(self):
        llm = StubLLM(responder_por_etapas(
            '{"secciones": [{"titulo": "Uno"}]}',
            {"Uno": "Contenido [7]"}))
        ctx = contexto()

        ReportGenerator(llm, coarse_to_fine=True).decide(ctx)

        aviso = [d for d in ctx.decision_log
                 if d["step"] == "report_validation"][0]
        self.assertEqual(aviso["decision"], "cita_fuera_de_rango")
        self.assertIn("Sección Uno: [7]", aviso["rationale"])

    def test_error_en_una_seccion_no_tumba_el_informe(self):
        def responder(prompt):
            if "Design the outline" in prompt:
                return '{"secciones": [{"titulo": "Uno"}, {"titulo": "Dos"}]}'
            if '"Uno"' in prompt:
                return "Contenido uno [1]"
            if '"Dos"' in prompt:
                raise RuntimeError("fallo simulado")
            raise AssertionError(f"prompt inesperado: {prompt[:80]}")

        ctx = contexto()
        informe = ReportGenerator(
            StubLLM(responder), coarse_to_fine=True).decide(ctx)

        self.assertIn("## Uno\n\nContenido uno [1]", informe)
        self.assertIn("## Dos\n\n(No content generated for this section.)",
                      informe)
        error = [d for d in ctx.decision_log
                 if d["decision"] == "error"][0]
        self.assertEqual(error["step"], "report_section")
        self.assertIn("RuntimeError: fallo simulado", error["rationale"])
        self.assertEqual(ctx.decision_log[-1]["step"], "report_generation")

    def test_fallback_por_esquema_invalido_valida_citas(self):
        def responder(prompt):
            if "Design the outline" in prompt:
                return "esto no es JSON"
            return "Dato [9]"

        ctx = contexto()
        informe = ReportGenerator(
            StubLLM(responder), coarse_to_fine=True).decide(ctx)

        self.assertEqual(informe, "Dato [9]")
        aviso = [d for d in ctx.decision_log
                 if d["step"] == "report_validation"][0]
        self.assertEqual(aviso["decision"], "cita_fuera_de_rango")
        self.assertIn("Informe completo (fallback)", aviso["rationale"])
        self.assertIn("[9]", aviso["rationale"])

    def test_fallback_por_secciones_vacias_valida_citas(self):
        def responder(prompt):
            if "Design the outline" in prompt:
                return '{"secciones": [{"titulo": "Uno"}]}'
            if "Write the section" in prompt:
                return "   "
            return "Dato [9]"

        ctx = contexto()
        informe = ReportGenerator(
            StubLLM(responder), coarse_to_fine=True).decide(ctx)

        self.assertEqual(informe, "Dato [9]")
        aviso = [d for d in ctx.decision_log
                 if d["step"] == "report_validation"][0]
        self.assertEqual(aviso["decision"], "cita_fuera_de_rango")
        self.assertIn("Informe completo (fallback)", aviso["rationale"])

    def test_todas_las_secciones_vacias_caen_a_pasada_unica(self):
        def responder(prompt):
            if "Design the outline" in prompt:
                return '{"secciones": [{"titulo": "Uno"}]}'
            if "Write the section" in prompt:
                return "   "
            return "informe único"

        llm = StubLLM(responder)
        ctx = contexto()

        informe = ReportGenerator(llm, coarse_to_fine=True).decide(ctx)

        self.assertEqual(informe, "informe único")
        self.assertEqual(len(llm.prompts), 3)
        fallback = [d for d in ctx.decision_log
                    if d["step"] == "report_generation"
                    and d["decision"] == "fallback_single_pass"]
        self.assertEqual(len(fallback), 1)
        self.assertIn("Ninguna sección generó contenido",
                      fallback[0]["rationale"])

    def test_orquestador_propaga_el_modo(self):
        apagado = ResearchOrchestrator(MockLLM(), MockSearchAPI())
        encendido = ResearchOrchestrator(
            MockLLM(), MockSearchAPI(), informe_coarse_to_fine=True)

        self.assertFalse(apagado.generator.coarse_to_fine)
        self.assertTrue(encendido.generator.coarse_to_fine)


if __name__ == "__main__":
    unittest.main()
