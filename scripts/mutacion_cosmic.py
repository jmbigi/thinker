#!/usr/bin/env python3
"""Mutación con cosmic-ray (motor independiente de mutmut, Hallazgo 143).

Las campañas con mutmut quedaron bloqueadas porque declara «killed» mutantes
que sobreviven a la misma suite (cuatro hipótesis descartadas; el experimento
blanco muestra que mutmut funciona en general, así que el defecto es de la
interacción con esta suite). cosmic-ray aporta maquinaria independiente:
genera los mutantes, ejecuta el test-command por mutante y deja una sesión
SQLite consultable.

Seguridad (P0.3): cosmic-ray aplica y restaura el archivo mutado EN SU RUTA.
Por eso la config apunta siempre a una **copia** del repo en el destino
(`scripts/mutacion.py: copiar_proyecto`), nunca al árbol de trabajo.

La campaña completa de `evaluar_proyecto.py` tarda HORAS (miles de mutantes ×
la suite del evaluador): este script no la lanza por defecto. Usos:

    python3 scripts/mutacion_cosmic.py --config --destino DIR
        # copia el repo a DIR y genera la config (sin ejecutar)
    python3 scripts/mutacion_cosmic.py --init --destino DIR
        # genera la sesión (lista los mutantes; minutos)
    python3 scripts/mutacion_cosmic.py --exec --destino DIR
        # ejecuta la campaña completa (horas; avisar antes, P2.5)
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
# `python3 scripts/mutacion_cosmic.py` deja sys.path[0]=scripts/: sin esto,
# `from scripts.mutacion import copiar_proyecto` no se resuelve (mismo
# mecanismo documentado en el Hallazgo 142 para scripts/doctor.py).
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

SELECCION_TESTS = ("tests/test_evaluar_proyecto.py "
                   "tests/test_evaluador_corpus.py "
                   "tests/test_evaluador_precision.py")


def generar_config(destino: Path, timeout: float = 60.0) -> Path:
    """Config TOML de cosmic-ray sobre la COPIA en `destino` (función pura).

    `module-path` y `test-command` son relativos al directorio de ejecución
    (el destino), nunca al repo: cosmic-ray reemplaza el archivo durante la
    ejecución y un fallo a mitad no debe dejar el árbol de trabajo mutado.
    """
    destino.mkdir(parents=True, exist_ok=True)
    config = destino / "config.toml"
    config.write_text(
        "[cosmic-ray]\n"
        'module-path = "evaluar_proyecto.py"\n'
        f"timeout = {timeout}\n"
        f'test-command = "{sys.executable} -m pytest -x -q '
        f'{SELECCION_TESTS}"\n\n'
        "[cosmic-ray.distributor]\n"
        'name = "local"\n',
        encoding="utf-8")
    return config


def _cosmic(argumentos, cwd):
    return subprocess.run([sys.executable, "-m", "cosmic_ray", *argumentos],
                          cwd=cwd, capture_output=True, text=True,
                          timeout=86400)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--destino", default=None,
                        help="directorio de trabajo (por defecto, temporal)")
    parser.add_argument("--timeout", type=float, default=60.0,
                        help="timeout por mutante en segundos")
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument("--config", action="store_true",
                       help="copia el repo al destino y genera la config")
    grupo.add_argument("--init", action="store_true",
                       help="genera la sesión (lista los mutantes)")
    grupo.add_argument("--exec", action="store_true",
                       help="ejecuta la campaña completa (HORAS)")
    args = parser.parse_args(argv)

    destino = Path(args.destino) if args.destino \
        else Path(tempfile.mkdtemp(prefix="cosmic-evaluar-"))
    from scripts.mutacion import copiar_proyecto
    copiar_proyecto(destino)
    config = generar_config(destino, args.timeout)
    print(f"config: {config}")
    if args.config:
        print("(sin ejecutar; usa --init y --exec para la campaña)")
        return 0
    sesion = destino / "session.sqlite"
    if args.init:
        proc = _cosmic(["init", str(config), str(sesion)], destino)
        print(proc.stdout[-500:] or proc.stderr[-500:])
        return proc.returncode
    proc = _cosmic(["exec", str(config), str(sesion)], destino)
    print(proc.stdout[-500:] or proc.stderr[-500:])
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
