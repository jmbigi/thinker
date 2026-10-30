"""Contratos offline de datasets externos y atribución."""

import contextlib
import io
import json
import re
import tempfile
import unittest
from pathlib import Path

from tests.benchmarks import external


class _LLMPerfecto:
    def __init__(self, veredictos):
        self.veredictos = veredictos

    def generate(self, prompt, model=None, **kwargs):
        coincidencia = re.search(r"^Claim: (.*)$", prompt, re.M)
        claim = coincidencia.group(1).strip() if coincidencia else ""
        return json.dumps({
            "verdict": self.veredictos.get(claim, "not_addressed"),
            "credibility": 0.9,
            "confidence": 0.9,
        })


class TestBenchmarkExterno(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)

    def _jsonl(self, registros, nombre="dataset.jsonl"):
        ruta = self.raiz / nombre
        ruta.write_text("\n".join(json.dumps(r) for r in registros) + "\n",
                        encoding="utf-8")
        return str(ruta)

    def test_carga_formato_oficial_drb(self):
        ruta = self._jsonl([
            {"id": 1, "topic": "Science & Technology", "language": "en", "prompt": "Research A"},
            {"id": 2, "topic": "Otro", "language": "zh", "prompt": "Research B"},
        ])
        tareas = external.load_drb_tasks(ruta, max_tasks=1)
        self.assertEqual(len(tareas), 1)
        self.assertEqual(tareas[0].id, "1")
        self.assertEqual(tareas[0].question, "Research A")
        self.assertEqual(tareas[0].domain, "science_tech")
        self.assertEqual(tareas[0].metadata["external"], "DeepResearch Bench")

    def test_raw_data_conserva_contrato_oficial(self):
        ruta = self._jsonl([
            {"id": 1, "topic": "Otro", "language": "en", "prompt": "Research A"},
            {"id": 2, "topic": "Otro", "language": "en", "prompt": "Research B"},
        ])
        tareas = external.load_drb_tasks(ruta)

        def investigar(pregunta):
            return {"report": f"Informe sobre {pregunta}", "sources": []}

        resultado = external.run_drb(tareas, investigar, str(self.raiz / "salida"))

        self.assertFalse(resultado["official_race_fact"])
        self.assertEqual(resultado["summary"]["total_tasks"], 2)
        lineas = [json.loads(linea) for linea in
                  Path(resultado["raw_data"]).read_text(encoding="utf-8").splitlines()]
        self.assertEqual(lineas[0], {
            "id": "1", "prompt": "Research A", "article": "Informe sobre Research A"})
        self.assertEqual(lineas[1]["id"], "2")

    def test_jsonl_invalido_indica_linea(self):
        ruta = self.raiz / "roto.jsonl"
        ruta.write_text('{"id": 1}\nno-json\n', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "roto.jsonl:2"):
            external.load_jsonl(str(ruta))

    def test_atribucion_mide_aciertos_y_falsos_verificados(self):
        casos = [
            {"id": 1, "claim": "A es cierto", "passage": "A es cierto", "expected": "supported"},
            {"id": 2, "claim": "B es cierto", "passage": "B es falso", "expected": "contradicted"},
            {"id": 3, "claim": "C es cierto", "passage": "Otro tema", "expected": "insufficient"},
        ]
        ruta = self._jsonl(casos)
        cargados = external.load_attribution_cases(ruta)
        veredictos = {caso["claim"]: external.MAPA_ESPERADO[caso["categoria"]]
                      for caso in cargados}
        resultado = external.evaluar_atribucion(cargados, _LLMPerfecto(veredictos))
        self.assertEqual(resultado["metricas"]["exactitud"], 1.0)
        self.assertEqual(resultado["metricas"]["falsos_verificados"], 0)
        self.assertEqual(resultado["metricas"]["tasa_abstencion"], 1.0)

        simulado = external.evaluar_atribucion(cargados)
        self.assertIn("no mide calidad real", simulado["modo"])
        self.assertEqual(simulado["metricas"]["falsos_verificados"], 2)

    def test_cli_drb_declara_modo_simulado(self):
        ruta = self._jsonl([
            {"id": 1, "topic": "Otro", "language": "en", "prompt": "Research A"},
        ])
        salida = io.StringIO()
        with contextlib.redirect_stdout(salida):
            codigo = external.main([
                "--dataset", ruta, "--kind", "drb", "--provider", "mock",
                "--max-tasks", "1", "--output", str(self.raiz / "bench"), "--json",
            ])
        self.assertEqual(codigo, 0)
        resultado = json.loads(salida.getvalue())
        self.assertIn("no mide calidad real", resultado["modo"])


if __name__ == "__main__":
    unittest.main()
