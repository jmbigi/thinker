#!/usr/bin/env python3
"""Escaneo de secretos y datos personales en archivos VERSIONADOS (P0.6/P0.9).

Portable (Python puro; no requiere bash): el hook pre-commit usa el wrapper
`scripts/scan-secrets.sh`, que delega aquí. Uso:

    python3 scripts/scan_secrets.py            # repo actual (git ls-files)
    python3 scripts/scan_secrets.py --root R   # árbol sin git (walk)

Exit 0 si no hay hallazgos, 1 si los hay.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

CREDENCIALES = re.compile(
    r"(sk-[A-Za-z0-9]{16,}|sk-or-v1-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|"
    r"ghp_[A-Za-z0-9]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"xox[baprs]-[A-Za-z0-9-]{10,})")
PERSONALES = re.compile(
    r"(/home/[a-z][a-z0-9_-]+/|/Users/[a-z][a-z0-9_-]+/|"
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.(com|net|org|es|io))")

SUFIJOS_TEXTO = {".py", ".md", ".sh", ".toml", ".txt", ".lock", ".json",
                 ".example", ".yml", ".yaml", ".cfg", ".ini"}

def _archivos_del_repo(raiz: Path):
    """Archivos versionados + nuevos sin ignorar (así el hook ve lo staged).

    Falla cerrado: si git no responde, no se puede afirmar que el repo está
    limpio. Devolver [] y decir «OK» sería un gate silencioso (P1.19).
    """
    try:
        salida = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=raiz, capture_output=True, text=True, check=True).stdout
        return [raiz / linea for linea in salida.splitlines() if linea]
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(
            f"no se pudo listar archivos versionados con git: {exc}") from exc


def _archivos_del_arbol(raiz: Path):
    return [p for p in raiz.rglob("*") if p.is_file()
            and p.suffix in SUFIJOS_TEXTO
            and ".git" not in p.parts and "__pycache__" not in p.parts
            and ".venv" not in p.parts]


def _hallazgos(archivo: Path, patron: re.Pattern):
    try:
        texto = archivo.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        # No se puede leer: se trata como hallazgo para no ocultar una fuga.
        return [(0, f"ERROR DE LECTURA: {exc}")]
    encontrados = []
    for numero, linea in enumerate(texto.splitlines(), 1):
        if patron.search(linea):
            encontrados.append((numero, linea.strip()[:120]))
    return encontrados


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", help="directorio a escanear (sin git)")
    args = parser.parse_args(argv)

    raiz = Path(args.root).resolve() if args.root else Path.cwd()
    try:
        archivos = (_archivos_del_arbol(raiz) if args.root
                    else _archivos_del_repo(raiz))
    except RuntimeError as exc:
        print(f"FALLO: {exc}", file=sys.stderr)
        return 1
    fallo = False
    for patron, etiqueta in ((CREDENCIALES, "Posibles credenciales"),
                             (PERSONALES, "Posibles datos personales o rutas "
                                          "reales")):
        hallazgos = [(a, _hallazgos(a, patron)) for a in archivos]
        hallazgos = [(a, h) for a, h in hallazgos if h]
        if hallazgos:
            print(f"[!] {etiqueta}:")
            for archivo, lineas in hallazgos:
                try:
                    ruta = archivo.relative_to(raiz)
                except ValueError:
                    ruta = archivo
                print(f"   {ruta}:")
                for numero, linea in lineas[:3]:
                    print(f"     {numero}:{linea}")
            fallo = True

    if fallo:
        print("\nFALLO: revisa los hallazgos. Si es un falso positivo, "
              "documéntalo o ajusta el patrón.\n"
              "Ojo: 'API_KEY=' vacío o con '...' es un placeholder y NO debe "
              "coincidir.")
        return 1
    print("OK: sin secretos ni datos personales en archivos versionados")
    return 0


if __name__ == "__main__":
    sys.exit(main())
