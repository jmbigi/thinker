#!/usr/bin/env python3
"""Ejecuta el holdout independiente y verifica que no fue alterado.

El holdout vive en `holdout/` y **no** se descubre con `make test`. El
manifiesto `holdout/HASHES.json` fija el SHA-256 de cada test: si un test
cambia sin actualizar el manifiesto, el runner falla. No es una protección
criptográfica contra alguien que edite ambos artefactos; es tamper-evidence y
debe ejecutarse fuera del alcance de escritura del agente (hook, CI u otro
checkout).
"""

import argparse
import hashlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

HOLDOUT_DIR = REPO_ROOT / "holdout"
MANIFEST = HOLDOUT_DIR / "HASHES.json"
PATRON = "test_*.py"


def calcular_hashes(directorio: Path = HOLDOUT_DIR) -> Dict[str, str]:
    return {
        archivo.name: hashlib.sha256(archivo.read_bytes()).hexdigest()
        for archivo in sorted(directorio.glob(PATRON))
        if archivo.is_file()
    }


def actualizar_manifiesto(directorio: Path = HOLDOUT_DIR,
                          manifiesto: Path = MANIFEST) -> Dict[str, object]:
    datos = {"version": 1, "files": calcular_hashes(directorio)}
    manifiesto.parent.mkdir(parents=True, exist_ok=True)
    manifiesto.write_text(json.dumps(datos, indent=2, sort_keys=True) + "\n",
                          encoding="utf-8")
    return datos


def verificar_hashes(directorio: Path = HOLDOUT_DIR,
                     manifiesto: Path = MANIFEST) -> Dict[str, str]:
    if not manifiesto.is_file():
        raise ValueError(f"No existe el manifiesto {manifiesto}; ejecuta "
                         "--update y revisa el cambio")
    try:
        datos = json.loads(manifiesto.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"No se pudo leer {manifiesto}: {exc}") from exc
    esperados = datos.get("files") if isinstance(datos, dict) else None
    if not isinstance(esperados, dict):
        raise ValueError(f"{manifiesto}: falta el mapa 'files'")
    reales = calcular_hashes(directorio)
    faltan = sorted(set(esperados) - set(reales))
    sobran = sorted(set(reales) - set(esperados))
    cambiados = sorted(nombre for nombre in set(esperados) & set(reales)
                       if esperados[nombre] != reales[nombre])
    if faltan or sobran or cambiados:
        detalles = []
        if faltan:
            detalles.append(f"faltan: {', '.join(faltan)}")
        if sobran:
            detalles.append(f"sobran: {', '.join(sobran)}")
        if cambiados:
            detalles.append(f"cambiados: {', '.join(cambiados)}")
        raise ValueError("holdout alterado sin actualizar HASHES.json: "
                         + "; ".join(detalles))
    return reales


def ejecutar_tests(directorio: Path = HOLDOUT_DIR) -> bool:
    archivos = sorted(directorio.glob(PATRON))
    if not archivos:
        raise ValueError(f"No hay tests holdout en {directorio}")
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for archivo in archivos:
        spec = importlib.util.spec_from_file_location(
            f"holdout_{archivo.stem}", archivo)
        if spec is None or spec.loader is None:
            raise ValueError(f"No se pudo cargar {archivo}")
        modulo = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(modulo)
        except Exception as exc:  # el runner reporta, no oculta
            raise ValueError(f"No se pudo importar {archivo}: {exc}") from exc
        suite.addTests(loader.loadTestsFromModule(modulo))
    resultado = unittest.TextTestRunner(verbosity=2).run(suite)
    return resultado.wasSuccessful()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verifica hashes y ejecuta el holdout independiente.")
    parser.add_argument("--update", action="store_true",
                        help="regenera HASHES.json; revisar el diff después")
    args = parser.parse_args(argv)

    try:
        if args.update:
            datos = actualizar_manifiesto()
            print(f"HOLDOUT: manifiesto actualizado "
                  f"({len(datos['files'])} tests)")
            return 0
        verificar_hashes()
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    try:
        correcto = ejecutar_tests()
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if not correcto:
        print("HOLDOUT: FAIL", file=sys.stderr)
        return 1
    print("HOLDOUT: OK (hashes y tests)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
