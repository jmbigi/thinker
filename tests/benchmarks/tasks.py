"""Tareas de benchmark para Deep Research (20 tareas: 5 dominios × 4 complejidad).

Basado en DeepResearch Bench (ICLR 2026): 100 tareas PhD-level, 22 dominios.
Aquí versión reducida pero representativa para validación continua.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class BenchmarkTask:
    """Tarea de benchmark individual."""
    id: str
    domain: str
    complexity: str  # "simple", "moderate", "complex", "expert"
    question: str
    expected_elements: Dict[str, List[str]]  # Claves por dimensión de evaluación
    metadata: Dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


# --- 20 Tareas: 5 dominios × 4 niveles de complejidad ---

BENCHMARK_TASKS: List[BenchmarkTask] = [
    # === DOMINIO: CIENCIA Y TECNOLOGÍA ===
    BenchmarkTask(
        id="scitech_simple_01",
        domain="science_tech",
        complexity="simple",
        question="¿Cuál es el principio de funcionamiento de una pila de combustible de hidrógeno?",
        expected_elements={
            "information_recall": ["hidrógeno", "oxígeno", "electrolito", "electricidad", "agua"],
            "analysis": ["reacción electroquímica", "ánodo", "cátodo", "eficiencia"],
            "presentation": ["principio", "componentes", "productos", "aplicaciones"],
        },
        metadata={"difficulty": "undergraduate", "expected_sources": 3}
    ),
    BenchmarkTask(
        id="scitech_moderate_02",
        domain="science_tech",
        complexity="moderate",
        question="¿Cuáles son los principales desafíos técnicos para la fusión nuclear comercial y su cronograma realista?",
        expected_elements={
            "information_recall": ["ITER", "tokamak", "confinamiento magnético", "ganancia neta", "materiales"],
            "analysis": ["confinamiento", "inestabilidades", "materiales resistentes", "tritio", "cronograma"],
            "presentation": ["estado actual", "desafíos", "hititos", "perspectivas 2030-2040"],
        },
        metadata={"difficulty": "graduate", "expected_sources": 5}
    ),
    BenchmarkTask(
        id="scitech_complex_03",
        domain="science_tech",
        complexity="complex",
        question="Compara los enfoques de fusión por confinamiento magnético (tokamak/stellarator) vs confinamiento inercial (láser) en viabilidad comercial.",
        expected_elements={
            "information_recall": ["tokamak", "stellarator", "NIF", "ignición", "Q>1", "repetición"],
            "analysis": ["ventajas/desventajas", "escalabilidad", "costo", "complejidad ingeniería", "cronograma"],
            "presentation": ["comparativa tabla", "veredicto fundamentado", "recomendación"],
        },
        metadata={"difficulty": "expert", "expected_sources": 8}
    ),
    BenchmarkTask(
        id="scitech_expert_04",
        domain="science_tech",
        complexity="expert",
        question="Analiza el impacto de los superconductores de alta temperatura (REBCO) en la viabilidad económica de reactores de fusión compactos (ARCF, SPARC).",
        expected_elements={
            "information_recall": ["REBCO", "SPARC", "CFETR", "campo magnético >20T", "costo por kW"],
            "analysis": ["reducción tamaño", "costo capital", "cadena suministro", "madurez tecnología", "competitividad LCOE"],
            "presentation": ["modelo económico", "sensibilidad", "riesgos", "conclusión inversión"],
        },
        metadata={"difficulty": "research", "expected_sources": 10}
    ),

    # === DOMINIO: MEDICINA Y SALUD ===
    BenchmarkTask(
        id="med_simple_01",
        domain="medicine",
        complexity="simple",
        question="¿Qué es la inmunoterapia CAR-T y para qué cánceres está aprobada?",
        expected_elements={
            "information_recall": ["células T", "receptor quimérico", "antígeno", "leucemia", "linfoma"],
            "analysis": ["mecanismo", "proceso fabricación", "efectos adversos", "indicaciones aprobadas"],
            "presentation": ["definición", "mecanismo", "indicaciones", "limitaciones"],
        },
        metadata={"difficulty": "undergraduate", "expected_sources": 3}
    ),
    BenchmarkTask(
        id="med_moderate_02",
        domain="medicine",
        complexity="moderate",
        question="Evalúa la evidencia actual sobre eficacia y seguridad de los inhibidores de PCSK9 en prevención cardiovascular secundaria.",
        expected_elements={
            "information_recall": ["PCSK9", "evolocumab", "alirocumab", "FOURIER", "ODYSSEY", "LDL-C"],
            "analysis": ["reducción eventos", "seguridad", "costo-efectividad", "comparativa estatinas", "poblaciones especiales"],
            "presentation": ["evidencia ensayos", "guías actuales", "posicionamiento terapia"],
        },
        metadata={"difficulty": "graduate", "expected_sources": 6}
    ),
    BenchmarkTask(
        id="med_complex_03",
        domain="medicine",
        complexity="complex",
        question="Compara estrategias de screening de cáncer colorrectal: colonoscopía vs test FIT vs sangre oculta vs colonografía TC.",
        expected_elements={
            "information_recall": ["sensibilidad", "especificidad", "intervalo", "adherencia", "costo", "complicaciones"],
            "analysis": ["balance beneficio-riesgo", "costo-efectividad", "equidad acceso", "preferencias paciente"],
            "presentation": ["tabla comparativa", "recomendación por perfil riesgo", "gaps evidencia"],
        },
        metadata={"difficulty": "expert", "expected_sources": 8}
    ),
    BenchmarkTask(
        id="med_expert_04",
        domain="medicine",
        complexity="expert",
        question="Analiza el potencial de la edición genética CRISPR-Cas9 in vivo para enfermedades monogénicas: estado actual, barreras entrega, seguridad off-target.",
        expected_elements={
            "information_recall": ["CRISPR", "Cas9", "entrega AAV", "LNP", "off-target", "inmunogenicidad", "ensayos clínicos"],
            "analysis": ["eficiencia edición", "barreras entrega tejido", "riesgos genotóxicos", "estrategias mitigación", "vias regulatorias"],
            "presentation": ["estado arte", "pipeline desarrollo", "riesgos críticos", "pronóstico 5-10 años"],
        },
        metadata={"difficulty": "research", "expected_sources": 10}
    ),

    # === DOMINIO: ECONOMÍA Y POLÍTICA ===
    BenchmarkTask(
        id="econ_simple_01",
        domain="economics",
        complexity="simple",
        question="¿Qué es la inflación subyacente y por qué los bancos centrales la usan para decisiones de política monetaria?",
        expected_elements={
            "information_recall": ["IPC", "componentes volátiles", "alimentos", "energía", "política monetaria"],
            "analysis": ["señal vs ruido", "persistencia", "expectativas", "transmisión política"],
            "presentation": ["definición", "cálculo", "uso bancos centrales", "limitaciones"],
        },
        metadata={"difficulty": "undergraduate", "expected_sources": 3}
    ),
    BenchmarkTask(
        id="econ_moderate_02",
        domain="economics",
        complexity="moderate",
        question="Analiza el impacto de la IA generativa en productividad laboral: evidencia empírica actual vs proyecciones teóricas.",
        expected_elements={
            "information_recall": ["productividad", "trabajo conocimiento", "automatización", "complementariedad", "estudios NBER"],
            "analysis": ["efecto sustitución vs complemento", "heterogeneidad sectores", "brecha adopción", "medición productividad"],
            "presentation": ["evidencia micro/macro", "incertidumbres", "escenarios", "implicaciones política"],
        },
        metadata={"difficulty": "graduate", "expected_sources": 6}
    ),
    BenchmarkTask(
        id="econ_complex_03",
        domain="economics",
        complexity="complex",
        question="Evalúa la efectividad de los paquetes de estímulo verde post-COVID en UE, EE. UU. y China: asignación, adicionalidad, impacto climático.",
        expected_elements={
            "information_recall": ["NextGenerationEU", "IRA", "dual carbon goals", "taxonomía verde", "adicionalidad"],
            "analysis": ["efectividad asignación", "fugas carbono", "coherencia política", "medición impacto", "lecciones"],
            "presentation": ["comparativa jurisdicciones", "métricas efectividad", "recomendaciones diseño"],
        },
        metadata={"difficulty": "expert", "expected_sources": 8}
    ),
    BenchmarkTask(
        id="econ_expert_04",
        domain="economics",
        complexity="expert",
        question="Modela las implicaciones macroeconómicas de la transición a cero neto 2050: inversión requerida, efectos distribución, riesgo stranded assets.",
        expected_elements={
            "information_recall": ["IEA NZE2050", "inversión anual", "stranded assets", "transición justa", "carbon pricing"],
            "analysis": ["necesidades inversión", "impacto sectorial", "distribución ingreso", "riesgo financiero", "políticas complementarias"],
            "presentation": ["modelo macro", "escenarios", "sensibilidad", "recomendaciones política"],
        },
        metadata={"difficulty": "research", "expected_sources": 10}
    ),

    # === DOMINIO: DERECHO Y POLÍTICA PÚBLICA ===
    BenchmarkTask(
        id="law_simple_01",
        domain="law_policy",
        complexity="simple",
        question="¿Qué es el RGPD (GDPR) y cuáles son los derechos principales que otorga a los interesados?",
        expected_elements={
            "information_recall": ["datos personales", "consentimiento", "derecho acceso", "rectificación", "supresión", "portabilidad"],
            "analysis": ["ámbito territorial", "responsable/encargado", "medidas técnicas", "sanciones"],
            "presentation": ["principios", "derechos", "obligaciones", "sanciones"],
        },
        metadata={"difficulty": "undergraduate", "expected_sources": 3}
    ),
    BenchmarkTask(
        id="law_moderate_02",
        domain="law_policy",
        complexity="moderate",
        question="Analiza el marco regulatorio emergente para IA en la UE (AI Act): clasificación de riesgo, obligaciones high-risk, gobernanza.",
        expected_elements={
            "information_recall": ["AI Act", "riesgo inaceptable", "alto riesgo", "riesgo limitado", "mínimo", "GPAI"],
            "analysis": ["clasificación", "requisitos high-risk", "evaluación conformidad", "sandbox", "coherencia GDPR"],
            "presentation": ["pirámide riesgo", "obligaciones clave", "cronograma", "impacto innovación"],
        },
        metadata={"difficulty": "graduate", "expected_sources": 5}
    ),
    BenchmarkTask(
        id="law_complex_03",
        domain="law_policy",
        complexity="complex",
        question="Compara enfoques regulatorios de IA: UE (AI Act) vs EE. UU. (orden ejecutiva, NIST) vs Reino Unido (pro-innovación) vs China (algoritmos).",
        expected_elements={
            "information_recall": ["AI Act", "EO 14110", "NIST AI RMF", "UK white paper", "reglamento algoritmos China"],
            "analysis": ["filosofía reguladora", "alcance extraterritorial", "flexibilidad", "ejecución", "interoperabilidad"],
            "presentation": ["tabla comparativa", "convergencias/divergencias", "impacto empresas globales"],
        },
        metadata={"difficulty": "expert", "expected_sources": 8}
    ),
    BenchmarkTask(
        id="law_expert_04",
        domain="law_policy",
        complexity="expert",
        question="Analiza los desafíos jurídicos de la atribución de responsabilidad por daños de sistemas IA autónomos: producto, servicio, agencia.",
        expected_elements={
            "information_recall": ["responsabilidad civil", "defecto producto", "deber vigilancia", "caja negra", "agencia artificial"],
            "analysis": ["lagunas legales", "propuestas directiva UE", "seguro obligatorio", "reversión carga prueba", "jurisprudencia emergente"],
            "presentation": ["marco teórico", "comparativa jurisdicciones", "propuesta regulatoria", "implicaciones industria"],
        },
        metadata={"difficulty": "research", "expected_sources": 10}
    ),

    # === DOMINIO: MEDIO AMBIENTE Y CLIMA ===
    BenchmarkTask(
        id="climate_simple_01",
        domain="climate",
        complexity="simple",
        question="¿Qué son los sumideros de carbono naturales y cuál es su papel en la mitigación del cambio climático?",
        expected_elements={
            "information_recall": ["bosques", "océanos", "suelos", "fotosíntesis", "secuestro", "GtCO2/año"],
            "analysis": ["capacidad actual", "vulnerabilidad clima", "saturación", "restauración"],
            "presentation": ["tipos", "capacidad", "amenazas", "gestión sostenible"],
        },
        metadata={"difficulty": "undergraduate", "expected_sources": 3}
    ),
    BenchmarkTask(
        id="climate_moderate_02",
        domain="climate",
        complexity="moderate",
        question="Evalúa el potencial y limitaciones de la captura directa de aire (DACCS) como tecnología de emisiones negativas.",
        expected_elements={
            "information_recall": ["DACCS", "Climeworks", "Carbon Engineering", "energía requerida", "costo tonelada", "escalabilidad"],
            "analysis": ["balance energético", "costo actual vs objetivo", "almacenamiento", "competencia uso suelo", "papel cartera mitigación"],
            "presentation": ["tecnologías", "curva aprendizaje", "barreras despliegue", "políticas necesarias"],
        },
        metadata={"difficulty": "graduate", "expected_sources": 5}
    ),
    BenchmarkTask(
        id="climate_complex_03",
        domain="climate",
        complexity="complex",
        question="Analiza la viabilidad de los objetivos de triple renovables / duplicar eficiencia 2030 (COP28): requerimientos inversión, cadena suministro, permisos.",
        expected_elements={
            "information_recall": ["COP28", "triple renovables", "eficiencia energética", "IEA", "inversión redes", "permisología"],
            "analysis": ["cuello botella cadena suministro", "minerales críticos", "redes/almacenamiento", "marco regulatorio", "financiación"],
            "presentation": ["brecha actual", "cuellos botella", "paquete políticas", "probabilidad cumplimiento"],
        },
        metadata={"difficulty": "expert", "expected_sources": 8}
    ),
    BenchmarkTask(
        id="climate_expert_04",
        domain="climate",
        complexity="expert",
        question="Modela la interacción entre mitigación, adaptación y pérdidas/daños en escenarios de overshoot 1.5°C: umbrales irreversibles, justicia climática, gobernanza.",
        expected_elements={
            "information_recall": ["overshoot", "puntos inflexión", "pérdidas daños", "fondo L&D", "justicia climática", "gobernanza solar"],
            "analysis": ["riesgos irreversibles", "asimetrías regionales", "financiación adaptación", "marco legal L&D", "geoingeniería gobernanza"],
            "presentation": ["escenarios overshoot", "umbrales críticos", "arquitectura financiera", "recomendaciones gobernanza"],
        },
        metadata={"difficulty": "research", "expected_sources": 10}
    ),
]


def get_task(task_id: str) -> Optional[BenchmarkTask]:
    """Obtiene una tarea por ID."""
    for task in BENCHMARK_TASKS:
        if task.id == task_id:
            return task
    return None


def list_tasks(domain: str = None, complexity: str = None) -> List[BenchmarkTask]:
    """Lista tareas filtradas por dominio y/o complejidad."""
    tasks = BENCHMARK_TASKS
    if domain:
        tasks = [t for t in tasks if t.domain == domain]
    if complexity:
        tasks = [t for t in tasks if t.complexity == complexity]
    return tasks


def get_domains() -> List[str]:
    return sorted(set(t.domain for t in BENCHMARK_TASKS))


def get_complexities() -> List[str]:
    return ["simple", "moderate", "complex", "expert"]