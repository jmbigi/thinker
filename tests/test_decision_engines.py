"""Tests de comportamiento preciso de los motores de decisión.

Motivo (P1.1): la cobertura medía líneas ejecutadas, no errores detectados.
Las pruebas de mutación (mutmut) mostraron supervivientes concentrados en
`MockLLM`, `SourceRetriever`, `ClaimExtractor`, `EvidenceEvaluator`,
`ReportGenerator` y `DuckDuckGoSearchAPI`: se ejecutaban sus líneas pero no se
comprobaba su comportamiento exacto. Aquí se fijan esas conductas.
"""

import json
import unittest

from deep_research_system import (ClaimExtractor, EvidenceEvaluator,
                                  MockLLM, ReportGenerator, ResearchContext,
                                  SourceRetriever)
from tests.helpers import StubLLM, StubSearch


class TestMockLLMComportamiento(unittest.TestCase):
    """MockLLM debe responder con la forma exacta que cada componente espera."""

    def setUp(self):
        self.llm = MockLLM()

    def test_descomposicion_devuelve_tres_lineas_sin_numeracion(self):
        salida = self.llm.generate("Decompose this into 3-5 sub-questions")
        lineas = salida.split("\n")
        self.assertEqual(len(lineas), 3)
        for linea in lineas:
            self.assertTrue(linea.strip())
            self.assertFalse(linea.strip()[0].isdigit())

    def test_claims_es_json_valido_con_las_claves_esperadas(self):
        salida = self.llm.generate("Extract factual claims from this snippet")
        datos = json.loads(salida)
        self.assertIsInstance(datos, list)
        self.assertEqual(set(datos[0]), {"claim", "confidence", "source_url"})
        self.assertIsInstance(datos[0]["confidence"], float)

    def test_evaluacion_es_json_con_veredicto_valido(self):
        salida = self.llm.generate("Evaluate this claim against the sources")
        datos = json.loads(salida)
        self.assertEqual(set(datos), {"verdict", "credibility", "confidence", "reasoning"})
        self.assertIn(datos["verdict"],
                      {"supported", "contradicted", "not_addressed"})

    def test_informe_es_markdown_declarado_como_simulado(self):
        salida = self.llm.generate("Generate a comprehensive research report")
        self.assertIn("# Informe", salida)
        self.assertIn("SIMULADO", salida)
        self.assertIn("## Conclusiones", salida)

    def test_detecta_el_numero_de_paso(self):
        datos = json.loads(self.llm.generate("PASO 4 - RESULTADOS DE BÚSQUEDA"))
        self.assertEqual(datos["paso"], 4)

    def test_prompt_desconocido_se_declara_simulado(self):
        salida = self.llm.generate("pregunta cualquiera sin patrón")
        self.assertIn("MockLLM", salida)
        self.assertIn("offline", salida)


class TestSourceRetrieverComportamiento(unittest.TestCase):

    def test_usa_consulta_formulada_con_ancla_tematica(self):
        search = StubSearch([{"title": "T", "url": "u1", "snippet": "s"}])
        ctx = ResearchContext("¿Cuál es el estado actual de la fusión nuclear?")
        SourceRetriever(search).decide(
            ctx, "¿Cuáles son los logros experimentales recientes en ganancia de energía?")
        consulta = search.queries[0]
        # Las anclas (términos de la pregunta original) van AL PRINCIPIO: sin
        # ellas la subpregunta pierde el tema (hallazgo 19).
        self.assertTrue(consulta.startswith("estado fusión nuclear"),
                        f"consulta sin anclas al principio: {consulta!r}")
        self.assertIn("logros", consulta)
        self.assertEqual(len(search.queries), 1)

    def test_no_repite_fuentes_ya_recuperadas(self):
        resultados = [{"title": "T", "url": "u1", "snippet": "s"}]
        search = StubSearch(resultados)
        ctx = ResearchContext("fusión nuclear")
        retriever = SourceRetriever(search)
        retriever.decide(ctx, "ganancia de energía")
        retriever.decide(ctx, "confinamiento de plasma")
        self.assertEqual(len(ctx.sources), 1, "duplicó una fuente por URL")

    def test_registra_cuenta_de_fuentes_nuevas(self):
        search = StubSearch([
            {"title": "A", "url": "u1"}, {"title": "B", "url": "u2"},
        ])
        ctx = ResearchContext("fusión")
        SourceRetriever(search).decide(ctx, "plasma")
        decisiones = [d for d in ctx.decision_log if d["step"] == "source_retrieval"]
        self.assertEqual(len(decisiones), 1)
        self.assertIn("2 fuentes nuevas", decisiones[0]["rationale"])
        self.assertEqual(ctx.sources[0]["query_used"], search.queries[0])

    def test_amplia_la_consulta_si_no_hay_resultados(self):
        class SearchVacia(StubSearch):
            def search(self, query, max_results=5):
                self.queries.append(query)
                return [] if len(self.queries) < 4 else [{"title": "T", "url": "u"}]

        search = SearchVacia([])
        ctx = ResearchContext("fusión nuclear")
        SourceRetriever(search).decide(ctx, "materiales de primera pared")
        # Se probaron varias consultas y TODAS quedaron registradas
        self.assertGreaterEqual(len(search.queries), 2)
        requeries = [d for d in ctx.decision_log if d["decision"] == "requery"]
        self.assertEqual(len(requeries), len(search.queries) - 1)
        self.assertEqual(len(ctx.sources), 1)

    def test_limita_a_cinco_resultados_por_consulta(self):
        resultados = [{"title": f"T{i}", "url": f"u{i}"} for i in range(9)]
        ctx = ResearchContext("fusión")
        SourceRetriever(StubSearch(resultados)).decide(ctx, "plasma")
        self.assertEqual(len(ctx.sources), 5)


class TestClaimExtractorComportamiento(unittest.TestCase):

    def test_parsea_json_con_fences_y_anota_origen(self):
        respuesta = '```json\n[{"claim": "C", "confidence": 0.9, "source_url": "u"}]\n```'
        ctx = ResearchContext("q")
        fuente = {"url": "https://fuente", "snippet": "texto"}
        claims = ClaimExtractor(StubLLM(lambda p: respuesta)).decide(ctx, fuente)
        self.assertEqual(len(claims), 1)
        self.assertEqual(claims[0]["source_id"], "https://fuente")
        self.assertIn("extracted_at", claims[0])
        self.assertEqual(len(ctx.claims), 1)
        self.assertEqual(ctx.decision_log[-1]["decision"], "extract")

    def test_json_invalido_devuelve_vacio_y_registra_fallo(self):
        ctx = ResearchContext("q")
        claims = ClaimExtractor(StubLLM(lambda p: "no es json")).decide(
            ctx, {"url": "u", "snippet": "s"})
        self.assertEqual(claims, [])
        self.assertEqual(ctx.claims, [])
        self.assertEqual(ctx.decision_log[-1]["decision"], "fail")

    def test_objeto_json_en_vez_de_array_tambien_es_fallo(self):
        ctx = ResearchContext("q")
        claims = ClaimExtractor(
            StubLLM(lambda p: '{"claim": "suelto"}')).decide(ctx, {"url": "u", "snippet": "s"})
        self.assertEqual(claims, [])
        self.assertEqual(ctx.decision_log[-1]["decision"], "fail")

    def test_el_prompt_incluye_el_snippet(self):
        llm = StubLLM(lambda p: "[]")
        ClaimExtractor(llm).decide(ResearchContext("q"),
                                   {"url": "u", "snippet": "TEXTO_CLAVE"})
        self.assertIn("TEXTO_CLAVE", llm.prompts[0])


class TestEvidenceEvaluatorComportamiento(unittest.TestCase):

    def test_usa_las_fuentes_que_coinciden_por_url(self):
        llm = StubLLM(lambda p: '{"verdict": "supported", "credibility": 0.9, "confidence": 0.8, "reasoning": "r"}')
        ctx = ResearchContext("q")
        ctx.sources = [
            {"url": "otra", "title": "Otra", "snippet": "no relevante"},
            {"url": "objetivo", "title": "Objetivo", "snippet": "SNIPPET_OBJETIVO"},
        ]
        ev = EvidenceEvaluator(llm).decide(
            ctx, {"claim": "C", "source_url": "objetivo"})
        self.assertIn("SNIPPET_OBJETIVO", llm.prompts[0])
        self.assertNotIn("no relevante", llm.prompts[0])
        self.assertEqual(ev["source_url"], "objetivo")
        self.assertEqual(ev["claim"], "C")
        self.assertIn("evaluated_at", ev)

    def test_sin_coincidencia_usa_las_tres_primeras(self):
        llm = StubLLM(lambda p: '{"verdict": "not_addressed", "credibility": 0.1, "confidence": 0.1, "reasoning": "r"}')
        ctx = ResearchContext("q")
        ctx.sources = [{"url": f"u{i}", "title": f"T{i}", "snippet": f"s{i}"} for i in range(5)]
        EvidenceEvaluator(llm).decide(ctx, {"claim": "C", "source_url": "inexistente"})
        self.assertIn("s0", llm.prompts[0])
        self.assertIn("s2", llm.prompts[0])
        self.assertNotIn("s3", llm.prompts[0])

    def test_registra_veredicto_y_credibilidad(self):
        llm = StubLLM(lambda p: '{"verdict": "contradicted", "credibility": 0.42, "confidence": 0.5, "reasoning": "r"}')
        ctx = ResearchContext("q")
        EvidenceEvaluator(llm).decide(ctx, {"claim": "C", "source_url": "u"})
        rationale = ctx.decision_log[-1]["rationale"]
        self.assertIn("contradicted", rationale)
        self.assertIn("0.42", rationale)
        self.assertEqual(ctx.evaluations[-1]["verdict"], "contradicted")

    def test_json_invalido_produce_not_addressed_sin_tragar_error(self):
        llm = StubLLM(lambda p: "respuesta no json")
        ctx = ResearchContext("q")
        ev = EvidenceEvaluator(llm).decide(ctx, {"claim": "C", "source_url": "u"})
        self.assertEqual(ev["verdict"], "not_addressed")
        self.assertEqual(ev["credibility"], 0.0)
        self.assertIn("Failed to parse", ev["reasoning"])
        self.assertEqual(len(ctx.evaluations), 1)


class TestReportGeneratorComportamiento(unittest.TestCase):

    def test_prompt_incluye_la_pregunta_y_las_cifras(self):
        llm = StubLLM(lambda p: "# informe")
        ctx = ResearchContext("PREGUNTA_CLAVE")
        ctx.claims = [{"claim": "a"}, {"claim": "b"}]
        ctx.evaluations = [{"claim": "a", "verdict": "supported"}]
        ctx.sources = [{"url": "u1"}, {"url": "u2"}, {"url": "u3"}]
        ReportGenerator(llm).decide(ctx)
        prompt = llm.prompts[0]
        self.assertIn("PREGUNTA_CLAVE", prompt)
        self.assertIn("Total claims extracted: 2", prompt)
        self.assertIn("Supported: 1", prompt)
        self.assertIn("Total sources retrieved: 3", prompt)

    def test_extrae_conclusiones_y_registra_la_generacion(self):
        llm = StubLLM(lambda p: "# Uno\n## Dos\n### Tres\n#### Cuatro")
        ctx = ResearchContext("q")
        informe = ReportGenerator(llm).decide(ctx)
        self.assertEqual(informe, "# Uno\n## Dos\n### Tres\n#### Cuatro")
        self.assertTrue(ctx.conclusions)
        self.assertEqual(ctx.decision_log[-1]["step"], "report_generation")
        self.assertIn("conclusion sections", ctx.decision_log[-1]["rationale"])

    def test_clasifica_soportados_y_contradichos(self):
        llm = StubLLM(lambda p: "# informe")
        ctx = ResearchContext("q")
        ctx.claims = [{"claim": "soportado"}, {"claim": "contradicho"}]
        ctx.evaluations = [
            {"claim": "soportado", "verdict": "supported"},
            {"claim": "contradicho", "verdict": "contradicted"},
        ]
        ReportGenerator(llm).decide(ctx)
        prompt = llm.prompts[0]
        self.assertIn("Supported: 1", prompt)
        self.assertIn("Contradictions: 1", prompt)


if __name__ == "__main__":
    unittest.main()
