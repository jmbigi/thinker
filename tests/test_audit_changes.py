"""Tests del auditor de cambios: diffs sintéticos, offline y deterministas."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts.audit_changes import (OpcionesAuditoria, auditar_diff,
                                   informe_texto, main, parsear_diff)


def _diff(ruta, lineas=(), nuevo=False, borrado=False):
    """Construye un diff unificado mínimo; `lineas` son (prefijo, texto)."""
    texto = f"diff --git a/{ruta} b/{ruta}\n"
    if nuevo:
        texto += f"new file mode 100644\n--- /dev/null\n+++ b/{ruta}\n"
    elif borrado:
        texto += f"deleted file mode 100644\n--- a/{ruta}\n+++ /dev/null\n"
    else:
        texto += f"--- a/{ruta}\n+++ b/{ruta}\n"
    texto += "@@ -1,1 +1,1 @@\n"
    texto += "".join(f"{prefijo}{contenido}\n" for prefijo, contenido in lineas)
    return texto


class TestAuditorDeCambios(unittest.TestCase):
    def _reglas(self, informe):
        return [hallazgo["regla"] for hallazgo in informe["hallazgos"]]

    def test_diff_limpio_es_ok(self):
        informe = auditar_diff(_diff("app.py", [("-", "x = 1"), ("+", "x = 2")]))

        self.assertEqual(informe["veredicto"], "OK")
        self.assertEqual(informe["hallazgos"], [])
        self.assertIn("Sin señales", informe_texto(informe))

    def test_skip_real_bloquea(self):
        informe = auditar_diff(_diff("tests/test_app.py", [
            ("+", '@pytest.mark.skip(reason="flaky")'),
            (" ", "def test_ok():"),
            (" ", "    assert 1 == 1"),
        ]))

        self.assertEqual(informe["veredicto"], "BLOQUEAR")
        self.assertIn("skip_añadido", self._reglas(informe))

    def test_skip_comentado_no_bloquea(self):
        informe = auditar_diff(_diff("tests/test_app.py", [
            ("+", '# @pytest.mark.skip(reason="flaky")'),
            (" ", "def test_ok():"),
        ]))

        self.assertNotIn("skip_añadido", self._reglas(informe))
        self.assertEqual(informe["veredicto"], "REVISAR")

    def test_asserts_eliminados_bloquea(self):
        informe = auditar_diff(_diff("tests/test_app.py", [
            (" ", "def test_ok():"),
            ("-", "    assert 1 == 1"),
            ("+", "    pass"),
        ]))

        self.assertEqual(informe["veredicto"], "BLOQUEAR")
        self.assertIn("asserts_eliminados", self._reglas(informe))

    def test_test_borrado_bloquea_incluso_si_permitido(self):
        informe = auditar_diff(
            _diff("tests/test_app.py", [("-", "def test_ok():"),
                                        ("-", "    assert True")],
                  borrado=True),
            OpcionesAuditoria(permitir=["tests"]))

        self.assertEqual(informe["veredicto"], "BLOQUEAR")
        self.assertIn("test_borrado", self._reglas(informe))

    def test_test_eliminado_es_revisar(self):
        informe = auditar_diff(_diff("tests/test_app.py", [
            ("-", "def test_viejo():"),
            ("-", "    assert True"),
            (" ", "def test_nuevo():"),
            (" ", "    assert True"),
        ]))

        self.assertEqual(informe["veredicto"], "REVISAR")
        self.assertIn("test_eliminado", self._reglas(informe))

    def test_matcher_flojo_es_revisar(self):
        informe = auditar_diff(_diff("tests/test_app.py", [
            (" ", "def test_ok():"),
            ("-", "    self.assertEqual(valor, 1)"),
            ("+", "    self.assertTrue(valor)"),
        ]))

        self.assertEqual(informe["veredicto"], "REVISAR")
        self.assertIn("matcher_flojo", self._reglas(informe))

    def test_supresion_global_bloquea(self):
        informe = auditar_diff(_diff("app.py", [
            ("+", "x = 1  # type: ignore"),
        ]))

        self.assertEqual(informe["veredicto"], "BLOQUEAR")
        self.assertIn("supresion_global", self._reglas(informe))

    def test_cobertura_rebajada_bloquea(self):
        informe = auditar_diff(_diff("pyproject.toml", [
            ("-", "fail_under = 90"),
            ("+", "fail_under = 40"),
        ]))

        self.assertEqual(informe["veredicto"], "BLOQUEAR")
        self.assertIn("cobertura_rebajada", self._reglas(informe))

    def test_config_relajada_bloquea(self):
        informe = auditar_diff(_diff("tsconfig.json", [
            ("-", '  "strict": true'),
            ("+", '  "strict": false'),
        ]))

        self.assertEqual(informe["veredicto"], "BLOQUEAR")
        self.assertIn("config_relajada", self._reglas(informe))

    def test_dependencia_nueva_es_revisar(self):
        informe = auditar_diff(_diff("requirements.txt", [
            ("+", "nueva-dependencia==1.0"),
        ]))

        self.assertEqual(informe["veredicto"], "REVISAR")
        self.assertIn("dependencia_nueva", self._reglas(informe))
        self.assertIn("manifiesto", self._reglas(informe))

    def test_requisitos_modificados_es_revisar(self):
        informe = auditar_diff(_diff("docs/REQUISITOS.md", [
            ("+", "- Criterio de aceptación: nuevo"),
        ]))

        self.assertEqual(informe["veredicto"], "REVISAR")
        self.assertIn("requisitos_modificados", self._reglas(informe))

    def test_ci_modificado_bloquea(self):
        informe = auditar_diff(_diff(".github/workflows/ci.yml", [
            ("+", "  continue-on-error: true"),
        ]))

        self.assertEqual(informe["veredicto"], "BLOQUEAR")
        self.assertIn("ci_hooks", self._reglas(informe))

    def test_presupuesto_de_archivos_es_revisar(self):
        texto = (_diff("app.py", [("+", "x = 1")]) +
                 _diff("otro.py", [("+", "y = 2")]))
        informe = auditar_diff(texto, OpcionesAuditoria(max_archivos=1))

        self.assertEqual(informe["veredicto"], "REVISAR")
        self.assertIn("presupuesto_archivos", self._reglas(informe))

    def test_permitir_tests_no_oculta_un_skip(self):
        informe = auditar_diff(_diff("tests/test_app.py", [
            ("+", '@pytest.mark.skip(reason="flaky")'),
            (" ", "def test_ok():"),
        ]), OpcionesAuditoria(permitir=["tests"]))

        self.assertEqual(informe["veredicto"], "BLOQUEAR")
        self.assertIn("skip_añadido", self._reglas(informe))
        self.assertNotIn("tests_modificados", self._reglas(informe))

    def test_redacta_secretos_en_la_evidencia(self):
        informe = auditar_diff(_diff("scripts/deploy.sh", [
            ("+", "git push --force https://x?token=SECRETO123"),
        ]))
        serializado = json.dumps(informe, ensure_ascii=False)

        self.assertEqual(informe["veredicto"], "BLOQUEAR")
        self.assertIn("comando_peligroso", self._reglas(informe))
        self.assertNotIn("SECRETO123", serializado)

    def test_ruta_sensible_bloquea(self):
        informe = auditar_diff(_diff(".env", [("+", "API_KEY=valor")]))

        self.assertEqual(informe["veredicto"], "BLOQUEAR")
        self.assertIn("ruta_sensible", self._reglas(informe))

    def test_lockfile_es_revisar(self):
        informe = auditar_diff(_diff("requirements.lock", [
            ("+", "requests==2.31.0"),
        ]))

        self.assertEqual(informe["veredicto"], "REVISAR")
        self.assertIn("lockfile", self._reglas(informe))

    def test_test_nuevo_sin_asserts_es_revisar(self):
        informe = auditar_diff(_diff("tests/test_nuevo.py", [
            ("+", "def test_nuevo():"),
            ("+", "    pass"),
        ], nuevo=True))

        self.assertEqual(informe["veredicto"], "REVISAR")
        self.assertIn("test_sin_asserts", self._reglas(informe))

    def test_eval_exec_es_revisar(self):
        informe = auditar_diff(_diff("app.py", [
            ("+", 'resultado = eval("1")'),
        ]))

        self.assertEqual(informe["veredicto"], "REVISAR")
        self.assertIn("eval_exec", self._reglas(informe))

    def test_supresion_especifica_es_revisar(self):
        informe = auditar_diff(_diff("app.py", [
            ("+", "x = 1  # noqa: E501"),
        ]))

        self.assertEqual(informe["veredicto"], "REVISAR")
        self.assertIn("supresion_especifica", self._reglas(informe))

    def test_presupuesto_de_lineas_es_revisar(self):
        informe = auditar_diff(_diff("app.py", [
            ("+", "x = 1"), ("+", "y = 2"), ("+", "z = 3"),
        ]), OpcionesAuditoria(max_lineas=1))

        self.assertEqual(informe["veredicto"], "REVISAR")
        self.assertIn("presupuesto_lineas", self._reglas(informe))

    def test_reglas_modificadas_es_revisar(self):
        informe = auditar_diff(_diff("AGENTS.md", [("+", "nueva regla")]))

        self.assertEqual(informe["veredicto"], "REVISAR")
        self.assertIn("reglas_modificadas", self._reglas(informe))

    def test_archivo_eliminado_es_revisar(self):
        informe = auditar_diff(_diff("docs/guia.md", [("-", "texto")],
                                     borrado=True))

        self.assertEqual(informe["veredicto"], "REVISAR")
        self.assertIn("archivo_eliminado", self._reglas(informe))

    def test_holdout_modificado_es_revisar(self):
        informe = auditar_diff(_diff("holdout/test_x.py", [
            ("+", "assert True"),
        ]))

        self.assertEqual(informe["veredicto"], "REVISAR")
        self.assertIn("holdout_modificado", self._reglas(informe))

    def test_parsear_diff_multiples_archivos(self):
        texto = (_diff("app.py", [("+", "x = 1")]) +
                 _diff("tests/test_app.py", [("+", "assert True")]))

        archivos = parsear_diff(texto)

        self.assertEqual([a.ruta for a in archivos],
                         ["app.py", "tests/test_app.py"])

    def test_cli_json_y_codigo_de_salida(self):
        with tempfile.TemporaryDirectory() as tmp:
            archivo = Path(tmp) / "cambios.diff"
            archivo.write_text(_diff("tests/test_app.py", [
                ("+", '@pytest.mark.skip(reason="flaky")'),
            ]), encoding="utf-8")
            salida = io.StringIO()
            with contextlib.redirect_stdout(salida):
                codigo = main(["--diff", str(archivo), "--json"])
            datos = json.loads(salida.getvalue())

        self.assertEqual(codigo, 1)
        self.assertEqual(datos["veredicto"], "BLOQUEAR")
        self.assertEqual(datos["fuente"], str(archivo))

    def test_cli_fallar_en_bloquear_permite_revisar(self):
        with tempfile.TemporaryDirectory() as tmp:
            archivo = Path(tmp) / "cambios.diff"
            archivo.write_text(_diff("docs/REQUISITOS.md", [
                ("+", "- nuevo requisito"),
            ]), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                codigo = main(["--diff", str(archivo), "--fallar-en",
                               "bloquear"])

        self.assertEqual(codigo, 0)


if __name__ == "__main__":
    unittest.main()
