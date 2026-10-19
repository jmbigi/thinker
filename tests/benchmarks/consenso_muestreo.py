#!/usr/bin/env python3
"""Benchmark offline del detector de discrepancias por muestreo (Hallazgo 76).

Mide, sin red ni API keys (LLM SIMULADO y declarado):
1. DETECCIÓN: con 3 muestras donde 1 diverge, el evaluador marca
   `discrepancia_muestreo` y lo registra en el `decision_log`.
2. FALSOS POSITIVOS: con 3 muestras idénticas, no marca discrepancia.
3. COSTE: llamadas LLM reales (3 con `muestras_consenso=3` frente a 1 por
   defecto) y llamadas extra declaradas por el propio evaluador.

Uso:
    python3 tests/benchmarks/consenso_muestreo.py
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

from deep_research_system import EvidenceEvaluator, ResearchContext  # noqa: E402
from tests.helpers import StubLLM  # noqa: E402

VEREDICTO_APOYADO = '{"verdict": "supported", "credibility": 0.9}'
VEREDICTO_CONTRADICE = '{"verdict": "contradicted", "credibility": 0.2}'


def _contexto():
    contexto = ResearchContext("benchmark-consenso")
    contexto.sources.append({"url": "u0", "title": "T0", "snippet": "s0"})
    return contexto


def caso_divergente():
    """Una muestra contradice a las otras dos: debe marcarse discrepancia."""
    cola = iter([VEREDICTO_APOYADO, VEREDICTO_CONTRADICE, VEREDICTO_CONTRADICE])
    llm = StubLLM(lambda p: next(cola))
    contexto = _contexto()

    evaluacion = EvidenceEvaluator(llm, muestras_consenso=3).decide(
        contexto, {"claim": "c", "source_url": "u0"})
    consenso = evaluacion["consenso_muestreo"]
    decisiones = [d for d in contexto.decision_log
                  if d["step"] == "sampling_consensus"]

    return {
        "detectado": bool(evaluacion.get("discrepancia_muestreo")),
        "acuerdo": consenso["acuerdo"],
        "verdicts": consenso["verdicts"],
        "llamadas_reales": len(llm.prompts),
        "llamadas_extra_declaradas": consenso["llamadas_extra"],
        "decision": decisiones[-1]["decision"] if decisiones else None,
    }


def caso_acuerdo():
    """Tres muestras idénticas: no debe marcar discrepancia."""
    llm = StubLLM(lambda p: VEREDICTO_APOYADO)
    contexto = _contexto()

    evaluacion = EvidenceEvaluator(llm, muestras_consenso=3).decide(
        contexto, {"claim": "c", "source_url": "u0"})

    return {
        "falso_positivo": bool(evaluacion.get("discrepancia_muestreo")),
        "acuerdo": evaluacion["consenso_muestreo"]["acuerdo"],
        "llamadas_reales": len(llm.prompts),
    }


def caso_por_defecto():
    """Sin muestreo (defecto): una sola llamada y sin claves nuevas."""
    llm = StubLLM(lambda p: VEREDICTO_APOYADO)
    contexto = _contexto()

    evaluacion = EvidenceEvaluator(llm).decide(
        contexto, {"claim": "c", "source_url": "u0"})

    return {
        "llamadas_reales": len(llm.prompts),
        "consenso_activo": "consenso_muestreo" in evaluacion,
    }


def main() -> int:
    resultado = {
        "escenario": "consenso-muestreo (offline, LLM simulado declarado)",
        "divergente": caso_divergente(),
        "acuerdo": caso_acuerdo(),
        "por_defecto": caso_por_defecto(),
    }
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
