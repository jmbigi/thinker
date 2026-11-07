#!/usr/bin/env python3
"""
Generador de Código Inteligente, Seguro, Honesto y Exacto
==========================================================

Principios (alineados con AGENTS.md del proyecto):
1. INTELIGENTE - Capa de pensamiento estructurado (7 pasos), reutiliza StepThinkingEngine
2. SEGURO - Validación en cada paso, sandboxing de ejecución, sin eval/exec no controlado
3. HONESTO - Declara cuando es simulado (MockLLM), no inventa APIs ni archivos
4. EXACTO - Verificación empírica (py_compile + tests), evidencia reproducible

Arquitectura:
- CodeGeneratorThinker: 7 pasos de pensamiento para generación
- CodeGeneratorOrchestrator: orquesta análisis → generación → validación
- Verificador integrado: py_compile + unittest + lint (ruff)
- Modo offline por defecto (MockLLM), opt-in real con proveedores
"""

import re
import sys
import time
import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Callable

from thinking_engine import StepThinkingEngine


# =====================================================================
# ESTADO Y CONTEXTO
# =====================================================================

@dataclass
class GenerationContext:
    """Contexto que mantiene el estado de la generación de código."""
    project_path: str
    requirements: str = ""
    target_language: str = "python"
    max_steps: int = 7
    issues: List[Dict[str, Any]] = field(default_factory=list)
    thinking_steps: List[Dict[str, Any]] = field(default_factory=list)
    generated_files: Dict[str, str] = field(default_factory=dict)
    validation_results: Dict[str, Any] = field(default_factory=dict)
    start_time: float = field(default_factory=time.time)
    mode: str = "offline"  # "offline" | "online"

    def add_thinking_step(self, step: str, reasoning: str, result: Any):
        self.thinking_steps.append({
            "step": step,
            "reasoning": reasoning,
            "result": result,
            "timestamp": time.time()
        })

    def add_issue(self, severity: str, description: str, file: str = "",
                  line: Optional[int] = None, suggestion: str = ""):
        self.issues.append({
            "severity": severity,
            "description": description,
            "file": file,
            "line": line,
            "suggestion": suggestion,
            "detected_at": time.time()
        })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_path": self.project_path,
            "requirements": self.requirements,
            "target_language": self.target_language,
            "mode": self.mode,
            "total_issues": len(self.issues),
            "issues": self.issues,
            "thinking_steps": len(self.thinking_steps),
            "generated_files": list(self.generated_files.keys()),
            "validation": self.validation_results,
            "elapsed_seconds": round(time.time() - self.start_time, 2)
        }


# =====================================================================
# THINKER PARA GENERACIÓN DE CÓDIGO (7 PASOS ESTRUCTURADOS)
# =====================================================================

class CodeGeneratorThinker(StepThinkingEngine):
    """
    Thinker para generación de código con 7 pasos estructurados.
    Reutiliza StepThinkingEngine: validación, confianza, decisión.
    Sin proveedor LLM → MockLLM (offline, declarado como simulado).
    """

    # Pasos canónicos
    _NOMBRES_PASOS = ("requirements_analysis", "architecture_design",
                       "interface_design", "implementation_strategy",
                       "code_generation", "validation_plan", "final_review")

    _ETIQUETAS_PASOS = ("ANÁLISIS REQUISITOS", "ARQUITECTURA",
                         "INTERFACES", "ESTRATEGIA IMPL.",
                         "GENERACIÓN CÓDIGO", "PLAN VALIDACIÓN",
                         "REVISIÓN FINAL")

    def __init__(self, name: str = "code_generator", llm_provider=None,
                 max_steps: int = 7, mode: str = "offline"):
        super().__init__(llm_provider, name, max_steps=max_steps)
        self.mode = mode  # "offline" | "online"
        self.max_thinking_steps = max_steps
        self._step_index = 0

    # Implementar métodos abstractos de StepThinkingEngine
    def _step_builders(self) -> List[Tuple[str, Callable[[Dict[str, Any]], str]]]:
        """Construye los prompts para cada paso del ciclo."""
        # El ciclo lineal usa _execute_generation_cycle, pero estos son
        # requeridos por la clase base. Devolvemos builders vacíos
        # porque nuestra lógica personalizada maneja los 7 pasos.
        return []

    def _render_thought(self, steps: List[Tuple[str, str]]) -> str:
        """Renderiza el pensamiento (usado por la clase base)."""
        return self._render_steps(steps)

    def think(self, prompt: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Compatibilidad con interfaz base: delega a generate()."""
        gen_context = context.get("generation_context") if context else None
        if gen_context:
            return self.generate(gen_context, prompt)
        # Fallback: usar ciclo base con builders vacíos
        return super().think(prompt, context)

    def generate(self, context: GenerationContext, prompt: str,
                 progress: Optional[Callable] = None) -> Dict[str, Any]:
        """Ejecuta ciclo completo de 7 pasos para generar código."""
        self._step_index = 0
        return self._execute_generation_cycle(context, prompt, progress)

    def _execute_generation_cycle(self, context: GenerationContext, prompt: str,
                                   progress: Optional[Callable]) -> Dict[str, Any]:
        steps = []
        _decir = progress or (lambda _m: None)

        # PASO 1: Análisis de requisitos
        step1 = self._llm_generate(f"""
PASO 1 - ANÁLISIS DE REQUISITOS:
Analiza los requisitos y extrae:
- Funcionalidad principal
- Entradas/salidas esperadas
- Restricciones (performance, seguridad, compatibilidad)
- Casos de borde
- Criterios de aceptación

Requisitos: {prompt}
Contexto existente: {context.requirements or "Ninguno"}

Respuesta en JSON:
{{
  "funcionalidad_principal": "...",
  "entradas": ["..."],
  "salidas": ["..."],
  "restricciones": {{"performance": "...", "seguridad": "...", "compatibilidad": "..."}},
  "casos_borde": ["..."],
  "criterios_aceptacion": ["..."]
}}
""")
        fin = self._registrar(steps, "requirements_analysis", step1, _decir)
        if fin:
            return fin

        # PASO 2: Diseño de arquitectura
        step2 = self._llm_generate(f"""
PASO 2 - DISEÑO DE ARQUITECTURA:
Define la arquitectura del código a generar:
- Estructura de módulos/clases/funciones
- Patrones de diseño aplicables
- Separación de responsabilidades
- Flujo de datos principal
- Dependencias externas (mínimas, declaradas)

Análisis: {step1}

JSON:
{{
  "modulos": [{{"nombre": "...", "responsabilidad": "..."}}],
  "patrones": ["..."],
  "flujo_datos": "descripción",
  "dependencias_externas": ["..."],
  "puntos_extension": ["..."]
}}
""")
        fin = self._registrar(steps, "architecture_design", step2, _decir)
        if fin:
            return fin

        # PASO 3: Diseño de interfaces (firmas, tipos, contratos)
        step3 = self._llm_generate(f"""
PASO 3 - DISEÑO DE INTERFACES:
Define interfaces públicas (firmas, tipos, docstrings, contratos):
- Funciones/clases públicas con type hints
- Precondiciones y postcondiciones
- Excepciones documentadas
- Ejemplos de uso en docstrings

Arquitectura: {step2}

JSON:
{{
  "interfaces": [
    {{
      "nombre": "...",
      "tipo": "function|class",
      "firma": "def foo(x: int) -> str:",
      "docstring": "Descripción... Args: ... Returns: ... Raises: ...",
      "precondiciones": ["..."],
      "postcondiciones": ["..."],
      "excepciones": ["ValueError si ..."]
    }}
  ]
}}
""")
        fin = self._registrar(steps, "interface_design", step3, _decir)
        if fin:
            return fin

        # PASO 4: Estrategia de implementación
        step4 = self._llm_generate(f"""
PASO 4 - ESTRATEGIA DE IMPLEMENTACIÓN:
Planifica cómo implementar cada interfaz:
- Algoritmos clave
- Estructuras de datos
- Manejo de errores
- Logging/observabilidad
- Tests unitarios a generar

Interfaces: {step3}

JSON:
{{
  "implementaciones": [
    {{
      "interfaz": "nombre",
      "algoritmo": "descripción",
      "estructuras_datos": ["..."],
      "manejo_errores": "estrategia",
      "tests_sugeridos": ["..."]
    }}
  ]
}}
""")
        fin = self._registrar(steps, "implementation_strategy", step4, _decir)
        if fin:
            return fin

        # PASO 5: Generación de código REAL (no simulado)
        step5 = self._llm_generate(f"""
PASO 5 - GENERACIÓN DE CÓDIGO:
TU RESPUESTA DEBE EMPEZAR CON {{ Y SER EXCLUSIVAMENTE JSON VÁLIDO.
NO ESCRIBAS TEXTO EXPLICATIVO, NO USES MARKDOWN, NO INCLUYAS RAZONAMIENTO.

Genera el código COMPLETO y EJECUTABLE para cada módulo.
REGLAS ESTRICTAS:
- Código real, no pseudocódigo
- Type hints completos
- Docstrings estilo Google/NumPy
- Manejo de errores real
- Sin placeholders (pass, TODO, ...)
- Imports al inicio, ordenados
- Compatibilidad Python 3.11+

Estrategia: {step4}
Interfaces: {step3}

RESPONDE SOLO CON ESTE JSON (empieza con {{, termina con }}):
{{
  "archivos": {{
    "main.py": "código completo del archivo principal como string con \\n escapados",
    "utils/helpers.py": "otro archivo si aplica",
    "tests/test_main.py": "tests unitarios completos con unittest"
  }}
}}
""")
        fin = self._registrar(steps, "code_generation", step5, _decir)
        if fin:
            return fin

        # PASO 6: Plan de validación empírica
        step6 = self._llm_generate(f"""
PASO 6 - PLAN DE VALIDACIÓN EMPÍRICA:
Define cómo VERIFICAR el código generado (no simulado):
- py_compile (sintaxis)
- unittest (cobertura funcional)
- ruff (lint, 0 errores)
- mypy (tipos, opcional)
- Tests de borde

Código generado: {step5[:500]}...

JSON:
{{
  "validaciones": [
    {{"herramienta": "py_compile", "objetivo": "sintaxis válida", "criterio": "exit 0"}},
    {{"herramienta": "ruff", "objetivo": "lint", "criterio": "0 errores"}},
    {{"herramienta": "unittest", "objetivo": "funcionalidad", "criterio": "cobertura >= 80%"}},
    {{"herramienta": "mypy", "objetivo": "tipos", "criterio": "0 errores (opcional)"}}
  ],
  "tests_esperados": ["..."],
  "casos_borde_a_probar": ["..."]
}}
""")
        fin = self._registrar(steps, "validation_plan", step6, _decir)
        if fin:
            return fin

        # PASO 7: Revisión final y decision
        step7 = self._llm_generate(f"""
PASO 7 - REVISIÓN FINAL Y DECISIÓN:
Revisa todo lo generado y decide:
- ¿El código cumple los requisitos originales?
- ¿Es seguro (sin eval/exec, validación entradas)?
- ¿Es honesto (declara limitaciones, no inventa)?
- ¿Es exacto (verificable empíricamente)?

Validación: {step6}

JSON:
{{
  "aprobado": true/false,
  "justificacion": "explicación breve",
  "limitaciones_conocidas": ["..."],
  "mejoras_futuras": ["..."]
}}
""")
        fin = self._registrar(steps, "final_review", step7, _decir)
        if fin:
            return fin

        return self._resultado_valido(steps)

    def _registrar(self, steps: List[Tuple[str, str]], nombre: str, contenido: str,
                   progress) -> Optional[Dict[str, Any]]:
        if not self.validate_step(contenido):
            return self._resultado_invalido(steps, nombre)
        steps.append((nombre, contenido))
        if progress:
            progress(f"paso {len(steps)}/{self.max_thinking_steps}: {nombre}")
        if len(steps) >= self.max_thinking_steps:
            return self._resultado_valido(steps)
        return None

    def _resultado_valido(self, steps: List[Tuple[str, str]]) -> Dict[str, Any]:
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

    def _resultado_invalido(self, steps: List[Tuple[str, str]], nombre: str) -> Dict[str, Any]:
        numero = self._NOMBRES_PASOS.index(nombre) + 1
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
        lines = [f"        CODE GENERATOR THINKER: {self.name}", "        =================================", ""]
        for i, (nombre, contenido) in enumerate(steps):
            etiqueta = self._ETIQUETAS_PASOS[self._NOMBRES_PASOS.index(nombre)]
            lines.append(f"        PASO {i + 1} - {etiqueta}: {contenido[:150]}")
        lines.extend(["", f"        PASOS: {len(steps)}/{self.max_thinking_steps}",
                       f"        DECISIÓN: {self._extract_decision(steps)}",
                       f"        CONFIANZA: {self._compute_confidence(steps)}"])
        return "\n".join(lines)

    def _extract_decision(self, steps: List[Tuple[str, str]]) -> str:
        """Extrae la decisión final del último paso válido."""
        for nombre, contenido in reversed(steps):
            if nombre == "final_review":
                return contenido[:200]
            if nombre == "code_generation":
                return "Código generado"
        return "En progreso"

    def _compute_confidence(self, steps: List[Tuple[str, str]]) -> float:
        """Confianza heurística: pasos completados / total."""
        if not steps:
            return 0.0
        return round(len(steps) / self.max_thinking_steps, 2)


# =====================================================================
# VERIFICADOR EMPÍRICO (py_compile + ruff + unittest)
# =====================================================================

class EmpiricalValidator:
    """
    Validador empírico: ejecuta herramientas REALES sobre el código generado.
    No simula, no asume: VERIFICA.
    """

    @staticmethod
    def validate_syntax(code: str, filename: str = "generated.py") -> Dict[str, Any]:
        """py_compile - sintaxis válida con la herramienta real."""
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                temp_path = Path(tmpdir) / (Path(filename).name or "generated.py")
                if temp_path.suffix != ".py":
                    temp_path = temp_path.with_suffix(".py")
                temp_path.write_text(code)
                result = subprocess.run(
                    [sys.executable, "-m", "py_compile", str(temp_path)],
                    capture_output=True, text=True, timeout=30
                )
                return {
                    "passed": result.returncode == 0,
                    "tool": "py_compile",
                    "errors": result.stderr.splitlines() if result.stderr else [],
                }
        except (subprocess.TimeoutExpired, OSError) as exc:
            return {"passed": False, "tool": "py_compile", "errors": [str(exc)]}

    @staticmethod
    def validate_ruff(code: str, filename: str = "generated.py") -> Dict[str, Any]:
        """ruff check - lint 0 errores."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(code)
            temp_path = f.name
        try:
            result = subprocess.run(
                ["ruff", "check", temp_path],
                capture_output=True, text=True, timeout=30
            )
            return {
                "passed": result.returncode == 0,
                "tool": "ruff",
                "errors": result.stdout.splitlines() if result.stdout else [],
                "stderr": result.stderr
            }
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            return {"passed": False, "tool": "ruff", "errors": [str(e)]}
        finally:
            temp_file = Path(temp_path)
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError:
                    # Fallo silencioso esperado: archivo ya borrado o permisos
                    _cleanup_failed = True

    @staticmethod
    def validate_unittest(test_code: str, source_code: str,
                          module_name: str = "generated") -> Dict[str, Any]:
        """Ejecuta tests unitarios reales."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            # Escribir código fuente
            (tmp / f"{module_name}.py").write_text(source_code)
            # Escribir tests
            (tmp / f"test_{module_name}.py").write_text(test_code)
            # __init__.py para imports
            (tmp / "__init__.py").write_text("")

            try:
                result = subprocess.run(
                    [sys.executable, "-m", "unittest",
                     f"test_{module_name}", "-v"],
                    cwd=tmpdir, capture_output=True, text=True, timeout=60
                )
                passed = result.returncode == 0
                return {
                    "passed": passed,
                    "tool": "unittest",
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "tests_run": result.stdout.count("ok") + result.stdout.count("FAIL")
                }
            except subprocess.TimeoutExpired:
                return {"passed": False, "tool": "unittest",
                        "errors": ["Timeout (>60s)"]}

    @staticmethod
    def validate_all(source_files: Dict[str, str],
                     test_files: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Valida todo el proyecto generado."""
        if test_files is None:
            # Los tests pueden venir en el mismo dict de archivos generados.
            test_files = {
                name: code for name, code in source_files.items()
                if Path(name).name.startswith("test_")
            }
        results = {"files": {}, "summary": {"total": 0, "passed": 0, "failed": 0}}

        for filename, code in source_files.items():
            if not filename.endswith(".py"):
                continue
            file_results = {}
            # Sintaxis
            file_results["syntax"] = EmpiricalValidator.validate_syntax(code, filename)
            # Lint
            file_results["lint"] = EmpiricalValidator.validate_ruff(code, filename)

            # Tests si existen (buscar test_<stem>.py en cualquier carpeta)
            test_name = f"test_{Path(filename).stem}.py"
            test_file = next(
                (name for name in test_files if Path(name).name == test_name), None)
            if test_file:
                file_results["tests"] = EmpiricalValidator.validate_unittest(
                    test_files[test_file], code, Path(filename).stem
                )

            file_passed = all(r.get("passed", False) for r in file_results.values())
            results["files"][filename] = {"results": file_results, "passed": file_passed}
            results["summary"]["total"] += 1
            if file_passed:
                results["summary"]["passed"] += 1
            else:
                results["summary"]["failed"] += 1

        return results


# =====================================================================
# ORQUESTADOR PRINCIPAL
# =====================================================================

class CodeGeneratorOrchestrator:
    """
    Orquesta: Thinker (7 pasos) → Generación → Validación empírica.
    Principio: "Hacer las cosas de manera eficiente" - un ciclo, no 49 llamadas.
    """

    def __init__(self, thinker: CodeGeneratorThinker, context: GenerationContext):
        self.thinker = thinker
        self.context = context
        self.validator = EmpiricalValidator()

    def generate_and_validate(self, requirements: str,
                              progress: Optional[Callable] = None) -> Dict[str, Any]:
        """Ciclo completo: Thinker → Generación → Validación real."""
        _decir = progress or (lambda _m: None)

        _decir(">>> Iniciando generador de código (modo: {})".format(self.context.mode))
        _decir(">>> Capa de pensamiento: 7 pasos estructurados")

        # 1. CICLO THINKER (7 pasos)
        _decir(">>> Ejecutando ciclo de pensamiento...")
        ciclo = self.thinker.generate(self.context, requirements, progress=_decir)

        if not ciclo["valid"]:
            return {
                "error": f"Ciclo de pensamiento falló: {ciclo.get('error', 'paso inválido')}",
                "thinking": ciclo,
                "validation": None
            }

        _decir(f">>> Pensamiento completado: {ciclo['step_count']} pasos, confianza={ciclo['confidence']}")

        # 2. EXTRAER CÓDIGO GENERADO del paso 5
        code_step = next((s for s in ciclo["steps"] if s[0] == "code_generation"), None)
        if not code_step:
            return {"error": "No se generó código (paso 5 ausente)", "thinking": ciclo}

        generated = self._parse_generated_code(code_step[1])
        self.context.generated_files = generated.get("archivos", {})

        # 3. VALIDACIÓN EMPÍRICA REAL
        _decir(">>> Validando código generado (py_compile + ruff + unittest)...")
        validation = self.validator.validate_all(self.context.generated_files)
        self.context.validation_results = validation

        _decir(f">>> Validación: {validation['summary']['passed']}/{validation['summary']['total']} archivos OK")

        return {
            "thinking": ciclo,
            "generated": self.context.generated_files,
            "validation": validation,
            "context": self.context.to_dict()
        }

    @staticmethod
    def _try_parse_json(text: str) -> Optional[Dict[str, Any]]:
        """Intenta parsear JSON, retorna None si falla."""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    def _parse_generated_code(self, step_content: str) -> Dict[str, Any]:
        """Extrae JSON del contenido del paso 5."""
        # 1. Buscar bloque JSON en markdown ```json ... ``` (requiere ```json al inicio de línea)
        match = re.search(r'(?m)^```json\s*(\{.*?\})\s*```', step_content, re.DOTALL)
        if match:
            parsed = self._try_parse_json(match.group(1))
            if parsed:
                return parsed
        # 2. Buscar bloque JSON en markdown genérico ``` ... ```
        match = re.search(r'(?m)^```\s*(\{.*?\})\s*```', step_content, re.DOTALL)
        if match:
            parsed = self._try_parse_json(match.group(1))
            if parsed and "archivos" in parsed:
                return parsed
        # 3. Extraer JSON balanceado que contenga "archivos" (cuenta llaves)
        idx = step_content.find('"archivos"')
        if idx >= 0:
            start = step_content.rfind('{', 0, idx)
            if start >= 0:
                balance = 0
                for i, ch in enumerate(step_content[start:], start):
                    if ch == '{':
                        balance += 1
                    elif ch == '}':
                        balance -= 1
                        if balance == 0:
                            candidate = step_content[start:i+1]
                            parsed = self._try_parse_json(candidate)
                            if parsed and "archivos" in parsed:
                                return parsed
                            break
        # 4. Fallback: buscar cualquier JSON válido con "archivos"
        for match in re.finditer(r'\{.*?"archivos".*?\}', step_content, re.DOTALL):
            parsed = self._try_parse_json(match.group(0))
            if parsed and "archivos" in parsed:
                return parsed
        return {"archivos": {}}

    def save_generated(self, output_dir: str) -> List[str]:
        """Guarda archivos generados en disco, sin salir del directorio."""
        out = Path(output_dir).resolve()
        out.mkdir(parents=True, exist_ok=True)
        saved = []
        for rel_path, content in self.context.generated_files.items():
            file_path = (out / rel_path).resolve()
            if file_path == out or not file_path.is_relative_to(out):
                raise ValueError(
                    f"Ruta generada fuera del directorio de salida: {rel_path!r}")
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)
            saved.append(str(file_path))
        return saved


# =====================================================================
# MOCK LLM (OFFLINE, DECLARADO COMO SIMULADO)
# =====================================================================

class MockLLM:
    """Mock LLM determinista para modo offline. DECLARADO COMO SIMULADO."""

    def __init__(self):
        self.call_count = 0

    def generate(self, prompt: str) -> str:
        self.call_count += 1
        step_num = self.call_count

        # Respuestas deterministas por paso
        if step_num == 1:  # requirements_analysis
            return json.dumps({
                "funcionalidad_principal": "Generar código Python seguro y verificable",
                "entradas": ["requisitos en lenguaje natural"],
                "salidas": ["código Python con tests", "validación empírica"],
                "restricciones": {
                    "performance": "ejecución < 5s",
                    "seguridad": "sin eval/exec, validación entradas",
                    "compatibilidad": "Python 3.11+"
                },
                "casos_borde": ["requisitos vacíos", "requisitos ambiguos", "código inválido"],
                "criterios_aceptacion": ["py_compile OK", "ruff 0 errores", "tests pasan"]
            })
        elif step_num == 2:  # architecture_design
            return json.dumps({
                "modulos": [
                    {"nombre": "code_generator", "responsabilidad": "Generación principal"},
                    {"nombre": "validator", "responsabilidad": "Validación empírica"},
                    {"nombre": "orchestrator", "responsabilidad": "Orquestación completa"}
                ],
                "patrones": ["Builder", "Strategy", "Template Method"],
                "flujo_datos": "Requisitos → Thinker → Código → Validador → Resultado",
                "dependencias_externas": ["ruff", "unittest", "ast (stdlib)"],
                "puntos_extension": ["nuevos validadores", "nuevos lenguajes target"]
            })
        elif step_num == 3:  # interface_design
            return json.dumps({
                "interfaces": [
                    {
                        "nombre": "generate_and_validate",
                        "tipo": "function",
                        "firma": "def generate_and_validate(self, requirements: str) -> Dict[str, Any]:",
                        "docstring": "Genera y valida código. Args: requirements. Returns: dict con thinking, generated, validation.",
                        "precondiciones": ["requirements no vacío"],
                        "postcondiciones": ["retorna dict con keys thinking, generated, validation"],
                        "excepciones": ["ValueError si requirements vacío"]
                    }
                ]
            })
        elif step_num == 4:  # implementation_strategy
            return json.dumps({
                "implementaciones": [
                    {
                        "interfaz": "generate_and_validate",
                        "algoritmo": "Ciclo thinker → parseo JSON → escritura archivos → validación subprocess",
                        "estructuras_datos": ["dict para resultados", "tempfile para aislamiento"],
                        "manejo_errores": "try/except en cada subprocess, timeout 60s",
                        "tests_sugeridos": ["test_generacion_basica", "test_validacion_falla", "test_codigo_invalido"]
                    }
                ]
            })
        elif step_num == 5:  # code_generation - GENERA CÓDIGO REAL
            return json.dumps({
                "archivos": {
                    "generated_code.py": (
                        '"""Módulo generado - DEMO OFFLINE SIMULADO."""\n\n'
                        'def saludar(nombre: str) -> str:\n'
                        '    """Saluda a una persona.\n\n'
                        '    Args:\n'
                        '        nombre: Nombre de la persona.\n\n'
                        '    Returns:\n'
                        '        Saludo formateado.\n\n'
                        '    Raises:\n'
                        '        ValueError: Si nombre está vacío.\n'
                        '    """\n'
                        '    if not nombre or not nombre.strip():\n'
                        '        raise ValueError("Nombre no puede estar vacío")\n'
                        '    return f"Hola, {nombre.strip()}!"\n\n\n'
                        'def sumar(a: int, b: int) -> int:\n'
                        '    """Suma dos enteros.\n\n'
                        '    Args:\n'
                        '        a: Primer sumando.\n'
                        '        b: Segundo sumando.\n\n'
                        '    Returns:\n'
                        '        Suma de a y b.\n'
                        '    """\n'
                        '    return a + b\n\n\n'
                        'if __name__ == "__main__":\n'
                        '    print(saludar("Mundo"))\n'
                        '    print(sumar(2, 3))\n'
                    ),
                    "tests/test_generated_code.py": (
                        '"""Tests para módulo generado - DEMO OFFLINE SIMULADO."""\n\n'
                        'import unittest\n'
                        'from generated_code import saludar, sumar\n\n\n'
                        'class TestSaludar(unittest.TestCase):\n'
                        '    def test_saludar_normal(self):\n'
                        '        self.assertEqual(saludar("Mundo"), "Hola, Mundo!")\n\n'
                        '    def test_saludar_con_espacios(self):\n'
                        '        self.assertEqual(saludar("  Ana  "), "Hola, Ana!")\n\n'
                        '    def test_saludar_vacio_raise(self):\n'
                        '        with self.assertRaises(ValueError):\n'
                        '            saludar("")\n\n'
                        '    def test_saludar_none_raise(self):\n'
                        '        with self.assertRaises(ValueError):\n'
                        '            saludar(None)\n\n\n'
                        'class TestSumar(unittest.TestCase):\n'
                        '    def test_sumar_positivos(self):\n'
                        '        self.assertEqual(sumar(2, 3), 5)\n\n'
                        '    def test_sumar_negativos(self):\n'
                        '        self.assertEqual(sumar(-1, -1), -2)\n\n'
                        '    def test_sumar_cero(self):\n'
                        '        self.assertEqual(sumar(0, 5), 5)\n\n\n'
                        'if __name__ == "__main__":\n'
                        '    unittest.main()\n'
                    )
                }
            })
        elif step_num == 6:  # validation_plan
            return json.dumps({
                "validaciones": [
                    {"herramienta": "py_compile", "objetivo": "sintaxis válida", "criterio": "exit 0"},
                    {"herramienta": "ruff", "objetivo": "lint", "criterio": "0 errores"},
                    {"herramienta": "unittest", "objetivo": "funcionalidad", "criterio": "cobertura >= 80%"}
                ],
                "tests_esperados": ["test_saludar_normal", "test_sumar_positivos"],
                "casos_borde_a_probar": ["entrada vacía", "None", "números negativos"]
            })
        elif step_num == 7:  # final_review
            return json.dumps({
                "aprobado": True,
                "justificacion": "Código generado cumple requisitos, tiene tests, validación empírica definida",
                "limitaciones_conocidas": ["Demo offline: código fijo, no adaptativo a requisitos variables"],
                "mejoras_futuras": ["Integrar LLM real opt-in", "Más plantillas de código", "Validación mypy"]
            })
        return json.dumps({"error": "Paso no reconocido"})


# =====================================================================
# CLI / DEMO
# =====================================================================

def main():
    print("*** MODO DEMO OFFLINE — RESULTADOS SIMULADOS ***")
    print("    LLM: MockLLM (determinista, sin red)")
    print("    Validación: EMPÍRICA REAL (py_compile + ruff + unittest)\n")

    # Configuración
    context = GenerationContext(
        project_path="demo_output",
        requirements="Generar un módulo Python con funciones básicas y tests",
        mode="offline"
    )

    # Thinker con MockLLM
    mock_llm = MockLLM()
    thinker = CodeGeneratorThinker(name="demo_generator", llm_provider=mock_llm, mode="offline")
    # Inyectar MockLLM en el motor base
    thinker._llm = mock_llm

    orchestrator = CodeGeneratorOrchestrator(thinker, context)

    # Ejecutar
    print("=" * 60)
    print("GENERANDO CÓDIGO CON VALIDACIÓN EMPÍRICA")
    print("=" * 60)

    result = orchestrator.generate_and_validate(
        "Crear un módulo con función saludar(nombre) y sumar(a,b) con tests",
        progress=lambda m: print(f"   {m}")
    )

    if "error" in result:
        print(f"\nERROR: {result['error']}")
        return 1

    # Mostrar resultados
    print("\n" + "=" * 60)
    print("RESULTADO")
    print("=" * 60)

    val = result["validation"]
    print(f"Archivos generados: {len(result['generated'])}")
    print(f"Validación: {val['summary']['passed']}/{val['summary']['total']} OK")

    for fname, fres in val["files"].items():
        status = "✅" if fres["passed"] else "❌"
        print(f"  {status} {fname}")
        for tool, tres in fres["results"].items():
            tstatus = "✓" if tres.get("passed") else "✗"
            print(f"    {tstatus} {tool}")

    # Guardar
    saved = orchestrator.save_generated("demo_output")
    print("\nGuardado en: demo_output/")
    for f in saved:
        print(f"  {f}")

    print("\n*** FIN DEMO OFFLINE ***")
    return 0


if __name__ == "__main__":
    sys.exit(main())