"""Tests de scripts/doctor.py (offline, deterministas): el autodiagnóstico
debe pasar en el entorno de desarrollo y su lista de variables de proveedores
debe coincidir con las que llm_providers.py consulta de verdad.
"""

import contextlib
import io
import re
import unittest
from pathlib import Path

import scripts.doctor as doctor

RAIZ = Path(__file__).resolve().parent.parent


class TestDoctor(unittest.TestCase):
    def test_entorno_de_desarrollo_sin_fallos_esenciales(self):
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            codigo = doctor.main([])
        salida = buf.getvalue()
        self.assertEqual(codigo, 0, salida)
        self.assertIn("Python >= 3.11", salida)
        self.assertIn("plugins descubiertos", salida)
        self.assertNotIn("✗", salida)

    def test_nunca_imprime_valores_de_claves(self):
        # Aunque una clave esté definida, la salida solo declara presencia.
        clave = "TEST_DOCTOR_CLAVE_FALSA"
        valor = "sk-valor-secreto-12345"
        import os
        os.environ[clave] = valor
        try:
            with contextlib.redirect_stdout(io.StringIO()) as buf:
                doctor.main([])
            self.assertNotIn(valor, buf.getvalue())
        finally:
            del os.environ[clave]

    def test_variables_coinciden_con_las_fuentes_que_las_consultan(self):
        # llm_providers.py consulta las claves de proveedor; OLLAMA_MODEL es
        # del runner opt-in test_ollama_real.py. Si aparece una variable nueva,
        # doctor.py debe listarla.
        usadas = set()
        for archivo in ("llm_providers.py", "test_ollama_real.py"):
            fuente = (RAIZ / archivo).read_text(encoding="utf-8")
            usadas |= set(re.findall(r'os\.environ\.get\("([A-Z_]+)"', fuente))
        declaradas = set(doctor.VARIABLES_PROVEEDORES)
        self.assertEqual(usadas, declaradas,
                         "doctor.py debe listar exactamente las variables que "
                         "el código consulta")

    def test_con_red_es_opt_in(self):
        # Sin --con-red no se abren sockets: la sección de sondas no aparece.
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            doctor.main([])
        self.assertNotIn("Sondas de red", buf.getvalue())

    def test_consola_sin_unicode_no_revienta(self):
        # Consolas cp1252 (Windows CI): las marcas caen a ASCII y el
        # diagnóstico termina sin UnicodeEncodeError.
        import subprocess
        proc = subprocess.run(
            [__import__("sys").executable, "scripts/doctor.py"],
            cwd=RAIZ, capture_output=True, encoding="cp1252",
            errors="replace",
            env={**__import__("os").environ, "PYTHONIOENCODING": "cp1252"},
            timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr[-500:])
        self.assertNotIn("UnicodeEncodeError", proc.stderr)
        self.assertIn("[OK]", proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
