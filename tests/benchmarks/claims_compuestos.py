#!/usr/bin/env python3
"""Benchmark offline de descomposición de claims compuestos (R13-C).

Un claim "A y B" se evalúa monolíticamente como supported; al descomponerlo,
B se contradice y el agregado pasa a contradicted. Usa LLM simulado (StubLLM).
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from deep_research_system import EvidenceEvaluator, ResearchContext  # noqa: E402
from tests.helpers import StubLLM  # noqa: E402


def _respuesta(prompt):
    if "Claim: B es falso" in prompt:
        return json.dumps({"verdict": "contradicted", "credibility": 0.1,
                           "confidence": 0.9, "reasoning": "B no se sostiene"})
    if "Claim: A es verdad" in prompt:
        return json.dumps({"verdict": "supported", "credibility": 0.9,
                           "confidence": 0.9, "reasoning": "A sí"})
    return json.dumps({"verdict": "supported", "credibility": 0.9,
                       "confidence": 0.9, "reasoning": "monolítico"})


def _contexto():
    contexto = ResearchContext("q")
    contexto.sources.extend([
        {"url": "u0", "title": "T0", "snippet": "s0"},
        {"url": "u1", "title": "T1", "snippet": "s1"},
    ])
    return contexto


def ejecutar():
    claim = {"claim": "A es verdad y B es falso", "source_url": "u0"}
    mono_llm = StubLLM(_respuesta)
    mono = EvidenceEvaluator(mono_llm, descomponer_claims=False).decide(
        _contexto(), claim)
    desc_llm = StubLLM(_respuesta)
    desc = EvidenceEvaluator(desc_llm, descomponer_claims=True).decide(
        _contexto(), claim)
    return {
        "monolitico": {
            "verdict": mono.get("verdict"),
            "llamadas": len(mono_llm.prompts),
            "subclaims": len(mono.get("subclaims", [])),
        },
        "descompuesto": {
            "verdict": desc.get("verdict"),
            "llamadas": len(desc_llm.prompts),
            "subclaims": len(desc.get("subclaims", [])),
            "regla": "cualquier contradicted => contradicted",
        },
        "mejora": (mono.get("verdict") == "supported"
                   and desc.get("verdict") == "contradicted"),
        "nota": "LLM simulado; no mide calidad real de descomposición",
    }


def main():
    print(json.dumps(ejecutar(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
