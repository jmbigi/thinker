#!/usr/bin/env python3
"""Registro de métricas de calidad con fecha, commit, alcance y evidencia.

No sustituye a los gates: los gates dicen PASS/FAIL; estas métricas dicen
*cuánto* mide cada instrumento y con qué límites. Cada bloque declara su
método y lo que **no** prueba. La historia se guarda en
`docs/metricas-calidad.json`; el detalle narrativo, en `docs/EVALUACIONES.md`.

Uso:
    python3 scripts/metricas_calidad.py                  # mide y escribe JSON
    python3 scripts/metricas_calidad.py --json           # imprime, no escribe
    python3 scripts/metricas_calidad.py --con-cobertura  # añade cobertura de ramas
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from scripts.check_docs import contar_tests  # noqa: E402
from tests.benchmarks.calibracion_confianza import evaluar as evaluar_calibracion  # noqa: E402
from tests.benchmarks.evaluador_holdout import evaluar_holdout  # noqa: E402
from tests.benchmarks.evaluador_precision import evaluar_corpus  # noqa: E402
from tests.benchmarks.rag_retrieval import evaluar as evaluar_rag  # noqa: E402
from tests.benchmarks.rendimiento import ejecutar as ejecutar_rendimiento  # noqa: E402


def _commit() -> Optional[str]:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=RAIZ, check=True,
            capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _cobertura_ramas() -> Dict[str, Any]:
    """Ejecuta la suite con coverage --branch y devuelve el total agregado."""
    with tempfile.TemporaryDirectory() as tmp:
        datos = Path(tmp) / ".coverage"
        informe = Path(tmp) / "coverage.json"
        entorno = {"COVERAGE_FILE": str(datos)}
        comando = [sys.executable, "-m", "coverage", "run", "--branch",
                   "--source=.", "-m", "unittest", "discover", "-s", "tests"]
        ejecucion = subprocess.run(comando, cwd=RAIZ, capture_output=True,
                                   text=True, env={**os.environ, **entorno},
                                   timeout=1800)
        if ejecucion.returncode != 0:
            return {"estado": "FAIL", "motivo": ejecucion.stdout[-500:]
                    + ejecucion.stderr[-500:]}
        exportar = subprocess.run(
            [sys.executable, "-m", "coverage", "json", "-o", str(informe)],
            cwd=RAIZ, capture_output=True, text=True,
            env={**os.environ, **entorno}, timeout=120)
        if exportar.returncode != 0 or not informe.exists():
            return {"estado": "FAIL", "motivo": exportar.stderr[-500:]}
        datos_json = json.loads(informe.read_text(encoding="utf-8"))
    total = datos_json.get("totals", {})
    ramas = total.get("num_branches")
    cubiertas = total.get("covered_branches")
    porcentaje_ramas = (round(100 * cubiertas / ramas, 2)
                        if ramas and cubiertas is not None else None)
    return {
        "estado": "PASS",
        "porcentaje_lineas": total.get("percent_covered"),
        "porcentaje_ramas": porcentaje_ramas,
        "lineas": total.get("num_statements"),
        "ramas": ramas,
        "ramas_cubiertas": cubiertas,
        "faltantes": total.get("missing_lines"),
        "comando": ("python3 -m coverage run --branch --source=. "
                    "-m unittest discover -s tests"),
    }


def recolectar(con_cobertura: bool = False) -> Dict[str, Any]:
    precision = evaluar_corpus()
    holdout = evaluar_holdout()
    rag = evaluar_rag()
    calibracion = evaluar_calibracion()
    rendimiento = ejecutar_rendimiento()
    metricas: Dict[str, Any] = {
        "tests_estaticos": {
            "valor": contar_tests(RAIZ),
            "metodo": "conteo AST de métodos test_* en TestCase",
            "no_prueba": "que los tests sean fuertes o que el producto sea correcto",
        },
        "evaluador_precision": {
            "casos": precision["casos"],
            "criterios_objetivo": precision["criterios"],
            "precision": precision["global"]["precision"],
            "recall": precision["global"]["recall"],
            "f1": precision["global"]["f1"],
            "accuracy": precision["global"]["accuracy"],
            "cobertura": precision["cobertura"],
            "metodo": "fixtures sintéticas etiquetadas, offline",
            "no_prueba": "precisión sobre repositorios reales ni independencia humana",
        },
        "evaluador_holdout": {
            "casos": holdout["casos"],
            "aprobadas": holdout["aprobadas"],
            "total": holdout["total"],
            "exactitud": holdout["exactitud"],
            "metodo": holdout["metodo"],
            "no_prueba": "validez externa: fixtures creadas por el mismo proyecto",
        },
        "rag": {
            "corpus": rag["corpus"],
            "consultas": rag["consultas"],
            "metricas": rag["metricas"],
            "metodo": rag["metodo"],
            "no_prueba": rag["no_prueba"],
        },
        "calibracion": {
            "casos": calibracion["casos"],
            "brier": calibracion["brier"],
            "ece": calibracion["ece"],
            "calibrada": calibracion["calibrada"],
            "metodo": "confianzas simuladas; instrumento de medida",
            "no_prueba": "calibración real: no hay etiquetas humanas suficientes",
        },
        "rendimiento": {
            "escenarios": rendimiento["escenarios"],
            "modo": rendimiento["modo"],
            "metodo": "tres escenarios con MockLLM/MockSearchAPI",
            "no_prueba": "latencia ni coste con proveedores reales",
        },
    }
    if con_cobertura:
        metricas["cobertura_ramas"] = _cobertura_ramas()
    return {
        "schema_version": 1,
        "generado": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit": _commit(),
        "python": platform.python_version(),
        "so": platform.platform(),
        "metricas": metricas,
    }


def _actualizar_historial(informe: Dict[str, Any]) -> Dict[str, Any]:
    destino = RAIZ / "docs" / "metricas-calidad.json"
    historial = []
    if destino.exists():
        try:
            previo = json.loads(destino.read_text(encoding="utf-8"))
            historial = previo.get("historial", [])
        except (json.JSONDecodeError, OSError):
            historial = []
    entrada = {
        "generado": informe["generado"],
        "commit": informe["commit"],
        "python": informe["python"],
        "so": informe["so"],
        "metricas": informe["metricas"],
    }
    if historial and historial[-1].get("commit") == informe["commit"]:
        historial[-1] = entrada
    else:
        historial.append(entrada)
    return {"schema_version": 1, "historial": historial}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true",
                        help="imprime el informe y no escribe")
    parser.add_argument("--con-cobertura", action="store_true",
                        help="ejecuta coverage --branch (más lento)")
    args = parser.parse_args(argv)
    informe = recolectar(con_cobertura=args.con_cobertura)
    if args.json:
        print(json.dumps(informe, ensure_ascii=False, indent=2))
    else:
        destino = RAIZ / "docs" / "metricas-calidad.json"
        historial = _actualizar_historial(informe)
        destino.write_text(json.dumps(historial, ensure_ascii=False, indent=2)
                           + "\n", encoding="utf-8")
        print(f"Métricas escritas en {destino.relative_to(RAIZ)}")
        print(f"  tests estáticos: {informe['metricas']['tests_estaticos']['valor']}")
        print(f"  evaluador: F1={informe['metricas']['evaluador_precision']['f1']:.3f} "
              f"holdout={informe['metricas']['evaluador_holdout']['exactitud']:.3f}")
        print(f"  RAG: Recall@5={informe['metricas']['rag']['metricas']['recall@5']:.3f} "
              f"MRR={informe['metricas']['rag']['metricas']['mrr']:.3f}")
        print(f"  calibración simulada: Brier={informe['metricas']['calibracion']['brier']:.4f} "
              f"ECE={informe['metricas']['calibracion']['ece']:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
