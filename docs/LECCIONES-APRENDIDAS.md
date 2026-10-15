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
- **Solución**: eliminados (con verificación previa de destino, P1.28). El
  estado real lo genera `verify_install.py` bajo demanda en `install_check.json`.

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

## 2026-10-15 — ToT con evaluación LLM, benchmark framework, plugins y fixes pre-commit (hallazgos 39–43)

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
