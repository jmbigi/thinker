# Lecciones Aprendidas

Regla **P1.20** del `AGENTS.md`: cada prueba/fallo/hallazgo se documenta aquí
con fecha, problema, solución y evidencia. Anonimizado (P0.9).

---

## 2026-10-14 — Reparación integral del proyecto

### Hallazgo 1: Verificación engañosa con `&&` tras pipe
- **Problema**: `python3 -m py_compile f.py 2>&1 | head -3 && echo OK` imprime
  "OK" aunque la compilación falle, porque `&&` evalúa el exit de `head`, no el
  de `py_compile`. Resultado: 6 archivos rotos parecían sanos.
- **Solución**: capturar el exit code del comando real
  (`if python3 -m py_compile "$f"; then ...`) sin pipes intermedios.
- **Evidencia**: ejecución del 2026-10-14 — 6 archivos con SYNTAX_ERROR
  detectados al separar la verificación.
- **Regla derivada**: toda verificación con pipes debe comprobar el exit code
  del comando relevante, no el del último comando del pipe (refuerza P0.1).

### Hallazgo 2: Errores de sintaxis ocultan errores de sintaxis posteriores
- **Problema**: `deep_research_system.py` tenía un f-string roto en la línea
  129 que impedía compilar; al corregirlo apareció un segundo f-string con
  llaves sin escapar en `EvidenceEvaluator` (línea ~174). Un archivo que "no
  compila" puede esconder varios errores más.
- **Solución**: tras cada corrección de sintaxis, recompilar Y ejecutar el
  módulo para sacar a la luz errores latentes (P1.11: verde antes de seguir).

### Hallazgo 3: Artefactos de shell pegados en archivos Python
- **Problema**: `honest_test.py` terminaba con `" > test_results.txt 2>&1` y
  `test_systems_honest.py` con `PYEOF`: restos de heredocs/redirecciones de
  shell copiados dentro del código. `test_import.py` era directamente un
  volcado de texto con extensión `.py`.
- **Solución**: reescribir los archivos limpios; eliminar el que no era código.
- **Regla derivada**: al generar archivos desde shell (heredoc), verificar
  siempre la última línea del archivo resultante.

### Hallazgo 4: SDK openai>=1.0 incompatible con la API antigua
- **Problema**: `OpenAILLM`/`KiloGatewayLLM` usaban `openai.ChatCompletion.create`
  y `openai.api_base`, eliminados en openai 1.x (instalado: 1.109.1). Toda
  llamada real habría fallado aunque el código compilase.
- **Solución**: migrar al cliente moderno
  (`from openai import OpenAI; OpenAI(api_key=..., base_url=...)`), verificado
  contra la versión instalada (P1.7: doc/entorno real > memoria).

### Hallazgo 5: Tests "deshonestos" que declaran éxitos pre-escritos
- **Problema**: varios tests imprimían resúmenes de éxito redactados de
  antemano, llamaban funciones con firmas incorrectas
  (`analyze_python_code(código)` en vez de una ruta) y un test escribía 20
  caracteres de la API key a un archivo de texto.
- **Solución**: tests reescritos con asserts reales, resumen construido a
  partir de resultados, código de salida 0/1, y sin escribir secretos (P0.6,
  P1.1, P1.26).
- **Regla derivada**: un test sin asserts que puedan fallar y sin exit code
  no es un test (refuerza P1.1).

### Hallazgo 6: Estado del proyecto contradictorio en JSONs sueltos
- **Problema**: 5 archivos JSON de estado (`task_status.json`, `verify.json`,
  etc.) con rutas de otro SO y estados "in_progress/pending" obsoletos que
  contradecían la realidad.
- **Solución**: eliminados (con verificación previa de destino, P1.28). En
  aquel momento el estado real lo generaba `verify_install.py` bajo demanda en
  `install_check.json`; ese script se eliminó el 2026-10-20 y hoy el estado se
  verifica con la suite de tests y los comandos de `AGENTS.md`.

---

## 2026-10-14 (ronda 2) — Revisión y comprobación exhaustiva

### Hallazgo 7: Editar docs numerados exige releer el resultado
- **Problema**: al insertar la regla 8 ("Comprobaciones obligatorias") en
  `AGENTS.md` quedaron dos reglas numeradas "8". Lo detectó la relectura
  posterior, no la escritura.
- **Solución**: renumerar a 9 la regla de secretos. Lección: tras editar
  listas numeradas, releer la sección completa (P0.1 aplicado a documentos).

### Hallazgo 8: Lint con ruff — 31 problemas que las pruebas no veían
- **Problema**: `ruff check` encontró 31 incidencias en código que ya
  compilaba y pasaba tests: f-strings sin placeholders (F541), imports sin
  usar (F401), imports fuera de cabecera (E402), variable asignada sin uso
  (F841). Compilar y pasar tests NO equivale a código limpio.
- **Solución**: corrección manual de los imports que eran el propio test
  (referenciándolos con asserts, no borrándolos con `--fix`), sondas de
  disponibilidad con `importlib.util.find_spec` en vez de `import` + `except
  ImportError: pass` (más limpio y sin F401), y autofix para los F541.
  Resultado verificado: `ruff check` → 0 errores.
- **Regla derivada**: `ruff check` pasa a formar parte de la comprobación
  obligatoria (regla propia 8) junto a py_compile y los tests.

### Hallazgo 9: Cobertura incompleta de tests
- **Problema**: ningún test ejercitaba `ResearchOrchestratorWithThinking`
  ni los casos límite del análisis estático (sintaxis rota, archivo
  inexistente, fuente vacía, LLM que devuelve JSON inválido).
- **Solución**: comprobados con un script de verificación ad-hoc: todos
  pasan; el pipeline tolera JSON inválido del LLM registrando la decisión
  "fail" en el log (comportamiento diseñado, no error silencioso).

---

## 2026-10-14 (ronda 3) — OpenRouter con modelos gratuitos

### Hallazgo 10: Los IDs de modelo caducan: verificar contra la API, no la memoria
- **Problema**: los IDs de modelos gratuitos que "recordaba"
  (`meta-llama/...:free`, `deepseek/...:free`) ya no aparecían en el catálogo.
- **Solución**: consultar `https://openrouter.ai/api/v1/models` (público, sin
  key) y filtrar `:free`. De 462 modelos, 14 gratuitos. Probados con llamadas
  reales: funcionan `nvidia/nemotron-3-super-120b-a12b:free` (2.3 s),
  `nvidia/nemotron-3-ultra-550b-a55b:free`, `dots-studio/dots-3-note-preview:free`,
  `cohere/north-mini-code:free`, `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`.
  Descartados: `thinkingmachines/inkling:free` (403: solo agentic harnesses),
  `google/gemma-4-*:free` y `poolside/*:free` (429 rate-limit), y varios que
  devolvían contenido vacío con presupuesto bajo (modelos de razonamiento).
- **Regla derivada**: nunca fijar un ID de modelo de memoria (P0.2); verificar
  con la API del proveedor.

### Hallazgo 11: `load_dotenv()` sin ruta falla cuando no hay archivo de script
- **Problema**: `load_dotenv()` usa `find_dotenv()`, que introspecciona el frame
  actual; ejecutado desde stdin/heredoc lanza `AssertionError`.
- **Solución**: usar siempre `load_dotenv(".env")` con ruta explícita.

### Hallazgo 12: Los modelos reales no devuelven JSON puro
- **Problema**: los prompts pedían "JSON" y el código hacía `json.loads()`
  directo; los modelos reales suelen envolver la respuesta en ```json ... ```
  o añadir texto, lo que rompía la extracción de claims/evaluaciones.
- **Solución**: helper `_parse_json_response()` que quita fences markdown y
  aísla el primer objeto/array JSON; la descomposición de preguntas ahora
  limpia numeración y viñetas que añaden los modelos reales. El fallo de
  parseo real sigue registrándose como decisión "fail" (sin ocultarlo).

### Hallazgo 13: Validación demasiado estricta + retorno de error incompleto
- **Problema**: el primer test real con modelo gratuito falló con
  `KeyError: 'step_count'`. Dos causas combinadas: (a) `_validate_step`
  rechazaba cualquier respuesta que contuviera `...`, y los modelos reales
  usan puntos suspensivos legítimos, así que el paso 1 se marcaba inválido;
  (b) la rama de error devolvía un dict sin las claves `steps`/`step_count`,
  rompiendo a quien consumía el resultado (el test hacía `r["step_count"]`).
- **Solución**: validador que exige contenido sustancial (≥10 caracteres
  alfanuméricos tras eliminar puntuación/plantilla) en vez de vetar `...`;
  y todas las ramas devuelven la misma forma de diccionario. Los tests
  offline con MockLLM siguen en verde.
- **Regla derivada**: los caminos de error deben devolver la MISMA forma que
  el camino feliz (evita `KeyError` en el consumidor); verificar con un test
  que ejerza la rama de error, no solo la feliz.

---

## 2026-10-14 (ronda 4) — Repositorio Git

### Hallazgo 14: Claves ficticias con formato de clave real disparan escáneres
- **Problema**: el test de integración usaba como valor ficticio una cadena
  con el prefijo habitual de una credencial real; el escaneo la marcó como
  posible secreto.
- **Solución**: placeholders inequívocos (`"clave-ficticia-de-test"`).
- **Regla derivada**: en tests, usar valores que no imiten el formato de una
  credencial real.

### Hallazgo 15: Validación con falso positivo por "etc."
- **Problema**: con el modelo real, el paso `plan` (2.824 caracteres de
  contenido sustancial) se marcaba inválido porque el texto contenía "etc.".
  Vetar "etc."/"..." en cualquier posición produce falsos positivos: los
  modelos reales los usan dentro de respuestas legítimas.
- **Solución**: validar por contenido sustancial (≥10 caracteres alfanuméricos
  tras eliminar puntuación/plantilla) en vez de vetar palabras concretas.
  Casos comprobados: texto largo con "..." → válido; plantilla vacía → inválido.
- **Regla derivada**: los validadores deben medir el contenido, no bloquear por
  la presencia de una palabra aislada.

### Hallazgo 16: Errores 5xx transitorios del proveedor (P1.34)
- **Problema**: el modelo gratuito devolvió `502 Failed to generate
  completions` (infraestructura del proveedor) y abortaba la ejecución.
- **Solución**: helper `_chat_completion()` con reintentos (máximo 3), backoff
  exponencial + jitter, aplicado a `OpenAILLM`/`OpenRouterLLM` y
  `KiloGatewayLLM`. Reintenta solo errores transitorios (429, 5xx, red/timeout),
  informa cada reintento por stderr y **eleva el error al agotar** (nada de
  fallback silencioso, P1.19). Verificado con un cliente falso: 3 intentos +
  excepción final.
- **Resultado**: tras el fix, la prueba real completa (conexión + pensamiento de
  7 pasos + investigación end-to-end) pasa 3/3 con `exit=0`.

### Hallazgo 17: Datos de cuenta en los mensajes de error
- **Problema**: los errores de OpenRouter incluyen `'user_id': 'user_...'`;
  el test lo escribía en su log de resultados.
- **Solución**: función `_sanitizar()` que oculta el `user_id` antes de
  imprimir o guardar (P0.9). El log está además en `.gitignore`.

---

## 2026-10-14 (ronda 5) — Mejoras: búsqueda real, motor unificado, tests

### Hallazgo 18: El retrieve con búsqueda real recuperaba 0 fuentes
- **Problema**: al conectar `WikipediaSearchAPI` al pipeline, el informe salió
  con 0 fuentes y 0 claims (el modelo, honestamente, lo reportó). Reproducido
  de forma determinista: el modelo real genera subpreguntas de 160–270
  caracteres y Wikipedia devuelve 0 resultados en 4 de 5.
- **Diagnóstico**: `SourceRetriever` pasaba la pregunta natural completa al
  buscador. Los motores por palabras clave no entienden preguntas
  multi-cláusula. Con un LLM falso (subpreguntas cortas) el mismo código
  recuperaba 20 fuentes: el fallo era de los datos de entrada, no del retrieve.
- **Solución**: `formulate_query()` extrae los términos con contenido
  (sin palabras vacías) antes de buscar, con escalera de ampliación que se
  registra en el log de decisiones (nunca en silencio).
- **Evidencia**: 0 → 19 fuentes, 12 claims, 12 evaluaciones.

### Hallazgo 19: Formular consulta sin ancla temática destruye la relevancia
- **Problema**: con los 4 primeros términos de la subpregunta, "fusión"
  (9ª palabra) quedaba fuera y Wikipedia devolvía "Cine experimental",
  "Estereoscopio", "Unión Internacional de Química Pura y Aplicada".
- **Solución**: `formulate_query(..., anchor_terms=...)` coloca al principio
  los términos del tema tomados de la pregunta original del usuario.
- **Evidencia**: 13/13 fuentes con términos del tema (antes, resultados
  irrelevantes), manteniendo 13 fuentes y 12 claims.

### Hallazgo 20: Elegir parámetros con medición, no por intuición
- **Método**: se midió el recall de `formulate_query` con `max_terms` ∈
  {8,5,4,3,2} sobre 5 subpreguntas reales: 8→8 resultados, 5→21, 4→24, 3→25,
  2→25. Ordenar los términos por longitud daba peor resultado (15).
- **Decisión**: `max_terms=4` (buen recall sin perder especificidad),
  con escalera de ampliación si falla.

### Hallazgo 21: Duplicación estructural en los dos motores de pensamiento
- **Problema**: `pensamiento_layer` y `code_design_improvement_tools` repetían
  el validador, el cálculo de confianza, la extracción de decisión y la forma
  del resultado (14 prompts de paso replicados).
- **Solución**: `thinking_engine.StepThinkingEngine` centraliza el ciclo, la
  validación (ahora existe en un solo sitio), la confianza y la forma estable
  del resultado; cada módulo aporta solo sus pasos.
- **Mejora añadida**: si un paso no valida, el ciclo se detiene y lo reporta
  en `invalid_steps` (validación antes de avanzar).

### Hallazgo 22: Forma de resultado rota en la rama de error de `CodeDesignThinker`
- **Problema**: `_execute_thinking_cycle` devuelve, cuando el paso 1 no valida,
  un dict SIN la clave `invalid_steps` (el camino feliz y
  `StepThinkingEngine._run_cycle` sí la incluyen). Un consumidor que haga
  `result["invalid_steps"]` en esa rama obtiene `KeyError`: la misma clase de
  regresión del Hallazgo 13. Detectado al escribir el test de la rama inválida
  de la suite `tests/`.
- **Estado**: **CORREGIDO** — se añadió `"invalid_steps": ["analysis"]` a esa
  rama y el test de regresión `tests/test_regressions.py` compara las claves de
  ambas ramas (si el bug reaparece, el test falla).
- **Regla derivada**: al añadir una rama de error nueva, comparar
  `set(resultado)` contra el camino feliz en el propio test.

### Hallazgo 23: El binario `coverage` puede apuntar a OTRO intérprete
- **Problema**: `~/.local/bin/coverage` tiene shebang al Python 3.10 de Blender;
  bajo ese intérprete el SDK `openai` instalado para 3.10 está roto
  (`ModuleNotFoundError: annotated_types`) y 3 tests fallaban solo con
  `coverage run`, no con `python3 -m unittest`.
- **Solución**: usar `python3 -m coverage run/report` (mismo intérprete del
  proyecto, 3.11) en vez del script de `~/.local/bin`.
- **Regla derivada**: si una herramienta CLI se comporta distinto que
  `python3 -m <herramienta>`, sospechar del shebang y verificar con
  `head -1 $(which <herramienta>)` (P0.16).

---

## 2026-10-14 (ronda 6) — Reproducibilidad, arquitectura y seguridad

### Hallazgo 24: Un contador como señal de estado es un acoplamiento frágil
- **Problema**: `QuestionDecomposer` decidía si descomponer mirando
  `context.iteration == 0`, un contador que incrementaba el recuperador de
  fuentes. Funcionaba por casualidad: cualquier cambio en el orden del pipeline
  lo rompía.
- **Solución**: flag explícito `ResearchContext.decomposed`, expuesto en
  `to_dict()`. **Evidencia de que la suite protege el contrato**: al cambiar el
  diseño, el test `test_decomposer_no_recalcula_si_iteracion_avanzada` falló
  (era el único acoplado al diseño viejo) y se actualizó a la nueva semántica
  más un test del flag.

### Hallazgo 25: Separar por cohesión sin romper consumidores
- **Acción**: los proveedores LLM salieron de `deep_research_system.py`
  (642 → 435 líneas) a `llm_providers.py` (228 líneas); el pipeline ya no sabe
  cómo se habla con un modelo.
- **Cómo sin romper nada**: re-export con `# noqa: F401` en el módulo original,
  así los consumidores (tests incluidos) siguen importando del mismo sitio.
  Verificado: `MockLLM is llm_providers.MockLLM` y los 134 tests en verde.
- **Regla derivada**: al mover código, re-exportar en el origen y comprobar la
  identidad de objetos, no solo que "importa".

### Hallazgo 26: SBOM honesto cuando falta la herramienta estándar
- **Problema**: `syft` no está instalado; fingir un SPDX completo sería
  deshonesto.
- **Solución**: `scripts/generate-sbom.sh` usa syft si existe y, si no,
  `scripts/sbom_fallback.py`, que etiqueta el resultado como
  `"conformsTo": "ninguno (inventario propio...)"`. Inventario real: 20
  paquetes con 462 hashes.

### Hallazgo 27: Instalación reproducible verificada, no supuesta
- **Acción**: `uv pip compile --generate-hashes` → `requirements.lock`
  (20 paquetes, 462 hashes). Instalación comprobada con
  `python3 -m pip install --dry-run --require-hashes -r requirements.lock`.
- **Extra**: `pip-audit` sobre el lockfile → "No known vulnerabilities found".
  `scripts/scan-secrets.sh` integrado en el hook pre-commit; su política de
  placeholders (valores vacíos o `...` son seguros) evita falsos positivos en
  `.env.example` y README, documentada para no relajar el patrón por pereza.

---

## 2026-10-14 (ronda 7) — Licencia y último resto simulado

### Hallazgo 28: El texto de una licencia se verifica, no se transcribe a ojo
- **Acción**: `LICENSE` con la GNU GPL v3. La propia licencia prohíbe
  modificarla, así que se comprobó con `diff` contra la fuente oficial
  (`https://www.gnu.org/licenses/gpl-3.0.txt`): **idénticos, 35.149 bytes**.
- **Decisión declarada**: `license = "GPL-3.0-only"` en `pyproject.toml`
  (SPDX). Cambiar a `GPL-3.0-or-later` es una palabra, pero es decisión del
  titular; se documenta en vez de asumirse.
- **Atribución**: se conserva la de `better-ai` (CC BY-SA 4.0) y
  `better-project` (GPL-3.0-or-later) en README y AGENTS.md.

### Hallazgo 29: Simular una pipeline completa es deuda, aunque esté declarada
- **Problema**: `ResearchOrchestratorWithThinking` tenía 70 líneas de
  heurísticas propias (claims/evaluaciones/síntesis "simuladas") que duplicaban
  y empobrecían el pipeline real: dos formas de hacer lo mismo, una de ellas
  fingida.
- **Solución**: delega en `ResearchOrchestrator` (el pipeline real). Se
  eliminaron los tres métodos simulados y su resultado ahora expone el
  `report`, las `sources`, los `claims` y las `evaluaciones` reales.
- **Evidencia**: el mismo caso offline pasó de 1 claim simulado con veredicto
  fijo a 3 fuentes / 3 claims / 3 evaluaciones del pipeline; `pensamiento_layer`
  bajó de 416 a ~330 líneas y su cobertura quedó en 100%. Test de regresión que
  verifica que los métodos simulados **ya no existen**.

### Hallazgo 30: "Funciona en mi árbol" no es verificación
- **Problema**: toda la verificación se hacía sobre el árbol de trabajo, con
  archivos sin comitear presentes. Un proyecto que dependiera de un archivo no
  versionado pasaría las comprobaciones y rompería al clonar.
- **Solución**: `scripts/ci.sh` (y `make ci`) exporta **HEAD a una copia
  limpia** (`git archive | tar -x` en un temporal) y verifica allí: ruff,
  py_compile, 131 tests y escaneo de secretos. Sin nube ni proveedores.
- **Efecto colateral**: `scan-secrets.sh` aprendió a trabajar sin repositorio
  git (la copia exportada no tiene `.git`): usa `find` como respaldo.
- **Evidencia**: `bash scripts/ci.sh` → exit 0 con la copia limpia.

---

## 2026-10-14 (ronda 8) — Mutación, Ollama en vivo y tests de comportamiento

### Hallazgo 31: La cobertura NO mide la fuerza de la suite
- **Medición**: con 99% de cobertura, `mutmut` (2.664 mutantes) solo mató
  1.444 → **54,2%**. Las líneas se ejecutaban, pero no se comprobaba su efecto.
- **Acción**: 41 tests nuevos de comportamiento exacto (parámetros enviados,
  limpieza de HTML, resolución de redirecciones, registros del log de
  decisiones, cifras del prompt del informe, formato del reporte) →
  **1.531/2.664 = 57,5%**.
- **Composición de los 1.133 supervivientes**: 330 en las funciones `main()`
  de demo (impresiones), 127 en `analyze_and_improve`, 79 en
  `EvidenceEvaluator.decide`, 74 en `generate_report`, 72 en `MockLLM.generate`,
  47 en `SourceRetriever.decide`.
- **Regla derivada**: cobertura y mutación son complementarias; para lógica
  nueva, asertar valores exactos y efectos (no solo "no revienta").

### Hallazgo 32: Un pragma que la herramienta no implementa es documentación falsa
- **Intento**: añadir `# pragma: no mutate` a los `main()` de demo para que la
  métrica midiera lógica. Los números no cambiaron.
- **Verificación**: el propio código de mutmut 3 trae
  `# TODO: pragma no mutate should end up in 'skipped' category` → **no está
  implementado**. Se retiraron los comentarios en lugar de dejar escrita una
  exclusión que no existe (P1.10).
- **Regla derivada**: antes de afirmar en un comentario que una herramienta
  ignora algo, comprobar que lo ignora de verdad.

### Hallazgo 33: Ollama local verificado en vivo (LLM sin API key)
- **Contexto**: el servidor Ollama estaba corriendo con varios modelos.
- **Acción**: `test_ollama_real.py` (opt-in; si el servidor no responde, la
  prueba se OMITE, nunca se simula).
- **Evidencia**: 3/3 — conexión, pensamiento de 7 pasos válido e investigación
  completa con `qwen3:1.7b` (5 subpreguntas, 5 claims, informe de 6.851 chars).
  El proyecto funciona con LLM local, sin coste ni claves.

### Hallazgo 34: Subir la mutación exige asertar valores, no llamadas
- **Progresión medida**: 54,2% → 57,5% → **61,2%** (1631/2664) añadiendo 68
  tests de precisión (constantes exactas, límites de umbral, formatos de dos
  decimales, claves devueltas, orden de la escalera de consultas, truncados).
- **Tres expectativas mías eran erróneas** y los números lo delataron: el
  umbral de línea larga es `>120` (no `>=120`), `EvidenceEvaluator` usa SOLO
  las fuentes que coinciden por URL (no añade las demás) y el paso inválido del
  ciclo queda registrado vacío en lugar de desaparecer. Se corrigió el test, no
  el código: el comportamiento era el correcto.
- **Dónde queda el resto**: 330 mutantes en las tres funciones `main()` de demo
  (impresiones) y 193 en el orquestador/reporte de código (también impresivos).
- **Regla derivada**: al escribir tests, asertar el valor y el efecto concretos
  (qué se envía, cuánto se trunca, qué se registra); "no revienta" no cuenta.

### Hallazgo 35: Verificación multi-versión en venv aislado
- **Acción**: suite completa en un venv de **Python 3.12** (aislado, sin tocar
  el entorno del sistema): `python3.12 -m venv /tmp/venv312` + `pip install -r
  requirements.txt`.
- **Evidencia**: **199 tests OK en 3.12** (antes solo se había verificado 3.11).
  El código no depende de APIs exclusivas de una versión ni de rutas de sistema.

---

## 2026-10-14 (ronda 9) — Separar lógica de presentación

### Hallazgo 36: La lógica mezclada con impresión es intestable (y no mata mutantes)
- **Medición**: 193 de los mutantes supervivientes estaban en
  `analyze_and_improve` (que imprimía en cada fase) y `generate_report`.
- **Solución**: `run_analysis(progress=None)` (núcleo puro, sin `print`) y
  `report_lines()` (devuelve la lista de líneas); `analyze_and_improve()` y
  `generate_report()` quedan como presentación fina. Se añaden 16 tests que
  comprueban mensajes, claves, contenido exacto de cada sección y formato.
- **Evidencia**: mutación **61,2% → 64,0%** (1675/2617); el código total bajó
  de 2664 a 2617 mutantes porque desapareció lógica duplicada.
- **Regla derivada**: separar núcleo y presentación no es cosmética: es lo que
  permite comprobar valores en lugar de capturar stdout.

### Hallazgo 37: Dos definiciones del mismo concepto ("score de eficiencia")
- **Problema**: `CodeAnalysisContext` calculaba `issues/50` y
  `analyze_python_source` calculaba `issues/30`; el reporte mostraba una y el
  análisis la otra. Dos números distintos para lo mismo.
- **Solución**: constante única `EFFICIENCY_REFERENCE_ISSUES = 30` usada por
  ambos, con docstring que explica que mide cobertura del análisis, no calidad.
- **Regla derivada**: si dos módulos calculan la misma métrica, extraer una
  única referencia; si no, cualquier cambio la desincroniza.

---

## 2026-10-14 (ronda 10) — Configuración real de mutmut y 75% de mutación

### Hallazgo 38: Tres opciones de mutmut que parecen iguales y solo una funciona
- **Comprobado en el código de mutmut 3** (no por suposición):
  - `# pragma: no mutate`: el visitante de pragmas solo marca **su propia
    línea** (no el bloque), así que no sirve para excluir una función entera.
  - `do_not_mutate = [...]`: la clave existe en `configuration.py` pero el
    motor **nunca la lee**; ponerla no cambió ninguna cifra.
  - `do_not_mutate_patterns = [...]`: es la que el motor aplica
    (`pragma_handling.get_lines_ignored_by_pattern`, por línea de código).
- **Uso**: se excluyen las líneas `print(...)`, que no alteran estado y generan
  mutantes equivalentes (inmatables de forma útil).
- **Resultados publicados (ambos reales)**:
  - Sin excluir nada: **65,7%** (1720/2617 mutantes muertos).
  - Excluyendo líneas `print`: **75,0%** (1604/2139).
  - Progresión de la sesión: 54,2% → 57,5% → 61,2% → 64,0% → **75,0%**.
- **Supervivientes restantes** (535): `EvidenceEvaluator.decide` 59,
  `SourceRetriever.decide` 35, `run_analysis` 34, `MockLLM.generate` 31,
  `ClaimExtractor.decide` 25, `report_lines` 25.
- **Regla derivada**: antes de usar una opción de configuración para mejorar una
  métrica, comprobar en el código de la herramienta que esa opción se lee y se
  aplica; si no, es un cambio cosmético que no debe reportarse como mejora.

---

## 2026-10-15 — ToT con evaluación LLM, benchmark framework, plugins y fixes pre-commit (hallazgos 39–48)

### Hallazgo 39: Anotaciones de tipo sin importar rompen el import en Python ≤3.13 (pero pasan en 3.14)
- **Problema**: los 6 plugins usaban `List`, `Dict`, `Any` en firmas sin
  importarlos de `typing`. En Python 3.14 (PEP 649, anotaciones perezosas) el
  import funciona; en 3.12.7 falla con
  `NameError: name 'List' is not defined`. El proyecto declara 3.11/3.12 como
  plataformas verificadas, así que era un bug real de compatibilidad.
- **Solución**: importar en cada archivo los tipos usados en sus firmas y
  verificar el import con el Python 3.12 real instalado.
- **Evidencia**: con Python 3.12.7 → `NameError` antes del fix; tras el fix,
  `deepseek_plugin import OK`; ruff F821 en 0.
- **Regla derivada**: verificar imports en la VERSIÓN MÍNIMA soportada, no solo
  en la más nueva instalada; en Python ≤3.13 las anotaciones se evalúan al
  importar.

### Hallazgo 40: Descubrir un plugin no es cargarlo (ni ejecutarlo)
- **Problema**: los 6 plugins se descubrían bien, pero DuckDuckGo y Wikipedia
  fallaban al CARGAR: llamaban a `DuckDuckGoSearchAPI(max_results=...)` y
  `WikipediaSearchAPI(language=..., max_results=...)` — argumentos que no
  existen. Las firmas reales son `DuckDuckGoSearchAPI(timeout=20)` y
  `WikipediaSearchAPI(language="es", timeout=20)`, con
  `search(query, max_results=5)`. Wikipedia además accedía a
  `self._search.max_results` (atributo inexistente). El discovery no ejecuta
  constructores, por eso no lo detectaba.
- **Solución**: pasar los argumentos reales y eliminar el acceso al atributo
  inexistente; verificar la carga completa de los 6.
- **Evidencia**: «Load duckduckgo: FAILED» / «Load wikipedia: FAILED» antes;
  tras el fix, los 6 cargan («Loaded plugin ... v1.0.0») y
  `python test_plugin_system.py` pasa 8/8.
- **Regla derivada**: una verificación debe cargar Y ejecutar el componente;
  la presencia en un registro (o un discovery) no prueba nada.

### Hallazgo 41: Definiciones duplicadas = código muerto silenciado (F811)
- **Problema**: `tests/benchmarks/rubrics.py` acabó con DOS versiones de
  `evaluate_dimension` y `evaluate_all_dimensions`: las nuevas (con soporte
  `domain`) se añadieron sin borrar las viejas, que quedaron anuladas (gana la
  última definición) — código muerto y engañoso.
- **Solución**: eliminar las versiones viejas; conservar `_heuristic_check`,
  que sí usa la versión nueva.
- **Evidencia**: ruff F811 antes; «All checks passed!» después.
- **Regla derivada**: al reemplazar una función por una "mejorada", sustituir la
  anterior; dejarlas convivir crea código muerto que el lint ve y las personas no.

### Hallazgo 42: Los IDs de modelos gratis se miden contra la API, no se eligen de memoria
- **Problema**: el modelo por defecto de OpenRouter (Nemotron 3 Super) tardaba
  ~11 s por llamada y no terminaba los tests reales. Varios "gratuitos" de
  páginas de terceros fallaban de verdad: 403 por límite de la key, 403 "solo
  para harnesses agénticos", 429 del proveedor.
- **Solución**: script de benchmark real (13 modelos, latencia medida) + cadena
  de fallback ordenada por velocidad que salta al siguiente modelo ante
  429/403/404; por defecto `poolside/laguna-xs-2.1:free` (1,58 s medido).
- **Evidencia**: 9/13 modelos respondieron; latencias 1,58–10,97 s; el pipeline
  real completo se corta por rate limit del tier gratis (50 req/día) — se
  declara como límite de la prueba, no se oculta.
- **Regla derivada**: medir antes de fijar un valor por defecto; 403/404 →
  probar siguiente modelo, 429 → reintento con backoff; documentar los límites
  del tier gratuito como límite externo.
- **Re-verificación 2026-10-16**: con el defecto ya unificado en laguna,
  `python3 test_openrouter_real.py` no completó en 280 s: la API devolvió 429
  repetidos y el cliente recorrió la cadena de fallback (laguna →
  cohere/north-mini-code) sin llegar al final antes del corte. Es el mismo
  límite externo documentado aquí, no un fallo del código: los reintentos con
  backoff y el salto de modelo funcionaron como se diseñaron. El último
  resultado completo sigue siendo el del 2026-10-14
  (`test_openrouter_result.txt`), y esta prueba sigue siendo opt-in.

### Hallazgo 43: El CI en copia limpia como última red (avisos ruff post-commit)
- **Problema**: tras el commit 4e9dd1b, el CI en copia limpia (`scripts/ci.sh`)
  encontró 3 avisos ruff en código recién comiteado: F401 (`SearchStrategy`
  importado sin usar en `pensamiento_layer.py`), F541 (f-string sin placeholders)
  y E401 (`import json, re` en una línea). El árbol de trabajo no los había
  señalado porque no se ejecutó `ruff check .` completo tras los últimos edits
  del núcleo (solo sobre `plugins/` y `tests/benchmarks/`), y el hook
  pre-commit no está instalado.
- **Solución**: corregir los 3 avisos (import limpio, print sin `f`, imports
  separados) y añadir a la rutina la ejecución de `ruff check .` completo
  inmediatamente antes de cada commit.
- **Evidencia**: `ci.sh` falló con los 3 avisos en la copia limpia de HEAD; tras
  el fix, `ruff check pensamiento_layer.py thinking_engine.py` →
  «All checks passed!» y `py_compile` OK.
- **Regla derivada**: la verificación previa al commit incluye `ruff check .`
  sobre TODO el árbol (o instalar el hook); verificar solo subconjuntos deja
  pasar avisos, y el CI en copia limpia es la última red, no la primera.

### Hallazgo 44: El CI bash en Windows falla por el intérprete, no por el código
- **Problema**: al re-ejecutar `scripts/ci.sh` con Git Bash en Windows, el
  unittest de la copia limpia falló con 11 `ModuleNotFoundError: No module
  named 'requests'`; el `python3` que resolvía Git Bash apuntaba a un intérprete
  sin las dependencias del proyecto (y además imprimía «Could not find platform
  independent libraries <prefix>»). El código estaba bien: `ruff` pasaba y la
  misma suite daba 227/227 con el intérprete de desarrollo.
- **Solución**: shim `python3` temporal (`#!/bin/sh` +
  `exec /c/Python314/python.exe "$@"`) en un directorio añadido a `PATH`;
  re-ejecutar `PATH=<shim>:$PATH bash scripts/ci.sh` → verde total. No se tocó
  `ci.sh` (correcto en Linux) ni se instalaron paquetes de sistema.
- **Evidencia**: CI con 11 errors ModuleNotFoundError vs CI con shim →
  «ruff All checks passed!», py_compile limpio, «Ran 227 tests … OK»,
  «OK: sin secretos…», «…la copia limpia de HEAD verifica entera».
- **Regla derivada**: ante un fallo del CI con mensajes de imports ausentes,
  comprobar QUÉ intérprete resuelve `python3` en el shell (sobre todo en
  Windows/Git Bash) antes de tocar el código; distinguir fallo de entorno de
  fallo real, y documentarlo.

### Hallazgo 45: Restos de depuración sin trackear mantenían rojo el lint del árbol de trabajo

- **Problema**: `ruff check .` del árbol de trabajo acumulaba 13 avisos (E722
  `except:` desnudo, F541 f-strings sin placeholders, F401 imports sin usar) en
  9 de los 14 scripts de depuración sin trackear (búsqueda de logs,
  configuración de opencode, etc.). El entregable (copia limpia de HEAD) estaba
  limpio y el CI verde, pero el lint local — y por tanto el hook pre-commit —
  quedaba inutilizable por restos ajenos al proyecto.
- **Solución**: arreglarlos de forma mínima y no destructiva sin tocar ningún
  archivo versionado: 5 reemplazos de `except:` → `except Exception:`
  (check_logs.py, check_plugin_ts.py, find_logs.py, search_plugin_load.py,
  search_plugin_validation.py, leídos antes de editar) y 8 auto-fixes con
  `ruff check --fix` (F541/F401). Los scripts siguen sin trackear y sin
  comitear; el borrado queda a decisión del usuario.
- **Evidencia**: antes: `ruff check .` → 13 errores en 9 scripts, todos sin
  trackear; después: `ruff check --fix .` → «Found 8 errors (8 fixed,
  0 remaining)» + `ruff check .` → «All checks passed!»; py_compile de los 5
  editados OK; `git status --short` posterior → ningún archivo trackeado
  modificado.
- **Regla derivada**: distinguir el lint del ENTREGABLE (copia limpia de HEAD)
  del lint del ÁRBOL DE TRABAJO (herramienta local, que puede ensuciarse con
  restos locales); ante avisos que el CI no reproduce, comprobar si los
  archivos están versionados antes de tocar código del proyecto; los restos
  locales se arreglan mínimo o se retiran, nunca se comitean.

### Hallazgo 46: Una sola campaña de benchmark no calibra; hacen falta ≥2 dominios

- **Problema**: con una única campaña real (science_tech, n=3) no se podía
  distinguir si los scores bajos (0,235) eran del sistema, del dominio o de
  las tareas; la evaluación previa pedía ampliar la calibración.
- **Solución**: segunda campaña real con DeepSeek en otro dominio (medicine,
  n=3, mismas complejidades simple/moderate/complex) y comparación entre
  dominios y complejidades con el mismo esquema (modo lineal, 5 fuentes,
  LLM-as-judge).
- **Evidencia**: medicine → general 0,381 (IR 0,538 / AN 0,257 / PR 0,389;
  simple 0,458; moderate 0,606; complex 0,079) frente a science_tech → 0,235
  (0,291 / 0,287 / 0,127); mejor score individual acumulado:
  med_moderate_02 = 0,606 (IR 0,92); en ambos dominios las tareas complejas
  caen (0,127 y 0,079); ~104–110 s/tarea; 7 tareas reales acumuladas en 2
  dominios (DeepSeek).
- **Regla derivada**: calibrar el framework en al menos 2 dominios antes de
  extrapolar conclusiones por modelo; al reportar, declarar n por celda y que
  el modelo juez es el mismo modelo evaluado como límites de validez.

### Hallazgo 47: El reinicio canceló el monitoreo, no los resultados

- **Problema**: tras el reinicio del servidor, la notificación «Command cancelled
  because the server restarted» dio por perdida la campaña de calibración
  economics→law_policy→climate (9 tareas reales, ~17 min de cómputo y coste de
  API); el impulso natural era relanzarla entera.
- **Solución**: antes de relanzar, inspeccionar `benchmark_results/` — los tres
  dominios YA habían escrito sus resultados completos (timestamps
  17:02/17:10/17:19, anteriores al reinicio). Cero trabajo duplicado.
- **Evidencia**: economics 0,234 / law_policy 0,204 / climate 0,291 con 3/3
  tareas cada uno; matriz completa 5 dominios: science_tech 0,235 | medicine
  0,381 | economics 0,234 | law_policy 0,204 | climate 0,291 (media 0,269);
  complejidad agregada: simple 0,302, moderate 0,353, complex 0,152 (climate
  complex 0,316 > climate simple 0,252: la debilidad de las complejas no es
  universal); latencias 103–129 s/tarea.
- **Regla derivada**: ante un trabajo «cancelado» (reinicio, timeout de shell,
  desconexión), inspeccionar los artefactos de salida ANTES de relanzar; lo
  cancelado es la supervisión, no necesariamente la ejecución.

### Hallazgo 48: Restos locales en cuarentena y hook no instalado en Windows

- **Problema**: 14 scripts de depuración del entorno local (opencode: plugins,
  logs, config, scaffolding) ensuciaban `git status` y, antes de arreglarlos,
  rompían `ruff check .`; además el hook pre-commit no está instalado y en este
  Windows fallaría (python3 sin dependencias), bloqueando commits del usuario.
- **Solución**: cuarentena no destructiva: mover los 14 archivos a
  `_local_debug/` (dentro del repo) + patrón `_local_debug/` en `.gitignore`;
  decisión razonada de NO instalar el hook (el CI en copia limpia cubre las
  mismas comprobaciones; el hook exigiría el shim python3). Todo reversible y
  documentado.
- **Evidencia**: `git status --short` → solo « M .gitignore»; `ruff check .` →
  «All checks passed!»; 14 archivos listados en `_local_debug/`; CI en copia
  limpia verde con el shim.
- **Regla derivada**: los restos locales se aíslan en cuarentena ignorada (ni
  al repo ni a la papelera sin decisión); no instalar hooks que exijan
  herramientas no ejecutables en el entorno — documentar la alternativa (CI)
  en su lugar.

## 2026-10-16 (ronda 11) — Revisión del subsistema de plugins (hallazgos 49–51)

### Hallazgo 49: Un flag de configuración leído donde no se decide

- **Problema**: `enabled: false` en `config/plugins.yaml` no impedía la carga:
  `load_all` comprobaba `entry.config.enabled`, fijado en el descubrimiento con
  el valor por defecto (`PluginConfig()`, `enabled=True`), ANTES de fusionar el
  archivo (la fusión solo ocurría dentro de `load_plugin`). La configuración
  documentada como `enabled`/`priority`/`params` era decorativa para `enabled`.
- **Solución**: `load_all` consulta `self._merge_config(name).enabled` (config
  ya fusionada). La llamada explícita `load_plugin(name)` sigue cargando el
  plugin deshabilitado: la acción deliberada prevalece.
- **Evidencia**: con `mock_llm: enabled: false` en un archivo temporal,
  `load_all` lo cargaba igualmente («estado mock_llm pese a enabled:false ->
  loaded») ANTES; tras el fix, la regresión queda cubierta por
  `test_enabled_false_impide_que_load_all_cargue_el_plugin`.
- **Regla derivada**: la configuración que gobierna una decisión debe estar
  fusionada EN el punto donde se decide; probar el flag desactivándolo, no
  solo el camino feliz.

### Hallazgo 50: Dependencia no declarada + fallo silencioso = config ignorada

- **Problema**: el subsistema de plugins lee `config/plugins.yaml`, pero PyYAML
  no estaba en `requirements.txt` ni en `requirements.lock`; además,
  `_load_config_file` capturaba cualquier error de lectura y continuaba con los
  valores por defecto (`except Exception` → print a stderr → `{}`). En una
  instalación limpia TODA la configuración se ignoraba sin que ninguna prueba
  lo notara (funcionaba solo porque PyYAML estaba instalado en el entorno de
  desarrollo).
- **Solución**: declarar `PyYAML==6.0.3` en `requirements.txt`/`pyproject.toml`
  y regenerar el lock con hashes (`make lock`: única línea añadida,
  `pyyaml==6.0.3`, 0 versiones alteradas); y elevar `RuntimeError` con el
  motivo si el archivo no se puede leer o falta la dependencia (fallo ruidoso,
  P1.19/P1.26).
- **Evidencia**: `grep -i yaml requirements.lock` → vacío antes; tras `make
  lock`, `pyyaml==6.0.3` con hashes; test
  `test_config_ilegible_eleva_error_en_vez_de_ignorarse` en verde.
- **Regla derivada**: toda dependencia que el código importa —aunque sea dentro
  de una función— va declarada en el manifiesto; un error al leer configuración
  se eleva, no se degrada a defaults silenciosos.

### Hallazgo 51: La baja de hooks no encontraba lo que la alta registró

- **Problema**: `_unregister_hooks` volvía a llamar a `plugin.get_hooks()`, que
  devuelve objetos NUEVOS en cada llamada (lambdas): `hook_func in
  self._hooks[...]` era siempre falso y, al descargar un CorePlugin (o hacer
  hot-swap), sus hooks seguían ejecutándose. Lo destapó el test nuevo
  `test_hook_se_registra_al_cargar_y_se_retira_al_descargar`.
- **Solución**: guardar los callables exactos registrados por plugin
  (`self._plugin_hooks[name]`) y retirar esos mismos en la baja.
- **Evidencia**: antes → `AssertionError: ['hook-ejecutado'] != []` tras
  `unload_plugin`; después → 21/21 tests de plugins y 248/248 de la suite.
- **Regla derivada**: si una API devuelve objetos nuevos en cada llamada, guarda
  los que registraste; no asumas que dos llamadas producen lo mismo.

## 2026-10-16 (ronda 12) — Coherencia del defecto, silencios del ToT y límites reales (hallazgos 52–54)

### Hallazgo 52: El valor por defecto vivía en cuatro sitios y decía tres cosas distintas

- **Problema**: el modelo por defecto de OpenRouter aparecía como
  `nvidia/nemotron-3-super-120b-a12b:free` en `llm_providers.py`, `README.md`,
  `AGENTS.md` y `.env.example`, pero como `poolside/laguna-xs-2.1:free` en
  `config/plugins.yaml` y en el plugin OpenRouter, mientras el Hallazgo 42 ya
  afirmaba que el defecto medido era laguna (1,58 s). El código construía el
  cliente con nemotron (10,97 s medidos) pese a que la cadena de fallback
  empezaba por laguna: «defecto documentado» y «defecto real» no coincidían.
- **Solución**: unificar a `poolside/laguna-xs-2.1:free` (el más rápido medido y
  el que usa el `.env` del programador) en código, README, AGENTS.md,
  `.env.example` y el docstring del test real; anclar la invariante con
  `test_modelo_por_defecto_es_gratuito_y_esta_en_la_cadena`.
- **Evidencia**: `grep -rn nemotron` antes → apariciones en 5 archivos con dos
  valores distintos; después → solo entradas legítimas de la cadena de fallback;
  `DEFAULT_FREE_MODEL == OPENROUTER_FALLBACK_CHAIN[0]` verificado en ejecución.
- **Regla derivada**: un valor por defecto es un dato único; si aparece en
  documentación, configuración y código, se unifica y se ancla con un test que
  compare las fuentes entre sí.

### Hallazgo 53: Dos silencios anidados en el juez del ToT

- **Problema**: `_evaluate_state` envolvía `_evaluate_state_llm` en
  `except Exception: pass`, y este último tenía su propio `except Exception:
  pass` interno: si el juez devolvía algo que no era JSON, el sistema degradaba
  a la heurística sin dejar rastro. Dos capas de silencio para el mismo fallo
  (P1.19/P1.26).
- **Solución**: un único punto de degradación: `_evaluate_state_llm` eleva
  `ValueError` si no hay JSON y `_evaluate_state` reporta la causa por stderr
  antes de usar la heurística local.
- **Evidencia**: con un juez que no devuelve JSON, stderr muestra «[ToTEngine]
  LLM-as-judge falló (ValueError: Respuesta del juez sin JSON…); se usa la
  heurística local»; el score pasa de 1.0 (juez válido) a 0.66 (heurística);
  cubierto por `test_juez_sin_json_se_reporta_y_usa_heuristica` y
  `test_juez_con_json_usa_su_puntuacion`.
- **Regla derivada**: una degradación prevista se implementa UNA vez y se
  reporta; envolver un fallo ya envuelto produce silencio doble.

### Hallazgo 54: Un parámetro de límite que no limitaba nada

- **Problema**: `max_iterations` se guardaba en `ResearchContext` y se pasaba por
  el orquestador, pero ninguna comparación lo usaba: el bucle procesaba todas
  las subpreguntas. Un límite declarado y no aplicado es peor que no tenerlo
  (da falsa sensación de control de tiempo/coste).
- **Solución**: aplicarlo en `ResearchOrchestrator.research` (cada subpregunta =
  una iteración), registrando el recorte en `decision_log`
  (`iteration_limit`/`truncate`) y ajustando `context.subquestions` a lo
  realmente procesado.
- **Evidencia**: con `max_iterations=2`, `len(ctx.subquestions) == 2`,
  `ctx.iteration == 2` y una decisión `truncate`; con 5, las 3 subpreguntas de
  MockLLM se procesan sin recorte.
- **Regla derivada**: un parámetro de límite se prueba con un caso que lo
  exceda; si ningún test distingue «límite aplicado» de «límite ignorado», el
  parámetro no existe de verdad.

### Hallazgo 55: Dos objetos `metadata` para el mismo plugin (y el dashboard mentía)

- **Problema**: `_register_plugin_class` creaba una instancia temporal y guardaba
  SU metadata en el registro; al cargar, el registro marcaba
  `status`/`load_time`/`error_message` en esa copia, pero la instancia real tenía
  su propio objeto `metadata` (creado en su `__init__`, con
  `status="unloaded"`). Y `get_stats()` —lo que leen `list_plugins`, el
  dashboard y el CLI— devuelve los del INSTANCE: un plugin cargado se mostraba
  como «unloaded», con `uptime` y `load_time` a 0 y `healthy_plugins` a 0.
- **Solución**: una única fuente de metadatos: tras crear la instancia,
  `instance.metadata = entry.metadata` (el instance comparte el objeto del
  registro).
- **Evidencia**: antes → `test_uptime_solo_cuenta_si_esta_cargado` (uptime 0) y
  `test_health_healthy_sin_degradados` (healthy 0 ≠ 1) fallaban; después →
  «status tras cargar: loaded | load_time > 0: True» y «status tras descargar:
  unloaded»; `dashboard.py` pasa de 0% a 100% de cobertura.
- **Regla derivada**: si el estado vive en dos objetos, alguien leerá el
  equivocado; comparte el objeto o sincroniza en un único punto verificable.

### Hallazgo 56: Un `discover_plugins()` posterior descartaba lo ya cargado

- **Problema**: `_register_plugin_class` sobrescribía la entrada existente sin
  condiciones. Cualquier descubrimiento posterior (el CLI lo ejecuta al inicio
  de CADA comando) descartaba la instancia viva: el plugin volvía a «unloaded»,
  se perdía su estado y sus hooks quedaban registrados sin dueño.
- **Solución**: si la entrada existente está LOADED/LOADING, no se pisa.
- **Evidencia**: antes → los tests del CLI `test_test_plugin_llm` y
  `test_set_active_llm_y_rechazo_por_tipo` fallaban porque la carga del primer
  comando se perdía al ejecutar el segundo; después → 47/47 tests de plugins y
  281/281 de la suite.
- **Regla derivada**: un descubrimiento/escaneo debe ser idempotente respecto a
  lo ya cargado; sobrescribir sin comprobar el estado destruye trabajo vivo.

### Hallazgo 57: La sonda por muestreo separa «key rota» de «rate limit», y la regla de mínima calidad de modelos

- **Problema**: `test_openrouter_real.py` no completó por 429 repetidos
  (re-verificación del Hallazgo 42) y quedaba la duda de si la causa era la
  key, la red, el servicio o el modelo. Un único intento no distingue causa ni
  permanencia, y la prueba completa agota el cupo al reintentar.
- **Solución**: sondear en el tiempo en vez de repetir la prueba completa: 9
  llamadas mínimas (`"Helo"`) cada 15 s durante 2 minutos contra el modelo por
  defecto, con timeout explícito por muestra; la sonda queda reutilizable en
  `scripts/probe_model.py` (sin key definida: no prueba y se omite).
- **Evidencia** (2026-10-16, `poolside/laguna-xs-2.1:free`): 8/9 respuestas OK
  con latencias 2,37–21,52 s y 1 solo fallo 429. Es decir: key y servicio
  correctos, con rate limit intermitente del tier gratuito; el defecto cumple
  la regla con margen (máximo 21,52 s frente a 60 s).
- **Regla del programador derivada**: no se prueba ni se fija como defecto un
  modelo que tarde SIEMPRE más de 1 minuto en responder `"Helo"` (no es
  práctico ni realista); si no hay key definida, no se prueba. Documentada como
  regla propia 10 en `AGENTS.md` y verificable con `scripts/probe_model.py`.
- **Regla derivada (técnica)**: ante un fallo intermitente de API, muestrear
  llamadas mínimas en el tiempo —distingue causa (key/red/servicio/rate limit)
  y permanencia— antes de repetir la prueba completa, que consume cupo.

### Hallazgo 58: La cifra de mutación publicada era anterior al código de ToT

- **Problema**: `AGENTS.md` publicaba «75,0% de mutantes muertos (1604/2139)»
  (2026-10-14) como fuerza actual de la suite, pero el Tree of Thoughts entró al
  día siguiente (commit 4e9dd1b) y nadie volvió a medir: la cifra publicada
  describía un árbol de código que ya no existía entero. Además decía «la
  cobertura (99%)» cuando dos de los seis módulos mutados estaban muy por
  debajo (77% y 82%).
- **Solución**: re-medir con `make mutation` y publicar el resultado con fecha,
  contexto y desglose por archivo; corregir la afirmación de cobertura.
- **Evidencia** (2026-10-16, HEAD): 1895 matados / 787 supervivientes / 99 sin
  test = 2781 mutantes → 68,1% matados; por archivo (matados/total, incluyendo
  los sin test): `thinking_engine` 59,0%, `deep_research_system` 66,3%,
  `llm_providers` 73,7%, `code_design_improvement_tools` 79,0%,
  `pensamiento_layer` 80,8%, `web_search` 84,0%. El código nuevo (ToT) es el
  punto débil, no una regresión de los tests viejos.
- **Regla derivada**: una métrica publicada se re-mide tras cada cambio grande
  de código y se anota su fecha y alcance; un porcentaje sin fecha ni
  denominador comparable es una afirmación no verificada.

### Hallazgo 59: Tests que importan módulos fuera de `source_paths` rompen la campaña

- **Problema**: los tests nuevos del subsistema de plugins importan `plugins/`,
  que no está en `[tool.mutmut] source_paths` y por tanto no existe en el
  sandbox `mutants/`: `make mutation` moría al colectar
  (`ModuleNotFoundError: No module named 'plugins'`) sin ejecutar ni un mutante.
  El fallo solo aparecía en el sandbox: `make test` y el CI seguían verdes.
- **Solución**: excluir esos tres ficheros de la selección de pytest de mutmut
  (`pytest_add_cli_args_test_selection` con `--ignore=...`), documentando que
  siguen corriendo en `make test` (miden el subsistema de plugins, que no se
  muta).
- **Evidencia**: antes → «ERROR collecting tests/test_plugin_cli.py … Failed to
  collect list of tests» y `make: *** [Makefile:40: mutation] Error 1`; después
  → campaña completa (2781 mutantes medidos, resultados por archivo del
  Hallazgo 58).
- **Regla derivada**: al añadir tests, comprobar también la herramienta que los
  ejecuta en OTRO entorno (mutmut): un test que pasa en `make test` puede romper
  una campaña que corre en un sandbox con solo parte del árbol.

### Hallazgo 60: Diez tests dirigidos por datos mataron 95 mutantes del ToT

- **Problema**: tras la re-medición (Hallazgo 58), `thinking_engine` era el punto
  débil con 243 mutantes supervivientes, concentrados en el código de ToT
  (`_evaluate_state_heuristic` 64, `think_tot` 52, `_generate_branches` 40,
  `_evaluate_state_llm` 30).
- **Solución**: en vez de un test por mutante, aserciones EXACTAS dirigidas por
  datos: una tabla de 11 casos para la heurística (base, tope de longitud, topes
  de marcadores y de coherencia, filtro `len(w) > 4`), una tabla de 5 casos para
  la ponderación del juez, y valores exactos de `think_tot` (poda total,
  `max_depth`, `pruned_nodes`, `best_score`) y de `_generate_branches`
  (`variant`, `depth`, prompts con variante, prompt/contexto en las ramas).
- **Evidencia** (misma campaña, antes→después): matados 1895→1990,
  supervivientes 787→692; `thinking_engine` 243→148 supervivientes (−95, −39%)
  con 10 tests nuevos (297 en total). Global: 1990/2781 = 71,6% (74,2% sin los
  99 mutantes que ningún test ejecuta). Por archivo
  (matados/supervivientes/sin test): `web_search` 204/39/0, `code_design`
  556/148/0, `thinking_engine` 411/148/34, `deep_research_system` 410/208/0,
  `llm_providers` 281/108/21, `pensamiento_layer` 128/41/44.
- **Tercera medición** (misma fecha, tras cubrir los 99 «sin test» con tests de
  `_render_tot_tree`/`get_tree_visualization`, `DeepResearchThinkingLayer.think_tot`
  y `DeepSeekLLM.__init__`): matados 1990→2086, supervivientes 692→713, **sin
  ningún mutante sin ejecutar**; global 2086/2799 = 74,5% (el total creció
  2781→2799 por las líneas del arreglo de claves del Hallazgo 61). Por archivo
  (matados/supervivientes de su total): `web_search` 204/39 de 243,
  `code_design` 556/148 de 704, `thinking_engine` 448/145 de 593,
  `deep_research_system` 410/208 de 618, `llm_providers` 299/129 de 428,
  `pensamiento_layer` 169/44 de 213.
- **Un caso del test estaba mal, no el código**: esperaba 0,60 y salía 0,57,
  porque "alfa" tiene 4 letras y el filtro es `len(w) > 4`; se corrigió la
  expectativa y se documentó en el propio test.
- **Regla derivada (eficiencia + inteligencia)**: para subir mutación, primero
  localizar los focos por función y atacar con aserciones exactas dirigidas por
  datos; perseguir mutantes equivalentes (p. ej. el recorte inalcanzable
  `min(round(score, 2), 1.0)`) no aporta valor.

### Hallazgo 61: Una aserción de test imprimió la clave real (y un cliente de otro proveedor la heredaba)

- **Problema (seguridad)**: al escribir los tests del constructor de
  `DeepSeekLLM` se comprobó `llm.api_key == ""` sin aislar el entorno; la clave
  no era vacía y `assertEqual` imprimió su valor REAL en la salida de unittest
  (una clave `sk-proj-…` de OpenAI). La causa de fondo era un bug: `DeepSeekLLM`
  y `OpenRouterLLM` heredaban `OPENAI_API_KEY` porque `OpenAILLM.__init__` cae a
  esa variable cuando la clave propia está vacía — un cliente de OTRO proveedor
  habría enviado la clave de OpenAI a `api.deepseek.com` / `openrouter.ai`.
- **Solución**: (1) `DeepSeekLLM` y `OpenRouterLLM` fijan su propia clave tras
  `super().__init__()`, sin heredar la de OpenAI; (2) los tests de claves usan
  SIEMPRE valores ficticios o vacíos (fijados con `patch.dict`, incluida
  `OPENAI_API_KEY`) para que un fallo no pueda imprimir una clave real;
  (3) regresiones `test_no_hereda_la_clave_de_openai` y
  `test_openrouter_no_hereda_la_clave_de_openai`.
- **Evidencia**: el fallo imprimió `sk-proj-…` en la salida de unittest;
  `grep -rl "sk-proj-" .` y `scripts/scan-secrets.sh` → sin rastro en ningún
  archivo del repo (el escape fue solo a la salida de esa ejecución); tras el
  arreglo, 312/312 tests OK.
- **Regla derivada**: un test nunca debe asertar contra valores del entorno sin
  fijarlos antes (una aserción fallida imprime ambos lados), y la clave de un
  proveedor no debe poder caer en el cliente de otro.

## 2026-10-16 (ronda 13) — Eficiencia medida: timeout explícito y caché (hallazgo 62)

### Hallazgo 62: En modo ToT, el 60% de las llamadas repetían un prompt ya hecho

- **Problema**: el cuello de botella real medido hoy es el cupo del tier
  gratuito (429, Hallazgo 57) y el pipeline repetía prompts idénticos; además el
  SDK usa 600 s de timeout por defecto, así que una llamada colgada bloquea la
  campaña entera.
- **Solución** (propuestas 1 y 2 de `docs/REFERENCIAS-IA.md`): `ResponseCache`
  por instancia de cliente (solo respuestas exitosas; los errores NO se cachean)
  y `DEFAULT_TIMEOUT = 60 s` explícito por petición, ambos configurables
  (`use_cache=`, `timeout=`); la caché expone `hits` y puede desactivarse.
  Además `_chat_completion` rechaza `max_retries < 1` (antes elevaba `None`).
- **Medición** (offline, con la capa de pensamiento real y un LLM contador):
  modo lineal 7 llamadas / 7 únicas (0% de ahorro); modo ToT
  (`branch_factor=2`, `beam_width=2`) **52 llamadas / 21 únicas → 31 duplicadas
  (60% eliminable)**; el prompt más repetido aparecía 4 veces.
- **Evidencia**: 13 tests nuevos (`tests/test_llm_cache_y_timeout.py`), incluidos
  «los errores no se cachean», «la caché es por instancia» y «el timeout llega a
  la petición» (`cliente.calls[0]["timeout"] == 60.0`); 325/325 tests OK; ruff
  sin avisos.
- **Regla derivada**: la eficiencia se mide contando llamadas reales (totales vs
  únicas), no se supone; y un timeout por defecto de una librería (600 s) es una
  decisión que el proyecto debe tomar explícitamente.

### Hallazgo 63: El registro decía «se amplía la consulta» cuando ya no había más

- **Problema**: en `SourceRetriever.decide`, el bucle de candidatas registraba
  «requery: sin resultados; se amplía la consulta» TAMBIÉN en la última
  candidata, cuando ya no quedaba ninguna por probar; y con una subpregunta sin
  términos (todas las candidatas vacías) el acceso `queries[0]` habría elevado
  `IndexError`. Lo destaparon los tests de aserciones exactas escritos para
  matar mutantes.
- **Solución**: se registra `requery` solo si queda una próxima candidata; en la
  última se registra `no_results` con el número de consultas probadas; y una
  subpregunta sin consulta posible devuelve `[]` sin llamar al buscador.
- **Evidencia**: con un buscador que siempre devuelve `[]` → 3 consultas,
  2 `requery` + 1 `no_results` (antes 3 `requery`); `test_retriever_con_subpregunta_vacia_no_revienta`
  en verde; 349/349 tests OK.
- **Regla derivada**: un registro de decisión no debe prometer una acción que ya
  no va a ocurrir; los tests con aserciones exactas encuentran incoherencias que
  el «camino feliz» no ve.

### Hallazgo 64: Aserciones exactas en los cuatro motores (mutación 66,3% → 79,4%)

- **Problema**: `deep_research_system` era el módulo más débil en mutación
  (66,3%; 208 supervivientes) y los cuatro motores del pipeline
  (`EvidenceEvaluator` 59, `SourceRetriever` 34, `ReportGenerator` 27,
  `ClaimExtractor` 25) estaban cubiertos solo por tests de «camino feliz».
- **Solución**: 24 tests de valores EXACTOS — selección de fuentes por URL del
  claim (y respaldo a las 3 primeras), truncados (snippet 200, claim 500,
  conclusión 100), formato exacto de las decisiones, diccionario de fallo del
  evaluador, orden y agotamiento de las consultas candidatas, contadores del
  prompt del informe — más el Hallazgo 63 que destaparon.
- **Evidencia** (campaña completa, antes→después): matados 2086→2237,
  supervivientes 713→641; `deep_research_system` 208→133 supervivientes
  (66,3%→79,4%); global 74,5%→77,7%.
- **Regla derivada**: los motores con prompts largos se testean por partes (qué
  entra en el prompt, qué se anota en el resultado, qué se registra en la
  decisión), no solo por el resultado final: ahí viven los mutantes vivos.

### Hallazgo 65: CoVe opt-in y fidelidad a las fuentes (del estudio a la práctica)

- **Problema**: (a) `EvidenceEvaluator` evaluaba cada claim contra los snippets
  que lo ORIGINARON → confirmación circular (Self-RAG/CoVe, arXiv:2309.11495);
  (b) el benchmark premiaba recordar datos, pero no medía si el informe inventa
  cifras respecto a las fuentes (RAGAS, arXiv:2309.15217).
- **Solución**: (a) segunda pasada `verificacion_independiente` (opt-in, una
  llamada extra por claim) que evalúa contra las fuentes que no lo originaron y
  marca `contested`; si no hay alternativas registra `skip` y no inventa nada;
  (b) `rubrics.evaluar_fidelidad(report, fuentes)` — proporción de cifras del
  informe presentes en las fuentes, con normalización de miles/decimales —,
  integrada en `run_benchmark` (campo `evaluation.fidelidad` del JSON) y en la
  línea de progreso.
- **Evidencia**: 12 tests nuevos (CoVe: activa/desactivada, fuentes
  alternativas, coincidencia vs contestado, sin alternativas, JSON inválido,
  paso del flag; fidelidad: cifras respaldadas, cifra inventada 99.9 → 0.0, sin
  cifras → 1.0 documentado como vacío, sin fuentes); 361/361 tests OK; campaña
  de humo del benchmark (mock, 1 tarea) con `fidelidad` en el JSON.
- **Decisión de diseño**: la fidelidad es una métrica APARTE, no un criterio más
  de las rúbricas: añadirla cambiaría las puntuaciones y rompería la
  comparabilidad con las campañas ya calibradas (Hallazgos 46-47).
- **Regla derivada**: una mejora del estudio se implementa opt-in y con medición
  propia, sin alterar las métricas ya publicadas.

### Hallazgo 66: CRAG, Self-Consistency y routing por tarea (y por qué NO paralelizar)

- **Problema**: cerrar las propuestas 5, 6, 7 y 3 del estudio sin comprometer la
  eficiencia ni la comparabilidad de las métricas ya calibradas.
- **Solución**:
  (5) `RelevanceJudge` + acción correctiva en `SourceRetriever`: si la
  relevancia puntúa bajo el umbral y quedan candidatas, se reformula la consulta;
  en la última se acepta lo recuperado y se registra; un juez sin JSON es
  fail-open REGISTRADO (nunca silencioso). Opt-in.
  (6) `voto_top_k` en `ToTEngine.think_tot`: entre las k mejores hojas gana el
  camino mayoritario y el resultado reporta `consenso` (k=1 = comportamiento
  original).
  (7) `llm_rapido` en `ResearchOrchestrator`: descompone y extrae el modelo
  rápido; evalúa y redacta el principal (enrutado por tarea).
- **Evidencia**: 15 tests nuevos (routing 3, CRAG 9, voto 3); **376/376 tests
  OK**; coste del juez CRAG medido en un pipeline mock: **8 → 11 llamadas** (una
  por subpregunta), declarado porque es un intercambio inteligencia/eficiencia;
  el voto se probó con un juez que puntúa MEJOR a la minoría, para que el test
  discrimine el voto y no el score.
- **Decisión razonada (propuesta 3, paralelización)**: el cuello de botella
  medido es el cupo del tier gratuito (429 repetidos, Hallazgo 57); paralelizar
  multiplicaría la presión sobre ese límite. Se aparca y se documenta, en vez de
  implementarla por completar la lista.
- **Mutación del lote** (misma campaña, antes→después): matados 2237→2354,
  supervivientes 641→846; global 77,7%→**73,6%**. La tasa baja porque `deep_research_system`
  pasó de 647 a 925 mutantes (63,9% hoy) con las funciones nuevas: **medir
  después de añadir código cambia el denominador** (mismo efecto que el ToT,
  Hallazgo 58). Las aserciones de prompt EXACTO (`TestPromptsExactos`) mataron
  22 mutantes de fragmento de los prompts nuevos.
- **Regla derivada**: una propuesta de eficiencia se implementa solo si ataca el
  cuello de botella MEDIDO; si la evidencia dice que lo empeora, se documenta el
  motivo.

### Hallazgo 67: thinker evalúa proyectos externos (y se evalúa a sí mismo)

- **Problema**: no había forma de evaluar un proyecto ajeno en las seis
  dimensiones acordadas (funcionalidades, calidad, vigencia, herramientas,
  inteligencia, eficiencia) con evidencia, sin impresionismo y sin tocar el
  proyecto evaluado.
- **Solución**: `evaluar_proyecto.py` — 24 criterios BINARIOS (4 por dimensión),
  evaluación estática y **read-only**, cero LLM, cada hallazgo con evidencia
  `archivo:línea`, y una capa de **mejoras derivadas de las métricas**: cada
  propuesta nace de un criterio fallido y trae su propia verificación (la métrica
  es el criterio de aceptación).
- **Evidencia**: 7 tests (fixture con defectos plantados, orden por prioridad,
  read-only comprobado, autoevaluación del propio repo); 387/387 tests OK.
  Resultados: **thinker 0,958** (único fallo: dependencias por detrás de PyPI) y
  **better-ocr 0,708** (sin licencia, sin linter, 5 `except: pass`, sin lockfile,
  sin caché). Informes completos en `docs/EVALUACIONES.md`.
- **Dos falsos positivos propios, detectados y corregidos**: (1) comparaba los
  `archivo.py` citados en el README contra nombres base, así que las rutas con
  carpeta (`scripts/bateria_360.py`) figuraban como «prometidas y no existentes»;
  (2) contaba «TODO REAL» —nombre de una regla de dominio en better-ocr— como
  deuda técnica. Corregidos, y el resto de hallazgos (`except: pass`) se verificó
  a mano contra el código real antes de darlos por buenos.
- **Mejora derivada de la métrica**: la autoevaluación encontró el único
  `except ImportError: pass` del repo (`verify_install.py`) y se corrigió:
  Calidad 0,75 → 1,00.
- **Regla derivada**: un evaluador automático debe (a) declarar sus límites en el
  propio informe, (b) no penalizar lo que no aplica (sin dependencias pesadas, el
  criterio de import perezoso no cuenta) y (c) verificarse contra un proyecto con
  defectos conocidos y contra sí mismo.
- **Ampliación posterior (misma fecha)**: `--ejecutar-tests` ejecuta el comando
  de tests **declarado** por el proyecto (Makefile → script/README → convención),
  con timeout y salida capturada, y las licencias de las dependencias se
  consultan en PyPI. Con eso, `no_verificado` queda **vacío** en las dos
  evaluaciones: thinker **0,958** (suite `make test` OK en 1,0 s) y better-ocr
  **0,733** (475 tests OK en 43,4 s).
- **Cuatro defectos del propio instrumento**, encontrados al usarlo contra
  proyectos reales y corregidos: rutas con carpeta del README, «TODO REAL» como
  deuda, `python-dotenv` como «sin licencia libre» (declara BSD-3-Clause en texto
  libre, sin clasificador OSI) y dependencias contadas dos veces cuando aparecen
  en dos manifiestos (ahora se deduplican prefiriendo `==`).
- **Tope de hallazgos = información oculta**: el informe listaba solo los 5
  primeros silencios (`except: pass/continue`). Al aplicar las mejoras en
  better-ocr se descubrió que en realidad eran **37**. Ahora la nota declara el
  total («silencios detectados: 37, se listan hasta 20») y la cuenta nunca se
  oculta.
- **Regla derivada (ampliada)**: un instrumento de medición se valida **usándolo
  en real**, no solo con fixtures; cada falso positivo se verifica a mano contra
  la fuente antes de corregirlo, y la primera cifra publicada es provisional
  hasta pasar por ese ciclo.

### Hallazgo 68: La superación es método y estructura (plan derivado de métricas)

- **Problema**: las propuestas de mejora eran una tabla redactada a mano
  (criterio → frase fija): iguales para todo proyecto, sin cuantificar el trabajo
  ni relacionar unas propuestas con otras.
- **Solución (método y estructura, no ingenio puntual)**: `proponer_mejoras`
  deriva el plan de las métricas del informe — sitios afectados, esfuerzo
  estimado por número de sitios, **secuencia** entre propuestas dependientes
  (fijar versiones → generar lockfile) y la verificación exacta de cada una — y
  lo ordena por prioridad, secuencia y esfuerzo (más valor por unidad de
  trabajo). `plan_texto` resume el plan por prioridad.
- **Evidencia**: para better-ocr el plan sale ordenado y accionable: licencia
  (alta, esfuerzo bajo) → 37 silencios (alta, esfuerzo alto) → medias por
  secuencia/esfuerzo, cada una con su verificación; 397/397 tests OK (3 nuevos:
  cuantificación y orden, secuencia del lockfile, resumen del plan).
- **Corrección de honestidad asociada**: el listado de hallazgos tenía tope de 20
  y `sitios` subestimaba (20 en vez de 37). Ahora se listan todos y la cifra es
  exacta: un plan con datos recortados decide sobre una realidad recortada.
- **Regla derivada**: una propuesta de mejora vale por su **método** (de dónde
  sale el dato) y su **estructura** (orden, secuencia, verificación), no por lo
  elocuente que suene; y ninguna cifra que alimente una decisión puede llevar
  tope oculto.

### Hallazgo 69: Síntesis del modelo con control anti-invención y dudas declaradas

- **Problema**: el plan mecánico (Hallazgo 68) es reproducible pero no ve lo que
  no cabe en un criterio binario (diseño, algoritmos, riesgos); y un LLM suelto
  puede inventar archivos, métricas o APIs al proponer mejoras.
- **Solución**: `--sintesis-llm` (opt-in; coste 0 con modelos `:free`) pide
  propuestas de FONDO a partir del informe **medido**. Control mecánico
  anti-invención: cada propuesta se marca `con_respaldo` solo si la evidencia que
  cita aparece en la evidencia medida del informe. Lo que el modelo no puede
  decidir se declara en `preguntas_abiertas` en vez de inventarse, y
  `--investigar` resuelve esas dudas con búsqueda real (reutiliza `web_search`)
  citando fuentes (o declarando «sin resultados» y los errores).
- **Evidencia** (ejecución real 2026-10-16 sobre better-ocr, modelo `:free`): el
  modelo devolvió propuestas sobre carga de modelos y caché —marcadas **SIN
  RESPALDO** al no coincidir su cita con la evidencia medida— y **2 preguntas
  abiertas** (arquitectura, flujo de datos) que no inventó; 403/403 tests OK
  (6 nuevos, offline con dobles).
- **Regla derivada**: cuando un modelo propone sobre datos medidos, la evidencia
  citada se verifica mecánicamente y lo desconocido se declara como pregunta —con
  su investigación citada— nunca como afirmación.

### Hallazgo 70: Un rango soportado y verificado en 3 versiones (openai 1/2/3)

- **Problema**: `openai` estaba fijado en 1.109.1 y la última es 3.33.0 (dos
  versiones mayores). Saltar sin verificar podía romper el cliente; quedarse en
  1.x dejaba la dependencia atrasada.
- **Solución**: declarar el rango `openai>=1.0,<4` en `requirements.txt` y
  `pyproject.toml` (el lock fija 3.33.0 con hashes), añadir un **canario** que
  comprueba la superficie que usamos (`OpenAI(...)` y
  `chat.completions.create` con `model`/`messages`/`timeout`) y verificar la
  suite completa en tres versiones mayores con venvs aislados.
- **Evidencia**: **405/405 tests** con openai **1.109.1**, **2.54.0** y
  **3.33.0**; instalación `--require-hashes -r requirements.lock` en un venv
  limpio → 3.33.0 y 405/405. El lock cambió de árbol de dependencias
  (httpx2/httpcore2/truststore; fuera distro/tqdm) y se validó **instalándolo**,
  no releyéndolo. El canario falla ruidosamente si una futura 4.x cambia la
  superficie.
- **Hallazgo colateral**: en el venv mínimo faltaba PyYAML y la suite falló con
  el error ruidoso del Hallazgo 50 — la corrección funcionó como se diseñó (antes
  la config se habría ignorado en silencio).
- **Regla derivada**: una dependencia se actualiza con un rango verificado en más
  de una versión y un canario de la superficie usada; y el lock se valida
  instalándolo con hashes en un entorno limpio, nunca leyéndolo.

## 2026-10-17 (ronda 14) — Revisión con reproducción: 6 bugs ALTA (hallazgo 71)

### Hallazgo 71: Seis errores silenciosos, cada uno reproducido antes y después

- **Problema**: la revisión del núcleo con reproducción propia encontró 6 bugs
  ALTA: (1) las ramas ToT perdían `prompt`/`context` desde el paso 2
  (`_generate_branches` leía el metadata del nodo actual, y solo la raíz los
  guarda); (2) con todas las ramas podadas ToT devolvía `valid=True` y camino
  vacío (la búsqueda devuelve la raíz, score 1.0 por construcción); (3)
  `run_analysis` se tragaba el `syntax_error` y reportaba «0 problemas»
  analizando código que no compila; (4) el prompt del informe no incluía
  ninguna fuente ni claim y sin embargo exigía citas `[1]`, `[2]`; (5)
  `credibility` no numérico (`"0.75"`, `null`) abortaba `research()` con un
  `ValueError` no capturado y, con `null`, registraba la evaluación dos veces;
  (6) la verificación independiente (CoVe) excluía el origen por `source_url`
  (lo que dijo el modelo) en vez de `source_id` (URL real que fija el
  extractor), re-incluyendo la fuente original.
- **Solución**: leer prompt/contexto de la raíz del árbol; `valid` exige camino
  no vacío (`valid = hay_camino and score >= umbral`); detener `run_analysis`
  con el error de sintaxis reportado por stderr; incluir fuentes
  (título/URL/snippet) y claims con veredicto y origen en el prompt del
  informe, con la instrucción de no inventar si la evidencia no alcanza;
  normalizar `credibility` a float acotado [0,1] (guardando `credibility_raw`
  cuando no es numérico) y registrar una sola evaluación; usar
  `source_id or source_url` como origen en CoVe.
- **Evidencia**: cada bug se reprodujo con script propio antes del cambio y se
  re-ejecutó después (paso 2 ToT: `prompt=''`→`'MI PREGUNTA'`; poda total:
  `valid=True`→`False`; sintaxis rota: «0 problemas»→error con motivo;
  informe: URL/título/snippet ausentes→presentes; `"0.75"`: aborto→0.75 sin
  abortar y una evaluación; CoVe: ORIGEN dentro→fuera y 1 alternativa). 7
  tests nuevos/ampliados; **414/414** OK en 3.11; ruff limpio; mutación
  re-medida: **73,9%** (2467/3340).
- **Hallazgo colateral**: `make mutation` no arrancaba desde que se añadió el
  evaluador (su test importa `evaluar_proyecto`, que el sandbox de mutmut no
  copia). Los tests de plugins ya se excluían por el mismo motivo; faltaba el
  nuevo. Se añadió `--ignore=tests/test_evaluar_proyecto.py` y la campaña
  volvió a correr entera.
- **Pendiente rutinario resuelto**: `requests` 2.33.0→**2.34.2** y
  `python-dotenv` 1.2.2→**1.2.4** (últimas verificadas en PyPI), lock
  regenerado con `uv` e instalado `--require-hashes` en venv aislado:
  414/414; openai 1.109.1/2.54.0/3.33.0 re-verificado con la suite actual.
- **Regla derivada**: cuando un prompt exige citas, el prompt debe llevar las
  fuentes citables; y todo flag `valid` debe exigir trabajo realmente
  ejecutado, nunca el score de un nodo raíz que no hizo nada.

### Hallazgo 72: Pase de coherencia «herramienta real» — asistente de pensamiento, sin silencios

- **Origen**: orden del programador (2026-10-17): el proyecto es una
  herramienta real —los modos demo offline son una ayuda para probar y
  comprender, no la naturaleza del proyecto— y todo debe ser coherente y
  consistente, con la máxima calidad. Queda registrado como regla 11 de
  `AGENTS.md` y este pase baja el cambio a código, tests, textos y cifras.
- **Qué se corrigió** (cada punto con test o medición):
  - `code_design_improvement_tools.run_analysis` gastaba hasta 49 llamadas LLM
    (7 fases repitiendo el ciclo de 7 pasos) y no se detenía ante un paso
    inválido: ahora es UN ciclo de 7 pasos validado paso a paso (corta con
    error explícito si un paso no produce resultado válido) y `max_steps` del
    motor es efectivo.
  - `pensamiento_layer.think()` ignoraba `use_tot` (sin enrutar a ToT) y
    `think_tot` perdía `return_tree`; un kwarg desconocido ahora eleva
    `TypeError` en vez de tragarse en silencio (P1.26).
  - `llm_providers`: cliente del SDK reutilizado por (clave, base_url) —antes
    se creaba uno por llamada, tirando el pool keep-alive—; OpenRouter
    recuerda el modelo que funcionó para no repetir la cascada de fallos; Kilo
    gana caché y timeout (60 s) como las rutas OpenAI.
  - `deep_research_system._parse_json_response` fallaba con varios bloques
    («{mal} luego [bien]») por regex codiciosa: ahora decodifica por posición y
    devuelve el primer JSON válido.
  - `ResearchContext.to_dict` declara `duration_seconds`; la URL de Wikipedia
    va percent-encoded; `_clean_url` rechaza hosts privados/localhost;
    `max_results <= 0` devuelve `[]`.
- **El propio evaluador como control**: la primera pasada marcó
  `c3_sin_silencios` por un `except`/`continue` recién introducido en
  `_parse_json_response` (P1.26); se reestructuró con un helper que devuelve
  `None`. Con `--sin-red`, `v4_dependencias_al_dia` queda sin verificar y la
  global baja a 0.925 (no verificado ⇒ fallo, coherente con P0.1). Con red:
  GLOBAL 1.000 y sin plan de mejora.
- **Evidencia**: **433/433** tests en Python 3.11 (openai 1.109.1) y en los
  venvs 2.54.0, 3.33.0 y 3.12+3.33.0; ruff limpio; demos offline 0; tests
  honestos 0; autoevaluación con `--ejecutar-tests` GLOBAL 1.000 (sin
  `no_verificado`); mutación re-medida: **73,9% (2602/3521; 0 timeouts, 0 sin
  ejecutar)**, `deep_research_system` 65,1% (680/1045); los seis módulos
  mutados quedan al 97-99% de cobertura (`llm_providers` 98%).
- **Anomalía observada y descartada por repetición**: una primera pasada de
  cobertura, en el minuto siguiente al final de la campaña mutmut, dio cifras
  no reproducibles (`llm_providers` 78%); dos repeticiones inmediatas dieron
  98% y se publica la medición reproducible (P0.1: nada se publica sin repetir
  la medición limpia).
- **Regla derivada**: ningún modo de compatibilidad (kwargs «extra», claves
  heredadas, fallbacks, ciclos anidados) puede tragarse errores ni multiplicar
  el trabajo; y cuando cambia el marco declarado del proyecto, el cambio baja a
  código, tests, textos y cifras en el mismo pase.

### Hallazgo 73: Cobertura al 100% y mutación del 78,1% — cerrar huecos, no disfrazarlos

- **Origen**: pase de mejoras eficientes del programador (2026-10-17):
  verificar HEAD en copia limpia, cerrar los 22 huecos de cobertura, reforzar
  la mutación en los módulos débiles y probar el pipeline real.
- **Cobertura**: de 22 líneas sin cubrir en los seis módulos mutados a 0.
  - Tests dirigidos para ramas reales: pasos inválidos 2–7 del ciclo de
    diseño; `max_steps > 7` (retorno final del ciclo); error de red sin status
    en OpenRouter (reintenta y eleva, sin fallback); JSON que no es objeto en
    `RelevanceJudge` y en CoVe; hostname vacío en `_clean_url`; `best_child`;
    contenido inválido puntuado 0 sin llamar al juez; BFS con poda total
    («Score bajo») y con `max_depth`; demo completa de `pensamiento_layer`.
  - Cuerpos `abstractmethod` (3) marcados `# pragma: no cover`: nunca se
    ejecutan.
  - Ramas muertas eliminadas con invariante demostrado: `raise last_error`
    inalcanzable en `_chat_completion` (el bucle siempre eleva en el último
    intento) y `return self._root` inalcanzable en BFS (la raíz está siempre
    en `_all_nodes` y todo árbol finito tiene hojas).
- **Demo ToT corregida**: el demo mostraba «Mejor camino» vacío porque MockLLM
  respondía al juez con un JSON genérico sin las claves esperadas y el juez
  puntuaba 0 (claves ausentes = 0). MockLLM ahora responde al prompt del juez
  con el esquema exacto (simulado, declarado): el demo muestra el camino y un
  test lo verifica.
- **Mutación**: 777 supervivientes frente a 919 (164 muertos más con 22
  mutantes nuevos): **78,1% (2766/3543)** desde 73,9% (2602/3521).
  `deep_research_system` 65,1→73,9% (772/1045) y `llm_providers`
  73,0→81,4% (429/527). Tests nuevos de prompts exactos (informe completo
  y evaluación), motivos CRAG exactos, salidas exactas de MockLLM,
  constructores y reintentos exactos.
- **Cadena y verificación real**: `make ci` OK en copia limpia de HEAD;
  `make vuln-scan` sin vulnerabilidades conocidas; sonda «Helo» 2,98 s
  (1 muestra, APTO); `test_openrouter_real.py` 3/3 (un 429 reintentado, sin
  fallback) con el modelo gratis.
- **Evidencia**: 463/463 tests (3.11 y 3.12; openai 1.109.1/2.54.0/3.33.0),
  ruff limpio, demos 0, tests honestos 0, cobertura 100% en los seis módulos
  mutados y autoevaluación GLOBAL 1.000 sin plan de mejora.
- **Regla derivada**: un stub simulado que alimenta a un evaluador debe
  responder con el esquema que ese evaluador parsea (si no, el silencio se
  convierte en puntuaciones 0 y demos vacíos); y una rama «defensiva» que no
  puede ocurrir se elimina con su invariante demostrado, no se cubre con un
  test artificial.

### Hallazgo 74: Un 1.000 no mide lo que el instrumento no pregunta — evidencia marcada y preflight determinista

- **Origen**: corte 1 (opción A) autorizado por el programador (2026-10-19)
  tras revisar cinco mejoras de vanguardia: la autoevaluación daba **GLOBAL
  1.000** y, sin embargo, no respondía ninguna de las preguntas de esas
  mejoras (procedencia de la evidencia, imports no declarados, silencios,
  duplicación, tareas asyncio sueltas). Un 1.000 describe solo lo que el
  instrumento pregunta.
- **Solución**:
  - `evidence.py`: tres tipos de procedencia excluyentes (`verified-real`,
    `verified-synthetic`, `unverified`) con marcadores estables y regla de
    promoción: lo real promociona; lo sintético solo con autorización explícita
    Y justificación no vacía (queda declarado y auditable); lo no verificado
    nunca promociona. Resumen formateado compartido.
  - `evaluar_proyecto.py`: cada `Hallazgo` lleva `tipo_evidencia` (real por
    defecto; `unverified` en «No se pudo comprobar en PyPI» y «Licencia no
    verificable»); el informe añade la clave `evidencia` y el texto imprime
    marcadores por hallazgo y la línea `Evidencia: ...`; el digesto del LLM
    también recibe los marcadores.
  - `scripts/preflight.py`: gate determinista, offline y read-only por AST —
    sintaxis, imports declarados en manifiesto (stdlib y locales exentos;
    alias dotenv/yaml), silencios `except: pass/continue/...`, duplicados
    sustanciales (>= 60 nodos AST, para no castigar envoltorios) y
    `asyncio.create_task`/`ensure_future` sin referencia. Integrado en
    `make check`, hook pre-commit, `make ci` y con tests propios.
- **Hallazgos reales del gate en el propio repositorio**: (1) `plugins/
  registry.py` importaba `toml` sin declararlo en ningún manifiesto (fallback
  de config `.toml`): sustituido por `tomllib` de stdlib y cubierto con un
  test; (2) `tests/test_evaluar_proyecto.py` duplicaba la fixture `_proyecto`
  en dos clases: extraída a `tests/helpers.crear_proyecto`. Los envoltorios de
  plugins comparten boilerplate intencional y quedan por debajo del umbral
  (documentado en el módulo).
- **Evidencia**: **500/500 tests** en Python 3.11 (34 nuevos: 15 de
  `evidence` y 19 de `preflight`, incluido el canario «el repositorio real
  pasa su propio preflight»), ruff limpio, `python3 scripts/preflight.py` →
  **OK (0 hallazgos)** sobre el repo, autoevaluación `--ejecutar-tests`
  **GLOBAL 1.000** con la línea de evidencia impresa, demos offline 0.
  Mutación no re-medida (los seis módulos de `source_paths` no cambiaron);
  3.12 y openai 2.54/3.33 pendientes de re-verificación.
- **Regla derivada**: cada instrumento de calidad solo responde a lo que
  pregunta: junto a la nota global debe publicarse SIEMPRE la procedencia de
  la evidencia y lo que no se verificó; y un gate determinista nuevo se valida
  sobre el propio repositorio (test canario) antes de exigírselo a terceros.

### Hallazgo 75: Separación estricta generador/verificador — la independencia se declara, no se finge

- **Origen**: corte 2 (mejoras de vanguardia, 2026-10-19): la segunda pasada
  CoVe de `EvidenceEvaluator` usaba SIEMPRE el mismo proveedor que generó y
  evaluó los claims —independencia de nombre, no de hecho— y no lo declaraba.
- **Solución**:
  - `EvidenceEvaluator` acepta `llm_verificador`: si es OTRO objeto, la pasada
    CoVe va a ese proveedor y el resultado declara
    `independencia: "proveedor-distinto"`; si es None o el mismo objeto, la
    pasada corre igual (compatibilidad) pero queda declarada
    `"mismo-proveedor"` —en el dict del resultado Y en el `decision_log`
    (`[mismo-proveedor]`/`[proveedor-distinto]`)—. Nunca se finge
    independencia que no existe.
  - `ResearchOrchestrator` y `ResearchOrchestratorWithThinking` propagan
    `llm_verificador`; el nombre del generador y del verificador viajan en el
    resultado por claim (`verificador`, `generador`).
- **Evidencia**: 5 tests nuevos (ruteo de la llamada CoVe al verificador,
  declaración de `mismo-proveedor` en dos casos, pass-through en ambos
  orquestadores) y 1 dict exacto actualizado; **505/505 tests** en Python
  3.11 (openai 1.109.1 y 2.54.0) y 3.12 (openai 3.33.0, venv aislado desde
  `requirements.lock`), ruff limpio, preflight 0, demos offline 0,
  `test_systems_honest`/`kilo`/`env` 0 y autoevaluación GLOBAL 1.000.
  honest_test 5/6 solo por `.env` ausente en el worktree (ambiental).
  Mutación re-medida (deep_research_system está en `source_paths`):
  **79,9% (2863/3582; 0 timeouts, 0 sospechosos, 0 sin ejecutar)**, desde
  78,1% (2766/3543): 39 mutantes más y 97 muertos más.
- **Regla derivada**: una independencia que comparte proveedor es una
  independencia degradada y debe declararse como tal en el MISMO artefacto
  que la consume; un parámetro nuevo que cambia el quién-verifica debe
  propagarse por TODOS los orquestadores que montan el pipeline (si no, la
  mitad de la superficie pública ignora la mejora).

### Hallazgo 76: Phase-chain freeze y consenso por muestreo — pilotos medidos, no adoptados a ciegas

- **Origen**: las dos mejoras restantes de la revisión de vanguardia
  (2026-10-19): congelar fases del razonamiento para que fases posteriores no
  reescriban las anteriores, y detectar alucinaciones por desacuerdo entre
  muestras repetidas del mismo prompt.
- **Solución (pilotos opt-in, comportamiento por defecto intacto)**:
  - `thinking_engine.StepThinkingEngine(congelar_fases=True)`: cada fase
    ejecutada se congela con su hash sha256 corto y las fases posteriores
    reciben un bloque `[FASES CONGELADAS — INMUTABLES]` (nombre, hash,
    contenido truncado) con la regla explícita de declarar contradicciones en
    la fase nueva sin reescribir las previas. El resultado incluye
    `fases_congeladas` e `inmutabilidad_verificada` (re-hash de lo devuelto:
    un consumidor que mute `steps` se detecta). ToT lo declara como no
    aplicable (`congelacion_fases: "no aplica a ToT..."` + aviso por stderr):
    las ramas son exploratorias por diseño. El ciclo de diseño de código no
    acepta el flag (TypeError explícito, no silencio).
  - `deep_research_system.EvidenceEvaluator(muestras_consenso>1)`: repite la
    evaluación del claim y declara `consenso_muestreo` (muestras, veredictos,
    `acuerdo`, `llamadas_extra`); veredictos divergentes ⇒
    `discrepancia_muestreo` y entrada `sampling_consensus: discrepancia` en el
    `decision_log` (revisión humana). Ambos orquestadores propagan el
    parámetro (lección del Hallazgo 75).
  - Benchmark dedicado `tests/benchmarks/consenso_muestreo.py` (offline,
    LLM simulado declarado).
- **Medición del benchmark (2026-10-19)**: caso divergente → `detectado:
  true`, `decision: discrepancia`, 3 llamadas reales y 2 extra declaradas;
  caso acuerdo → `falso_positivo: false`; por defecto → 1 llamada y consenso
  inactivo. El detector marca lo que debe y no marca lo que no debe, con el
  coste exacto publicado.
- **Evidencia**: 12 tests nuevos (6 de congelación + 6 de consenso/propagación),
  **517/517 tests** en Python 3.11 (openai 1.109.1 y 2.54.0) y 3.12 (openai
  3.33.0), ruff limpio, preflight 0, demos offline 0, autoevaluación
  GLOBAL 1.000. honest_test 5/6 solo por `.env` ausente en el worktree.
  Mutación re-medida (cambiaron `thinking_engine` y `deep_research_system`):
  **79,8% (3022/3789; 0 timeouts, 0 sospechosos, 0 sin ejecutar)**, desde
  79,9% (2863/3582): 207 mutantes más y 159 muertos más.
- **Regla derivada**: un detector de alucinaciones se publica con su medición
  (detección, falsos positivos y coste) o no se publica; y una mejora que
  cambia el prompt de fases posteriores debe declarar qué partes de la
  superficie (ToT, ciclo de diseño) NO la aplican, en el mismo artefacto.

### Hallazgo 77: La deriva puede estar en el entorno, no en el repo — verificar lo instalado contra el lock

- **Origen**: revisión general del proyecto (2026-10-19). La autoevaluación
  offline (`--sin-red`) devolvió 0.958 con `v4_dependencias_al_dia` en NO, y
  el estado del 2026-10-16 aún listaba «actualizar requests/python-dotenv»
  como decisión pendiente.
- **Diagnóstico**: ese pendiente ya se había aplicado en el repo el 2026-10-17
  (Hallazgo 71): `requirements.txt` y `requirements.lock` fijaban
  `requests==2.34.2` y `python-dotenv==1.2.4`. Lo desactualizado era el
  **entorno instalado** (2.33.0/1.2.2): la suite pasaba igual porque ningún
  test depende del cambio, así que la deriva era invisible para los tests. Y
  el `v4` en NO offline es el instrumento funcionando (no verificado ⇒ fallo,
  Hallazgo 72), no una dependencia por detrás.
- **Solución**: `python3 -m pip install --require-hashes -r
  requirements.lock` y verificación de lo instalado con
  `importlib.metadata.version` (no `modulo.__version__`: `dotenv` no lo
  expone — comprobado). Efecto colateral declarado: el user-site es
  compartido con otros proyectos y pip avisó de conflictos ajenos (`ccxt`
  fija `certifi`/`idna`/`charset-normalizer` exactos; `betterocr` pide
  `pandas<3` con pandas 3.0.6 ya presente, preexistente a esta sesión). No se
  tocaron: pertenecen a otros proyectos (P1.2).
- **Evidencia**: 517/517 tests con `requests 2.34.2` / `python-dotenv 1.2.4`,
  ruff 0, preflight 0, demos offline 0, `make vuln-scan` «No known
  vulnerabilities found», autoevaluación con red **GLOBAL 1.000** (sin plan de
  mejora, `no_verificado` vacío, licencias de las 4 dependencias consultadas
  en PyPI).
- **Regla derivada**: «dependencias al día» se comprueba en DOS sitios —
  manifiesto/lock contra PyPI Y entorno instalado contra el lock
  (`pip install --require-hashes` es idempotente: sirve como verificación); y
  un NO del evaluador en modo `--sin-red` sobre un criterio que exige red se
  lee como «no verificado», no como «por detrás».

## 2026-10-20 (ronda 15) — El evaluador pregunta más: imports declarados, tests que pueden fallar y decisiones registradas (hallazgos 78–82)

### Hallazgo 78: Añadir un criterio al evaluador halla defectos propios — y el instrumento se aplica a sí mismo desde el primer commit

- **Origen**: petición de mejorar la evaluación de proyectos ajenos en
  decisiones, requerimientos, coherencia y consistencia. Se añadieron tres
  criterios a `evaluar_proyecto.py`: `h6_imports_declarados` (reutiliza el
  gate AST de `scripts/preflight.py`: cada import de terceros debe estar en
  el manifiesto — cierra el límite declarado «solo se ven dependencias
  declaradas», con la salvedad de los imports dinámicos, que se declara),
  `c5_tests_con_aserciones` (AST: toda función `test_*` debe poder fallar;
  regla propia 4) y `h7_decisiones_documentadas` (señal estructural:
  ADR/lecciones/CHANGELOG/`decision_log`; se declara NO veredicto).
- **Diagnóstico**: el criterio nuevo, aplicado al propio repo, encontró 3
  tests sin aserciones en `test_plugin_system.py` (`test_hot_reload`,
  `test_dashboard`, `test_config_loading`): imprimían estado pero no podían
  fallar. Uno llevaba un comentario que contradecía el comportamiento real
  («usage should reset» cuando `registry.py` comparte la metadata con la
  instancia para que las estadísticas SOBREVIVAN la recarga — por diseño,
  línea de `instance.metadata = entry.metadata`): se asertó la invariante
  real y se corrigió el comentario (P1.10). Además, el primer borrador del
  propio criterio c5 violó P1.26 (`except SyntaxError: continue` silencioso)
  y lo cazó `preflight` en la misma sesión: ahora los archivos de test que
  no parsean se devuelven y se declaran en el informe, no se saltan en
  silencio.
- **Evidencia**: 524/524 tests (7 nuevos), ruff 0, preflight 0, demo
  `test_plugin_system.py` en verde, autoevaluación con los tres criterios en
  OK (`python3 evaluar_proyecto.py . --sin-red --ejecutar-tests`) y 7 tests
  nuevos que plantan cada defecto en una fixture (import no declarado,
  import declarado, stdlib/local sin declarar, test con `assert`/`raises`,
  tests vacío y de solo impresión, sin registro de decisiones, con
  LECCIONES/`decision_log`).
- **Regla derivada**: todo criterio nuevo del evaluador se exige de
  inmediato al propio repo en `TestAutoevaluacionDeThinker` (quien mide debe
  quedar medido); y un comentario que afirma un comportamiento es una
  afirmación sujeta a P0.1: se verifica ejecutando antes de convertirlo en
  aserción.

### Hallazgo 79 (ambiental): el binario `coverage` del PATH puede no ser del intérprete del proyecto

- **Origen**: al medir cobertura el 2026-10-20, `coverage run --source=. -m
  unittest discover -s tests` (la forma documentada) colectó solo 453 tests
  con 27 errores falsos (`patch("openai.OpenAI")` fallaba).
- **Diagnóstico**: el binario `coverage` del PATH pertenece al Python 3.10
  empaquetado con Blender (`/opt/blender/...`), sin las dependencias del
  proyecto. No era una regresión: con `python3 -m coverage` (mismo
  intérprete que la suite) los 524 tests pasan y la cobertura es la real.
- **Regla derivada**: las herramientas Python se invocan como
  `python3 -m <herramienta>` (coverage, pip, ruff si aplica) para garantizar
  el intérprete correcto; un binario suelto del PATH es una afirmación no
  verificada sobre QUÉ Python lo respalda.

### Hallazgo 80: La tasa de mutación puede moverse SIN cambiar las fuentes — publicar fecha, conteo crudo y varianza

- **Origen**: re-medición de la campaña mutmut el 2026-10-20 (autorizada por
  el programador) tras los criterios nuevos del evaluador, que NO tocan
  ninguno de los seis módulos de `source_paths` ni los tests de la campaña
  (`tests/test_evaluar_proyecto.py` está en la lista de exclusión).
- **Medición**: **78,0% (2957/3789; 0 timeouts, 0 sospechosos, 0 sin
  ejecutar)**, dos pasadas completas el mismo día con el mismo resultado
  (832 supervivientes en ambas). La cifra documentada del 2026-10-19 era
  79,8% (3022/3789): −65 muertos con fuentes y configuración idénticas.
  Desglose: `llm_providers` clavado (98 supervivientes ambos días); la
  variación se concentra en `deep_research_system` (273 → 312
  supervivientes, +39).
- **Diagnóstico**: causa de la cifra del 2026-10-19 NO determinada. Descartado
  con evidencia: cambio de fuentes (git diff vacío en los seis módulos),
  cambio de configuración (`pyproject.toml` intacto), cambio en los tests de
  la campaña (exclusiones intactas), aleatoriedad evidente en los tests (solo
  un `random.uniform` y va parcheado) y **versión de la dependencia openai**:
  una tercera pasada el 2026-10-20 ya con openai 3.35.1 dio exactamente el
  mismo resultado (2957/832) que las dos con 3.33.0 — la medición actual es
  reproducible (3 pasadas, 2 versiones de openai, mismo conteo). La medición
  del 2026-10-19 se hizo ANTES de alinear el entorno con el lock (commit de
  las 15:23; la alineación del Hallazgo 77 fue a las 20:47), con versiones
  instaladas no registradas: no reproducible a posteriori. Se declara la
  deriva en vez de inventarle una explicación (P0.2).
- **Regla derivada**: toda cifra de mutación publicada lleva fecha y conteo
  crudo (muertos/total), y una re-medición que difiera con fuentes
  idénticas se reporta como DERIVA con su desglose por módulo — nunca se
  «ajusta» la cifra anterior ni se maquilla la nueva.

### Hallazgo 81: Cierre de pendientes 2026-10-20 — cobertura portable, openai al día, APIs reales y vuln-scan

- **Origen**: cierre de todos los pendientes declarados en la sesión del
  2026-10-20, autorizado por el programador (incluida la instalación).
- **Hecho y evidencia**:
  - Comando de cobertura en AGENTS.md corregido a `python3 -m coverage ...`
    (el binario suelto del PATH era del Python 3.10 de Blender — Hallazgo 79;
    el Makefile ya usaba la forma correcta: la incoherencia era solo del doc).
  - `make vuln-scan` (pip-audit sobre `requirements.lock`, con red): **«No
    known vulnerabilities found»**.
  - API real OpenRouter (`test_openrouter_real.py`, modelo `:free`, coste 0):
    **3/3 comprobaciones** (pipeline end-to-end: 3 subpreguntas, 6 claims, 6
    evaluaciones, reporte de 5166 chars).
  - Sonda de modelo (`scripts/probe_model.py --samples 5`): **APTO** — 5/5
    respuestas, mediana 2,88 s, máx 5,92 s, 0 por encima de 60 s (regla 10).
  - Ollama (`test_ollama_real.py`): servidor no disponible ⇒ prueba
    **OMITIDA** (declarado; no se simula).
  - openai subido a **3.35.1** en `requirements.lock`
    (`uv pip compile --upgrade-package openai`): 524/524 en Python 3.11 y en
    3.12.3 (venv `/tmp/thinker-venv312` recreado desde el lock con hashes).
    Autoevaluación con red: **GLOBAL 1.000**, `no_verificado` vacío, «nada
    que proponer».
  - Efecto colateral declarado: pip repite el aviso preexistente de conflicto
    ajeno (`betterocr` pide `pandas<3` con pandas 3.0.6 en el user-site);
    pertenece a otro proyecto y no se toca (P1.2).
- **Regla derivada**: «cerrar todo» incluye re-verificar lo que cambia de
  estado por el propio cierre (subir openai ⇒ re-correr la autoevaluación con
  red, porque `v4` depende de la versión fijada); y toda prueba opt-in que no
  puede correr se reporta como OMITIDA, nunca como verde.

### Hallazgo 82: Paquete instalable y callable desde otros proyectos — el flat-layout exige declarar py-modules y packages explícitos

- **Origen**: petición del programador (2026-10-20): que el proyecto evalúe y
  recomiende a otros proyectos Y que otros proyectos puedan llamarlo y usar
  sus funcionalidades, investigando primero en internet.
- **Investigación**: la guía oficial de setuptools sobre [package
  discovery](https://setuptools.pypa.io/en/latest/userguide/package_discovery.html)
  confirma que el flat-layout con varios módulos/paquetes de nivel raíz hace
  que el auto-descubrimiento SE NIEGUE a empaquetar («multiple top-level
  packages/modules»); la práctica estándar es declarar `py-modules` y
  `packages` explícitos en `[tool.setuptools]`.
- **Estado previo real**: `pyproject.toml` ya tenía `[project]` con scripts de
  consola (`think`, `research`, `code-design`, `bench`), pero SIN
  `[build-system]` ni declaración de módulos: el empaquetado nunca se había
  probado de verdad (declarado ≠ verificado, P0.1).
- **Solución**: `[build-system]` (setuptools>=77), `py-modules` con los 8
  módulos del núcleo, `packages` con `plugins*`/`scripts`/`tests.benchmarks`
  (los subpaquetes sin `__init__.py` se instalan como namespace packages PEP
  420) y el script de consola nuevo `evaluate-project =
  evaluar_proyecto:main`. README documenta el uso como librería y como
  herramienta, incluida la nota honesta de que `PluginRegistry` usa rutas
  relativas por defecto (desde otro proyecto se pasan `plugin_dirs` y
  `config_path` explícitos).
- **Evidencia end-to-end**: `pip install .` en venv limpio (Python 3.12.3);
  desde `/tmp` (otro cwd): `evaluate-project /tmp/proyecto_ajeno --sin-red`
  evalúa y detecta los defectos plantados (h6 import sin declarar, c5 test
  vacío, h7 sin registro de decisiones — GLOBAL 0.344 con 19 propuestas);
  imports de librería `evaluar()`, `DeepResearchThinkingLayer.think()` y
  `ResearchOrchestrator.research()` funcionan offline con mocks; `think` como
  comando funciona. Suite 524/524, ruff 0, preflight 0 tras el cambio.
- **Incidente honesto**: el primer intento de prueba de librería usó
  `PensamientoLayer`, nombre INVENTADO (la clase real es
  `DeepResearchThinkingLayer`): ImportError inmediato. Regla reforzada: ni
  en una prueba rápida se escribe un nombre de API sin grep previo (P0.2).
- **Regla derivada**: todo proyecto que declare scripts de consola o
  empaquetado debe probar la instalación en un venv limpio y la llamada
  desde OTRO directorio; «declarado en pyproject» no es «instalable».


### Hallazgo 83: Un paquete raíz llamado `tests` en site-packages colisiona con cualquier otro proyecto

- **Origen**: revisión post-empaquetado (2026-10-20, aprobada por el
  programador): `pip install .` instalaba `tests` y `tests.benchmarks` como
  paquetes de nivel raíz en site-packages solo para dar servicio al console
  script `bench`.
- **Problema**: `tests` es un nombre raíz genérico: si otro paquete instalado
  hace lo mismo (práctica desaconsejada pero habitual), ambos se pisan en
  site-packages y el import resuelve al equivocado. La guía de empaquetado de
  PyPA desaconseja instalar paquetes raíz con nombres genéricos.
- **Solución**: `tests` y `tests.benchmarks` fuera de `[tool.setuptools]
  packages` y el console script `bench` eliminado; el benchmark se ejecuta
  desde el repo con `python3 -m tests.benchmarks.run_bench` (forma ya
  documentada en `docs/REFERENCIAS-IA.md`). `scripts` SÍ se queda instalado:
  `evaluar_proyecto.py` importa `scripts.preflight` (dependencia dura
  verificada con grep), quitarlo rompería `h6_imports_declarados` en la
  instalación.
- **Evidencia**: reinstalación en venv limpio (Python 3.12.3): `import tests`
  ya NO resuelve desde otro directorio (0 entradas `tests/` en el RECORD del
  dist-info), `from scripts.preflight import cargar_modulos, revisar_imports`
  SÍ funciona, `evaluate-project /tmp/proyecto_ajeno --sin-red` sigue
  detectando los defectos plantados (GLOBAL 0.344) y `python3 -m
  tests.benchmarks.run_bench --list` funciona desde el repo. Suite 524/524,
  ruff 0, preflight 0, autoevaluación con red GLOBAL 1.000.
- **Incidente honesto**: la PRIMERA reinstalación siguió mostrando `tests`
  importable: setuptools reutilizó el `build/lib` y el `.egg-info` de la
  compilación anterior (artefactos stale: `build_py` copia lo nuevo pero NO
  elimina paquetes retirados). Lo cazó la propia verificación (import desde
  otro cwd + inspección del RECORD). Solución: apartar los artefactos
  regenerables a `/tmp` (movidos, no borrados — P0.3) y recompilar.
- **Regla derivada**: al empaquetar, cada paquete raíz instalado debe
  justificar su nombre (¿colisionaría en site-packages?) y cada console
  script debe justificar su existencia (¿el mismo resultado se obtiene con
  `python3 -m ...` desde el repo?). Lo que solo sirve para desarrollo no se
  instala. Y tras cambiar `packages`/`py-modules`, la verificación de la
  instalación solo es válida partiendo de artefactos de build limpios:
  setuptools no limpia `build/` entre compilaciones.


### Hallazgo 84: Triaje de los 832 supervivientes — y 4 trampas de mutmut 3.6.0 que invalidan verificaciones si se ignoran

- **Origen**: petición del programador (2026-10-20): cerrar todos los
  pendientes; el mayor era investigar uno a uno los supervivientes de la
  medición 78,0% (2957/3789). Se repartieron los 6 módulos mutados entre
  agentes en paralelo con el protocolo apply → test FALLA → restore → test
  PASA.
- **Resultado del triaje** (verificado mutante a mutante): de los 832
  supervivientes listados, ~650 mueren con tests honestos nuevos (177 tests
  añadidos en 6 archivos; la suite pasa de 524 a 701) y el resto son
  **mutantes equivalentes** documentados con su razón (decenas de ellos:
  argumentos internos del `raise JSONDecodeError` absorbidos por el mismo
  `except`, defaults redundantes, dead stores, codecs case-insensitive).
  El listado `mutmut results` estaba además desactualizado: decenas de
  "survived" ya morían con la suite anterior (p. ej. 37 de 165 en
  code_design_improvement_tools).
- **Trampa 1 — `mutmut apply` emplaza mal mutantes de métodos con nombre
  repetido**: un mutante de `SubClase.metodo` se inserta en la PRIMERA
  función con ese nombre del archivo (p. ej. el método abstracto o la de
  otra clase), no en la que ejecuta el trampoline. Toda verificación basada
  en `mutmut apply` para métodos `__init__`/`search`/`decide`/`generate` es
  inválida en este repo: hay que aplicar a mano el diff exacto de
  `mutmut show` (los agentes usaron un aplicador propio por AST) y
  restaurar tras cada uno. Esta trampa produjo falsos MUERTO en las
  primeras pasadas, corregidos al re-verificar.
- **Trampa 2 — `.pyc` stale resucita mutantes**: `git checkout` que restaura
  el archivo en el mismo segundo y con el mismo tamaño deja válido el
  bytecode mutado en `__pycache__` (suite en rojo fantasma). Antídoto:
  `touch` del archivo tras restaurar.
- **Trampa 3 — `mutmut apply` en paralelo contamina verificaciones ajenas**:
  un agente con un mutante aplicado en su módulo mientras otro ejecuta la
  suite produce falsos DEAD/VIVO en el módulo del segundo (8 falsos DEAD
  detectados y re-verificados limpios). Las pasadas apply/test/restore
  deben serializarse entre agentes, o cada verificación debe re-ejecutarse
  tras confirmar que todos los archivos están restaurados.
- **Trampa 4 — el gate `c5_tests_con_aserciones` exige la aserción en el
  cuerpo del test**: aserciones delegadas en helpers (`self._helper(...)`)
  se marcan como "test sin aserciones". Inlinear la aserción o nombrar el
  helper `test_*` no vale; la aserción debe estar en el cuerpo.
- **Reglas derivadas**: (1) nunca confiar en `mutmut results` de una
  campaña anterior: re-medir antes de triar; (2) verificación de mutantes =
  diff de `show` aplicado en la ubicación real + restore + `touch` +
  re-ejecución; (3) en campañas paralelas, la verificación final de cada
  módulo se hace con TODOS los archivos restaurados.
- **Medición oficial post-triaje (2026-10-20)**: **94,1% (3567/3789; 222
  supervivientes, 0 timeouts, 0 sospechosos, 0 sin ejecutar)**, con la misma
  exclusión de `print`. Los 222 supervivientes corresponden en su gran
  mayoría a los equivalentes documentados por los 6 agentes (más la clase
  "prompt-literal" de textos de demo, no observable). Suite: 701/701 en
  Python 3.11 y 3.12; ruff 0; preflight 0.


### Hallazgo 85: El triaje de mutantes como detector de código muerto — y el nombre de PyPI como decisión de identidad

- **Origen**: petición del programador (2026-10-21): cerrar todas las
  mejoras pendientes, incluidas las anomalías de código que destapó el
  Hallazgo 84, y dejar el paquete listo para PyPI.
- **Anomalías corregidas** (todas detectadas porque sus mutantes eran
  equivalentes — la mutación señala código que no cambia el comportamiento):
  1. `thinking_engine`: parámetros muertos `prompt`/`context` de
     `_bfs_search`/`_dfs_search`/`_beam_search` y `context` de
     `_generate_branches` eliminados (los datos viven en la metadata de la
     raíz, que es de donde se leen de verdad); metadata solo-escrita
     (`is_root`, `builder_output`) retirada; `parent=`/`depth=` redundantes
     del constructor (los pisa `add_child`) eliminados.
  2. `deep_research_system:186`: dead store `query = queries[0]` eliminado
     (el `for` reasigna siempre).
  3. `llm_providers:240`: literal `{429, 500, 502, 503, 504}` duplicado
     sustituido por la constante `TRANSIENT_STATUS` ya existente.
  4. `code_design_improvement_tools.analyze_python_code`: solo capturaba
     `OSError`; un archivo no-UTF-8 propagaba `UnicodeDecodeError` rompiendo
     el contrato `{"error": ...}`. Ahora captura ambos (con test que lo
     fija).
  5. `code_design_improvement_tools`: la métrica `max_nesting` se
     inicializaba a 0 y nunca se calculaba. Implementada de verdad
     (`_max_nesting`: profundidad de bloques de control vía AST) con tests
     (plano=0, tres niveles=3).
- **Decisión NO cambiada**: `CodeAnalysisContext.design_decisions` se
  mantiene aunque el módulo no lo usa: es atributo público del contexto
  (consumidores de la librería pueden rellenarlo) y un test fija su
  contrato de inicialización; borrar API pública por limpieza interna sería
  peor que el peso muerto.
- **PyPI**: el nombre `thinker` está ocupado desde 2017 por otro autor
  (verificado contra la API de PyPI). El programador eligió
  **`thinker-research`** (libre: 404 en la API el 2026-10-21). `pyproject`
  renombrado, `python -m build` regenera `thinker_research-0.1.0` (sdist +
  wheel) y `twine check` PASA; wheel reinstalado en venv limpio y verificado
  (imports + `evaluate-project` desde otro directorio). La SUBIDA queda
  pendiente de las credenciales del programador (token PyPI en el entorno;
  no se piden por chat, P0.6). Comando cuando las tenga:
  `python3 -m twine upload dist/*` (recomendado ensayar antes en TestPyPI).
- **Evidencia**: suite 703/703 (2 tests nuevos de `max_nesting` y 1 de
  UnicodeDecodeError), ruff 0, preflight 0. Re-medición de mutación tras
  tocar 4 de los 6 módulos mutados: **94,7% (3570/3769; 199 supervivientes,
  0 timeouts, 0 sospechosos, 0 sin ejecutar)** — el total baja de 3789 a
  3769 porque la limpieza eliminó ~20 mutantes de código muerto.
- **Regla derivada**: un mutante equivalente no siempre pide un test mejor;
  a veces señala código que no debería existir. Antes de clasificar un
  equivalente como "aceptado", preguntarse si la línea mutada tiene
  justificación para seguir ahí.


### Hallazgo 86: `elif` no es un nivel de anidamiento — y `try/except*`/`match` también son bloques de control

- **Origen**: revisión de los cambios de las últimas 12 horas (2026-10-21).
  El test de `max_nesting` cubría código plano y tres niveles reales, pero no
  `elif`.
- **Problema**: la documentación oficial de `ast` confirma que `elif` no
  tiene nodo propio: se representa como un `If` dentro de `orelse`
  (<https://docs.python.org/3/library/ast.html#ast.If>). La recursión
  genérica lo contaba como un nivel nuevo; `if/elif/elif` plano devolvía 3
  en vez de 1.
- **Solución**: `_max_nesting` no incrementa cuando el `If` está en `orelse`
  y comparte `col_offset` con el `if` padre (elif); un `if` dentro de un
  `else` real sí suma. Se añadieron `ast.TryStar` (`except*`) y `ast.Match`
  como bloques de control.
- **Evidencia**: antes `if/elif/elif -> 3`; después `-> 1`; `else` con `if`
  anidado `-> 2`; `try/except*` y `match` planos `-> 1`, con `if` dentro
  `-> 2`. Suite 706/706, ruff 0, preflight 0; mutación **94,7%
  (3581/3780; 199 supervivientes, 0 timeouts, 0 sospechosos)**: no queda
  ningún superviviente en `_max_nesting`; los 11 mutantes nuevos se matan y
  la tasa se mantiene.
- **Regla derivada**: una métrica basada en AST necesita casos límite
  (`elif`, `else`, `except*`, `match`), no solo el caso feliz; la fuente de
  verdad es la representación real del AST, no la forma del texto.


### Hallazgo 87: las cifras también viven en el README — la coherencia no termina en AGENTS.md

- **Origen**: revisión 2026-10-21. El commit `da5aa31` decía «cifras al día»
  y actualizó `AGENTS.md`/`EVALUACIONES.md`, pero el README seguía con la
  medición de mutación de 2026-10-19 (79,8%) y con `openai` hasta 3.33.0.
- **Problema**: la vitrina del proyecto mostraba cifras obsoletas; una
  lectura rápida podía concluir que la suite era mucho más débil de lo que
  es. Contradice la regla propia 11 y P1.10.
- **Solución**: README con la medición vigente, historial de mediciones y
  `openai 3.35.1`; aclaración de que la distribución es `thinker-research`
  (`thinker` está ocupado en PyPI desde 2017, verificado en la API).
- **Evidencia**: `grep` de las cifras antiguas; suite 706/706. Los artefactos
  `dist/` de `0.1.0` no se regeneraron con esta corrección: el tag `v0.1.0`
  apunta al commit anterior y regenerar el mismo número rompería la
  correspondencia versión/tag. La corrección se preparó como `0.1.1` (build
  + `twine check` PASSED) y se etiquetó/empujó; sus textos decían «tag
  pendiente» al construirse, así que `0.1.2` corrige la documentación
  (Hallazgo 89). `0.1.1` no se publicó en PyPI.
- **Regla derivada**: al cerrar un hito, buscar la cifra anterior en TODO el
  repo (`grep`) y actualizar solo las afirmaciones vigentes; las históricas
  se conservan con su fecha.


### Hallazgo 88: `uv pip compile` reutiliza la caché — refrescar el paquete antes de dar el lock por actualizado

- **Origen**: actualización de seguridad de `certifi` 2026.7.22 → 2026.10.19
  (PYSEC-2026-4320), commit `be14329`.
- **Problema**: `make lock` a secas no actualizó `certifi`: uv reutilizó la
  caché del índice. La regeneración solo cambió la versión y los hashes
  esperados tras refrescar ese paquete.
- **Solución**: `uv pip compile --generate-hashes ... --refresh-package
  certifi` (el header del lock registra el flag); `--upgrade-package` es la
  opción documentada para actualizar un paquete concreto. Verificado que el
  diff del lock solo tocaba `certifi`.
- **Evidencia**: `make vuln-scan` «No known vulnerabilities found»; suite
  706/706; `pip check` global con 15 avisos de paquetes ajenos (`ccxt`,
  `betterocr`, `torchaudio`, `opentelemetry`, `gruut`, `tts`, `flake8` y
  `code2prompt_rs`); el venv del proyecto está limpio. Los conflictos de
  `ccxt`/`betterocr` ya se declararon en el Hallazgo 77.
- **Regla derivada**: un lock generado no garantiza que las versiones estén
  al día; tras un aviso de seguridad, refrescar explícitamente el paquete,
  regenerar y revisar el diff (no solo el exit code).


### Hallazgo 89: no escribas «tag pendiente» en el commit que vas a etiquetar

- **Origen**: release `0.1.1` (2026-10-21). El commit `a56e0b8` se etiquetó
  y empujó como `v0.1.1` después de construir los artefactos.
- **Problema**: README, AGENTS y PUBLICACION decían «preparada localmente»,
  «pendiente de tag» y «la última etiquetada es v0.1.0». Al crear el tag, el
  texto del commit y el METADATA del wheel `0.1.1` pasaron a contradecir la
  realidad. Además, `v0.1.1` quedó como tag ligero frente al `v0.1.0`
  anotado.
- **Solución**: no reescribir el tag empujado ni reconstruir la misma
  versión. Se preparó `0.1.2` con textos durables (sin estados
  transitorios), tag anotado y build desde el tag; `0.1.1` queda como tag de
  git, no se publicó en PyPI.
- **Evidencia**: `git cat-file -t v0.1.0` = `tag` y `v0.1.1` = `commit`;
  `unzip -p dist/thinker_research-0.1.1-py3-none-any.whl
  thinker_research-0.1.1.dist-info/METADATA | grep` mostró «preparada
  localmente/última etiquetada v0.1.0»; PyPI respondió 404 y
  la consulta de releases vía CLI de GitHub = «release not found»; suite
  706/706 en 3.11 y 3.12 (venv desde el lock), `git archive v0.1.1` 706/706;
  `pip check` del
  venv limpio y global con 15 conflictos ajenos.
- **Regla derivada**: en el commit de release, evitar afirmaciones sobre el
  tag que aún no existe; usar frases durables o actualizar después. Crear
  tag anotado y verificar `git tag --points-at HEAD`/`git ls-remote` antes
  de anunciar la instalación.


### Hallazgo 90: el README de una release no puede declarar «PyPI pendiente» si se va a publicar

- **Origen**: preparación de `0.1.2` (2026-10-21). El README empaquetado
  decía «La publicación en PyPI como `thinker-research` sigue pendiente de
  credenciales» y «Mientras no haya PyPI, esa es la vía sin keys».
- **Problema**: `twine check` pasaba, pero PyPI usa el README como
  descripción del proyecto. Al subir `0.1.2`, la ficha habría dicho que PyPI
  estaba pendiente justo después de publicarla. Es el mismo error de estado
  transitorio del Hallazgo 89, ahora en el texto que ve el usuario de PyPI.
  `0.1.2` ya estaba etiquetado y empujado: rehacerlo habría roto la
  correspondencia versión/tag.
- **Solución**: preparar `0.1.3` (solo documentación) con una formulación
  durable: la instalación por tag no requiere PyPI y la de PyPI se presenta
  como «cuando la versión esté publicada». No se afirma disponibilidad ni
  ausencia de publicación. La guía de publicación deja de usar la CLI de
  GitHub (regla propia 12); las releases se crean desde la web.
- **Evidencia**: METADATA de `0.1.2` (líneas 86–89) contenía «sigue
  pendiente»/«Mientras no haya PyPI»; `0.1.3` contiene `Name:
  thinker-research`/`Version: 0.1.3` y ya no contiene esas frases. Suite
  706/706, ruff 0, preflight 0, build + `twine check` PASSED (wheel y sdist),
  wheel instalado en venv temporal con imports OK y `evaluate-project --help`
  OK. `0.1.2` no se publica; `0.1.3` se publicó en TestPyPI y PyPI.
- **Regla derivada**: antes de publicar, revisar el METADATA del wheel y el
  README empaquetado, no solo el README del árbol. Todo texto de release
  debe ser verdad antes y después de la publicación: evitar «pendiente»,
  «preparada» o «disponible» como estados, y usar condicionales o hechos
  estables.


### Hallazgo 91: la ficha JSON de PyPI no garantiza que el pip local resuelva la versión

- **Origen**: publicación de `0.1.3` (2026-10-21). Tras subir wheel y sdist,
  la API JSON de PyPI y el índice simple mostraban `0.1.3` y los hashes
  correctos, pero `pip install thinker-research==0.1.3` con la configuración
  por defecto respondió «from versions: none».
- **Problema**: un fallo de resolución local puede parecer un fallo de
  publicación. No se determinó la causa (caché, propagación o un índice
  configurado en el entorno); no se tocó la configuración global. Con
  `--index-url https://pypi.org/simple/ --no-cache-dir` la instalación
  funcionó, con imports OK y `pip check` limpio.
- **Solución**: para verificar una publicación, contrastar JSON, índice
  simple y hashes; si pip no ve la versión, forzar el índice oficial y
  desactivar la caché antes de concluir que la subida falló. No cambiar la
  configuración global sin orden (P0.5/P1.9).
- **Evidencia**: PyPI JSON 200/`0.1.3`; índice simple con
  `thinker_research-0.1.3-py3-none-any.whl` y `.tar.gz`; hashes
  `7622495bd4976d937dc7892f5aea93674fc867260cda6965db2ed1549616aa4e` y
  `f8bf541c3898ef779aa374e3f0d2774acb6ab526aba962deccaa997c171b400f`;
  instalación limpia desde PyPI y `pip check` sin conflictos.
- **Regla derivada**: separar «publicado en el índice» de «resuelto por el
  pip local»; anotar el comando exacto que funcionó y no atribuir la causa
  sin diagnóstico.


### Hallazgo 92: una opción de configuración sin prueba puede no hacer nada

- **Origen**: revisión del 2026-10-21. El 100% de cobertura en los 6 módulos
  núcleo no cubría el subsistema de plugins (64-97%) ni el CLI del evaluador.
- **Problema**: cuatro defectos silenciosos reproducidos con un script antes
  de tocar código:
  1. `params.max_results` de `config/plugins.yaml` se ignoraba:
     `search(query)` pasaba siempre 5 y la configuración no tenía efecto.
  2. `DuckDuckGoSearchPlugin` declaraba `beautifulsoup4` como dependencia,
     pero `web_search.py` extrae el HTML con regex y el paquete no está en
     `requirements.txt`: dependencia inventada (P0.2).
  3. `archivos_python` filtraba por las partes ABSOLUTAS de la ruta: un
     proyecto alojado en `.../build/proyecto` producía 0 archivos y un
     informe vacío.
  4. `reload_plugin` reutilizaba la configuración fusionada antigua y no
     invalidaba la caché: editar `config/plugins.yaml` y recargar no cambiaba
     nada, aunque el hot-swap promete aplicarla.
- **Solución**: límite común en `SearchProviderPlugin.search` (un solo
  método, sin duplicar; `max_results=None` usa `params.max_results`);
  dependencia declarada solo `requests`; `archivos_python` compara las partes
  relativas al proyecto; el registro cachea por `mtime_ns`, invalida al
  recargar, relee el YAML y conserva los overrides pasados por código.
  `main()` del evaluador acepta `argv` para poder probar el CLI real.
- **Evidencia**: reproducción antes → después: `[5] → [1]`;
  `['requests','beautifulsoup4'] → ['requests']`; `0 → 1` archivos bajo
  `build/`; config `uno/uno → uno/dos` tras editar y recargar. Suite
  **724/724** en Python 3.11 y 3.12 (venv del lock, openai 3.35.1), ruff 0,
  preflight 0; cobertura de plugins: openrouter 97%, deepseek 79% (antes
  65/64%) y `web_search`/núcleo siguen al 100%.
- **Regla derivada**: toda opción documentada en configuración debe tener una
  prueba que demuestre que CAMBIA el comportamiento; un «hot-reload» se
  verifica editando el archivo y recargando, no solo llamando a recargar.


### Hallazgo 93: «no verificado» contado como éxito y manifiestos mal parseados

- **Origen**: revisión del 2026-10-21 con la auto-evaluación del propio
  proyecto (`evaluar_proyecto.py`). El informe daba `v4_dependencias_al_dia`
  por bueno sin consultar PyPI, y los manifiestos generaban dependencias
  inexistentes.
- **Problema**: tres defectos reproducidos antes de tocar código.
  1. `evaluar_vigencia` solo comparaba dependencias fijadas (`==`); si el
     manifiesto usaba rangos (`pandas>=2`) el bucle no ejecutaba ninguna
     consulta y `not atrasadas and not no_verificadas` valía `True`: cero
     comprobaciones se declaraban «al día» (P0.1/P1.19).
  2. El parser de requisitos convertía `-r base.txt`, `--index-url ...` y
     `-e .` en paquetes llamados `-r`, `--index-url` y `-e`; tampoco ignoraba
     URLs, rutas, wheels ni referencias `pkg @ url`. En `pyproject.toml` la
     regex cogía el primer `dependencies = [...]` aunque estuviera en
     `[tool.*]`, no entendía comillas simples y `pkg==` (sin versión) contaba
     como fijada.
  3. `_es_host_publico` aceptaba `localhost.` y `evil.localhost.:8080` (punto
     final válido en DNS) y las notaciones IPv4 alternativas `127.1`,
     `0x7f000001`, `2130706433` y `0177.0.0.1`, que algunos resolvers
     interpretan como loopback: el filtro anti-SSRF se podía eludir.
- **Solución**: `evaluar_vigencia` cuenta las comparaciones reales; con cero
  fijadas devuelve `v4=False`, lo anota y emite un hallazgo `UNVERIFIED`, y si
  compara solo una parte lo declara. Un único `_parsear_requisito` (PEP 508
  básico) descarta directivas de pip, URLs, rutas, wheels y referencias
  directas; `[project].dependencies` se lee con `tomllib` (con la heurística
  anterior solo como respaldo de formatos no estándar); `==` exige versión.
  El host se normaliza con `lower().rstrip(".")` y, si no es una IP canónica,
  se prueba `socket.inet_aton` para las notaciones alternativas.
- **Evidencia**: reproducción antes → después: `v4=True` con 0 llamadas a
  PyPI → `v4=False` + nota «sin dependencias fijadas (==)»;
  `['-r','--index-url','-e']` → solo `requests` y `pandas`;
  `127.1`/`localhost.` aceptados → rechazados. Suite **730/730** en Python
  3.11 y 3.12 (venv del lock, openai 3.35.1), ruff 0, preflight 0 y escaneo
  de secretos OK sobre el árbol de trabajo; `make ci` OK sobre HEAD (los
  cambios están sin comitear, así que esa copia limpia aún no los incluye).
  Auto-evaluación con red: `GLOBAL 1.000`; sin red: `0.958` con v4 `NO`, que
  es el resultado honesto.
- **Regla derivada**: una comprobación debe registrar cuántas verificaciones
  hizo y fallar cuando son cero; «no comprobado» nunca es «correcto». Los
  parsers de manifiestos se prueban con directivas, URLs y secciones ajenas,
  y la validación de hosts se hace sobre la forma canónica, no por prefijos.


### Hallazgo 94: un evaluador que confunde «no aplica» con «falla» y «docs» con «paquete»

- **Origen**: auditoría del 2026-10-21 sobre 7 repositorios externos
  (FastAPI, Flask, Httpie, Hypothesis, Requests, Testcontainers Java y un
  proyecto JS) más un control con 10 defectos plantados y una variante de
  rangos. La evaluación fue estática y read-only; no se ejecutaron suites
  ajenas.
- **Problema**: los diagnósticos tenían cuatro causas sistemáticas.
  1. **h6** analizaba todos los `.py`: `docs_src`, tests, ejemplos y scripts
     producían cientos de imports «sin declarar» (FastAPI 853, Hypothesis 919)
     y no reconocía `src/` como primera parte, `setup.cfg`, grupos PEP 735 ni
     requirements anidados. Tampoco distinguía imports opcionales,
     `TYPE_CHECKING` o condicionales.
  2. **h5** solo leía `info.license`; los 12 paquetes marcados por el audit
     tenían `license_expression` válida (PEP 639) y `info.license` vacío.
  3. **c5** recorría funciones con `ast.walk`: marcaba endpoints anidados,
     tests que delegan en helpers y property tests; **c3** contaba silencios
     de tests y de imports opcionales como si fueran producción.
  4. El plan reutilizaba la evidencia de toda la dimensión y `datos_medidos`
     de notas ajenas: h5/h6/h7 de FastAPI citaban los mismos 855 sitios. Los
     proyectos Java/JS reciben 0 en criterios Python que no pueden cumplir.
- **Fuentes consultadas** (2026-10-21): PEP 639
  <https://peps.python.org/pep-0639/>, PEP 735
  <https://peps.python.org/pep-0735/>, detección de primera parte con `src/`
  de Ruff <https://docs.astral.sh/ruff/settings/>, checks por ecosistema de
  OpenSSF Scorecard
  <https://github.com/ossf/scorecard/blob/main/docs/checks.md> y aserciones
  de pytest <https://docs.pytest.org/en/stable/how-to/assert.html>.
- **Solución**: perfil determinista de proyecto (lenguajes, manifiestos,
  locks, tests y dependencias por ámbito); criterios N/A que no se cuentan;
  cobertura y aviso de comparabilidad. h6 se limita al código del paquete y
  excluye tests/docs/scripts, `TYPE_CHECKING`, imports opcionales/condicionales
  y `if __name__`; lee pyproject (PEP 621/735, Poetry/PDM), setup.cfg/setup.py,
  requirements con `-r` y package.json. h5 lee `license_expression` SPDX,
  luego clasificador OSI y luego texto; desconocido es `unverified`, no
  «no libre». c5 solo marca tests no-op (sin aserción ni operación que pueda
  fallar); c3 solo código de producción. v4 usa la versión resuelta por lock
  (uv/poetry/Pipfile/pip-compile/package-lock) y compara solo runtime Python.
  h4/f1/h7 cubren build.sh, npm/Gradle/Maven/tox/nox, comillas simples,
  `__main__.py`, console_scripts/bin y CHANGES/HISTORY/ADR en `.rst` anidados.
  El plan filtra la evidencia por criterio.
- **Evidencia antes → después** (mismos clones, con red; global v1 del audit
  y v2):
  FastAPI 0.723 → **0.825** (h6 853 → 0; c5 anidados 4/18 → 0; 20/29);
  Flask 0.626 → **0.887** (h6 104 → 0; c5 anidados 8/18 → 0);
  Httpie 0.572 → **0.602** (h6 88 → 3, los tres imports reales de `urllib3`;
  c5 no desglosado por el audit → 0);
  Hypothesis 0.572 → **0.887** (h6 919 → 0; c5 anidados 226/771 → 0);
  Requests 0.529 → **0.700** (h6 34 → 0; c5 no desglosado → 0);
  Testcontainers Java 0.408 → **1.000 con cobertura baja 10/29** (criterios
  Python N/A; no comparable);
  QA JS 0.289 → **0.692 con cobertura baja 12/29** (N/A).
  El control plantado sigue detectando **10/10** defectos; el control de
  rangos sigue fallando v4 con **0 llamadas a PyPI**. Detalle y límites en
  `docs/EVALUACIONES.md`.
- **Autoevaluación**: con red **0.958** (27/29; único fallo, real:
  `openai 3.35.1 → 3.36.0` en el lock); sin red **1.000** (v4/h5 N/A, no
  fallos). Suite **747/747** en Python 3.11 y 3.12 (openai 3.35.1), ruff 0,
  preflight 0. Los cambios quedaron **sin comitear**.
- **Regla derivada**: antes de puntuar, detectar el perfil y marcar N/A lo que
  no se puede verificar; N/A nunca es un fallo ni un 0. El análisis estático
  se limita al código publicable y cada hallazgo debe pertenecer a UN criterio;
  una recomendación sin evidencia de su propio criterio es ruido. Los metadatos
  se leen por el campo vigente del estándar (PEP 639), no por el primero que
  existió.

### Hallazgo 95: portabilidad Windows — rutas, reloj de resolución gruesa y directorios locales

- **Origen**: revisión y prueba de instalación del 2026-10-22 en Windows 11
  (Python 3.12.7 y 3.14.3), con venv limpio, `pip install .` y
  `pip install --require-hashes -r requirements.lock`.
- **Problema**: la suite pasaba en Linux, pero en Windows fallaban 5 tests por
  tres causas reales:
  1. `tests_sin_aserciones()` construía la evidencia con `str(Path)`, que en
     Windows usa `\`; el contrato del informe y sus tests esperan
     `archivo:línea` con `/`. Fallaban c5 y el control de defectos plantados.
  2. `preflight` recorría `_local_debug/`, un directorio local ignorado por git
     (`.gitignore`) con scripts de depuración; el repo no pasaba su propio gate.
  3. `load_time` y `uptime` de los plugins usaban `time.time()`. En Windows
     3.12 ese reloj tiene una resolución de ~15,6 ms y una carga de plugin
     tarda <1 ms: el valor quedaba en 0.0 y fallaban los dos tests de ciclo de
     vida.
- **Solución**: `Path.as_posix()` en las evidencias; `_local_debug` en la lista
  `IGNORAR` de `preflight` (con test de regresión); `time.perf_counter()` para
  duraciones (se mantiene `time.time()` para marcas de tiempo de pared como
  `last_used`). No se cambió el contrato del informe ni se relajó ningún test.
- **Evidencia**: antes, 747 tests con 3 fallos en 3.14 y 2 en 3.12; después,
  **748/748** en Python 3.12.7 (openai 3.36.1) y **748/748** en 3.14.3
  (openai 1.109.1), ruff 0 y preflight 0 (58 archivos, antes 72 por
  `_local_debug`). Instalación limpia verificada: wheel `0.1.3`, imports de los
  8 módulos públicos + `plugins` + `scripts.preflight` desde site-packages,
  `pip check` sin conflictos y los 4 comandos de consola con exit 0; el lock
  con hashes también instala en Windows 3.12. `python3` no es fiable en
  Windows (en el equipo de prueba apuntaba a otro intérprete): se usó la ruta
  explícita.
- **Regla derivada**: medir duraciones con reloj monótono, emitir rutas de
  evidencia en POSIX y excluir del análisis lo que el repo declara local;
  probar la instalación en un SO distinto antes de afirmar que es portable.

### Hallazgo 96: el lock no se actualizaba solo y el evaluador leía un directorio local

- **Origen**: cierre de R1 y autoevaluación con red del 2026-10-22, tras
  instalar `uv` 0.13.5 y regenerar `requirements.lock`.
- **Problema**:
  1. `make lock` ejecutaba `uv pip compile --generate-hashes ...` sin
     `--upgrade`. uv conserva los pines del lock existente, así que el primer
     intento mantuvo `openai 3.35.1` aunque PyPI ya servía 3.36.1: el target
     parecía actualizar pero no lo hacía.
  2. `evaluar_proyecto.IGNORAR` no incluía `_local_debug/`, el directorio de
     scripts locales ignorado por git. La autoevaluación con red bajó a
     **0.967** por 5 hallazgos c3 falsos en esos scripts; `preflight` ya los
     excluía desde el Hallazgo 95, pero la lista del evaluador era otra copia.
  3. Las evidencias c3 se construían con la ruta relativa de `Path`, que en
     Windows usa `\`, y no cumplían el contrato `archivo:línea` en POSIX que ya
     se había corregido en c5.
- **Solución**: `make lock` añade `--upgrade`; `_local_debug` entra en
  `IGNORAR` con comentario y test de regresión
  (`test_c3_ignora_scripts_locales_de_depuracion`); las evidencias c3 usan
  `Path.as_posix()`. No se relajó ningún criterio ni se ocultó el hallazgo:
  simplemente se dejó de analizar lo que el repo declara local.
- **Evidencia**: la primera regeneración fijó `openai 3.36.1`; al reejecutar
  la autoevaluación, PyPI ya servía 3.37.0 y se regeneró de nuevo con
  `--upgrade`. Lock final con `openai 3.37.0`, `httpx2/httpcore2 2.16.0` y el
  resto de pines sin cambios; instalación con `--require-hashes` en Python
  3.12.7 correcta; suite **750/750** en 3.12.7 (openai 3.37.0) y **750/750** en
  3.14.3 (openai 1.109.1); autoevaluación con red **1.000** (27/27 sin
  ejecutar tests; 28/28 con `--ejecutar-tests`; 2 N/A);
  ruff 0; preflight 0 (58 archivos). La primera pasada de la autoevaluación
  había dado 0.967 precisamente por los 5 hallazgos de `_local_debug`.
- **Regla derivada**: un comando de actualización debe pedir la actualización
  de forma explícita y verificarse contra el lock resultante; las políticas de
  exclusión (git, preflight, evaluador) deben mantenerse alineadas o
  centralizarse, porque las copias divergen; toda evidencia con rutas se emite
  en POSIX.

---

## 2026-10-23 (ronda 16) — Auditoría independiente de los commits recientes (hallazgo 97)

### Hallazgo 97: una auditoría externa encontró 19 defectos que la suite no veía

- **Origen**: auditoría de la actividad del 2026-10-16 al 2026-10-22 —
  **50 commits (`17798f7..HEAD`)**, revisados en dos tramos: 32 en
  `84cbeac^..HEAD` y los 18 previos de esa sesión en `17798f7..84cbeac`. (El
  encargo hablaba de 53; el recuento real con `git rev-list --count` es 50.)
  La hicieron 4 revisores independientes con hallazgos verificados
  individualmente, más un pase de coherencia docs/config (regla propia 11).
- **Problema**: 12 defectos de código y 7 de coherencia, todos verificados en
  el código real antes de tocar nada:
  1. El parser Poetry concatenaba nombre+versión y lo reparseaba:
     `requests = "2.28.0"` (sintaxis legal de versión exacta) producía la
     dependencia ficticia `requests2.28.0` (P0.2), consultable en PyPI con red.
  2. `_es_lock` trataba cualquier `requirements/*.txt` como lockfile: uno con
     líneas sin fijar (`requests>=2.0`) afirmaba reproducibilidad falsa.
  3. `detectar_comando_tests` casaba sin límites de palabra ni ancla: "django
     test runner" producía el comando basura `['go','test','runner','o',
     'detox.']` y "detox en iOS" producía `['tox','en','iOS.']`.
  4. c3 leía y parseaba con `ast` cada archivo de producción dos veces.
  5. `lineas_silenciosas` tenía una rama fallback regex por `SyntaxError`
     inalcanzable (su único llamador hace `continue` antes; código muerto).
  6. El hallazgo e3 decía "en docs/" pero la búsqueda cubre todo el repo.
  7. `_es_licencia_libre` clasificaba una SPDX mixta (`MIT AND LicenseRef-X`)
     entera como no libre en vez de no verificable.
  8. `_evaluar` casaba fuentes por `source_url` (lo que dijo el modelo, puede
     faltar) mientras la pasada independiente ya casaba por `source_id` (lo
     fija el pipeline).
  9. `_es_host_publico` sin `socket.inet_aton` (WASI/Emscripten) dejaba pasar
     cualquier host como público (degradación silenciosa).
  10. `MockSearchPlugin` ignoraba el contrato común de `SearchProviderPlugin`:
      `search(query, max_results=5)` propio con tope fijo de 3 e indiferente a
      `params.max_results` (con 2 devolvía 3).
  11. El docstring de `preflight.py` sobreestimaba su gate de imports (omitía
      las exenciones `TYPE_CHECKING`, `__main__`, `try/except ImportError` y
      flags `has_*`).
  12. **CoVe circular** (hallazgo del segundo tramo, introducido en 1198968):
      si el claim llegaba sin `source_id` y con una `source_url` que no casaba
      con ninguna fuente, la pasada principal caía a `sources[:3]` y la
      "independiente" volvía a ver esas mismas fuentes: `contested: False`
      garantizado, justo lo que CoVe debía evitar.
  13. Coherencia docs/config: cifra de tests de Linux desactualizada en
      `AGENTS.md` (747 cuando la suite ya corría 750), recuento de N/A sin red
      mal en `EVALUACIONES.md` (25/27 con 2 N/A cuando son 25/29 con 4),
      Hallazgo 6 hablando en presente de `verify_install.py` (eliminado el
      2026-10-20 en e463aca), entradas huérfanas `install_check.json` e
      `install_result.json` en `.gitignore`, la semántica `--upgrade` de
      `make lock` sin documentar, docstring del canario openai con "403/403"
      y versiones viejas, y notación de rango errónea (`674eb8c..f9b3cc8`
      excluye el propio 674eb8c) en `docs/ESTADO-2026-10-16.md`.
- **Solución**: cada arreglo con su test de regresión honesto (11 tests nuevos:
  Poetry exacta/^/~, lock fijado/sin fijar/a medias, prosa que no es comando,
  `go test`/`pytest` válidos, SPDX mixta, casado por `source_id`, hosts sin
  `inet_aton`, `params.max_results` del mock y 2 de CoVe: exclusión de fuentes
  del fallback y omisión declarada cuando se agotan). c3 parsea una sola vez y
  `lineas_silenciosas` recibe el árbol (rama muerta eliminada, precedente del
  Hallazgo 85). La SPDX mixta devuelve `None` (no verificable). El mock migra
  al patrón común (`self._search` + `self._max_results` en `initialize()`).
  CoVe pasa a devolver las fuentes vistas por la pasada principal y la
  independiente las excluye (si no quedan, `skip` registrado). Docs alineados
  con lo medido hoy. NO se tocó la numeración ni las cifras históricas fechadas.
- **Evidencia**: suite **778/778** en Linux con Python 3.11.9 y 3.12.3 (venv
  aislado recreado desde `requirements.lock`, openai 3.37.0); `ruff check .`
  0 errores; `preflight` 0; demos offline (`deep_research_system`,
  `pensamiento_layer`, `code_design_improvement_tools`) exit 0;
  autoevaluación **1.000 con red** (27/29, cobertura 93%, N/A `e1`/`e2`) y
  **1.000 sin red** (25/29; 4 N/A: `v4`, `h5`, `e1`, `e2`); dependencias
  runtime ya en la última versión de PyPI (openai 3.37.0, requests 2.34.2,
  python-dotenv 1.2.4, PyYAML 6.0.3) y `pip-audit` sin vulnerabilidades
  conocidas.
- **Regla derivada**: una suite verde y una mutación alta no bastan — la
  revisión humana independiente sigue encontrando defectos de diseño
  (inventar datos, falsos positivos de afirmación, degradaciones silenciosas)
  que los tests no plantean; toda afirmación de estado presente en docs debe
  re-medirse al tocarla.
- **Seguimiento 2026-10-23 (misma sesión)**: los dos hallazgos sistémicos se
  convierten en gates en vez de en promesas. `scripts/check_docs.py` (10 tests)
  falla si el nº de tests declarado en `AGENTS.md`/`EVALUACIONES.md` no cuadra
  con el conteo AST, si `requirements.txt` diverge del lock o si la versión de
  `pyproject.toml` no está publicada; integrado en `make check` y en el hook.
  `tests/test_evaluador_corpus.py` (4 casos) fija las regresiones del evaluador
  (Poetry, falso lock, prosa/runner, comando válido). Evidencia final: suite
  **778/778** en Linux 3.11.9 y 3.12.3, ruff 0, preflight 0, docs-check OK,
  demos offline exit 0 y autoevaluación 1.000 (con y sin red). Los hallazgos
  R2 (cobertura ≥90%) y R3 (mutación del evaluador) siguen abiertos en
  `docs/RECOMENDACIONES-MEJORAS.md`.
- **Seguimiento de mutación (2026-10-23)**: la primera campaña tras los tests
  nuevos falló al colectar (`ModuleNotFoundError: scripts.check_docs`): los
  tests que importan módulos fuera de `source_paths` deben añadirse a
  `pytest_add_cli_args_test_selection` o el sandbox `mutants/` no puede
  importarlos. Añadidos `test_check_docs.py` y `test_evaluador_corpus.py`;
  colecta verificada (596 tests seleccionados) y campaña reanudada. El fallo
  fue ruidoso y rápido, no silencioso: la regla P1.19 funcionó.
- **Triaje y resultado final de mutación (2026-10-23)**: primera re-medición
  **94,31% (3614/3832; 218 supervivientes)**; el triaje mostró dos clases:
  (a) mutantes **equivalentes** en `_es_host_publico` (`rstrip("XX.XX")` tras
  `lower()`, regex `[0-9X]` tras `lower()`, y precedencias `and`/`or` que la
  rama `is_private` ya cubre) y en los argumentos de `json.JSONDecodeError`
  (la excepción se captura igual); (b) **huecos reales**: forzar
  `inet_aton=None`, aceptar host vacío y mutar el dict de respaldo de
  `_evaluar`. Arreglo: 3 tests honestos (IP pública 8.8.8.8/1.1.1.1, host
  vacío/punto, forma exacta del dict de respaldo) y eliminación de la lógica
  redundante `origen` en `_evaluar_independiente` (sus 8 mutantes eran
  equivalentes porque `fuentes_usadas` ya excluye el origen). Resultado final:
  **95,2% (3635/3819; 184 supervivientes, 0 timeouts, 0 sospechosos)**;
  `deep_research_system` pasa de 90 a 57 supervivientes y el total baja en 13
  mutantes por el código redundante eliminado.
- **Modo `--requisitos` (2026-10-23)**: el estado del arte no ofrece un
  verificador general de requisitos naturales. Hay trazabilidad explícita
  (OpenFastTrace, StrictDoc), requisitos ejecutables (BDD/contratos),
  formalización (FRET, Simulink) y LLM con revisión humana (F1 ~80%,
  explicaciones completas 43-71%). Lección: un enlace o un test declarado no es
  un cumplimiento; el modo separa `CUBIERTO` (evidencia estática) de `CUMPLE`
  (suite verde) y `NO VERIFICABLE` (manual o ambiguo). No altera el GLOBAL, no
  sigue evidencias fuera del proyecto y ejecuta la suite una sola vez,
  reutilizando el resultado de calidad. Evidencia: 17 tests nuevos
  (**795/795**), ruff 0, preflight 0 y `scripts/check_docs.py` OK.
- **Auditoría de cambios de agentes (2026-10-23)**: no se puede detectar
  intención ni autoría con un diff; sí se pueden detectar señales mecánicas de
  cambios no solicitados y test tampering. `scripts/audit_changes.py` clasifica
  `OK`/`REVISAR`/`BLOQUEAR` con rutas sensibles, CI/hooks, tests borrados o
  debilitados, skips, asserts eliminados, matchers flojos, supresiones,
  cobertura rebajada, configuración relajada, dependencias nuevas, requisitos
  modificados, comandos peligrosos y presupuesto excesivo. Lecciones: (a) las
  instrucciones solas no bastan; (b) una suite verde es engañosa si el agente
  puede editar los tests; (c) el auditor debe ejecutarse fuera del alcance de
  escritura del agente (CI/otro checkout), o el propio control es editable;
  (d) `--permitir tests/` no oculta un archivo de test eliminado ni un skip.
  Evidencia: 28 tests nuevos del auditor y 9 del runner (**832/832**), ruff 0,
  preflight 0 y `scripts/check_docs.py` OK.
- **Holdout con hashes (2026-10-23)**: `holdout/` no se descubre con
  `make test`; `scripts/run_holdout.py` verifica el SHA-256 de cada test contra
  `HASHES.json` y ejecuta la suite. Si un test cambia sin actualizar el
  manifiesto, falla con código 2; si se actualizan ambos, el auditor marca
  `holdout_modificado` para revisión. Límite declarado: es tamper-evidence, no
  una protección criptográfica; debe ejecutarse en hook/CI fuera del alcance de
  escritura del agente. Evidencia: 4 tests holdout, hook y `make ci`
  integrados.
- **Ejecutar Python con `python3`, no con `bash` (2026-10-23)**: al probar
  `run_holdout.py` se ejecutó por error con `bash`; las líneas `import ...`
  invocaron el `import` de ImageMagick y crearon seis PostScript de ~12 MB en
  la raíz del repo. Se detectaron en `git status` antes de comitear, se
  inspeccionó solo tipo/tamaño (no contenido, P0.6) y se movieron a `/tmp`.
  Lección: los scripts Python se ejecutan con `python3`; antes de comitear,
  revisar `git status` para artefactos no versionados. El hook y el CI ya usan
  `python3`.

## 2026-10-24 (ronda 17) — Evaluación integral: dos defectos reales del evaluador (hallazgo 98)

### Hallazgo 98: la clave estaba en `.env` pero el evaluador no la leía; N/A se contaba como no verificado

- **Origen**: evaluación integral pedida por el programador (6 dimensiones,
  mutación, síntesis LLM, demos, tests honestos, cobertura y proveedores
  reales). La mutación se re-midió y la síntesis se ejecutó de verdad; el
  proveedor local Ollama no estaba disponible y se declaró OMITIDO.
- **Problema 1**: `python3 evaluar_proyecto.py . --ejecutar-tests
  --sintesis-llm --investigar` falló con `ERROR: OpenAI API key required`
  aunque `OPENROUTER_API_KEY` estaba en `.env` (73 caracteres, nunca
  impresos). `test_env_usage.py`, `test_openrouter_real.py`,
  `scripts/probe_model.py` y el demo de OpenRouter cargan
  `load_dotenv(".env")`; `main()` del evaluador no lo hacía. La síntesis solo
  funcionó con un envoltorio que cargaba dotenv antes de llamar a `main`.
- **Problema 2**: con todos los criterios en OK, el informe imprimía
  `[UNVERIFIED] 1`: la nota «2 criterios declarados N/A» se añadía a
  `no_verificado` y `resumen_evidencias` la contaba como evidencia no
  verificada. Contradice el contrato declarado («N/A no se cuenta como
  fallo») y hacía que `no_verificado` no quedara vacío en una pasada limpia.
- **Solución 1**: `cargar_entorno_llm(dotenv_path=None)` carga
  `Path.cwd()/".env"` solo con `--sintesis-llm`/`--investigar`; `main`
  comprueba `OPENROUTER_API_KEY` antes de construir el proveedor y devuelve 2
  con un mensaje explícito. El modo offline no lee `.env`.
- **Solución 2**: la nota N/A se mueve a `cobertura.nota_no_aplicables`;
  `no_verificado` solo contiene lo realmente no verificado y
  `[UNVERIFIED]` cuenta solo eso. `informe_texto` imprime «No aplicable:».
- **Tests**: 10 nuevos (suite del evaluador: 83 → 91; preflight: 20 → 22; total
  832 → 842): carga
  de dotenv desde ruta, fallo sin key antes del proveedor, `ImportError` de
  dotenv, N/A vs no verificado, `setup.py`, locks (uv/Pipfile/package-lock/
  texto/JSON inválido) y renderizado de requisitos, síntesis e investigación.
  La reproducción previa al arreglo fue manual: el fallo real de la síntesis y
  el `[UNVERIFIED] 1` con `no_verificado` no vacío. No se afirma que cada test
  se haya ejecutado contra el código viejo.
- **Evidencia**: suite **842/842** en Linux (Python 3.11.9); `ruff check .` 0;
  preflight 0; `check_docs.py` OK; copia limpia del árbol (HEAD + diff) 842/842;
  autoevaluación **1.000** (28/30; 93%) con `no_verificado` vacío y
  `[UNVERIFIED] 0`; cobertura del evaluador **86% → 90%** (149/1432 sin
  ejecutar), preflight 91%, total 83%; mutación re-medida **95,2%**
  (3635/3819; 184 supervivientes, 0 timeouts, 0 sospechosos); síntesis real
  con el modelo gratuito: 4 propuestas, **0 con respaldo medido** (juicio, no
  medición) y 3 preguntas abiertas; `test_openrouter_real.py` quedó no
  concluyente por 429 repetidos y se canceló; Ollama OMITIDO por servidor
  ausente.
- **Lección/regla**: (a) si el proyecto adopta `.env` como fuente de claves,
  todo entrypoint opt-in debe cargarlo del mismo modo o declarar que exige la
  variable exportada; (b) «N/A» y «no verificado» son categorías distintas:
  mezclarlas infla la evidencia no verificada y erosiona la confianza en el
  resumen; (c) un test que solo ejecuta líneas no basta: los nuevos tests
  comprueban efectos (clave cargada, código 2, `[UNVERIFIED] 0`, versiones de
  lock y texto renderizado).

## 2026-10-24 (ronda 18) — Publicación 0.1.4: el JSON de PyPI llega tarde (hallazgo 99)

### Hallazgo 99: PyPI sirve 0.1.4 por el índice simple antes de que su JSON lo refleje

- **Origen**: publicación de `thinker-research 0.1.4` en TestPyPI y PyPI el
  2026-10-24, con los mismos artefactos verificados en ambos índices.
- **Problema**: tras un `twine upload` correcto, el endpoint
  `https://pypi.org/pypi/thinker-research/0.1.4/json` devolvió 404 durante
  unos 30 s y el JSON del proyecto seguía anunciando `0.1.3`, mientras el
  índice simple ya listaba `0.1.4` y `pip install thinker-research==0.1.4`
  funcionaba. TestPyPI mostró el mismo retardo antes de actualizar su JSON.
- **Solución**: verificar la publicación por tres vías independientes —
  índice simple con hashes, endpoint versionado e instalación limpia en un
  venv—; no declarar fallo por un JSON de «última versión» con caché. Los
  artefactos de TestPyPI y PyPI tienen los mismos SHA-256; `twine check`
  PASSED; la instalación limpia mostró `--requisitos`, imports OK y
  `pip check` limpio.
- **Evidencia**: wheel
  `835a5c355322f2b0de2f15e1dc69b4911df6a6177d2dbc4cd66f287d6171d8fe` y
  sdist `e3014903654316cd0760cdc950588dac8d9a998b1917c172bb0b468beec69422`;
  `.../0.1.4/json` responde 200/`0.1.4`; tag anotado `v0.1.4` (commit
  `858bdf8`) empujado; suite **842/842**.
- **Lección**: un caché de «latest» no invalida una publicación; hay que
  contrastar índice simple, endpoint versionado, hashes e instalación real.
  Refuerza el Hallazgo 91 y la regla P0.1.

## 2026-10-24 (ronda 19) — Alias de importación y directorios generados (hallazgo 100)

### Hallazgo 100: `pywin32` y los entornos con sufijo

- **Origen**: revisión externa de dos falsos positivos del gate de imports y de
  la exploración de directorios. Se verificaron con fixtures antes de tocar
  código.
- **Problema 1**: `ALIAS_IMPORTACION` no incluía los módulos de `pywin32`
  (`win32api`, `win32con`, `win32gui`, `win32com`, `pythoncom`, `pywintypes`).
  Un proyecto con `pywin32` declarado e `import win32api` producía
  `import no declarado: win32api` (reproducido con un fixture).
- **Problema 2**: `IGNORAR` comparaba nombres exactos. Un `.venv-docs/`,
  `venv-old/` o `pytest-of-1/` se recorrían enteros, con el coste que eso
  implica en un repo grande. `dist/` sí estaba excluido; `exe/` no se excluye
  a propósito porque puede ser código real.
- **Solución**: alias estáticos para los seis módulos de `pywin32` y un helper
  compartido `es_parte_ignorada()` con prefijos `.venv`, `venv-`,
  `pytest-of-` y sufijo `.egg-info`; lo usan `evaluar_proyecto` y `preflight`.
  Cuatro tests nuevos: dos de alias/h6 y dos de exclusiones, incluido que
  `exe/` sigue entrando.
- **Investigación**: la documentación de Python separa distribución e import
  package y ofrece `packages_distributions()`, pero advierte que las
  instalaciones editables pueden no declarar top-level names; por eso el mapa
  estático sigue siendo necesario para proyectos evaluados offline
  ([docs.python.org](https://docs.python.org/3.12/library/importlib.metadata.html#mapping-import-to-distribution-packages)).
  El código de pytest confirma que el directorio base temporal es
  `pytest-of-{user}` ([docs.pytest.org](https://docs.pytest.org/en/6.2.x/_modules/_pytest/tmpdir.html)).
  `pywin32` se distribuye desde PyPI
  ([pypi.org/project/pywin32](https://pypi.org/project/pywin32/)).
- **Evidencia**: suite **846/846**, autoevaluación **1.000**, preflight propio
  0 hallazgos; cobertura del evaluador **90%** (149/1433) y preflight **91%**
  (35/376), total 83%. Publicada como `0.1.5` en TestPyPI y PyPI el
  2026-10-24. La mutación no se re-mide porque los módulos mutados no
  cambiaron y evaluador/preflight están excluidos de la campaña.
- **Lección**: un alias de importación no puede deducirse solo del nombre de la
  distribución; para offline hace falta un mapa curado. Y los directorios
  generados se excluyen por patrón, no por nombre exacto, sin ignorar nombres
  genéricos como `exe`.

## 2026-10-24 (ronda 20) — Exclusiones configurables e imports hermanos (hallazgo 101)

### Hallazgo 101: `tools/` no es una dependencia externa

- **Origen**: evaluación externa de MultiStat. De 98 hallazgos restantes, 65
  eran imports en `tools/` donde importar módulos hermanos por nombre es
  intencional; el snapshot con lista blanca evitaba el coste pero no la causa.
- **Problema 1**: `revisar_imports` resolvía módulos locales solo desde la
  raíz/paquetes con `__init__.py`. `tools/a.py` con `import helper` y
  `tools/helper.py` se marcaba como import no declarado.
- **Problema 2**: no había forma de excluir `exe/` u otros directorios
  generados sin editar el código o usar un snapshot; `dist/` ya estaba en
  `IGNORAR`.
- **Solución**: (a) cada archivo añade a su contexto los `.py` hermanos y los
  paquetes hijos con `__init__.py`; (b) `--ignorar DIRECTORIO` repetible en
  `evaluar_proyecto` y `preflight`, que actualiza el conjunto `IGNORAR` del
  proceso. Tres tests nuevos: import hermano en `tools/`, y `--ignorar exe`
  en ambas CLI (con restauración del global en los tests).
- **Evidencia**: suite **849/849**, autoevaluación **1.000**, preflight propio
  0; cobertura 90% evaluador (149/1435) y 91% preflight (35/385), total 83%.
  Publicada como `0.1.6` en TestPyPI y PyPI el 2026-10-24; hashes wheel
  `4ed2ef35…e3bc2` y sdist `189d57a7…f04c`, tag `v0.1.6` (`4b4216e`).
- **Lección**: la localidad de un import es contextual (directorio del archivo),
  no solo global; y las exclusiones de análisis deben ser configurables por el
  usuario, no un workaround con snapshot. `exe` no se ignora por defecto.

## 2026-10-24 (ronda 21) — Alias reales y ruido de MultiStat (hallazgo 102)

### Hallazgo 102: solo tres alias de los seis reportados eran reales

- **Origen**: revisión de los cambios de las últimas 48 h y de los comentarios
  de MultiStat. Se probaron los seis alias reportados con fixtures de
  `pyproject` + import.
- **Resultado**: `PIL`→`pillow`, `docx`→`python-docx` y `pptx`→`python-pptx`
  eran falsos positivos reales. `pygetwindow`, `rapidocr_onnxruntime` y
  `shiboken6` **pasan** si la distribución está declarada directamente; el
  caso `shiboken6` con solo `PySide6` es una dependencia transitiva y el flag
  es correcto según la política de dependencias directas.
- **Solución**: tres alias con test de preflight y de h6; no se añadieron los
  otros tres ni se debilitó el gate de silencios, conforme a la regla 13.
- **Evidencia**: suite **851/851**, autoevaluación **1.000**, preflight 0;
  cobertura 90% evaluador (149/1435) y 91% preflight (35/385). Publicada como
  `0.1.7` en TestPyPI y PyPI el 2026-10-24; tag `v0.1.7` (`4e631ed`).
- **Lección**: una opinión externa puede señalar un defecto real y, a la vez,
  incluir falsos positivos; la única forma de separarlos es reproducir cada
  caso. La regla 13 prohíbe tocar el gate para que la nota suba.

## 2026-10-25 (ronda 21) — Revisión integral y regla 12 (hallazgo 103)

### Hallazgo 103: cifras duplicadas que derivan y un `.env` demasiado abierto

- **Origen**: revisión integral del repositorio en `eaea4d4` y nueva regla del
  programador sobre `gh`/GitHub Releases (2026-10-25).
- **Problema 1**: `README.md` declaraba 94,7% de mutación (3581/3780) mientras
  `AGENTS.md`, `docs/EVALUACIONES.md` y `docs/RECOMENDACIONES-MEJORAS.md`
  tenían 95,2% (3635/3819); el gate documental no comprobaba esa cifra.
- **Problema 2**: la cabecera de `docs/RECOMENDACIONES-MEJORAS.md` seguía
  fechada el 2026-10-23 y decía «sin publicar» cuando `0.1.7` ya estaba
  publicada el 2026-10-24.
- **Problema 3 (seguridad local)**: `.env` estaba en modo 644; `AGENTS.md`
  indica que contiene una clave real. No se leyó su contenido.
- **Solución**: cifras y cabecera alineadas; regla 12 ampliada (sin `gh` ni
  GitHub Releases desde el repo) y `docs/PUBLICACION.md` sin pasos de release;
  `chmod 600 .env`; dos palabras duplicadas de `STOPWORDS` retiradas (B033);
  completada la descripción de `docs-check` en README. El gate documental
  contrasta ahora la cifra de mutación de README con la vigente de AGENTS, con
  test de regresión. No se tocó ningún criterio de evaluación (regla 13).
- **Evidencia**: suite **852/852**, ruff 0, preflight 0, docs-check OK;
  autoevaluación **1.000**; `.env` en 600; el test del gate falla si las
  cifras de README y AGENTS divergen.
- **Lección**: una cifra duplicada en varios documentos deriva si el gate no
  la mira; o se centraliza o se comprueba. Los permisos de un `.env` local
  también son parte de P0.6 aunque el archivo no se versione, y publicar no
  debe depender de la CLI ni de una cuenta de GitHub (regla 12).

## 2026-10-25 (ronda 22) — Publicación 0.1.8 (hallazgo 104)

### Hallazgo 104: el índice simple de PyPI tarda en ver una versión recién subida

- **Origen**: publicación de `thinker-research 0.1.8` tras la revisión
  integral y la ampliación de la regla 12.
- **Problema**: tras subir a TestPyPI y PyPI, el JSON versionado y los hashes
  ya mostraban `0.1.8`, pero `pip install thinker-research==0.1.8` respondía
  «from versions: ... 0.1.7»; `--no-cache-dir` no bastó en el primer intento.
  Es el retardo del índice simple, no un fallo del artefacto (misma clase que
  el Hallazgo 91).
- **Solución**: contrastar JSON, índice simple y hashes; esperar la
  propagación y reintentar la instalación limpia. No se re-subió nada.
  TestPyPI y PyPI aceptaron la misma wheel/sdist con hashes idénticos.
- **Evidencia**: wheel
  `91dd0168fda2d4e8c8d5da0d695ae06cc1a70e15bf0e87465fc1e1a49d9afa02` y sdist
  `4a4f36a20746e0d03135a9c0e195cb8e521e618b7f345d4f6f7880ee00ae9f6a`;
  instalación limpia desde TestPyPI y PyPI OK; `evaluate-project --help`,
  imports OK y `pip check` limpio; suite 852/852; tag anotado `v0.1.8`
  (`18990b0`); autoevaluación 1.000.
- **Lección**: un «no matching distribution» inmediato tras publicar no
  prueba que la subida falló; verificar el JSON y los hashes antes de
  concluir y no duplicar la subida.

## 2026-10-25 (ronda 23) — Cobertura de ramas y licencias no runtime (hallazgo 105)

### Hallazgo 105: el 90% combinado estaba a una rama y las licencias dev no se veían

- **Origen**: recomendaciones abiertas R2 y R10 de
  `docs/RECOMENDACIONES-MEJORAS.md`.
- **Problema 1**: la cobertura era 90% en `evaluar_proyecto.py` y 91% en
  preflight, pero **89,9% combinada**; el objetivo ≥90% no se alcanzaba por
  dos sentencias. Las ramas de error de requisitos, ámbitos de requirements,
  TOML inválido y manifiestos no Python no tenían test.
- **Problema 2**: `h5` solo miraba licencias runtime; las de desarrollo y
  opcionales no aparecían, aunque también se distribuyen.
- **Solución**: tests de comportamiento para las ramas de error y campo
  `licencias_no_runtime` (nombre, ámbito, origen, versión, licencia, fuente y
  procedencia). `h5` no cambia; sin red cada entrada es `unverified`.
- **Evidencia**: evaluador **91%** (130/1466 sin ejecutar), preflight **91%**
  (35/385), **91% combinado** (1686/1851); suite **858/858**, ruff 0,
  autoevaluación **1.000**. Dos tests de licencias no runtime: un extra no
  libre no altera `h5` y sin red queda `unverified`. Publicada como `0.1.9`
  en TestPyPI y PyPI el 2026-10-25; tag `v0.1.9` (`14e2b7f`); wheel
  `88918e4bfa69e316222ff7730964723941e74ae27d75c2ece0486c2dac528270` y sdist
  `756d838ff11659c3a172a50b354c190edfbe1912747259a903febbcd046f8a81`.
- **Lección**: un objetivo de cobertura debe medirse con su denominador exacto
  (el 90% redondeado ocultaba un 89,9%); y una licencia fuera del score sigue
  siendo un riesgo que hay que hacer visible, separado del runtime.

## 2026-10-25 (ronda 24) — Dogfooding medible (regla 14)

### Hallazgo 106: usar thinker al final no es usarlo en la mejora

- **Origen**: regla del programador del 2026-10-25: thinker debe usarse en al
  menos el 90% de las tareas de mejora de thinker.
- **Problema**: en R2/R10 thinker se usó como evaluador final y consultor, pero
  no como diagnóstico/diseño de la mejora. Una ejecución decorativa al final
  no demuestra dogfooding y no debe contar para el 90%.
- **Solución**: regla 14 en `AGENTS.md`, con unidad de medida por **tarea**
  (no por tiempo), registro de componente/evidencia/verificación, 100% en
  lotes de menos de 10 salvo excepción declarada y exclusión explícita de
  ejecuciones de trámite o de salidas no verificadas. La sección 5 de
  `docs/RECOMENDACIONES-MEJORAS.md` incluye la tabla de registro.
- **Evidencia**: regla 14 + ítem en el checklist pre-entrega; tabla de registro
  en RECOMENDACIONES; sin cambios de código.
- **Lección**: el dogfooding se demuestra con trazas de decisiones, no con una
  ejecución final; si thinker alucina, se descarta y se registra, y la
  verificación empírica sigue decidiendo.

## 2026-10-25 (ronda 25) — Aserciones débiles y benchmark (hallazgo 107)

### Hallazgo 107: c5 no mide fuerza y un benchmark sin cobertura no es una validación global

- **Origen**: R7 y R4 de `docs/RECOMENDACIONES-MEJORAS.md`. Diagnóstico con
  `analyze_python_code` (thinker): 2811 líneas, 83 funciones, complejidad 398,
  sin issues estáticos; baseline con `evaluar_proyecto` (1.000, 28/30).
- **R7**: c5 detectaba no-ops pero `assert True` pasaba. Se añadió
  `aserciones_debiles` (campo y sección de texto) con detección conservadora de
  constantes verdaderas, comparaciones constantes que pasan y
  `assertTrue/assertFalse/assertEqual` con literales. No cambia c5 y no marca
  variables, helpers ni property tests.
- **R4**: `tests/benchmarks/evaluador_precision.py` con 33 casos sintéticos
  etiquetados sobre 14 criterios, incluidos 5 trampas; TP/FP/FN, precision y recall por criterio y
  global. Resultado **14 TP, 0 FP, 0 FN; 1,00/1,00**. Límite declarado: 14 de 29
  criterios y fixtures sintéticas; no es una campaña sobre proyectos reales.
- **Evidencia**: suite **891/891**, ruff 0, cobertura evaluador 91% (145/1571),
  preflight 94%; autoevaluación 1.000. El benchmark y sus métricas son
  reproducibles con `python3 tests/benchmarks/evaluador_precision.py`.
- **Lección**: una aserción que no puede fallar no aporta fuerza, aunque pase
  c5; y un benchmark con 14 criterios sirve como regresión, no como certificado
  de precisión/recall global. La cobertura del benchmark debe declararse siempre
  (R4 sigue parcial).

## 2026-10-25 (ronda 26) — Mutación fuera del núcleo (hallazgo 108)

### Hallazgo 108: mutar el evaluador exige aislar dependencias y el triaje es el coste real

- **Origen**: R3. El 95,2% de mutación global excluye `evaluar_proyecto.py` y
  `scripts/preflight.py`; medirlos requiere una campaña separada.
- **Fallo 1**: el test `test_el_repositorio_real_pasa_su_propio_preflight`
  evalúa el repo completo y falla en el sandbox de mutantes; se deselecciona.
  Sin eso, la línea base falla y mata mutantes por error.
- **Fallo 2**: al mutar solo `evaluar_proyecto.py`, el sandbox importó
  `scripts.preflight` desde `site-packages` (versión instalada sin
  `es_parte_ignorada`) y la colecta falló. Se corrigió con
  `also_copy = ["evidence.py", "scripts"]`, que copia dependencias sin mutarlas.
- **Fallo 3**: `tempfile.mkdtemp` crea el destino y `shutil.copytree` fallaba
  con `FileExistsError`; se corrigió con `dirs_exist_ok=True`.
- **Piloto preflight inicial**: 949 mutantes, 495 muertos, 414 supervivientes,
  40 sin tests. Tras añadir 3 tests de helpers y 6 de manifiestos: **1015
  mutantes, 645 muertos, 370 supervivientes, 0 sin tests**, 0
  timeouts/sospechosos. Tasa bruta 63,5% (645/1015). **Sin triaje de los 370**,
  así que no es una tasa cerrada.
- **Estado del evaluador**: el arnés `scripts/mutacion.py` queda listo
  (`--objetivo evaluar`), pero la campaña completa no terminó; no se publica
  tasa del evaluador. R3 sigue **parcial**.
- **Evidencia**: 3 tests del arnés, suite **891/891**, ruff 0, docs-check OK.
- **Lección**: una campaña de mutación fuera de `source_paths` debe copiar sus
  dependencias sin mutarlas y verificar primero la línea base; los mutantes «sin
  tests» y los supervivientes son hallazgos, no ruido. Sin triaje no hay tasa
  honesta que publicar.

## 2026-10-25 (ronda 27) — Confianza no calibrada (hallazgo 109)

### Hallazgo 109: declarar «no calibrada» es más honesto que fingir una probabilidad

- **Origen**: R14. `EvidenceEvaluator` normaliza `credibility`/`confidence` a
  [0,1], pero no hay Brier ni tabla de fiabilidad que justifique leerlos como
  probabilidad.
- **Acción**: README y AGENTS declaran que **no están calibradas** y que no se
  presentan como probabilidad de acierto. `tests/test_docs_calibracion.py`
  protege la declaración; `tests/benchmarks/calibracion_confianza.py` añade un
  Brier **simulado** (0,1166 en 16 pares) que prueba el instrumento, no el
  modelo.
- **Evidencia**: suite **891/891**, ruff 0, docs-check OK. **No hay Brier
  real**; no se afirma calibración.
- **Lección**: cuando no hay medición real, la opción honesta es declarar la
  limitación, etiquetar el simulador como simulado y evitar que el número se
  lea como probabilidad.

## 2026-10-25 (ronda 28) — Comparabilidad, warnings y verificador barato (hallazgo 110)

### Hallazgo 110: un 1.000 con cobertura baja no es un ranking; una marca de silencio debe verse

- **R5**: `cobertura.comparable` exige ratio ≥80%; con cobertura baja el texto
  dice **«GLOBAL NO COMPARABLE»** y `motivo_no_comparable` explica por qué.
  Java/JS solo reciben señales genéricas; no se promete paridad.
- **R6**: `# noqa: silent: motivo` (≥3 caracteres) convierte el silencio en
  **warning** visible en c3 y preflight; sin marca o sin motivo sigue siendo
  hallazgo. Thinker no usa la marca.
- **R13-B**: benchmark con generador y verificador simulados: 1 llamada al
  generador, 1 al verificador, 1 extra; independencia `proveedor-distinto`.
  La descomposición de claims (C) sigue pendiente.
- **R14-B**: Brier simulado 0,1166 con 16 pares; la declaración «no calibrada»
  sigue vigente. No se usa como evidencia de calibración real.
- **Evidencia**: 10 tests nuevos, suite **891/891**, ruff 0, preflight 0,
  docs-check OK; cobertura evaluador 91% (145/1571) y preflight 94% (26/425).
- **Lección**: la honestidad del informe también se juega en los rótulos
  (comparable/no comparable) y en los warnings; una marca sin motivo o invisible
  es peor que un hallazgo.

## 2026-10-25 (ronda 29) — Publicación 0.1.10

### Hallazgo 111: el índice simple puede ir por detrás del JSON

- **Acción**: publicar `0.1.10` en TestPyPI y PyPI desde el tag `v0.1.10`
  (`551d693`), con wheel SHA-256
  `9571519215f336bd1b1b05e5f7a9f516f64500ebde57f2e16dbd5abdf7d26caa` y sdist
  `5ab2ef2cf790342b46a14af8f9161c42a3ecb6f0c0d31153dd31713891621f75`.
- **Incidencia**: el JSON y los hashes ya publicaban `0.1.10`, pero `pip`
  seguía sin verla en el índice simple; tras esperar la propagación, la
  instalación limpia funcionó. No se re-subió nada.
- **Evidencia**: `pip show` → `Version: 0.1.10`, `pip check` limpio,
  `evaluate-project --help` e imports OK desde PyPI y TestPyPI.
- **Lección**: verificar JSON/hashes no basta para pip; hay que comprobar el
  índice simple y reintentar tras la propagación (misma clase que el Hallazgo
  104). No confundir retardo de índice con artefacto ausente.

## 2026-10-25 (ronda 30) — Descomposición de claims y triaje R3

### Hallazgo 112: dividir claims es heurístico; sirve como piloto opt-in, no como verdad

- **R13-C**: `EvidenceEvaluator(descomponer_claims=True)` separa por
  conjunciones simples, evalúa cada subclaim y agrega por contradicción. El
  benchmark muestra el claim compuesto monolítico como `supported` con 1
  llamada y el descompuesto como `contradicted` con 2. Es opt-in y la división
  se declara heurística, no semántica.
- **R3**: 6 tests de manifiestos y un arreglo real (`extras_require` contaba
  sus claves como dependencias). Preflight queda en **1015 mutantes, 645
  muertos, 370 supervivientes, 0 sin tests**; el evaluador se midió después:
  **5939 mutantes, 3034 muertos, 2901 supervivientes, 0 sin tests, 4 timeouts**
  (tasa bruta 51,09%). Cobertura 94% y suite 891/891. Ninguno de los dos tiene
  triaje cerrado; los 4 timeouts siguen sin clasificar.
- **Lección**: una descomposición por conjunciones mejora el caso compuesto
  medido, pero puede partir mal una frase; el modo por defecto no se toca. En
  mutación, atacar los clusters con tests directos reduce el trabajo, pero no
  sustituye el triaje de los supervivientes.

## 2026-10-25 (ronda 31) — Piloto real de Brier (R14-C)

### Hallazgo 113: un Brier bajo en seis hechos fáciles no es calibración

- **Acción**: `tests/benchmarks/calibracion_real.py` con 6 claims factuales,
  fuentes y veredicto esperado; ampliado a **20 claims**. Llamadas reales a
  OpenRouter (`poolside/laguna-xs-2.1:free`; con 429 se usó el fallback
  `cohere/north-mini-code:free`).
- **Resultado**: **20/20 aciertos, Brier 0,0540** (el piloto inicial de 6 daba
  0,0017; al ampliar, la confianza fue menos optimista). Es un piloto, no una
  calibración: la muestra es pequeña y los hechos son fáciles.
- **Decisión**: la declaración «confidence no calibrada» sigue vigente. Para
  afirmar calibración general haría falta una muestra representativa, con
  intervalos y casos difíciles.
- **Evidencia**: 2 tests puros del cálculo; la ejecución real es opt-in y no
  forma parte de la suite offline.
- **Lección**: un Brier casi perfecto en casos triviales mide el instrumento,
  no la calidad probabilística del modelo. Declarar el tamaño y la dificultad
  de la muestra es parte del resultado.

## 2026-10-25 (ronda 32) — Mutación del evaluador: 51,09%, sin triaje

### Hallazgo 114: medir no es cerrar; 2901 supervivientes y 4 timeouts siguen abiertos

- **Medición**: campaña completa del evaluador con `scripts/mutacion.py
  --objetivo evaluar`: **5939 mutantes, 3034 muertos, 2901 supervivientes,
  0 sin tests, 4 timeouts, 0 sospechosos**. Tasa bruta **51,09%**
  (3034/5939); los timeouts cuentan como no muertos.
- **Estado**: R3 **no se cierra**. Faltan el triaje de los 2901 supervivientes
  del evaluador y de los 370 de preflight, además de clasificar los 4 timeouts.
  No se mezclan denominadores: el 95,2% del núcleo, el 63,5% de preflight y el
  51,09% del evaluador miden objetivos distintos.
- **Lección**: una tasa baja no autoriza a cambiar tests o umbrales para
  maquillarla; primero se triaja y se distingue mutante equivalente de test
  ausente. La cifra es evidencia para dirigir tests, no una nota.
