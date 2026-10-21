"""Tests de thinking_engine.py: ciclo de pasos, validación, confianza y decisión."""

import io
import unittest
from contextlib import redirect_stderr

from deep_research_system import MockLLM
from tests.helpers import StubLLM
from thinking_engine import (SearchStrategy, StepThinkingEngine, ThinkingNode,
                             ToTEngine)


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

    def test_max_steps_acota_el_ciclo(self):
        engine = TinyEngine(llm_provider=StubLLM(lambda p: "contenido " + p),
                            max_steps=1)
        result = engine.think("entrada")
        self.assertTrue(result["valid"])
        self.assertEqual(result["step_count"], 1)
        self.assertEqual([name for name, _ in result["steps"]], ["uno"])

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


class TestCongelacionFases(unittest.TestCase):
    """Phase-chain freeze (piloto): fases inmutables en el ciclo lineal."""

    def test_sin_congelar_no_anade_claves_ni_bloque(self):
        llm = StubLLM(lambda p: "contenido " + p)
        result = TinyEngine(llm_provider=llm).think("entrada")

        self.assertNotIn("fases_congeladas", result)
        self.assertNotIn("FASES CONGELADAS", llm.prompts[1])

    def test_congelar_inyecta_bloque_y_hashes(self):
        llm = StubLLM(lambda p: "contenido " + p)
        result = TinyEngine(llm_provider=llm, congelar_fases=True).think("entrada")

        self.assertNotIn("FASES CONGELADAS", llm.prompts[0])  # paso 1: nada previo
        self.assertIn("FASES CONGELADAS", llm.prompts[1])
        self.assertIn("uno (hash", llm.prompts[1])
        self.assertIn("INMUTABLE", llm.prompts[1])

        fases = result["fases_congeladas"]
        self.assertEqual([f["nombre"] for f in fases], ["uno", "dos"])
        self.assertTrue(all(len(f["hash"]) == 16 for f in fases))
        self.assertTrue(all(f["contenido"] for f in fases))
        self.assertTrue(result["inmutabilidad_verificada"])

    def test_verificar_congelacion_detecta_mutacion(self):
        llm = StubLLM(lambda p: "contenido " + p)
        result = TinyEngine(llm_provider=llm, congelar_fases=True).think("entrada")

        steps = list(result["steps"])
        self.assertTrue(TinyEngine.verificar_congelacion(
            steps, result["fases_congeladas"]))

        steps[0] = ("uno", "contenido alterado por un consumidor")
        self.assertFalse(TinyEngine.verificar_congelacion(
            steps, result["fases_congeladas"]))

    def test_paso_invalido_se_congela_igual_y_detiene(self):
        def responder(prompt):
            return "" if "paso 2" in prompt else "contenido válido y largo"

        result = TinyEngine(llm_provider=StubLLM(responder),
                            congelar_fases=True).think("entrada")

        self.assertFalse(result["valid"])
        self.assertEqual(result["invalid_steps"], ["dos"])
        self.assertEqual([f["nombre"] for f in result["fases_congeladas"]],
                         ["uno", "dos"])
        self.assertTrue(result["inmutabilidad_verificada"])

    def test_tot_declara_que_el_congelado_no_aplica(self):
        error = io.StringIO()
        with redirect_stderr(error):
            result = TinyToT(llm_provider=StubLLM(
                lambda p: "contenido sustancial y largo"),
                branch_factor=2, beam_width=2,
                congelar_fases=True).think_tot("entrada")

        self.assertIn("congelar_fases no aplica a ToT", error.getvalue())
        self.assertEqual(result["congelacion_fases"],
                         "no aplica a ToT (ramas exploratorias)")

    def test_tot_sin_congelar_declara_inactiva(self):
        result = TinyToT(llm_provider=StubLLM(
            lambda p: "contenido sustancial y largo"),
            branch_factor=2, beam_width=2).think_tot("entrada")

        self.assertEqual(result["congelacion_fases"], "inactiva")


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
        # Sin pasos ejecutados NO puede declararse válido (antes: valid=True)
        self.assertFalse(result["valid"])
        self.assertEqual(result["error"],
                         "Ninguna rama superó el umbral de score: sin camino válido")

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
                def dos(o):
                    capturado.append(dict(o))
                    return "paso 2"
                return [("uno", uno), ("dos", dos)]

        engine = Captura(llm_provider=StubLLM(lambda p: "contenido sustancial y largo"),
                         branch_factor=1)
        engine.think_tot("mi pregunta", context={"clave": "valor"})

        # Paso 1: la entrada completa (sin salidas previas)
        self.assertEqual(capturado[0]["prompt"], "mi pregunta")
        self.assertEqual(capturado[0]["context"], {"clave": "valor"})
        self.assertNotIn("uno", capturado[0])
        # Paso 2: prompt y contexto NO se pierden y sí llega el paso previo
        # (antes se construía con prompt='' y context={})
        paso2 = [o for o in capturado if "uno" in o]
        self.assertEqual(len(paso2), 1)
        self.assertEqual(paso2[0]["prompt"], "mi pregunta")
        self.assertEqual(paso2[0]["context"], {"clave": "valor"})
        self.assertEqual(paso2[0]["uno"], "contenido sustancial y largo")


class TestThinkingNode(unittest.TestCase):
    def test_best_child_sin_hijos_es_none(self):
        self.assertIsNone(
            ThinkingNode(content="raíz", step_name="root").best_child())

    def test_best_child_elige_el_de_mayor_score(self):
        padre = ThinkingNode(content="raíz", step_name="root")
        padre.add_child(ThinkingNode(content="bajo", step_name="uno", score=0.2))
        alto = padre.add_child(
            ThinkingNode(content="alto", step_name="dos", score=0.9))

        self.assertIs(padre.best_child(), alto)


class TestCoberturaBFS(unittest.TestCase):
    @staticmethod
    def _llm():
        def responder(prompt):
            if "evaluador experto" in prompt:
                return ('{"relevance": 8, "depth": 8, "coherence": 8, '
                        '"reasoning": 8}')
            return "contenido sustancial y largo"
        return StubLLM(responder)

    def test_contenido_invalido_puntua_cero_sin_llamar_al_juez(self):
        def no_llamar(prompt):
            raise AssertionError("el juez no debe llamarse para contenido inválido")

        engine = TinyToT(llm_provider=StubLLM(no_llamar))

        self.assertEqual(engine._evaluate_state("", "uno", {}), 0.0)
        self.assertEqual(engine._evaluate_state("{}", "uno", {}), 0.0)

    def test_bfs_con_todo_podado_reporta_score_bajo(self):
        engine = TinyToT(llm_provider=self._llm(), branch_factor=2,
                         search_strategy=SearchStrategy.BFS,
                         min_score_threshold=0.95)
        result = engine.think_tot("prueba")

        self.assertFalse(result["valid"])
        self.assertTrue(result["best_path"])   # hay camino, pero puntúa bajo
        self.assertIn("Score bajo:", result["error"])

    def test_bfs_respeta_max_depth(self):
        engine = TinyToT(llm_provider=self._llm(), branch_factor=1,
                         search_strategy=SearchStrategy.BFS, max_depth=1)
        result = engine.think_tot("prueba")

        self.assertEqual([n for n, _ in result["best_path"]], ["uno"])
        self.assertEqual(result["step_count"], 1)


class TestVisualizacionDelArbol(unittest.TestCase):
    """`_render_tot_tree`/`get_tree_visualization`: 35 mutantes sin ningún test."""

    def test_arbol_vacio(self):
        self.assertEqual(TinyToT(llm_provider=None).get_tree_visualization(),
                         "(árbol vacío)")

    def test_incluye_raiz_pasos_indentacion_y_puntuacion(self):
        engine = TinyToT(llm_provider=StubLLM(lambda p: "contenido sustancial y largo"),
                         branch_factor=1)
        engine.think_tot("mi pregunta")

        lineas = engine.get_tree_visualization().split("\n")
        self.assertEqual(len(lineas), 3)
        # la raíz no muestra puntuación y conserva su contenido
        self.assertTrue(lineas[0].startswith("● root:"))
        self.assertNotIn("[", lineas[0])
        self.assertIn("mi pregunta", lineas[0])
        # los hijos van indentados con "└─" y la puntuación con 2 decimales
        self.assertTrue(lineas[1].startswith("  └─ uno ["))
        self.assertTrue(lineas[2].startswith("    └─ dos ["))

    def test_contenido_se_trunca_a_80_caracteres(self):
        def responder(prompt):
            if "evaluador experto" in prompt:
                return '{"relevance": 5, "depth": 5, "coherence": 5, "reasoning": 5}'
            return "x" * 100

        engine = TinyToT(llm_provider=StubLLM(responder), branch_factor=1)
        engine.think_tot("p")

        linea = engine.get_tree_visualization().split("\n")[1]
        self.assertIn("x" * 80 + "...", linea)
        self.assertNotIn("x" * 81, linea)

    def test_renderiza_un_nodo_concreto_sin_raiz(self):
        engine = TinyToT(llm_provider=StubLLM(lambda p: "contenido sustancial y largo"),
                         branch_factor=1)
        engine.think_tot("p")

        dibujo = engine._render_tot_tree(engine._root.children[0])

        self.assertTrue(dibujo.startswith("● uno ["))
        self.assertNotIn("root", dibujo)
        self.assertIn("└─ dos [", dibujo)


class TestVotoPorConsenso(unittest.TestCase):
    """Self-Consistency opt-in (`voto_top_k`): gana el camino mayoritario."""

    def _motor(self, cola, **kwargs):
        def responder(prompt):
            if "evaluador experto" in prompt:
                # La minoría ('beta') puntúa MEJOR: si ganara el score, el test
                # no discriminaría el voto.
                valor = "10" if "beta" in prompt else "5"
                return ('{"relevance": %s, "depth": %s, "coherence": %s, '
                        '"reasoning": %s}' % (valor, valor, valor, valor))
            return cola.pop(0)

        class ToTUnPaso(TinyToT):
            def _step_builders(self):
                return [("uno", lambda o: "paso 1")]

        return ToTUnPaso(llm_provider=StubLLM(responder), branch_factor=3,
                         beam_width=3, **kwargs)

    def test_voto_top_k_uno_mantiene_el_comportamiento_original(self):
        motor = self._motor(["contenido alfa suficientemente largo"] * 3,
                            voto_top_k=1)

        result = motor.think_tot("p")

        self.assertEqual(result["hojas_votadas"], 1)
        self.assertEqual(result["consenso"], 1.0)

    def test_la_mayoria_gana_aunque_la_minoria_puntue_mejor(self):
        motor = self._motor(["contenido alfa suficientemente largo",
                             "contenido alfa suficientemente largo",
                             "contenido beta suficientemente largo"],
                            voto_top_k=3)

        result = motor.think_tot("p")

        self.assertEqual(result["hojas_votadas"], 3)
        self.assertEqual(result["consenso"], 0.667)
        self.assertIn("alfa", result["best_path"][-1][1])
        self.assertLess(result["best_score"], 1.0)   # ganó el voto, no el score

    def test_sin_mayoria_gana_el_mayor_score(self):
        motor = self._motor(["contenido alfa suficientemente largo",
                             "contenido gamma suficientemente largo",
                             "contenido beta suficientemente largo"],
                            voto_top_k=3)

        result = motor.think_tot("p")

        self.assertEqual(result["consenso"], 0.333)
        self.assertIn("beta", result["best_path"][-1][1])


def _juez_fijo(puntuacion):
    """Stub de LLM: el juez puntúa siempre igual y el paso da contenido (SIMULADO)."""
    def responder(prompt):
        if "evaluador experto" in prompt:
            p = puntuacion
            return ('{"relevance": %s, "depth": %s, "coherence": %s, '
                    '"reasoning": %s}' % (p, p, p, p))
        return "contenido sustancial y largo"
    return StubLLM(responder)


class TestValoresPorDefectoMotorBase(unittest.TestCase):
    """Los valores por defecto del constructor son contrato público."""

    def test_defaults_del_motor_base(self):
        engine = TinyEngine()

        self.assertEqual(engine.name, "thinking_engine")
        self.assertEqual(engine.max_steps, 7)
        self.assertEqual(engine.step_count, 0)
        self.assertIsNone(engine.llm)
        self.assertFalse(engine.congelar_fases)

    def test_tot_pasa_nombre_y_max_steps_al_motor_base(self):
        self.assertEqual(TinyToT(llm_provider=None).name, "tot_engine")
        self.assertEqual(TinyToT(llm_provider=None, max_steps=3).max_steps, 3)


class TestEntradasDelCiclo(unittest.TestCase):
    def test_el_prompt_llega_a_los_builders(self):
        capturado = {}

        class CapturaPrompt(TinyEngine):
            def _step_builders(self):
                def builder(o):
                    capturado["prompt"] = o["prompt"]
                    return "paso 1"
                return [("uno", builder)]

        engine = CapturaPrompt(llm_provider=StubLLM(lambda p: "contenido " + p))
        engine.think("mi entrada")

        self.assertEqual(capturado["prompt"], "mi entrada")

    def test_las_salidas_previas_llegan_encadenadas(self):
        capturado = {}

        class Encadenada(TinyEngine):
            def _step_builders(self):
                def dos(o):
                    capturado["uno"] = o["uno"]
                    return "paso 2"
                return [("uno", lambda o: "paso 1"), ("dos", dos)]

        engine = Encadenada(llm_provider=StubLLM(lambda p: "contenido " + p))
        engine.think("entrada")

        self.assertEqual(capturado["uno"], "contenido paso 1")

    def test_llm_generate_reenvia_kwargs_al_proveedor(self):
        class RegistraKwargs:
            def __init__(self):
                self.kwargs = None

            def generate(self, prompt, **kwargs):
                self.kwargs = kwargs
                return "contenido válido y largo"

        llm = RegistraKwargs()
        engine = TinyEngine(llm_provider=llm)
        engine._llm_generate("p", model="x", temperature=0.1)

        self.assertEqual(llm.kwargs, {"model": "x", "temperature": 0.1})


class TestVerificarCongelacionBordes(unittest.TestCase):
    def test_longitudes_distintas_es_falso(self):
        fases = [{"nombre": "uno",
                  "hash": TinyEngine._hash_fase("uno", "abc"),
                  "contenido": "abc"}]

        self.assertFalse(
            TinyEngine.verificar_congelacion([("uno", "abc"), ("dos", "de")], fases))
        self.assertFalse(TinyEngine.verificar_congelacion([], fases))


class TestFronterasValidacionYConfianza(unittest.TestCase):
    def test_frontera_de_diez_caracteres_significativos(self):
        self.assertTrue(StepThinkingEngine.validate_step("abcdefghij"))   # 10 letras
        self.assertFalse(StepThinkingEngine.validate_step("abcdefghi"))   # 9 letras

    def test_confianza_se_redondea_a_dos_decimales(self):
        steps = [("a", "x"), ("b", ""), ("c", "")]

        self.assertEqual(StepThinkingEngine._compute_confidence(steps), 0.33)


class TestBloqueFasesCongeladasExacto(unittest.TestCase):
    def test_bloque_completo_exacto_y_truncado_a_300(self):
        llm = StubLLM(lambda p: "c" * 400)
        TinyEngine(llm_provider=llm, congelar_fases=True).think("entrada")

        hash_uno = TinyEngine._hash_fase("uno", "c" * 400)
        esperado = (
            "paso 2"
            "\n[FASES CONGELADAS — INMUTABLES]\n"
            "Cada fase congelada es inmodificable. Si una evidencia posterior "
            "la contradice, declara la contradicción en la fase actual; NO "
            "reescribas, resumas ni contradigas su contenido.\n"
            f"- uno (hash {hash_uno}): " + "c" * 300
        )
        self.assertEqual(llm.prompts[1], esperado)


class TestThinkTotContrato(unittest.TestCase):
    CLAVES_TOT = {"thought", "decision", "confidence", "valid", "invalid_steps",
                  "steps", "step_count", "error", "best_path", "explored_nodes",
                  "pruned_nodes", "best_score", "consenso", "hojas_votadas",
                  "congelacion_fases"}

    def test_claves_exactas_y_metricas_de_un_ciclo_valido(self):
        engine = TinyToT(llm_provider=_juez_fijo("8"),
                         branch_factor=2, beam_width=2)
        result = engine.think_tot("prueba")

        self.assertEqual(set(result), self.CLAVES_TOT)
        self.assertTrue(result["valid"])
        self.assertIsNone(result["error"])
        self.assertEqual(result["confidence"], 1.0)
        self.assertEqual(result["pruned_nodes"], 0)

    def test_tree_es_la_raiz_explorada(self):
        engine = TinyToT(llm_provider=_juez_fijo("8"))
        result = engine.think_tot("prueba", return_tree=True)

        self.assertIs(result["tree"], engine._root)


class TestUmbralExacto(unittest.TestCase):
    """Score IGUAL al umbral se acepta (>=), no se poda ni invalida."""

    def test_score_igual_al_umbral_se_acepta(self):
        for estrategia in (SearchStrategy.BFS, SearchStrategy.DFS, SearchStrategy.BEAM):
            with self.subTest(estrategia=estrategia):
                engine = TinyToT(llm_provider=_juez_fijo("5"), branch_factor=1,
                                 search_strategy=estrategia,
                                 min_score_threshold=0.5)
                result = engine.think_tot("prueba")

                self.assertEqual([n for n, _ in result["best_path"]], ["uno", "dos"])
                self.assertTrue(result["valid"])
                self.assertEqual(result["pruned_nodes"], 0)


class TestVotoConDosHojas(unittest.TestCase):
    def test_dos_hojas_exactas_tambien_votan(self):
        cola = ["contenido alfa suficientemente largo",
                "contenido beta suficientemente largo"]

        def responder(prompt):
            if "evaluador experto" in prompt:
                return ('{"relevance": 5, "depth": 5, "coherence": 5, '
                        '"reasoning": 5}')
            return cola.pop(0)

        class UnPaso(TinyToT):
            def _step_builders(self):
                return [("uno", lambda o: "paso 1")]

        engine = UnPaso(llm_provider=StubLLM(responder), branch_factor=2,
                        beam_width=2, voto_top_k=2)
        result = engine.think_tot("p")

        self.assertEqual(result["hojas_votadas"], 2)
        self.assertEqual(result["consenso"], 0.5)


class TestJuezRecibeElPaso(unittest.TestCase):
    def test_el_prompt_del_juez_lleva_el_nombre_del_paso(self):
        prompts_juez = []

        def juez(prompt):
            if "evaluador experto" in prompt:
                prompts_juez.append(prompt)
                return ('{"relevance": 8, "depth": 8, "coherence": 8, '
                        '"reasoning": 8}')
            return "contenido sustancial y largo"

        engine = TinyToT(llm_provider=StubLLM(juez), branch_factor=1)
        engine.think_tot("prueba")

        self.assertEqual(len(prompts_juez), 2)
        self.assertIn("PASO ACTUAL: uno", prompts_juez[0])
        self.assertIn("PASO ACTUAL: dos", prompts_juez[1])

    def test_evaluate_state_pasa_outputs_a_la_heuristica(self):
        engine = TinyToT(llm_provider=None)

        self.assertEqual(
            engine._evaluate_state("alfa bravo charlie", "uno",
                                   {"prompt": "alfa bravo charlie delta"}), 0.64)


class TestMarcadoresHeuristica(unittest.TestCase):
    """Cada marcador de razonamiento cuenta por sí solo (+0,05)."""

    def setUp(self):
        self.engine = TinyToT(llm_provider=None)

    def test_cada_marcador_suma(self):
        marcadores = ["por tanto", "sin embargo", "por lo tanto", "en consecuencia",
                      "dado que", "puesto que", "así que", "because", "therefore",
                      "however", "moreover", "thus", "given that", "since", "so"]
        for marcador in marcadores:
            with self.subTest(marcador=marcador):
                self.assertEqual(
                    self.engine._evaluate_state_heuristic(
                        f"{marcador} " + "x" * 20, "uno", {}), 0.56)

    def test_coherencia_con_varios_pasos_previos(self):
        self.assertEqual(
            self.engine._evaluate_state_heuristic(
                "bravo charlie", "dos",
                {"prompt": "alfa bravo", "uno": "charlie delta"}), 0.64)

    def test_solapamiento_con_una_sola_palabra_previa(self):
        self.assertEqual(
            self.engine._evaluate_state_heuristic(
                "bravo", "uno", {"prompt": "bravo"}), 0.65)


class TestJuezLLMContrato(unittest.TestCase):
    def setUp(self):
        self.engine = TinyToT(llm_provider=None)

    def _prompt_del_juez(self, contenido, paso, outputs, respuesta=None):
        capturado = {}

        def responder(prompt):
            capturado["prompt"] = prompt
            return respuesta or ('{"relevance": 5, "depth": 5, "coherence": 5, '
                                 '"reasoning": 5}')

        self.engine.llm = StubLLM(responder)
        self.engine._evaluate_state_llm(contenido, paso, outputs)
        return capturado["prompt"]

    def test_sin_pasos_previos_lo_declara(self):
        prompt = self._prompt_del_juez("contenido", "uno", {})

        self.assertIn("CONTEXTO PREVIO (pasos ya ejecutados):\n"
                      "(ninguno - primer paso)\n", prompt)

    def test_context_str_no_va_a_los_pasos_previos(self):
        prompt = self._prompt_del_juez(
            "contenido", "dos",
            {"context": "texto de contexto", "uno": "paso previo largo"})

        self.assertNotIn("--- context ---", prompt)
        self.assertIn("--- uno ---", prompt)

    def test_varios_pasos_previos_se_acumulan(self):
        prompt = self._prompt_del_juez(
            "contenido", "tres",
            {"uno": "primer paso largo", "dos": "segundo paso largo"})

        self.assertIn("--- uno ---", prompt)
        self.assertIn("--- dos ---", prompt)

    def test_paso_previo_se_trunca_a_300(self):
        prompt = self._prompt_del_juez("contenido", "dos", {"uno": "p" * 400})

        self.assertIn("p" * 300, prompt)
        self.assertNotIn("p" * 301, prompt)

    def test_contenido_se_trunca_a_1500(self):
        prompt = self._prompt_del_juez("z" * 1600, "uno", {})

        self.assertIn("z" * 1500, prompt)
        self.assertNotIn("z" * 1501, prompt)

    def test_json_multilinea_se_parsea(self):
        respuesta = ('{\n"relevance": 10,\n"depth": 10,\n"coherence": 10,\n'
                     '"reasoning": 10\n}')
        self.engine.llm = StubLLM(lambda p: respuesta)

        self.assertEqual(
            self.engine._evaluate_state_llm("contenido", "uno", {}), 1.0)

    def test_puntuacion_se_redondea_a_dos_decimales(self):
        self.engine.llm = StubLLM(
            lambda p: '{"relevance": 9, "depth": 8, "coherence": 7, "reasoning": 6}')

        self.assertEqual(
            self.engine._evaluate_state_llm("contenido", "uno", {}), 0.74)

    def test_error_sin_json_menciona_la_causa_y_trunca_la_respuesta(self):
        self.engine.llm = StubLLM(lambda p: "x" * 200)

        with self.assertRaises(ValueError) as ctx:
            self.engine._evaluate_state_llm("contenido", "uno", {})

        self.assertIn("sin JSON", str(ctx.exception))
        self.assertIn("x" * 120, str(ctx.exception))
        self.assertNotIn("x" * 121, str(ctx.exception))


class TestRenderArbolPorDefecto(unittest.TestCase):
    def test_render_sin_argumentos_usa_la_raiz(self):
        engine = TinyToT(llm_provider=_juez_fijo("8"), branch_factor=1)
        engine.think_tot("p")

        self.assertIn("root", engine._render_tot_tree())


class TestBusquedasFrontera(unittest.TestCase):
    def test_bfs_tolera_nodos_en_max_depth_en_pasos_restantes(self):
        class TresPasos(TinyToT):
            def _step_builders(self):
                return [("uno", lambda o: "paso 1"),
                        ("dos", lambda o: "paso 2"),
                        ("tres", lambda o: "paso 3")]

        engine = TresPasos(llm_provider=_juez_fijo("8"), branch_factor=1,
                           search_strategy=SearchStrategy.BFS, max_depth=1)
        result = engine.think_tot("prueba")

        self.assertEqual([n for n, _ in result["best_path"]], ["uno"])

    def test_dfs_respeta_max_depth(self):
        engine = TinyToT(llm_provider=_juez_fijo("8"), branch_factor=1,
                         search_strategy=SearchStrategy.DFS, max_depth=1)
        result = engine.think_tot("prueba")

        self.assertEqual([n for n, _ in result["best_path"]], ["uno"])

    def test_dfs_explora_primero_la_mejor_rama(self):
        cola = ["contenido alfa suficientemente largo",
                "contenido beta suficientemente largo",
                "segundo alfa suficientemente largo",
                "segundo beta suficientemente largo"]

        def responder(prompt):
            if "evaluador experto" in prompt:
                # Puntuar SOLO el pensamiento evaluado: el contexto previo
                # también lleva "beta" y contaminaría la puntuación.
                evaluado = prompt.split("PENSAMIENTO A EVALUAR:\n", 1)[1]
                evaluado = evaluado.split("\n\nCONTEXTO PREVIO", 1)[0]
                valor = "10" if "beta" in evaluado else "5"
                return ('{"relevance": %s, "depth": %s, "coherence": %s, '
                        '"reasoning": %s}' % (valor, valor, valor, valor))
            return cola.pop(0)

        engine = TinyToT(llm_provider=StubLLM(responder), branch_factor=2,
                         search_strategy=SearchStrategy.DFS)
        result = engine.think_tot("prueba")

        self.assertIn("beta", result["best_path"][0][1])
        self.assertIn("segundo beta", result["best_path"][-1][1])

    def test_beam_mantiene_los_mejores_candidatos(self):
        cola = ["contenido alfa suficientemente largo",
                "contenido beta suficientemente largo",
                "contenido gamma suficientemente largo"]

        def responder(prompt):
            if "evaluador experto" in prompt:
                valor = ("10" if "gamma" in prompt
                         else "8" if "beta" in prompt else "5")
                return ('{"relevance": %s, "depth": %s, "coherence": %s, '
                        '"reasoning": %s}' % (valor, valor, valor, valor))
            return cola.pop(0)

        class UnPaso(TinyToT):
            def _step_builders(self):
                return [("uno", lambda o: "paso 1")]

        engine = UnPaso(llm_provider=StubLLM(responder), branch_factor=3,
                        beam_width=2)
        result = engine.think_tot("prueba")

        self.assertEqual(result["best_score"], 1.0)
        self.assertIn("gamma", result["best_path"][-1][1])

    def test_beam_cae_al_beam_previo_si_el_nivel_se_poda_entero(self):
        def juez(prompt):
            if "evaluador experto" in prompt:
                valor = "8" if "PASO ACTUAL: uno" in prompt else "3"
                return ('{"relevance": %s, "depth": %s, "coherence": %s, '
                        '"reasoning": %s}' % (valor, valor, valor, valor))
            return "contenido sustancial y largo"

        engine = TinyToT(llm_provider=StubLLM(juez), branch_factor=1,
                         min_score_threshold=0.5)
        result = engine.think_tot("prueba")

        self.assertEqual([n for n, _ in result["best_path"]], ["uno"])
        self.assertTrue(result["valid"])
        self.assertEqual(result["best_score"], 0.8)


if __name__ == "__main__":
    unittest.main()