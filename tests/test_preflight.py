"""Tests de scripts/preflight.py: gates deterministas, fixtures y repo real."""

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from scripts.preflight import archivos_python, ejecutar, main
import scripts.preflight as preflight_mod
from tests.helpers import crear_proyecto

RAIZ_THINKER = Path(__file__).resolve().parent.parent

# Dos funciones con el MISMO cuerpo sustancial (5 sentencias, 61 nodos AST):
# el gate debe detectar la segunda como duplicado de la primera.
DUPLICADO_SUSTANCIAL = (
    "def suma_a(x):\n"
    "    total = 0\n"
    "    for i in range(x):\n"
    "        if i % 2 == 0:\n"
    "            total += i\n"
    "        else:\n"
    "            total -= i\n"
    "    for j in range(x):\n"
    "        total += j\n"
    "    resultado = {\"total\": total, \"x\": x}\n"
    "    return resultado\n"
    "\n"
    "def suma_b(x):\n"
    "    total = 0\n"
    "    for i in range(x):\n"
    "        if i % 2 == 0:\n"
    "            total += i\n"
    "        else:\n"
    "            total -= i\n"
    "    for j in range(x):\n"
    "        total += j\n"
    "    resultado = {\"total\": total, \"x\": x}\n"
    "    return resultado\n"
)


class TestPreflight(unittest.TestCase):
    def _gates(self, informe):
        return {gate["nombre"]: gate for gate in informe["gates"]}

    def test_proyecto_limpio_pasa(self):
        raiz = crear_proyecto(self, {
            "paquete/__init__.py": "",
            "paquete/mod.py": "import os\nimport requests\n",
            "requirements.txt": "requests==2.31.0\n",
        })

        informe = ejecutar(raiz)

        self.assertTrue(informe["ok"])
        self.assertEqual(informe["evidencia"], "verified-real")
        self.assertEqual(informe["total_hallazgos"], 0)
        self.assertTrue(all(gate["ok"] for gate in informe["gates"]))

    def test_import_no_declarado_falla_con_archivo_y_linea(self):
        raiz = crear_proyecto(self, {"app.py": "\nimport modulo_fantasma\n"})

        informe = ejecutar(raiz)
        imports = self._gates(informe)["imports"]

        self.assertFalse(informe["ok"])
        self.assertEqual(len(imports["hallazgos"]), 1)
        hallazgo = imports["hallazgos"][0]
        self.assertEqual(hallazgo["archivo"], "app.py")
        self.assertEqual(hallazgo["linea"], 2)
        self.assertIn("modulo_fantasma", hallazgo["mensaje"])
        self.assertEqual(hallazgo["tipo_evidencia"], "verified-real")

    def test_import_local_y_stdlib_no_necesita_manifiesto(self):
        raiz = crear_proyecto(self, {
            "helpers.py": "VALOR = 1\n",
            "app.py": "import os\nimport helpers\n",
        })

        self.assertTrue(ejecutar(raiz)["ok"])

    def test_pyproject_declara_dependencias(self):
        raiz = crear_proyecto(self, {
            "pyproject.toml": ("[project]\nname = \"x\"\n"
                               "dependencies = [\"requests>=2\"]\n"),
            "app.py": "import requests\n",
        })

        self.assertTrue(ejecutar(raiz)["ok"])

    def test_alias_dotenv_reconoce_python_dotenv(self):
        raiz = crear_proyecto(self, {
            "requirements.txt": "python-dotenv==1.0.0\n",
            "app.py": "import dotenv\n",
        })

        self.assertTrue(ejecutar(raiz)["ok"])

    def test_allow_permite_un_import_extra(self):
        raiz = crear_proyecto(self, {"app.py": "import modulo_extra\n"})

        self.assertFalse(ejecutar(raiz)["ok"])
        self.assertTrue(ejecutar(raiz, permitidos=["modulo_extra"])["ok"])

    def test_silencio_con_pass_falla(self):
        raiz = crear_proyecto(self, {
            "app.py": ("def f():\n"
                       "    try:\n"
                       "        return 1\n"
                       "    except Exception:\n"
                       "        pass\n"),
        })

        silencios = self._gates(ejecutar(raiz))["silencios"]

        self.assertEqual(len(silencios["hallazgos"]), 1)
        self.assertEqual(silencios["hallazgos"][0]["linea"], 4)
        self.assertIn("P1.26", silencios["hallazgos"][0]["mensaje"])

    def test_silencio_con_ellipsis_falla(self):
        raiz = crear_proyecto(self, {
            "app.py": ("def f():\n"
                       "    try:\n"
                       "        return 1\n"
                       "    except ValueError:\n"
                       "        ...\n"),
        })

        self.assertFalse(ejecutar(raiz)["ok"])

    def test_except_que_reporta_no_falla(self):
        raiz = crear_proyecto(self, {
            "app.py": ("def f():\n"
                       "    try:\n"
                       "        return 1\n"
                       "    except ValueError as exc:\n"
                       "        raise RuntimeError(\"fallo\") from exc\n"),
        })

        self.assertTrue(ejecutar(raiz)["ok"])

    def test_duplicado_sustancial_falla(self):
        raiz = crear_proyecto(self, {"app.py": DUPLICADO_SUSTANCIAL})

        duplicados = self._gates(ejecutar(raiz))["duplicados"]

        self.assertEqual(len(duplicados["hallazgos"]), 1)
        hallazgo = duplicados["hallazgos"][0]
        self.assertEqual(hallazgo["archivo"], "app.py")
        self.assertIn("suma_a", hallazgo["mensaje"])
        self.assertIn("suma_b", hallazgo["mensaje"])

    def test_duplicado_trivial_no_falla(self):
        raiz = crear_proyecto(self, {
            "app.py": ("def a():\n"
                       "    return 42\n"
                       "\n"
                       "def b():\n"
                       "    return 42\n"),
        })

        self.assertTrue(ejecutar(raiz)["ok"])

    def test_tarea_asyncio_sin_referencia_falla(self):
        raiz = crear_proyecto(self, {
            "app.py": ("import asyncio\n\n"
                       "async def tarea():\n"
                       "    return 1\n\n"
                       "async def main():\n"
                       "    asyncio.create_task(tarea())\n"),
        })

        tareas = self._gates(ejecutar(raiz))["tareas"]

        self.assertEqual(len(tareas["hallazgos"]), 1)
        self.assertIn("create_task", tareas["hallazgos"][0]["mensaje"])

    def test_tarea_asyncio_guardada_no_falla(self):
        raiz = crear_proyecto(self, {
            "app.py": ("import asyncio\n\n"
                       "async def tarea():\n"
                       "    return 1\n\n"
                       "async def main():\n"
                       "    guardada = asyncio.create_task(tarea())\n"
                       "    await guardada\n"),
        })

        self.assertTrue(ejecutar(raiz)["ok"])

    def test_sintaxis_rota_falla_sin_crash(self):
        raiz = crear_proyecto(self, {"roto.py": "def f(:\n    pass\n"})

        informe = ejecutar(raiz)
        sintaxis = self._gates(informe)["sintaxis"]

        self.assertFalse(informe["ok"])
        self.assertEqual(sintaxis["hallazgos"][0]["archivo"], "roto.py")
        self.assertIn("error de sintaxis", sintaxis["hallazgos"][0]["mensaje"])

    def test_pyproject_invalido_falla_sin_crash(self):
        raiz = crear_proyecto(self, {
            "pyproject.toml": "[project\n",
            "app.py": "import os\n",
        })

        informe = ejecutar(raiz)

        self.assertFalse(informe["ok"])
        self.assertIn("TOML inválido",
                      self._gates(informe)["imports"]["hallazgos"][0]["mensaje"])

    def test_cli_json_y_codigo_de_salida(self):
        raiz = crear_proyecto(self, {"app.py": "import modulo_fantasma\n"})
        salida = io.StringIO()

        with redirect_stdout(salida):
            codigo = main(["--root", str(raiz), "--json"])
        informe = json.loads(salida.getvalue())

        self.assertEqual(codigo, 1)
        self.assertFalse(informe["ok"])
        self.assertEqual(informe["total_hallazgos"], 1)

    def test_cli_limpio_devuelve_cero(self):
        raiz = crear_proyecto(self, {"app.py": "import os\n"})
        salida = io.StringIO()

        with redirect_stdout(salida):
            codigo = main(["--root", str(raiz)])

        self.assertEqual(codigo, 0)
        self.assertIn("PREFLIGHT: OK", salida.getvalue())

    def test_cli_ruta_inexistente_devuelve_dos(self):
        salida = io.StringIO()
        error = io.StringIO()
        with redirect_stdout(salida), redirect_stderr(error):
            codigo = main(["--root", "/ruta/que/no/existe"])

        self.assertEqual(codigo, 2)
        self.assertIn("no es un directorio", error.getvalue())

    def test_ignora_scripts_locales_de_depuracion(self):
        raiz = crear_proyecto(self, {
            "app.py": "import os\n",
            "_local_debug/check.py": ("try:\n"
                                      "    valor = 1\n"
                                      "except Exception:\n"
                                      "    pass\n"),
        })

        self.assertTrue(ejecutar(raiz)["ok"])

    def test_setup_cfg_y_setup_py_declaran_imports(self):
        raiz = crear_proyecto(self, {
            "app.py": "import requests\nimport sphinx\n",
            "setup.cfg": ("[options]\ninstall_requires =\n"
                          "    requests==2.31.0\n"
                          "[options.extras_require]\ndocs =\n"
                          "    sphinx==7.0\n"),
            "setup.py": ("setup(install_requires=['urllib3==2.0'],\n"
                         "      extras_require={'extra': ['pyyaml==6.0']})\n"),
        })

        informe = ejecutar(raiz)

        self.assertTrue(informe["ok"], [
            hallazgo for gate in informe["gates"]
            for hallazgo in gate["hallazgos"]])

    def test_setup_cfg_invalido_es_hallazgo_de_imports(self):
        raiz = crear_proyecto(self, {
            "app.py": "import requests\n",
            "setup.cfg": "[options\ninstall_requires = requests\n",
        })

        informe = ejecutar(raiz)
        imports = self._gates(informe)["imports"]

        self.assertFalse(informe["ok"])
        self.assertTrue(any("setup.cfg inválido" in h["mensaje"]
                            for h in imports["hallazgos"]))

    def test_alias_pywin32_no_es_falso_positivo(self):
        raiz = crear_proyecto(self, {
            "app.py": "import win32api\n",
            "pyproject.toml": ('[project]\nname = "x"\nversion = "0.1.0"\n'
                               'dependencies = ["pywin32"]\n'),
        })

        self.assertTrue(ejecutar(raiz)["ok"])

    def test_ignora_venvs_alternativos_temporales_y_egg_info(self):
        raiz = crear_proyecto(self, {
            "app.py": "x = 1\n",
            ".venv-docs/a.py": "x = 1\n",
            "venv-old/b.py": "x = 1\n",
            "pytest-of-1/c.py": "x = 1\n",
            "paquete.egg-info/d.py": "x = 1\n",
            "exe/e.py": "x = 1\n",
        })

        nombres = [p.relative_to(raiz).as_posix()
                   for p in archivos_python(raiz)]

        self.assertEqual(nombres, ["app.py", "exe/e.py"])

    def test_alias_pil_docx_pptx_no_son_falsos_positivos(self):
        raiz = crear_proyecto(self, {
            "app.py": "import PIL\nimport docx\nimport pptx\n",
            "pyproject.toml": ('[project]\nname = "x"\nversion = "0.1.0"\n'
                               'dependencies = ["pillow", "python-docx", '
                               '"python-pptx"]\n'),
        })

        self.assertTrue(ejecutar(raiz)["ok"])

    def test_import_hermano_en_tools_es_local(self):
        raiz = crear_proyecto(self, {
            "tools/a.py": "import helper\n",
            "tools/helper.py": "X = 1\n",
        })

        self.assertTrue(ejecutar(raiz)["ok"])

    def test_cli_ignorar_excluye_directorio(self):
        raiz = crear_proyecto(self, {
            "app.py": "x = 1\n",
            "exe/malo.py": ("try:\n"
                            "    x = 1\n"
                            "except Exception:\n"
                            "    pass\n"),
        })
        antes = set(preflight_mod.IGNORAR)
        try:
            salida = io.StringIO()
            with redirect_stdout(salida):
                codigo = main(["--root", str(raiz), "--ignorar", "exe",
                               "--json"])
            datos = json.loads(salida.getvalue())
        finally:
            preflight_mod.IGNORAR.clear()
            preflight_mod.IGNORAR.update(antes)

        self.assertEqual(codigo, 0)
        self.assertTrue(datos["ok"])

    def test_el_repositorio_real_pasa_su_propio_preflight(self):
        informe = ejecutar(RAIZ_THINKER)

        self.assertTrue(informe["ok"], [
            hallazgo for gate in informe["gates"]
            for hallazgo in gate["hallazgos"]])


class TestSilenciosR6(unittest.TestCase):
    """R6: marca con motivo = warning; sin marca = hallazgo."""

    def _gates(self, informe):
        return {gate["nombre"]: gate for gate in informe["gates"]}

    def test_marca_con_motivo_es_warning(self):
        raiz = crear_proyecto(self, {
            "paquete/mod.py": (
                "def f():\n"
                "    try:\n"
                "        return 1\n"
                "    except Exception:  # noqa: silent: limpieza temporal\n"
                "        pass\n"),
        })

        informe = ejecutar(raiz)
        gate = self._gates(informe)["silencios"]

        self.assertTrue(informe["ok"])
        self.assertEqual(gate["hallazgos"], [])
        self.assertEqual(len(gate["advertencias"]), 1)
        self.assertIn("limpieza temporal",
                      gate["advertencias"][0]["mensaje"])
        self.assertEqual(informe["total_advertencias"], 1)

    def test_marca_sin_motivo_sigue_fallando(self):
        raiz = crear_proyecto(self, {
            "paquete/mod.py": (
                "def f():\n"
                "    try:\n"
                "        return 1\n"
                "    except Exception:  # noqa: silent:\n"
                "        pass\n"),
        })

        informe = ejecutar(raiz)

        self.assertFalse(informe["ok"])
        self.assertEqual(
            len(self._gates(informe)["silencios"]["hallazgos"]), 1)


if __name__ == "__main__":
    unittest.main()
