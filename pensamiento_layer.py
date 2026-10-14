#!/usr/bin/env python3
"""
Pensamiento Layer - Capa de Razonamiento Estructurado para Sistemas LLM
=====================================================================

Implementa un "pensamiento" deliberado que las LLMs no tienen de forma natural.
Evita el "prueba y error" repetitivo al forzar raciocinio estructurado en pasos
claros y verificables antes de generar salida.

El ciclo de pasos (validación, confianza, forma del resultado) vive en
`thinking_engine.StepThinkingEngine` y es compartido con las herramientas de
diseño de código: aquí sólo se definen los 7 pasos de investigación.

Principios clave:
1. Pensamiento externado: el razonamiento se muestra explícitamente
2. Decomposición paso a paso: cada decisión tiene un paso explícito
3. Verificación antes de avanzar: se valida cada paso antes de continuar
4. Patrón anti-repitencia: si un paso falla, el ciclo se detiene y se reporta
"""

from typing import Any, Dict, List, Tuple

from thinking_engine import StepThinkingEngine

# Nombre histórico mantenido por compatibilidad.
ThinkingLayer = StepThinkingEngine


class DeepResearchThinkingLayer(StepThinkingEngine):
    """
    Capa de pensamiento profunda específicamente para sistemas de investigación.
    Implementa 7 pasos deliberados para evitar decisiones precipitadas.
    """

    def __init__(self, llm_provider, name: str = "deep_research_thinking"):
        super().__init__(llm_provider, name, max_steps=7)

    def _validate_step(self, thought: str, decision: Any = None) -> bool:
        """Compatibilidad: delega en el validador común."""
        return self.validate_step(thought)

    def _step_builders(self) -> List[Tuple[str, Any]]:
        def step1(o):
            return f"""
PASO 1 - ANÁLISIS DE PREGUNTA:
Analiza esta pregunta de investigación profundamente. Identifica:
- El objetivo principal
- Las variables clave
- Las suposiciones implícitas
- Los posibles sesgos
- Las lagunas de información

Pregunta: {o['prompt']}

Respuesta estructurada en formato JSON:
{{
  "objetivo": "...",
  "variables": ["..."],
  "suposiciones": ["..."],
  "sesgos_posibles": ["..."],
  "lagunas": ["..."]
}}
"""

        def step2(o):
            return f"""
PASO 2 - PLAN DE INVESTIGACIÓN:
Basado en el análisis, diseña un plan de investigación con:
- Sub-preguntas específicas (3-5)
- Fuentes esperadas
- Métricas de éxito
- Iteraciones máximas

Contexto: {o['context']}

Análisis previo: {o['analysis']}

Genera el plan en JSON:
{{
  "subpreguntas": ["..."],
  "fuentes_objetivo": ["..."],
  "metricas_exito": ["..."],
  "max_iteraciones": 5
}}
"""

        def step3(o):
            return f"""
PASO 3 - ESTRATEGIA DE BÚSQUEDA:
Define la estrategia de búsqueda considerando:
- Motores de búsqueda preferidos
- Palabras clave y booleanos
- Fecha de corte de información
- Diversidad de fuentes

Plan anterior: {o['plan']}

Estrategia: {{
  "motores": ["..."],
  "palabras_clave": "...",
  "booleanos": "...",
  "fecha_corte": "YYYY-MM-DD",
  "diversidad": "descripción"
}}
"""

        def step4(o):
            return f"""
PASO 4 - RESULTADOS DE BÚSQUEDA:
Ejecuta la estrategia y resume los hallazgos clave.

Estrategia: {o['search_strategy']}

Hallazgos resumidos:
- Fuente principal: título, URL, relevancia (0-1)
- Afirmaciones destacadas: 3 máximo
- Contradicciones potenciales: 3 máximo

Formato JSON:
{{
  "fuentes": [{{
    "titulo": "...",
    "url": "...",
    "relevancia": 0-1
  }}],
  "afirmaciones": ["..."],
  "contradicciones": ["..."]
}}
"""

        def step5(o):
            return f"""
PASO 5 - EXTRACCIÓN DE CLAIMS:
Extrae claims verificables de los hallazgos.

Hallazgos: {o['search_results']}

Para cada claim, proporciona:
- claim: texto exacto
- confidence: 0-1 (qué tan cierto parece)
- source_quality: 0-1 (calidad de la fuente)
- verificable: sí/no

JSON array:
[
  {{
    "claim": "...",
    "confidence": 0-1,
    "source_quality": 0-1,
    "verificable": true/false
  }}
]
"""

        def step6(o):
            return f"""
PASO 6 - EVALUACIÓN DE EVIDENCIA:
Evalúa cada claim contra la evidencia disponible.

Claims: {o['claim_extraction']}

Para cada claim, determina:
- verdict: "supported" | "contradicted" | "not_addressed"
- credibility: 0-1 (credibilidad de las fuentes)
- strength: 0-1 (fuerza de la evidencia)
- reasoning: explicación breve

JSON array:
[
  {{
    "claim": "...",
    "verdict": "...",
    "credibility": 0-1,
    "strength": 0-1,
    "reasoning": "..."
  }}
]
"""

        def step7(o):
            return f"""
PASO 7 - SÍNTESIS Y CONCLUSIONES:
Sintetiza todos los hallazgos evaluados.

Evidencia evaluada: {o['evidence_eval']}

Produce:
1. Conclusiones principales (máximo 3, con niveles de confianza)
2. Puntos que requieren más investigación
3. Limitaciones identificadas
4. Recomendaciones accionables

Formato JSON:
{{
  "conclusiones": [
    {{
      "enunciado": "...",
      "confianza": 0-1,
      "basada_en": ["claim_id_1", "claim_id_2"]
    }}
  ],
  "gaps": ["..."],
  "recomendaciones": ["..."]
}}
"""

        return [
            ("analysis", step1),
            ("plan", step2),
            ("search_strategy", step3),
            ("search_results", step4),
            ("claim_extraction", step5),
            ("evidence_eval", step6),
            ("synthesis", step7),
        ]

    def _render_thought(self, steps: List[Tuple[str, str]]) -> str:
        by_name = dict(steps)
        lines = [
            f"        CAPA DE PENSAMIENTO: {self.name}",
            "        ============================",
            "",
        ]
        etiquetas = {
            "analysis": "ANÁLISIS",
            "plan": "PLAN",
            "search_strategy": "ESTRATEGIA",
            "search_results": "RESULTADOS",
            "claim_extraction": "CLAIMS",
            "evidence_eval": "EVALUACIÓN",
            "synthesis": "SÍNTESIS",
        }
        numero = 0
        for name, _ in self._step_builders():
            if name not in by_name:
                continue
            numero += 1
            lines.append(f"        PASO {numero} - {etiquetas[name]}: {by_name[name][:200]}")

        lines.extend([
            "",
            f"        PASOS COMPLETADOS: {len(steps)}/{self.max_steps}",
            f"        CONFIANZA GENERAL: {self._compute_confidence(steps)}",
            f"        VALIDEZ: {'VALID' if self.validate_step(steps[-1][1]) and all(self.validate_step(c) for _, c in steps) else 'REVISAR'}",
        ])
        return "\n".join(lines)


class ResearchOrchestratorWithThinking:
    """
    Orquestador que integra la capa de pensamiento en el flujo de investigación.

    Honestidad: la extracción/evaluación de claims de esta clase usa
    heurísticas locales SIMULADAS (declaradas en el resultado). Para
    extracción real con LLM, usar `ResearchOrchestrator` de
    `deep_research_system`.
    """

    def __init__(self, llm_provider, search_api, thinking_layer: DeepResearchThinkingLayer):
        self.llm = llm_provider
        self.search = search_api
        self.thinking = thinking_layer
        self.context = None
        self.results = None

    def research_with_thinking(self, question: str) -> Dict[str, Any]:
        """Ejecuta investigación con la capa de pensamiento completa."""

        print("\n=== INICIANDO INVESTIGACIÓN CON CAPA DE PENSAMIENTO ===")
        print(f"Pregunta: {question}\n")

        # Paso 1: ciclo de pensamiento estructurado (7 pasos internos, una sola vez)
        print(">>> Ciclo de pensamiento estructurado (7 pasos)...")
        thinking_result = self.thinking.think(question)
        print(f"   Pasos: {thinking_result['step_count']}, "
              f"Confianza: {thinking_result['confidence']:.2f}, "
              f"Válido: {thinking_result['valid']}")

        if not thinking_result['valid']:
            return {
                "error": "Ciclo de pensamiento no válido; replantear la pregunta (anti-repitencia)",
                "thinking": thinking_result,
            }

        # Paso 2: búsqueda real con la API de búsqueda configurada
        print(">>> Ejecutando búsqueda...")
        search_results = self.search.search(question)
        print(f"   {len(search_results)} resultados")

        # Pasos 3-5: heurísticas locales SIMULADAS (declaradas en el resultado)
        print(">>> Extrayendo claims (heurística local simulada)...")
        claims = self._extract_claims_with_thought(search_results)
        print(f"   {len(claims)} claims extraídos")

        print(">>> Evaluando evidencia (heurística local simulada)...")
        evaluations = self._evaluate_evidence_with_thought(claims)
        print(f"   {len(evaluations)} claims evaluados")

        print(">>> Sintetizando conclusiones (heurística local simulada)...")
        synthesis = self._synthesize_with_thought(evaluations)
        print("   Síntesis completada")

        self.results = {
            "question": question,
            "thinking": thinking_result,
            "num_search_results": len(search_results),
            "claims": claims,
            "evaluations": evaluations,
            "synthesis": synthesis,
            "total_thinking_steps": thinking_result["step_count"],
            "simulated_steps": ["claim_extraction", "evidence_evaluation", "synthesis"],
            "nota": ("claims/evaluations/synthesis son heurísticas locales SIMULADAS. "
                     "Para extracción real con LLM, usar ResearchOrchestrator de "
                     "deep_research_system."),
        }

        print("\n=== INVESTIGACIÓN COMPLETADA ===")
        print(f"Pasos de pensamiento ejecutados: {thinking_result['step_count']}")
        print(f"Confianza del pensamiento: {thinking_result['confidence']:.2f}")

        return self.results

    def _extract_claims_with_thought(self, search_results: List[Dict]) -> List[Dict]:
        """Extrae claims de los snippets reales (heurística local, SIMULADA)."""
        claims = []
        for i, result in enumerate(search_results[:3]):
            snippet = (result.get("snippet") or "").strip()
            claims.append({
                "claim": snippet[:200] if snippet else f"Contenido de {result.get('title', 'fuente desconocida')}",
                "confidence": round(0.5 + i * 0.1, 2),
                "source_quality": round(0.6 + i * 0.1, 2),
                "verificable": True,
                "simulado": True,
            })
        return claims

    def _evaluate_evidence_with_thought(self, claims: List[Dict]) -> List[Dict]:
        """Evalúa evidencia con heurística local (SIMULADA, veredicto por umbral)."""
        evaluations = []
        for claim in claims:
            evaluations.append({
                "claim": claim["claim"],
                "verdict": "supported" if claim["confidence"] > 0.7 else "not_addressed",
                "credibility": round(claim["source_quality"] * 0.9, 2),
                "strength": round(claim["confidence"] * 0.8, 2),
                "reasoning": f"Heurística local sobre: {claim['claim'][:50]}",
                "simulado": True,
            })
        return evaluations

    def _synthesize_with_thought(self, evaluations: List[Dict]) -> Dict:
        """Síntesis final con heurística local (SIMULADA)."""
        supported = sum(1 for e in evaluations if e["verdict"] == "supported")
        contradicted = sum(1 for e in evaluations if e["verdict"] == "contradicted")

        return {
            "conclusiones": [
                {
                    "enunciado": f"Heurística local: {supported} claims supported, {contradicted} contradicted",
                    "confianza": round((supported / max(len(evaluations), 1)) * 0.8, 2),
                    "basada_en": [f"claim_{i}" for i in range(len(evaluations))],
                }
            ],
            "gaps": [f"{len(evaluations) - supported - contradicted} claims sin evaluar"],
            "recomendaciones": [
                "Continuar investigación con fuentes primarias",
                "Verificar claims con documentación original",
            ],
            "simulado": True,
        }


# Demo / Usage
def main():
    print("=" * 70)
    print("CAPA DE PENSAMIENTO PARA SISTEMAS LLM")
    print("==========================================")
    print()
    print("Objetivo: Implementar 'pensamiento' que las LLMs no tienen naturalmente")
    print("           y evitar el 'prueba y error' repetitivo.")
    print()
    print("Características:")
    print("  • Razonamiento estructurado en 7 pasos deliberados")
    print("  • Validación en cada etapa antes de avanzar")
    print("  • Evita decisiones precipitadas")
    print("  • Confianza explícita en cada paso")
    print("  • Patrón anti-repitencia con reinicio automático")
    print()
    print("Arquitectura:")
    print("  StepThinkingEngine (thinking_engine.py, común)")
    print("  └── DeepResearchThinkingLayer (7 pasos de investigación)")
    print("       → Análisis, Plan, Estrategia, Búsqueda, Claims, Evidencia, Síntesis")
    print()
    print("=" * 70)

    # Demo offline: sin proveedor real, _llm_generate usa MockLLM
    # (determinista, sin red, declarado como simulado).
    # Para un modelo real: DeepResearchThinkingLayer(llm_provider=OpenRouterLLM())
    thinking_layer = DeepResearchThinkingLayer(llm_provider=None, name="deep_research")

    result = thinking_layer.think(
        "¿Cuál es el estado actual de la fusión nuclear y sus perspectivas a 2030?"
    )

    print("\n" + "=" * 70)
    print("RESULTADO DEL PENSAMIENTO ESTRUCTURADO")
    print("=" * 70)
    print(result["thought"])
    print(f"\nConfianza: {result['confidence']:.2f}")
    print(f"Válido: {result['valid']}")
    print(f"Pasos ejecutados: {result['step_count']}")
    print("=" * 70)


if __name__ == "__main__":
    main()
