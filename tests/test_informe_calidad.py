"""Contrato del informe de calidad (`scripts/informe_calidad.py`): controles
reales del repo, estados honestos y sin marcar como PASS lo no ejecutado."""

import json
import unittest

import scripts.informe_calidad as ic


class TestInformeCalidad(unittest.TestCase):
    def test_los_controles_son_comandos_reales_del_repo(self):
        nombres = [n for n, _ in ic.CONTROLES]
        self.assertEqual(nombres, ["ruff", "preflight", "docs-check", "tests",
                                   "holdout", "secrets", "doctor"])

    def test_solo_ejecuta_un_control_y_declara_el_resto(self):
        informe = ic.generar(solo="ruff")
        self.assertEqual(list(informe["controles"]), ["ruff"])
        self.assertEqual(informe["controles"]["ruff"]["estado"], "PASS")
        self.assertIn("preflight", informe["no_ejecutados"])
        self.assertIn("commit", informe)
        self.assertIn("python", informe)

    def test_un_comando_inexistente_es_not_run(self):
        resultado = ic._ejecutar_control(
            "x", ["/ruta/que/no/existe/binario"])
        self.assertEqual(resultado["estado"], "NOT_RUN")

    def test_un_fallo_es_fail_no_pass(self):
        resultado = ic._ejecutar_control(
            "x", [__import__("sys").executable, "-c", "raise SystemExit(3)"])
        self.assertEqual(resultado["estado"], "FAIL")
        self.assertEqual(resultado["codigo"], 3)

    def test_el_json_es_serializable(self):
        texto = json.dumps(ic.generar(solo="ruff"))
        self.assertIn('"estado": "PASS"', texto)


if __name__ == "__main__":
    unittest.main()
