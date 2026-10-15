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

from deep_research_system import ResearchOrchestrator
from thinking_engine import StepThinkingEngine, ToTEngine, SearchStrategy

# Nombre histórico mantenido por compatibilidad.
ThinkingLayer = StepThinkingEngine


class DeepResearchThinkingLayer(ToTEngine):
    """
    Capa de pensamiento profunda específicamente para sistemas de investigación.
    Implementa 7 pasos deliberados para evitar decisiones precipitadas.
    
    Hereda de ToTEngine que extiende StepThinkingEngine, añadiendo:
    - Modo ToT: ramificación, evaluación de estado, búsqueda (BFS/DFS/Beam)
    - Modo lineal: API original `think()` intacta para compatibilidad total
    """

    def __init__(self, llm_provider, name: str = "deep_research_thinking",
                 use_tot: bool = False, **tot_kwargs):
        super().__init__(llm_provider, name, max_steps=7, **tot_kwargs)
        self._use_tot = use_tot

    def _validate_step(self, thought: str, decision: Any = None) -> bool:
        """Compatibilidad: delega en el validador común."""
        return self.validate_step(thought)

    def think_tot(self, prompt: str, context: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        """
        Ejecuta pensamiento con Tree of Thoughts (ToT).
        
        Args:
            prompt: Pregunta de investigación
            context: Contexto adicional
            **kwargs: Parámetros ToT (branch_factor, beam_width, search_strategy, etc.)
            
        Returns:
            Dict con claves del modo lineal + best_path, explored_nodes, pruned_nodes, best_score
        """
        # Guardar parámetros originales
        orig_branch = self.branch_factor
        orig_beam = self.beam_width
        orig_strategy = self.search_strategy
        orig_threshold = self.min_score_threshold
        orig_depth = self.max_depth
        
        # Aplicar overrides temporales
        if "branch_factor" in kwargs:
            self.branch_factor = kwargs["branch_factor"]
        if "beam_width" in kwargs:
            self.beam_width = kwargs["beam_width"]
        if "search_strategy" in kwargs:
            self.search_strategy = kwargs["search_strategy"]
        if "min_score_threshold" in kwargs:
            self.min_score_threshold = kwargs["min_score_threshold"]
        if "max_depth" in kwargs:
            self.max_depth = kwargs["max_depth"]
        
        try:
            # Usar el método heredado de ToTEngine directamente
            return super().think_tot(prompt, context)
        finally:
            # Restaurar parámetros originales
            self.branch_factor = orig_branch
            self.beam_width = orig_beam
            self.search_strategy = orig_strategy
            self.min_score_threshold = orig_threshold
            self.max_depth = orig_depth

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
            f"        VALIDEZ: {'VALID' if steps and self.validate_step(steps[-1][1]) and all(self.validate_step(c) for _, c in steps) else 'REVISAR'}",
        ])
        return "\n".join(lines)


class ResearchOrchestratorWithThinking:
    """Investigación con capa de pensamiento + pipeline REAL de evidencias.

    El pensamiento estructura el razonamiento en 7 pasos (validados antes de
    avanzar); la recuperación de fuentes, la extracción de claims y su
    evaluación las realiza `ResearchOrchestrator` (`deep_research_system`) con
    el LLM y el buscador configurados. Sin heurísticas simuladas: lo que no se
    puede hacer, se reporta en vez de rellenarse.
    """

    def __init__(self, llm_provider, search_api, thinking_layer: DeepResearchThinkingLayer):
        self.llm = llm_provider
        self.search = search_api
        self.thinking = thinking_layer
        self.results = None

    def research_with_thinking(self, question: str) -> Dict[str, Any]:
        """Ejecuta el pensamiento estructurado y luego el pipeline real."""

        print("\n=== INICIANDO INVESTIGACIÓN CON CAPA DE PENSAMIENTO ===")
        print(f"Pregunta: {question}\n")

        print(">>> Ciclo de pensamiento estructurado (7 pasos)...")
        thinking_result = self.thinking.think(question)
        print(f"   Pasos: {thinking_result['step_count']}, "
              f"Confianza: {thinking_result['confidence']:.2f}, "
              f"Válido: {thinking_result['valid']}")

        if not thinking_result["valid"]:
            return {
                "error": "Ciclo de pensamiento no válido; replantear la pregunta (anti-repitencia)",
                "thinking": thinking_result,
            }

        print(">>> Ejecutando pipeline de evidencias (LLM + búsqueda)...")
        report, context = ResearchOrchestrator(self.llm, self.search).research(question)
        print(f"   {len(context.sources)} fuentes, {len(context.claims)} claims, "
              f"{len(context.evaluations)} evaluaciones")

        self.results = {
            "question": question,
            "thinking": thinking_result,
            "report": report,
            "context": context,
            "sources": context.sources,
            "claims": context.claims,
            "evaluations": context.evaluations,
            "total_thinking_steps": thinking_result["step_count"],
        }

        print("\n=== INVESTIGACIÓN COMPLETADA ===")
        print(f"Pasos de pensamiento ejecutados: {thinking_result['step_count']}")
        print(f"Informe generado: {len(report)} caracteres")

        return self.results


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
    print("  • NUEVO: Tree of Thoughts (ToT) con ramificación y búsqueda")
    print()
    print("Arquitectura:")
    print("  StepThinkingEngine (thinking_engine.py, común)")
    print("  └── ToTEngine (ramificación + búsqueda BFS/DFS/Beam)")
    print("       └── DeepResearchThinkingLayer (7 pasos de investigación)")
    print("            → Análisis, Plan, Estrategia, Búsqueda, Claims, Evidencia, Síntesis")
    print()
    print("=" * 70)

    # Demo offline: sin proveedor real, _llm_generate usa MockLLM
    # (determinista, sin red, declarado como simulado).
    # Para un modelo real: DeepResearchThinkingLayer(llm_provider=OpenRouterLLM())
    thinking_layer = DeepResearchThinkingLayer(llm_provider=None, name="deep_research")

    print("\n--- MODO LINEAL (API original) ---")
    result = thinking_layer.think(
        "¿Cuál es el estado actual de la fusión nuclear y sus perspectivas a 2030?"
    )

    print("\n" + "=" * 70)
    print("RESULTADO MODO LINEAL")
    print("=" * 70)
    print(result["thought"])
    print(f"\nConfianza: {result['confidence']:.2f}")
    print(f"Válido: {result['valid']}")
    print(f"Pasos ejecutados: {result['step_count']}")
    print("=" * 70)

    print("\n--- MODO ToT (Tree of Thoughts, Beam Search) ---")
    result_tot = thinking_layer.think_tot(
        "¿Cuál es el estado actual de la fusión nuclear y sus perspectivas a 2030?",
        branch_factor=3,
        beam_width=2,
    )

    print("\n" + "=" * 70)
    print("RESULTADO MODO ToT (Beam Search)")
    print("=" * 70)
    print(f"Válido: {result_tot['valid']}")
    print(f"Pasos: {result_tot['step_count']}")
    print(f"Confianza: {result_tot['confidence']:.2f}")
    print(f"Score mejor: {result_tot['best_score']:.2f}")
    print(f"Nodos explorados: {result_tot['explored_nodes']}")
    print(f"Nodos podados: {result_tot['pruned_nodes']}")
    print(f"Mejor camino:")
    for name, content in result_tot['best_path']:
        print(f"  [{name}] {content[:80]}...")
    print("\nÁrbol explorado:")
    print(thinking_layer.get_tree_visualization() if hasattr(thinking_layer, 'get_tree_visualization') else "N/A")
    print("=" * 70)


if __name__ == "__main__":
    main()
