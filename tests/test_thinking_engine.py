"""Tests de thinking_engine.py: ciclo de pasos, validación, confianza y decisión."""

import unittest

from deep_research_system import MockLLM
from tests.helpers import StubLLM
from thinking_engine import StepThinkingEngine


class TinyEngine(StepThinkingEngine):
    """Motor mínimo de 2 pasos para ejercitar el ciclo común (SIMULADO)."""

    def _step_builders(self):
        return [
            ("uno", lambda o: "paso 1"),
            ("dos", lambda o: "paso 2"),
        ]

    def _render_thought(self, steps):
        return "thought:" + ",".join(name for name, _ in steps)


class TestAbstractBase(unittest.TestCase):
    def test_no_instanciable_directamente(self):
        with self.assertRaises(TypeError):
            StepThinkingEngine()


class TestValidateStep(unittest.TestCase):
    def test_rechaza_vacios_y_plantillas(self):
        casos_invalidos = ["", "   ", "abc", "{}", "...", "12345-67890_()"]
        for contenido in casos_invalidos:
            with self.subTest(contenido=contenido):
                self.assertFalse(StepThinkingEngine.validate_step(contenido))

    def test_acepta_contenido_sustancial(self):
        valido = "Respuesta con contenido real y suficientemente sustancial"
        self.assertTrue(StepThinkingEngine.validate_step(valido))

    def test_no_veta_etc_ni_puntos_suspensivos_con_contenido(self):
        texto = ("Análisis detallado con variables, supuestos, etc. y "
                 "puntos suspensivos ... dentro de una respuesta legítima")
        self.assertTrue(StepThinkingEngine.validate_step(texto))


class TestComputeConfidence(unittest.TestCase):
    def test_sin_pasos_es_cero(self):
        self.assertEqual(StepThinkingEngine._compute_confidence([]), 0.0)

    def test_proporcion_de_pasos_con_contenido(self):
        steps = [("a", "contenido"), ("b", ""), ("c", "más"), ("d", "  ")]
        self.assertEqual(StepThinkingEngine._compute_confidence(steps), 0.5)

    def test_todos_llenos_es_uno(self):
        steps = [("a", "x"), ("b", "y")]
        self.assertEqual(StepThinkingEngine._compute_confidence(steps), 1.0)


class TestExtractDecision(unittest.TestCase):
    def test_menos_de_cinco_pasos_devuelve_none(self):
        steps = [("a", "x"), ("b", "y"), ("c", "z"), ("d", "w")]
        self.assertIsNone(StepThinkingEngine._extract_decision(steps))

    def test_cinco_pasos_usa_el_ultimo_con_contenido(self):
        steps = [("a", "x"), ("b", "y"), ("c", "z"), ("d", "w"), ("e", "v")]
        self.assertEqual(
            StepThinkingEngine._extract_decision(steps), "decision_from_e"
        )

    def test_ultimo_vacio_usa_el_anterior_con_contenido(self):
        steps = [("a", "x"), ("b", "y"), ("c", "z"), ("d", "w"), ("e", "")]
        self.assertEqual(
            StepThinkingEngine._extract_decision(steps), "decision_from_d"
        )

    def test_todos_vacios_devuelve_none(self):
        steps = [("a", ""), ("b", ""), ("c", ""), ("d", ""), ("e", "  ")]
        self.assertIsNone(StepThinkingEngine._extract_decision(steps))


class TestRunCycle(unittest.TestCase):
    CLAVES = {"thought", "decision", "confidence", "valid",
              "invalid_steps", "steps", "step_count", "error"}

    def test_ciclo_completo_valido(self):
        engine = TinyEngine(llm_provider=StubLLM(lambda p: "contenido " + p))
        result = engine.think("entrada")
        self.assertEqual(set(result), self.CLAVES)
        self.assertTrue(result["valid"])
        self.assertEqual(result["step_count"], 2)
        self.assertEqual(result["invalid_steps"], [])
        self.assertIsNone(result["error"])
        self.assertEqual(result["confidence"], 1.0)
        self.assertIsNone(result["decision"])  # menos de 5 pasos
        self.assertEqual(result["thought"], "thought:uno,dos")
        self.assertEqual([name for name, _ in result["steps"]], ["uno", "dos"])

    def test_paso_invalido_detiene_el_ciclo(self):
        def responder(prompt):
            return "" if "paso 2" in prompt else "contenido válido y largo"

        engine = TinyEngine(llm_provider=StubLLM(responder))
        result = engine.think("entrada")
        self.assertFalse(result["valid"])
        self.assertEqual(result["invalid_steps"], ["dos"])
        self.assertEqual(result["step_count"], 2)
        self.assertEqual(result["error"], "Paso inválido: dos")
        self.assertEqual(result["confidence"], 0.5)

    def test_sin_proveedor_usa_mock_llm_offline(self):
        engine = TinyEngine(llm_provider=None)
        result = engine.think("entrada")
        self.assertIsInstance(engine.llm, MockLLM)
        self.assertTrue(result["valid"])

    def test_think_reinicia_step_count(self):
        engine = TinyEngine(llm_provider=StubLLM(lambda p: "contenido " + p))
        engine.think("primera")
        self.assertEqual(engine.step_count, 2)
        engine.think("segunda")
        self.assertEqual(engine.step_count, 2)

    def test_context_llega_a_los_builders(self):
        capturado = {}

        class CtxEngine(TinyEngine):
            def _step_builders(self):
                def builder(o):
                    capturado.update(o["context"])
                    return "paso 1"
                return [("uno", builder)]

        engine = CtxEngine(llm_provider=StubLLM(lambda p: "contenido " + p))
        engine.think("entrada", context={"clave": "valor"})
        self.assertEqual(capturado, {"clave": "valor"})


if __name__ == "__main__":
    unittest.main()
