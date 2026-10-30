"""Contratos de conectores externos con respuestas simuladas, sin red."""

import unittest
from unittest.mock import patch

from web_search import (ArxivSearchAPI, PubMedSearchAPI, SemanticScholarSearchAPI,
                        SearXNGSearchAPI)


class _Respuesta:
    def __init__(self, datos=None, contenido=b""):
        self._datos = datos
        self.content = contenido

    def raise_for_status(self):
        return None

    def json(self):
        if isinstance(self._datos, Exception):
            raise self._datos
        return self._datos


class TestConectores(unittest.TestCase):
    def test_searxng_filtra_urls_y_valida_privado(self):
        respuesta = _Respuesta({"results": [
            {"title": "Público", "url": "https://example.com/a", "content": "A"},
            {"title": "Privado", "url": "http://127.0.0.1/b", "content": "B"},
        ]})
        with patch("web_search.requests.get", return_value=respuesta) as get:
            resultados = SearXNGSearchAPI("https://search.example.com").search("solar", 5)
        self.assertEqual(len(resultados), 1)
        self.assertEqual(resultados[0]["source"], "searxng")
        self.assertEqual(get.call_args.kwargs["params"]["q"], "solar")
        with self.assertRaisesRegex(ValueError, "allow_private"):
            SearXNGSearchAPI("http://localhost:8080")
        local = SearXNGSearchAPI("http://localhost:8080", allow_private=True)
        self.assertEqual(local.base_url, "http://localhost:8080")

    def test_arxiv_parsea_atom(self):
        xml = b"""<feed xmlns='http://www.w3.org/2005/Atom'><entry>
        <id>http://arxiv.org/abs/1234.5678</id><title> Fusion research </title>
        <summary> Evidence about fusion. </summary></entry></feed>"""
        with patch("web_search.requests.get", return_value=_Respuesta(contenido=xml)):
            resultados = ArxivSearchAPI().search("fusion", 1)
        self.assertEqual(resultados[0]["url"], "https://arxiv.org/abs/1234.5678")
        self.assertEqual(resultados[0]["title"], "Fusion research")
        self.assertEqual(resultados[0]["source"], "arxiv")

    def test_pubmed_realiza_dos_llamadas(self):
        respuestas = iter([
            _Respuesta({"esearchresult": {"idlist": ["123"]}}),
            _Respuesta({"result": {"123": {
                "title": "Artículo", "pubdate": "2026", "source": "Journal",
                "authors": [{"name": "Autor"}],
            }}}),
        ])
        with patch("web_search.requests.get", side_effect=lambda *a, **k: next(respuestas)) as get:
            resultados = PubMedSearchAPI().search("cancer", 1)
        self.assertEqual(get.call_count, 2)
        self.assertEqual(resultados[0]["url"], "https://pubmed.ncbi.nlm.nih.gov/123/")
        self.assertIn("Autor", resultados[0]["snippet"])

    def test_semantic_scholar_forma_y_campos(self):
        respuesta = _Respuesta({"data": [{
            "paperId": "abc", "title": "Paper", "url": "https://example.com/paper",
            "abstract": "Resumen", "year": 2025, "authors": [{"name": "A"}],
        }]})
        with patch("web_search.requests.get", return_value=respuesta) as get:
            resultados = SemanticScholarSearchAPI().search("quantum", 1)
        self.assertEqual(resultados[0]["source"], "semantic_scholar")
        self.assertIn("Resumen", resultados[0]["snippet"])
        self.assertIn("abstract", get.call_args.kwargs["params"]["fields"])

    def test_json_invalido_es_error_explicito(self):
        with patch("web_search.requests.get", return_value=_Respuesta(ValueError("no json"))):
            with self.assertRaisesRegex(RuntimeError, "no JSON"):
                SemanticScholarSearchAPI().search("quantum")


if __name__ == "__main__":
    unittest.main()
