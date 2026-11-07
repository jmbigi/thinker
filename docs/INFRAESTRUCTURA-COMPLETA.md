# Infraestructura de IA local y modelos gratuitos

**Fecha:** 2026-11-07 (actualizada con mejoras validadas 2026-11-07)  
**Ámbito:** orquestación local con Ollama, proxy de contexto y llama.cpp; configuración de Kimi Code y OpenCode con modelos gratuitos.  
**Estado:** la configuración de Kimi Code valida con `kimi doctor`; OpenCode resuelve el modelo gratuito; los servicios locales se comprueban con `make local-status`. El modelo gratuito remoto exige red y `OPENROUTER_API_KEY`; no es local y su contexto efectivo lo fija el proveedor.

---

## Resumen

| Pieza | Detalle |
|-------|---------|
| Ollama (11434) | `deepseek-r1:8b` (5,2 GB, Q4_K_M), `qwen3:8b`, `glm-ocr`, `qwen3:1.7b`, `qwen3-coder-opt`, `qwen2.5vl:7b`. |
| Proxy de contexto (11435) | `build/ollama-context-proxy` (Go); inyecta `num_ctx` por modelo en `/v1/chat/completions`, elimina `max_tokens`. **Alternativas gratuitas/OSS**: **Olla** (Apache 2.0, multi-backend) y **SOLLOL** (MIT, orquestador de clusters Ollama). |
| llama.cpp (11436) | Servidor opcional `build/llama-cpp-server.py`, compatible con OpenAI; health en `/health`. |
| Kimi Code | `~/.kimi-code/config.toml`; modelo por defecto gratuito OpenRouter (`nemotron-3-ultra:free`) y Ollama local (`qwen3:8b`) como alternativa. |
| OpenCode | `~/.config/opencode/opencode.jsonc`; OpenRouter gratuito y proveedor Kilo (`kilo-auto/free`). |
| Kilo AI Gateway | `research --provider kilo` / plugin `kilo`; `cohere/north-mini-code:free` anónimo (200 req/h por IP), `kilo-auto/free` como auto-routing; `KILO_API_KEY` para el catálogo completo; remoto y con cuota. |
| DeepSeek Free Agent | Integración opt-in con fallback local declarado; **solo intercambia texto, no ejecuta herramientas**; no es un modelo local. |

---

## Arquitectura

```
Kimi Code / OpenCode ── OpenRouter ──> nvidia/nemotron-3-ultra-550b-a55b:free
        │                                   (remoto, coste 0, requiere red, tool_use ✓)
        ├── Kilo Gateway ──> cohere/north-mini-code:free (remoto, 0 €, 200 req/h por IP)
        │
        └── :11435 proxy (ollama-context-proxy / Olla / SOLLOL) ──> Ollama :11434
              (inyecta num_ctx por modelo, OpenAI-compat /v1/chat/completions)

research / smart-research ──> Ollama vía proxy (tool_use con qwen3:8b)
                          ──> OpenRouter / Kilo / DeepSeek (opt-in, remoto)
llama.cpp :11436 <── clientes OpenAI-compatibles (opcional)
```

El proxy y Ollama escuchan solo en loopback. OpenRouter, Kilo y DeepSeek no son
privados: los prompts salen de la máquina y sus cuotas/límites aplican.

---

## Herramientas gratuitas / Open-Source evaluadas

| Categoría | Herramienta | Licencia | Qué hace | Integración real en thinker |
|-----------|-------------|----------|----------|-----------------------------|
| **Proxy / Load Balancer** | **Olla** | Apache 2.0 | Proxy/balanceador multi-backend (Ollama, llama.cpp, vLLM), catálogo unificado y health checks | Plugin `olla` opt-in (`plugins/llm_providers/olla_plugin.py`); salud `/internal/health`, API `/olla/proxy/v1/*` |
| | **SOLLOL** | MIT | Orquestación de clusters Ollama: autodescubrimiento, failover, enrutamiento | **Externo** (PyPI `sollol`); no es un plugin de thinker |
| **Sandbox / Evaluación código** | **Proof** (proof-ai) | MIT | Verificación de código generado; reglas + Docker opcional | **Externo/no integrado** (Node/Docker). `code_evaluator.py` ofrece evaluación local/offline (`ast.parse` + subproceso `shell=False`, timeout, sin red); aislamiento limitado, no sandbox de contenedor. |
| | **Promptfoo** + **Epicbox** | MIT | Framework de evaluación y sandbox Docker | **No integrado**: requiere Node/Docker; no se declara como parte del flujo |
| **Gate de herramientas** | **dsh-agent-gate** | AGPL | Plugin comunitario para DeepSeek Harness: riesgo, raíces, cuota y auditoría | **No usable desde Python** (plugin Node/TS). `LocalToolGate` reimplementa la política en local, offline y con tests |
| **llama.cpp optim.** | OpenBLAS / offloading GPU | OSS | `make LLAMA_OPENBLAS=1` acelera **prefill** (prompts largos), no la generación token a token; `-t` ya usa núcleos físicos; `-ngl 999` y bajar de 5 en 5 si OOM | Flags documentados; el benchmark mide el efecto real |

> **Nota de alcance**: Olla, SOLLOL, Proof, Promptfoo y dsh-agent-gate son
> gratuitos y autoalojables, pero **no todos están integrados** (ver columna).
> El modelo gratuito de OpenRouter **sí es un servicio en la nube**: no es
> privado y tiene cuota diaria; no se presenta como ilimitado.

---

## Scripts

| Script | Uso | Qué hace |
|--------|-----|----------|
| `start-all.sh` | `./start-all.sh` | Levanta Ollama, proxy 11435 (ollama-context-proxy) y llama.cpp 11436. Bloquea hasta Ctrl+C. |
| `research-local.sh` | `./research-local.sh "pregunta"` | Investigación con Ollama local vía proxy, corpus local, privacidad `private-documents`. |
| `smart-research.sh` | `./smart-research.sh "pregunta"` | Prueba estrategias (Ollama proxy, DeepSeek Free Agent con fallback local). DeepSeek solo opt-in `SMART_ALLOW_DEEPSEEK=1`. |
| `scripts/benchmark_llama_cpp.py` | `python3 scripts/benchmark_llama_cpp.py --backend ollama --model qwen3:8b` | Mide prefill, generación, TTFT y latencia contra llama.cpp, Ollama u Olla. |
| `scripts/scan_secrets.py` | `make secrets` | Escanea credenciales y datos personales en archivos versionados. |
| `tests/test_security_gate.py` | `python3 -m unittest tests.test_security_gate -v` | Verifica el gate local fail-closed (`LocalToolGate`): raíces, cuota, confirmación y auditoría. |

`start-all.sh` solo detiene los procesos que él mismo inició (guarda sus PIDs);
si un servicio ya estaba activo, lo reutiliza y no lo toca. Ollama se deja
corriendo. No se añade otro script que arranque o mate servicios:
`scripts/start-olla-cluster.sh` se retiró por duplicar `start-all.sh` y usar
`pkill` sobre procesos ajenos.

### Olla: puesta en marcha manual (opcional)

```bash
# Instalar (Go 1.22+) o usar la imagen oficial
go install github.com/thushan/olla@latest
# o: docker run -p 40114:40114 ghcr.io/thushan/olla:latest

# Crear config/config.local.yaml con un endpoint Ollama y arrancar
olla --config config/config.local.yaml

# Comprobar
curl http://localhost:40114/internal/health
curl http://localhost:40114/olla/proxy/v1/models
```

Después se activa el plugin en `config/plugins.yaml` (`olla.enabled: true`) o se
usa `--ollama-base-url http://127.0.0.1:40114/olla/proxy/v1 --ollama-api openai`.
No se arranca automáticamente porque el binario y su configuración son opt-in.

### Optimizaciones llama.cpp en `start-all.sh`
```bash
# Flags recomendados (ajustar a tu hardware):
# -t <núcleos físicos>        # Por defecto llama.cpp ya usa núcleos físicos; solo forzar si necesario
# make LLAMA_OPENBLAS=1       # Acelera PREFIll (prompts largos); impacto en generación token-a-token limitado/nulo
# -ngl 999                    # Offload all layers to GPU; bajar de 5 en 5 si OOM
# stream_buffer_size          # 2-4 KB (chat baja latencia) / 8 KB (equilibrio) si se usa proxy adicional
```

> **Nota técnica**: OpenBLAS acelera el procesamiento de prompts (prefill), no la generación token-a-token. La documentación de llama.cpp lo recomienda para "faster prompt processing". El parámetro `-t` (hilos) se autodetecta a núcleos físicos por defecto; el ajuste manual solo es necesario para forzar un valor distinto.

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

# Ollama local (proxy 11435) — modelo instalado con tool_use
[providers.ollama]
type = "openai"
base_url = "http://127.0.0.1:11435/v1"
api_key = "ollama"

[models."ollama/qwen3:8b"]
provider = "ollama"
model = "qwen3:8b"
max_context_size = 131072
max_output_size = 8192
capabilities = [ "thinking", "tool_use" ]
display_name = "Qwen3 8B Local"
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

`api_key_env` indica que la clave se lee de `OPENROUTER_API_KEY`; no se escribe en el archivo. Para trabajar sin red, cambia `default_model` a `ollama/qwen3:8b` y levanta el proxy con `./start-all.sh`.

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

## DeepSeek Free Agent — alcance y seguridad

`DeepSeekFreeAgentLLM` **solo intercambia texto**: no ejecuta herramientas y, por
tanto, no requiere un gate de herramientas. El puerto 9527 es del servicio
`deepseek-free-agent` (Playwright + Chromium), no de un gate.

`dsh-agent-gate` es un plugin Node/TypeScript para DeepSeek Harness; no es un
servicio HTTP y no se puede invocar desde Python. Para agentes Python que sí
ejecutan tool calls, thinker incluye `LocalToolGate` (offline, fail-closed):
`allowed_roots`, cuota por minuto, confirmación humana y auditoría JSONL. No es
el plugin: es una reimplementación local de su política.

### Uso en `smart-research.sh`
```bash
SMART_ALLOW_DEEPSEEK=1 ./smart-research.sh "pregunta"
# DeepSeek solo con autorización explícita; fallback local si falla.
```

Ver `docs/DEEPSEEK-FREE-AGENT.md` para el contrato, la verificación real del
2026-11-07 y los límites (no es ilimitado).

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

Suite del proyecto: **1492 tests** (registrada en `AGENTS.md`); hook pre-commit la ejecuta antes de cada commit.

---

## Matriz real: coste, cuota y calidad (medido 2026-11-07)

Equipo: 16 CPU, 15 GiB RAM, sin GPU utilizable (`nvidia-smi` falla). Las
latencias son de **una pasada en frío** (incluye carga de modelo); no son un
benchmark sostenido ni una medida de calidad factual.

| Camino | Coste | Cuota | Privacidad | Modelo | Medición |
|--------|-------|-------|------------|--------|----------|
| Ollama `qwen3:8b` | 0 | **sin cuota** | local | 8B, tool_use | 62,1 tok/s; TTFT 14,4 s |
| Ollama `deepseek-r1:8b` | 0 | **sin cuota** | local | 8B reasoning, sin tools | 58,6 tok/s; TTFT 8,7 s |
| DeepSeek Free Agent | 0 con cuenta | límites del servicio | prompts a DeepSeek | modelo web | «OK» en 43,2 s |
| OpenRouter `:free` | 0 | **cuota diaria** | prompts a OpenRouter | modelo grande | el límite diario bloqueó el 2026-11-07 (`free-models-per-day-high-balance`); no se midió |
| Kilo `cohere/north-mini-code:free` | 0 | **200 req/h por IP** (anónimo) | prompts a Kilo | free, 256k | «París» en 1,4 s; «OK» en 0,9 s |
| Kilo `kilo-auto/free` | 0 | 200 req/h por IP (anónimo) | prompts a Kilo | auto-ruteado | «OK» en 3,9 s (puede elegir un reasoning lento) |

Lectura honesta:

- **Ilimitado** solo es defendible en local: no hay cuota de API, pero el
  hardware y el tamaño del modelo son el límite real. 8B no es «muy bueno» para
  todo; no se declara calidad frontier.
- **Muy bueno** con coste 0 depende hoy de cuotas externas (OpenRouter,
  Kilo y DeepSeek). Cuando la cuota se agota, el respaldo local mantiene el servicio:
  `--fallback-model qwen3:8b`.
- No se puede garantizar que un modelo externo no rechace una petición; no se
  implementan técnicas para eludir las políticas del proveedor. «Sin
  protestar» se interpreta aquí como **sin fallos silenciosos por cuota**: el
  pipeline declara el proveedor usado y falla de forma visible si no hay ninguno.

Comandos reproducibles:

```bash
python3 scripts/benchmark_llama_cpp.py --backend ollama --model qwen3:8b \
  --max-tokens 32 --runs 1
python3 scripts/benchmark_llama_cpp.py --backend ollama --model deepseek-r1:8b \
  --max-tokens 32 --runs 1
# DeepSeek: arrancar el agente y ejecutar la prueba de docs/DEEPSEEK-FREE-AGENT.md
```

## Métricas declaradas

- Contexto local: 131.072 tokens mediante proxy (según código y config Kimi).
- Modelo gratuito: 1.000.000 contexto declarado en Kimi; límite efectivo fija OpenRouter.
- Las cifras de la matriz anterior son medidas puntuales, no promedios ni promesas.

---

## Seguridad y privacidad

- Ollama y proxy escuchan en `127.0.0.1`; no exponer a red.
- Proxy sin autenticación; herramienta local.
- `OPENROUTER_API_KEY` en entorno. `.env` no se versiona; `scripts/scan_secrets.py` bloquea credenciales/rutas personales.
- Modelo gratuito envía prompts a OpenRouter: no apto para documentos privados. Para privacidad: Ollama local + `--privacy private-documents`.
- Escaneo secretos y validación léxica no demuestran privacidad ni calidad modelo.
- **DeepSeek Free Agent**: solo con `SMART_ALLOW_DEEPSEEK=1`; no ejecuta
  herramientas y no se presenta como ilimitado. Su salida es texto no confiable.

---

## Limitaciones

- `deepseek-r1:8b` es modelo pequeño: calidad inferior a modelos grandes; **no soporta tools**.
- Inyección `num_ctx` aplica a rutas OpenAI-compat del proxy; clientes API nativa Ollama o contexto propio pueden no beneficiarse.
- `start-all.sh` solo detiene los PIDs que inició; si reutiliza un servicio
  previo, no lo detiene. Aun así, revisa qué hay en los puertos antes de ejecutar.
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
- **Olla**: <https://github.com/thushan/olla> (Apache 2.0)
- **SOLLOL**: <https://github.com/BenevolentJoker-JohnL/SOLLOL> (MIT, PyPI `sollol`)
- **Proof**: <https://github.com/altorlab/proof-ai> (MIT, npm `proof-ai`)
- **Promptfoo**: <https://github.com/promptfoo/promptfoo> (MIT)
- **dsh-agent-gate**: <https://github.com/DSH-Raising-Plan/dsh-agent-gate> (AGPL, plugin comunitario para DeepSeek Harness, no oficial)

---

## Herramientas gratuitas/Open-Source — Resumen rápido

```bash
# Proxy multi-backend (Apache 2.0)
go install github.com/thushan/olla@latest
# o: docker run -p 40114:40114 ghcr.io/thushan/olla:latest

# Orquestación de clusters Ollama (MIT, Python)
pip install sollol

# Verificación de código generado (MIT, Node; Docker opcional)
npm install -g proof-ai

# Framework de evaluación de prompts (MIT, Node)
npm install -g promptfoo

# Gate de DeepSeek Harness (AGPL, plugin Node/TS; NO es un servicio HTTP)
dsh plugin --profile web add github:DSH-Raising-Plan/dsh-agent-gate#plugin/dsh

# llama.cpp con OpenBLAS (acelera prefill, no generación)
make LLAMA_OPENBLAS=1
# -t <núcleos físicos> (por defecto ya autodetecta) -ngl 999
```

> **Alcance**: Olla, SOLLOL, Proof, Promptfoo y dsh-agent-gate son gratuitos y
> autoalojables, pero **no todos están integrados** en thinker (ver tabla). El
> modelo `:free` de OpenRouter es un servicio en la nube: gratuito con cuota,
> no privado y no ilimitado.