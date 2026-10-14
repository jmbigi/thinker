"""Tests de precisión: valores y efectos exactos (contra mutantes supervivientes).

Motivo: tras medir con mutmut quedaban 1.133 mutantes vivos. Estos tests fijan
los valores concretos (constantes, límites, formatos, claves devueltas) que los
tests de "no revienta" no distinguían.
"""

import json
import unittest
from unittest.mock import patch

from code_design_improvement_tools import (CodeDesignThinker,
                                           CodeImprovementOrchestrator,
                                           analyze_python_source)
from deep_research_system import (ClaimExtractor, EvidenceEvaluator, MockLLM,
                                  ResearchContext, SourceRetriever)
from pensamiento_layer import DeepResearchThinkingLayer
from tests.helpers import StubLLM, StubSearch
from web_search import WikipediaSearchAPI


class _Respuesta:
    def __init__(self, payload=None):
        self._payload = payload or {"query": {"search": []}}

    def json(self):
        return self._payload

    def raise_for_status(self):
        pass


class TestMockLLMValoresExactos(unittest.TestCase):

    def setUp(self):
        self.llm = MockLLM()

    def test_claves_de_descomposicion(self):
        lineas = self.llm.generate("Decompose this into sub-questions").split("\n")
        self.assertEqual(lineas[0], "¿Cuáles son los avances recientes documentados sobre el tema?")
        self.assertEqual(lineas[2], "¿Qué limitaciones, riesgos e incertidumbres se reportan?")

    def test_valor_de_confidence_en_claims(self):
        datos = json.loads(self.llm.generate("Extract factual claims from this"))
        self.assertEqual(datos[0]["confidence"], 0.7)
        self.assertEqual(datos[0]["source_url"], "https://example.com/mock-source")

    def test_valores_en_evaluacion(self):
        datos = json.loads(self.llm.generate("Evaluate this claim against sources"))
        self.assertEqual(datos["credibility"], 0.75)
        self.assertEqual(datos["confidence"], 0.7)
        self.assertEqual(datos["verdict"], "supported")

    def test_numero_de_paso_es_entero_y_con_nota(self):
        datos = json.loads(self.llm.generate("PASO 2 - PLAN"))
        self.assertIsInstance(datos["paso"], int)
        self.assertEqual(datos["paso"], 2)
        self.assertEqual(datos["confianza"], 0.7)
        self.assertIn("determinista", datos["nota"])

    def test_texto_de_respaldo_exacto(self):
        self.assertEqual(
            self.llm.generate("cualquier cosa"),
            "Respuesta simulada por MockLLM (offline): "
            "el prompt no corresponde a un patrón conocido.")


class TestEvidenceEvaluatorDetalles(unittest.TestCase):

    def test_trunca_el_snippet_a_200_y_numerar_fuentes(self):
        llm = StubLLM(lambda p: '{"verdict": "supported", "credibility": 1.0, "confidence": 1.0, "reasoning": "r"}')
        ctx = ResearchContext("q")
        ctx.sources = [
            {"url": "u1", "title": "T1", "snippet": "A" * 300},
            {"url": "u2", "title": "T2", "snippet": "B" * 300},
        ]
        EvidenceEvaluator(llm).decide(ctx, {"claim": "CL", "source_url": "u1"})
        prompt = llm.prompts[0]
        # Sólo la fuente que coincide por URL, con el snippet truncado a 200
        self.assertIn("Source 1: T1: " + "A" * 200, prompt)
        self.assertNotIn("A" * 201, prompt)
        self.assertNotIn("Source 2", prompt)
        self.assertIn("Claim: CL", prompt)
        self.assertIn("Return ONLY JSON", prompt)

    def test_formato_de_dos_decimales_en_el_log(self):
        llm = StubLLM(lambda p: '{"verdict": "supported", "credibility": 0.5, "confidence": 0.5, "reasoning": "r"}')
        ctx = ResearchContext("q")
        EvidenceEvaluator(llm).decide(ctx, {"claim": "C", "source_url": "u"})
        self.assertIn("Credibility: 0.50", ctx.decision_log[-1]["rationale"])

    def test_las_evaluaciones_se_acumulan(self):
        llm = StubLLM(lambda p: '{"verdict": "supported", "credibility": 0.5, "confidence": 0.5, "reasoning": "r"}')
        ctx = ResearchContext("q")
        evaluador = EvidenceEvaluator(llm)
        evaluador.decide(ctx, {"claim": "A", "source_url": "u"})
        evaluador.decide(ctx, {"claim": "B", "source_url": "u"})
        self.assertEqual([e["claim"] for e in ctx.evaluations], ["A", "B"])


class TestSourceRetrieverDetalles(unittest.TestCase):

    def test_campos_de_la_fuente_guardada(self):
        search = StubSearch([{"title": "T", "url": "u", "snippet": "s", "source": "wikipedia"}])
        ctx = ResearchContext("fusión nuclear")
        retriever = SourceRetriever(search)
        devueltos = retriever.decide(ctx, "plasma tokamak")
        fuente = ctx.sources[0]
        self.assertEqual(fuente["related_to"], "plasma tokamak")
        self.assertEqual(fuente["source"], "wikipedia")
        self.assertEqual(fuente["query_used"], search.queries[0])
        self.assertIn("retrieved_at", fuente)
        self.assertEqual(devueltos, search._results)
        self.assertEqual(fuente["url"], "u")

    def test_fuente_sin_source_queda_como_unknown(self):
        ctx = ResearchContext("fusión")
        SourceRetriever(StubSearch([{"title": "T", "url": "u"}])).decide(ctx, "plasma")
        self.assertEqual(ctx.sources[0]["source"], "unknown")
        self.assertEqual(ctx.sources[0]["snippet"], "")

    def test_escalera_de_consultas_en_orden(self):
        class SoloTercera(StubSearch):
            def search(self, query, max_results=5):
                self.queries.append(query)
                if len(self.queries) == 3:
                    return [{"title": "T", "url": "u"}]
                return []

        search = SoloTercera([])
        ctx = ResearchContext("¿Cuál es el estado de la fusión nuclear?")
        SourceRetriever(search).decide(ctx, "materiales de primera pared y tritio")
        self.assertEqual(len(search.queries), 3)
        # 3ª consulta = solo las anclas de la pregunta original, sin la subpregunta
        self.assertEqual(search.queries[2], "estado fusión nuclear")
        self.assertEqual(len(ctx.sources), 1)


class TestClaimExtractorDetalles(unittest.TestCase):

    def test_source_id_unknown_si_falta_url(self):
        ctx = ResearchContext("q")
        claims = ClaimExtractor(StubLLM(lambda p: '[{"claim": "C", "confidence": 0.5}]')).decide(
            ctx, {"snippet": "s"})
        self.assertEqual(claims[0]["source_id"], "unknown")

    def test_acumula_claims_en_el_contexto(self):
        ctx = ResearchContext("q")
        ctx.claims = [{"claim": "previa"}]
        extractor = ClaimExtractor(StubLLM(lambda p: '[{"claim": "nueva"}]'))
        extractor.decide(ctx, {"url": "u", "snippet": "s"})
        self.assertEqual([c["claim"] for c in ctx.claims], ["previa", "nueva"])

    def test_mensaje_del_log_incluye_url_y_cuenta(self):
        ctx = ResearchContext("q")
        ClaimExtractor(StubLLM(lambda p: '[{"claim": "C"}]')).decide(
            ctx, {"url": "https://x", "snippet": "s"})
        self.assertEqual(ctx.decision_log[-1]["rationale"],
                         "Extracted 1 claims from https://x")


class TestAnalisisEstaticoDetalles(unittest.TestCase):

    def test_limite_exacto_de_linea_larga(self):
        # El umbral es >120 caracteres ya recortados: 120 no avisa, 121 sí.
        self.assertEqual(len(analyze_python_source("x = 1  # " + "a" * 111)["metrics"]["issues"]), 0)
        largo = analyze_python_source("x = 1  # " + "a" * 112)["metrics"]["issues"]
        self.assertEqual(len(largo), 1)
        self.assertEqual(largo[0]["severity"], "low")

    def test_complejidad_cuenta_if_for_while_try(self):
        codigo = (
            "def f(xs):\n"
            "    for x in xs:\n"
            "        if x:\n"
            "            while x:\n"
            "                x -= 1\n"
            "    try:\n"
            "        return 1\n"
            "    except Exception:\n"
            "        return 0\n"
        )
        self.assertEqual(analyze_python_source(codigo)["source_summary"]["complexity"], 4)

    def test_recuento_de_lineas_y_funciones(self):
        r = analyze_python_source("def a():\n    pass\n\n\ndef b():\n    pass\n")
        self.assertEqual(r["source_summary"]["total_lines"], 6)
        self.assertEqual(r["source_summary"]["functions"], 2)
        self.assertEqual(r["source_summary"]["classes"], 0)

    def test_efficiency_score_es_issues_sobre_30(self):
        codigo = "\n".join("import os, sys" for _ in range(3))
        score = analyze_python_source(codigo)["metrics"]["efficiency_score"]
        self.assertAlmostEqual(score, 3 / 30.0, places=6)

    def test_recorta_a_cincuenta_issues(self):
        codigo = "\n".join("import os, sys" for _ in range(60))
        self.assertEqual(len(analyze_python_source(codigo)["metrics"]["issues"]), 50)

    def test_sugerencia_y_razonamiento_presentes(self):
        issue = analyze_python_source("import os, sys\n")["metrics"]["issues"][0]
        self.assertEqual(issue["category"], "style")
        self.assertIn("Separar importaciones", issue["suggestion"])
        self.assertIn("Mantenimiento", issue["thinking_reasoning"])


class TestRenderThought(unittest.TestCase):

    def test_incluye_etiquetas_de_pasos_y_contadores(self):
        layer = DeepResearchThinkingLayer(MockLLM(), name="t")
        texto = layer.think("pregunta")["thought"]
        for etiqueta in ("PASO 1 - ANÁLISIS", "PASO 4 - RESULTADOS",
                         "PASO 6 - EVALUACIÓN", "PASO 7 - SÍNTESIS"):
            self.assertIn(etiqueta, texto)
        self.assertIn("PASOS COMPLETADOS: 7/7", texto)
        self.assertIn("CONFIANZA GENERAL:", texto)
        self.assertIn("VALIDEZ: VALID", texto)

    def test_ciclo_parcial_incluye_el_paso_invalido_vacio(self):
        layer = DeepResearchThinkingLayer(
            StubLLM(lambda p: "contenido suficientemente largo" if "PASO 1" in p else ""))
        texto = layer.think("pregunta")["thought"]
        self.assertIn("PASO 1 - ANÁLISIS: contenido suficientemente largo", texto)
        # El paso que falla se detiene ahí y queda registrado vacío
        self.assertIn("PASO 2 - PLAN: \n", texto)
        self.assertNotIn("PASO 3", texto)
        self.assertIn("PASOS COMPLETADOS: 2/7", texto)
        self.assertIn("VALIDEZ: REVISAR", texto)


class TestWikipediaDetalles(unittest.TestCase):

    def test_idioma_y_parametros(self):
        with patch("web_search.requests.get", return_value=_Respuesta()) as get:
            WikipediaSearchAPI(language="en").search("fusion", 7)
        self.assertTrue(get.call_args.args[0].startswith("https://en.wikipedia.org/"))
        params = get.call_args.kwargs["params"]
        self.assertEqual(params["srlimit"], 7)
        self.assertEqual(params["list"], "search")
        self.assertEqual(params["format"], "json")

    def test_max_results_por_defecto(self):
        with patch("web_search.requests.get", return_value=_Respuesta()) as get:
            WikipediaSearchAPI().search("x")
        self.assertEqual(get.call_args.kwargs["params"]["srlimit"], 5)


class TestOrquestadorDeCodigoDetalles(unittest.TestCase):

    def _ejecutar(self, fuente="import os, sys\n"):
        import contextlib
        import io
        thinker = CodeDesignThinker(name="t", llm_provider=MockLLM())
        orq = CodeImprovementOrchestrator(thinker, source_code=fuente)
        with contextlib.redirect_stdout(io.StringIO()):
            orq.analyze_and_improve()
        return orq

    def test_claves_del_resultado(self):
        orq = self._ejecutar()
        for clave in ("analysis", "objectives", "design_options_considered",
                      "evaluations", "selection", "implementation_plan",
                      "validation_criteria", "total_thinking_steps",
                      "efficiency_principle", "project_metrics"):
            self.assertIn(clave, orq.results)
        self.assertEqual(orq.results["total_thinking_steps"], 7)

    def test_reporte_con_cifras_exactas(self):
        reporte = self._ejecutar().generate_report()
        self.assertIn("- **Pasos de pensamiento**: 7", reporte)
        self.assertIn("- **Problemas identificados**: 1", reporte)
        self.assertIn("- **Score de eficiencia**:", reporte)
        self.assertIn("*Pasos deliberados: 7/7*", reporte)

    def test_contexto_de_metricas_incluye_issues_detallados(self):
        ctx = self._ejecutar().context
        self.assertIn("issues", ctx.to_dict())
        self.assertEqual(len(ctx.to_dict()["issues"]), 1)
        self.assertEqual(ctx.to_dict()["total_issues"], 1)


if __name__ == "__main__":
    unittest.main()
