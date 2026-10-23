"""Holdout del auditor: casos que no viven en la suite principal."""

import unittest

from scripts.audit_changes import auditar_diff


def _diff(ruta, lineas):
    texto = (f"diff --git a/{ruta} b/{ruta}\n"
             f"--- a/{ruta}\n+++ b/{ruta}\n"
             f"@@ -1 +1,{len(lineas)} @@\n")
    return texto + "".join(f"{prefijo}{contenido}\n"
                           for prefijo, contenido in lineas)


class TestAuditorHoldout(unittest.TestCase):
    def test_skip_bloquea(self):
        informe = auditar_diff(_diff("tests/test_x.py", [
            ("+", '@pytest.mark.skip(reason="flaky")'),
        ]))

        self.assertEqual(informe["veredicto"], "BLOQUEAR")

    def test_env_bloquea(self):
        informe = auditar_diff(_diff(".env", [("+", "TOKEN=valor")]))

        self.assertEqual(informe["veredicto"], "BLOQUEAR")

    def test_diff_limpio_ok(self):
        informe = auditar_diff(_diff("app.py", [
            ("-", "x = 1"), ("+", "x = 2"),
        ]))

        self.assertEqual(informe["veredicto"], "OK")


if __name__ == "__main__":
    unittest.main()
