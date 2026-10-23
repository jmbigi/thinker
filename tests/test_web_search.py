"""Tests offline de web_search.py: `requests` mockeado, cero llamadas de red reales."""

import socket
import unittest
from unittest.mock import MagicMock, patch

import requests

from web_search import (DuckDuckGoSearchAPI, MockSearchAPI, SearchAPI,
                        USER_AGENT, WikipediaSearchAPI, _es_host_publico,
                        _strip_html, formulate_query)


def fake_http_response(json_data=None, text=""):
    """Respuesta HTTP simulada con la interfaz de `requests.Response`."""
    resp = MagicMock()
    resp.text = text
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


DDG_HTML = """
<html><body>
<a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fpagina">Título <b>uno</b></a>
<a class="result__snippet" href="//duckduckgo.com/l/?uddg=x">Snippet <b>primero</b> aquí</a>
<a rel="nofollow" class="result__a" href="https://directa.org/doc">Título dos</a>
<a class="result__snippet" href="https://directa.org/doc">Snippet segundo</a>
</body></html>
"""

DDG_HTML_SOLO_JS = (
    '<a class="result__a" href="javascript:alert(1)">X</a>'
    '<a class="result__snippet" href="q">S</a>'
)


class TestFormulateQuery(unittest.TestCase):
    def test_elimina_stopwords_y_conserva_orden(self):
        q = formulate_query("¿Cuál es el estado actual de la fusión nuclear?")
        self.assertEqual(q, "estado fusión nuclear")

    def test_anchor_terms_van_al_principio(self):
        q = formulate_query("¿estado actual?", 4,
                            anchor_terms=["Fusión", "nuclear"])
        self.assertEqual(q, "fusión nuclear estado")

    def test_anchor_terms_deduplican_con_la_pregunta(self):
        q = formulate_query("fusión en la práctica", 4,
                            anchor_terms=["fusión", "nuclear"])
        self.assertEqual(q, "fusión nuclear práctica")

    def test_respeta_max_terms(self):
        self.assertEqual(
            formulate_query("alpha bravo charlie delta echo", 3),
            "alpha bravo charlie",
        )

    def test_descarta_palabras_cortas_y_digitos(self):
        # "xy" se descarta (≤2 letras), "123"/"456" no son palabras,
        # "def4" aporta solo el run de letras "def"
        self.assertEqual(formulate_query("abc 123 xy def4 456"), "abc def")

    def test_sin_terminos_devuelve_la_pregunta_original(self):
        self.assertEqual(formulate_query("¿y tú?"), "¿y tú?")

    def test_deduplica_terminos(self):
        self.assertEqual(formulate_query("fusión fusión nuclear"), "fusión nuclear")

    def test_max_terms_por_defecto_es_cuatro(self):
        self.assertEqual(
            formulate_query("alpha bravo charlie delta echo foxtrot"),
            "alpha bravo charlie delta",
        )

    def test_anchor_de_dos_letras_se_descarta(self):
        self.assertEqual(
            formulate_query("plasma", anchor_terms=["ab", "fusión"]),
            "fusión plasma",
        )

    def test_anchor_de_tres_letras_se_conserva(self):
        self.assertEqual(
            formulate_query("tokamak", anchor_terms=["sol", "fusión"]),
            "sol fusión tokamak",
        )


class TestSearchAPIInterface(unittest.TestCase):
    def test_search_api_es_abstracta(self):
        with self.assertRaises(TypeError):
            SearchAPI()


class TestStripHtml(unittest.TestCase):
    def test_quita_etiquetas_y_normaliza_espacios(self):
        self.assertEqual(_strip_html("<b>Hola</b>   mundo<br>!"), "Hola mundo!")

    def test_none_y_vacio(self):
        self.assertEqual(_strip_html(None), "")
        self.assertEqual(_strip_html(""), "")

    def test_entidades_html(self):
        self.assertEqual(_strip_html("a &amp; b"), "a & b")


class TestEsHostPublico(unittest.TestCase):
    def test_nombre_dns_publico_se_acepta(self):
        self.assertIs(_es_host_publico("example.com"), True)
        self.assertIs(_es_host_publico("es.wikipedia.org"), True)

    def test_subdominio_localhost_se_rechaza(self):
        self.assertIs(_es_host_publico("evil.localhost"), False)

    def test_localhost_con_punto_final_se_rechaza(self):
        self.assertIs(_es_host_publico("localhost."), False)
        self.assertIs(_es_host_publico("evil.localhost.:8080"), False)

    def test_notaciones_alternativas_de_ip_privada_se_rechazan(self):
        for host in ("127.1", "0x7f000001", "2130706433", "0177.0.0.1"):
            with self.subTest(host=host):
                self.assertIs(_es_host_publico(host), False)

    def test_ip_multicast_se_rechaza(self):
        self.assertIs(_es_host_publico("224.0.0.1"), False)

    def test_sin_inet_aton_rechaza_notaciones_numericas(self):
        """Plataformas sin `socket.inet_aton` (WASI/Emscripten): la política
        conservadora rechaza lo que parece IP numérica/hex y acepta nombres
        DNS inequívocos (antes TODO host pasaba como público)."""
        with patch.object(socket, "inet_aton", None):
            for host in ("127.1", "0x7f000001", "2130706433", "0177.0.0.1"):
                with self.subTest(host=host):
                    self.assertIs(_es_host_publico(host), False)
            self.assertIs(_es_host_publico("example.com"), True)
            self.assertIs(_es_host_publico("es.wikipedia.org"), True)


class TestMockSearchAPI(unittest.TestCase):
    def test_resultado_determinista_con_campos(self):
        results = MockSearchAPI().search("fusión nuclear")
        self.assertEqual(len(results), 1)
        r = results[0]
        self.assertEqual(r["title"], "Article about fusión nuclear")
        self.assertEqual(r["url"], "https://example.com/fusión-nuclear")
        self.assertIn("fusión nuclear", r["snippet"])
        self.assertEqual(r["source"], "mock-search")

    def test_max_results_recorta(self):
        results = MockSearchAPI().search("tema", max_results=0)
        self.assertEqual(results, [])


class TestWikipediaSearchAPI(unittest.TestCase):
    def test_endpoint_segun_idioma(self):
        self.assertEqual(
            WikipediaSearchAPI(language="en").endpoint,
            "https://en.wikipedia.org/w/api.php",
        )
        self.assertEqual(
            WikipediaSearchAPI().endpoint,
            "https://es.wikipedia.org/w/api.php",
        )

    @patch("web_search.requests.get")
    def test_busqueda_exitosa(self, mock_get):
        mock_get.return_value = fake_http_response(json_data={
            "query": {
                "search": [
                    {"title": "Fusión nuclear", "snippet": "<span>Proceso</span> de unión"},
                    {"title": "ITER", "snippet": "Reactor experimental"},
                ]
            }
        })
        results = WikipediaSearchAPI(language="es").search("fusión", max_results=2)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["title"], "Fusión nuclear")
        self.assertEqual(
            results[0]["url"],
            "https://es.wikipedia.org/wiki/Fusi%C3%B3n_nuclear",
        )
        self.assertEqual(results[0]["snippet"], "Proceso de unión")
        self.assertEqual(results[0]["source"], "wikipedia")

        args, kwargs = mock_get.call_args
        self.assertEqual(args[0], "https://es.wikipedia.org/w/api.php")
        self.assertEqual(kwargs["params"]["srsearch"], "fusión")
        self.assertEqual(kwargs["params"]["srlimit"], 2)

    @patch("web_search.requests.get")
    def test_payload_sin_clave_query_eleva_runtime_error(self, mock_get):
        mock_get.return_value = fake_http_response(json_data={"batchcomplete": ""})
        with self.assertRaises(RuntimeError) as cm:
            WikipediaSearchAPI().search("fusión")
        self.assertIn("Respuesta inesperada", str(cm.exception))

    @patch("web_search.requests.get")
    def test_json_invalido_eleva_runtime_error(self, mock_get):
        resp = fake_http_response()
        resp.json.side_effect = ValueError("no JSON")
        mock_get.return_value = resp
        with self.assertRaises(RuntimeError):
            WikipediaSearchAPI().search("fusión")

    @patch("web_search.requests.get")
    def test_error_http_se_propaga(self, mock_get):
        resp = fake_http_response(json_data={})
        resp.raise_for_status.side_effect = requests.HTTPError("500 Server Error")
        mock_get.return_value = resp
        with self.assertRaises(requests.HTTPError):
            WikipediaSearchAPI().search("fusión")

    @patch("web_search.requests.get")
    def test_timeout_y_cabecera_exactos_en_la_peticion(self, mock_get):
        mock_get.return_value = fake_http_response(
            json_data={"query": {"search": []}})
        api = WikipediaSearchAPI()
        self.assertEqual(api.timeout, 20)
        api.search("fusión", 2)
        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["timeout"], 20)
        self.assertEqual(kwargs["headers"], {"User-Agent": USER_AGENT})

    @patch("web_search.requests.get")
    def test_params_exactos_de_la_api(self, mock_get):
        mock_get.return_value = fake_http_response(
            json_data={"query": {"search": []}})
        WikipediaSearchAPI().search("fusión nuclear", 3)
        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["params"], {
            "action": "query",
            "list": "search",
            "srsearch": "fusión nuclear",
            "format": "json",
            "srlimit": 3,
        })

    @patch("web_search.requests.get")
    def test_max_results_uno_realiza_busqueda(self, mock_get):
        mock_get.return_value = fake_http_response(json_data={
            "query": {"search": [{"title": "T", "snippet": "s"}]}})
        results = WikipediaSearchAPI().search("tema", 1)
        self.assertEqual(len(results), 1)
        self.assertEqual(mock_get.call_args.kwargs["params"]["srlimit"], 1)

    @patch("web_search.requests.get")
    def test_hit_sin_title_ni_snippet_usa_cadenas_vacias(self, mock_get):
        mock_get.return_value = fake_http_response(
            json_data={"query": {"search": [{}]}})
        results = WikipediaSearchAPI().search("tema", 1)
        self.assertEqual(results[0]["title"], "")
        self.assertEqual(results[0]["url"], "https://es.wikipedia.org/wiki/")
        self.assertEqual(results[0]["snippet"], "")


class TestDuckDuckGoSearchAPI(unittest.TestCase):
    @patch("web_search.requests.post")
    def test_busqueda_exitosa_limpia_redirects(self, mock_post):
        mock_post.return_value = fake_http_response(text=DDG_HTML)
        results = DuckDuckGoSearchAPI().search("consulta")

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["url"], "https://example.com/pagina")
        self.assertEqual(results[0]["title"], "Título uno")
        self.assertEqual(results[0]["snippet"], "Snippet primero aquí")
        self.assertEqual(results[0]["source"], "duckduckgo")
        self.assertEqual(results[1]["url"], "https://directa.org/doc")

        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://html.duckduckgo.com/html/")
        self.assertEqual(kwargs["data"], {"q": "consulta"})

    @patch("web_search.requests.post")
    def test_max_results_recorta(self, mock_post):
        mock_post.return_value = fake_http_response(text=DDG_HTML)
        results = DuckDuckGoSearchAPI().search("consulta", max_results=1)
        self.assertEqual(len(results), 1)

    @patch("web_search.requests.post")
    def test_html_sin_resultados_eleva_runtime_error(self, mock_post):
        mock_post.return_value = fake_http_response(text="<html><body>nada</body></html>")
        with self.assertRaises(RuntimeError) as cm:
            DuckDuckGoSearchAPI().search("consulta")
        self.assertIn("no se extrajo ningún resultado", str(cm.exception))

    @patch("web_search.requests.post")
    def test_url_javascript_se_descarta_y_sin_validas_eleva(self, mock_post):
        mock_post.return_value = fake_http_response(text=DDG_HTML_SOLO_JS)
        with self.assertRaises(RuntimeError):
            DuckDuckGoSearchAPI().search("consulta")

    @patch("web_search.requests.post")
    def test_error_http_se_propaga(self, mock_post):
        resp = fake_http_response(text=DDG_HTML)
        resp.raise_for_status.side_effect = requests.HTTPError("403 Forbidden")
        mock_post.return_value = resp
        with self.assertRaises(requests.HTTPError):
            DuckDuckGoSearchAPI().search("consulta")

    @patch("web_search.requests.post")
    def test_timeout_y_cabecera_exactos_en_la_peticion(self, mock_post):
        mock_post.return_value = fake_http_response(text=DDG_HTML)
        api = DuckDuckGoSearchAPI()
        self.assertEqual(api.timeout, 20)
        api.search("consulta")
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["timeout"], 20)
        self.assertEqual(kwargs["headers"], {"User-Agent": USER_AGENT})

    @patch("web_search.requests.post")
    def test_max_results_por_defecto_es_cinco(self, mock_post):
        html6 = "".join(
            f'<a class="result__a" href="https://s{i}.example/x">T{i}</a>'
            f'<a class="result__snippet">S{i}</a>'
            for i in range(6)
        )
        mock_post.return_value = fake_http_response(text=html6)
        results = DuckDuckGoSearchAPI().search("consulta")
        self.assertEqual(len(results), 5)

    @patch("web_search.requests.post")
    def test_mensaje_de_error_exacto_sin_resultados(self, mock_post):
        mock_post.return_value = fake_http_response(text="<html>nada</html>")
        with self.assertRaises(RuntimeError) as cm:
            DuckDuckGoSearchAPI().search("consulta")
        self.assertEqual(
            str(cm.exception),
            "DuckDuckGo devolvió 200 pero no se extrajo ningún resultado: "
            "el formato HTML puede haber cambiado.",
        )


class TestCleanUrl(unittest.TestCase):
    def test_resuelve_redirect_uddg(self):
        href = "//duckduckgo.com/l/?uddg=https%3A%2F%2Fejemplo.org%2Fa%20b&rut=zz"
        self.assertEqual(
            DuckDuckGoSearchAPI._clean_url(href), "https://ejemplo.org/a b"
        )

    def test_prefijo_protocolo_relativo(self):
        self.assertEqual(
            DuckDuckGoSearchAPI._clean_url("//ejemplo.org/ruta"),
            "https://ejemplo.org/ruta",
        )

    def test_url_directa_se_mantiene(self):
        self.assertEqual(
            DuckDuckGoSearchAPI._clean_url("https://ok.com/x"), "https://ok.com/x"
        )

    def test_descarta_esquemas_no_http(self):
        self.assertEqual(DuckDuckGoSearchAPI._clean_url("javascript:alert(1)"), "")
        self.assertEqual(DuckDuckGoSearchAPI._clean_url("ftp://host/x"), "")
        self.assertEqual(DuckDuckGoSearchAPI._clean_url("sin-esquema"), "")


if __name__ == "__main__":
    unittest.main()
