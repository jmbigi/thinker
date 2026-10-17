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
