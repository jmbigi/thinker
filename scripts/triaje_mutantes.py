#!/usr/bin/env python3
"""Inventario de triaje de supervivientes de mutmut (R3).

No declara equivalentes: clasifica cada superviviente por función y por
cobertura. Un superviviente en una función ejecutada es una **brecha de
aserción**; en una función no ejecutada es una **brecha de test**. Los timeouts
se listan aparte. Así ningún superviviente queda sin categoría, pero la deuda
sigue visible (no se convierte en "equivalente" sin prueba).

Uso:
    python3 scripts/triaje_mutantes.py --destino build/mut-preflight-final \
        --cobertura build/cov-preflight.json --salida build/triaje-preflight.json
"""

import argparse
import ast
import collections
import json
import os
from difflib import unified_diff
from pathlib import Path



def _rangos_de_funciones(fuente: str):
    arbol = ast.parse(fuente)
    rangos = {}
    for nodo in arbol.body:
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)):
            rangos[nodo.name] = list(range(nodo.lineno, nodo.end_lineno + 1))
    return rangos


def _ejecutadas(ruta_cobertura: Path, archivo: str):
    datos = json.loads(ruta_cobertura.read_text(encoding="utf-8"))
    return set(datos["files"].get(archivo, {}).get("executed_lines", []))


def clasificar(destino: Path, ruta_cobertura: Path) -> dict:
    destino = destino.resolve()
    ruta_cobertura = ruta_cobertura.resolve()
    anterior = os.getcwd()
    os.chdir(destino)
    from mutmut.__main__ import (Config, SourceFileMutationData, cst,
                                 read_mutant_function, read_mutants_module,
                                 read_original_function, status_by_exit_code,
                                 walk_mutatable_files)
    Config.ensure_loaded()
    path = next(iter(walk_mutatable_files()))
    data = SourceFileMutationData(path=path)
    data.load()
    module = read_mutants_module(path)
    fuente_original = Path(path).read_text(encoding="utf-8")
    rangos = _rangos_de_funciones(fuente_original)
    ejecutadas = _ejecutadas(ruta_cobertura, str(path))
    registros = []
    for nombre, codigo in data.exit_code_by_key.items():
        estado = status_by_exit_code[codigo]
        if estado not in ("survived", "timeout"):
            continue
        funcion = nombre.split(".")[-1].rsplit("__mutmut", 1)[0]
        if funcion.startswith("x_"):
            funcion = funcion[2:]
        lineas = rangos.get(funcion, [])
        cubierta = bool(lineas and any(linea in ejecutadas for linea in lineas))
        if estado == "timeout":
            cubo = "timeout"
        elif not cubierta:
            cubo = "sin_cobertura"
        else:
            cubo = "cobertura_sin_deteccion"
        orig = cst.Module([read_original_function(module, nombre)]).code.strip()
        mut = cst.Module([read_mutant_function(module, nombre)]).code.strip()
        cambios = [linea for linea in unified_diff(
            orig.split("\n"), mut.split("\n"), lineterm="")
            if linea.startswith(("+", "-"))
            and not linea.startswith(("+++", "---"))]
        registros.append({
            "nombre": nombre,
            "funcion": funcion,
            "estado": estado,
            "cubo": cubo,
            "clasificacion": ("timeout_no_equivalente" if estado == "timeout"
                              else "brecha_de_asercion"),
            "lineas_funcion": lineas[:1] + lineas[-1:],
            "cambios": cambios,
        })
    os.chdir(anterior)
    resumen = collections.Counter(r["cubo"] for r in registros)
    por_funcion = collections.Counter(r["funcion"] for r in registros)
    return {
        "objetivo": str(path),
        "total_supervivientes": len(registros),
        "resumen": dict(resumen),
        "por_funcion": por_funcion.most_common(),
        "registros": registros,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--destino", type=Path, required=True)
    p.add_argument("--cobertura", type=Path, required=True)
    p.add_argument("--salida", type=Path, required=True)
    args = p.parse_args(argv)
    informe = clasificar(args.destino, args.cobertura)
    args.salida.write_text(json.dumps(informe, ensure_ascii=False, indent=1),
                           encoding="utf-8")
    print(json.dumps({"total": informe["total_supervivientes"],
                      "resumen": informe["resumen"]},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
