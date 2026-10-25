#!/usr/bin/env python3
"""Brier y tabla de fiabilidad offline, con confianzas SIMULADAS (R14-B).

No mide calibración real: usa pares (confianza, acierto) fijos para probar el
instrumento. La declaración «confidence no calibrada» sigue vigente hasta que
haya etiquetas reales (R14-C).

Uso:
    python3 tests/benchmarks/calibracion_confianza.py [--json]
"""

import argparse
import json
import sys

# (confianza declarada, acierto binario). Simulados y declarados como tales.
CASOS_SIMULADOS = [
    (0.95, True), (0.90, True), (0.85, True), (0.80, True),
    (0.75, True), (0.70, False), (0.65, True), (0.60, False),
    (0.55, True), (0.50, False), (0.40, False), (0.30, False),
    (0.20, False), (0.10, False), (0.05, False), (0.00, False),
]

TRAMOS = ((0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.0))


def calcular_brier(casos):
    """Brier = media de (confianza - acierto)^2; menor es mejor."""
    if not casos:
        return None
    return sum((confianza - (1.0 if acierto else 0.0)) ** 2
               for confianza, acierto in casos) / len(casos)


def tabla_fiabilidad(casos):
    """Cuenta, confianza media y frecuencia observada por tramo."""
    tabla = []
    for inferior, superior in TRAMOS:
        en_tramo = [(c, a) for c, a in casos
                    if (inferior <= c < superior)
                    or (superior == 1.0 and c == 1.0)]
        if not en_tramo:
            tabla.append({"tramo": f"{inferior:.1f}-{superior:.1f}",
                          "n": 0, "confianza_media": None,
                          "frecuencia": None})
            continue
        tabla.append({
            "tramo": f"{inferior:.1f}-{superior:.1f}",
            "n": len(en_tramo),
            "confianza_media": round(
                sum(c for c, _ in en_tramo) / len(en_tramo), 3),
            "frecuencia": round(
                sum(1 for _, a in en_tramo if a) / len(en_tramo), 3),
        })
    return tabla


def evaluar(casos=None):
    casos = CASOS_SIMULADOS if casos is None else casos
    return {
        "casos": len(casos),
        "brier": round(calcular_brier(casos), 4)
        if calcular_brier(casos) is not None else None,
        "tabla_fiabilidad": tabla_fiabilidad(casos),
        "calibrada": False,
        "nota": ("confianzas simuladas; el Brier no prueba calibración real. "
                 "La declaración «no calibrada» sigue vigente (R14)."),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    resultado = evaluar()
    if args.json:
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
        return 0
    print(f"Brier offline (simulado): {resultado['brier']:.4f} "
          f"en {resultado['casos']} casos")
    print(f"{'tramo':10} {'n':>3} {'confianza':>10} {'frecuencia':>10}")
    for fila in resultado["tabla_fiabilidad"]:
        conf = "-" if fila["confianza_media"] is None \
            else f"{fila['confianza_media']:.2f}"
        frec = "-" if fila["frecuencia"] is None \
            else f"{fila['frecuencia']:.2f}"
        print(f"{fila['tramo']:10} {fila['n']:>3} {conf:>10} {frec:>10}")
    print(resultado["nota"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
