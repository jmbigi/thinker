"""Pruebas offline del evaluador local de código generado."""

import unittest

from code_evaluator import CodeEvaluator, TestCase


class TestCodeEvaluator(unittest.TestCase):
    def setUp(self):
        self.ev = CodeEvaluator()

    def test_sintaxis_valida_sin_casos(self):
        r = self.ev.evaluate_generated_code("def suma(a,b):\n    return a+b\n")
        self.assertTrue(r.syntax_ok)
        self.assertTrue(r.passed)
        self.assertEqual(r.failures, [])

    def test_sintaxis_invalida_falla(self):
        r = self.ev.evaluate_generated_code("def roto(:\n    pass\n")
        self.assertFalse(r.syntax_ok)
        self.assertFalse(r.passed)
        self.assertTrue(any("SyntaxError" in f for f in r.failures))

    def test_caso_args_stdout_pasa(self):
        code = (
            "import sys\n"
            "a,b=int(sys.argv[1]),int(sys.argv[2])\n"
            "print(a+b)\n"
        )
        r = self.ev.evaluate_generated_code(
            code, [TestCase(name="add", input_data=["1", "2"], expected_output="3\n")]
        )
        self.assertTrue(r.passed, r.failures)

    def test_caso_falla_con_evidencia(self):
        code = "print('no')\n"
        r = self.ev.evaluate_generated_code(
            code, [TestCase(name="x", expected_output="si\n")]
        )
        self.assertFalse(r.passed)
        self.assertTrue(r.failures)

    def test_error_esperado(self):
        code = "raise ValueError('boom')\n"
        r = self.ev.evaluate_generated_code(
            code, [TestCase(name="err", expected_error=True)]
        )
        self.assertTrue(r.passed, r.failures)

    def test_lenguaje_no_soportado(self):
        r = self.ev.evaluate_generated_code("puts 1", language="ruby")
        self.assertFalse(r.passed)
        self.assertFalse(r.syntax_ok)

    def test_timeout_reportado(self):
        code = "import time\ntime.sleep(2)\n"
        r = self.ev.evaluate_generated_code(
            code, [TestCase(name="t", timeout_seconds=0.1)]
        )
        self.assertFalse(r.passed)
        self.assertIn("timeout", r.failures[0])


if __name__ == "__main__":
    unittest.main()
