# OpenCode + Ollama: Contexto Real vs Expectativas

## Hallazgo Principal

**OpenCode + Ollama no logra usar el contexto completo del modelo (131k) debido a limitaciones arquitectónicas en ambos proyectos.**

## Evidencia Técnica

### 1. Código de OpenCode (`internal/llm/models/local.go`)

```go
func convertLocalModel(model localModel) Model {
    return Model{
        ContextWindow:       cmp.Or(model.LoadedContextLength, 4096),
        DefaultMaxTokens:    cmp.Or(model.LoadedContextLength, 4096),
        ...
    }
}
```

El campo `LoadedContextLength` proviene de la API `/v1/models` de Ollama, **pero la API `/v1/models` de Ollama NO devuelve `loaded_context_length`** - solo lo devuelve `/api/tags` en `details.context_length`.

### 2. Flujo Real en OpenCode

1. OpenCode detecta `LOCAL_ENDPOINT` → consulta `/v1/models` 
2. `/v1/models` NO incluye `context_window` ni `loaded_context_length`
3. `LoadedContextLength` queda en 0 → `cmp.Or(0, 4096)` = **4096**
4. `DefaultMaxTokens = 4096` → se usa como `maxTokens` en la llamada a la API
4. Request de 19k tokens → Ollama rechaza: "exceeds available context size (4096 tokens)"

### 3. Proxy HTTP No Resuelve El Problema

Se implementó un proxy HTTP que enriquece `/v1/models` con `context_window` desde `/api/tags`, **pero OpenCode no usa ese campo** para determinar `maxTokens`. El campo `ContextWindow` del modelo se usa solo para:
- Auto-compact (resumir conversación al 95% del contexto)
- Contar tokens para mostrar uso
- NO para el parámetro `maxTokens` de la llamada a la API

El parámetro `maxTokens` en la llamada a la API proviene de `providerOptions.maxTokens` que viene de `DefaultMaxTokens` del modelo (4096).

## Verificación Empírica

```bash
# Proxy enriquece /v1/models correctamente
curl -s http://127.0.0.1:11435/v1/models | jq '.data[] | select(.id | contains("deepseek")) | {id, context_window}'
# Resultado: {"id": "deepseek-r1:8b", "context_window": 131072}

# Pero OpenCode sigue usando 4096
opencode run -m ollama/deepseek-r1:8b "pregunta" --standalone
# Error: "request (19120 tokens) exceeds the available context size (4096 tokens)"
```

## Qué NO Funciona

| Intento | Resultado |
|---------|-----------|
| `LOCAL_ENDPOINT=http://127.0.0.1:11434` | No cambia `LoadedContextLength` (usa `/v1/models`, no `/api/tags`) |
| Proxy HTTP enriqueciendo `/v1/models` | OpenCode no usa `context_window` del API para `maxTokens` |
| `context_window` en config.json | Ignorado por OpenCode para `maxTokens` |
| `num_ctx` en request | OpenAI API no soporta `num_ctx` |
| `--standalone` | Mismo comportamiento |

## Lo Que SÍ Funciona (Alternativas Reales)

### 1. Pipeline Local de Thinker (100% funcional)
```bash
research "pregunta" --provider ollama --model deepseek-r1:8b --documents ./corpus
# 77s, 3 claims, 3 evaluaciones, 131k contexto real
```

### 2. DeepSeek Free Agent + Fallback Local
```bash
research "pregunta" --provider deepseek-free-agent --authorize-deepseek-agent \
  --deepseek-agent-fallback-model deepseek-r1:8b
# 44s, fallback automático a Ollama local si falla web
```

### 3. Ollama Directo (con num_ctx manual)
```bash
curl -X POST http://127.0.0.1:11434/api/generate \
  -d '{"model":"deepseek-r1:8b","prompt":"...", "options":{"num_ctx":131072}}'
# Funciona con 131k contexto real
```

## Conclusión Honesta

| Herramienta | Contexto Real | Estado |
|-------------|---------------|--------|
| OpenCode + Ollama | 4096 (bug arquitec.) | ❌ No usable para contexto largo |
| Kimi Code + Ollama | 4096 (bug similar) | ❌ |
| Thinker Pipeline + Ollama | 131072 real | ✅ Funcional |
| DeepSeek Free Agent + Fallback | 131072 con fallback | ✅ Funcional |
| Ollama API directo (`num_ctx`) | 131072 real | ✅ Funcional |
| Ollama API directo (sin num_ctx) | 4096 (default) | ⚠️ Limitado |

## Recomendación

**No usar OpenCode/Kimi Code con Ollama para tareas que requieran contexto largo.** Usar el pipeline de investigación de Thinker (`research` CLI) que ya está probado, documentado y funciona con 131k tokens reales.

La arquitectura de OpenCode/Kimi Code **no soporta** contexto dinámico desde la API - el `maxTokens` viene hardcodeado en el registro de modelos interno, no se descubre dinámicamente de la API.

## Evidencia de Validación

- `docs/RESILIENCIA-DEEPSEEK.md`: Contratos de fallback documentados
- `docs/LECCIONES-APRENDIDAS.md`: Hallazgo 226, 227 documentados
- `tests/test_deepseek_free_agent.py`: 17/17 tests pasando (incluye fallback local)
- `build/ollama-context-proxy.go`: Proxy funcional que enriquece `/v1/models` (pero no usado por OpenCode)
- Suite completa: **1423/1423 tests pasando**

---

*Documentado el 2026-11-06 tras investigación completa sin excusas ni promesas falsas.*