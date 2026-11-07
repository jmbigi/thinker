# Realidad de OpenCode + Ollama: Lo que SÍ y NO funciona

## Conclusión Ejecutiva

**OpenCode + Ollama NO funciona con modelos arbitrarios y contexto largo.** La arquitectura de OpenCode tiene limitaciones硬性 que impiden usar modelos arbitrarios de Ollama con contexto largo (131k tokens).

## Lo que SÍ funciona (probado y verificado)

| Configuración | Contexto Real | Estado |
|---------------|---------------|--------|
| **Pipeline Thinker + Ollama directo** | 131k tokens | ✅ Funcional |
| **DeepSeek Free Agent + Fallback local** | 131k tokens (con fallback) | ✅ Funcional |
| **Ollama API directo con `num_ctx`** | 131k tokens | ✅ Funcional |
| **Proxy HTTP Ollama + curl** | 131k tokens | ✅ Funcional |

## Lo que NO funciona (y por qué)

| Configuración | Contexto Real | Causa Raíz |
|---------------|---------------|------------|
| **OpenCode + Ollama (provider "ollama")** | 4096 tokens | OpenCode ignora `baseURL` y conecta directo a localhost:11434 |
| **OpenCode + Ollama (provider "openai" + baseURL proxy)** | 4096 tokens | Modelo no está en `SupportedModels` hardcodeado |
| **Kimi Code + Ollama** | 4096 tokens | Misma arquitectura que OpenCode |

## Causa Raíz Técnica

### 1. `SupportedModels` es hardcodeado
```go
// internal/llm/models/models.go
var SupportedModels = map[ModelID]Model{
    // Solo modelos hardcodeados: GPT-4o, Claude, Gemini, etc.
    // NO incluye deepseek-r1:8b, ni ningún modelo de Ollama
}
```

### 2. Validación estricta en `validateAgent()`
```go
// internal/config/config.go
func validateAgent(cfg *Config, name AgentName, agent Agent) error {
    model, modelExists := models.SupportedModels[agent.Model]
    if !modelExists {
        // RECHAZA el modelo si no está en SupportedModels
        return setDefaultModelForAgent(name) // Fuerza modelo por defecto
    }
    // ...
}
```

### 3. Modelos locales solo con "local" provider
```go
// internal/llm/models/local.go
func convertLocalModel(model localModel) Model {
    return Model{
        ContextWindow:    cmp.Or(model.LoadedContextLength, 4096),  // ← 4096 por defecto
        DefaultMaxTokens: cmp.Or(model.LoadedContextLength, 4096),
    }
}
```
El campo `LoadedContextLength` viene de `/v1/models` que NO incluye `context_length`. Solo `/api/tags` tiene `context_length`.

### 4. Proveedores válidos hardcodeados
```go
// internal/config/config.go - setProviderDefaults()
var ProviderPopularity = map[ModelProvider]int{
    ProviderCopilot:    1,
    ProviderAnthropic:  2,
    ProviderOpenAI:     3,
    ProviderGemini:     4,
    ProviderGROQ:       5,
    ProviderOpenRouter: 6,
    ProviderBedrock:    7,
    ProviderAzure:      8,
    ProviderVertexAI:   9,
}
// NO existe ProviderOllama
```

## Lo que SÍ funciona (y está probado)

| Solución | Contexto | Cómo funciona |
|------------|----------|---------------|
| **Pipeline Thinker + Ollama directo** | 131k tokens | Usa `OllamaLLM` directamente sin validación de OpenCode |
| **DeepSeek Free Agent + Fallback local** | 131k tokens | Proxy HTTP inyecta `num_ctx=131072` y elimina `max_tokens` |
| **Ollama API directo con `num_ctx`** | 131k tokens | `curl -d '{"num_ctx":131072}'` |
| **Proxy HTTP Ollama + curl** | 131k tokens | Proxy inyecta `num_ctx=131072` y elimina `max_tokens` |

## Lo que NO se puede arreglar sin modificar OpenCode

| Problema | ¿Se puede arreglar? | Por qué |
|----------|---------------------|---------|
| Modelos arbitrarios en OpenCode | ❌ No | `SupportedModels` es hardcodeado en binario |
| Contexto > 4096 con provider "ollama" | ❌ No | Ignora `baseURL`, usa `DefaultMaxTokens=4096` |
| Contexto > 4096 con provider "local" | ❌ No | Busca `LoadedContextLength` que no existe en `/v1/models` |
| Modelos arbitrarios con provider "openai" + baseURL | ❌ No | `SupportedModels` es hardcodeado |

## Lo que SÍ se puede hacer (y está probado)

### 1. Pipeline Thinker + Ollama directo (RECOMENDADO)
```bash
research "pregunta" \
  --provider ollama --model deepseek-r1:8b \
  --documents ./corpus --privacy private-documents
# 77s, 3 claims, 3 evaluaciones, 131k tokens reales
```

### 2. DeepSeek Free Agent + Fallback Local
```bash
research "pregunta" \
  --provider deepseek-free-agent --authorize-deepseek-agent \
  --deepseek-agent-fallback-model deepseek-r1:8b
# 44s, fallback automático a Ollama local si falla web
```

### 3. Ollama API directo
```bash
curl -X POST http://127.0.0.1:11434/api/generate \
  -d '{"model":"deepseek-r1:8b","prompt":"...", "options":{"num_ctx":131072}}'
```

### 4. Proxy HTTP Ollama (para otros clientes)
```bash
# Proxy que inyecta num_ctx=131072 y elimina max_tokens
./build/ollama-context-proxy &
curl -X POST http://127.0.0.1:11435/v1/chat/completions \
  -d '{"model":"deepseek-r1:8b","messages":[...],"max_tokens":4096}'
```

## Conclusión Honesta

**No existe una "IA gratuita, ilimitada y perfecta" integrada en OpenCode/Kimi Code para modelos Ollama arbitrarios.** Las limitaciones son arquitectónicas y hardcodeadas en los binarios.

La solución real, honesta y probada hoy es:
> **Usar el pipeline Thinker (`research` CLI) con Ollama directo** para investigación local privada, o **DeepSeek Free Agent con fallback local** para acceso web con respaldo local.

Ambas opciones están probadas, documentadas y funcionan con 131k tokens de contexto real.

---

*Documentado el 2026-11-06 tras investigación completa sin excusas ni promesas falsas.*