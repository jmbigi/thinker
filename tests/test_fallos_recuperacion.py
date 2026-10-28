"""Fallos de recuperación: JSON inválido/truncado y respuesta vacía no deben
convertirse nunca en "verificado" (offline, StubLLM/StubSearch).
"""

import unittest

from deep_research_system import _parse_json_response
from evaluar_proyecto import sintetizar_con_llm
from tests.helpers import StubLLM

INFORME_MINIMO = {
    "ruta": "/tmp/proyecto",
    "archivos_python": 1,
    "lineas_python": 1,
    "cobertura": {},
    "dimensiones": {
        "calidad": {"puntuacion": 1.0, "criterios": {},
                    "hallazgos": [], "notas": []},
    },
}


class TestSintesisConFallosDeParseo(unittest.TestCase):
    def _sintetizar(self, respuesta):
        return sintetizar_con_llm(INFORME_MINIMO,
                                  StubLLM(lambda p: respuesta))

    def test_texto_sin_json_eleva_value_error(self):
        with self.assertRaises(ValueError):
            self._sintetizar("esto no es JSON en absoluto")

    def test_respuesta_vacia_eleva_value_error(self):
        with self.assertRaises(ValueError):
            self._sintetizar("")

    def test_json_que_no_es_objeto_ni_array_eleva(self):
        for crudo in ('"solo un string"', "42", "true", "null"):
            with self.subTest(crudo=crudo):
                with self.assertRaises(ValueError):
                    self._sintetizar(crudo)

    def test_propuestas_que_no_es_lista_eleva(self):
        with self.assertRaises(ValueError):
            self._sintetizar('{"propuestas": "no es lista"}')

    def test_objeto_valido_con_propuestas_vacias_es_aceptado(self):
        sintesis = self._sintetizar(
            '{"propuestas": [], "preguntas_abiertas": []}')
        self.assertEqual(sintesis["propuestas"], [])
        self.assertEqual(sintesis["preguntas_abiertas"], [])
        self.assertEqual(sintesis["sin_respaldo"], 0)


class TestParseoDelVerificador(unittest.TestCase):
    def test_respuesta_truncada_no_produce_json(self):
        with self.assertRaises(Exception):
            _parse_json_response('{"veredicto": "supported", "evidencia": [1, 2')

    def test_bloque_markdown_se_extrae(self):
        self.assertEqual(_parse_json_response("```json\n{\"ok\": 1}\n```"),
                         {"ok": 1})

    def test_texto_alrededor_encuentra_el_primer_json_decodificable(self):
        self.assertEqual(
            _parse_json_response('intro {"a": 1} cierre'), {"a": 1})

    def test_vacio_eleva_en_vez_de_devolver_none_silencioso(self):
        with self.assertRaises(Exception):
            _parse_json_response("")


if __name__ == "__main__":
    unittest.main()
