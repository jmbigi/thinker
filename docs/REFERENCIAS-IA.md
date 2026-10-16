# Estudio de teoría y práctica de IA aplicada a thinker

**Fecha de verificación:** 2026-10-16. **Método:** cada referencia de arXiv se
comprobó contra la API oficial (`export.arxiv.org`, título/año/autores reales) y
cada guía de ingeniería con una petición HTTP real (código 200 y contenido). No
hay citas de memoria: una de las candidatas resultó ser OTRO paper (el id
`2308.02490` es *MM-Vet*, no GPTCache) y se descartó.

**Cómo usar este documento:** cada fila propone un cambio concreto, su
referencia y **cómo medirlo aquí**. Nada se da por bueno sin medirlo con el
framework propio (`python3 -m tests.benchmarks.run_bench`) y la suite; los
papers validan en *sus* entornos, no en este.

## 1. Teoría (referencias verificadas)

| Referencia | Idea central | Estado en thinker |
|---|---|---|
| **ReAct** — arXiv:2210.03629 (2022), Yao et al. | Intercalar razonamiento y acciones con observación real. | Parcial: `DecisionEngine` alterna decidir/actuar, pero **sin bucle de observación** (cada etapa corre una vez). |
| **Self-RAG** — arXiv:2310.11511 (2023), Asai et al. | El modelo decide *si* recuperar y critica lo generado. | Parcial: hay `ClaimExtractor` + `EvidenceEvaluator`, pero **no se decide recuperar más** ni se itera con la crítica. |
| **CRAG** — arXiv:2401.15884 (2024), Yan et al. | Evaluador ligero de la recuperación + acciones correctivas (refinar, buscar, descartar). | Casi: `SourceRetriever` ya reintenta consultas con anclas (`deep_research_system.py`), pero **sin evaluar la calidad** de lo recuperado ni descartar fuentes malas. |
| **Reflexion** — arXiv:2303.11366 (2023), Shinn et al. | Memoria verbal de fallos para corregir el siguiente intento. | Falta: `decision_log` registra, pero **no alimenta** la siguiente iteración. |
| **CoVe** — arXiv:2309.11495 (2023), Dhuliawala et al. | Verificar cada claim con preguntas de verificación **independientes**. | Falta: `EvidenceEvaluator` evalúa el claim contra los *mismos* snippets que lo originaron → **circularidad** (riesgo de confirmar el sesgo de la fuente). |
| **Lost in the Middle** — arXiv:2307.03172 (2023), Liu et al. | La información del medio del contexto se aprovecha peor que la de los extremos. | Relevante: `ReportGenerator` construye un prompt largo (subpreguntas + contadores); los snippets se truncan (`[:500]`, `[:200]`) sin criterio de posición. |
| **LLM-as-a-Judge** — arXiv:2306.05685 (2023), Zheng et al. | Sesgos medidos: posición, verbosidad y **autopreferencia** (el modelo prefiere su propia salida). | Ya en uso (ToT y benchmark). El proyecto declara el sesgo de autopreferencia como límite (Hallazgo 46): el juez es el mismo modelo evaluado. |
| **RAGAS** — arXiv:2309.15217 (2023), Es et al. | Métricas automáticas para RAG: fidelidad a las fuentes y relevancia de la respuesta. | Parcial: el benchmark mide IR/AN/PR con rúbricas propias; **no mide fidelidad** (¿el informe dice lo que dicen las fuentes?). |
| **DSPy** — arXiv:2310.03714 (2023), Khattab et al. | Compilar/optimizar prompts como un programa, con métricas. | Falta: los prompts están fijos en el código (mezcla ES/EN). Optimizarlos con el benchmark propio es la vía natural, sin cambiar de arquitectura. |
| **Chain-of-Thought** — arXiv:2201.11903 (2022), Wei et al. | Razonamiento paso a paso mejora tareas complejas. | **Implementado**: `thinking_engine.StepThinkingEngine` (7 pasos validados) es exactamente esto. |
| **Self-Consistency** — arXiv:2203.11171 (2022), Wang et al. | Muestrear varias cadenas y **votar** en vez de quedarse con una. | Parcial: `ToTEngine` ramifica (beam/BFS/DFS) pero elige la mejor hoja **por score**, sin votar entre las top-k. |

## 2. Práctica (guías de ingeniería verificadas)

- **Anthropic, *Building effective agents* (2024-12-19)** — verificado HTTP 200:
  <https://www.anthropic.com/engineering/building-effective-agents>. Tesis:
  «las implementaciones con más éxito usan patrones simples y componibles en vez
  de frameworks complejos». Patrones: *prompt chaining*, *routing*,
  *parallelization*, *orchestrator-workers*, *evaluator-optimizer*.
  - thinker **ya tiene**: *orchestrator-workers* (orquestador + subpreguntas) y
    *evaluator-optimizer* (extracción y evaluación de claims).
  - thinker **no tiene**: *routing* (elegir modelo por tarea) ni
    *parallelization* (búsquedas y evaluaciones en paralelo).
- **Anthropic, *Effective context engineering for AI agents* (2025-09-29)** —
  verificado HTTP 200:
  <https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents>.
  Tesis: el contexto es un recurso **finito**; se gestiona con compactación,
  notas estructuradas, subagentes y recuperación *just-in-time* (traer lo
  necesario cuando se necesita, no todo por adelantado).
  - thinker **asume ese coste** con truncados fijos; no hay compactación
    explícita ni recuperación dirigida por claim (just-in-time).

## 3. Propuestas priorizadas

Cada propuesta indica **qué**, **dónde**, **por qué** y **cómo se mide**.

### Eficiencia

1. **Caché de respuestas LLM (por hash de prompt+modelo).**
   Dónde: `llm_providers._chat_completion`. Por qué: el pipeline repite prompts
   idénticos entre reintentos/campañas y agota el cupo del tier gratuito, que es
   el cuello de botella **medido hoy** (Hallazgo 57). Medir: número de llamadas
   reales por campaña de benchmark antes/después.
2. **Timeout explícito y configurable.**
   Dónde: `_chat_completion` (el SDK usa 600 s por defecto y hoy no se puede
   ajustar; la sonda tuvo que usar el SDK directo). Medir: una llamada colgada
   no debe superar el timeout fijado.
3. **Paralelizar la recuperación y la evaluación.**
   Dónde: `ResearchOrchestrator.research` (hoy secuencial). Por qué: son
   llamadas independientes (patrón *parallelization*). Medir: tiempo de la
   campaña con el mismo n y mismas tareas.

### Inteligencia

4. **Verificador de recuperación tipo CRAG.**
   Dónde: `SourceRetriever` + un evaluador ligero. Medir: `information_recall`
   del benchmark en los 5 dominios (hoy 0,20-0,54 según campaña).
5. **Verificación independiente de claims (CoVe).**
   Dónde: `EvidenceEvaluator` (hoy evalúa contra los snippets de origen).
   Medir: proporción de claims `supported` que sobreviven a una verificación
   independiente, y no conformes por dominio.
6. **Voto entre las top-k hojas del ToT (Self-Consistency).**
   Dónde: `thinking_engine.ToTEngine.think_tot`. Medir: `best_score` y calidad
   del informe en el benchmark (modo `--tot`).
7. **Routing por tarea: modelo rápido para descomponer/extraer, modelo mayor
   para el informe.**
   Dónde: `ResearchOrchestrator` (los pasos ya están separados). Medir: coste 0
   con `:free`; comparar latencia total y puntuación por dominio.
8. **Optimizar los prompts con el benchmark propio (DSPy o búsqueda manual).**
   Dónde: prompts de `deep_research_system.py` y `pensamiento_layer.py`.
   Medir: la rúbrica del benchmark como función objetivo.

### Medición

9. **Añadir métricas de fidelidad a las fuentes (RAGAS-like).**
   Dónde: `tests/benchmarks/rubrics.py`. Por qué: hoy se premia recordar datos,
   no que el informe **no invente** respecto a las fuentes citadas.

### Estado de las propuestas (2026-10-16)

- ✅ **1** (caché de respuestas) y **2** (timeout explícito): implementadas en
  `_chat_completion`/`OpenAILLM`; ahorro medido en ToT 2×2: 52 llamadas, solo 21
  únicas (**60% eliminable**).
- ✅ **4** (verificación independiente tipo CoVe): segunda pasada opt-in en
  `EvidenceEvaluator` (`verificacion_independiente=True`), que evalúa el claim
  contra las fuentes que NO lo originaron y marca `contested`; sin fuentes
  alternativas registra `skip` y **no inventa** la verificación.
- ✅ **9** (fidelidad a las fuentes): `rubrics.evaluar_fidelidad` mide qué cifras
  del informe están respaldadas por las fuentes y queda en el JSON de cada tarea
  del benchmark (campo `evaluation.fidelidad`).
- Pendientes: **3** (paralelización), **5** (evaluador de recuperación tipo
  CRAG), **6** (voto entre las top-k hojas del ToT), **7** (routing por tarea),
  **8** (optimizar prompts con el benchmark).

## 4. Límites y responsabilidad

- Los papers validan en sus propios entornos y modelos; aquí **solo cuenta la
  medición local** con `tests/benchmarks` (5 dominios, rúbricas propias).
- Las campañas reales consumen cupo del tier gratuito (429 documentado): medir
  por tandas y con `n` declarado, no extrapolar de una sola campaña
  (Hallazgo 46).
- No añadir dependencias sin declararlas (P0.18) ni complejidad sin medición:
  la regla propia 1 exige eficiencia **e** inteligencia, valor medido y no
  volumen.
- El sesgo de autopreferencia del juez (mismo modelo evaluado) es un límite
  declarado, no resuelto: cualquier mejora medida con ese juez hereda el sesgo.
