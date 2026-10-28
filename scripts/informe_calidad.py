#!/usr/bin/env python3
"""Informe de calidad verificable: ejecuta los gates y escribe un JSON con su
estado real (`PASS`, `FAIL`, `NOT_RUN`), fecha, commit y entorno.

No marca como aprobado un control que no se ejecutó: si un comando falla al
lanzarse (herramienta ausente) o se omite, el estado es `NOT_RUN` con el
motivo. `--solo NOMBRE` ejecuta un subconjunto (útil para tests y para
diagnóstico rápido).

Uso:
    python3 scripts/informe_calidad.py                # ejecuta todo y escribe docs/informe-calidad.json
    python3 scripts/informe_calidad.py --json         # imprime, no escribe
    python3 scripts/informe_calidad.py --solo ruff    # un control
"""

import argparse
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Cada control es un comando real del repo; el informe declara su estado.
CONTROLES = [
    ("ruff", [sys.executable, "-m", "ruff", "check", "."]),
    ("preflight", [sys.executable, "scripts/preflight.py"]),
    ("docs-check", [sys.executable, "scripts/check_docs.py"]),
    ("tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests"]),
    ("holdout", [sys.executable, "scripts/run_holdout.py"]),
    ("secrets", [sys.executable, "scripts/scan_secrets.py"]),
    ("doctor", [sys.executable, "scripts/doctor.py"]),
]


def _git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=RAIZ,
                              capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _ejecutar_control(nombre, comando, timeout=900):
    inicio = time.monotonic()
    try:
        proc = subprocess.run(comando, cwd=RAIZ, capture_output=True,
                              text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"estado": "NOT_RUN", "motivo": f"{type(exc).__name__}: {exc}",
                "duracion_s": round(time.monotonic() - inicio, 1)}
    salida = (proc.stdout or "") + (proc.stderr or "")
    resumen = ""
    if nombre == "tests":
        resumen = " | ".join(
            linea for linea in salida.splitlines()
            if linea.startswith(("Ran ", "OK", "FAILED")))
    elif nombre == "mutacion":
        resumen = "campaña externa (make mutation / scripts/mutacion.py)"
    return {
        "estado": "PASS" if proc.returncode == 0 else "FAIL",
        "codigo": proc.returncode,
        "resumen": resumen or (salida.strip().splitlines()[-1][:200]
                               if salida.strip() else ""),
        "duracion_s": round(time.monotonic() - inicio, 1),
    }


def generar(solo=None):
    controles = [(n, c) for n, c in CONTROLES if solo is None or n == solo]
    resultados = {}
    for nombre, comando in controles:
        resultados[nombre] = _ejecutar_control(nombre, comando)
    return {
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit": _git_commit(),
        "python": platform.python_version(),
        "so": platform.platform(),
        "controles": resultados,
        "no_ejecutados": [n for n, _ in CONTROLES
                          if solo is not None and n != solo],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true",
                        help="imprime el informe y no escribe archivo")
    parser.add_argument("--solo", help="ejecuta solo el control indicado")
    args = parser.parse_args(argv)

    informe = generar(args.solo)
    texto = json.dumps(informe, ensure_ascii=False, indent=2)
    if args.json:
        print(texto)
    else:
        destino = RAIZ / "docs" / "informe-calidad.json"
        destino.write_text(texto + "\n", encoding="utf-8")
        print(f"Informe escrito en {destino.relative_to(RAIZ)}")
        for nombre, datos in informe["controles"].items():
            print(f"  {datos['estado']:8s} {nombre}"
                  f" ({datos['duracion_s']} s)")
    return 0 if all(d["estado"] == "PASS"
                    for d in informe["controles"].values()) else 1


if __name__ == "__main__":
    sys.exit(main())
