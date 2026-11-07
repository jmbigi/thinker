# Resiliencia local para DeepSeek Free Agent

## Objetivo
Garantizar que una tarea de investigación pueda completarse sin depender de la disponibilidad del servicio web de DeepSeek (chat.deepseek.com) ni de la API pagada. El respaldo local usa Ollama con un modelo descargado y se activa solo ante fallos operativos del proveedor principal.

## Contrato del fallback (`LocalFallbackLLM`)

- **Regla de conmutación**: solo errores operativos del proveedor principal (red, timeout, HTTP 5xx, error JSON, respuestas intermedias) disparan la conmutación. `ValueError` (prompt vacío) y `PermissionError` (sin autorización) **no** conmutan.
- **Modelo de respaldo**: se especifica explícitamente (`deepseek-r1:8b` por defecto en CLI y plugin). No hay auto-detección ni auto-selección.
- **Registro**: cada conmutación incrementa `fallback_calls`, guarda el motivo en `last_fallback_reason` y emite una línea a `stderr` con modelo local usado.
- **Cache**: no hay caché compartida. `LocalFallbackLLM` no cachea; el proveedor
  principal solo guarda éxitos. Tras conmutar, la siguiente llamada vuelve a
  intentar el principal y solo usa el local si vuelve a fallar.
- **Privacidad**: `PrivacyPolicy` valida tanto el proveedor principal como el respaldo; el fallback solo pasa con `public` si **ambos** cumplen la política.

## Contratos de prueba (`tests/test_deepseek_free_agent.py`)

- `TestLocalFallback.test_fallo_operativo_usa_local_y_lo_declara`: error operativo conmutado, respuesta local, contador y motivo registrados, stderr llamado.
- `TestLocalFallback.test_exito_principal_y_errores_de_uso_no_conmutan`: éxito principal devuelve principal; `ValueError`/`PermissionError` no conmutan.
- `TestLocalFallback.test_cli_y_privacidad_del_fallback`: CLI construye `LocalFallbackLLM` con modelo explícito; `private-documents` rechaza por `chat.deepseek.com`; `--deepseek-agent-fallback-model` sin `--provider deepseek-free-agent` da `ValueError`.

## Política de privacidad (`PrivacyPolicy`)

- `LocalFallbackLLM` se valida recorriendo **ambos** proveedores (primario y fallback). Solo pasa si **ambos** cumplen el ámbito:
  - `public`: siempre permitido.
  - `local-only` / `private-documents`: rechazado porque `deepseek-free-agent` reenvía a `chat.deepseek.com`.

## Configuración del proveedor (`DeepSeekFreeAgentPlugin`)

| Parámetro | Tipo | Defecto | Descripción |
|---|---|---|---|
| `base_url` | string | `http://127.0.0.1:9527` | Endpoint loopback del agente |
| `timeout` | number | `300.0` | Segundos de espera de respuesta |
| `authorized` | boolean | `false` | Requiere `--authorize-deepseek-agent` o `authorized: true` |
| `fallback_model` | string | `""` | Modelo Ollama para respaldo (vacío = sin fallback) |

Si `fallback_model` está vacío o ausente, el plugin carga solo `DeepSeekFreeAgentLLM` sin fallback.

## CLI (`research_cli.py`)

| Argumento | Descripción |
|---|---|
| `--deepseek-agent-fallback-model` | Modelo Ollama para respaldo (p. ej. `deepseek-r1:8b`). Opcional; si se omite usa `deepseek-r1:8b`; sin valor se ignora. Exige `--provider deepseek-free-agent`. |

El CLI construye `LocalFallbackLLM(primary, OllamaLLM(model=args.deepseek_agent_fallback_model))` cuando se proporciona el argumento. Si no se pasa, usa `DeepSeekFreeAgentLLM` sin fallback.

## Plugin `deepseek_free_agent`

La configuración declarativa en `config/plugins.yaml` incluye `fallback_model`:

```yaml
deepseek_free_agent:
  enabled: true
  priority: 110
  params:
    base_url: "http://127.0.0.1:9527"
    timeout: 300
    authorized: true
    fallback_model: "deepseek-r1:8b"
```

Si `fallback_model` es no vacío, el plugin instancia `LocalFallbackLLM(primary, OllamaLLM(model=fallback_model))`. Sin `fallback_model`, solo `DeepSeekFreeAgentLLM`.

## Verificación (`kimi doctor` y tests)

- `python3 -m unittest tests.test_deepseek_free_agent -v`: 19/19 tests OK (incluye 4 tests de `TestLocalFallback`).
- `kimi doctor config config.toml`: valida esquema y que el modelo está declarado.
- `kimi doctor` sobre la config completa: OK.

## Resiliencia operativa (resumen)

| Escenario | Resultado |
|---|---|
| Servicio web DeepSeek caído (`RuntimeError`) | Conmuta a Ollama local, registra motivo y modelo, emite stderr, sin caché compartida. |
| DeepSeek responde `One more step before you proceed...` | Rechazado como texto intermedio; lanza `RuntimeError` → conmuta si hay fallback. |
| `ERR_NETWORK_CHANGED` / `HTTP 5xx` | Conmuta. |
| Prompt vacío / sin autorización | **No** conmuta; error explícito visible. |
| Política `private-documents` | Rechaza antes de cualquier llamada. |

## Activación manual (resumen CLI)

```bash
# Solo DeepSeek web (sin fallback)
research "pregunta" --provider deepseek-free-agent --authorize-deepseek-agent

# Con respaldo local Ollama
research "pregunta" \
  --provider deepseek-free-agent --authorize-deepseek-agent \
  --deepseek-agent-fallback-model deepseek-r1:8b
```

## Kimi Code (configuración aislada local)

Un archivo `config.toml` mínimo para probar aisladamente:

```toml
default_model = "ollama/deepseek-r1:8b"

[providers.ollama]
type = "openai"
base_url = "http://127.0.0.1:11434/v1"
api_key = ""

[models."ollama/deepseek-r1:8b"]
provider = "ollama"
model = "deepseek-r1:8b"
max_context_size = 131072
max_output_size = 8192
capabilities = [ "thinking", "tool_use" ]
display_name = "DeepSeek R1 8B Local"
reasoning_key = "reasoning_content"
```

Validación: `kimi doctor config <archivo>` → OK.

---

**Evidencias**: `tests/test_deepseek_free_agent.py` (19/19 OK), `kimi doctor` (OK), `research_cli.py` y `llm_providers.py` (compilación OK), suite completa `1488/1488`.