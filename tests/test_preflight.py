"""Tests de scripts/preflight.py: gates deterministas, fixtures y repo real."""

import ast
import io
import json
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from scripts.preflight import (archivos_python, cargar_modulos,
                               dependencias_declaradas, ejecutar, imprimir,
                               main, modulos_locales, revisar_duplicados,
                               revisar_imports, revisar_silencios,
                               revisar_tareas, _alias_asyncio, _es_main,
                               _es_type_checking, _lineas_import_opcional,
                               _lineas_condicionales, _lineas_no_runtime,
                               _leer_requisitos, _nombre_excepcion,
                               _nombre_tarea, _nombres_de_lista,
                               _nombres_setup)
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


def _funcion_con_literal(nombre, claves, asignacion=True):
    """Función con un literal grande para probar los umbrales del gate."""
    literal = "{" + ", ".join(f"'k{i}': x" for i in range(claves)) + "}"
    if asignacion:
        return (f"def {nombre}(x):\n"
                f"    datos = {literal}\n"
                "    return datos\n")
    return f"def {nombre}(x):\n    return {literal}\n"


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
        self.assertEqual(informe["root"], str(raiz))
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


class TestHelpersSinTestsR3(unittest.TestCase):
    """Cubre los helpers que no tenían tests directos (R3-C)."""

    def test_nombre_excepcion(self):
        self.assertEqual(
            _nombre_excepcion(ast.Name(id="ImportError")), "ImportError")
        self.assertEqual(
            _nombre_excepcion(ast.Tuple(
                elts=[ast.Name(id="OSError"), ast.Name(id="ValueError")],
                ctx=ast.Load())), "OSError,ValueError")
        self.assertEqual(_nombre_excepcion(ast.Constant(value=1)), "")

    def test_lineas_import_opcional(self):
        arbol = ast.parse(
            "try:\n"
            "    import requests\n"
            "except (ImportError, ModuleNotFoundError):\n"
            "    pass\n"
            "try:\n"
            "    import seguro\n"
            "except ValueError:\n"
            "    pass\n")
        self.assertEqual(_lineas_import_opcional(arbol), {2})

    def test_lineas_condicionales(self):
        arbol = ast.parse(
            "if has_foo:\n"
            "    import foo\n"
            "if not has_bar:\n"
            "    import bar\n"
            "if has_baz:\n"
            "    pass\n")
        self.assertEqual(_lineas_condicionales(arbol), {2})


class TestDependenciasDeclaradasR3(unittest.TestCase):
    """Triaje R3: cubre las ramas de manifiestos de dependencias."""

    def test_pyproject_pep621_poetry_pdm(self):
        raiz = crear_proyecto(self, {
            "pyproject.toml": (
                '[project]\nname = "d"\nversion = "0.1.0"\n'
                'dependencies = ["requests>=2.0", "pkg[extra]==1.0"]\n'
                '[project.optional-dependencies]\n'
                'dev = ["pytest>=8"]\n'
                '[dependency-groups]\n'
                'test = ["coverage"]\n'
                '[tool.poetry.dependencies]\n'
                'python = "^3.11"\nflask = "^3"\n'
                '[tool.poetry.group.dev.dependencies]\n'
                'black = "^24"\n'
                '[tool.pdm.dev-dependencies]\n'
                'lint = ["ruff"]\n'),
        })

        declaradas, hallazgos = dependencias_declaradas(raiz)

        self.assertEqual(hallazgos, [])
        self.assertEqual(declaradas, {
            "requests", "pkg", "pytest", "coverage", "flask", "black", "ruff"})

    def test_requirements_anidado(self):
        raiz = crear_proyecto(self, {
            "requirements.txt": "-r requirements/dev.txt\nrequests==2.31.0\n",
            "requirements/dev.txt": "flask==3.0.0\n",
        })

        declaradas, hallazgos = dependencias_declaradas(raiz)

        self.assertEqual(hallazgos, [])
        self.assertEqual(declaradas, {"requests", "flask"})

    def test_setup_cfg(self):
        raiz = crear_proyecto(self, {
            "setup.cfg": (
                "[options]\n"
                "install_requires =\n"
                "    requests>=2.0\n"
                "    flask\n"
                "tests_require =\n"
                "    pytest\n"
                "[options.extras_require]\n"
                "dev =\n"
                "    black\n"),
        })

        declaradas, hallazgos = dependencias_declaradas(raiz)

        self.assertEqual(hallazgos, [])
        self.assertEqual(declaradas, {"requests", "flask", "pytest", "black"})

    def test_setup_py(self):
        raiz = crear_proyecto(self, {
            "setup.py": (
                "from setuptools import setup\n"
                'setup(install_requires=["requests>=2.0"], '
                'extras_require={"dev": ["pytest"]})\n'),
        })

        declaradas, hallazgos = dependencias_declaradas(raiz)

        self.assertEqual(hallazgos, [])
        self.assertEqual(declaradas, {"requests", "pytest"})

    def test_toml_invalido_reporta_hallazgo(self):
        raiz = crear_proyecto(self, {"pyproject.toml": "[[[ roto\n"})

        _, hallazgos = dependencias_declaradas(raiz)

        self.assertEqual(len(hallazgos), 1)
        self.assertIn("TOML inválido", hallazgos[0].mensaje)

    def test_setup_cfg_invalido_reporta_hallazgo(self):
        raiz = crear_proyecto(self, {"setup.cfg": "[options\nsin cerrar\n"})

        _, hallazgos = dependencias_declaradas(raiz)

        self.assertEqual(len(hallazgos), 1)
        self.assertIn("setup.cfg inválido", hallazgos[0].mensaje)

    def test_ramas_de_manifiestos_y_normalizacion(self):
        raiz = crear_proyecto(self, {
            "requirements/base.in": (
                "-e git+https://example.invalid/pkg.git#egg=Editable_Pkg\n"
                "Foo_Bar>=1\n"
                "-c constraints.txt\n"),
            "requirements/constraints.txt": "ignorada==1\n",
            "pyproject.toml": (
                '[project]\nname = "d"\nversion = "0.1.0"\n'
                'optional-dependencies = { dev = ["Pytest>=8", "no-valido"] }\n'
                '[dependency-groups]\n'
                'test = ["coverage[toml]"]\n'
                '[tool.poetry.dependencies]\npython = "^3.11"\n'
                'requests = "^2"\n'
                '[tool.poetry.dev-dependencies]\nblack = "^24"\n'
                '[tool.poetry.group.docs.dependencies]\nsphinx = "^7"\n'
                '[tool.pdm.dev-dependencies]\nlint = ["ruff"]\n'),
            "setup.cfg": (
                "[options]\ninstall_requires =\n    flask>=3\n"
                "[options.extras_require]\n"
                "dev =\n    mypy\n"),
            "setup.py": (
                "from setuptools import setup\n"
                "setup(install_requires=DESCONOCIDO, "
                "extras_require={'x': ['pytest']})\n"),
            "node_modules/requirements.txt": "no-debe-entrar==1\n",
        })

        declaradas, hallazgos = dependencias_declaradas(raiz)

        self.assertEqual(hallazgos, [])
        self.assertEqual(declaradas, {
            "ignorada", "foo-bar", "pytest", "no-valido", "coverage",
            "requests", "black", "sphinx", "ruff", "flask", "mypy"})

    def test_setup_py_con_sintaxis_invalida_no_rompe(self):
        raiz = crear_proyecto(self, {
            "setup.py": "setup(install_requires=[\n",
            "requirements/in.txt": "requests\n",
        })

        declaradas, hallazgos = dependencias_declaradas(raiz)

        self.assertEqual(hallazgos, [])
        self.assertEqual(declaradas, {"requests"})


class TestLecturaManifiestosR3(unittest.TestCase):
    """Triaje R3: casos límite de lectura de manifiestos."""

    def test_nombres_de_lista_y_setup(self):
        self.assertEqual(_nombres_de_lista(None), set())
        self.assertEqual(_nombres_de_lista(["a==1", 2, "b[extra]>=2"]),
                         {"a", "b"})
        self.assertEqual(_nombres_setup("no-es-lista"), set())
        self.assertEqual(
            _nombres_setup({"dev": ["pytest>=8", "black"], "x": "no"}),
            {"pytest", "black"})

    def test_requirements_ciclo_y_archivo_faltante(self):
        raiz = crear_proyecto(self, {
            "requirements.txt": "-r requirements-2.txt\nrequests==2.31\n# c\n",
            "requirements-2.txt": "-r requirements.txt\nflask==3.0\n",
        })

        nombres = _leer_requisitos(raiz / "requirements.txt", set())

        self.assertEqual(nombres, {"requests", "flask"})
        self.assertEqual(
            _leer_requisitos(raiz / "no-existe.txt", set()), set())

    def test_requirements_con_unicode_invalido(self):
        raiz = crear_proyecto(self, {})
        ruta = raiz / "requirements.txt"
        ruta.write_bytes(b"\xff\xfe\x00")

        self.assertEqual(_leer_requisitos(ruta, set()), set())


class TestMainYModulosR3(unittest.TestCase):
    def test_cargar_modulos_errores_y_archivos_explicitos(self):
        raiz = crear_proyecto(self, {
            "ok.py": "x = 1\n",
            "mal.py": "def f(:\n",
            "bin.py": "",
        })
        (raiz / "bin.py").write_bytes(b"\xff\xfe\x00")

        modulos, resultado = cargar_modulos(
            raiz, [raiz / "ok.py", raiz / "mal.py", raiz / "bin.py"])

        self.assertEqual(set(modulos), {raiz / "ok.py"})
        self.assertEqual(len(resultado.hallazgos), 2)
        self.assertEqual({h.archivo for h in resultado.hallazgos},
                         {"mal.py", "bin.py"})

    def test_cli_allow_acepta_import_extra(self):
        raiz = crear_proyecto(self, {"demo.py": "import extra\n"})
        salida = io.StringIO()

        with redirect_stdout(salida):
            codigo = main(["--root", str(raiz), "--allow", "extra", "--json"])

        self.assertEqual(codigo, 0)
        self.assertTrue(json.loads(salida.getvalue())["ok"])


class TestImportsYSilenciosR3(unittest.TestCase):
    def test_imports_hermanos_opcionales_permitidos_y_duplicados(self):
        raiz = crear_proyecto(self, {
            "tools/principal.py": (
                "import os\nimport helper\nimport extra\n"
                "try:\n    import requests\nexcept ImportError:\n    pass\n"
                "import os\n"),
            "tools/helper.py": "x = 1\n",
        })
        modulos, _ = cargar_modulos(raiz)

        resultado = revisar_imports(
            raiz, modulos, permitidos=["extra"], ignorar_opcionales=True)

        self.assertEqual(resultado.hallazgos, [])

    def test_import_no_declarado_se_reporta_una_vez(self):
        raiz = crear_proyecto(self, {
            "demo.py": "import requests\nimport requests\n"})
        modulos, _ = cargar_modulos(raiz)

        resultado = revisar_imports(raiz, modulos)

        self.assertEqual(len(resultado.hallazgos), 1)
        self.assertEqual(resultado.hallazgos[0].mensaje,
                         "import no declarado: requests")
        self.assertEqual(resultado.hallazgos[0].severidad, "alta")

    def test_silencios_marca_valida_y_cuerpos_multiples(self):
        raiz = crear_proyecto(self, {
            "demo.py": (
                "def a():\n"
                "    try:\n        return 1\n"
                "    except Exception:  # noqa: silent: motivo\n"
                "        pass\n"
                "def b():\n"
                "    try:\n        return 1\n"
                "    except Exception:\n        pass\n        return 0\n"
                "def c():\n"
                "    for x in []:\n"
                "        try:\n            pass\n"
                "        except Exception:\n            continue\n"
                "def d():\n"
                "    try:\n        return 1\n"
                "    except Exception:\n        ...\n")})
        modulos, _ = cargar_modulos(raiz)

        resultado = revisar_silencios(raiz, modulos)

        self.assertEqual(len(resultado.advertencias), 1)
        self.assertEqual(resultado.advertencias[0].severidad, "baja")
        self.assertEqual(len(resultado.hallazgos), 2)
        self.assertEqual({h.linea for h in resultado.hallazgos}, {16, 21})


class TestCamposDelInformeR3(unittest.TestCase):
    """R3: el contrato del hallazgo incluye gate, archivo, línea y severidad."""

    def test_cargar_modulos_campos_y_linea_de_sintaxis(self):
        raiz = crear_proyecto(self, {
            "tarde.py": "x = 1\ny = 2\ndef f(:\n",
            "bin.py": "",
        })
        (raiz / "bin.py").write_bytes(b"\xff\xfe")

        modulos, resultado = cargar_modulos(
            raiz, [raiz / "tarde.py", raiz / "bin.py"])

        self.assertEqual(modulos, {})
        por_archivo = {h.archivo: h for h in resultado.hallazgos}
        self.assertEqual(set(por_archivo), {"bin.py", "tarde.py"})
        binario = por_archivo["bin.py"]
        self.assertEqual(binario.gate, "sintaxis")
        self.assertEqual(binario.linea, 0)
        self.assertEqual(binario.severidad, "alta")
        self.assertEqual(binario.tipo_evidencia.value, "verified-real")
        self.assertTrue(binario.mensaje.startswith(
            "no se pudo leer: UnicodeDecodeError:"))
        sintaxis = por_archivo["tarde.py"]
        self.assertEqual(sintaxis.gate, "sintaxis")
        self.assertEqual(sintaxis.linea, 3)
        self.assertEqual(sintaxis.severidad, "alta")
        self.assertTrue(sintaxis.mensaje.startswith("error de sintaxis: "))

    def test_dependencias_sigue_tras_manifiesto_invalido(self):
        raiz = crear_proyecto(self, {
            "pyproject.toml": "[project\n",
            "setup.cfg": "[options\n",
            "requirements.txt": "requests==2\n",
            "setup.py": "setup(install_requires=['flask'])\n",
        })

        declaradas, hallazgos = dependencias_declaradas(raiz)

        self.assertEqual(declaradas, {"requests", "flask"})
        por_archivo = {h.archivo: h for h in hallazgos}
        self.assertEqual(set(por_archivo), {"pyproject.toml", "setup.cfg"})
        for archivo, prefijo in (("pyproject.toml", "TOML inválido"),
                                 ("setup.cfg", "setup.cfg inválido")):
            hallazgo = por_archivo[archivo]
            self.assertEqual(hallazgo.gate, "imports")
            self.assertEqual(hallazgo.linea, 0)
            self.assertEqual(hallazgo.severidad, "alta")
            self.assertEqual(hallazgo.tipo_evidencia.value, "verified-real")
            self.assertTrue(hallazgo.mensaje.startswith(prefijo),
                            hallazgo.mensaje)

    def test_solo_requirements_txt_o_in_cuenta(self):
        raiz = crear_proyecto(self, {
            "requirements/notas.md": "flask==3\n",
            "requirements.txt": "requests==2\n",
        })

        declaradas, hallazgos = dependencias_declaradas(raiz)

        self.assertEqual(hallazgos, [])
        self.assertEqual(declaradas, {"requests"})

    def test_setup_py_reconoce_tests_require(self):
        raiz = crear_proyecto(self, {
            "setup.py": ("setup(description='x', install_requires=['a'], "
                         "tests_require=['pytest'], "
                         "extras_require={'x': ['b']})\n"),
        })

        self.assertEqual(
            dependencias_declaradas(raiz), ({"a", "pytest", "b"}, []))

    def test_pdm_con_lista_no_rompe(self):
        raiz = crear_proyecto(self, {
            "pyproject.toml": (
                '[project]\nname = "x"\nversion = "0.1.0"\n'
                '[tool.pdm]\ndev-dependencies = ["ruff"]\n'),
        })

        self.assertEqual(dependencias_declaradas(raiz), (set(), []))

    @unittest.skipIf(
        os.name == "nt" or getattr(os, "geteuid", lambda: 1)() == 0,
        "chmod no deniega la lectura en Windows ni como root")
    def test_setup_py_ilegible_reporta_campos(self):
        raiz = crear_proyecto(self, {
            "setup.py": "setup()\n",
            "requirements.txt": "requests\n",
            "zz/requirements/dev.txt": "flask\n",
        })
        ruta = raiz / "setup.py"
        ruta.chmod(0)
        try:
            declaradas, hallazgos = dependencias_declaradas(raiz)
        finally:
            ruta.chmod(0o600)

        self.assertEqual(declaradas, {"requests", "flask"})
        self.assertEqual(len(hallazgos), 1)
        hallazgo = hallazgos[0]
        self.assertEqual(hallazgo.gate, "imports")
        self.assertEqual(hallazgo.archivo, "setup.py")
        self.assertEqual(hallazgo.linea, 0)
        self.assertEqual(hallazgo.severidad, "alta")
        self.assertTrue(hallazgo.mensaje.startswith(
            "setup.py ilegible, no se pueden verificar dependencias: "))

    def test_silencios_campos_y_marca_en_ultima_linea(self):
        raiz = crear_proyecto(self, {
            "app.py": ("try:\n"
                       "    x = 1\n"
                       "except Exception:  pass  # noqa: silent: abc")})
        resultado = revisar_silencios(raiz, cargar_modulos(raiz)[0])

        self.assertEqual(resultado.hallazgos, [])
        self.assertEqual([a.a_dict() for a in resultado.advertencias], [{
            "gate": "silencios", "archivo": "app.py", "linea": 3,
            "mensaje": "silencio aceptado (warning): abc",
            "severidad": "baja", "tipo_evidencia": "verified-real"}])

        raiz2 = crear_proyecto(self, {
            "app.py": ("try:\n"
                       "    x = 1\n"
                       "except ValueError:\n"
                       "    pass\n")})
        resultado2 = revisar_silencios(raiz2, cargar_modulos(raiz2)[0])

        self.assertEqual([h.a_dict() for h in resultado2.hallazgos], [{
            "gate": "silencios", "archivo": "app.py", "linea": 3,
            "mensaje": "except con pass/continue/... (P1.26)",
            "severidad": "alta", "tipo_evidencia": "verified-real"}])

    @unittest.skipIf(
        os.name == "nt" or getattr(os, "geteuid", lambda: 1)() == 0,
        "chmod no deniega la lectura en Windows ni como root")
    def test_silencios_con_archivo_ilegible_no_rompe(self):
        raiz = crear_proyecto(self, {
            "app.py": ("try:\n"
                       "    x = 1\n"
                       "except Exception:\n"
                       "    pass\n")})
        modulos, _ = cargar_modulos(raiz)
        ruta = raiz / "app.py"
        ruta.chmod(0)
        try:
            resultado = revisar_silencios(raiz, modulos)
        finally:
            ruta.chmod(0o600)

        self.assertEqual(len(resultado.hallazgos), 1)


class TestDuplicadosR3(unittest.TestCase):
    """R3: umbrales del gate de duplicados y mensaje exacto."""

    def test_limites_de_cuerpo_y_nodos(self):
        raiz = crear_proyecto(self, {"app.py": (
            _funcion_con_literal("grande_a", 30) + "\n"
            + _funcion_con_literal("grande_b", 30) + "\n"
            + _funcion_con_literal("medio_a", 16) + "\n"
            + _funcion_con_literal("medio_b", 16) + "\n"
            + _funcion_con_literal("uno_a", 20, asignacion=False) + "\n"
            + _funcion_con_literal("uno_b", 20, asignacion=False))})

        resultado = revisar_duplicados(raiz, cargar_modulos(raiz)[0])

        self.assertEqual(len(resultado.hallazgos), 1)
        self.assertIn("grande_b", resultado.hallazgos[0].mensaje)

    def test_funciones_distintas_no_se_confunden(self):
        raiz = crear_proyecto(self, {"app.py": (
            _funcion_con_literal("grande_a", 30) + "\n"
            + _funcion_con_literal("grande_c", 31))})

        resultado = revisar_duplicados(raiz, cargar_modulos(raiz)[0])

        self.assertEqual(resultado.hallazgos, [])

    def test_duplicado_tras_trivial_y_mensaje_exacto(self):
        raiz = crear_proyecto(self, {"app.py": (
            "def trivial():\n"
            "    return 1\n"
            "\n" + DUPLICADO_SUSTANCIAL)})

        resultado = revisar_duplicados(raiz, cargar_modulos(raiz)[0])

        self.assertEqual([h.a_dict() for h in resultado.hallazgos], [{
            "gate": "duplicados", "archivo": "app.py", "linea": 16,
            "mensaje": "cuerpo idéntico a app.py:4 (suma_a);"
                       " actual: suma_b",
            "severidad": "media", "tipo_evidencia": "verified-real"}])


class TestImportsR3Extra(unittest.TestCase):
    """R3: opcionales por defecto, imports múltiples y relativos."""

    def test_opcional_por_defecto_no_se_ignora(self):
        raiz = crear_proyecto(self, {
            "app.py": ("try:\n"
                       "    import requests\n"
                       "except ImportError:\n"
                       "    pass\n")})
        modulos, _ = cargar_modulos(raiz)

        resultado = revisar_imports(raiz, modulos)

        self.assertEqual([h.linea for h in resultado.hallazgos], [2])

    def test_import_multiple_punteado_y_relativo(self):
        raiz = crear_proyecto(self, {
            "paquete/__init__.py": "",
            "paquete/mod.py": "x = 1\n",
            "sub/__init__.py": "",
            "app.py": ("import os, requests\n"
                       "import paquete.mod as pm\n"
                       "from paquete.mod import x\n"
                       "from .mod import y\n"
                       "import sub\n")})
        modulos, _ = cargar_modulos(raiz)

        resultado = revisar_imports(raiz, modulos)

        self.assertEqual([(h.linea, h.mensaje) for h in resultado.hallazgos],
                         [(1, "import no declarado: requests")])

    def test_import_bajo_guardia_negativa_no_es_no_runtime(self):
        raiz = crear_proyecto(self, {
            "app.py": ("if __name__ != '__main__':\n"
                       "    import requests\n")})
        modulos, _ = cargar_modulos(raiz)

        resultado = revisar_imports(raiz, modulos)

        self.assertEqual([(h.linea, h.mensaje) for h in resultado.hallazgos],
                         [(2, "import no declarado: requests")])

    def test_type_checking_y_opcionales_a_la_vez(self):
        raiz = crear_proyecto(self, {
            "app.py": ("from typing import TYPE_CHECKING\n"
                       "if TYPE_CHECKING:\n"
                       "    import sphinx\n"
                       "try:\n"
                       "    import requests\n"
                       "except ImportError:\n"
                       "    pass\n")})
        modulos, _ = cargar_modulos(raiz)

        resultado = revisar_imports(raiz, modulos, ignorar_opcionales=True)

        self.assertEqual(resultado.hallazgos, [])

    def test_hallazgo_campos_exactos(self):
        raiz = crear_proyecto(self, {"app.py": "\nimport requests\n"})
        modulos, _ = cargar_modulos(raiz)

        resultado = revisar_imports(raiz, modulos)

        self.assertEqual([h.a_dict() for h in resultado.hallazgos], [{
            "gate": "imports", "archivo": "app.py", "linea": 2,
            "mensaje": "import no declarado: requests",
            "severidad": "alta", "tipo_evidencia": "verified-real"}])


class TestTareasR3(unittest.TestCase):
    """R3: alias de asyncio y detección de tareas sin referencia."""

    def test_alias_asyncio_y_funciones(self):
        arbol = ast.parse(
            "import asyncio\n"
            "import asyncio as aio\n"
            "from asyncio import create_task as ct, ensure_future\n"
            "from .asyncio import create_task as rel\n")

        self.assertEqual(_alias_asyncio(arbol), (
            {"asyncio", "aio"},
            {"ct": "create_task", "ensure_future": "ensure_future"}))

    def test_nombre_tarea_desenvuelve_atributos(self):
        alias_modulo = {"asyncio", "aio"}
        alias_funcion = {"ct": "create_task"}

        def nombre(codigo):
            return _nombre_tarea(
                ast.parse(codigo).body[0].value.func,
                alias_modulo, alias_funcion)

        self.assertEqual(nombre("ct(t)"), "asyncio.create_task")
        self.assertEqual(nombre("aio.ensure_future(t)"),
                         "asyncio.ensure_future")
        self.assertEqual(nombre("asyncio.tasks.create_task(t)"),
                         "asyncio.create_task")
        self.assertIsNone(nombre("otro.create_task(t)"))
        self.assertIsNone(nombre("otro(t)"))

    def test_tareas_detecta_alias_y_evita_falsos_positivos(self):
        raiz = crear_proyecto(self, {
            "app.py": ("import asyncio as aio\n"
                       "from asyncio import ensure_future as ef\n"
                       "aio.create_task(t())\n"
                       "asyncio.tasks.ensure_future(t())\n"
                       "ef(t())\n"
                       "otro.create_task(t())\n")})
        modulos, _ = cargar_modulos(raiz)

        resultado = revisar_tareas(raiz, modulos)

        self.assertEqual([h.linea for h in resultado.hallazgos], [3, 4, 5])
        self.assertEqual([h.mensaje for h in resultado.hallazgos], [
            "asyncio.create_task sin referencia: el event loop puede "
            "recolectar la tarea (P1.34)",
            "asyncio.ensure_future sin referencia: el event loop puede "
            "recolectar la tarea (P1.34)",
            "asyncio.ensure_future sin referencia: el event loop puede "
            "recolectar la tarea (P1.34)"])
        self.assertEqual(resultado.hallazgos[0].a_dict(), {
            "gate": "tareas", "archivo": "app.py", "linea": 3,
            "mensaje": "asyncio.create_task sin referencia: el event loop "
                       "puede recolectar la tarea (P1.34)",
            "severidad": "media", "tipo_evidencia": "verified-real"})


class TestAstFlagsR3(unittest.TestCase):
    """R3: detección de __main__, TYPE_CHECKING y líneas no runtime."""

    def test_es_main_variantes(self):
        def es_main(codigo):
            return _es_main(ast.parse(codigo).body[0].test)

        self.assertTrue(es_main("if __name__ == '__main__':\n    pass\n"))
        self.assertFalse(es_main("if __name__ != '__main__':\n    pass\n"))
        self.assertFalse(es_main("if __name__ == 'otro':\n    pass\n"))
        self.assertFalse(es_main("if otro == '__main__':\n    pass\n"))
        self.assertFalse(es_main("if 1 == '__main__':\n    pass\n"))
        self.assertFalse(es_main("if __name__ == foo:\n    pass\n"))
        self.assertFalse(es_main("if __name__ == '__main__' == x:\n    pass\n"))
        self.assertFalse(_es_main(ast.Name(id="__name__")))

    def test_es_type_checking_variantes(self):
        def es_type_checking(codigo):
            return _es_type_checking(ast.parse(codigo).body[0].test)

        self.assertTrue(es_type_checking("if TYPE_CHECKING:\n    pass\n"))
        self.assertTrue(es_type_checking("if typing.TYPE_CHECKING:\n    pass\n"))
        self.assertFalse(es_type_checking("if OTHER:\n    pass\n"))
        self.assertFalse(es_type_checking("if typing.OTHER:\n    pass\n"))
        self.assertFalse(_es_type_checking(ast.Constant(value=True)))

    def test_lineas_no_runtime_exactas(self):
        arbol = ast.parse(
            "import os\n"
            "if cond:\n"
            "    import django\n"
            "if TYPE_CHECKING:\n"
            "    import requests\n"
            "if __name__ == '__main__':\n"
            "    import flask\n")

        self.assertEqual(_lineas_no_runtime(arbol), {5, 7})

    def test_import_opcional_modulenotfound_y_break(self):
        arbol = ast.parse(
            "try:\n    x = 1\nexcept ValueError:\n    pass\n"
            "try:\n    import requests\nexcept ModuleNotFoundError:\n"
            "    pass\n"
            "try:\n    import flask\n"
            "except (OSError, ModuleNotFoundError):\n    pass\n")

        self.assertEqual(_lineas_import_opcional(arbol), {6, 10})


class TestModulosLocalesR3(unittest.TestCase):
    """R3: layout plano, src/, lib/, mayúsculas y directorios ignorados."""

    def test_conjunto_exacto_de_modulos_locales(self):
        raiz = crear_proyecto(self, {
            "raiz.py": "x = 1\n",
            "paquete/__init__.py": "",
            "paquete/mod.py": "x = 1\n",
            "solo/__init__.py": "",
            "src/pkg/__init__.py": "",
            "src/plano.py": "x = 1\n",
            "src/sininit/mod.py": "x = 1\n",
            "lib/util.py": "x = 1\n",
            "lib/otro/__init__.py": "",
            "lib/otro/mod.py": "x = 1\n",
            "tools/helper.py": "x = 1\n",
            "mayus.PY": "x = 1\n",
            ".venv/__init__.py": "",
            ".venv/oculto/__init__.py": "",
        })

        self.assertEqual(modulos_locales(raiz), {
            "lib", "otro", "paquete", "pkg", "plano", "raiz", "sininit",
            "solo", "src", "tools", "util"})


class TestImprimirR3(unittest.TestCase):
    """R3: el render de texto conserva estados, marcas y veredicto."""

    def test_render_exacto(self):
        informe = {
            "root": "/tmp/x", "archivos_python": 3,
            "evidencia": "verified-real", "total_hallazgos": 1,
            "total_advertencias": 1, "ok": False,
            "gates": [
                {"nombre": "sintaxis", "ok": True, "hallazgos": []},
                {"nombre": "silencios", "ok": False,
                 "hallazgos": [{
                     "gate": "silencios", "archivo": "a.py", "linea": 2,
                     "mensaje": "except con pass/continue/... (P1.26)",
                     "severidad": "alta",
                     "tipo_evidencia": "verified-real"}],
                 "advertencias": [{
                     "gate": "silencios", "archivo": "b.py", "linea": 5,
                     "mensaje": "silencio aceptado (warning): motivo",
                     "severidad": "baja",
                     "tipo_evidencia": "verified-real"}]},
            ]}
        salida = io.StringIO()

        with redirect_stdout(salida):
            imprimir(informe)

        self.assertEqual(salida.getvalue().splitlines(), [
            "PREFLIGHT (offline, read-only): /tmp/x",
            "Python: 3 archivos | evidencia: [VERIFIED-REAL] observación "
            "estática, sin ejecutar el código",
            "  [OK] sintaxis: 0 hallazgos, 0 warnings",
            "  [FAIL] silencios: 1 hallazgos, 1 warnings",
            "    [VERIFIED-REAL] a.py:2 except con pass/continue/... (P1.26)",
            "    [VERIFIED-REAL] WARNING b.py:5 silencio aceptado "
            "(warning): motivo",
            "PREFLIGHT: FAIL (1 hallazgos, 1 warnings)"])


class TestMainR3(unittest.TestCase):
    """R3: superficie del CLI y raíz por defecto."""

    def test_help_documenta_opciones(self):
        salida = io.StringIO()

        with mock.patch.dict(os.environ, {"COLUMNS": "200"}):
            with redirect_stdout(salida), self.assertRaises(
                    SystemExit) as contexto:
                main(["--help"])

        self.assertEqual(contexto.exception.code, 0)
        texto = salida.getvalue()
        self.assertNotIn("XX", texto)
        self.assertIn("Preflight determinista y offline del código Python.",
                      texto.splitlines())
        for fragmento in (
                "Preflight determinista y offline del código Python.",
                "--root ROOT",
                "directorio raíz a revisar (defecto: raíz de este proyecto)",
                "salida JSON para máquinas",
                "--allow MODULO",
                "módulo de importación permitido sin declarar (repetible)",
                "--ignorar DIRECTORIO",
                "directorio a excluir del análisis (repetible)"):
            self.assertIn(fragmento, texto)

    def test_root_por_defecto_es_el_repositorio(self):
        salida = io.StringIO()
        informe = {
            "root": str(preflight_mod.REPO_ROOT), "archivos_python": 0,
            "evidencia": "verified-real", "gates": [], "total_hallazgos": 0,
            "total_advertencias": 0, "ok": True,
        }

        with mock.patch.object(preflight_mod, "ejecutar",
                               return_value=informe) as ejecutar_mock:
            with redirect_stdout(salida):
                codigo = main(["--json"])

        self.assertEqual(codigo, 0)
        self.assertEqual(ejecutar_mock.call_args.args[0],
                         preflight_mod.REPO_ROOT)
        self.assertEqual(json.loads(salida.getvalue())["root"],
                         str(preflight_mod.REPO_ROOT))

    def test_error_de_lectura_devuelve_dos(self):
        error = io.StringIO()

        with mock.patch.object(preflight_mod, "ejecutar",
                               side_effect=OSError("boom")):
            with redirect_stderr(error):
                codigo = main(["--json"])

        self.assertEqual(codigo, 2)
        self.assertIn("no se pudo leer el proyecto", error.getvalue())


if __name__ == "__main__":
    unittest.main()
