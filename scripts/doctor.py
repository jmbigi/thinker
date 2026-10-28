#!/usr/bin/env python3
"""Autodiagnóstico del entorno de thinker (offline por defecto).

Comprueba lo que más a menudo explica un "no me funciona": versión de Python,
dependencias instaladas frente a requirements.txt, herramientas externas
(git/make), variables de entorno de proveedores (solo PRESENCIA: nunca se
imprime el valor, P0.6) y descubrimiento de plugins con las rutas por defecto.

Con `--con-red` (opt-in, declarado) sondea además el servidor Ollama local y,
si hay `OPENROUTER_API_KEY`, el endpoint de modelos de OpenRouter; ambos con
timeout corto y sin escribir nada.

Exit 0 si lo esencial (Python + dependencias) está bien; 1 en caso contrario.
Las claves ausentes se declaran como información, no como fallo: el proyecto
funciona offline por defecto (regla propia 6).
"""

import argparse
import os
import shutil
import socket
import sys
import urllib.request
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
# `python3 scripts/doctor.py` deja sys.path[0]=scripts/: sin esto, `plugins`
# se importaría del paquete instalado en site-packages (una copia congelada)
# en vez del repo que se está diagnosticando. Verificado: antes del fix el
# doctor mostraba 3 plugins del paquete instalado y 3 fallos que el repo no
# tiene.
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

# Contrato con llm_providers.py (cubierto por tests/test_doctor.py): si un
# proveedor añade una variable de entorno, debe aparecer aquí.
VARIABLES_PROVEEDORES = (
    "OPENAI_API_KEY", "OPENROUTER_API_KEY", "OPENROUTER_MODEL",
    "KILO_API_KEY", "DEEPSEEK_API_KEY", "OLLAMA_MODEL", "OLLAMA_BASE_URL",
)


class _Doctor:
    """Salida con marcas Unicode si la consola las soporta; ASCII si no
    (consolas cp1252 de Windows: `✓` lanza UnicodeEncodeError)."""

    def __init__(self):
        self.fallos = 0
        codificacion = getattr(sys.stdout, "encoding", "") or "utf-8"
        try:
            "✓✗ℹ".encode(codificacion)
            self._ok, self._mal, self._info = "✓", "✗", "ℹ"
        except (UnicodeEncodeError, LookupError):
            self._ok, self._mal, self._info = "[OK]", "[FALLO]", "[i]"

    def check(self, ok: bool, etiqueta: str, detalle: str = ""):
        print(f"  {self._ok if ok else self._mal} {etiqueta}"
              + (f" — {detalle}" if detalle else ""))
        if not ok:
            self.fallos += 1

    def info(self, etiqueta: str, detalle: str = ""):
        print(f"  {self._info} {etiqueta}" + (f" — {detalle}" if detalle else ""))


def _deps_declaradas():
    deps = []
    for linea in (RAIZ / "requirements.txt").read_text(
            encoding="utf-8").splitlines():
        linea = linea.split("#", 1)[0].strip()
        if linea and not linea.startswith("-"):
            deps.append(linea)
    return deps


def _nombre_distribucion(dep: str) -> str:
    for sep in ("==", ">=", "<=", "~=", "!=", ">", "<", "["):
        if sep in dep:
            return dep.split(sep, 1)[0].strip()
    return dep.strip()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--con-red", action="store_true",
                        help="sondea Ollama/OpenRouter (opt-in, declarado)")
    args = parser.parse_args(argv)

    d = _Doctor()
    print("DOCTOR de thinker (offline; --con-red para las sondas de red)\n")

    print("Python:")
    actual = sys.version_info
    d.check(actual >= (3, 11), "Python >= 3.11 (requires-python)",
            f"{actual.major}.{actual.minor}.{actual.micro} — {sys.executable}")

    print("\nDependencias (requirements.txt):")
    for dep in _deps_declaradas():
        nombre = _nombre_distribucion(dep)
        try:
            d.check(True, nombre, f"instalada {version(nombre)}")
        except PackageNotFoundError:
            d.check(False, nombre, "NO instalada")

    print("\nHerramientas externas:")
    for herramienta in ("git", "make"):
        ruta = shutil.which(herramienta)
        (d.check if ruta else d.info)(ruta is not None and True, herramienta,
                                      ruta or "no encontrada")

    print("\nProveedores LLM (solo presencia; valores nunca se muestran):")
    for variable in VARIABLES_PROVEEDORES:
        d.info(variable, "definida" if os.environ.get(variable)
               else "no definida")

    print("\nPlugins (rutas por defecto, resueltas respecto al paquete):")
    import plugins as paquete_plugins
    from plugins.registry import PluginRegistry
    d.info("paquete `plugins` importado desde", paquete_plugins.__file__)
    registro = PluginRegistry()
    encontrados = registro.discover_plugins()
    d.check(encontrados >= 1, "plugins descubiertos", str(encontrados))
    d.info("config por defecto", registro.config_path
           + (" (existe)" if Path(registro.config_path).exists()
              else " (no existe: valores por defecto)"))

    if args.con_red:
        print("\nSondas de red (opt-in):")
        try:
            with socket.create_connection(("localhost", 11434), timeout=2):
                d.info("Ollama", "escuchando en localhost:11434")
        except OSError as exc:
            d.info("Ollama", f"no responde: {exc}")
        if os.environ.get("OPENROUTER_API_KEY"):
            try:
                peticion = urllib.request.Request(
                    "https://openrouter.ai/api/v1/models",
                    headers={"User-Agent": "thinker-doctor"})
                with urllib.request.urlopen(peticion, timeout=5) as resp:
                    d.info("OpenRouter", f"responde HTTP {resp.status}")
            except Exception as exc:  # noqa: BLE001 - se declara el fallo
                d.info("OpenRouter", f"fallo: {type(exc).__name__}: {exc}")
        else:
            d.info("OpenRouter", "sin OPENROUTER_API_KEY: sonda omitida")

    print()
    if d.fallos:
        print(f"RESULTADO: {d.fallos} problemas esenciales")
        return 1
    print("RESULTADO: entorno esencial correcto")
    return 0


if __name__ == "__main__":
    sys.exit(main())
