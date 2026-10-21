"""Tests offline de code_design_improvement_tools.py (LLM SIMULADO)."""

import contextlib
import io
import os
import tempfile
import time
import unittest

import code_design_improvement_tools as cdt
from code_design_improvement_tools import (SEVERITY_ORDER, CodeAnalysisContext,
                                           CodeDesignThinker,
                                           CodeImprovementOrchestrator,
                                           ThinkingDecisionEngine,
                                           analyze_python_code,
                                           analyze_python_source)
from deep_research_system import MockLLM
from tests.helpers import StubLLM

CODIGO_CON_ISSUES = (
    "import os, sys\n"
    'x = "' + "a" * 130 + '"\n'
    "def f(n):\n"
    "    if n:\n"
    "        return 1\n"
    "    return 0\n"
)


class TestSeverityOrder(unittest.TestCase):
    def test_orden_critical_menor_que_low(self):
        self.assertLess(SEVERITY_ORDER["critical"], SEVERITY_ORDER["high"])
        self.assertLess(SEVERITY_ORDER["high"], SEVERITY_ORDER["medium"])
        self.assertLess(SEVERITY_ORDER["medium"], SEVERITY_ORDER["low"])


class TestCodeAnalysisContext(unittest.TestCase):
    def test_issues_ordenados_por_severidad(self):
        ctx = CodeAnalysisContext("proyecto")
        ctx.add_issue("style", "low", "issue leve")
        ctx.add_issue("security", "critical", "issue crítico")
        ctx.add_issue("style", "medium", "issue medio")
        severities = [i["severity"] for i in ctx.issues]
        self.assertEqual(severities, ["critical", "medium", "low"])

    def test_max_issues_recorta_manteniendo_los_mas_criticos(self):
        ctx = CodeAnalysisContext("proyecto", max_issues=2)
        ctx.add_issue("style", "low", "leve")
        ctx.add_issue("security", "critical", "crítico")
        ctx.add_issue("style", "medium", "medio")
        self.assertEqual(len(ctx.issues), 2)
        self.assertEqual([i["severity"] for i in ctx.issues],
                         ["critical", "medium"])

    def test_severidad_desconocida_va_al_final(self):
        ctx = CodeAnalysisContext("proyecto")
        ctx.add_issue("otra", "inventada", "rara")
        ctx.add_issue("style", "low", "leve")
        self.assertEqual(ctx.issues[-1]["severity"], "inventada")

    def test_to_dict_incluye_issues_y_desglose(self):
        ctx = CodeAnalysisContext("proyecto")
        ctx.add_issue("security", "critical", "c")
        ctx.add_issue("style", "low", "l")
        ctx.add_thinking_step("paso", "razonamiento", {"r": 1})
        d = ctx.to_dict()
        self.assertIn("issues", d)
        self.assertEqual(d["total_issues"], 2)
        self.assertEqual(d["issue_breakdown"],
                         {"critical": 1, "high": 0, "medium": 0, "low": 1})
        self.assertEqual(d["thinking_steps"], 1)
        # Referencia única (EFFICIENCY_REFERENCE_ISSUES = 30): 2/30 → 0.07
        self.assertEqual(d["efficiency_score"], 0.07)

    def test_efficiency_score_sin_project_path_es_cero(self):
        ctx = CodeAnalysisContext("")
        ctx.add_issue("style", "low", "l")
        self.assertEqual(ctx.to_dict()["efficiency_score"], 0.0)

    def test_add_issue_rellena_campos_por_defecto(self):
        ctx = CodeAnalysisContext("proyecto")
        ctx.add_issue("style", "low", "desc")
        issue = ctx.issues[0]
        self.assertEqual(issue["file"], "unknown")
        self.assertIsNone(issue["line"])
        self.assertIsNone(issue["suggestion"])
        self.assertIn("detected_at", issue)


class TestThinkingDecisionEngine(unittest.TestCase):
    def test_es_abstracto(self):
        with self.assertRaises(TypeError):
            ThinkingDecisionEngine()


class TestCodeDesignThinker(unittest.TestCase):
    def test_ciclo_completo_valido_con_mock_llm(self):
        thinker = CodeDesignThinker(name="t", llm_provider=MockLLM())
        result = thinker.decide(CodeAnalysisContext("p"), "código fuente")
        self.assertTrue(result["valid"])
        self.assertEqual(result["step_count"], 7)
        self.assertEqual(result["invalid_steps"], [])
        self.assertIsNone(result["error"])
        self.assertEqual(result["confidence"], 1.0)
        self.assertEqual(result["decision"], "decision_from_validation")
        self.assertEqual(
            [name for name, _ in result["steps"]],
            ["analysis", "objectives", "design_options", "evaluation",
             "selection", "implementation_plan", "validation"],
        )
        self.assertIn("PASO 1 - ANÁLISIS", result["thought"])
        self.assertEqual(thinker.step_count, 7)

    def test_paso1_invalido_devuelve_error(self):
        thinker = CodeDesignThinker(llm_provider=StubLLM(lambda p: ""))
        result = thinker.decide(CodeAnalysisContext("p"), "código")
        self.assertFalse(result["valid"])
        self.assertEqual(result["step_count"], 0)
        self.assertEqual(result["steps"], [])
        self.assertIn("Paso 1", result["error"])
        self.assertEqual(result["thought"], "")

    def test_paso_intermedio_invalido_detiene_el_ciclo(self):
        llm = StubLLM(lambda p: "" if "PASO 2" in p
                      else "texto válido con contenido suficiente")
        thinker = CodeDesignThinker(llm_provider=llm)
        result = thinker.decide(CodeAnalysisContext("p"), "código")
        self.assertFalse(result["valid"])
        self.assertEqual(result["invalid_steps"], ["objectives"])
        self.assertEqual(result["step_count"], 1)
        self.assertEqual([n for n, _ in result["steps"]], ["analysis"])
        self.assertIn("Paso 2", result["error"])

    def test_max_steps_acota_el_ciclo(self):
        thinker = CodeDesignThinker(llm_provider=MockLLM(), max_steps=3)
        result = thinker.decide(CodeAnalysisContext("p"), "código")
        self.assertTrue(result["valid"])
        self.assertEqual(result["step_count"], 3)
        self.assertEqual([n for n, _ in result["steps"]],
                         ["analysis", "objectives", "design_options"])

    def test_paso_invalido_en_cualquier_posicion_detiene_el_ciclo(self):
        for numero in range(2, 8):
            with self.subTest(paso=numero):
                llm = StubLLM(lambda p, n=numero: "" if f"PASO {n}" in p
                              else "texto válido con contenido suficiente")
                result = CodeDesignThinker(llm_provider=llm).decide(
                    CodeAnalysisContext("p"), "código")
                self.assertFalse(result["valid"])
                self.assertEqual(len(result["invalid_steps"]), 1)
                self.assertEqual(result["step_count"], numero - 1)
                self.assertIn(f"Paso {numero}", result["error"])

    def test_max_steps_mayor_que_siete_completa_el_ciclo(self):
        # Con max_steps=8 `_registrar` no cierra en el paso 7: el ciclo debe
        # terminar por su retorno final (rama que antes no se ejecutaba).
        thinker = CodeDesignThinker(llm_provider=MockLLM(), max_steps=8)
        result = thinker.decide(CodeAnalysisContext("p"), "código")
        self.assertTrue(result["valid"])
        self.assertEqual(result["step_count"], 7)
        self.assertEqual(len(result["steps"]), 7)

    def test_sin_proveedor_usa_mock_llm_offline(self):
        thinker = CodeDesignThinker()
        result = thinker.decide(CodeAnalysisContext("p"), "código")
        self.assertIsInstance(thinker.llm, MockLLM)
        self.assertTrue(result["valid"])

    def test_validate_thought_compat(self):
        thinker = CodeDesignThinker(llm_provider=MockLLM())
        self.assertTrue(thinker._validate_thought("contenido largo suficiente"))
        self.assertFalse(thinker._validate_thought(""))

    def test_motor_base_sin_step_builders_propios(self):
        # ThinkingDecisionEngine define su propio ciclo (decide): los hooks del
        # ciclo común quedan como stubs vacíos explícitos.
        thinker = CodeDesignThinker(llm_provider=MockLLM())
        self.assertEqual(thinker._step_builders(), [])
        self.assertEqual(thinker._render_thought([]), "")


class TestCodeImprovementOrchestrator(unittest.TestCase):
    def test_analyze_and_improve_completo(self):
        thinker = CodeDesignThinker(llm_provider=MockLLM())
        orchestrator = CodeImprovementOrchestrator(
            thinker, source_code=CODIGO_CON_ISSUES)
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            results = orchestrator.analyze_and_improve()

        self.assertIn("analysis", results)
        self.assertEqual(results["total_thinking_steps"], 7)
        self.assertEqual(results["efficiency_principle"],
                         "Hacer las cosas de manera eficiente")
        metrics = results["project_metrics"]
        # 1 issue por importaciones múltiples (medium) + 1 por línea larga (low)
        self.assertEqual(metrics["total_issues"], 2)
        self.assertEqual(metrics["issue_breakdown"],
                         {"critical": 0, "high": 0, "medium": 1, "low": 1})
        self.assertEqual(metrics["metrics"]["functions"], 1)
        self.assertIn("ANÁLISIS COMPLETADO", buffer.getvalue())

    def test_run_analysis_usa_un_solo_ciclo(self):
        llm = StubLLM(lambda p: "texto válido con contenido suficiente")
        thinker = CodeDesignThinker(llm_provider=llm)
        orq = CodeImprovementOrchestrator(thinker, source_code="x = 1")
        results = orq.run_analysis()
        self.assertEqual(results["total_thinking_steps"], 7)
        self.assertEqual(len(llm.prompts), 7)   # antes: 49 llamadas

    def test_generate_report_tras_analisis(self):
        thinker = CodeDesignThinker(llm_provider=MockLLM())
        orchestrator = CodeImprovementOrchestrator(
            thinker, source_code=CODIGO_CON_ISSUES)
        with contextlib.redirect_stdout(io.StringIO()):
            orchestrator.analyze_and_improve()
        report = orchestrator.generate_report()
        self.assertIn("# Análisis y Mejora de Proyecto de Código", report)
        self.assertIn("[MEDIUM]", report)
        self.assertIn("[LOW]", report)
        self.assertIn("Sugerencia:", report)
        self.assertIn("Decisiones de Diseño", report)

    def test_generate_report_sin_resultados(self):
        orchestrator = CodeImprovementOrchestrator(
            CodeDesignThinker(llm_provider=MockLLM()))
        self.assertEqual(orchestrator.generate_report(),
                         "No results to report.")

    def test_analyze_and_improve_sin_codigo_fuente(self):
        orchestrator = CodeImprovementOrchestrator(
            CodeDesignThinker(llm_provider=MockLLM()), source_code="")
        with contextlib.redirect_stdout(io.StringIO()):
            results = orchestrator.analyze_and_improve()
        self.assertEqual(results["project_metrics"]["total_issues"], 0)

    def test_analyze_and_improve_falla_si_paso1_invalido(self):
        thinker = CodeDesignThinker(llm_provider=StubLLM(lambda p: ""))
        orchestrator = CodeImprovementOrchestrator(thinker, source_code="x = 1")
        with contextlib.redirect_stdout(io.StringIO()):
            results = orchestrator.analyze_and_improve()
        self.assertIn("error", results)
        self.assertIn("falló", results["error"])
        self.assertEqual(results["steps"][0][0], "fallido")

    def test_analyze_and_improve_falla_con_error_de_sintaxis(self):
        thinker = CodeDesignThinker(llm_provider=MockLLM())
        orchestrator = CodeImprovementOrchestrator(
            thinker, source_code="def broken(:\n")
        errores = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(errores):
            results = orchestrator.analyze_and_improve()

        self.assertIn("error", results)
        self.assertIn("error de sintaxis", results["error"])
        self.assertEqual(results["steps"][0][0], "fallido")
        self.assertFalse(orchestrator.results)   # no se ejecutó ninguna fase
        self.assertEqual(orchestrator.generate_report(), "No results to report.")
        self.assertIn("ERROR:", errores.getvalue())


class TestAnalyzePythonSource(unittest.TestCase):
    def test_error_de_sintaxis(self):
        result = analyze_python_source("def broken(:\n")
        self.assertIn("syntax_error", result)
        self.assertNotIn("metrics", result)

    def test_linea_larga_es_issue_low(self):
        result = analyze_python_source('x = "' + "a" * 130 + '"\n')
        issues = result["metrics"]["issues"]
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["severity"], "low")
        self.assertEqual(issues[0]["category"], "style")
        self.assertIn("línea demasiado larga", issues[0]["description"])

    def test_importaciones_multiples_es_issue_medium(self):
        result = analyze_python_source("import os, sys\n")
        issues = result["metrics"]["issues"]
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["severity"], "medium")
        self.assertIn("importaciones múltiples", issues[0]["description"])

    def test_fuente_vacia_sin_funciones(self):
        result = analyze_python_source("")
        self.assertEqual(result["metrics"]["total_lines"], 0)
        self.assertEqual(result["metrics"]["total_functions"], 0)
        self.assertEqual(result["metrics"]["total_classes"], 0)
        self.assertEqual(result["metrics"]["issues"], [])

    def test_cuenta_funciones_clases_y_complejidad(self):
        source = (
            "class A:\n"
            "    def m(self, items):\n"
            "        for i in items:\n"
            "            if i:\n"
            "                try:\n"
            "                    pass\n"
            "                except ValueError:\n"
            "                    pass\n"
            "def g(n):\n"
            "    while n:\n"
            "        n -= 1\n"
        )
        result = analyze_python_source(source)
        summary = result["source_summary"]
        self.assertEqual(summary["functions"], 2)
        self.assertEqual(summary["classes"], 1)
        # complejidad: for+if+try en m() = 3, while en g() = 1
        self.assertEqual(summary["complexity"], 4)
        self.assertIn("efficiency_score", result["metrics"])

    def test_cuenta_async_y_no_duplica_anidados(self):
        source = (
            "async def f(items):\n"
            "    async for i in items:\n"
            "        if i:\n"
            "            def interna():\n"
            "                if True:\n"
            "                    return 1\n"
            "            return interna\n"
        )
        result = analyze_python_source(source)
        summary = result["source_summary"]
        self.assertEqual(summary["functions"], 2)
        self.assertEqual(summary["complexity"], 3)

    def test_efficiency_score_acotado(self):
        result = analyze_python_source("import os, sys\n")
        self.assertLessEqual(result["metrics"]["efficiency_score"], 1.0)
        self.assertGreater(result["metrics"]["efficiency_score"], 0.0)


class TestAnalyzePythonCode(unittest.TestCase):
    def test_archivo_inexistente_devuelve_error(self):
        result = analyze_python_code("no_existe.py")
        self.assertIn("error", result)
        self.assertIn("no_existe.py", result["error"])

    def test_archivo_real(self):
        fd, path = tempfile.mkstemp(suffix=".py")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write("def suma(a, b):\n    return a + b\n")
            result = analyze_python_code(path)
        finally:
            os.unlink(path)
        self.assertEqual(result["source_summary"]["functions"], 1)
        self.assertEqual(result["source_summary"]["total_lines"], 2)


class TestMain(unittest.TestCase):
    def test_main_offline_completa(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            cdt.main()
        salida = buffer.getvalue()
        self.assertIn("ANÁLISIS ESTÁTICO DE EJEMPLO DE CÓDIGO", salida)
        self.assertIn("ANÁLISIS COMPLETADO", salida)
        self.assertIn("REPORTE MARKDOWN", salida)

    def test_main_ejecuta_analisis_estatico_sobre_la_demo(self):
        # Sin esta línea de progreso, el orquestador no recibió la fuente demo.
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            cdt.main()
        self.assertIn(">>> Análisis estático:", buffer.getvalue())


class TestCodeAnalysisContextDetalle(unittest.TestCase):
    def test_init_valores_por_defecto(self):
        ctx = CodeAnalysisContext("proyecto")
        self.assertEqual(ctx.max_issues, 20)
        self.assertEqual(ctx.metrics, {})
        self.assertEqual(ctx.design_decisions, [])
        self.assertIsInstance(ctx.start_time, float)
        self.assertLessEqual(ctx.start_time, time.time())

    def test_max_issues_por_defecto_es_20(self):
        ctx = CodeAnalysisContext("proyecto")
        for i in range(21):
            ctx.add_issue("style", "low", f"issue {i}")
        self.assertEqual(len(ctx.issues), 20)

    def test_add_issue_claves_exactas_y_reasoning_vacio(self):
        ctx = CodeAnalysisContext("proyecto")
        ctx.add_issue("style", "low", "desc")
        issue = ctx.issues[0]
        self.assertEqual(set(issue), {
            "category", "severity", "description", "file", "line",
            "suggestion", "thinking_reasoning", "detected_at",
        })
        self.assertEqual(issue["category"], "style")
        self.assertEqual(issue["thinking_reasoning"], "")

    def test_add_thinking_step_claves_y_valores(self):
        ctx = CodeAnalysisContext("proyecto")
        ctx.add_thinking_step("paso1", "razonamiento", {"r": 1})
        entry = ctx.thinking_steps[0]
        self.assertEqual(set(entry), {"step", "reasoning", "result", "timestamp"})
        self.assertEqual(entry["step"], "paso1")
        self.assertEqual(entry["reasoning"], "razonamiento")
        self.assertEqual(entry["result"], {"r": 1})
        self.assertIsInstance(entry["timestamp"], float)

    def test_to_dict_project_path_y_desglose_high(self):
        ctx = CodeAnalysisContext("proyecto")
        ctx.add_issue("security", "high", "h")
        d = ctx.to_dict()
        self.assertEqual(d["project_path"], "proyecto")
        self.assertEqual(d["issue_breakdown"]["high"], 1)

    def test_to_dict_low_cuenta_solo_severidad_low(self):
        ctx = CodeAnalysisContext("proyecto")
        ctx.add_issue("style", "low", "l1")
        ctx.add_issue("style", "low", "l2")
        self.assertEqual(ctx.to_dict()["issue_breakdown"]["low"], 2)

    def test_efficiency_score_acotado_a_1_con_muchos_issues(self):
        ctx = CodeAnalysisContext("proyecto", max_issues=40)
        for i in range(40):
            ctx.add_issue("style", "low", f"issue {i}")
        self.assertEqual(ctx.to_dict()["efficiency_score"], 1.0)


class TestThinkingEngineInit(unittest.TestCase):
    def test_nombre_por_defecto(self):
        thinker = CodeDesignThinker(llm_provider=MockLLM())
        self.assertEqual(thinker.name, "thinking_decision_engine")

    def test_init_propaga_nombre_y_max_steps_al_motor_base(self):
        thinker = CodeDesignThinker(name="propio", llm_provider=MockLLM(),
                                    max_steps=3)
        self.assertEqual(thinker.name, "propio")
        self.assertEqual(thinker.max_steps, 3)
        self.assertEqual(thinker.max_thinking_steps, 3)


class CicloGrabador(CodeDesignThinker):
    """Doble: registra los argumentos que `decide` pasa al ciclo (SIMULADO)."""

    def __init__(self):
        super().__init__(llm_provider=MockLLM())
        self.recibidos = None

    def _execute_thinking_cycle(self, context, prompt, progress=None):
        self.recibidos = (context, prompt, progress)
        return {"valid": True, "step_count": 0, "steps": []}


class TestDecidePasaArgumentos(unittest.TestCase):
    def test_decide_pasa_contexto_prompt_y_progress(self):
        thinker = CicloGrabador()
        contexto = CodeAnalysisContext("p")
        progreso = []
        thinker.decide(contexto, "código fuente", progress=progreso.append)
        self.assertIs(thinker.recibidos[0], contexto)
        self.assertEqual(thinker.recibidos[1], "código fuente")
        self.assertEqual(thinker.recibidos[2], progreso.append)


class TestResultadosDetalle(unittest.TestCase):
    def test_resultado_invalido_a_mitad_de_ciclo_renderiza_pasos_previos(self):
        llm = StubLLM(lambda p: "" if "PASO 3" in p
                      else "texto válido con contenido suficiente")
        result = CodeDesignThinker(llm_provider=llm).decide(
            CodeAnalysisContext("p"), "código")
        self.assertFalse(result["valid"])
        self.assertIn("PASO 1 - ANÁLISIS", result["thought"])
        self.assertIn("PASO 2 - OBJETIVOS", result["thought"])
        # Los 2 pasos registrados tienen contenido: confianza plena.
        self.assertEqual(result["confidence"], 1.0)

    def test_resultado_invalido_tiene_claves_exactas(self):
        thinker = CodeDesignThinker(llm_provider=StubLLM(lambda p: ""))
        result = thinker.decide(CodeAnalysisContext("p"), "código")
        self.assertEqual(set(result), {
            "thought", "decision", "confidence", "valid", "invalid_steps",
            "steps", "step_count", "error",
        })
        self.assertEqual(thinker.step_count, 0)

    def test_render_steps_con_pasos_es_multilinea_exacta(self):
        thinker = CodeDesignThinker(name="t", llm_provider=MockLLM())
        render = thinker._render_steps([("analysis", "contenido del paso")])
        self.assertEqual(render.split("\n"), [
            "        CAPA DE PENSAMIENTO DISEÑO: t",
            "        ========================================",
            "",
            "        PASO 1 - ANÁLISIS: contenido del paso",
            "",
            "        PASOS COMPLETADOS: 1/7",
            "        DECISIÓN FINAL: None",
            "        CONFIANZA: 1.0",
        ])

    def test_render_steps_trunca_contenido_a_150(self):
        thinker = CodeDesignThinker(name="t", llm_provider=MockLLM())
        contenido = "x" * 200
        render = thinker._render_steps([("analysis", contenido)])
        linea_paso = render.split("\n")[3]
        self.assertEqual(linea_paso, "        PASO 1 - ANÁLISIS: " + "x" * 150)


class TestOrchestratorDetalle(unittest.TestCase):
    def test_init_valores_por_defecto(self):
        orq = CodeImprovementOrchestrator(CodeDesignThinker(llm_provider=MockLLM()))
        self.assertEqual(orq.source_code, "")
        self.assertEqual(orq.context.project_path, "project_analysis")
        self.assertEqual(orq.results, {})

    def test_analyze_and_improve_muestra_el_progreso(self):
        orq = CodeImprovementOrchestrator(
            CodeDesignThinker(llm_provider=MockLLM()), source_code="x = 1")
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            orq.analyze_and_improve()
        salida = buffer.getvalue()
        self.assertIn(">>> Ciclo de pensamiento de diseño...", salida)
        self.assertIn(">>> Análisis estático:", salida)

    def test_resultados_por_fase_tienen_claves_y_valores_exactos(self):
        llm = StubLLM(lambda p: "texto válido con contenido suficiente")
        orq = CodeImprovementOrchestrator(
            CodeDesignThinker(llm_provider=llm), source_code="x = 1")
        r = orq.run_analysis()
        esperado = {
            "thought": "texto válido con contenido suficiente",
            "decision": "texto válido con contenido suficiente",
            "confidence": 1.0,
            "valid": True,
            "invalid_steps": [],
            "steps": [("selection", "texto válido con contenido suficiente")],
            "step_count": 1,
            "error": None,
        }
        self.assertEqual(r["selection"], esperado)

    def test_decide_recibe_el_contexto_y_la_fuente(self):
        thinker = CicloGrabador()
        orq = CodeImprovementOrchestrator(thinker, source_code="x = 1")
        orq.run_analysis()
        self.assertIs(thinker.recibidos[0], orq.context)
        self.assertEqual(thinker.recibidos[1], "x = 1")

    def test_error_de_sintaxis_notifica_por_progreso(self):
        orq = CodeImprovementOrchestrator(
            CodeDesignThinker(llm_provider=MockLLM()),
            source_code="def broken(:\n")
        mensajes = []
        orq.run_analysis(progress=mensajes.append)
        self.assertEqual(len(mensajes), 1)
        self.assertIn("error de sintaxis", mensajes[0])

    def test_report_lines_con_resultados_minimos_usa_na(self):
        orq = CodeImprovementOrchestrator(
            CodeDesignThinker(llm_provider=MockLLM()))
        orq.results = {
            "total_thinking_steps": 0,
            "efficiency_principle": "P",
            "project_metrics": {"total_issues": 0, "efficiency_score": 0.0},
        }
        self.assertEqual(orq.report_lines(), [
            "# Análisis y Mejora de Proyecto de Código",
            "",
            "## Resumen Ejecutivo",
            "- **Pasos de pensamiento**: 0",
            "- **Problemas identificados**: 0",
            "- **Score de eficiencia**: 0.00",
            "- **Principio rector**: P",
            "",
            "## Problemas Detectados",
            "## Decisiones de Diseño",
            "- **Enfoque seleccionado**: N/A",
            "- **Confianza**: N/A",
            "",
            "## Plan de Implementación",
            "",
            "## Criterios de Validación",
            "- **Decisión de validación**: N/A",
            "- **Confianza**: N/A",
            "",
            "---",
            "*Generado por sistema de diseño de código con capa de pensamiento estructurado*",
            "*Pasos deliberados: 0/7*",
        ])

    def test_report_lines_trunca_pasos_a_80_y_acepta_strings(self):
        orq = CodeImprovementOrchestrator(
            CodeDesignThinker(llm_provider=MockLLM()))
        orq.results = {
            "total_thinking_steps": 1,
            "efficiency_principle": "P",
            "project_metrics": {"total_issues": 0, "efficiency_score": 0.0},
            "implementation_plan": {"steps": [("plan", "y" * 100), "z" * 100]},
        }
        lineas = orq.report_lines()
        self.assertIn("1. " + "y" * 80, lineas)
        self.assertIn("2. " + "z" * 80, lineas)


class TestAnalyzePythonSourceDetalle(unittest.TestCase):
    def test_syntax_error_contiene_el_mensaje_real(self):
        result = analyze_python_source("def broken(:\n")
        self.assertIn("invalid syntax", result["syntax_error"])

    def test_metricas_incluyen_max_nesting_a_cero(self):
        result = analyze_python_source("x = 1\n")
        self.assertEqual(result["metrics"]["max_nesting"], 0)

    def test_cuenta_cada_clase(self):
        result = analyze_python_source("class A:\n    pass\nclass B:\n    pass\n")
        self.assertEqual(result["source_summary"]["classes"], 2)

    def test_issue_linea_larga_campos_exactos(self):
        result = analyze_python_source('x = "' + "a" * 130 + '"\n')
        issue = result["metrics"]["issues"][0]
        self.assertEqual(issue["suggestion"],
                         "Dividir línea o reestructurar código")
        self.assertEqual(issue["thinking_reasoning"],
                         "Eficiencia: líneas largas reducen legibilidad")

    def test_issue_importaciones_campos_exactos(self):
        result = analyze_python_source("import os, sys\n")
        issue = result["metrics"]["issues"][0]
        self.assertEqual(issue["suggestion"],
                         "Separar importaciones en líneas individuales")
        self.assertEqual(
            issue["thinking_reasoning"],
            "Mantenimiento: importaciones separadas son más fáciles de modificar")

    def test_efficiency_score_tope_en_1(self):
        fuente = "".join(f'x{i} = "' + "a" * 130 + '"\n' for i in range(31))
        result = analyze_python_source(fuente)
        self.assertEqual(len(result["metrics"]["issues"]), 31)
        self.assertEqual(result["metrics"]["efficiency_score"], 1.0)


if __name__ == "__main__":
    unittest.main()
