"""Contrato de scripts/verificar_instalacion.py con pyproject.toml: las listas
de módulos y console scripts del verificador deben cubrir exactamente lo que el
paquete declara (si pyproject cambia y el script no, este test lo detecta).
La verificación real (venv + wheel) se ejecuta bajo demanda con
`python3 scripts/verificar_instalacion.py` / `make verify-install`.
"""

import ast
import importlib.metadata
import unittest
from pathlib import Path

import scripts.verificar_instalacion as vi

RAIZ = Path(__file__).resolve().parent.parent
PYPROJECT = RAIZ / "pyproject.toml"


def _listas_pyproject():
    """Extrae py-modules, packages y scripts de pyproject.toml (tomllib)."""
    import tomllib
    datos = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    setuptools = datos["tool"]["setuptools"]
    scripts = set(datos["project"]["scripts"])
    return (set(setuptools["py-modules"]), set(setuptools["packages"]),
            scripts)


class TestContratoVerificadorInstalacion(unittest.TestCase):
    def test_modulos_cubren_exactamente_los_declarados(self):
        py_modules, packages, _ = _listas_pyproject()
        cubiertos = set(vi.MODULOS_STDLIB) | set(vi.MODULOS_CON_DEPS)
        declarados = py_modules | {"plugins.registry", "scripts.preflight"}
        self.assertEqual(cubiertos, declarados)
        self.assertEqual(packages, {"plugins", "plugins.llm_providers",
                                    "plugins.search_providers", "scripts"})

    def test_console_scripts_coinciden_con_pyproject(self):
        _, _, scripts = _listas_pyproject()
        self.assertEqual(set(vi.CONSOLE_SCRIPTS), scripts)

    def test_modulos_stdlib_no_importan_terceros_en_cabecera(self):
        # La lista MODULOS_STDLIB promete importar sin dependencias: sus
        # imports de nivel módulo deben ser stdlib o internos del proyecto.
        terceros = {"requests", "openai", "yaml", "dotenv", "ollama"}
        for modulo in vi.MODULOS_STDLIB:
            ruta = RAIZ / (modulo.replace(".", "/") + ".py")
            if not ruta.exists():
                ruta = RAIZ / modulo.replace(".", "/") / "__init__.py"
            with self.subTest(modulo=modulo):
                arbol = ast.parse(ruta.read_text(encoding="utf-8"))
                # Solo imports de nivel módulo: los perezosos (dentro de
                # funciones) no rompen el import sin dependencias.
                for nodo in arbol.body:
                    if isinstance(nodo, ast.Import):
                        nombres = [a.name.split(".")[0] for a in nodo.names]
                    elif isinstance(nodo, ast.ImportFrom) and nodo.level == 0:
                        nombres = [(nodo.module or "").split(".")[0]]
                    else:
                        continue
                    self.assertFalse(terceros & set(nombres),
                                     f"{modulo} importa {nombres}")

    def test_los_modulos_listados_existen_en_el_repo(self):
        for modulo in vi.MODULOS_STDLIB + vi.MODULOS_CON_DEPS:
            ruta = RAIZ / (modulo.replace(".", "/") + ".py")
            with self.subTest(modulo=modulo):
                self.assertTrue(ruta.exists(), str(ruta))

    def test_comando_wheel_usa_aislamiento_sin_setuptools(self):
        # Python 3.12 no trae setuptools en el venv (PEP 632): el comando
        # debe construirse con aislamiento (sin --no-build-isolation).
        original = vi._setuptools_disponible
        try:
            vi._setuptools_disponible = lambda: True
            self.assertIn("--no-build-isolation", vi._comando_wheel())
        finally:
            vi._setuptools_disponible = original
        try:
            vi._setuptools_disponible = lambda: False
            self.assertNotIn("--no-build-isolation", vi._comando_wheel())
        finally:
            vi._setuptools_disponible = original

    def test_setuptools_debe_cumplir_minimo_build(self):
        original = importlib.metadata.version
        try:
            importlib.metadata.version = lambda _nombre: "65.5.0"
            self.assertFalse(vi._setuptools_disponible())
            self.assertNotIn("--no-build-isolation", vi._comando_wheel())
            importlib.metadata.version = lambda _nombre: "77.0.0"
            self.assertTrue(vi._setuptools_disponible())
            self.assertIn("--no-build-isolation", vi._comando_wheel())
        finally:
            importlib.metadata.version = original

    def test_wheel_dir_queda_junto_al_destino(self):
        original = vi._setuptools_disponible
        try:
            vi._setuptools_disponible = lambda: True
            comando = vi._comando_wheel() + ["DESTINO"]
        finally:
            vi._setuptools_disponible = original

        self.assertEqual(comando[-2:], ["--wheel-dir", "DESTINO"])
        self.assertIn("--no-build-isolation", comando)


if __name__ == "__main__":
    unittest.main()
