"""Tests del clasificador de triaje de mutantes (R3)."""

import json
import tempfile
import unittest
from pathlib import Path

from scripts.triaje_mutantes import _ejecutadas, _rangos_de_funciones


class TestTriajeMutantes(unittest.TestCase):
    def test_rangos_de_funciones(self):
        rangos = _rangos_de_funciones("def a():\n    pass\n\n\ndef b():\n    return 1\n")
        self.assertEqual(rangos["a"], [1, 2])
        self.assertEqual(rangos["b"], [5, 6])

    def test_ejecutadas(self):
        with tempfile.TemporaryDirectory() as d:
            ruta = Path(d) / "coverage.json"
            ruta.write_text(json.dumps({"files": {"x.py": {"executed_lines": [2, 3]}}}),
                            encoding="utf-8")
            self.assertEqual(_ejecutadas(ruta, "x.py"), {2, 3})
            self.assertEqual(_ejecutadas(ruta, "no.py"), set())


if __name__ == "__main__":
    unittest.main()
