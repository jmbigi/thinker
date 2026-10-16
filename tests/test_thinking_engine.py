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


class TestEvaluacionHeuristica(unittest.TestCase):
    """Valores EXACTOS de la heurística: sin ellos sobrevivían 64 mutantes."""

    def setUp(self):
        self.engine = TinyToT(llm_provider=None)

    def test_valores_exactos(self):
        casos = [
            ("a" * 100, {}, 0.54),                        # base 0.5 + longitud
            ("a" * 500, {}, 0.70),                        # longitud en el tope
            ("a" * 1000, {}, 0.70),                       # por encima del tope
            ("porque " + "b" * 20, {}, 0.56),             # 1 marcador
            ("porque además " + "c" * 7, {}, 0.61),       # 2 marcadores
            ("porque dado que así que puesto que " + "d" * 465, {}, 0.85),  # 4 -> tope
            ("alfa bravo charlie delta",
             {"prompt": "alfa bravo charlie delta"}, 0.66),  # solapamiento total
            # "alfa" (4 letras) queda fuera del filtro len(w) > 4: la intersección
            # es {bravo} sobre 3 palabras previas -> 1/3
            ("alfa bravo", {"prompt": "alfa bravo charlie delta"}, 0.57),
            ("a", {"prompt": "a b c"}, 0.50),             # sin palabras largas
            ("a", {"dato": 42}, 0.50),                    # sin valores str
            ("a", {}, 0.50),                              # outputs vacío
        ]
        for contenido, outputs, esperado in casos:
            with self.subTest(contenido=contenido[:24], esperado=esperado):
                self.assertEqual(
                    self.engine._evaluate_state_heuristic(contenido, "uno", outputs),
                    esperado)


class TestJuezLLM(unittest.TestCase):
    def setUp(self):
        self.engine = TinyToT(llm_provider=None)

    def test_ponderacion_exacta(self):
        casos = [
            ('{"relevance": 8, "depth": 6, "coherence": 4, "reasoning": 10}', 0.73),
            ('{"relevance": 10, "depth": 10, "coherence": 10, "reasoning": 10}', 1.0),
            ('{"relevance": 0, "depth": 0, "coherence": 0, "reasoning": 0}', 0.0),
            ('{"relevance": 10}', 0.25),                  # claves ausentes -> 0
            ('{"relevance": 20, "depth": 20, "coherence": 20, "reasoning": 20}', 1.0),
        ]
        for respuesta, esperado in casos:
            with self.subTest(respuesta=respuesta):
                self.engine.llm = StubLLM(lambda p, r=respuesta: r)
                self.assertEqual(
                    self.engine._evaluate_state_llm("contenido", "uno", {}), esperado)

    def test_json_embebido_en_texto(self):
        respuesta = ('bla {"relevance": 10, "depth": 10, "coherence": 10, '
                     '"reasoning": 10} fin')
        self.engine.llm = StubLLM(lambda p: respuesta)

        self.assertEqual(self.engine._evaluate_state_llm("contenido", "uno", {}), 1.0)

    def test_sin_json_eleva_value_error(self):
        self.engine.llm = StubLLM(lambda p: "esto no es JSON")

        with self.assertRaises(ValueError):
            self.engine._evaluate_state_llm("contenido", "uno", {})

    def test_prompt_incluye_paso_contenido_y_previos(self):
        capturado = {}

        def responder(prompt):
            capturado["prompt"] = prompt
            return '{"relevance": 5, "depth": 5, "coherence": 5, "reasoning": 5}'

        self.engine.llm = StubLLM(responder)
        self.engine._evaluate_state_llm(
            "contenido evaluado", "dos",
            {"uno": "paso previo largo", "prompt": "pregunta", "context": {}})

        prompt = capturado["prompt"]
        self.assertIn("PASO ACTUAL: dos", prompt)
        self.assertIn("contenido evaluado", prompt)
        self.assertIn("--- uno ---", prompt)
        self.assertIn("paso previo largo", prompt)
        self.assertNotIn("--- prompt ---", prompt)
        self.assertNotIn("--- context ---", prompt)


class TestToTEngineDetalle(unittest.TestCase):
    def test_valores_por_defecto(self):
        engine = TinyToT(llm_provider=None)

        self.assertEqual(engine.branch_factor, 3)
        self.assertEqual(engine.beam_width, 3)
        self.assertEqual(engine.search_strategy, "beam")
        self.assertEqual(engine.min_score_threshold, 0.3)
        self.assertEqual(engine.max_steps, 7)
        self.assertEqual(engine.max_depth, 7)
        self.assertIsNone(engine._root)
        self.assertEqual(engine._all_nodes, [])

    def test_max_depth_limita_el_camino(self):
        engine = TinyToT(llm_provider=StubLLM(lambda p: "contenido sustancial y largo"),
                         branch_factor=1, max_depth=1)
        result = engine.think_tot("prueba")

        self.assertEqual([n for n, _ in result["best_path"]], ["uno"])

    def test_todo_podado_vuelve_a_la_raiz(self):
        engine = TinyToT(llm_provider=StubLLM(lambda p: "contenido sustancial y largo"),
                         branch_factor=2, min_score_threshold=0.95)
        result = engine.think_tot("prueba")

        self.assertEqual(result["best_path"], [])
        self.assertEqual(result["best_score"], 1.0)   # la raíz vale 1.0
        self.assertEqual(result["pruned_nodes"], 2)
        self.assertEqual(result["explored_nodes"], 3)
        self.assertEqual(result["step_count"], 0)

    def test_branch_factor_crea_ramas_con_variantes(self):
        def responder(prompt):
            if "evaluador experto" in prompt:
                return '{"relevance": 5, "depth": 5, "coherence": 5, "reasoning": 5}'
            return "contenido sustancial y largo"

        llm = StubLLM(responder)
        engine = TinyToT(llm_provider=llm, branch_factor=3, beam_width=1)
        result = engine.think_tot("prueba")

        self.assertEqual(len(engine._root.children), 3)
        self.assertEqual([c.metadata["variant"] for c in engine._root.children],
                         [1, 2, 3])
        self.assertTrue(all(c.depth == 1 for c in engine._root.children))
        self.assertEqual(result["explored_nodes"], 7)   # raíz + 3 + 3

        generados = [p for p in llm.prompts if p.startswith("paso 1")]
        self.assertEqual(len(generados), 3)
        self.assertNotIn("Variante", generados[0])
        self.assertIn("[Variante 2/3", generados[1])
        self.assertIn("[Variante 3/3", generados[2])

    def test_las_ramas_reciben_prompt_y_contexto(self):
        capturado = []

        class Captura(TinyToT):
            def _step_builders(self):
                def uno(o):
                    capturado.append(dict(o))
                    return "paso 1"
                return [("uno", uno)]

        engine = Captura(llm_provider=StubLLM(lambda p: "contenido sustancial y largo"),
                         branch_factor=1)
        engine.think_tot("mi pregunta", context={"clave": "valor"})

        self.assertEqual(capturado[0]["prompt"], "mi pregunta")
        self.assertEqual(capturado[0]["context"], {"clave": "valor"})
        self.assertNotIn("uno", capturado[0])


if __name__ == "__main__":
    unittest.main()