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
