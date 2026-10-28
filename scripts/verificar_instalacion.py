#!/usr/bin/env python3
"""Verificación de instalación limpia del paquete (Hallazgo 82 hecho reproducible).

Nivel 1 (offline, por defecto): construye el wheel sin red
(`pip wheel --no-deps --no-build-isolation`), lo instala en un venv temporal
con `--no-index --no-deps` y comprueba, desde un CWD ajeno al repo:

- los console scripts existen en el venv;
- los módulos públicos que solo usan stdlib importan (`evidence`,
  `thinking_engine`, `llm_providers`, `code_design_improvement_tools`,
  `plugins.registry`, `scripts.preflight`);
- los que necesitan dependencias de terceros (`requests`/`openai`) fallan
  SOLO por esa dependencia ausente — es decir, el paquete está bien formado
  y lo que falta es la dependencia declarada, no código del paquete.

Nivel 2 (`--con-red`, opt-in): instala además las dependencias declaradas e
importa los 8 módulos públicos y ejecuta los console scripts con `--help`.

Read-only sobre el repo: todo se construye en temporales que se limpian.
Exit 0 si todas las comprobaciones pasan, 1 en caso contrario.
"""

import argparse
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Contrato con pyproject.toml ([tool.setuptools] py-modules y packages): si
# cambia allí, debe cambiar aquí; el test de humo del script lo contrasta.
MODULOS_STDLIB = ("evidence", "thinking_engine", "llm_providers",
                  "code_design_improvement_tools", "plugins.registry",
                  "scripts.preflight")
MODULOS_CON_DEPS = ("web_search", "deep_research_system", "pensamiento_layer",
                    "evaluar_proyecto")
CONSOLE_SCRIPTS = ("evaluate-project", "think", "research", "code-design")
# Dependencias de terceros que el venv sin deps no tiene: su ImportError es lo
# ESPERADO en el nivel offline; cualquier otro ImportError es un defecto del
# paquete.
DEPS_TERCEROS = ("requests", "openai", "yaml", "dotenv", "ollama")


def _bin_dir(venv_dir: Path) -> Path:
    return venv_dir / ("Scripts" if sys.platform == "win32" else "bin")


def _python_venv(venv_dir: Path) -> Path:
    return _bin_dir(venv_dir) / ("python.exe" if sys.platform == "win32"
                                 else "python")


def _ejecutar(comando, cwd=None):
    return subprocess.run(comando, cwd=cwd, capture_output=True, text=True,
                          timeout=300)


class _Verificador:
    def __init__(self):
        self.fallos = 0

    def check(self, ok: bool, etiqueta: str, detalle: str = ""):
        marca = "✓" if ok else "✗"
        print(f"  {marca} {etiqueta}" + (f" — {detalle}" if detalle else ""))
        if not ok:
            self.fallos += 1


def _construir_wheel(tmp: Path, v: _Verificador) -> Path:
    dist = tmp / "dist"
    proc = _ejecutar([sys.executable, "-m", "pip", "wheel", ".", "--no-deps",
                      "--no-build-isolation", "--wheel-dir", str(dist)],
                     cwd=RAIZ)
    ruedas = list(dist.glob("*.whl")) if proc.returncode == 0 else []
    v.check(proc.returncode == 0 and len(ruedas) == 1,
            "wheel construido sin red (--no-deps --no-build-isolation)",
            ruedas[0].name if ruedas else proc.stderr.strip()[:200])
    if not ruedas:
        sys.exit(1)
    return ruedas[0]


def _crear_venv(tmp: Path, v: _Verificador) -> Path:
    venv_dir = tmp / "venv"
    venv.EnvBuilder(with_pip=True).create(venv_dir)
    python = _python_venv(venv_dir)
    v.check(python.exists(), "venv temporal creado", str(venv_dir))
    if not python.exists():
        sys.exit(1)
    return venv_dir


def _instalar(rueda: Path, venv_dir: Path, con_red: bool,
              v: _Verificador) -> None:
    python = _python_venv(venv_dir)
    if con_red:
        comando = [str(python), "-m", "pip", "install", str(rueda)]
    else:
        comando = [str(python), "-m", "pip", "install", "--no-index",
                   "--no-deps", str(rueda)]
    proc = _ejecutar(comando)
    v.check(proc.returncode == 0,
            "paquete instalado en el venv" + ("" if con_red
                                              else " (--no-index --no-deps)"),
            proc.stderr.strip()[:200] if proc.returncode else "")


def _verificar_console_scripts(venv_dir: Path, con_red: bool,
                               v: _Verificador, cwd: Path) -> None:
    for nombre in CONSOLE_SCRIPTS:
        exe = _bin_dir(venv_dir) / (nombre + (".exe" if sys.platform == "win32"
                                              else ""))
        v.check(exe.exists(), f"console script `{nombre}` instalado")
        if con_red and exe.exists():
            proc = _ejecutar([str(exe), "--help"], cwd=cwd)
            v.check(proc.returncode == 0, f"`{nombre} --help` ejecuta",
                    proc.stderr.strip()[:150] if proc.returncode else "")


def _verificar_imports(venv_dir: Path, con_red: bool, v: _Verificador,
                       cwd: Path) -> None:
    python = _python_venv(venv_dir)
    if con_red:
        modulos = MODULOS_STDLIB + MODULOS_CON_DEPS
        proc = _ejecutar([str(python), "-c",
                          "import " + ", ".join(modulos)], cwd=cwd)
        v.check(proc.returncode == 0,
                "los 8 módulos públicos + paquetes importan con deps",
                proc.stderr.strip()[:200] if proc.returncode else "")
        return
    for modulo in MODULOS_STDLIB:
        proc = _ejecutar([str(python), "-c", f"import {modulo}"], cwd=cwd)
        v.check(proc.returncode == 0, f"import {modulo} (solo stdlib)",
                proc.stderr.strip()[:150] if proc.returncode else "")
    for modulo in MODULOS_CON_DEPS:
        proc = _ejecutar([str(python), "-c", f"import {modulo}"], cwd=cwd)
        if proc.returncode == 0:
            v.check(True, f"import {modulo} (deps ya presentes, inesperado "
                          "pero válido)")
            continue
        ultimo = proc.stderr.strip().splitlines()[-1] if proc.stderr else ""
        solo_deps = "ModuleNotFoundError" in ultimo and any(
            f"'{dep}'" in ultimo for dep in DEPS_TERCEROS)
        v.check(solo_deps,
                f"import {modulo} falla SOLO por dependencia de terceros",
                ultimo[:150])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--con-red", action="store_true",
                        help="instala también las dependencias (opt-in, red)")
    args = parser.parse_args(argv)

    print(f"VERIFICACIÓN DE INSTALACIÓN LIMPIA ({'con red' if args.con_red else 'offline, --no-deps'})")
    print(f"Repo (read-only): {RAIZ}\n")
    v = _Verificador()
    with tempfile.TemporaryDirectory() as tmp_s:
        tmp = Path(tmp_s)
        cwd_ajeno = tmp / "cwd-ajeno"
        cwd_ajeno.mkdir()
        rueda = _construir_wheel(tmp, v)
        venv_dir = _crear_venv(tmp, v)
        _instalar(rueda, venv_dir, args.con_red, v)
        _verificar_console_scripts(venv_dir, args.con_red, v, cwd_ajeno)
        _verificar_imports(venv_dir, args.con_red, v, cwd_ajeno)

    print()
    if v.fallos:
        print(f"RESULTADO: {v.fallos} comprobaciones fallaron")
        return 1
    cobertura = ("completa (módulos + consola con dependencias)"
                 if args.con_red else
                 "forma del paquete sin dependencias; la ejecución con deps "
                 "se verifica con --con-red")
    print(f"RESULTADO: OK — cobertura declarada: {cobertura}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
