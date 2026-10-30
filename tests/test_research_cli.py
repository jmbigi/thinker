"""Pruebas offline de la CLI real de investigación."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from research_cli import main


class TestResearchCLI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)

    def _run(self, args):
        salida = io.StringIO()
        errores = io.StringIO()
        with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(errores):
            codigo = main(args)
        return codigo, salida.getvalue(), errores.getvalue()

    def test_json_es_consumible_y_diagnostico_va_a_stderr(self):
        codigo, salida, errores = self._run(["Energía solar", "--format", "json"])
        self.assertEqual(codigo, 0)
        datos = json.loads(salida)
        self.assertTrue(datos["completed"])
        self.assertEqual(datos["question"], "Energía solar")
        self.assertIn("SIMULADO", errores)
        self.assertIn("Completado:", errores)

    def test_documentos_locales_conservan_procedencia(self):
        documento = self.raiz / "solar.txt"
        documento.write_text("Energía solar distribuida y paneles fotovoltaicos",
                             encoding="utf-8")
        codigo, salida, _ = self._run([
            "Energía solar", "--documents", str(documento), "--format", "json"])
        self.assertEqual(codigo, 0)
        datos = json.loads(salida)
        self.assertTrue(datos["sources"])
        self.assertEqual(datos["sources"][0]["source"], "local-document")
        self.assertIn("sha256", datos["sources"][0])

    def test_output_y_checkpoint_se_reanudan(self):
        informe = self.raiz / "informe.md"
        estado = self.raiz / "estado.json"
        args = ["pregunta", "--output", str(informe), "--state", str(estado)]
        primero, _, _ = self._run(args)
        contenido = informe.read_text(encoding="utf-8")
        segundo, salida, _ = self._run(args)
        self.assertEqual((primero, segundo), (0, 0))
        self.assertEqual(informe.read_text(encoding="utf-8"), contenido)
        self.assertEqual(salida, "")
        self.assertTrue(json.loads(estado.read_text())["completed"])

    def test_presupuesto_agotado_es_error_visible(self):
        codigo, salida, errores = self._run(["pregunta", "--max-llm-calls", "1"])
        self.assertEqual(codigo, 2)
        self.assertEqual(salida, "")
        self.assertIn("Presupuesto de llamadas LLM agotado", errores)

    def test_full_text_rechaza_fuentes_mock(self):
        codigo, _, errores = self._run(["pregunta", "--full-text"])
        self.assertEqual(codigo, 2)
        self.assertIn("fuentes ficticias", errores)

    def test_busqueda_local_exige_documentos(self):
        codigo, _, errores = self._run(["pregunta", "--search", "local"])
        self.assertEqual(codigo, 2)
        self.assertIn("exige", errores)

    def test_conectores_exigen_configuracion_explicita(self):
        codigo, _, errores = self._run(["pregunta", "--search", "mcp"])
        self.assertEqual(codigo, 2)
        self.assertIn("--mcp-command", errores)
        codigo, _, errores = self._run(["pregunta", "--search", "searxng"])
        self.assertEqual(codigo, 2)
        self.assertIn("SEARXNG_URL", errores)

    def test_full_text_no_aplica_a_documentos_locales(self):
        documento = self.raiz / "doc.txt"
        documento.write_text("contenido", encoding="utf-8")
        codigo, _, errores = self._run([
            "pregunta", "--documents", str(documento), "--full-text"])
        self.assertEqual(codigo, 2)
        self.assertIn("no aplica", errores)


if __name__ == "__main__":
    unittest.main()
