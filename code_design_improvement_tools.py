#!/usr/bin/env python3
"""
Herramientas para Diseño y Mejora de Proyectos de Código
==========================================================

Aplicando los principios de eficiencia ("hacer las cosas de manera eficiente"),
la capa de pensamiento estructurado y el sistema de toma de decisiones autónomas
para el diseño, análisis y mejora de proyectos de software.

Principios clave:
1. Eficiencia - Minimizar redundancia, maximizar mantenibilidad
2. Pensamiento estructurado - Razonamiento en pasos válidos y verificables
3. Decisión autónoma - El sistema sugiere, el humano decide
4. Validación antes de actuar - No "prueba y error" repetitivo
"""

import ast
import re
import sys
import time
from abc import abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from thinking_engine import StepThinkingEngine

# Orden de severidad para priorizar issues (menor = más urgente)
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}

# Referencia única del "score de eficiencia": issues detectados / este valor,
# acotado a 1. Se usa en el contexto y en el analizador para no tener dos
# definiciones distintas del mismo concepto (antes: /50 y /30).
EFFICIENCY_REFERENCE_ISSUES = 30


class CodeAnalysisContext:
    """Contexto que mantiene el estado del análisis de código."""

    def __init__(self, project_path: str, max_issues: int = 20):
        self.project_path = project_path
        self.max_issues = max_issues
        self.issues: List[Dict[str, Any]] = []
        self.metrics: Dict[str, Any] = {}
        self.design_decisions: List[Dict[str, Any]] = []
        self.start_time = time.time()
        self.thinking_steps: List[Dict[str, Any]] = []

    def add_issue(self, category: str, severity: str, description: str,
                  line: Optional[int] = None, file: Optional[str] = None,
                  suggestion: Optional[str] = None, thinking_reasoning: str = ""):
        issue = {
            "category": category,
            "severity": severity,  # "critical", "high", "medium", "low"
            "description": description,
            "file": file or "unknown",
            "line": line,
            "suggestion": suggestion,
            "thinking_reasoning": thinking_reasoning,
            "detected_at": time.time()
        }
        self.issues.append(issue)
        # Mantener solo los max_issues más críticos
        self.issues.sort(key=lambda x: (SEVERITY_ORDER.get(x["severity"], 99), x["detected_at"]))
        if len(self.issues) > self.max_issues:
            self.issues = self.issues[:self.max_issues]

    def add_thinking_step(self, step: str, reasoning: str, result: Any):
        self.thinking_steps.append({
            "step": step,
            "reasoning": reasoning,
            "result": result,
            "timestamp": time.time()
        })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_path": self.project_path,
            "total_issues": len(self.issues),
            "issue_breakdown": {
                "critical": sum(1 for i in self.issues if i["severity"] == "critical"),
                "high": sum(1 for i in self.issues if i["severity"] == "high"),
                "medium": sum(1 for i in self.issues if i["severity"] == "medium"),
                "low": sum(1 for i in self.issues if i["severity"] == "low")
            },
            "issues": self.issues,
            "metrics": self.metrics,
            "thinking_steps": len(self.thinking_steps),
            "efficiency_score": self._compute_efficiency_score()
        }

    def _compute_efficiency_score(self) -> float:
        """Cobertura del análisis: issues detectados / referencia, acotado a 1.

        Es una medida heurística de cuánto se ha inspeccionado, no de calidad
        del código: más issues detectados suben el score.
        """
        if not self.project_path:
            return 0.0
        return min(round(len(self.issues) / EFFICIENCY_REFERENCE_ISSUES, 2), 1.0)


class ThinkingDecisionEngine(StepThinkingEngine):
    """Motor de decisiones con capa de pensamiento estructurado.

    Reutiliza el validador, el cálculo de confianza y la extracción de
    decisión comunes (`thinking_engine.StepThinkingEngine`); aquí sólo se
    añade la interfaz `decide(context, prompt)`.
    """

    def __init__(self, name: str = "thinking_decision_engine", llm_provider=None,
                 max_steps: int = 7):
        super().__init__(llm_provider, name, max_steps=max_steps)
        self.max_thinking_steps = max_steps

    def decide(self, context: CodeAnalysisContext, prompt: str,
               progress=None) -> Dict[str, Any]:
        """Ejecuta un ciclo de pensamiento para tomar una decisión de diseño."""
        self.step_count = 0
        return self._execute_thinking_cycle(context, prompt, progress)

    @abstractmethod
    def _execute_thinking_cycle(self, context: CodeAnalysisContext, prompt: str,
                                progress=None) -> Dict[str, Any]:
        pass  # pragma: no cover - cuerpo abstracto, nunca se ejecuta

    def _validate_thought(self, thought: str) -> bool:
        """Compatibilidad: delega en el validador común."""
        return self.validate_step(thought)

    # Este motor define su propio ciclo, así que no aporta constructores.
    def _step_builders(self):
        return []

    def _render_thought(self, steps):
        return ""


class CodeDesignThinker(ThinkingDecisionEngine):
    """
    Thinker para decisiones de diseño de código.
    Implementa 7 pasos estructurados para evitar decisiones precipitadas.

    Sin proveedor LLM usa MockLLM (offline, declarado como simulado).
    """

    # Orden canónico de los pasos del ciclo (índice → número de paso).
    _NOMBRES_PASOS = ("analysis", "objectives", "design_options", "evaluation",
                      "selection", "implementation_plan", "validation")

    _ETIQUETAS_PASOS = ("ANÁLISIS", "OBJETIVOS", "OPCIONES", "EVALUACIÓN",
                        "SELECCIÓN", "PLAN", "VALIDACIÓN")

    def _resultado_valido(self, steps: List[Tuple[str, str]]) -> Dict[str, Any]:
        self.step_count = len(steps)
        return {
            "thought": self._render_steps(steps),
            "decision": self._extract_decision(steps),
            "confidence": self._compute_confidence(steps),
            "valid": True,
            "invalid_steps": [],
            "steps": steps,
            "step_count": len(steps),
            "error": None,
        }

    def _resultado_invalido(self, steps: List[Tuple[str, str]],
                            nombre: str) -> Dict[str, Any]:
        numero = self._NOMBRES_PASOS.index(nombre) + 1
        self.step_count = len(steps)
        return {
            "thought": self._render_steps(steps),
            "decision": self._extract_decision(steps),
            "confidence": self._compute_confidence(steps),
            "valid": False,
            "invalid_steps": [nombre],
            "steps": steps,
            "step_count": len(steps),
            "error": f"Paso {numero} inválido: {nombre}",
        }

    def _render_steps(self, steps: List[Tuple[str, str]]) -> str:
        if not steps:
            return ""
        lines = [
            f"        CAPA DE PENSAMIENTO DISEÑO: {self.name}",
            "        ========================================",
            "",
        ]
        for i, (nombre, contenido) in enumerate(steps):
            etiqueta = self._ETIQUETAS_PASOS[self._NOMBRES_PASOS.index(nombre)]
            lines.append(f"        PASO {i + 1} - {etiqueta}: {contenido[:150]}")
        lines.extend([
            "",
            f"        PASOS COMPLETADOS: {len(steps)}/{self.max_thinking_steps}",
            f"        DECISIÓN FINAL: {self._extract_decision(steps)}",
            f"        CONFIANZA: {self._compute_confidence(steps)}",
        ])
        return "\n".join(lines)

    def _registrar(self, steps: List[Tuple[str, str]], nombre: str, contenido: str,
                   progress) -> Optional[Dict[str, Any]]:
        """Valida y registra un paso; devuelve el cierre si hay que parar.

        Validación antes de avanzar (regla 2 del proyecto): un paso inválido
        detiene el ciclo en el momento, no al final. `max_steps` acota de
        verdad el número de pasos ejecutados.
        """
        if not self.validate_step(contenido):
            return self._resultado_invalido(steps, nombre)
        steps.append((nombre, contenido))
        if progress:
            progress(f"paso {len(steps)}/{self.max_thinking_steps}: {nombre}")
        if len(steps) >= self.max_thinking_steps:
            return self._resultado_valido(steps)
        return None

    def _execute_thinking_cycle(self, context: CodeAnalysisContext, prompt: str,
                                progress=None) -> Dict[str, Any]:
        """Ciclo de 7 pasos de pensamiento para diseño de código."""

        steps = []

        # PASO 1: Análisis del código existente
        step1 = self._llm_generate(f"""
PASO 1 - ANÁLISIS DE CÓDIGO EXISTENTE:
Analiza el código proporcionado. Identifica:
- Estructura general del proyecto
- Patrones de diseño utilizados
- Acoplamiento y cohesión
- Technical debt evidente
- Oportunidades de mejora

Código: {prompt}

Respuesta en JSON:
{{
  "estructura": "descripción",
  "patrones": ["..."],
  "acoplamiento": "bajo/medio/alto",
  "cohesion": "alta/media/baja",
  "tech_debt": ["..."],
  "mejora_oportunidades": ["..."]
}}
""")

        fin = self._registrar(steps, "analysis", step1, progress)
        if fin is not None:
            return fin

        # PASO 2: Definición de objetivos de mejora
        step2 = self._llm_generate(f"""
PASO 2 - OBJETIVOS DE MEJORA:
Basado en el análisis, define objetivos específicos de mejora:
- Prioridades (seguridad, performance, maintainability, readability)
- Métricas objetivo
- Restricciones (tiempo, recursos, risk tolerance)

Análisis: {step1}

Objetivos en JSON:
{{
  "prioridades": ["..."],
  "metricas_objetivo": {{
    "maintainability_index": 0-100,
    "complexity_reduction": 0-100
  }},
  "restricciones": {{
    "max_refactor_time": "horas",
    "no_breaking_changes": true/false
  }}
}}
""")

        fin = self._registrar(steps, "objectives", step2, progress)
        if fin is not None:
            return fin

        # PASO 3: Generación de opciones de diseño
        step3 = self._llm_generate(f"""
PASO 3 - OPCIONES DE DISEÑO:
Genera opciones de diseño para lograr los objetivos.

Objetivos: {step2}

Para cada opción, proporciona:
- nombre: identificador único
- beneficios: lista de beneficios esperados
- costos: estimación de esfuerzo (person-horas)
- riesgos: posibles riesgos de implementación

Formato JSON:
[
  {{
    "nombre": "...",
    "beneficios": ["..."],
    "costos": "X person-horas",
    "riesgos": ["..."]
  }}
]
""")

        fin = self._registrar(steps, "design_options", step3, progress)
        if fin is not None:
            return fin

        # PASO 4: Evaluación de opciones
        step4 = self._llm_generate(f"""
PASO 4 - EVALUACIÓN DE OPCIONES:
Evalúa cada opción contra los objetivos.

Opciones: {step3}

Para cada opción, determina:
- idoneidad: 0-1 (qué tan bien cumple los objetivos)
- complejidad: 0-1
- riesgo de regresión: 0-1
- relación beneficio/costo

JSON:
[
  {{
    "nombre": "...",
    "idoneidad": 0-1,
    "complejidad": 0-1,
    "riesgo_regresion": 0-1,
    "beneficio_costo_ratio": 0-1
  }}
]
""")

        fin = self._registrar(steps, "evaluation", step4, progress)
        if fin is not None:
            return fin

        # PASO 5: Selección de enfoque
        step5 = self._llm_generate(f"""
PASO 5 - SELECCIÓN DE ENFOQUE:
Selecciona la mejor opción o combina opciones.

Evaluaciones: {step4}

Decisión:
- enfoque_seleccionado: nombre de la opción elegida
- justificación: explicación breve
- siguiente_paso: qué hacer primero

JSON:
{{
  "enfoque_seleccionado": "...",
  "justificación": "...",
  "siguiente_paso": "..."
}}
""")

        fin = self._registrar(steps, "selection", step5, progress)
        if fin is not None:
            return fin

        # PASO 6: Plan de implementación
        step6 = self._llm_generate(f"""
PASO 6 - PLAN DE IMPLEMENTACIÓN:
Crea un plan detallado para implementar el enfoque seleccionado.

Enfoque: {step5}

Plan en JSON con:
- pasos: lista de acciones específicas
- responsables: quién ejecuta cada paso
- timeline: estimación de tiempo por paso
- checkpoints: puntos de validación/intermediarios

[
  {{
    "paso": "...",
    "responsable": "rol",
    "tiempo_estimado": "horas",
    "checkpoint": "entregable o validación"
  }}
]
""")

        fin = self._registrar(steps, "implementation_plan", step6, progress)
        if fin is not None:
            return fin

        # PASO 7: Verificación y validación
        step7 = self._llm_generate(f"""
PASO 7 - VERIFICACIÓN Y VALIDACIÓN:
Define cómo verificar que la mejora fue exitosa.

Plan: {step6}

Criterios de éxito en JSON:
{{
  "metricas_mejoradas": ["..."],
  "umbral_exito": 0-1,
  "pruebas_necesarias": ["..."],
  "rollback_plan": "descripción si falla"
}}
""")

        fin = self._registrar(steps, "validation", step7, progress)
        if fin is not None:
            return fin

        return self._resultado_valido(steps)


class CodeImprovementOrchestrator:
    """
    Orquestador que integra el pensamiento en la mejora de código.
    Ejecuta el ciclo completo de análisis → diseño → mejora → validación.
    """

    def __init__(self, thinking_engine: CodeDesignThinker, source_code: str = ""):
        self.thinking = thinking_engine
        self.source_code = source_code
        self.context = CodeAnalysisContext("project_analysis")
        self.results: Dict[str, Any] = {}

    def run_analysis(self, progress=None) -> Dict[str, Any]:
        """Núcleo del análisis: SIN impresión, sólo lógica y resultados.

        `progress` es un callback opcional (recibe el texto del paso) para que
        la presentación sea responsabilidad del llamador. Así el núcleo es
        comprobable de forma precisa (valores y efectos) sin capturar stdout.
        """
        decir = progress or (lambda _mensaje: None)

        # Análisis estático real del código fuente: alimenta el contexto
        if self.source_code:
            static = analyze_python_source(self.source_code)
            if "syntax_error" in static:
                # Sin sintaxis válida no hay análisis posible: se detiene y se
                # reporta (antes seguía 7 fases sobre código roto y decía "0
                # problemas"; error silencioso, P1.19/P1.26).
                decir(f">>> Fuente con error de sintaxis: {static['syntax_error']}")
                return {
                    "error": f"Fuente con error de sintaxis: {static['syntax_error']}",
                    "steps": [("fallido", static)],
                }
            for issue in static.get("metrics", {}).get("issues", []):
                self.context.add_issue(**issue)
            self.context.metrics = static.get("source_summary", {})
            decir(f">>> Análisis estático: "
                  f"{self.context.to_dict()['total_issues']} issues detectados")

        # UN ciclo de 7 pasos (antes se repetía el ciclo completo por fase:
        # 7 decisiones × 7 pasos = 49 llamadas con prompts de relleno, lo
        # contrario al principio rector de eficiencia).
        decir(">>> Ciclo de pensamiento de diseño...")
        ciclo = self.thinking.decide(self.context, self.source_code,
                                     progress=lambda mensaje: decir(f"   {mensaje}"))
        decir(f"   pasos={ciclo['step_count']} válido={ciclo['valid']}")

        if not ciclo["valid"]:
            return {
                "error": f"El ciclo de diseño falló (paso inválido: "
                         f"{ciclo['invalid_steps'][0]})",
                "steps": [("fallido", ciclo)],
            }

        # Mapear cada paso del ciclo único a su clave histórica de fase.
        claves = {
            "analysis": "analysis",
            "objectives": "objectives",
            "design_options": "design_options_considered",
            "evaluation": "evaluations",
            "selection": "selection",
            "implementation_plan": "implementation_plan",
            "validation": "validation_criteria",
        }
        resultados: Dict[str, Any] = {}
        for nombre, contenido in ciclo["steps"]:
            resultados[claves.get(nombre, nombre)] = {
                "thought": contenido,
                "decision": contenido,
                "confidence": self.thinking._compute_confidence([(nombre, contenido)]),
                "valid": True,
                "invalid_steps": [],
                "steps": [(nombre, contenido)],
                "step_count": 1,
                "error": None,
            }

        self.results = {
            **resultados,
            "total_thinking_steps": self.thinking.step_count,
            "efficiency_principle": "Hacer las cosas de manera eficiente",
            "project_metrics": self.context.to_dict(),
        }
        return self.results

    def analyze_and_improve(self) -> Dict[str, Any]:
        """Ejecuta el ciclo completo y muestra el progreso por consola."""

        print("=" * 70)
        print("ANÁLISIS Y MEJORA DE PROYECTO DE CÓDIGO")
        print("=" * 70)
        print("Aplicando capa de pensamiento estructurado (7 pasos)")
        print("Principio rector: 'Hacer las cosas de manera eficiente'\n")

        resultado = self.run_analysis(progress=lambda mensaje: print(f"   {mensaje}"))

        if "error" in resultado:
            # El fallo se reporta por stderr (no silencioso): `self.results`
            # queda vacío y generate_report lo avisa.
            print(f"ERROR: {resultado['error']}", file=sys.stderr)
            return resultado

        metricas = self.results["project_metrics"]
        print(f"\n{'=' * 70}")
        print("ANÁLISIS COMPLETADO")
        print("=" * 70)
        print(f"Pasos de pensamiento ejecutados: {self.results['total_thinking_steps']}")
        print(f"Problemas identificados: {metricas['total_issues']}")
        print(f"Score de eficiencia: {metricas['efficiency_score']:.2f}")
        print(f"Principio aplicado: {self.results['efficiency_principle']}")
        print("=" * 70)

        return self.results

    def report_lines(self) -> List[str]:
        """Líneas del reporte markdown (sin unir): núcleo comprobable."""
        r = self.results
        lines = [
            "# Análisis y Mejora de Proyecto de Código",
            "",
            "## Resumen Ejecutivo",
            f"- **Pasos de pensamiento**: {r['total_thinking_steps']}",
            f"- **Problemas identificados**: {r['project_metrics']['total_issues']}",
            f"- **Score de eficiencia**: {r['project_metrics']['efficiency_score']:.2f}",
            f"- **Principio rector**: {r['efficiency_principle']}",
            "",
            "## Problemas Detectados",
        ]

        for issue in r['project_metrics'].get('issues', []):
            if isinstance(issue, dict) and 'description' in issue:
                lines.append(f"- **[{issue['severity'].upper()}]** {issue['description']}")
                if issue.get('suggestion'):
                    lines.append(f"  - Sugerencia: {issue['suggestion']}")
                lines.append("")

        lines.extend([
            "## Decisiones de Diseño",
            f"- **Enfoque seleccionado**: {r.get('selection', {}).get('decision', 'N/A')}",
            f"- **Confianza**: {r.get('selection', {}).get('confidence', 'N/A')}",
            "",
            "## Plan de Implementación",
        ])

        steps = r.get('implementation_plan', {}).get('steps', [])
        if isinstance(steps, list):
            for i, step in enumerate(steps[:5], 1):  # Máx 5 pasos en reporte
                descripcion = step[1][:80] if isinstance(step, tuple) else str(step)[:80]
                lines.append(f"{i}. {descripcion}")
        else:
            lines.append("No steps detail available")

        lines.extend([
            "",
            "## Criterios de Validación",
            f"- **Decisión de validación**: {r.get('validation_criteria', {}).get('decision', 'N/A')}",
            f"- **Confianza**: {r.get('validation_criteria', {}).get('confidence', 'N/A')}",
            "",
            "---",
            "*Generado por sistema de diseño de código con capa de pensamiento estructurado*",
            f"*Pasos deliberados: {r['total_thinking_steps']}/7*"
        ])
        return lines

    def generate_report(self) -> str:
        """Reporte markdown completo (presentación sobre `report_lines`)."""
        if not self.results:
            return "No results to report."
        return "\n".join(self.report_lines())


def _max_nesting(tree: ast.AST) -> int:
    """Profundidad máxima de anidamiento de bloques de control (if/for/while/
    try/with, incluidos try/except* y match). 0 = código plano.

    `elif` no tiene nodo propio en el AST: se representa como un `If` dentro
    de `orelse` y comparte indentación con el `if`, así que no suma un nivel.
    Un `if` dentro de un `else` real sí está indentado y sí suma.
    """
    anidables = (ast.If, ast.While, ast.For, ast.AsyncFor, ast.Try,
                 ast.TryStar, ast.With, ast.AsyncWith, ast.Match)

    def profundidad(nodo: ast.AST, nivel: int,
                    padre: Optional[ast.AST] = None) -> int:
        es_elif = (
            isinstance(nodo, ast.If)
            and isinstance(padre, ast.If)
            and nodo.col_offset == padre.col_offset
            and any(nodo is hijo for hijo in padre.orelse)
        )
        if isinstance(nodo, anidables) and not es_elif:
            nivel += 1
        hijos = [profundidad(hijo, nivel, nodo)
                 for hijo in ast.iter_child_nodes(nodo)]
        return max([nivel, *hijos])

    return profundidad(tree, 0)


def analyze_python_source(source_code: str) -> Dict[str, Any]:
    """Analiza código Python (string) y retorna métricas estructuradas."""
    try:
        tree = ast.parse(source_code)
    except SyntaxError as e:
        return {"syntax_error": str(e)}

    # Métricas básicas
    metrics = {
        "total_lines": len(source_code.splitlines()),
        "total_functions": 0,
        "total_classes": 0,
        "complexity": 0,
        "max_nesting": 0,
        "issues": []
    }

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            metrics["total_functions"] += 1
        elif isinstance(node, ast.ClassDef):
            metrics["total_classes"] += 1
        elif isinstance(node, (ast.If, ast.While, ast.For, ast.AsyncFor, ast.Try)):
            # Cada condicional se cuenta UNA vez (antes se sumaba otra vez
            # dentro de cada función que lo contenía: doble conteo).
            metrics["complexity"] += 1

    metrics["max_nesting"] = _max_nesting(tree)

    # Detectar problemas comunes
    lines = source_code.splitlines()
    for i, line in enumerate(lines, 1):
        line_stripped = line.strip()

        # Problemas de línea larga
        if len(line_stripped) > 120:
            metrics["issues"].append({
                "category": "style",
                "severity": "low",
                "description": f"Línea {i}: línea demasiado larga ({len(line_stripped)} chars)",
                "suggestion": "Dividir línea o reestructurar código",
                "thinking_reasoning": "Eficiencia: líneas largas reducen legibilidad"
            })

        # Importaciones múltiples en una línea
        if re.match(r'^\s*import\s+.+,\s+.+', line):
            metrics["issues"].append({
                "category": "style",
                "severity": "medium",
                "description": f"Línea {i}: importaciones múltiples en una línea",
                "suggestion": "Separar importaciones en líneas individuales",
                "thinking_reasoning": "Mantenimiento: importaciones separadas son más fáciles de modificar"
            })

    # Reducir issues a máximo max_issues
    max_issues = 50
    metrics["issues"] = metrics["issues"][:max_issues]

    # Recalcular score (misma referencia que el contexto)
    metrics["efficiency_score"] = min(len(metrics["issues"]) / EFFICIENCY_REFERENCE_ISSUES, 1.0)

    return {
        "metrics": metrics,
        "source_summary": {
            "total_lines": metrics["total_lines"],
            "functions": metrics["total_functions"],
            "classes": metrics["total_classes"],
            "complexity": metrics["complexity"]
        }
    }


def analyze_python_code(file_path: str) -> Dict[str, Any]:
    """Analiza un archivo Python real leyéndolo desde `file_path`."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
    except (OSError, UnicodeDecodeError) as e:
        # Un archivo legible pero no-UTF-8 también es un error de entrada:
        # el contrato devuelve {"error": ...}, no eleva (P1.19).
        return {"error": str(e)}
    return analyze_python_source(source)


# CLI principal (modo demo offline si no se configura proveedor)
def main():
    print("=" * 70)
    print("HERRAMIENTAS PARA DISEÑO Y MEJORA DE PROYECTOS DE CÓDIGO")
    print("==================================================================")
    print()
    print("Definición de inteligencia: 'Hacer las cosas de manera eficiente'")
    print("Aplicación: Análisis, diseño y mejora de proyectos de software")
    print()
    print("Arquitectura:")
    print("  CodeDesignThinker (7 pasos de pensamiento)")
    print("  │")
    print("  ├── PASO 1: Análisis código existente")
    print("  ├── PASO 2: Definir objetivos")
    print("  ├── PASO 3: Generar opciones")
    print("  ├── PASO 4: Evaluar opciones")
    print("  ├── PASO 5: Seleccionar enfoque")
    print("  ├── PASO 6: Plan implementación")
    print("  └── PASO 7: Verificar validación")
    print()
    print("  CodeAnalysisContext (estado del proyecto)")
    print("  │")
    print("  ├── Métricas: líneas, funciones, clases, complejidad")
    print("  ├── Issues: problemas detectados con severidad")
    print("  └── Decisiones: decisiones de diseño registradas")
    print()
    print("  CodeImprovementOrchestrator (orquestador completo)")
    print("  │")
    print("  └── Ejecuta ciclo completo: análisis → diseño → mejora → validación")
    print()
    print("Funcionalidades incluidas:")
    print("  • Análisis estático de código Python (AST)")
    print("  • Detección de problemas de estilo y maintainability")
    print("  • Capa de pensamiento estructurado (7 pasos)")
    print("  • Decisiones de diseño con validación en cada paso")
    print("  • Generación de planes de refactoring")
    print("  • Criterios de validación y éxito")
    print("  • Reportes markdown completos")
    print()
    print("=" * 70)

    # Ejemplo con código de demo
    demo_code = '''
def calcular_factorial(n):
    """Calcula el factorial de un número entero no negativo."""
    if n < 0:
        raise ValueError("No factorial para números negativos")
    result = 1
    for i in range(1, n + 1):
        result *= i
    return result

# Variable global no usada
GLOBAL_CONST = 42

# Importaciones múltiples
import os, sys, json, math, re, collections, datetime, uuid

def proceso_principal(datos):
    """Procesa los datos de entrada."""
    resultado = []
    for item in datos:
        if item is not None:
            resultado.append(item * 2)
    return resultado

# Código repetido
def utilidad_a():
    return 42

def utilidad_b():
    return 42

if __name__ == "__main__":
    datos = [1, 2, 3, 4, 5]
    print(calcular_factorial(5))
    print(proceso_principal(datos))
'''

    # Análisis estático
    print("\n" + "=" * 70)
    print("ANÁLISIS ESTÁTICO DE EJEMPLO DE CÓDIGO")
    print("=" * 70)

    analysis_result = analyze_python_source(demo_code)
    print("\nArchivo de ejemplo analizado:")
    print(f"  Líneas totales: {analysis_result['source_summary']['total_lines']}")
    print(f"  Funciones: {analysis_result['source_summary']['functions']}")
    print(f"  Clases: {analysis_result['source_summary']['classes']}")
    print(f"  Complejidad ciclomática: {analysis_result['source_summary']['complexity']}")
    print(f"  Issues detectados: {len(analysis_result['metrics']['issues'])}")
    print(f"  Score de eficiencia: {analysis_result['metrics']['efficiency_score']:.2f}")

    # Mostrar algunos issues
    if analysis_result['metrics']['issues']:
        print("\nIssues destacados:")
        for issue in analysis_result['metrics']['issues'][:5]:
            print(f"  - [{issue['severity'].upper()}] {issue['description']}")

    # Sistema completo con pensamiento (offline: sin proveedor usa MockLLM)
    print("\n" + "=" * 70)
    print("SISTEMA COMPLETO CON CAPA DE PENSAMIENTO")
    print("=" * 70)

    thinking_engine = CodeDesignThinker(name="code_design_thinker")
    orchestrator = CodeImprovementOrchestrator(thinking_engine, source_code=demo_code)

    orchestrator.analyze_and_improve()

    print("\n" + "=" * 70)
    print("REPORTE MARKDOWN")
    print("=" * 70)
    print(orchestrator.generate_report())


if __name__ == "__main__":
    main()
