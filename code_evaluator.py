#!/usr/bin/env python3
"""Evaluación local y offline de código generado (herramienta real, opt-in).

No depende de Node, Docker, Proof, Promptfoo ni red. Valida sintaxis con
`ast.parse` y, si hay casos, ejecuta el código en un subproceso Python aislado
con `shell=False`, sin entorno heredado y con timeout. La ausencia de sandbox
de contenedor se declara en el resultado: esto NO equivale a Proof/Epicbox.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


def _cap(texto: Any, limite: int = 4000) -> str:
    s = "" if texto is None else str(texto)
    return s if len(s) <= limite else s[:limite] + f"\n...[truncado {len(s)-limite} chars]"



@dataclass
class TestCase:
    """Caso de prueba ejecutable por stdin/stdout o por llamada simple."""

    name: str
    input_data: Any = None
    expected_output: Any = None
    expected_error: bool = False
    timeout_seconds: float = 30.0
    args: List[str] = field(default_factory=list)
    stdin: Optional[str] = None


@dataclass
class EvalResult:
    """Resultado verificable de la evaluación."""

    passed: bool
    syntax_ok: bool
    failures: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    cases: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class CodeEvaluator:
    """Evalúa código Python generado sin herramientas externas."""

    def __init__(self, python_executable: Optional[str] = None):
        self.python_executable = python_executable or sys.executable

    def evaluate_generated_code(
        self,
        code: str,
        test_cases: Optional[List[TestCase]] = None,
        language: str = "python",
    ) -> EvalResult:
        inicio = time.monotonic()
        test_cases = list(test_cases or [])
        meta = {"engine": "local", "sandbox": "subprocess", "language": language}
        if not isinstance(code, str):
            return EvalResult(
                passed=False,
                syntax_ok=False,
                failures=[f"Código inválido: se esperaba str, recibido {type(code).__name__}"],
                duration_seconds=time.monotonic() - inicio,
                metadata=meta,
            )
        if language != "python":
            return EvalResult(
                passed=False,
                syntax_ok=False,
                failures=[f"Lenguaje no soportado por el evaluador local: {language}"],
                duration_seconds=time.monotonic() - inicio,
                metadata=meta,
            )

        try:
            ast.parse(code)
        except SyntaxError as exc:
            return EvalResult(
                passed=False,
                syntax_ok=False,
                failures=[f"SyntaxError: {exc.msg} (línea {exc.lineno})"],
                duration_seconds=time.monotonic() - inicio,
                metadata=meta,
            )

        failures: List[str] = []
        cases: List[Dict[str, Any]] = []
        with tempfile.TemporaryDirectory(prefix="thinker-codeeval-") as tmp:
            ruta = Path(tmp) / "generated.py"
            ruta.write_text(code, encoding="utf-8")
            for caso in test_cases:
                detalle = self._run_case(ruta, caso)
                cases.append(detalle)
                if not detalle["passed"]:
                    failures.append(f"{caso.name}: {detalle['reason']}")

        return EvalResult(
            passed=not failures,
            syntax_ok=True,
            failures=failures,
            duration_seconds=time.monotonic() - inicio,
            cases=cases,
            metadata={
                "engine": "local",
                "sandbox": "subprocess",
                "language": language,
                "note": "No usa Docker/Proof/Promptfoo; aislamiento limitado a subproceso.",
            },
        )

    def _run_case(self, ruta: Path, caso: TestCase) -> Dict[str, Any]:
        args = [self.python_executable, "-I", str(ruta)] + list(caso.args)
        if caso.input_data is not None and not caso.args:
            # Compatibilidad con el formato simple del archivo archivado.
            if isinstance(caso.input_data, (list, tuple)):
                args.extend(str(v) for v in caso.input_data)
            else:
                args.append(str(caso.input_data))
        stdin = caso.stdin
        if stdin is None and caso.input_data is not None and not caso.args and not isinstance(
            caso.input_data, (list, tuple)
        ):
            stdin = str(caso.input_data)
        timeout = float(getattr(caso, "timeout_seconds", 30.0) or 30.0)
        if timeout <= 0:
            timeout = 30.0
        env = {"PATH": os.environ.get("PATH", ""), "PYTHONIOENCODING": "utf-8",
               "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
        try:
            proc = subprocess.run(
                args,
                input=stdin,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(ruta.parent),
                env=env,
                shell=False,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {"name": caso.name, "passed": False, "reason": f"timeout ({timeout}s)"}
        except OSError as exc:
            return {"name": caso.name, "passed": False, "reason": f"ejecución falló: {exc}"}

        salida = proc.stdout
        if caso.expected_error:
            ok = proc.returncode != 0
            reason = "ok" if ok else f"se esperaba error y salió con rc={proc.returncode}"
            return {"name": caso.name, "passed": ok, "reason": reason, "rc": proc.returncode, "stdout": _cap(salida), "stderr": _cap(proc.stderr)}
        if proc.returncode != 0:
            return {
                "name": caso.name,
                "passed": False,
                "reason": f"rc={proc.returncode}: {proc.stderr.strip() or salida.strip()}",
                "rc": proc.returncode,
                "stdout": salida,
                "stderr": proc.stderr,
            }
        if caso.expected_output is None:
            return {"name": caso.name, "passed": True, "reason": "ok", "rc": 0, "stdout": _cap(salida), "stderr": _cap(proc.stderr)}

        esperado = caso.expected_output
        if isinstance(esperado, (dict, list)):
            try:
                obtenido = json.loads(salida)
            except json.JSONDecodeError:
                obtenido = salida
            ok = obtenido == esperado
            reason = "ok" if ok else f"esperado={esperado!r} obtenido={obtenido!r}"
        else:
            esperado_txt = str(esperado)
            ok = salida == esperado_txt or salida.strip() == esperado_txt.strip()
            reason = "ok" if ok else f"esperado={esperado_txt!r} obtenido={salida!r}"
        return {"name": caso.name, "passed": ok, "reason": reason, "rc": proc.returncode, "stdout": _cap(salida), "stderr": _cap(proc.stderr)}


__all__ = ["CodeEvaluator", "EvalResult", "TestCase"]
