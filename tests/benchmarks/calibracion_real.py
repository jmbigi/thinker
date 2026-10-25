#!/usr/bin/env python3
"""Piloto de Brier con llamadas reales y etiquetas humanas (R14-C).

Casos factuales con fuente y veredicto esperado; mide si la `confidence` del
modelo coincide con el acierto. Es una muestra pequeña y declarada, no una
calibración definitiva. Requiere OPENROUTER_API_KEY y red (opt-in).

Uso:
    python3 tests/benchmarks/calibracion_real.py [--json]
"""

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from deep_research_system import EvidenceEvaluator, ResearchContext  # noqa: E402
from dotenv import load_dotenv  # noqa: E402
from llm_providers import OpenRouterLLM  # noqa: E402


CASOS = [
    {
        "claim": "El agua hierve a 100 grados Celsius al nivel del mar.",
        "fuente": "Al nivel del mar, el agua hierve a 100 grados Celsius.",
        "esperado": "supported",
    },
    {
        "claim": "La Tierra es plana.",
        "fuente": "La Tierra es un elipsoide achatado en los polos.",
        "esperado": "contradicted",
    },
    {
        "claim": "Python 3.11 se publico en 2022.",
        "fuente": "Python 3.11 fue lanzado en octubre de 2022.",
        "esperado": "supported",
    },
    {
        "claim": "El Sol gira alrededor de la Tierra.",
        "fuente": "La Tierra orbita alrededor del Sol.",
        "esperado": "contradicted",
    },
    {
        "claim": "La capital de Francia es Paris.",
        "fuente": "Paris es la capital de Francia.",
        "esperado": "supported",
    },
    {
        "claim": "El oro es un gas a temperatura ambiente.",
        "fuente": "El oro es un metal solido a temperatura ambiente.",
        "esperado": "contradicted",
    },
]


def calcular_brier(confianzas, aciertos):
    if not confianzas:
        return None
    return sum((c - (1.0 if a else 0.0)) ** 2
               for c, a in zip(confianzas, aciertos)) / len(confianzas)


def tabla_fiabilidad(confianzas, aciertos):
    tramos = ((0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.0))
    filas = []
    for inferior, superior in tramos:
        pares = [(c, a) for c, a in zip(confianzas, aciertos)
                 if (inferior <= c < superior)
                 or (superior == 1.0 and c == 1.0)]
        filas.append({
            "tramo": f"{inferior:.1f}-{superior:.1f}",
            "n": len(pares),
            "confianza_media": round(sum(c for c, _ in pares) / len(pares), 3)
            if pares else None,
            "frecuencia": round(sum(1 for _, a in pares if a) / len(pares), 3)
            if pares else None,
        })
    return filas


def ejecutar():
    load_dotenv()
    if not os.environ.get("OPENROUTER_API_KEY"):
        return {"error": "sin OPENROUTER_API_KEY; no se prueba (regla 10)"}
    llm = OpenRouterLLM()
    llm.max_retries = 2
    evaluador = EvidenceEvaluator(llm)
    confianzas, aciertos, detalle = [], [], []
    for caso in CASOS:
        contexto = ResearchContext(caso["claim"])
        contexto.sources.append({
            "url": "fuente", "title": "Fuente",
            "snippet": caso["fuente"]})
        evaluacion = evaluador.decide(
            contexto, {"claim": caso["claim"], "source_url": "fuente"})
        confianza = float(evaluacion.get("confidence", 0.0) or 0.0)
        acierto = evaluacion.get("verdict") == caso["esperado"]
        confianzas.append(confianza)
        aciertos.append(acierto)
        detalle.append({
            "claim": caso["claim"],
            "esperado": caso["esperado"],
            "verdict": evaluacion.get("verdict"),
            "confidence": confianza,
            "acierto": acierto,
        })
    return {
        "n": len(CASOS),
        "brier": round(calcular_brier(confianzas, aciertos), 4),
        "tabla_fiabilidad": tabla_fiabilidad(confianzas, aciertos),
        "calibrada": False,
        "modelo": getattr(llm, "model", "?"),
        "nota": ("muestra pequeña y factual; no prueba calibración general. "
                 "La declaración «no calibrada» sigue vigente."),
        "detalle": detalle,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    resultado = ejecutar()
    if args.json:
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
    else:
        if "error" in resultado:
            print(resultado["error"], file=sys.stderr)
            return 2
        print(f"Brier real: {resultado['brier']} en {resultado['n']} casos "
              f"(modelo {resultado['modelo']})")
        print(resultado["nota"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
