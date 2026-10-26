"""Contrato de la cadena de salvaguardas (P0.1, P1.1, P1.26).

Un gate que desaparece del hook o de `make check` deja de proteger sin que
nadie lo note. Estos tests convierten la cadena en un contrato verificable:
si se retira una comprobación, falla la suite en vez de degradarse en silencio.
"""

import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

GATES_PRE_COMMIT = (
    "ruff check .",
    "scripts/scan-secrets.sh",
    "py_compile",
    "scripts/preflight.py",
    "scripts/check_docs.py",
    "unittest discover -s tests",
    "audit_changes.py --staged",
    "scripts/run_holdout.py",
)


class TestCadenaDeSalvaguardas(unittest.TestCase):
    def test_pre_commit_no_pierde_gates(self):
        texto = (RAIZ / "scripts" / "hooks" / "pre-commit").read_text(
            encoding="utf-8")

        for gate in GATES_PRE_COMMIT:
            self.assertIn(gate, texto)

    def test_make_check_agrega_los_gates(self):
        texto = (RAIZ / "Makefile").read_text(encoding="utf-8")

        self.assertIn("check: lint preflight docs-check test secrets ci", texto)
        self.assertIn("scripts/hooks/pre-commit", texto)


if __name__ == "__main__":
    unittest.main()
