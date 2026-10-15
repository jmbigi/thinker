"""Rúbricas de evaluación binarias estilo DeepResearch Bench.

Tres dimensiones principales:
1. Information Recall - ¿Recupera la información correcta y relevante?
2. Analysis - ¿Analiza, sintetiza y razona correctamente?
3. Presentation - ¿Presenta de forma clara, estructurada y accionable?

Cada rúbrica es una lista de criterios binarios (Sí/No = 1/0).
"""

from typing import Dict, List, Any
from dataclasses import dataclass


@dataclass
class RubricCriterion:
    """Criterio individual de una rúbrica."""
    id: str
    description: str
    dimension: str  # "information_recall" | "analysis" | "presentation"
    weight: float = 1.0


# --- RÚBRICA 1: INFORMATION RECALL (Recuperación de información) ---
INFORMATION_RECALL_RUBRIC: List[RubricCriterion] = [
    RubricCriterion("ir_01", "Cita fuentes primarias relevantes y verificables", "information_recall"),
    RubricCriterion("ir_02", "Incluye datos cuantitativos específicos (no solo cualitativos)", "information_recall"),
    RubricCriterion("ir_03", "Distingue entre hechos establecidos y especulaciones", "information_recall"),
    RubricCriterion("ir_04", "Cubre los actores/estudios clave del dominio", "information_recall"),
    RubricCriterion("ir_05", "Identifica lagunas o incertidumbres en la evidencia", "information_recall"),
    RubricCriterion("ir_06", "Evita alucinaciones: claims verificables vs inventados", "information_recall"),
    RubricCriterion("ir_07", "Actualidad: fuentes recientes para temas en evolución rápida", "information_recall"),
    RubricCriterion("ir_08", "Diversidad de fuentes: múltiples perspectivas/estudios", "information_recall"),
    RubricCriterion("ir_09", "Cita correctamente: atribución precisa a fuente original", "information_recall"),
    RubricCriterion("ir_10", "Cobertura: aborda sub-preguntas implícitas en la pregunta", "information_recall"),
]


# --- RÚBRICA 2: ANALYSIS (Análisis y razonamiento) ---
ANALYSIS_RUBRIC: List[RubricCriterion] = [
    RubricCriterion("an_01", "Estructura el problema: descompone en componentes analizables", "analysis"),
    RubricCriterion("an_02", "Identifica relaciones causales, no solo correlaciones", "analysis"),
    RubricCriterion("an_03", "Evalúa calidad/credibilidad de la evidencia (no la toma al pie)", "analysis"),
    RubricCriterion("an_04", "Detecta y discute contradicciones en la literatura", "analysis"),
    RubricCriterion("an_05", "Realiza inferencias lógicas válidas desde la evidencia", "analysis"),
    RubricCriterion("an_06", "Cuantifica incertidumbre: rangos, probabilidades, escenarios", "analysis"),
    RubricCriterion("an_07", "Considera explicaciones alternativas / hipótesis rivales", "analysis"),
    RubricCriterion("an_08", "Identifica sesgos potenciales en fuentes o metodología", "analysis"),
    RubricCriterion("an_09", "Sintetiza: integra hallazgos en conclusiones coherentes", "analysis"),
    RubricCriterion("an_10", "Deriva implicaciones prácticas / recomendaciones accionables", "analysis"),
]


# --- RÚBRICA 3: PRESENTATION (Presentación y entrega) ---
PRESENTATION_RUBRIC: List[RubricCriterion] = [
    RubricCriterion("pr_01", "Estructura clara: introducción, cuerpo, conclusiones", "presentation"),
    RubricCriterion("pr_02", "Lenguaje preciso: terminología correcta del dominio", "presentation"),
    RubricCriterion("pr_03", "Visualizaciones úlidas: tablas, gráficos, comparativas", "presentation"),
    RubricCriterion("pr_04", "Nivel de detalle apropiado: ni superficial ni abrumador", "presentation"),
    RubricCriterion("pr_05", "Executive summary accionable para decisores", "presentation"),
    RubricCriterion("pr_06", "Citas trazables: cada claim vinculado a fuente", "presentation"),
    RubricCriterion("pr_07", "Limitaciones declaradas explícitamente", "presentation"),
    RubricCriterion("pr_08", "Formato consistente: headings, listas, énfasis", "presentation"),
    RubricCriterion("pr_09", "Conclusiones jerarquizadas: principal > secundarias", "presentation"),
    RubricCriterion("pr_10", "Reproducibilidad: metodología descrita para replicar", "presentation"),
]


ALL_RUBRICS = {
    "information_recall": INFORMATION_RECALL_RUBRIC,
    "analysis": ANALYSIS_RUBRIC,
    "presentation": PRESENTATION_RUBRIC,
}


def _heuristic_check(report: str, expected: Dict[str, List[str]], criterion: RubricCriterion) -> int:
    """Heurística simple: busca keywords esperadas en el reporte."""
    report_lower = report.lower()
    keywords = expected.get(criterion.dimension, [])
    
    if not keywords:
        # Criterios transversales: heurísticas generales
        if criterion.id == "ir_03":  # Hechos vs especulación
            return 1 if any(w in report_lower for w in ["según", "estudio", "investigación", "datos muestran", "evidencia sugiere"]) else 0
        if criterion.id == "ir_06":  # Anti-alucinación
            return 1 if not any(w in report_lower for w in ["seguramente", "definitivamente", "probablemente"]) else 0
        if criterion.id == "an_03":  # Evalúa calidad evidencia
            return 1 if any(w in report_lower for w in ["limitación", "sesgo", "muestra", "metodología", "calidad"]) else 0
        if criterion.id == "an_06":  # Cuantifica incertidumbre
            return 1 if any(w in report_lower for w in ["%", "por ciento", "rango", "intervalo", "probabilidad", "escenario"]) else 0
        if criterion.id == "pr_03":  # Visualizaciones
            return 1 if any(w in report_lower for w in ["tabla", "gráfico", "comparativa", "|", "---"]) else 0
        return 0
    
    # Buscar al menos 50% de keywords esperadas
    found = sum(1 for kw in keywords if kw.lower() in report_lower)
    return 1 if found >= max(1, len(keywords) // 2) else 0


# --- RÚBRICAS ESPECÍFICAS POR DOMINIO ---
# Extienden las rúbricas base con criterios específicos de cada dominio

# === CIENCIA Y TECNOLOGÍA ===
SCITECH_IR_EXTRA = [
    RubricCriterion("ir_scitech_01", "Cita papers/conferencias clave (Nature, Science, PRL, arXiv)", "information_recall"),
    RubricCriterion("ir_scitech_02", "Incluye métricas técnicas: eficiencia, Q-factor, temperatura, presión", "information_recall"),
    RubricCriterion("ir_scitech_03", "Menciona hitos experimentales recientes (últimos 2-3 años)", "information_recall"),
]

SCITECH_AN_EXTRA = [
    RubricCriterion("an_scitech_01", "Compara enfoques teóricos vs experimentales", "analysis"),
    RubricCriterion("an_scitech_02", "Identifica cuellos de botella de ingeniería (materiales, escalabilidad)", "analysis"),
    RubricCriterion("an_scitech_03", "Discute viabilidad económica/energética (LCOE, ganancia neta)", "analysis"),
]

SCITECH_PR_EXTRA = [
    RubricCriterion("pr_scitech_01", "Incluye tabla comparativa de enfoques/parámetros clave", "presentation"),
    RubricCriterion("pr_scitech_02", "Usa notación científica y unidades SI correctas", "presentation"),
]

# === MEDICINA Y SALUD ===
MED_IR_EXTRA = [
    RubricCriterion("ir_med_01", "Cita ensayos clínicos fase III / meta-análisis Cochrane", "information_recall"),
    RubricCriterion("ir_med_02", "Incluye números: NNT, HR, IC95%, p-value, tamaño muestra", "information_recall"),
    RubricCriterion("ir_med_03", "Menciona guías clínicas actuales (ESC, AHA, NICE, FDA/EMA)", "information_recall"),
]

MED_AN_EXTRA = [
    RubricCriterion("an_med_01", "Discute validez interna/externa de los ensayos", "analysis"),
    RubricCriterion("an_med_02", "Analiza subgrupos y heterogeneidad de efecto", "analysis"),
    RubricCriterion("an_med_03", "Evalúa balance beneficio-riesgo y costo-efectividad", "analysis"),
]

MED_PR_EXTRA = [
    RubricCriterion("pr_med_01", "Estructura PICO (Población, Intervención, Comparador, Outcome)", "presentation"),
    RubricCriterion("pr_med_02", "Tabla de evidencia: estudio, n, resultado primario, calidad", "presentation"),
]

# === ECONOMÍA Y POLÍTICA ===
ECON_IR_EXTRA = [
    RubricCriterion("ir_econ_01", "Cita datos FMI, OCDE, Banco Mundial, bancos centrales", "information_recall"),
    RubricCriterion("ir_econ_02", "Incluye series temporales, shocks, revisiones de datos", "information_recall"),
    RubricCriterion("ir_econ_03", "Menciona modelos estándar (DSGE, VAR, IO) y sus supuestos", "information_recall"),
]

ECON_AN_EXTRA = [
    RubricCriterion("an_econ_01", "Distingue correlación vs causalidad (IV, DiD, RCT, RD)", "analysis"),
    RubricCriterion("an_econ_02", "Analiza efectos distributivos (quintiles, Gini, pobreza)", "analysis"),
    RubricCriterion("an_econ_03", "Discute externalidades, efectos generales, segundo orden", "analysis"),
]

ECON_PR_EXTRA = [
    RubricCriterion("pr_econ_01", "Tabla de resultados: coeficientes, errores estándar, significancia", "presentation"),
    RubricCriterion("pr_econ_02", "Gráficos de series, impulso-respuesta, contrafactuales", "presentation"),
]

# === DERECHO Y POLÍTICA PÚBLICA ===
LAW_IR_EXTRA = [
    RubricCriterion("ir_law_01", "Cita artículos directivos, reglamentos, jurisprudencia TJUE/TS", "information_recall"),
    RubricCriterion("ir_law_02", "Menciona plazos transposición, entrada vigor, soft law", "information_recall"),
    RubricCriterion("ir_law_03", "Identifica autoridades competentes y mecanismos supervisión", "information_recall"),
]

LAW_AN_EXTRA = [
    RubricCriterion("an_law_01", "Aplica test proporcionalidad (idoneidad, necesidad, proporcionalidad estricta)", "analysis"),
    RubricCriterion("an_law_02", "Analiza competencias: principio subsidiariedad, margen apreciación", "analysis"),
    RubricCriterion("an_law_03", "Identifica lagunas, conflictos de normas, hard cases", "analysis"),
]

LAW_PR_EXTRA = [
    RubricCriterion("pr_law_01", "Estructura IRAC (Issue, Rule, Analysis, Conclusion)", "presentation"),
    RubricCriterion("pr_law_02", "Tabla comparativa jurisdicciones / opciones regulatorias", "presentation"),
]

# === MEDIO AMBIENTE Y CLIMA ===
CLIMATE_IR_EXTRA = [
    RubricCriterion("ir_clim_01", "Cita IPCC AR6, IEA, UNEP, Global Carbon Budget", "information_recall"),
    RubricCriterion("ir_clim_02", "Incluye GtCO2e, ppm, °C, TW, EJ, $/tCO2 — unidades correctas", "information_recall"),
    RubricCriterion("ir_clim_03", "Distingue mitigación / adaptación / pérdidas y daños", "information_recall"),
]

CLIMATE_AN_EXTRA = [
    RubricCriterion("an_clim_01", "Analiza pathways: SSP-RCP, overshoot, net-zero timing", "analysis"),
    RubricCriterion("an_clim_02", "Cuantifica brecha: NDCs vs 1.5°C/2°C, implementation gap", "analysis"),
    RubricCriterion("an_clim_03", "Evalúa justice: responsabilidad histórica, finanzas, L&D", "analysis"),
]

CLIMATE_PR_EXTRA = [
    RubricCriterion("pr_clim_01", "Gráfico de pathways / wedge diagram / carbon budget", "presentation"),
    RubricCriterion("pr_clim_02", "Tabla hitos: 2030, 2040, 2050 con indicadores cuantitativos", "presentation"),
]

# Mapeo dominio -> rúbricas extra
DOMAIN_RUBRICS_EXTRA = {
    "science_tech": {
        "information_recall": SCITECH_IR_EXTRA,
        "analysis": SCITECH_AN_EXTRA,
        "presentation": SCITECH_PR_EXTRA,
    },
    "medicine": {
        "information_recall": MED_IR_EXTRA,
        "analysis": MED_AN_EXTRA,
        "presentation": MED_PR_EXTRA,
    },
    "economics": {
        "information_recall": ECON_IR_EXTRA,
        "analysis": ECON_AN_EXTRA,
        "presentation": ECON_PR_EXTRA,
    },
    "law_policy": {
        "information_recall": LAW_IR_EXTRA,
        "analysis": LAW_AN_EXTRA,
        "presentation": LAW_PR_EXTRA,
    },
    "climate": {
        "information_recall": CLIMATE_IR_EXTRA,
        "analysis": CLIMATE_AN_EXTRA,
        "presentation": CLIMATE_PR_EXTRA,
    },
}


def get_rubrics_for_domain(domain: str) -> Dict[str, List[RubricCriterion]]:
    """
    Retorna rúbricas combinadas: base + específicas del dominio.
    
    Args:
        domain: "science_tech" | "medicine" | "economics" | "law_policy" | "climate"
        
    Returns:
        Dict con claves "information_recall", "analysis", "presentation"
    """
    base = {
        "information_recall": list(INFORMATION_RECALL_RUBRIC),
        "analysis": list(ANALYSIS_RUBRIC),
        "presentation": list(PRESENTATION_RUBRIC),
    }
    
    if domain in DOMAIN_RUBRICS_EXTRA:
        extra = DOMAIN_RUBRICS_EXTRA[domain]
        for dim in base:
            if dim in extra:
                base[dim].extend(extra[dim])
    
    return base


def evaluate_dimension(
    report: str,
    task_expected: Dict[str, List[str]],
    dimension: str,
    llm_judge=None,
    domain: str = None
) -> Dict[str, Any]:
    """
    Evalúa una dimensión usando rúbrica binaria (base + dominio).
    
    Args:
        report: Informe generado por el sistema
        task_expected: expected_elements de la tarea para esta dimensión
        dimension: "information_recall" | "analysis" | "presentation"
        llm_judge: Callable opcional para LLM-as-judge (prompt -> Sí/No)
        domain: Dominio de la tarea para rúbricas específicas
     
    Returns:
        Dict con score, detalles por criterio, y metadatos
    """
    # Usar rúbricas específicas del dominio si se proporciona
    if domain:
        rubrics = get_rubrics_for_domain(domain)
        rubric = rubrics.get(dimension, [])
    else:
        rubric = ALL_RUBRICS.get(dimension, [])
    
    results = {}
    
    for criterion in rubric:
        # Heurística simple basada en palabras clave esperadas
        # En producción, usar LLM-as-judge con prompt calibrado
        score = _heuristic_check(report, task_expected, criterion)
        results[criterion.id] = {
            "criterion": criterion.description,
            "score": score,
            "weight": criterion.weight,
        }
    
    # Score ponderado
    total_weight = sum(r.weight for r in rubric)
    weighted_score = sum(r["score"] * r["weight"] for r in results.values()) / total_weight if total_weight > 0 else 0
    
    passed = sum(1 for r in results.values() if r["score"] == 1)
    total = len(results)
    
    return {
        "dimension": dimension,
        "score": round(weighted_score, 3),
        "passed": passed,
        "total": total,
        "pass_rate": round(passed / total, 3) if total > 0 else 0,
        "details": results,
    }


def evaluate_all_dimensions(report: str, task_expected: Dict[str, List[str]], llm_judge=None, domain: str = None) -> Dict[str, Any]:
    """Evalúa las tres dimensiones y retorna score agregado."""
    results = {}
    for dim in ["information_recall", "analysis", "presentation"]:
        results[dim] = evaluate_dimension(report, task_expected, dim, llm_judge, domain)
    
    # Score general: media ponderada (Analysis pesa más estilo DeepResearch Bench)
    weights = {"information_recall": 0.3, "analysis": 0.4, "presentation": 0.3}
    overall = sum(results[dim]["score"] * weights[dim] for dim in weights)
    
    return {
        "dimensions": results,
        "overall_score": round(overall, 3),
        "weights": weights,
    }