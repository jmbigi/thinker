import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import evaluar_proyecto
from tests.helpers import crear_historial_git, entorno_git


class TestEntornoGit(unittest.TestCase):
    def test_no_hereda_el_indice_del_hook(self):
        with tempfile.TemporaryDirectory() as tmp, \
                tempfile.TemporaryDirectory() as ajeno:
            raiz = Path(tmp)
            (raiz / "demo.py").write_text("x = 1\n", encoding="utf-8")
            sentinela = Path(ajeno) / "indice"
            with patch.dict(os.environ, {"GIT_INDEX_FILE": str(sentinela),
                                         "GIT_DIR": "/no/existe"}):
                self.assertNotIn("GIT_INDEX_FILE", entorno_git())
                crear_historial_git(raiz, 0)
                self.assertEqual(len(evaluar_proyecto._git(
                    raiz, "log", "--oneline").splitlines()), 1)
            self.assertFalse(sentinela.exists())
            registro = subprocess.run(
                ["git", "-C", str(raiz), "log", "--oneline"],
                env=entorno_git(), capture_output=True, text=True, check=True)
            self.assertEqual(len(registro.stdout.splitlines()), 1)
