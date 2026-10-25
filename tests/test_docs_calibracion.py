"""R14: la confianza no calibrada debe declararse en README y AGENTS."""

import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


class TestCalibracionDeclarada(unittest.TestCase):
    def test_readme_y_agents_no_presentan_confianza_como_probabilidad(self):
        for nombre in ("README.md", "AGENTS.md"):
            texto = " ".join(
                (RAIZ / nombre).read_text(encoding="utf-8").lower().split())
            self.assertIn("no están calibradas", texto, nombre)
            self.assertIn("brier", texto, nombre)
            self.assertIn("probabilidad", texto, nombre)


if __name__ == "__main__":
    unittest.main()
