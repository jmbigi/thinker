"""Tests del núcleo puro del orquestador de código (sin capturar stdout).

Al separar `run_analysis`/`report_lines` de la presentación, la lógica se puede
comprobar por valores y efectos exactos en vez de por "no revienta".
"""

import unittest

from code_design_improvement_tools import (CodeDesignThinker,
                                           CodeImprovementOrchestrator)
from deep_research_system import MockLLM
from tests.helpers import StubLLM

FUENTE = "import os, sys\nx = 1\n"


def _orquestador(fuente=FUENTE, thinker=None):
    return CodeImprovementOrchestrator(
        thinker or CodeDesignThinker(name="t", llm_provider=MockLLM()),
        source_code=fuente)


class TestRunAnalysisNucleo(unittest.TestCase):

    def test_no_imprime_nada(self):
        import contextlib
        import io
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            _orquestador().run_analysis()
        self.assertEqual(buffer.getvalue(), "")

    def test_devuelve_todas_las_claves_y_guarda_en_self(self):
        orq = _orquestador()
        r = orq.run_analysis()
        self.assertEqual(set(r), {
            "analysis", "objectives", "design_options_considered", "evaluations",
            "selection", "implementation_plan", "validation_criteria",
            "total_thinking_steps", "efficiency_principle", "project_metrics",
        })
        self.assertIs(orq.results, r)

    def test_alimenta_el_contexto_con_el_analisis_estatico(self):
        orq = _orquestador()
        r = orq.run_analysis()
        self.assertEqual(r["project_metrics"]["total_issues"], 1)
        self.assertEqual(orq.context.metrics["functions"], 0)
        self.assertEqual(orq.context.issues[0]["severity"], "medium")

    def test_sin_codigo_fuente_no_hay_issues_ni_metricas(self):
        r = _orquestador(fuente="").run_analysis()
        self.assertEqual(r["project_metrics"]["total_issues"], 0)
        self.assertEqual(r["project_metrics"]["issues"], [])

    def test_progreso_recibe_los_mensajes_esperados(self):
        mensajes = []
        _orquestador().run_analysis(progress=mensajes.append)
        self.assertEqual(mensajes[0], ">>> Análisis estático: 1 issues detectados")
        self.assertEqual(mensajes[1], ">>> PASO 1: Análisis estructurado del código...")
        self.assertEqual(mensajes[-1], "   pasos=7 válido=True")
        pasos = [m for m in mensajes if m.startswith(">>> PASO")]
        self.assertEqual(len(pasos), 7)
        self.assertTrue(pasos[-1].startswith(">>> PASO 7: Definir criterios"))

    def test_total_de_pasos_y_principio_rector(self):
        r = _orquestador().run_analysis()
        self.assertEqual(r["total_thinking_steps"], 7)
        self.assertEqual(r["efficiency_principle"], "Hacer las cosas de manera eficiente")

    def test_paso_1_invalido_devuelve_error_sin_resultados(self):
        orq = _orquestador(thinker=CodeDesignThinker(
            name="t", llm_provider=StubLLM(lambda p: "")))
        r = orq.run_analysis()
        self.assertIn("error", r)
        self.assertIn("falló", r["error"])
        self.assertEqual(r["steps"][0][0], "fallido")
        self.assertEqual(orq.results, {}, "no debe haber resultados parciales")


class TestReportLinesNucleo(unittest.TestCase):

    def setUp(self):
        self.orq = _orquestador()
        self.orq.run_analysis()
        self.lineas = self.orq.report_lines()

    def test_cabecera_y_resumen_exactos(self):
        self.assertEqual(self.lineas[0], "# Análisis y Mejora de Proyecto de Código")
        self.assertEqual(self.lineas[1], "")
        self.assertEqual(self.lineas[2], "## Resumen Ejecutivo")
        self.assertEqual(self.lineas[3], "- **Pasos de pensamiento**: 7")
        self.assertEqual(self.lineas[4], "- **Problemas identificados**: 1")
        self.assertEqual(self.lineas[5], "- **Score de eficiencia**: 0.03")
        self.assertEqual(self.lineas[6],
                         "- **Principio rector**: Hacer las cosas de manera eficiente")

    def test_bloque_de_problema_con_sugerencia_y_separador(self):
        i = self.lineas.index("## Problemas Detectados")
        self.assertEqual(
            self.lineas[i + 1],
            "- **[MEDIUM]** Línea 1: importaciones múltiples en una línea")
        self.assertEqual(
            self.lineas[i + 2],
            "  - Sugerencia: Separar importaciones en líneas individuales")
        self.assertEqual(self.lineas[i + 3], "")

    def test_secciones_de_decisiones_y_plan(self):
        self.assertIn("## Decisiones de Diseño", self.lineas)
        self.assertIn("- **Enfoque seleccionado**: decision_from_validation", self.lineas)
        self.assertIn("- **Confianza**: 1.0", self.lineas)
        self.assertIn("## Plan de Implementación", self.lineas)
        pasos = [linea for linea in self.lineas
                 if linea[:2] in ("1.", "2.", "3.", "4.", "5.", "6.")]
        self.assertEqual(len(pasos), 5, "el reporte muestra como máximo 5 pasos")
        self.assertTrue(pasos[0].startswith("1. "))

    def test_pie_de_validacion_exacto(self):
        self.assertIn("## Criterios de Validación", self.lineas)
        self.assertIn("- **Decisión de validación**: decision_from_validation", self.lineas)
        self.assertIn("---", self.lineas)
        self.assertEqual(self.lineas[-1], "*Pasos deliberados: 7/7*")

    def test_plan_sin_lista_de_pasos(self):
        self.orq.results["implementation_plan"] = {"steps": "no es lista"}
        self.assertIn("No steps detail available", self.orq.report_lines())

    def test_issue_sin_sugerencia_no_añade_linea(self):
        self.orq.results["project_metrics"]["issues"] = [
            {"severity": "low", "description": "sin sugerencia"}]
        lineas = self.orq.report_lines()
        i = lineas.index("- **[LOW]** sin sugerencia")
        self.assertEqual(lineas[i + 1], "")

    def test_entradas_no_dict_se_ignoran(self):
        self.orq.results["project_metrics"]["issues"] = ["texto suelto", {"severity": "low"}]
        lineas = self.orq.report_lines()
        self.assertNotIn("texto suelto", "\n".join(lineas))
        self.assertFalse(any(linea.startswith("- **[LOW]**") for linea in lineas))


class TestGenerateReportUnion(unittest.TestCase):

    def test_une_con_salto_de_linea(self):
        orq = _orquestador()
        orq.run_analysis()
        self.assertEqual(orq.generate_report(), "\n".join(orq.report_lines()))

    def test_sin_resultados_avisa(self):
        orq = _orquestador()
        self.assertEqual(orq.generate_report(), "No results to report.")


if __name__ == "__main__":
    unittest.main()
