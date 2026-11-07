"""Tests del escáner de secretos portable (scripts/scan_secrets.py)."""

import io
import contextlib
import subprocess
import sys
import unittest
from pathlib import Path

from tests.helpers import crear_proyecto
import scripts.scan_secrets as scan


def _ejecutar(raiz):
    with contextlib.redirect_stdout(io.StringIO()) as buf:
        codigo = scan.main(["--root", str(raiz)])
    return codigo, buf.getvalue()


class TestScanSecrets(unittest.TestCase):
    # Los canarios se construyen en runtime: escribirlos literales haría que
    # ESTE archivo disparara el escáner del repo (auto-referencia).
    CANARIO_CLAVE = "sk-" + "CANARIO" + "0123456789abcdef"
    CANARIO_RUTA = "/home/" + "persona-real" + "/proyecto"

    def test_arbol_limpio_pasa(self):
        raiz = crear_proyecto(self, {
            "app.py": "API_KEY = os.environ.get('OPENAI_API_KEY')\n",
            "README.md": "Usa `OPENAI_API_KEY` en el entorno.\n",
        })
        codigo, salida = _ejecutar(raiz)
        self.assertEqual(codigo, 0, salida)
        self.assertIn("OK", salida)

    def test_clave_canaria_falla_y_se_muestra(self):
        raiz = crear_proyecto(self, {
            "fuga.py": f"TOKEN = '{self.CANARIO_CLAVE}'\n",
        })
        codigo, salida = _ejecutar(raiz)
        self.assertEqual(codigo, 1)
        self.assertIn("fuga.py", salida)
        self.assertIn("Posibles credenciales", salida)

    def test_ruta_personal_falla(self):
        raiz = crear_proyecto(self, {
            "nota.md": f"ruta: {self.CANARIO_RUTA}\n",
        })
        codigo, salida = _ejecutar(raiz)
        self.assertEqual(codigo, 1)
        self.assertIn("datos personales", salida)

    def test_placeholder_no_es_hallazgo(self):
        raiz = crear_proyecto(self, {
            ".env.example": "OPENAI_API_KEY=...\nOTRA=\n",
        })
        codigo, _ = _ejecutar(raiz)
        self.assertEqual(codigo, 0)

    def test_sin_git_escanea_arbol_y_no_dice_ok_por_defecto(self):
        """La copia limpia de CI no tiene .git: se escanea el árbol y se avisa."""
        raiz = crear_proyecto(self, {
            "fuga.py": f"TOKEN = '{self.CANARIO_CLAVE}'\n",
        })
        script = Path(__file__).resolve().parent.parent / "scripts" / "scan_secrets.py"
        proc = subprocess.run(
            [sys.executable, str(script)], cwd=raiz,
            capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("fuga.py", proc.stdout + proc.stderr)
        self.assertIn("no es un repositorio git", proc.stderr)


if __name__ == "__main__":
    unittest.main()
