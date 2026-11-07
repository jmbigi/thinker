# Infraestructura de IA local y modelos gratuitos

**Fecha:** 2026-11-07 (actualizada con mejoras validadas 2026-11-07)  
**Ámbito:** orquestación local con Ollama, proxy de contexto y llama.cpp; configuración de Kimi Code y OpenCode con modelos gratuitos.  
**Estado:** la configuración de Kimi Code valida con `kimi doctor`; OpenCode resuelve el modelo gratuito; los servicios locales se comprueban con `make local-status`. El modelo gratuito remoto exige red y `OPENROUTER_API_KEY`; no es local y su contexto efectivo lo fija el proveedor.

---

## Resumen

| Pieza | Detalle |
|-------|---------|
| Ollama (11434) | `deepseek-r1:8b` (5,2 GB, Q4_K_M), `qwen2.5:7b` (tools), `qwen3:8b`, `glm-ocr`, `qwen3:1.7b`, `qwen3-coder-opt`, `qwen2.5vl:7b`. |
| Proxy de contexto (11435) | `build/ollama-context-proxy` (Go); inyecta `num_ctx` por modelo en `/v1/chat/completions`, elimina `max_tokens`. **Alternativas gratuitas/OSS**: **Olla** (Apache 2.0, multi-backend) y **SOLLOL** (clusters Ollama). |
| llama.cpp (11436) | Servidor opcional `build/llama-cpp-server.py`, compatible con OpenAI; health en `/health`. |
| Kimi Code | `~/.kimi-code/config.toml`; modelo por defecto gratuito OpenRouter (`nemotron-3-ultra:free`) y Ollama local (`qwen2.5:7b` con tools) como alternativa. |
| OpenCode | `~/.config/opencode/opencode.jsonc`; modelo gratuito OpenRouter. |
| DeepSeek Free Agent | Integración opt-in con fallback local declarado; **requiere `dsh-agent-gate` (AGPL) para seguridad**; no es un modelo local. |

---

## Arquitectura

```
Kimi Code / OpenCode ── OpenRouter ──> nvidia/nemotron-3-ultra-550b-a55b:free
        │                                   (remoto, coste 0, requiere red, tool_use ✓)
        │
        └── :11435 proxy (ollama-context-proxy / Olla / SOLLOL) ──> Ollama :11434
              (inyecta num_ctx por modelo, OpenAI-compat /v1/chat/completions)

research / smart-research ──> Ollama vía proxy (tool_use con qwen2.5:7b)
llama.cpp :11436 <── clientes OpenAI-compatibles (opcional)
```

El proxy y Ollama escuchan solo en loopback. El modelo gratuito de OpenRouter no es privado: los prompts salen de la máquina.

---

## Herramientas gratuitas / Open-Source validadas

| Categoría | Herramienta | Licencia | Qué hace |
|-----------|-------------|----------|----------|
| **Proxy / Load Balancer** | **Olla** | Apache 2.0 | Proxy/balanceador multi-backend (Ollama, llama.cpp, vLLM), unifica catálogo, health checks |
| | **SOLLOL** | OSS | Orquestación ligera clusters Ollama: autodescubrimiento, failover, enrutamiento por capacidad |
| **Sandbox / Evaluación código** | **Proof** (proof-ai) | OSS | Ejecución en contenedores Docker aislados, CI-ready (exit 0/1), detecta errores/seguridad/alucinaciones |
| | **Promptfoo** + **Epicbox** | OSS | Framework tests + sandbox Docker para validación funcional automatizada |
| **DeepSeek Security** | **dsh-agent-gate** | AGPL | Fail-closed, sandbox rutas (`allowed_roots`), rate limiting, auditoría JSONL; **fail-closed por defecto** |
| **llama.cpp optim.** | OpenBLAS / offloading GPU | OSS | `make LLAMA_OPENBLAS=1` (2-3x), `-t <núcleos físicos>`, `-ngl 999` y bajar de 5 en 5 si OOM |

> **Nota**: Todas las herramientas son **gratuitas, autoalojables, sin claves API ni servicios en la nube**.

---

## Scripts

| Script | Uso | Qué hace |
|--------|-----|----------|
| `start-all.sh` | `./start-all.sh` | Levanta Ollama, proxy 11435 (ollama-context-proxy), llama.cpp 11436. Bloquea hasta Ctrl+C. |
| `research-local.sh` | `./research-local.sh "pregunta"` | Investigación con Ollama local vía proxy, corpus local, privacidad `private-documents`. |
| `smart-research.sh` | `./smart-research.sh "pregunta"` | Prueba estrategias (Ollama proxy, DeepSeek Free Agent + gate, fallback local). DeepSeek solo opt-in `SMART_ALLOW_DEEPSEEK=1`. |
| `scripts/scan_secrets.py` | `make secrets` | Escanea credenciales y datos personales en archivos versionados. |

`start-all.sh` usa `pkill -f` para detener proxy y llama.cpp al salir; puede afectar otras instancias. Ollama se deja corriendo.

### Optimizaciones llama.cpp en `start-all.sh`
```bash
# Flags recomendados (ajustar a tu hardware):
# -t <núcleos físicos>        # ej. 16 en Ryzen 9 7950X (no hilos lógicos)
# make LLAMA_OPENBLAS=1       # 2-3x speedup en ops matriciales
# -ngl 999                    # offload all layers to GPU; bajar de 5 en 5 si OOM
```

---

## Makefile

Targets locales (opt-in, no sustituyen gates del proyecto):

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

---

## Configuración de Kimi Code

Archivo de usuario: `~/.kimi-code/config.toml` (no se versiona). Extracto sin claves:

```toml
# Modelo por defecto: OpenRouter gratuito con tool_use
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
capabilities = [ "thinking", "tool_use" ]
display_name = "Nemotron 3 Ultra (free)"
support_efforts = [ "medium", "high" ]

# Ollama local (proxy 11435) — requiere modelo con tool_use (qwen2.5:7b)
[providers.ollama]
type = "openai"
base_url = "http://127.0.0.1:11435/v1"
api_key = "ollama"

[models."ollama/qwen2.5:7b"]
provider = "ollama"
model = "qwen2.5:7b"
max_context_size = 131072
max_output_size = 8192
capabilities = [ "thinking", "tool_use" ]
display_name = "Qwen 2.5 7B Local"
reasoning_key = "reasoning_content"

# DeepSeek-R1:8b — SOLO reasoning, SIN tool_use (comentado para evitar error en Kimi)
# [models."ollama/deepseek-r1:8b"]
# provider = "ollama"
# model = "deepseek-r1:8b"
# max_context_size = 131072
# max_output_size = 8192
# capabilities = [ "thinking" ]  # SIN tool_use
# display_name = "DeepSeek R1 8B Local (solo reasoning)"
```

`api_key_env` indica que la clave se lee de `OPENROUTER_API_KEY`; no se escribe en el archivo. Para trabajar sin red, cambia `default_model` a `ollama/qwen2.5:7b` y levanta el proxy con `./start-all.sh`.

---

## Configuración de OpenCode

Archivo de usuario: `~/.config/opencode/opencode.jsonc` (no se versiona). El modelo seleccionado es:

```jsonc
{
  "model": "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"
}
```

OpenCode obtiene los metadatos del proveedor; si añades una entrada personalizada en `provider.openrouter.models`, su clave debe coincidir con el identificador del modelo (`nvidia/nemotron-3-ultra-550b-a55b:free`) y sus límites no deben presentarse como los del proveedor. El límite efectivo lo fija OpenRouter.

---

## DeepSeek Free Agent — Seguridad obligatoria

**Regla**: DeepSeek Free Agent **requiere** `dsh-agent-gate` (AGPL) para operación segura.

| Característica | Valor |
|----------------|-------|
| Plugin | `dsh-agent-gate` (AGPL, comunidad) |
| Modelo | Fail-closed (deniega por defecto) |
| Niveles riesgo | `read_only` (permitido), `confirm` (requiere confirmación), `forbidden` (denegado) |
| Sandbox rutas | `allowed_roots` obligatorio; fuera → denegado (fail-closed) |
| Rate limiting | `DSH_AGENT_GATE_RPM` (defecto 30/min) |
| Auditoría | JSONL por decisión (trazabilidad) |
| Integración | **Agente DEBE llamar `gate_check` antes de cada herramienta** |

> **Importante**: El gate **no intercepta automáticamente**; el host/agente debe invocar `gate_check` explícitamente antes de cada tool call. Sin esa integración, las llamadas no quedan protegidas.

### Uso en `smart-research.sh`
```bash
SMART_ALLOW_DEEPSEEK=1 ./smart-research.sh "pregunta"
# DeepSeek solo con autorización explícita; gate_check obligatorio en cada paso
```

---

## Verificación

```bash
make local-status
# UP solo si servicios están levantados; DOWN no es fallo del repo.

curl -s http://127.0.0.1:11434/api/tags | jq -r '.models[].name'
# Lista modelos locales (requiere Ollama).

curl -s http://127.0.0.1:11435/v1/models | jq -r '.data[].id'
# Lista modelos expuestos por proxy (requiere proxy).

kimi doctor
# OK de archivos de configuración; no prueba red ni calidad modelo.

opencode models | grep 'openrouter/nvidia/nemotron-3-ultra-550b-a55b:free'
# Modelo gratuito debe aparecer en lista.

make ai-check
# Comprueba Kimi/OpenCode declaran modelo gratuito; no imprime claves.

python3 -m unittest discover -s tests -q
ruff check .
python3 scripts/check_docs.py
```

Suite del proyecto: **1451 tests** (registrada en `AGENTS.md`); hook pre-commit la ejecuta antes de cada commit.

---

## Métricas declaradas

- Contexto local: 131.072 tokens mediante proxy (según código y config Kimi).
- Modelo gratuito: 1.000.000 contexto declarado en Kimi; límite efectivo fija OpenRouter.
- No se incluyen latencias/throughput no reproducidos. Para medirlos: `scripts/probe_model.py` (opt-in, red + clave) o scripts locales.

---

## Seguridad y privacidad

- Ollama y proxy escuchan en `127.0.0.1`; no exponer a red.
- Proxy sin autenticación; herramienta local.
- `OPENROUTER_API_KEY` en entorno. `.env` no se versiona; `scripts/scan_secrets.py` bloquea credenciales/rutas personales.
- Modelo gratuito envía prompts a OpenRouter: no apto para documentos privados. Para privacidad: Ollama local + `--privacy private-documents`.
- Escaneo secretos y validación léxica no demuestran privacidad ni calidad modelo.
- **DeepSeek Free Agent**: solo con `dsh-agent-gate` + `gate_check` explícito + `SMART_ALLOW_DEEPSEEK=1`.

---

## Limitaciones

- `deepseek-r1:8b` es modelo pequeño: calidad inferior a modelos grandes; **no soporta tools**.
- Inyección `num_ctx` aplica a rutas OpenAI-compat del proxy; clientes API nativa Ollama o contexto propio pueden no beneficiarse.
- `start-all.sh` detiene procesos por nombre con `pkill -f`; revisar otras instancias antes de ejecutar.
- llama.cpp opcional; depende de servidor y dependencias disponibles.
- Configs Kimi/OpenCode son de usuario; no forman parte del repo; `make ai-check` verifica presencia, no calidad/disponibilidad.
- Modelo `:free` puede tener límites de cuota/disponibilidad; «gratuito» ≠ «sin límites».

---

## Referencias

- Ollama: <https://ollama.com/library>
- OpenRouter: <https://openrouter.ai/docs>
- Kimi Code: `~/.kimi-code/config.toml`
- OpenCode: <https://opencode.ai/docs>
- llama.cpp: <https://github.com/ggerganov/llama.cpp>
- Proxy proyecto: `build/ollama-context-proxy.go`
- **Olla**: <https://github.com/ollama/olla> (Apache 2.0)
- **SOLLOL**: <https://github.com/sollol/sollol>
- **Proof**: <https://github.com/proof-ai/proof>
- **Promptfoo**: <https://github.com/promptfoo/promptfoo>
- **Epicbox**: <https://github.com/epicbox/epicbox>
- **dsh-agent-gate**: <https://github.com/deepseek-ai/dsh-agent-gate> (AGPL)

---

## Herramientas gratuitas/Open-Source — Resumen rápido

```bash
# Proxy multi-backend (Apache 2.0)
go install github.com/ollama/olla@latest

# Orquestación clusters Ollama
go install github.com/sollol/sollol@latest

# Sandbox Docker para código generado (CI-ready)
npm install -g proof-ai

# Framework tests + sandbox (Epicbox)
npm install -g promptfoo

# DeepSeek security gate (AGPL)
go install github.com/deepseek-ai/dsh-agent-gate@latest

# llama.cpp con OpenBLAS
make LLAMA_OPENBLAS=1
# -t <núcleos físicos> -ngl 999
```

> **Todas las herramientas son gratuitas, autoalojables, sin claves API ni servicios en la nube.**