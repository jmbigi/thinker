# Requisitos y criterios de aceptación: deepseek-free-agent

Esta lista se verifica con:

```bash
python3 evaluar_proyecto.py . \
  --requisitos docs/REQUISITOS-DEEPSEEK-FREE-AGENT.md --ejecutar-tests
```

`CUMPLE` significa suite completa verde y test declarado existente; no demuestra
por sí solo equivalencia semántica. La disponibilidad real queda separada.

## DFA-01: Selección explícita del proveedor real
- Enunciado: La CLI debe construir `DeepSeekFreeAgentLLM` solo cuando el usuario selecciona `deepseek-free-agent`, conservando `mock` como opción offline por defecto.
- Criterio de aceptación: Los argumentos de proveedor, URL, timeout y autorización producen una instancia con esos valores sin realizar red durante la construcción.
- Verificación: test
- Evidencia: tests/test_deepseek_free_agent.py::TestDeepSeekFreeAgent::test_cli_construye_el_proveedor_sin_red

## DFA-02: Autorización formal antes del egreso
- Enunciado: Ninguna llamada al proveedor debe crear una tarea sin autorización humana explícita.
- Criterio de aceptación: Sin `authorized=True` o `--authorize-deepseek-agent`, `generate()` eleva `PermissionError` y el doble HTTP registra cero llamadas.
- Verificación: test
- Evidencia: tests/test_deepseek_free_agent.py::TestDeepSeekFreeAgent::test_autorizacion_es_obligatoria_antes_de_cualquier_tarea

## DFA-03: Frontera de red loopback
- Enunciado: El adaptador debe rechazar endpoints públicos, privados no loopback, credenciales y URL con componentes no admitidos.
- Criterio de aceptación: Solo URL HTTP(S) loopback sin ruta, query ni fragmento se normalizan; los once casos inválidos del contrato elevan `ValueError`.
- Verificación: test
- Evidencia: tests/test_deepseek_free_agent.py::TestDeepSeekFreeAgent::test_solo_acepta_endpoints_loopback

## DFA-04: Contrato HTTP y aislamiento de conversación
- Enunciado: Cada tarea debe llevar la instrucción de solo lectura, `newChat: true`, timeout, sin redirecciones, respuesta en streaming acotada y ningún salto de línea que el navegador pueda enviar prematuramente.
- Criterio de aceptación: El cuerpo multilínea se normaliza a una línea, las opciones HTTP coinciden con el contrato y una segunda consulta idéntica usa caché sin otra tarea.
- Verificación: test
- Evidencia: tests/test_deepseek_free_agent.py::TestDeepSeekFreeAgent::test_contrato_http_solo_lectura_y_cache

## DFA-05: Fallos visibles sin duplicar efectos
- Enunciado: Los errores HTTP y las respuestas inválidas deben elevarse sin reintentar la tarea ni cerrar silenciosamente el fallo.
- Criterio de aceptación: HTTP 500 produce una sola llamada y cierra la respuesta; JSON inválido, estado de error y texto vacío producen errores diferenciados.
- Verificación: test
- Evidencia: tests/test_deepseek_free_agent.py::TestDeepSeekFreeAgent::test_http_error_no_reintenta_y_cierra

## DFA-06: Política de privacidad coherente
- Enunciado: El endpoint intermedio local no debe clasificarse como inferencia local porque el agente reenvía prompts a DeepSeek.
- Criterio de aceptación: `local-only` y `private-documents` rechazan el proveedor mencionando `chat.deepseek.com`; `public` lo admite.
- Verificación: test
- Evidencia: tests/test_deepseek_free_agent.py::TestDeepSeekFreeAgent::test_privacidad_no_lo_confunde_con_modelo_local

## DFA-07: Salida hostil tratada como datos
- Enunciado: Una respuesta que parezca una orden o llamada de herramienta no debe ejecutarse por el adaptador.
- Criterio de aceptación: Una orden JSON de borrado se devuelve como cadena y los dobles de `subprocess.run` y `os.system` no reciben llamadas.
- Verificación: test
- Evidencia: tests/test_deepseek_free_agent.py::TestDeepSeekFreeAgent::test_respuesta_hostil_permanece_como_dato_y_no_ejecuta_procesos

## DFA-08: Mitigación de inyección y auditoría de evidencia
- Enunciado: Las fuentes externas deben delimitarse como datos no confiables y el informe debe conservar comprobaciones de citas y calidad de fuente.
- Criterio de aceptación: Se escapan cierres delimitadores y el informe registra `citation_verification`, `source_quality` y soporte léxico de una cita válida.
- Verificación: test
- Evidencia: tests/test_prompt_injection.py::TestPromptsConDatosNoConfiables::test_informe_declara_datos_y_audita_citas

## DFA-09: Gates de cambios y revisión humana
- Enunciado: La integración debe quedar cubierta por la cadena existente de lint, preflight, documentación, tests, secretos, auditoría de diff y holdout.
- Criterio de aceptación: El hook pre-commit conserva todos los gates declarados y `make check` conserva su agregación; ninguna protección se desactiva para este proveedor.
- Verificación: test
- Evidencia: tests/test_guardrails.py::TestCadenaDeSalvaguardas::test_pre_commit_no_pierde_gates

## DFA-10: Declaración honesta de límites
- Enunciado: La especificación debe prohibir las promesas de inferencia local, ausencia de alucinaciones, sandbox y disponibilidad ilimitada.
- Criterio de aceptación: Existe una especificación formal que declara egreso externo, límites de la verificación léxica, ausencia de sandbox y límites de cuenta o servicio.
- Verificación: formal
- Evidencia: docs/DEEPSEEK-FREE-AGENT.md

## DFA-11: Sin cobro ni fallback pagado
- Enunciado: El conector debe usar únicamente el servicio gratuito seleccionado, sin API key ni sustitución por un proveedor de pago.
- Criterio de aceptación: El coste estimado es cero, el cliente no tiene `api_key` y HTTP 402 produce una sola llamada, cierra la respuesta y eleva un error sin fallback.
- Verificación: test
- Evidencia: tests/test_deepseek_free_agent.py::TestDeepSeekFreeAgent::test_sin_cobro_ni_fallback_pagado

## DFA-12: Disponibilidad y calidad del servicio real
- Enunciado: La conexión real, la sesión y la calidad factual deben comprobarse con una cuenta y una revisión humana antes de darlas por válidas.
- Criterio de aceptación: Una ejecución real registra versión del paquete, respuesta, latencia, fuentes y discrepancias; sin esa evidencia el estado permanece no verificado.
- Verificación: manual
- Notas: El 2026-11-06 hubo respuesta factual correcta y pipeline 4/4, pero también texto intermedio en una subpregunta y 0 citas válidas. La calidad/disponibilidad general sigue requiriendo revisión humana; evidencia local `build/deepseek-free-agent-runtime/workspace/resultado-fotosintesis-2.json`.
