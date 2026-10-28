"""Tests del arnés del benchmark factual (offline, LLMs falsos declarados).

El arnés debe discriminar: un evaluador perfecto da 1.0 y un alucinador que
dice «supported» a todo produce exactamente los falsos verificados esperados.
Los LLM de estos tests son SIMULADOS (regla propia 4).
"""

import json
import re
import unittest

from tests.benchmarks import factual


class _LLMFijo:
    """LLM falso: lee el claim de la línea `Claim:` del prompt y responde."""

    def __init__(self, veredictos):
        self.veredictos = veredictos  # {claim: verdict} o constante str

    def generate(self, prompt, model=None, **kwargs):
        veredicto = "not_addressed"
        if isinstance(self.veredictos, str):
            veredicto = self.veredictos
        else:
            coincidencia = re.search(r"^Claim: (.*)$", prompt, re.M)
            claim = coincidencia.group(1).strip() if coincidencia else ""
            veredicto = self.veredictos.get(claim, "not_addressed")
        return json.dumps({"verdict": veredicto, "credibility": 0.9,
                           "confidence": 0.9, "reasoning": "falso"})


class TestBenchmarkFactual(unittest.TestCase):
    def test_el_conjunto_es_equilibrado_y_sin_duplicados(self):
        self.assertEqual(len(factual.CASOS), 30)
        por_categoria = {c: sum(1 for caso in factual.CASOS
                                if caso["categoria"] == c)
                         for c in factual.CATEGORIAS}
        self.assertEqual(por_categoria,
                         {"supported": 10, "contradicted": 10,
                          "insufficient": 10})
        claims = [caso["claim"] for caso in factual.CASOS]
        self.assertEqual(len(claims), len(set(claims)))

    def test_evaluador_perfecto_da_exactitud_1_y_abstencion_1(self):
        veredictos = {caso["claim"]: factual.esperado_de(caso)
                      for caso in factual.CASOS}
        resultado = factual.ejecutar(_LLMFijo(veredictos))
        metricas = resultado["metricas"]
        self.assertEqual(metricas["exactitud"], 1.0)
        self.assertEqual(metricas["falsos_verificados"], 0)
        self.assertEqual(metricas["tasa_abstencion"], 1.0)
        self.assertNotIn("simulado", resultado["modo"])

    def test_alucinador_que_dice_supported_produce_los_falsos_esperados(self):
        resultado = factual.ejecutar(_LLMFijo("supported"))
        metricas = resultado["metricas"]
        self.assertEqual(metricas["exactitud"], round(10 / 30, 3))
        # Los 20 casos contradicted/insufficient presentados como respaldo.
        self.assertEqual(metricas["falsos_verificados"], 20)
        self.assertEqual(metricas["tasa_abstencion"], 0.0)

    def test_modo_simulado_se_declara(self):
        resultado = factual.ejecutar()
        self.assertIn("simulado", resultado["modo"])
        self.assertIn("no mide calidad real", resultado["modo"])

    def test_metricas_con_entradas_vacias_no_revientan(self):
        metricas = factual.metricas([], [])
        self.assertIsNone(metricas["exactitud"])
        self.assertIsNone(metricas["tasa_abstencion"])


if __name__ == "__main__":
    unittest.main()
