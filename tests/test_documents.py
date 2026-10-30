"""Pruebas offline de contenido completo y recuperación documental."""

import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path

import requests

from documents import (CompositeSearchAPI, FullTextSearchAPI, LocalDocumentSearchAPI,
                       PassageIndex, load_document, load_documents)
from tests.helpers import StubSearch


def _pdf_minimo(texto: str) -> bytes:
    objetos = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        None,
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    contenido = f"BT /F1 12 Tf 72 720 Td ({texto}) Tj ET"
    objetos[3] = f"<< /Length {len(contenido)} >>\nstream\n{contenido}\nendstream"
    partes = ["%PDF-1.4\n"]
    offsets = []
    for numero, objeto in enumerate(objetos, start=1):
        offsets.append(len("".join(partes).encode("latin-1")))
        partes.append(f"{numero} 0 obj\n{objeto}\nendobj\n")
    xref = len("".join(partes).encode("latin-1"))
    partes.append("xref\n0 6\n0000000000 65535 f \n")
    for offset in offsets:
        partes.append(f"{offset:010d} 00000 n \n")
    partes.append(f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n")
    return "".join(partes).encode("latin-1")


class _Respuesta:
    def __init__(self, data=b"<p>contenido</p>", status=200, headers=None):
        self._data = data
        self.status_code = status
        self.headers = headers or {"Content-Type": "text/html"}
        self.encoding = "utf-8"
        self.closed = False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def iter_content(self, size):
        for inicio in range(0, len(self._data), size):
            yield self._data[inicio:inicio + size]

    def close(self):
        self.closed = True


class TestDocumentosLocales(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)

    def test_texto_html_csv_y_trazabilidad(self):
        (self.raiz / "nota.md").write_text("Investigación sobre energía solar", encoding="utf-8")
        (self.raiz / "web.html").write_text(
            "<script>ignorar()</script><p>Energía geotérmica</p>", encoding="utf-8")
        (self.raiz / "datos.csv").write_text("tema,valor\nsolar,renovable\n", encoding="utf-8")

        resultados = load_documents([str(self.raiz)])

        self.assertEqual(len(resultados), 3)
        self.assertTrue(all(r["source"] == "local-document" for r in resultados))
        self.assertTrue(all(len(r["sha256"]) == 64 for r in resultados))
        self.assertTrue(all(r["url"].startswith("document://") for r in resultados))
        self.assertIn("Línea 2", next(r for r in resultados if "csv" in r["url"])["snippet"])
        self.assertNotIn("ignorar", next(r for r in resultados if "html" in r["url"])["snippet"])

    def test_office_docx_pptx_xlsx(self):
        with zipfile.ZipFile(self.raiz / "informe.docx", "w") as archivo:
            archivo.writestr("word/document.xml",
                             "<w:document xmlns:w='http://schemas.openxmlformats.org/"
                             "wordprocessingml/2006/main'><w:body><w:p><w:r><w:t>"
                             "Texto DOCX verificable</w:t></w:r></w:p></w:body></w:document>")
        with zipfile.ZipFile(self.raiz / "slides.pptx", "w") as archivo:
            archivo.writestr("ppt/slides/slide1.xml",
                             "<p:sld xmlns:p='http://schemas.openxmlformats.org/presentationml/2006/main' "
                             "xmlns:a='http://schemas.openxmlformats.org/drawingml/2006/main'>"
                             "<p:cSld><a:t>Texto PPTX verificable</a:t></p:cSld></p:sld>")
        with zipfile.ZipFile(self.raiz / "datos.xlsx", "w") as archivo:
            archivo.writestr("xl/sharedStrings.xml",
                             "<sst xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'>"
                             "<si><t>Texto XLSX verificable</t></si></sst>")
            archivo.writestr("xl/worksheets/sheet1.xml",
                             "<worksheet xmlns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'>"
                             "<sheetData><row><c r='A1' t='s'><v>0</v></c></row></sheetData></worksheet>")

        docx = load_document(str(self.raiz / "informe.docx"))
        pptx = load_document(str(self.raiz / "slides.pptx"))
        xlsx = load_document(str(self.raiz / "datos.xlsx"))

        self.assertIn("DOCX", docx[0]["snippet"])
        self.assertIn("párrafo 1", docx[0]["location"])
        self.assertIn("PPTX", pptx[0]["snippet"])
        self.assertIn("diapositiva 1", pptx[0]["location"])
        self.assertIn("XLSX", xlsx[0]["snippet"])
        self.assertIn("A1", xlsx[0]["snippet"])

    def test_pdf_real_o_declara_dependencia(self):
        ruta = self.raiz / "fusion.pdf"
        ruta.write_bytes(_pdf_minimo("Energia de fusion controlada"))
        if importlib.util.find_spec("pypdf") is None:
            with self.assertRaisesRegex(RuntimeError, "requiere la dependencia"):
                load_document(str(ruta))
            return
        resultado = load_document(str(ruta))
        self.assertIn("fusion", resultado[0]["snippet"])
        self.assertIn("página 1", resultado[0]["location"])

    def test_documento_vacio_y_formato_no_soportado_fallan(self):
        (self.raiz / "vacio.md").write_text(" ", encoding="utf-8")
        (self.raiz / "binario.bin").write_bytes(b"abc")
        with self.assertRaisesRegex(RuntimeError, "sin texto extraíble"):
            load_document(str(self.raiz / "vacio.md"))
        with self.assertRaisesRegex(ValueError, "Formato no soportado"):
            load_document(str(self.raiz / "binario.bin"))

    def test_ranking_hibrido_es_determinista_y_trazable(self):
        pasajes = [
            {"title": "Solar", "url": "doc://solar", "snippet": "Paneles y energía solar"},
            {"title": "Motor", "url": "doc://motor", "snippet": "Motor de combustión interna"},
        ]
        indice = PassageIndex(pasajes)
        primero = indice.search("energía solar", 1)
        segundo = indice.search("energía solar", 1)
        self.assertEqual(primero, segundo)
        self.assertEqual(primero[0]["url"], "doc://solar")
        self.assertEqual(primero[0]["retrieval"], "bm25+vector-cosine")
        self.assertGreater(primero[0]["relevance_score"], 0)
        self.assertEqual(indice.search("", 2), [])
        self.assertEqual(indice.search("solar", 0), [])

    def test_local_search_y_composite_deduplican(self):
        (self.raiz / "solar.txt").write_text("Energía solar distribuida", encoding="utf-8")
        local = LocalDocumentSearchAPI([str(self.raiz / "solar.txt")])
        combinado = CompositeSearchAPI([local, local])
        resultados = combinado.search("solar", 4)
        self.assertEqual(len(resultados), 1)
        self.assertEqual(resultados[0]["source"], "local-document")


class TestContenidoWebCompleto(unittest.TestCase):
    def _api(self, respuestas, data=None, max_bytes=1000):
        buscador = StubSearch([{
            "title": "Fuente", "url": "https://example.com/articulo",
            "snippet": "snippet corto", "source": "stub",
        }])
        api = FullTextSearchAPI(buscador, max_bytes=max_bytes)
        api._get = lambda url: respuestas.pop(0)
        return api

    def test_extrae_texto_completo_sin_scripts(self):
        data = b"<script>secreto()</script><p>Energia solar y paneles fotovoltaicos</p>"
        api = self._api([_Respuesta(data)])
        resultados = api.search("energía solar", 2)
        self.assertIn("paneles fotovoltaicos", resultados[0]["snippet"])
        self.assertNotIn("secreto", resultados[0]["snippet"])
        self.assertTrue(resultados[0]["source"].startswith("fulltext:"))
        self.assertEqual(api.errors, [])

    def test_redireccion_actualiza_url_final(self):
        api = self._api([
            _Respuesta(status=302, headers={"Location": "https://example.com/final"}),
            _Respuesta(b"<p>Contenido final</p>"),
        ])
        resultados = api.search("contenido", 1)
        self.assertEqual(resultados[0]["url"], "https://example.com/final")

    def test_rechaza_host_privado_antes_de_red(self):
        api = FullTextSearchAPI(StubSearch([]))
        with self.assertRaisesRegex(ValueError, "no pública"):
            api._fetch("http://127.0.0.1/privado")

    def test_error_total_se_reporta_no_cae_a_snippet(self):
        api = FullTextSearchAPI(StubSearch([{
            "title": "Fuente", "url": "https://example.com", "snippet": "respaldo",
        }]))
        def fallar(url):
            raise requests.ConnectionError("sin red")
        api._get = fallar
        with self.assertRaisesRegex(RuntimeError, "contenido completo"):
            api.search("pregunta")
        self.assertEqual(len(api.errors), 1)

    def test_limite_de_bytes_es_fallo_visible(self):
        api = self._api([_Respuesta(b"<p>demasiado contenido</p>")], max_bytes=4)
        with self.assertRaisesRegex(RuntimeError, "contenido completo"):
            api.search("contenido")
        self.assertIn("supera", api.errors[0])


if __name__ == "__main__":
    unittest.main()
