#!/usr/bin/env python3
"""
Motor común de ciclos de pensamiento por pasos.

Elimina la duplicación entre `pensamiento_layer` (investigación) y
`code_design_improvement_tools` (diseño de código): ambos ejecutaban el mismo
ciclo de 7 pasos con validadores, cálculo de confianza y extracción de decisión
replicados.

Principios:
1. Pensamiento externado: cada paso se ejecuta y se registra explícitamente.
2. Validación antes de avanzar: si un paso no supera la validación, el ciclo
   se detiene y lo reporta (`invalid_steps`), en vez de continuar a ciegas.
3. Forma de resultado estable: éxito y error devuelven las MISMAS claves
   (evita `KeyError` en el consumidor).
"""

import re
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Tuple

# Nombres públicos del módulo
__all__ = ["StepThinkingEngine"]


class StepThinkingEngine(ABC):
    """Ciclo de pensamiento por pasos con validación antes de avanzar."""

    def __init__(self, llm_provider=None, name: str = "thinking_engine",
                 max_steps: int = 7):
        self.llm = llm_provider
        self.name = name
        self.step_count = 0
        self.max_steps = max_steps

    # --- A implementar por cada motor concreto -----------------------------
    @abstractmethod
    def _step_builders(self) -> List[Tuple[str, Callable[[Dict[str, Any]], str]]]:
        """Lista de (nombre, constructor del prompt) para cada paso.

        El constructor recibe un diccionario con las salidas previas indexadas
        por nombre de paso, más `prompt` (la entrada) y `context` (el dict de
        contexto pasado a `think`).
        """

    @abstractmethod
    def _render_thought(self, steps: List[Tuple[str, str]]) -> str:
        """Representación legible del ciclo completo."""

    # --- Ciclo común -------------------------------------------------------
    def think(self, prompt: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Ejecuta el ciclo completo de pensamiento estructurado."""
        self.step_count = 0
        return self._run_cycle(prompt, context or {})

    def _run_cycle(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        outputs: Dict[str, Any] = {"prompt": prompt, "context": context}

        steps: List[Tuple[str, str]] = []
        invalid_steps: List[str] = []

        for name, builder in self._step_builders():
            content = self._llm_generate(builder(outputs))
            steps.append((name, content))
            outputs[name] = content
            if not self.validate_step(content):
                # Validación antes de avanzar: no seguir construyendo sobre
                # un paso defectuoso (P1.11/P1.19: fallar y reportar).
                invalid_steps.append(name)
                break

        self.step_count = len(steps)
        return {
            "thought": self._render_thought(steps),
            "decision": self._extract_decision(steps),
            "confidence": self._compute_confidence(steps),
            "valid": not invalid_steps,
            "invalid_steps": invalid_steps,
            "steps": steps,
            "step_count": len(steps),
            "error": (f"Paso inválido: {invalid_steps[0]}" if invalid_steps else None),
        }

    def _llm_generate(self, prompt: str, **kwargs) -> str:
        """Genera con el proveedor inyectado; sin proveedor usa MockLLM.

        MockLLM es offline, determinista y se declara como simulado: nunca se
        hacen llamadas de red ocultas.
        """
        if self.llm is None:
            from deep_research_system import MockLLM
            self.llm = MockLLM()
        return self.llm.generate(prompt, **kwargs)

    # --- Utilidades comunes ------------------------------------------------
    @staticmethod
    def validate_step(content: str) -> bool:
        """Valida que un paso tenga contenido sustancial.

        Rechaza respuestas vacías o plantillas (solo llaves/puntuación/puntos
        suspensivos). NO veta "etc." ni "..." dentro de una respuesta con
        contenido: los modelos reales las usan con normalidad.
        """
        if not content or not content.strip():
            return False
        stripped = content.strip()
        if len(stripped) < 5:
            return False
        meaningful = re.sub(r'[\s\.·…"\'`{}\[\]:,;0-9\-_()|=]', "", stripped)
        return len(meaningful) >= 10

    @staticmethod
    def _compute_confidence(steps: List[Tuple[str, str]]) -> float:
        """Confianza = proporción de pasos con contenido no vacío."""
        if not steps:
            return 0.0
        filled = sum(1 for _, content in steps if content and content.strip())
        return round(filled / len(steps), 2)

    @staticmethod
    def _extract_decision(steps: List[Tuple[str, str]]) -> Any:
        """Decisión = último paso con contenido (marca de la fase alcanzada)."""
        if len(steps) >= 5:
            last = next((name for name, content in reversed(steps)
                         if content and content.strip()), None)
            return f"decision_from_{last}" if last else None
        return None
