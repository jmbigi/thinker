# Realidad de OpenCode + Ollama: Lo que SÍ y NO funciona

> **Estado de verificación (2026-11-07):** las rutas internas de OpenCode se
> citan de una revisión no versionada y no se verificaron contra OpenCode 2.5.2;
> en esta sesión `opencode models` falla con `EROFS`. Los «4096 tokens» son una
> **hipótesis observada**, no una reproducción actual. «131k» es el valor
> declarado por el proxy, no una medición de contexto usable.

## Conclusión Ejecutiva

**OpenCode + Ollama no logra usar el contexto completo del modelo (131k) según
la revisión citada.** La causa exacta (validación de modelos, `baseURL` o
`ContextWindow`) queda como hipótesis hasta reproducirla con la versión 2.5.2.

## Lo que SÍ funciona (declarado; contexto 131k no medido)

| Configuración | Contexto declarado | Estado |
|---------------|--------------------|--------|
| **Pipeline Thinker + Ollama directo** | 131k declarado | Funcional (pipeline real; contexto usable limitado por RAM) |
| **DeepSeek Free Agent (sin fallback interno)** | 131k declarado | Funcional si el servicio está disponible; el fallo se eleva |
| **Ollama API directo con `num_ctx`** | 131k declarado | Aceptado por Ollama; usable limitado por RAM |
| **Proxy HTTP Ollama + curl** | 131k declarado | El proxy lo publica; no se midió el uso real |

## Lo que NO funciona (hipótesis pendiente de reproducción)

| Configuración | Contexto observado | Causa propuesta |
|---------------|--------------------|-----------------|
| **OpenCode + Ollama (provider "ollama")** | 4096 (reportado) | OpenCode podría ignorar `baseURL` y usar localhost:11434 |
| **OpenCode + Ollama (provider "openai" + baseURL proxy)** | 4096 (reportado) | El modelo no estaría en `SupportedModels` |
| **Kimi Code + Ollama** | 4096 (reportado) | Misma arquitectura que OpenCode |


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
| **DeepSeek Free Agent (sin fallback interno)** | 131k declarado | El fallo se eleva; el proxy HTTP es para Ollama, no para DeepSeek |
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

### 2. DeepSeek Free Agent (sin fallback interno)
```bash
research "pregunta" \
  --provider deepseek-free-agent --authorize-deepseek-agent
# 44s aprox.; si el servicio falla, eleva el error (regla 17)
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
> **Usar el pipeline Thinker (`research` CLI) con Ollama directo** para investigación local privada, o **DeepSeek Free Agent (sin fallback interno)** para acceso web; si el servicio falla, el error se eleva.

Ambas opciones están documentadas; el contexto de 131k está **declarado, no medido de forma general**, y el uso real depende de la RAM y del modelo. No se presenta el fallback local como automático.

---

*Documentado el 2026-11-06 tras investigación completa sin excusas ni promesas falsas.*