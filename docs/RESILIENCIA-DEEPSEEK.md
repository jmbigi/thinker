# Resiliencia y límites de DeepSeek Free Agent

## Objetivo

El conector `deepseek-free-agent` usa el servicio web de DeepSeek sin API key
ni cobro de thinker. No es un modelo local, no es ilimitado y **no conmuta
automáticamente** a Ollama ni a otro proveedor: un fallo se eleva para que sea
visible (regla 17 de `AGENTS.md`).

## Contrato: sin fallback ni reintentos

- **Sin reintentos**: una tarea se envía una sola vez. Un HTTP 5xx, un timeout,
  una respuesta no JSON o un texto intermedio de verificación/UI elevan el
  error; no se repite la tarea ni se abre otro chat.
- **Sin fallback interno**: `--fallback-model` se rechaza con
  `--provider deepseek-free-agent`. El plugin no instala `LocalFallbackLLM`.
- **Sin proveedor de pago**: no se usa DeepSeek API, OpenRouter ni otro
  proveedor de pago como sustituto.
- **Sin claves**: el conector no lee ni envía `OPENAI_API_KEY`,
  `DEEPSEEK_API_KEY` ni una `API_KEY` genérica. Solo habla con el servicio
  loopback configurado.

`LocalFallbackLLM` sigue existiendo para otros proveedores que lo pidan de
forma explícita con `--fallback-model`; solo conmuta ante fallos operativos
(red, timeout, 429, 5xx). No conmuta ante 400, 401, 403, 404, 422, `ValueError`
ni `PermissionError`.

## Privacidad

`PrivacyPolicy` valida el proveedor antes de la llamada:

- `public`: permitido (el prompt sale a `chat.deepseek.com`).
- `local-only` y `private-documents`: rechazado con `RuntimeError`, porque el
  servicio reenvía los prompts a DeepSeek.

## Configuración del plugin (`DeepSeekFreeAgentPlugin`)

| Parámetro | Tipo | Defecto | Descripción |
|---|---|---|---|
| `base_url` | string | `http://127.0.0.1:9527` | Endpoint loopback del agente |
| `timeout` | number | `300.0` | Segundos de espera de respuesta |
| `authorized` | boolean | `false` | Autorización explícita; sin ella `initialize()` devuelve `false` |

La configuración distribuida en `config/plugins.yaml` deja el plugin
`enabled: false` y `authorized: false`. Actívalo solo en tu configuración local
después de leer `docs/DEEPSEEK-FREE-AGENT.md`.

## CLI (`research_cli.py`)

| Argumento | Descripción |
|---|---|
| `--authorize-deepseek-agent` | Autoriza el egreso a DeepSeek. Sin este flag `generate()` eleva `PermissionError`. |
| `--deepseek-agent-url` | URL loopback alternativa (o `DEEPSEEK_AGENT_URL`). |
| `--deepseek-agent-timeout` | Timeout de lectura en segundos. |

El flag antiguo `--deepseek-agent-fallback-model` **se eliminó**: ya no forma
parte de la CLI.

## Respaldo local: estrategia separada

Si el servicio gratuito no está disponible y quieres usar Ollama, ejecútalo
como proveedor explícito y separado:

```bash
research "pregunta" --provider ollama --model deepseek-r1:8b \
  --documents ./corpus --privacy private-documents
```

Eso no es un fallback automático del conector: es otra invocación, con su propio
ámbito de privacidad y su propio modelo.

## Verificación

- `python3 -m unittest tests.test_deepseek_free_agent -v`: **22/22 OK**
  (2026-11-07), incluidos autorización, loopback, sin reintentos, sin fallback,
  rechazo de texto intermedio, caché y privacidad.
- La suite completa se verifica con `make check` / `bash scripts/ci.sh` sobre una
  copia limpia de HEAD.

## Kimi Code (configuración aislada local)

Un archivo `config.toml` mínimo para probar Ollama de forma aislada:

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

Si tienes `kimi` instalado, puedes validar el archivo con
`kimi doctor config <archivo>`; este ejemplo es local y no forma parte de los
gates del repo ni se ha verificado en esta revisión.

---

**Evidencias**: `tests/test_deepseek_free_agent.py` (22/22 OK, 2026-11-07),
`llm_providers.py`, `research_cli.py` y `docs/DEEPSEEK-FREE-AGENT.md`.
