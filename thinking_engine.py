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

Extensión ToT (Tree of Thoughts): añade ramificación, evaluación de estado y
búsqueda (BFS/DFS) manteniendo compatibilidad total con la interfaz lineal.
"""

import hashlib
import re
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

# Nombres públicos del módulo
__all__ = ["StepThinkingEngine", "ThinkingNode", "ToTEngine", "SearchStrategy"]


@dataclass
class ThinkingNode:
    """
    Nodo en el árbol de pensamientos (ToT).
    
    Cada nodo representa un estado de razonamiento parcial con:
    - El contenido del pensamiento
    - Su puntuación de calidad (0-1)
    - Referencias a padre e hijos para navegación
    - Metadatos del paso (nombre, profundidad, etc.)
    """
    content: str
    step_name: str
    score: float = 0.0
    parent: Optional["ThinkingNode"] = None
    children: List["ThinkingNode"] = field(default_factory=list)
    depth: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_child(self, child: "ThinkingNode") -> "ThinkingNode":
        child.parent = self
        child.depth = self.depth + 1
        self.children.append(child)
        return child
    
    def path_to_root(self) -> List["ThinkingNode"]:
        """Retorna la cadena de nodos desde la raíz hasta este nodo."""
        path = []
        node = self
        while node:
            path.append(node)
            node = node.parent
        return list(reversed(path))
    
    def is_leaf(self) -> bool:
        return len(self.children) == 0
    
    def best_child(self) -> Optional["ThinkingNode"]:
        if not self.children:
            return None
        return max(self.children, key=lambda c: c.score)


class SearchStrategy:
    """Estrategias de búsqueda para ToT."""
    BFS = "bfs"
    DFS = "dfs"
    BEAM = "beam"  # Beam search: mantiene top-k por nivel


class StepThinkingEngine(ABC):
    """Ciclo de pensamiento por pasos con validación antes de avanzar."""

    def __init__(self, llm_provider=None, name: str = "thinking_engine",
                 max_steps: int = 7, congelar_fases: bool = False):
        self.llm = llm_provider
        self.name = name
        self.step_count = 0
        self.max_steps = max_steps
        # Phase-chain freeze (piloto, opt-in): cada fase ejecutada se registra
        # como congelada con su hash y las fases posteriores la reciben como
        # INMUTABLE en el prompt. Solo afecta al ciclo lineal `think()` (en ToT
        # las ramas son exploratorias por diseño y el modo lo declara en el
        # resultado).
        self.congelar_fases = congelar_fases

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

    # --- Ciclo común (lineal, compatible hacia atrás) ----------------------
    def think(self, prompt: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Ejecuta el ciclo completo de pensamiento estructurado (lineal)."""
        self.step_count = 0
        return self._run_cycle(prompt, context or {})

    def _run_cycle(self, prompt: str, context: Dict[str, Any]) -> Dict[str, Any]:
        outputs: Dict[str, Any] = {"prompt": prompt, "context": context}

        steps: List[Tuple[str, str]] = []
        invalid_steps: List[str] = []
        fases: List[Dict[str, str]] = []

        # `max_steps` acota de verdad el ciclo: un motor configurado con 3
        # pasos no ejecuta los 7 (antes el atributo era decorativo).
        for name, builder in self._step_builders()[:self.max_steps]:
            prompt_base = builder(outputs)
            if self.congelar_fases and fases:
                prompt_base += self._bloque_fases_congeladas(fases)
            content = self._llm_generate(prompt_base)
            steps.append((name, content))
            outputs[name] = content
            if self.congelar_fases:
                fases.append({"nombre": name,
                              "hash": self._hash_fase(name, content),
                              "contenido": content})
            if not self.validate_step(content):
                # Validación antes de avanzar: no seguir construyendo sobre
                # un paso defectuoso (P1.11/P1.19: fallar y reportar).
                invalid_steps.append(name)
                break

        self.step_count = len(steps)
        resultado = {
            "thought": self._render_thought(steps),
            "decision": self._extract_decision(steps),
            "confidence": self._compute_confidence(steps),
            "valid": not invalid_steps,
            "invalid_steps": invalid_steps,
            "steps": steps,
            "step_count": len(steps),
            "error": (f"Paso inválido: {invalid_steps[0]}" if invalid_steps else None),
        }
        if self.congelar_fases:
            resultado["fases_congeladas"] = fases
            resultado["inmutabilidad_verificada"] = self.verificar_congelacion(
                steps, fases)
        return resultado

    def _llm_generate(self, prompt: str, **kwargs) -> str:
        """Genera con el proveedor inyectado; sin proveedor usa MockLLM.

        MockLLM es offline, determinista y se declara como simulado: nunca se
        hacen llamadas de red ocultas.
        """
        if self.llm is None:
            from llm_providers import MockLLM
            self.llm = MockLLM()
        return self.llm.generate(prompt, **kwargs)

    # --- Phase-chain freeze (piloto) ----------------------------------------
    @staticmethod
    def _hash_fase(nombre: str, contenido: str) -> str:
        """Hash corto y estable de una fase congelada (nombre + contenido)."""
        return hashlib.sha256(
            f"{nombre}\x00{contenido}".encode("utf-8")).hexdigest()[:16]

    @classmethod
    def verificar_congelacion(cls, steps: List[Tuple[str, str]],
                              fases: List[Dict[str, str]]) -> bool:
        """True si los pasos devueltos coinciden byte a byte con las fases congeladas.

        El consumidor puede mutar la lista `steps` después del ciclo: esta
        comprobación detecta esa mutación (inmutabilidad verificable, no solo
        declarada).
        """
        if len(steps) != len(fases):
            return False
        return all(
            nombre == fase["nombre"]
            and cls._hash_fase(nombre, contenido) == fase["hash"]
            for (nombre, contenido), fase in zip(steps, fases))

    def _bloque_fases_congeladas(self, fases: List[Dict[str, str]]) -> str:
        """Bloque de prompt que declara las fases previas como INMUTABLES."""
        lineas = [
            "",
            "[FASES CONGELADAS — INMUTABLES]",
            "Cada fase congelada es inmodificable. Si una evidencia posterior "
            "la contradice, declara la contradicción en la fase actual; NO "
            "reescribas, resumas ni contradigas su contenido.",
        ]
        for fase in fases:
            lineas.append(
                f"- {fase['nombre']} (hash {fase['hash']}): "
                f"{fase['contenido'][:300]}")
        return "\n".join(lineas)

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


# --- Tree of Thoughts Engine -----------------------------------------------

class ToTEngine(StepThinkingEngine):
    """
    Motor de pensamiento con Tree of Thoughts (ToT).
    
    Extiende StepThinkingEngine añadiendo:
    - Ramificación: genera múltiples candidatos por paso
    - Evaluación de estado: puntúa cada pensamiento (0-1)
    - Búsqueda: BFS/DFS/Beam search con poda configurable
    - Backtracking automático cuando una rama falla
    
    Mantiene compatibilidad total: si se llama a `think()`, ejecuta el ciclo
    lineal original. El modo ToT se activa con `think_tot()`.
    """
    
    def __init__(
        self,
        llm_provider=None,
        name: str = "tot_engine",
        max_steps: int = 7,
        branch_factor: int = 3,
        beam_width: int = 3,
        search_strategy: str = SearchStrategy.BEAM,
        min_score_threshold: float = 0.3,
        max_depth: Optional[int] = None,
        voto_top_k: int = 1,
        congelar_fases: bool = False,
    ):
        super().__init__(llm_provider, name, max_steps,
                         congelar_fases=congelar_fases)
        self.branch_factor = branch_factor
        self.beam_width = beam_width
        self.search_strategy = search_strategy
        self.min_score_threshold = min_score_threshold
        self.max_depth = max_depth or max_steps
        # Self-Consistency (arXiv:2203.11171) opt-in: 1 = mejor hoja por score.
        self.voto_top_k = voto_top_k
        self._root: Optional[ThinkingNode] = None
        self._all_nodes: List[ThinkingNode] = []
    
    def think_tot(
        self,
        prompt: str,
        context: Dict[str, Any] = None,
        return_tree: bool = False,
    ) -> Dict[str, Any]:
        """
        Ejecuta pensamiento con Tree of Thoughts.
        
        Args:
            prompt: Pregunta/problema inicial
            context: Contexto adicional
            return_tree: Si True, incluye el árbol completo en el resultado
            
        Returns:
            Dict con las mismas claves que `think()` más:
            - tree: ThinkingNode raíz (si return_tree=True)
            - best_path: Lista de (step_name, content) del mejor camino
            - explored_nodes: Total de nodos explorados
            - pruned_nodes: Nodos podados por score bajo
        """
        self._root = None
        self._all_nodes = []

        # Phase-chain freeze NO aplica a ToT: las ramas son exploratorias por
        # diseño. Se declara (nunca en silencio): el congelado vale para el
        # ciclo lineal `think()`.
        if self.congelar_fases:
            print("[ToTEngine] congelar_fases no aplica a ToT (ramas "
                  "exploratorias): el congelado vale para el ciclo lineal "
                  "think()", file=sys.stderr)

        # Inicializar raíz
        self._root = ThinkingNode(
            content=prompt,
            step_name="root",
            score=1.0,
            depth=0,
            metadata={"is_root": True, "prompt": prompt, "context": context or {}}
        )
        self._all_nodes.append(self._root)
        
        # Ejecutar búsqueda según estrategia
        if self.search_strategy == SearchStrategy.BFS:
            best_leaf = self._bfs_search(prompt, context or {})
        elif self.search_strategy == SearchStrategy.DFS:
            best_leaf = self._dfs_search(prompt, context or {})
        else:  # BEAM
            best_leaf = self._beam_search(prompt, context or {})

        # Self-Consistency (arXiv:2203.11171) opt-in: entre las k mejores hojas
        # gana el camino más repetido (consenso); empate -> mayor score. Con
        # `voto_top_k=1` no cambia nada (comportamiento original).
        hojas = sorted((n for n in self._all_nodes if n.is_leaf()),
                       key=lambda n: n.score, reverse=True)[:max(1, self.voto_top_k)]
        consenso = 1.0
        if len(hojas) > 1:
            from collections import Counter

            def firma(nodo):
                return "|".join(n.content for n in nodo.path_to_root())

            conteo = Counter(firma(h) for h in hojas)
            firma_ganadora, votos = conteo.most_common(1)[0]
            consenso = round(votos / len(hojas), 3)
            best_leaf = next(h for h in hojas if firma(h) == firma_ganadora)
        
        # Extraer mejor camino
        best_path = [(n.step_name, n.content) for n in best_leaf.path_to_root()[1:]]  # skip root
        
        # Calcular métricas
        pruned = sum(1 for n in self._all_nodes if n.score < self.min_score_threshold and n != self._root)
        
        # Sin camino no hay pensamiento válido: si todas las ramas se podan, la
        # búsqueda devuelve la raíz (score 1.0 por construcción) y `valid` no
        # puede ser True sin un solo paso ejecutado (P1.19: no simular éxito).
        hay_camino = bool(best_path)
        valid = hay_camino and best_leaf.score >= self.min_score_threshold
        if valid:
            error = None
        elif not hay_camino:
            error = "Ninguna rama superó el umbral de score: sin camino válido"
        else:
            error = f"Score bajo: {best_leaf.score:.2f}"
        
        result = {
            "thought": self._render_thought(best_path),
            "decision": self._extract_decision(best_path),
            "confidence": self._compute_confidence(best_path),
            "valid": valid,
            "invalid_steps": [] if valid else [best_leaf.step_name],
            "steps": best_path,
            "step_count": len(best_path),
            "error": error,
            "best_path": best_path,
            "explored_nodes": len(self._all_nodes),
            "pruned_nodes": pruned,
            "best_score": best_leaf.score,
            "consenso": consenso,
            "hojas_votadas": len(hojas),
            "congelacion_fases": ("no aplica a ToT (ramas exploratorias)"
                                  if self.congelar_fases else "inactiva"),
        }
        
        if return_tree:
            result["tree"] = self._root
        
        return result
    
    def _generate_branches(
        self,
        node: ThinkingNode,
        step_name: str,
        builder: Callable[[Dict[str, Any]], str],
        context: Dict[str, Any],
    ) -> List[ThinkingNode]:
        """Genera múltiples ramas (candidatos) para un paso dado."""
        # Construir outputs previos desde el camino a la raíz. `prompt` y
        # `context` viven SOLO en la raíz (los hijos guardan variant/builder);
        # leerlos del nodo actual los perdía a partir del paso 2.
        root = node.path_to_root()[0]
        outputs = {"prompt": root.metadata.get("prompt", ""),
                   "context": root.metadata.get("context", {})}
        for n in node.path_to_root()[1:]:  # skip root
            outputs[n.step_name] = n.content
        
        # Generar branch_factor candidatos
        branches = []
        for i in range(self.branch_factor):
            # Variar ligeramente el prompt para diversidad
            varied_prompt = builder(outputs)
            if i > 0:
                varied_prompt += f"\n\n[Variante {i+1}/{self.branch_factor}: ofrece una perspectiva distinta o enfoque alternativo]"
            
            content = self._llm_generate(varied_prompt)
            score = self._evaluate_state(content, step_name, outputs)
            
            child = ThinkingNode(
                content=content,
                step_name=step_name,
                score=score,
                parent=node,
                depth=node.depth + 1,
                metadata={"variant": i + 1, "builder_output": varied_prompt[:200]}
            )
            node.add_child(child)
            self._all_nodes.append(child)
            branches.append(child)
        
        return branches
    
    def _evaluate_state(self, content: str, step_name: str, outputs: Dict[str, Any]) -> float:
        """
        Evalúa la calidad de un estado de pensamiento (0-1).
        
        Modo híbrido:
        - Si hay llm_provider: usa LLM-as-judge con prompt estructurado
        - Fallback: heurística simple (keywords/longitud/coherencia)
        
        El LLM-as-judge evalúa: relevancia, profundidad, coherencia, razonamiento.
        """
        if not self.validate_step(content):
            return 0.0
        
        # LLM-as-judge si hay proveedor; si falla, se REPORTA la causa por
        # stderr y se degrada a la heurística local (nunca en silencio,
        # P1.19/P1.26).
        if self.llm is not None:
            try:
                return self._evaluate_state_llm(content, step_name, outputs)
            except Exception as exc:  # noqa: BLE001 - se reporta y se degrada
                print(f"[ToTEngine] LLM-as-judge falló "
                      f"({type(exc).__name__}: {exc}); se usa la heurística local",
                      file=sys.stderr)
        
        # Fallback heurístico (código original)
        return self._evaluate_state_heuristic(content, step_name, outputs)
    
    def _evaluate_state_heuristic(self, content: str, step_name: str, outputs: Dict[str, Any]) -> float:
        """Heurística original: keywords, longitud, coherencia."""
        score = 0.5  # base por pasar validación
        
        # Longitud (normalizada, óptima ~200-500 chars)
        length_score = min(len(content) / 500, 1.0) * 0.2
        score += length_score
        
        # Marcadores de razonamiento
        reasoning_markers = [
            "porque", "por tanto", "sin embargo", "además", "por lo tanto",
            "en consecuencia", "dado que", "puesto que", "así que",
            "because", "therefore", "however", "moreover", "thus",
            "given that", "since", "so"
        ]
        marker_count = sum(1 for m in reasoning_markers if m in content.lower())
        score += min(marker_count * 0.05, 0.15)
        
        # Coherencia con pasos previos (keywords compartidos)
        if outputs:
            prev_text = " ".join(str(v) for v in outputs.values() if isinstance(v, str))
            if prev_text:
                prev_words = set(w.lower() for w in prev_text.split() if len(w) > 4)
                curr_words = set(w.lower() for w in content.split() if len(w) > 4)
                overlap = len(prev_words & curr_words) / max(len(prev_words), 1)
                score += min(overlap * 0.2, 0.15)
        
        return min(round(score, 2), 1.0)
    
    def _evaluate_state_llm(self, content: str, step_name: str, outputs: Dict[str, Any]) -> float:
        """
        LLM-as-judge para evaluar calidad de pensamiento.
        
        Prompt estructurado pide puntuación 0-10 en 4 dimensiones:
        - Relevancia: ¿responde al paso actual?
        - Profundidad: ¿va más allá de lo superficial?
        - Coherencia: ¿conecta con pasos previos?
        - Razonamiento: ¿muestra cadena lógica (no solo assertions)?
        """
        # Construir contexto previo
        prev_steps = ""
        for n in outputs:
            if isinstance(outputs[n], str) and n not in ("prompt", "context"):
                prev_steps += f"\n--- {n} ---\n{outputs[n][:300]}"
        
        prompt = f"""Eres un evaluador experto de calidad de razonamiento. Evalúa el siguiente pensamiento en una tarea de investigación.

PASO ACTUAL: {step_name}
PENSAMIENTO A EVALUAR:
{content[:1500]}

CONTEXTO PREVIO (pasos ya ejecutados):
{prev_steps if prev_steps else "(ninguno - primer paso)"}

INSTRUCCIONES:
Puntúa cada dimensión de 0 a 10 (enteros). Sé estricto pero justo.

DIMENSIONES:
1. RELEVANCIA: ¿El pensamiento aborda directamente lo que se pide en este paso?
2. PROFUNDIDAD: ¿Va más allá de definiciones superficiales? ¿Aporta análisis, matices, conexiones?
3. COHERENCIA: ¿Conecta lógicamente con los pasos previos? ¿No contradice ni repite?
4. RAZONAMIENTO: ¿Muestra cadena lógica (porque/por tanto/sin embargo) o solo assertions?

FORMATO DE RESPUESTA (JSON exacto):
{{
  "relevance": <0-10>,
  "depth": <0-10>,
  "coherence": <0-10>,
  "reasoning": <0-10>,
  "brief_justification": "una frase explicando la puntuación global"
}}

Responde SOLO con el JSON."""
        
        response = self._llm_generate(prompt)
        # Parsear JSON de la respuesta
        import json
        import re
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            eval_data = json.loads(json_match.group())
            # Promedio ponderado: reasoning pesa más
            weights = {"relevance": 0.25, "depth": 0.25, "coherence": 0.2, "reasoning": 0.3}
            weighted = sum(eval_data.get(k, 0) * w for k, w in weights.items())
            return round(min(max(weighted / 10.0, 0.0), 1.0), 2)

        # Sin JSON utilizable se eleva el error: `_evaluate_state` lo reporta
        # por stderr y degrada a la heurística en un único punto (P1.26).
        raise ValueError(f"Respuesta del juez sin JSON: {response[:120]!r}")
    
    def _bfs_search(self, prompt: str, context: Dict[str, Any]) -> ThinkingNode:
        """Búsqueda en anchura (BFS) - explora nivel por nivel."""
        from collections import deque
        
        queue = deque([self._root])
        
        for step_name, builder in self._step_builders():
            level_size = len(queue)
            if level_size == 0:
                break
            
            next_level = []
            for _ in range(level_size):
                node = queue.popleft()
                if node.depth >= self.max_depth:
                    next_level.append(node)
                    continue
                
                branches = self._generate_branches(node, step_name, builder, context)
                # Filtrar por threshold
                valid_branches = [b for b in branches if b.score >= self.min_score_threshold]
                next_level.extend(valid_branches)
            
            queue.extend(next_level)
        
        # Retornar la mejor hoja. La raíz siempre está en `_all_nodes`, así que
        # el conjunto de hojas nunca es vacío (todo árbol finito tiene hojas).
        leaves = [n for n in self._all_nodes if n.is_leaf()]
        return max(leaves, key=lambda n: n.score)
    
    def _dfs_search(self, prompt: str, context: Dict[str, Any]) -> ThinkingNode:
        """Búsqueda en profundidad (DFS) - explora una rama hasta el final."""
        def dfs(node: ThinkingNode, step_idx: int) -> ThinkingNode:
            if step_idx >= len(self._step_builders()) or node.depth >= self.max_depth:
                return node
            
            step_name, builder = self._step_builders()[step_idx]
            branches = self._generate_branches(node, step_name, builder, context)
            valid_branches = [b for b in branches if b.score >= self.min_score_threshold]
            
            if not valid_branches:
                return node
            
            # Ordenar por score descendente y explorar la mejor primero
            valid_branches.sort(key=lambda b: b.score, reverse=True)
            return dfs(valid_branches[0], step_idx + 1)
        
        return dfs(self._root, 0)
    
    def _beam_search(self, prompt: str, context: Dict[str, Any]) -> ThinkingNode:
        """Beam search - mantiene top-k candidatos por nivel."""
        current_beam = [self._root]
        previous_beam = [self._root]
        
        for step_name, builder in self._step_builders():
            all_candidates = []
            
            for node in current_beam:
                if node.depth >= self.max_depth:
                    all_candidates.append(node)
                    continue
                
                branches = self._generate_branches(node, step_name, builder, context)
                all_candidates.extend(branches)
            
            # Filtrar y ordenar por score
            valid_candidates = [c for c in all_candidates if c.score >= self.min_score_threshold]
            valid_candidates.sort(key=lambda n: n.score, reverse=True)
            
            # Mantener solo top-k (beam_width)
            previous_beam = current_beam
            current_beam = valid_candidates[:self.beam_width]
            
            if not current_beam:
                break
        
        # Retornar el mejor de los finalistas
        # Si current_beam vacío, usar previous_beam (último nivel con candidatos válidos)
        final_beam = current_beam if current_beam else previous_beam
        if not final_beam or final_beam == [self._root]:
            return self._root
        return max(final_beam, key=lambda n: n.score)
    
    def _render_tot_tree(self, node: Optional[ThinkingNode] = None, indent: int = 0) -> str:
        """Renderiza el árbol completo para debugging."""
        if node is None:
            node = self._root
        if node is None:
            return "(árbol vacío)"
        
        lines = []
        prefix = "  " * indent
        marker = "●" if node == self._root else ("└─" if indent > 0 else "●")
        score_str = f" [{node.score:.2f}]" if node.step_name != "root" else ""
        lines.append(f"{prefix}{marker} {node.step_name}{score_str}: {node.content[:80]}...")
        
        for child in node.children:
            lines.append(self._render_tot_tree(child, indent + 1))
        
        return "\n".join(lines)
    
    def get_tree_visualization(self) -> str:
        """Retorna visualización ASCII del árbol explorado."""
        return self._render_tot_tree(self._root)