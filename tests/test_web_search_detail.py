"""Tests precisos de los proveedores de búsqueda y del reporte de código.

Complementa a tests/test_decision_engines.py: las mutaciones sobrevivían por
comprobar "no revienta" en vez de la conducta exacta (parámetros enviados,
limpieza de HTML, resolución de redirecciones, formato del reporte).
"""

import unittest
from unittest.mock import patch

from code_design_improvement_tools import (CodeAnalysisContext,
                                           CodeDesignThinker,
                                           CodeImprovementOrchestrator)
from deep_research_system import MockLLM
from web_search import (DuckDuckGoSearchAPI, MockSearchAPI,
                        WikipediaSearchAPI, formulate_query)


class _Respuesta:
    def __init__(self, texto="", payload=None, status=200):
        self.text = texto
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class TestWikipediaSearch(unittest.TestCase):

    PAYLOAD = {"query": {"search": [
        {"title": "Fusión nuclear",
         "snippet": 'La <span class="searchmatch">fusión</span> &amp; m&aacute;s'},
    ]}}

    def test_construye_url_y_limpia_html(self):
        with patch("web_search.requests.get", return_value=_Respuesta(payload=self.PAYLOAD)) as get:
            resultados = WikipediaSearchAPI(language="es").search("fusión", 3)
        self.assertEqual(len(resultados), 1)
        self.assertEqual(resultados[0]["url"],
                         "https://es.wikipedia.org/wiki/Fusi%C3%B3n_nuclear")
        self.assertEqual(resultados[0]["snippet"], "La fusión & más")
        self.assertEqual(resultados[0]["source"], "wikipedia")
        # srlimit debe reflejar max_results solicitado
        self.assertEqual(get.call_args.kwargs["params"]["srlimit"], 3)
        self.assertEqual(get.call_args.kwargs["params"]["srsearch"], "fusión")

    def test_respuesta_sin_clave_query_eleva_error(self):
        with patch("web_search.requests.get", return_value=_Respuesta(payload={"error": "x"})):
            with self.assertRaises(RuntimeError):
                WikipediaSearchAPI().search("x")

    def test_json_invalido_eleva_error(self):
        class SinJson(_Respuesta):
            def json(self):
                raise ValueError("no json")

        with patch("web_search.requests.get", return_value=SinJson()):
            with self.assertRaises(RuntimeError):
                WikipediaSearchAPI().search("x")

    def test_error_http_se_propaga(self):
        with patch("web_search.requests.get", return_value=_Respuesta(status=500)):
            with self.assertRaises(RuntimeError):
                WikipediaSearchAPI().search("x")

    def test_max_results_cero_no_llama_a_la_red(self):
        with patch("web_search.requests.get") as get:
            self.assertEqual(WikipediaSearchAPI().search("x", 0), [])
        get.assert_not_called()


class TestDuckDuckGoSearch(unittest.TestCase):

    HTML = ('<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fejemplo.com%2Fa">'
            'T&iacute;tulo <b>A</b></a>'
            '<a class="result__snippet">Resumen <span>x</span> uno</a>'
            '<a class="result__a" href="https://ejemplo.com/b">Titulo B</a>'
            '<a class="result__snippet">Resumen dos</a>')

    def test_parsea_titulo_snippet_y_resuelve_redireccion(self):
        with patch("web_search.requests.post", return_value=_Respuesta(texto=self.HTML)) as post:
            resultados = DuckDuckGoSearchAPI().search("consulta", 5)
        self.assertEqual(len(resultados), 2)
        self.assertEqual(resultados[0]["url"], "https://ejemplo.com/a")
        self.assertEqual(resultados[0]["title"], "Título A")
        self.assertEqual(resultados[0]["snippet"], "Resumen x uno")
        self.assertEqual(resultados[0]["source"], "duckduckgo")
        self.assertEqual(resultados[1]["url"], "https://ejemplo.com/b")
        self.assertEqual(post.call_args.kwargs["data"], {"q": "consulta"})

    def test_respeta_max_results(self):
        with patch("web_search.requests.post", return_value=_Respuesta(texto=self.HTML)):
            self.assertEqual(len(DuckDuckGoSearchAPI().search("q", 1)), 1)

    def test_html_sin_resultados_eleva_error(self):
        with patch("web_search.requests.post", return_value=_Respuesta(texto="<html>nada</html>")):
            with self.assertRaises(RuntimeError):
                DuckDuckGoSearchAPI().search("q")

    def test_max_results_cero_no_llama_a_la_red(self):
        with patch("web_search.requests.post") as post:
            self.assertEqual(DuckDuckGoSearchAPI().search("q", 0), [])
        post.assert_not_called()

    def test_descarta_esquemas_no_http(self):
        html = ('<a class="result__a" href="javascript:alert(1)">Malo</a>'
                '<a class="result__snippet">s</a>'
                '<a class="result__a" href="https://bueno.example/x">Bueno</a>'
                '<a class="result__snippet">s2</a>')
        with patch("web_search.requests.post", return_value=_Respuesta(texto=html)):
            resultados = DuckDuckGoSearchAPI().search("q")
        self.assertEqual([r["url"] for r in resultados], ["https://bueno.example/x"])

    def test_clean_url_casos(self):
        limpiar = DuckDuckGoSearchAPI._clean_url
        self.assertEqual(limpiar("//duckduckgo.com/l/?uddg=https%3A%2F%2Fx.com%2Fy"),
                         "https://x.com/y")
        self.assertEqual(limpiar("//ejemplo.com/z"), "https://ejemplo.com/z")
        self.assertEqual(limpiar("http://ejemplo.com"), "http://ejemplo.com")
        self.assertEqual(limpiar("javascript:alert(1)"), "")
        self.assertEqual(limpiar("mailto:a@b.c"), "")
        self.assertEqual(limpiar("sin-esquema"), "")

    def test_clean_url_rechaza_hosts_privados(self):
        limpiar = DuckDuckGoSearchAPI._clean_url
        for href in ("http://localhost/x", "http://localhost./x",
                     "http://127.0.0.1/x", "http://127.1/x",
                     "http://192.168.1.10/x", "http://10.0.0.5/x",
                     "http://[::1]/x", "http://0.0.0.0/x",
                     "http://:8080/x"):
            with self.subTest(href=href):
                self.assertEqual(limpiar(href), "")


class TestMockSearchAPI(unittest.TestCase):

    def test_resultado_determinista_y_marcado(self):
        resultados = MockSearchAPI().search("fusión nuclear", 5)
        self.assertEqual(len(resultados), 1)
        self.assertEqual(resultados[0]["source"], "mock-search")
        self.assertIn("fusión-nuclear", resultados[0]["url"])

    def test_respeta_max_results_cero(self):
        self.assertEqual(MockSearchAPI().search("x", 0), [])


class TestFormulateQueryDetalle(unittest.TestCase):

    def test_recorta_a_max_terms_y_quita_duplicados(self):
        q = formulate_query("fusión fusión nuclear plasma tokamak iter demo", 3)
        self.assertEqual(q, "fusión nuclear plasma")

    def test_sin_terminos_utiles_devuelve_la_pregunta(self):
        self.assertEqual(formulate_query("¿Qué es?"), "¿Qué es?")

    def test_anclas_se_anteponen_sin_duplicarse(self):
        q = formulate_query("plasma tokamak", 3, anchor_terms=["fusión", "plasma"])
        self.assertEqual(q, "fusión plasma tokamak")


class TestReporteDeCodigo(unittest.TestCase):

    def _orquestador_con_resultados(self):
        thinker = CodeDesignThinker(name="t", llm_provider=MockLLM())
        orquestador = CodeImprovementOrchestrator(
            thinker, source_code="import os, sys\n" + "x = 1\n" * 5)
        orquestador.analyze_and_improve()
        return orquestador

    def test_sin_resultados_avisa(self):
        thinker = CodeDesignThinker(name="t", llm_provider=MockLLM())
        self.assertEqual(
            CodeImprovementOrchestrator(thinker).generate_report(),
            "No results to report.")

    def test_reporte_contiene_secciones_y_datos_reales(self):
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            orquestador = self._orquestador_con_resultados()
        reporte = orquestador.generate_report()
        for seccion in ("# Análisis y Mejora de Proyecto de Código",
                        "## Resumen Ejecutivo", "## Problemas Detectados",
                        "## Decisiones de Diseño", "## Plan de Implementación",
                        "## Criterios de Validación", "*Pasos deliberados: 7/7*"):
            self.assertIn(seccion, reporte)
        # El issue real del análisis estático aparece con su severidad
        self.assertIn("[MEDIUM]", reporte)
        self.assertIn("importaciones múltiples", reporte)
        self.assertIn("Sugerencia:", reporte)

    def test_el_analisis_estatico_alimenta_el_contexto(self):
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            orquestador = self._orquestador_con_resultados()
        self.assertEqual(orquestador.context.to_dict()["total_issues"], 1)
        self.assertEqual(orquestador.results["efficiency_principle"],
                         "Hacer las cosas de manera eficiente")

    def test_contexto_sin_issues_reporta_cero(self):
        import contextlib
        import io
        thinker = CodeDesignThinker(name="t", llm_provider=MockLLM())
        orquestador = CodeImprovementOrchestrator(thinker, source_code="x = 1\n")
        with contextlib.redirect_stdout(io.StringIO()):
            orquestador.analyze_and_improve()
        self.assertEqual(orquestador.context.to_dict()["total_issues"], 0)
        self.assertIn("Problemas Detectados", orquestador.generate_report())

    def test_issue_critico_se_ordena_primero_y_sobrevive_al_recorte(self):
        ctx = CodeAnalysisContext("p", max_issues=2)
        for severidad in ("low", "medium", "critical"):
            ctx.add_issue("x", severidad, f"desc {severidad}")
        self.assertEqual([i["severity"] for i in ctx.issues], ["critical", "medium"])


if __name__ == "__main__":
    unittest.main()
