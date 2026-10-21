"""Tests offline de pensamiento_layer.py (LLM y búsqueda SIMULADOS)."""

import contextlib
import io
import unittest

import pensamiento_layer as pl
from deep_research_system import MockLLM
from pensamiento_layer import (DeepResearchThinkingLayer,
                               ResearchOrchestratorWithThinking, ThinkingLayer)
from tests.helpers import StubLLM
from thinking_engine import StepThinkingEngine
from web_search import MockSearchAPI

CLAVES_RESULTADO = {"thought", "decision", "confidence", "valid",
                    "invalid_steps", "steps", "step_count", "error"}


class TestDeepResearchThinkingLayer(unittest.TestCase):
    def test_alias_thinking_layer(self):
        self.assertIs(ThinkingLayer, StepThinkingEngine)

    def test_ciclo_completo_valido_con_mock_llm(self):
        layer = DeepResearchThinkingLayer(MockLLM())
        self.assertEqual(layer.max_steps, 7)
        result = layer.think("¿Fusión nuclear en 2030?")

        self.assertTrue(CLAVES_RESULTADO <= set(result))
        self.assertTrue(result["valid"])
        self.assertEqual(result["step_count"], 7)
        self.assertEqual(result["invalid_steps"], [])
        self.assertIsNone(result["error"])
        self.assertEqual(result["confidence"], 1.0)
        self.assertEqual(result["decision"], "decision_from_synthesis")
        self.assertEqual(
            [name for name, _ in result["steps"]],
            ["analysis", "plan", "search_strategy", "search_results",
             "claim_extraction", "evidence_eval", "synthesis"],
        )
        self.assertIn("CAPA DE PENSAMIENTO", result["thought"])
        self.assertIn("PASO 1 - ANÁLISIS", result["thought"])
        self.assertIn("PASOS COMPLETADOS: 7/7", result["thought"])

    def test_llm_cadena_vacia_falla_en_analysis_con_todas_las_claves(self):
        # Regresión del KeyError corregido: la rama inválida debe devolver
        # exactamente las mismas claves que el camino feliz.
        layer = DeepResearchThinkingLayer(StubLLM(lambda p: ""))
        result = layer.think("pregunta")

        self.assertTrue(CLAVES_RESULTADO <= set(result))
        self.assertFalse(result["valid"])
        self.assertEqual(result["invalid_steps"], ["analysis"])
        self.assertEqual(result["step_count"], 1)
        self.assertEqual(result["confidence"], 0.0)
        self.assertEqual(result["error"], "Paso inválido: analysis")
        self.assertIn("REVISAR", result["thought"])

    def test_fallo_en_paso_intermedio_detiene_el_ciclo(self):
        def responder(prompt):
            return "contenido válido y sustancial" if "PASO 1" in prompt else ""

        layer = DeepResearchThinkingLayer(StubLLM(responder))
        result = layer.think("pregunta")
        self.assertFalse(result["valid"])
        self.assertEqual(result["invalid_steps"], ["plan"])
        self.assertEqual(result["step_count"], 2)

    def test_validate_step_compat(self):
        layer = DeepResearchThinkingLayer(MockLLM())
        self.assertTrue(layer._validate_step("contenido suficientemente largo"))
        self.assertFalse(layer._validate_step(""))

    def test_use_tot_activa_el_modo_tot_en_think(self):
        layer = DeepResearchThinkingLayer(MockLLM(), use_tot=True,
                                          branch_factor=1)
        result = layer.think("¿Fusión nuclear?")
        self.assertIn("best_path", result)
        self.assertIn("explored_nodes", result)

    def test_use_tot_false_mantiene_el_ciclo_lineal(self):
        layer = DeepResearchThinkingLayer(MockLLM(), use_tot=False)
        result = layer.think("¿Fusión nuclear?")
        self.assertNotIn("best_path", result)
        self.assertEqual(result["step_count"], 7)

    def test_nombre_por_defecto_y_explicito(self):
        self.assertEqual(DeepResearchThinkingLayer(MockLLM()).name,
                         "deep_research_thinking")
        self.assertEqual(DeepResearchThinkingLayer(MockLLM(), name="otro").name,
                         "otro")

    def test_think_lineal_pasa_prompt_y_contexto_al_llm(self):
        llm = StubLLM(lambda p: "contenido válido y sustancial")
        layer = DeepResearchThinkingLayer(llm)
        layer.think("¿Pregunta concreta?", {"clave": "valor-contexto"})

        self.assertTrue(any("¿Pregunta concreta?" in p for p in llm.prompts))
        self.assertTrue(any("valor-contexto" in p for p in llm.prompts))

    def test_think_tot_pasa_prompt_y_contexto_al_llm(self):
        def responder(prompt):
            if "evaluador experto" in prompt:
                return ('{"relevance": 5, "depth": 5, "coherence": 5, '
                        '"reasoning": 5}')
            return "contenido válido y sustancial"

        llm = StubLLM(responder)
        layer = DeepResearchThinkingLayer(llm, use_tot=True, branch_factor=1)
        layer.think("¿Pregunta ToT?", {"clave": "valor-tot"})

        self.assertTrue(any("¿Pregunta ToT?" in p for p in llm.prompts))
        self.assertTrue(any("valor-tot" in p for p in llm.prompts))


class TestResearchOrchestratorWithThinking(unittest.TestCase):
    def test_valores_por_defecto_del_orquestador(self):
        orchestrator = ResearchOrchestratorWithThinking(
            MockLLM(), MockSearchAPI(), DeepResearchThinkingLayer(MockLLM()))

        self.assertFalse(orchestrator.verificacion_independiente)
        self.assertIsNone(orchestrator.llm_verificador)
        self.assertEqual(orchestrator.muestras_consenso, 1)
        self.assertIsNone(orchestrator.results)

    def test_research_pasa_la_pregunta_al_ciclo_de_pensamiento(self):
        class PensamientoQueRegistra:
            """Capa de pensamiento simulada que anota la pregunta recibida."""

            def __init__(self):
                self.visto = None

            def think(self, question):
                self.visto = question
                return {"step_count": 7, "confidence": 1.0, "valid": True}

        pensamiento = PensamientoQueRegistra()
        orchestrator = ResearchOrchestratorWithThinking(
            MockLLM(), MockSearchAPI(), pensamiento)
        with contextlib.redirect_stdout(io.StringIO()):
            orchestrator.research_with_thinking("¿Pregunta registrada?")

        self.assertEqual(pensamiento.visto, "¿Pregunta registrada?")

    def test_investigacion_completa_offline(self):
        layer = DeepResearchThinkingLayer(MockLLM())
        orchestrator = ResearchOrchestratorWithThinking(
            MockLLM(), MockSearchAPI(), layer)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            result = orchestrator.research_with_thinking("¿Fusión nuclear?")

        self.assertEqual(result["question"], "¿Fusión nuclear?")
        self.assertEqual(result["total_thinking_steps"], 7)
        self.assertEqual(result["thinking"]["step_count"], 7)
        self.assertTrue(result["thinking"]["valid"])
        # Delega en el pipeline REAL: fuentes, claims y evaluaciones las
        # produce ResearchOrchestrator, no heurísticas locales.
        self.assertGreater(len(result["sources"]), 0)
        self.assertGreater(len(result["claims"]), 0)
        self.assertEqual(len(result["claims"]), len(result["evaluations"]))
        self.assertTrue(result["report"])
        self.assertIs(result["context"].sources, result["sources"])
        self.assertIs(orchestrator.results, result)
        self.assertIn("INVESTIGACIÓN COMPLETADA", buffer.getvalue())

    def test_pensamiento_invalido_devuelve_error_sin_buscar(self):
        layer = DeepResearchThinkingLayer(StubLLM(lambda p: ""))
        search = MockSearchAPI()
        orchestrator = ResearchOrchestratorWithThinking(
            MockLLM(), search, layer)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            result = orchestrator.research_with_thinking("pregunta")

        self.assertIn("error", result)
        self.assertEqual(
            result["error"],
            "Ciclo de pensamiento no válido; replantear la pregunta "
            "(anti-repitencia)")
        self.assertEqual(result["thinking"]["invalid_steps"], ["analysis"])

    def test_ya_no_existen_heuristicas_simuladas(self):
        """Regresión: se eliminaron las heurísticas simuladas del orquestador."""
        orchestrator = ResearchOrchestratorWithThinking(
            MockLLM(), MockSearchAPI(), DeepResearchThinkingLayer(MockLLM()))
        for metodo in ("_extract_claims_with_thought",
                       "_evaluate_evidence_with_thought",
                       "_synthesize_with_thought"):
            self.assertFalse(hasattr(orchestrator, metodo),
                             f"sigue existiendo el método simulado {metodo}")

    def test_pasa_verificador_separado_al_pipeline(self):
        generador = MockLLM()
        verificador = StubLLM(
            lambda p: '{"verdict": "contradicted", "credibility": 0.1}')
        orchestrator = ResearchOrchestratorWithThinking(
            generador, MockSearchAPI(), DeepResearchThinkingLayer(generador),
            verificacion_independiente=True, llm_verificador=verificador)
        buffer = io.StringIO()

        with contextlib.redirect_stdout(buffer):
            result = orchestrator.research_with_thinking("¿Fusión nuclear?")

        razones = [d["rationale"] for d in result["context"].decision_log
                   if d["step"] == "independent_verification"]
        self.assertTrue(razones)
        self.assertTrue(all("[proveedor-distinto]" in r for r in razones))
        self.assertTrue(any("contestado" in r for r in razones))

    def test_pasa_muestras_consenso_al_pipeline(self):
        generador = MockLLM()
        orchestrator = ResearchOrchestratorWithThinking(
            generador, MockSearchAPI(), DeepResearchThinkingLayer(generador),
            muestras_consenso=2)
        buffer = io.StringIO()

        with contextlib.redirect_stdout(buffer):
            result = orchestrator.research_with_thinking("¿Fusión nuclear?")

        consensos = [d for d in result["context"].decision_log
                     if d["step"] == "sampling_consensus"]
        self.assertTrue(consensos)
        self.assertTrue(all(d["decision"] == "acuerdo" for d in consensos))
        self.assertTrue(all("2/2" in d["rationale"] for d in consensos))
        self.assertTrue(all(
            e["consenso_muestreo"]["muestras"] == 2
            for e in result["context"].evaluations))


class TestMain(unittest.TestCase):
    def test_main_offline_completa(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            pl.main()
        salida = buffer.getvalue()
        # Verificar modo lineal
        self.assertIn("RESULTADO MODO LINEAL", salida)
        self.assertIn("Pasos ejecutados: 7", salida)
        self.assertIn("Válido: True", salida)
        # Verificar modo ToT
        self.assertIn("RESULTADO MODO ToT", salida)
        self.assertIn("Nodos explorados:", salida)
        self.assertIn("Score mejor:", salida)


class TestRenderThought(unittest.TestCase):
    """Formato exacto del pensamiento renderizado (salida visible del ciclo)."""

    def test_formato_exacto_de_cabecera_y_resumen(self):
        layer = DeepResearchThinkingLayer(MockLLM())
        result = layer.think("¿Fusión nuclear?")
        lineas = result["thought"].split("\n")

        self.assertEqual(lineas[0],
                         "        CAPA DE PENSAMIENTO: deep_research_thinking")
        self.assertEqual(lineas[1], "        ============================")
        self.assertEqual(lineas[2], "")
        self.assertIn("PASO 3 - ESTRATEGIA", result["thought"])
        self.assertIn("PASO 5 - CLAIMS", result["thought"])
        idx = lineas.index("        PASOS COMPLETADOS: 7/7")
        self.assertEqual(lineas[idx - 1], "")
        self.assertIn("CONFIANZA GENERAL: 1.0", result["thought"])
        self.assertIn("VALIDEZ: VALID", result["thought"])

    def test_contenido_de_paso_se_trunca_a_200_caracteres(self):
        layer = DeepResearchThinkingLayer(StubLLM(lambda p: "x" * 250))
        result = layer.think("pregunta")

        self.assertIn("x" * 200, result["thought"])
        self.assertNotIn("x" * 201, result["thought"])

    def test_paso_intermedio_ausente_no_detiene_el_render(self):
        layer = DeepResearchThinkingLayer(MockLLM())
        pasos = [("analysis", "contenido válido y sustancial"),
                 ("search_strategy", "contenido válido y sustancial")]

        render = layer._render_thought(pasos)

        self.assertIn("PASO 1 - ANÁLISIS", render)
        self.assertIn("PASO 2 - ESTRATEGIA", render)

    def test_validez_revisar_si_un_paso_previo_es_invalido(self):
        layer = DeepResearchThinkingLayer(MockLLM())
        pasos = [("analysis", ""),
                 ("plan", "contenido válido y sustancial")]

        render = layer._render_thought(pasos)

        self.assertIn("VALIDEZ: REVISAR", render)


class LayerQueCaptura(DeepResearchThinkingLayer):
    """Capa de un solo paso real ('analysis') que anota los parámetros ToT.

    El nombre del paso debe ser uno de los de la capa real: `_render_thought`
    indexa `etiquetas[name]` y lanzaría KeyError con un nombre inventado.
    """

    visto = None

    def _step_builders(self):
        def builder(o):
            if self.visto is not None:
                self.visto.append((self.branch_factor, self.beam_width,
                                   self.search_strategy,
                                   self.min_score_threshold, self.max_depth))
            return "prompt del paso"
        return [("analysis", builder)]


class TestThinkTotConOverrides(unittest.TestCase):
    """`DeepResearchThinkingLayer.think_tot` aplica y RESTAURA sus overrides."""

    def _layer(self, **kwargs):
        layer = LayerQueCaptura(
            StubLLM(lambda p: '{"relevance": 5, "depth": 5, "coherence": 5, '
                              '"reasoning": 5}'),
            **kwargs)
        layer.visto = []
        return layer

    def test_aplica_overrides_durante_la_llamada(self):
        layer = self._layer(branch_factor=1)

        layer.think_tot("pregunta", branch_factor=5, beam_width=2,
                        search_strategy="dfs", min_score_threshold=0.9,
                        max_depth=3)

        self.assertEqual(layer.visto[0], (5, 2, "dfs", 0.9, 3))

    def test_restaura_los_valores_originales(self):
        layer = self._layer(branch_factor=1, beam_width=4)

        layer.think_tot("pregunta", branch_factor=5, search_strategy="dfs")

        self.assertEqual(layer.branch_factor, 1)
        self.assertEqual(layer.beam_width, 4)
        self.assertEqual(layer.search_strategy, "beam")
        self.assertEqual(layer.min_score_threshold, 0.3)
        self.assertEqual(layer.max_depth, 7)

    def test_sin_kwargs_no_cambia_nada(self):
        layer = self._layer(branch_factor=1)

        layer.think_tot("pregunta")

        self.assertEqual(layer.visto[0], (1, 3, "beam", 0.3, 7))

    def test_restaura_tambien_si_el_llm_falla(self):
        def explotar(prompt):
            raise RuntimeError("fallo simulado de red")

        layer = DeepResearchThinkingLayer(StubLLM(explotar), branch_factor=1)
        with self.assertRaises(RuntimeError):
            layer.think_tot("pregunta", branch_factor=5, max_depth=2)

        self.assertEqual(layer.branch_factor, 1)
        self.assertEqual(layer.max_depth, 7)

    def test_devuelve_el_resultado_del_motor(self):
        layer = self._layer(branch_factor=1)

        result = layer.think_tot("pregunta")

        self.assertEqual([n for n, _ in result["best_path"]], ["analysis"])
        self.assertIn("best_score", result)

    def test_return_tree_se_reenvia_al_motor(self):
        layer = self._layer(branch_factor=1)

        result = layer.think_tot("pregunta", return_tree=True)

        self.assertIn("tree", result)

    def test_kwarg_desconocido_se_eleva(self):
        layer = self._layer(branch_factor=1)

        with self.assertRaises(TypeError) as ctx:
            layer.think_tot("pregunta", inventado=1)

        self.assertIn("desconocidos", str(ctx.exception))
        self.assertIn("inventado", str(ctx.exception))

    def test_return_tree_por_defecto_no_incluye_el_arbol(self):
        layer = self._layer(branch_factor=1)

        result = layer.think_tot("pregunta")

        self.assertNotIn("tree", result)


class TestDemo(unittest.TestCase):
    def test_main_muestra_los_dos_modos_y_el_camino_tot(self):
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida), \
                contextlib.redirect_stderr(io.StringIO()):
            pl.main()

        texto = salida.getvalue()
        self.assertIn("RESULTADO MODO LINEAL", texto)
        self.assertIn("RESULTADO MODO ToT", texto)
        self.assertIn("Mejor camino:", texto)
        # El ToT del demo ya produce camino (el juez simulado puntúa): cada
        # paso se imprime con nombre y contenido.
        self.assertIn("  [analysis]", texto)
        # La demo nombra la capa y fija los parámetros ToT: nombre y conteos
        # exactos (MockLLM es determinista).
        self.assertIn("        CAPA DE PENSAMIENTO: deep_research\n", texto)
        self.assertIn("Nodos explorados: 40", texto)
        self.assertIn("Nodos podados: 0", texto)


if __name__ == "__main__":
    unittest.main()
