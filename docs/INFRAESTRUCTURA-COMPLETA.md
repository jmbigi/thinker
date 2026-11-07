# Infraestructura de IA local y modelos gratuitos

**Fecha:** 2026-11-07  
**Ámbito:** orquestación local con Ollama, proxy de contexto y llama.cpp; configuración de Kimi Code y OpenCode con un modelo gratuito de OpenRouter.  
**Estado:** la configuración de Kimi Code valida con `kimi doctor`; OpenCode resuelve el modelo gratuito; los servicios locales se comprueban con `make local-status`. El modelo gratuito remoto exige red y `OPENROUTER_API_KEY`; no es local y su contexto efectivo lo fija el proveedor.

## Resumen

| Pieza | Detalle |
|-------|---------|
| Ollama (11434) | `deepseek-r1:8b` (5,2 GB, Q4_K_M) y otros modelos locales. |
| Proxy de contexto (11435) | `build/ollama-context-proxy`; inyecta `num_ctx=131072` en `/v1/chat/completions` y elimina `max_tokens`. |
| llama.cpp (11436) | Servidor opcional `build/llama-cpp-server.py`, compatible con OpenAI; health en `/health`. |
| Kimi Code | `~/.kimi-code/config.toml`; modelo por defecto gratuito de OpenRouter y Ollama local como alternativa. |
| OpenCode | `~/.config/opencode/opencode.jsonc`; modelo gratuito de OpenRouter. |
| DeepSeek Free Agent | Integración opt-in con fallback local declarado; no es un modelo local. |

## Arquitectura

```
Kimi Code / OpenCode ── OpenRouter ──> nvidia/nemotron-3-ultra-550b-a55b:free
        │                                   (remoto, coste 0, requiere red)
        │
        └── :11435 proxy ──> Ollama :11434 (deepseek-r1:8b, contexto ampliado)

research / smart-research ──> Ollama o proxy
llama.cpp :11436 <── clientes OpenAI-compatibles (opcional)
```

El proxy y Ollama escuchan solo en loopback. El modelo gratuito de OpenRouter no es privado: los prompts salen de la máquina.

## Scripts

Los scripts están en la raíz del repositorio:

| Script | Uso | Qué hace |
|--------|-----|----------|
| `start-all.sh` | `./start-all.sh` | Levanta Ollama si hace falta, el proxy 11435 y el servidor llama.cpp 11436. Bloquea hasta Ctrl+C. |
| `research-local.sh` | `./research-local.sh "pregunta"` | Investigación con Ollama local a través del proxy, corpus local y privacidad `private-documents`. |
| `smart-research.sh` | `./smart-research.sh "pregunta"` | Prueba varias estrategias (Ollama, DeepSeek Free Agent, fallback local) y registra el resultado. |
| `scripts/scan_secrets.py` | `make secrets` | Escanea credenciales y datos personales en archivos versionados. |

`start-all.sh` usa `pkill -f` para detener el proxy y llama.cpp al salir; puede afectar a otras instancias con el mismo nombre. Ollama se deja corriendo.

## Makefile

Targets locales (opt-in, no sustituyen los gates del proyecto):

```bash
make local-status                 # estado de 11434, 11435 y 11436
make local-doctor                 # estado + modelos de Ollama
make local-up                     # ejecuta start-all.sh (bloquea)
make local-research Q="pregunta"  # investigación local
make local-smart Q="pregunta"     # investigación con fallback
make ai-check                     # comprueba Kimi/OpenCode y el modelo gratuito
```

Gates del proyecto:

```bash
make lint          # ruff
make preflight     # AST, imports, silencios, duplicados
make docs-check    # coherencia de cifras documentadas
make test          # suite unittest
make secrets       # escaneo de secretos
make doctor        # autodiagnóstico del entorno
make verify-install
make check         # gates + hook
```

El Makefile no escribe configuraciones de usuario; `make ai-check` solo verifica, sin escribir ni imprimir claves.

## Configuración de Kimi Code

Archivo de usuario: `~/.kimi-code/config.toml` (no se versiona). Extracto sin claves:

```toml
default_model = "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"

[providers.openrouter]
type = "openai"
base_url = "https://openrouter.ai/api/v1"
api_key_env = "OPENROUTER_API_KEY"

[models."openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"]
provider = "openrouter"
model = "nvidia/nemotron-3-ultra-550b-a55b:free"
max_context_size = 1000000
max_output_size = 65536
capabilities = ["thinking", "tool_use"]

# Alternativa local (offline):
# default_model = "ollama/deepseek-r1:8b"
[providers.ollama]
type = "openai"
base_url = "http://127.0.0.1:11435/v1"
api_key = "ollama"

[models."ollama/deepseek-r1:8b"]
provider = "ollama"
model = "deepseek-r1:8b"
max_context_size = 131072
max_output_size = 8192
capabilities = ["thinking", "tool_use"]
```

`api_key_env` indica que la clave se lee de `OPENROUTER_API_KEY`; no se escribe en el archivo. Para trabajar sin red, cambia `default_model` a `ollama/deepseek-r1:8b` y levanta el proxy con `./start-all.sh`.

## Configuración de OpenCode

Archivo de usuario: `~/.config/opencode/opencode.jsonc` (no se versiona). El modelo seleccionado es:

```jsonc
{
  "model": "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"
}
```

OpenCode obtiene los metadatos del proveedor; si añades una entrada personalizada en `provider.openrouter.models`, su clave debe coincidir con el identificador del modelo (`nvidia/nemotron-3-ultra-550b-a55b:free`) y sus límites no deben presentarse como los del proveedor. El límite efectivo lo fija OpenRouter.

La ruta vigente es la indicada arriba; otras rutas de configuraciones antiguas no se usan en este proyecto.

## Verificación

Comandos y resultado esperado:

```bash
make local-status
# UP solo si los servicios están levantados; DOWN no es un fallo del repo.

curl -s http://127.0.0.1:11434/api/tags | jq -r '.models[].name'
# Lista los modelos locales (requiere Ollama).

curl -s http://127.0.0.1:11435/v1/models | jq -r '.data[].id'
# Lista los modelos expuestos por el proxy (requiere el proxy).

kimi doctor
# OK de los archivos de configuración; no prueba la red ni la calidad del modelo.

opencode models | grep 'openrouter/nvidia/nemotron-3-ultra-550b-a55b:free'
# El modelo gratuito debe aparecer en la lista.

make ai-check
# Comprueba que Kimi y OpenCode declaran el modelo gratuito; no imprime claves.

python3 -m unittest discover -s tests -q
ruff check .
python3 scripts/check_docs.py
```

La suite del proyecto figura en `AGENTS.md` (1426 tests en la última medición registrada); el hook pre-commit la ejecuta antes de cada commit.

## Métricas declaradas

- Contexto local: 131.072 tokens mediante el proxy (según su código y la configuración de Kimi).
- Modelo gratuito: 1.000.000 de contexto declarado en Kimi; el límite efectivo depende de OpenRouter.
- No se incluyen latencias ni throughput no reproducidos. Para medirlos, usa `scripts/probe_model.py` (opt-in, red y clave) o los scripts locales.

## Seguridad y privacidad

- Ollama y el proxy escuchan en `127.0.0.1`; no los expongas a la red.
- El proxy no añade autenticación; es una herramienta local.
- `OPENROUTER_API_KEY` vive en el entorno. `.env` no se versiona y `scripts/scan_secrets.py` bloquea credenciales y rutas personales.
- El modelo gratuito envía prompts a OpenRouter: no es adecuado para documentos privados. Para privacidad, usa Ollama local y `--privacy private-documents`.
- El escaneo de secretos y la validación léxica no demuestran privacidad ni calidad del modelo.

## Limitaciones

- `deepseek-r1:8b` es un modelo pequeño: su calidad es inferior a la de modelos grandes.
- La inyección de `num_ctx` aplica a las rutas OpenAI-compatibles del proxy; los clientes que usan la API nativa de Ollama o fijan su propio contexto pueden no beneficiarse.
- `start-all.sh` detiene procesos por nombre con `pkill -f`; revisa que no haya otras instancias antes de ejecutarlo.
- llama.cpp es opcional y depende de que el servidor y sus dependencias estén disponibles.
- Las configuraciones de Kimi y OpenCode son de usuario y no forman parte del repositorio; `make ai-check` verifica presencia, no calidad ni disponibilidad.
- El modelo `:free` puede tener límites de cuota o disponibilidad; «gratuito» no significa «sin límites».

## Referencias

- Ollama: <https://ollama.com/library>
- OpenRouter: <https://openrouter.ai/docs>
- Kimi Code: configuración local `~/.kimi-code/config.toml`
- OpenCode: <https://opencode.ai/docs>
- llama.cpp: <https://github.com/ggerganov/llama.cpp>
- Proxy del proyecto: `build/ollama-context-proxy.go`
