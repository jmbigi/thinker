"""Tests de las dimensiones separadas de calidad de fuentes (offline)."""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from source_quality import (_actualidad, _claims_para_fuente, _host,
                            evaluar_fuentes)


class _DateTimeFijo(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 10, 31, 12, tzinfo=tz)


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


class TestRobustezFuentes(unittest.TestCase):
    def test_fecha_futura_no_recibe_actualidad_maxima(self):
        fecha = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        actualidad = evaluar_fuentes([{
            "url": "https://example.org", "snippet": "x", "published_at": fecha,
        }])["fuentes"][0]["dimensiones"]["actualidad"]
        self.assertIsNone(actualidad["valor"])
        self.assertLess(actualidad["dias"], 0)
        self.assertIn("fecha futura", actualidad["detalle"])

    def test_url_malformada_no_interrumpe_evaluacion(self):
        resultado = evaluar_fuentes([{"url": "https://[::1", "snippet": "texto"}])
        self.assertEqual(resultado["total"], 1)
        self.assertIsNone(resultado["fuentes"][0]["dimensiones"]["autoridad"]["valor"])

    def test_claim_sin_fuente_no_se_asocia_por_identificadores_ausentes(self):
        resultado = evaluar_fuentes(
            [{"url": "https://example.org/doc", "snippet": "Motor diésel."}],
            claims=[{"claim": "Motor diésel."}],
        )
        soporte = resultado["fuentes"][0]["dimensiones"]["soporte"]
        self.assertIsNone(soporte["valor"])
        self.assertNotIn("claims_evaluados", soporte)

        asociado = evaluar_fuentes(
            [{"id": 7, "url": "https://example.org/doc", "snippet": "Motor diésel."}],
            claims=[{"claim": "Motor diésel.", "source_id": 7}],
        )
        self.assertEqual(
            asociado["fuentes"][0]["dimensiones"]["soporte"]["claims_evaluados"], 1)

    def test_parametros_de_contenido_no_son_rastreadores(self):
        sources = [
            {"url": "https://example.org/doc?reference=alpha", "snippet": "Energía solar."},
            {"url": "https://example.org/doc?reference=beta", "snippet": "Motor diésel."},
        ]
        resultado = evaluar_fuentes(sources, claims=[{
            "claim": "Motor diésel.", "source_url": sources[1]["url"],
        }])
        self.assertEqual(resultado["grupos_duplicados"], [])
        self.assertIsNone(resultado["fuentes"][0]["dimensiones"]["soporte"]["valor"])
        self.assertEqual(resultado["fuentes"][1]["dimensiones"]["soporte"]["valor"], 1.0)

    def test_contrato_actualidad_en_bordes(self):
        self.assertEqual(_actualidad({}), {
            "valor": None, "dias": None, "metodo": "fecha declarada",
            "detalle": "sin fecha legible: no evaluable",
        })
        with patch("source_quality.datetime", _DateTimeFijo):
            self.assertEqual(_actualidad({"published_at": "2026-11-01T12:00:00Z"}), {
                "valor": None, "dias": -1, "metodo": "fecha declarada",
                "detalle": "fecha futura: no evaluable como vigencia",
            })
            casos = [
                (0, 1.0, "<= 30 días"), (30, 1.0, "<= 30 días"),
                (31, 0.8, "<= 1 año"), (365, 0.8, "<= 1 año"),
                (366, 0.5, "<= 5 años"), (1825, 0.5, "<= 5 años"),
                (1826, 0.2, "> 5 años"),
            ]
            for dias, valor, detalle in casos:
                with self.subTest(dias=dias):
                    fecha = (datetime(2026, 10, 31, 12, tzinfo=timezone.utc)
                             - timedelta(days=dias)).isoformat()
                    self.assertEqual(_actualidad({"published_at": fecha}), {
                        "valor": valor, "dias": dias, "metodo": "fecha declarada",
                        "detalle": detalle,
                    })

    def test_contrato_asociacion_claims(self):
        source = {"id": 7, "url": "https://example.org/doc?x=1"}
        claims = [
            "no es un mapa",
            {"claim": ""},
            {"claim": "por URL alternativa",
             "url": "https://www.example.org/doc/?x=1&utm_source=a"},
            {"claim": "por ID URL", "source_id": "https://example.org/doc?x=1"},
            {"claim": "por ID numérico", "source_id": 7},
            {"claim": "URL distinta", "source_url": "https://other.invalid/doc"},
            {"claim": "ID URL distinto", "source_id": "https://other.invalid/doc"},
            {"claim": "sin asociación"},
        ]
        self.assertEqual(_claims_para_fuente(source, claims), [
            "por URL alternativa", "por ID URL", "por ID numérico",
        ])
        self.assertEqual(_claims_para_fuente({"id": 0}, [
            {"claim": "cero", "source_id": 0},
        ]), ["cero"])
        self.assertEqual(_claims_para_fuente(source, None), [])
        self.assertEqual(_claims_para_fuente({}, [
            {"claim": "ID relativo", "source_id": "XXXX"},
        ]), [])
        self.assertEqual(_claims_para_fuente({"id": 7}, [
            {"claim": "", "source_id": 7},
        ]), [])
        self.assertEqual(_claims_para_fuente({"url": "XXXX"}, [
            {"claim": "sin ID"},
        ]), [])

    def test_host_invalido_o_relativo_no_se_inventa(self):
        for url in (None, 0, "", " ", "ruta/relativa"):
            with self.subTest(url=url):
                self.assertEqual(_host(url), "")


if __name__ == "__main__":
    unittest.main()
