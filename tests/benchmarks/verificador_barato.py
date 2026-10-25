#!/usr/bin/env python3
"""Verificador más barato en CoVe, medido offline (R13-B).

Usa dos LLM simulados con nombres distintos: el generador y un verificador
barato. Comprueba que la segunda pasada va al verificador y declara el coste
(1 llamada extra por claim). No mide calidad de modelos reales.
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from deep_research_system import EvidenceEvaluator, ResearchContext  # noqa: E402

VEREDICTO = json.dumps({
    "verdict": "supported", "credibility": 0.9, "confidence": 0.8,
    "reasoning": "evidencia simulada"})


class _LLMContado:
    def __init__(self, model, respuesta=VEREDICTO):
        self.model = model
        self.respuesta = respuesta
        self.llamadas = 0

    def generate(self, prompt, model=None, **kwargs):
        self.llamadas += 1
        return self.respuesta


def ejecutar():
    generador = _LLMContado("generador-grande")
    verificador = _LLMContado("verificador-barato")
    contexto = ResearchContext("q")
    contexto.sources.extend([
        {"url": "u0", "title": "T0", "snippet": "s0"},
        {"url": "u1", "title": "T1", "snippet": "s1"},
    ])

    evaluacion = EvidenceEvaluator(
        generador, verificacion_independiente=True,
        llm_verificador=verificador).decide(
            contexto, {"claim": "c", "source_url": "u0"})
    info = evaluacion.get("verificacion_independiente", {})
    return {
        "llamadas_generador": generador.llamadas,
        "llamadas_verificador": verificador.llamadas,
        "coste_extra": verificador.llamadas,
        "independencia": info.get("independencia"),
        "verificador": info.get("verificador"),
        "generador": info.get("generador"),
        "nota": "LLM simulados; no mide calidad ni latencia reales",
    }


def main():
    print(json.dumps(ejecutar(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
