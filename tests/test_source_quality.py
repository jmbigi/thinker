"""Tests de las dimensiones separadas de calidad de fuentes (offline)."""

import unittest
from datetime import datetime, timedelta, timezone

from source_quality import evaluar_fuentes


class TestAutoridad(unittest.TestCase):
    def _autoridad(self, url):
        return evaluar_fuentes([{"url": url, "snippet": "texto"}])[
            "fuentes"][0]["dimensiones"]["autoridad"]

    def test_dominio_institucional(self):
        self.assertEqual(self._autoridad("https://www.nasa.gov/x")["valor"], 0.9)

    def test_dominio_conocido(self):
        self.assertEqual(self._autoridad("https://es.wikipedia.org/x")["valor"], 0.6)

    def test_red_social(self):
        self.assertEqual(self._autoridad("https://x.com/alguien")["valor"], 0.15)

    def test_dominio_desconocido(self):
        self.assertEqual(self._autoridad("https://ejemplo-raro.test/x")["valor"], 0.3)

    def test_sin_url_no_evaluable(self):
        self.assertIsNone(self._autoridad("")["valor"])


class TestActualidad(unittest.TestCase):
    def _dias(self, dias):
        fecha = (datetime.now(timezone.utc) - timedelta(days=dias)).isoformat()
        return evaluar_fuentes([{"url": "https://example.org", "snippet": "x",
                                 "published_at": fecha}])[
            "fuentes"][0]["dimensiones"]["actualidad"]

    def test_reciente(self):
        self.assertEqual(self._dias(5)["valor"], 1.0)

    def test_antiguo(self):
        self.assertEqual(self._dias(3650)["valor"], 0.2)

    def test_sin_fecha(self):
        resultado = evaluar_fuentes(
            [{"url": "https://example.org", "snippet": "x"}])
        self.assertIsNone(
            resultado["fuentes"][0]["dimensiones"]["actualidad"]["valor"])


class TestDimensionesSeparadas(unittest.TestCase):
    def setUp(self):
        self.sources = [
            {"url": "https://www.example.org/a?utm_source=x", "title": "A",
             "snippet": "La fusión nuclear está en investigación."},
            {"url": "https://example.org/a", "title": "A copia",
             "snippet": "La fusión nuclear está en investigación."},
            {"url": "https://otro.org/b", "title": "B",
             "snippet": "El agua hierve a 100 grados Celsius."},
        ]

    def test_relevancia_y_soporte(self):
        resultado = evaluar_fuentes(
            self.sources, query="fusión nuclear",
            claims=[{"claim": "La fusión nuclear está en investigación.",
                     "source_url": "https://example.org/a"}])
        primera = resultado["fuentes"][0]["dimensiones"]
        self.assertGreater(primera["relevancia"]["valor"], 0.9)
        self.assertEqual(primera["soporte"]["valor"], 1.0)
        self.assertEqual(primera["soporte"]["claims_evaluados"], 1)

    def test_duplicados_por_url_normalizada(self):
        resultado = evaluar_fuentes(self.sources)
        self.assertEqual(len(resultado["grupos_duplicados"]), 1)
        self.assertEqual(resultado["grupos_duplicados"][0]["indices"], [1, 2])
        self.assertEqual(resultado["grupos_independencia"][0]["indices"], [1, 2])
        self.assertEqual(resultado["dominios_unicos"], 2)
        self.assertIn("diversidad", " ".join(resultado["advertencias"]))

    def test_trazabilidad(self):
        resultado = evaluar_fuentes(self.sources)
        self.assertTrue(resultado["fuentes"][0]["dimensiones"]["trazabilidad"]["valor"])
        self.assertIn("url", resultado["fuentes"][0]["dimensiones"]["trazabilidad"]["campos"])

    def test_no_hay_nota_unica(self):
        resultado = evaluar_fuentes(self.sources)
        self.assertIn("no hay una nota única", resultado["nota"])
        self.assertNotIn("puntuacion", resultado)
        self.assertNotIn("global", resultado)

    def test_contradiccion_posible_por_negacion(self):
        resultado = evaluar_fuentes(
            [{"url": "https://example.org/c",
              "snippet": "El agua hierve a 100 grados Celsius."}],
            claims=[{"claim": "El agua no hierve a 100 grados Celsius.",
                     "source_url": "https://example.org/c"}])
        soporte = resultado["fuentes"][0]["dimensiones"]["soporte"]
        self.assertEqual(len(soporte["posible_contradiccion"]), 1)


if __name__ == "__main__":
    unittest.main()
