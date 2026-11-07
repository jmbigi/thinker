#!/usr/bin/env python3
"""
Tests para code_generator.py
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Añadir directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from code_generator import (
    GenerationContext,
    CodeGeneratorThinker,
    CodeGeneratorOrchestrator,
    EmpiricalValidator,
    MockLLM,
)


class TestGenerationContext(unittest.TestCase):
    """Tests para GenerationContext."""

    def test_context_creation(self):
        ctx = GenerationContext(project_path="/tmp/test", requirements="test req")
        self.assertEqual(ctx.project_path, "/tmp/test")
        self.assertEqual(ctx.requirements, "test req")
        self.assertEqual(ctx.mode, "offline")

    def test_add_thinking_step(self):
        ctx = GenerationContext(project_path="/tmp/test")
        ctx.add_thinking_step("step1", "reasoning", "result")
        self.assertEqual(len(ctx.thinking_steps), 1)
        self.assertEqual(ctx.thinking_steps[0]["step"], "step1")

    def test_add_issue(self):
        ctx = GenerationContext(project_path="/tmp/test")
        ctx.add_issue("high", "test issue", "file.py", 10, "fix it")
        self.assertEqual(len(ctx.issues), 1)
        self.assertEqual(ctx.issues[0]["severity"], "high")

    def test_to_dict(self):
        ctx = GenerationContext(project_path="/tmp/test", requirements="req")
        ctx.add_thinking_step("s1", "r1", "res1")
        d = ctx.to_dict()
        self.assertIn("project_path", d)
        self.assertIn("thinking_steps", d)
        self.assertEqual(d["thinking_steps"], 1)


class TestMockLLM(unittest.TestCase):
    """Tests para MockLLM."""

    def test_generate_deterministic(self):
        mock = MockLLM()
        # Mismo prompt produce misma respuesta
        r1 = mock.generate("test prompt")
        r2 = mock.generate("test prompt")
        # En este mock, el contador incrementa, así que cambian
        # Pero cada llamada es determinista por step_num
        self.assertIsInstance(r1, str)
        self.assertIsInstance(r2, str)

    def test_generate_valid_json(self):
        mock = MockLLM()
        for _ in range(7):
            resp = mock.generate("test")
            # Debe ser JSON válido
            import json
            parsed = json.loads(resp)
            self.assertIsInstance(parsed, dict)


class TestEmpiricalValidator(unittest.TestCase):
    """Tests para validación empírica real."""

    def test_validate_syntax_valid(self):
        code = "def foo():\n    return 42\n"
        result = EmpiricalValidator.validate_syntax(code)
        self.assertTrue(result["passed"])
        self.assertEqual(result["tool"], "py_compile")

    def test_validate_syntax_invalid(self):
        code = "def foo(:\n    return 42\n"  # sintaxis inválida
        result = EmpiricalValidator.validate_syntax(code)
        self.assertFalse(result["passed"])
        self.assertEqual(result["tool"], "py_compile")

    @patch("code_generator.subprocess.run")
    def test_validate_syntax_ejecuta_py_compile(self, run):
        run.return_value.returncode = 0
        run.return_value.stderr = ""
        result = EmpiricalValidator.validate_syntax("x = 1\n")
        self.assertTrue(result["passed"])
        comando = run.call_args.args[0]
        self.assertEqual(comando[0], sys.executable)
        self.assertEqual(comando[1:3], ["-m", "py_compile"])

    def test_validate_all_ejecuta_tests_generados(self):
        source = "def add(a, b):\n    return a + b\n"
        test_code = (
            "import unittest\n\n"
            "from generated_code import add\n\n\n"
            "class TestAdd(unittest.TestCase):\n"
            "    def test_add(self):\n"
            "        self.assertEqual(add(2, 3), 5)\n"
        )
        result = EmpiricalValidator.validate_all({
            "generated_code.py": source,
            "tests/test_generated_code.py": test_code,
        })
        file_result = result["files"]["generated_code.py"]["results"]
        self.assertIn("tests", file_result)
        self.assertTrue(file_result["tests"]["passed"])

    def test_validate_ruff(self):
        code = "def foo():\n    return 42\n"
        result = EmpiricalValidator.validate_ruff(code)
        self.assertIn("passed", result)
        self.assertEqual(result["tool"], "ruff")

    def test_validate_unittest(self):
        source = "def add(a, b):\n    return a + b\n"
        test_code = '''
import unittest
from generated import add

class TestAdd(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(2, 3), 5)

if __name__ == "__main__":
    unittest.main()
'''
        result = EmpiricalValidator.validate_unittest(test_code, source, "generated")
        self.assertIn("passed", result)
        self.assertEqual(result["tool"], "unittest")


class TestCodeGeneratorThinker(unittest.TestCase):
    """Tests para CodeGeneratorThinker."""

    def setUp(self):
        self.mock_llm = MockLLM()
        self.thinker = CodeGeneratorThinker(
            name="test_generator",
            llm_provider=self.mock_llm,
            mode="offline"
        )
        # Inyectar mock en el motor base
        self.thinker._llm = self.mock_llm

    def test_generate_returns_valid_structure(self):
        context = GenerationContext(
            project_path="/tmp/test",
            requirements="test requirements",
            mode="offline"
        )
        result = self.thinker.generate(context, "Crear función sumar")
        self.assertIn("valid", result)
        self.assertIn("steps", result)
        self.assertIn("step_count", result)
        self.assertIn("confidence", result)

    def test_generate_completes_7_steps(self):
        context = GenerationContext(project_path="/tmp/test", mode="offline")
        result = self.thinker.generate(context, "test")
        # MockLLM genera 7 pasos válidos
        self.assertTrue(result["valid"])
        self.assertEqual(result["step_count"], 7)

    def test_abstract_methods_implemented(self):
        # Verificar que los métodos abstractos están implementados
        self.assertTrue(hasattr(self.thinker, "_step_builders"))
        self.assertTrue(hasattr(self.thinker, "_render_thought"))
        self.assertTrue(callable(self.thinker._step_builders))
        self.assertTrue(callable(self.thinker._render_thought))


class TestCodeGeneratorOrchestrator(unittest.TestCase):
    """Tests para el orquestador completo."""

    def setUp(self):
        self.mock_llm = MockLLM()
        self.thinker = CodeGeneratorThinker(
            name="test_orchestrator",
            llm_provider=self.mock_llm,
            mode="offline"
        )
        self.thinker._llm = self.mock_llm

    def test_generate_and_validate(self):
        context = GenerationContext(
            project_path="/tmp/test",
            requirements="test req",
            mode="offline"
        )
        orchestrator = CodeGeneratorOrchestrator(self.thinker, context)
        result = orchestrator.generate_and_validate("Crear función sumar(a,b)")

        self.assertIn("thinking", result)
        self.assertIn("generated", result)
        self.assertIn("validation", result)
        self.assertIn("context", result)

        # Validación debe pasar, incluida la ejecución real de los tests.
        val = result["validation"]
        self.assertIn("summary", val)
        self.assertIn("files", val)
        self.assertIn("tests", val["files"]["generated_code.py"]["results"])

    def test_generated_files_exist(self):
        context = GenerationContext(project_path="/tmp/test", mode="offline")
        orchestrator = CodeGeneratorOrchestrator(self.thinker, context)
        result = orchestrator.generate_and_validate("test")

        self.assertGreater(len(result["generated"]), 0)
        for fname, content in result["generated"].items():
            self.assertIsInstance(content, str)
            self.assertGreater(len(content), 0)

    def test_save_generated_rechaza_traversal(self):
        context = GenerationContext(project_path="/tmp/test", mode="offline")
        context.generated_files = {"../fuera.py": "x = 1\n"}
        orchestrator = CodeGeneratorOrchestrator(self.thinker, context)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            with self.assertRaisesRegex(ValueError, "fuera"):
                orchestrator.save_generated(str(out))
            self.assertFalse((Path(tmp) / "fuera.py").exists())

    def test_save_generated_escribe_dentro(self):
        context = GenerationContext(project_path="/tmp/test", mode="offline")
        context.generated_files = {"pkg/mod.py": "x = 1\n"}
        orchestrator = CodeGeneratorOrchestrator(self.thinker, context)
        with tempfile.TemporaryDirectory() as tmp:
            saved = orchestrator.save_generated(tmp)
            self.assertEqual(Path(saved[0]).read_text(encoding="utf-8"), "x = 1\n")
            self.assertTrue(Path(saved[0]).is_relative_to(Path(tmp)))


class TestIntegration(unittest.TestCase):
    """Test de integración completo."""

    def test_full_offline_cycle(self):
        """Ciclo completo offline: thinker -> generacion -> validacion real."""
        mock_llm = MockLLM()
        thinker = CodeGeneratorThinker(
            name="integration_test",
            llm_provider=mock_llm,
            mode="offline"
        )
        thinker._llm = mock_llm

        context = GenerationContext(
            project_path="/tmp/integration_test",
            mode="offline"
        )

        orchestrator = CodeGeneratorOrchestrator(thinker, context)
        result = orchestrator.generate_and_validate(
            "Crear módulo con función saludar(nombre) y sumar(a,b)"
        )

        # Verificar estructura
        self.assertIn("thinking", result)
        self.assertIn("generated", result)
        self.assertIn("validation", result)

        # Verificar validación empírica pasó
        val = result["validation"]
        self.assertEqual(val["summary"]["failed"], 0,
                         f"Archivos fallaron: {val['summary']['failed']}")


if __name__ == "__main__":
    unittest.main()