"""Tests de thinking_engine.py: ciclo de pasos, validación, confianza y decisión."""

import io
import unittest
from contextlib import redirect_stderr

from deep_research_system import MockLLM
from tests.helpers import StubLLM
from thinking_engine import StepThinkingEngine, ToTEngine


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


class TinyToT(ToTEngine):
    """Motor ToT mínimo de 2 pasos para ejercitar ramificación y poda (SIMULADO)."""

    def _step_builders(self):
        return [
            ("uno", lambda o: "paso 1"),
            ("dos", lambda o: "paso 2"),
        ]

    def _render_thought(self, steps):
        return "tot:" + ",".join(name for name, _ in steps)


class TestToTEngine(unittest.TestCase):
    def test_think_tot_devuelve_arbol_y_metricas(self):
        engine = TinyToT(llm_provider=StubLLM(lambda p: "contenido sustancial y largo"),
                         branch_factor=2, beam_width=2)
        result = engine.think_tot("prueba")

        for clave in ("best_path", "explored_nodes", "pruned_nodes", "best_score"):
            self.assertIn(clave, result)
        self.assertEqual([name for name, _ in result["best_path"]], ["uno", "dos"])
        # raíz + 2 ramas del primer paso + 4 del segundo
        self.assertEqual(result["explored_nodes"], 7)
        self.assertEqual(len(engine._root.children), 2)

    def test_arbol_solo_se_incluye_si_se_pide(self):
        engine = TinyToT(llm_provider=StubLLM(lambda p: "contenido sustancial y largo"))

        self.assertNotIn("tree", engine.think_tot("prueba"))
        self.assertIn("tree", engine.think_tot("prueba", return_tree=True))

    def test_estrategias_bfs_y_dfs_exploran_el_arbol(self):
        from thinking_engine import SearchStrategy

        for estrategia in (SearchStrategy.BFS, SearchStrategy.DFS):
            with self.subTest(estrategia=estrategia):
                engine = TinyToT(
                    llm_provider=StubLLM(lambda p: "contenido sustancial y largo"),
                    branch_factor=2, beam_width=2, search_strategy=estrategia,
                )
                result = engine.think_tot("prueba")

                self.assertEqual([n for n, _ in result["best_path"]], ["uno", "dos"])
                self.assertGreater(result["explored_nodes"], 0)
                self.assertTrue(result["valid"])

    def test_juez_con_json_usa_su_puntuacion(self):
        def juez(prompt):
            if "evaluador experto" in prompt:
                return '{"relevance": 10, "depth": 10, "coherence": 10, "reasoning": 10}'
            return "contenido sustancial y largo"

        engine = TinyToT(llm_provider=StubLLM(juez), branch_factor=1)
        self.assertEqual(engine.think_tot("prueba")["best_score"], 1.0)

    def test_juez_sin_json_se_reporta_y_usa_heuristica(self):
        def juez(prompt):
            if "evaluador experto" in prompt:
                return "esto no es JSON"
            return "contenido sustancial y largo"

        engine = TinyToT(llm_provider=StubLLM(juez), branch_factor=1)
        capturado = io.StringIO()
        with redirect_stderr(capturado):
            result = engine.think_tot("prueba")

        # El fallo NO se silencia (P1.26) y se degrada a la heurística local.
        self.assertIn("LLM-as-judge falló", capturado.getvalue())
        self.assertGreater(result["best_score"], 0.0)
        self.assertLess(result["best_score"], 1.0)


if __name__ == "__main__":
    unittest.main()
