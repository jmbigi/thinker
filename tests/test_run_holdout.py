"""Tests del runner de holdout: hashes, manifiesto y ejecución offline."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts.run_holdout import (actualizar_manifiesto, calcular_hashes,
                                 ejecutar_tests, verificar_hashes)


class TestRunnerDeHoldout(unittest.TestCase):
    def _dir(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return Path(tmp.name)

    def test_actualiza_y_verifica_hashes(self):
        directorio = self._dir()
        (directorio / "test_a.py").write_text("x = 1\n", encoding="utf-8")
        manifiesto = directorio / "HASHES.json"

        datos = actualizar_manifiesto(directorio, manifiesto)

        self.assertEqual(datos["version"], 1)
        self.assertEqual(verificar_hashes(directorio, manifiesto),
                         calcular_hashes(directorio))
        guardado = json.loads(manifiesto.read_text(encoding="utf-8"))
        self.assertIn("test_a.py", guardado["files"])

    def test_detecta_hash_cambiado(self):
        directorio = self._dir()
        archivo = directorio / "test_a.py"
        archivo.write_text("x = 1\n", encoding="utf-8")
        manifiesto = directorio / "HASHES.json"
        actualizar_manifiesto(directorio, manifiesto)
        archivo.write_text("x = 2\n", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "cambiados"):
            verificar_hashes(directorio, manifiesto)

    def test_detecta_archivo_extra(self):
        directorio = self._dir()
        (directorio / "test_a.py").write_text("x = 1\n", encoding="utf-8")
        manifiesto = directorio / "HASHES.json"
        actualizar_manifiesto(directorio, manifiesto)
        (directorio / "test_b.py").write_text("y = 2\n", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "sobran"):
            verificar_hashes(directorio, manifiesto)

    def test_detecta_archivo_faltante(self):
        directorio = self._dir()
        archivo = directorio / "test_a.py"
        archivo.write_text("x = 1\n", encoding="utf-8")
        manifiesto = directorio / "HASHES.json"
        actualizar_manifiesto(directorio, manifiesto)
        archivo.unlink()

        with self.assertRaisesRegex(ValueError, "faltan"):
            verificar_hashes(directorio, manifiesto)

    def test_manifiesto_ausente_es_error(self):
        directorio = self._dir()
        (directorio / "test_a.py").write_text("x = 1\n", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "No existe el manifiesto"):
            verificar_hashes(directorio, directorio / "HASHES.json")

    def test_ejecuta_tests_ok(self):
        directorio = self._dir()
        (directorio / "test_ok.py").write_text(
            "import unittest\n\n\n"
            "class T(unittest.TestCase):\n"
            "    def test_ok(self):\n"
            "        self.assertTrue(True)\n", encoding="utf-8")

        with contextlib.redirect_stderr(io.StringIO()):
            correcto = ejecutar_tests(directorio)

        self.assertTrue(correcto)

    def test_ejecuta_tests_falla(self):
        directorio = self._dir()
        (directorio / "test_mal.py").write_text(
            "import unittest\n\n\n"
            "class T(unittest.TestCase):\n"
            "    def test_mal(self):\n"
            "        self.assertEqual(1, 2)\n", encoding="utf-8")

        with contextlib.redirect_stderr(io.StringIO()):
            correcto = ejecutar_tests(directorio)

        self.assertFalse(correcto)

    def test_sin_tests_es_error(self):
        directorio = self._dir()

        with self.assertRaisesRegex(ValueError, "No hay tests holdout"):
            ejecutar_tests(directorio)

    def test_error_de_importacion_es_ruidoso(self):
        directorio = self._dir()
        (directorio / "test_roto.py").write_text(
            'raise RuntimeError("boom")\n', encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "No se pudo importar"):
            ejecutar_tests(directorio)


if __name__ == "__main__":
    unittest.main()
