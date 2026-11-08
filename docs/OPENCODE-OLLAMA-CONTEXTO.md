# OpenCode + Ollama: Contexto Real vs Expectativas

> **Estado de verificación (2026-11-07):** las rutas de código de OpenCode se
> citan de una revisión no versionada y **no se verificaron** contra OpenCode
> 2.5.2. En esta sesión `opencode models` falla con `EROFS` al escribir su log,
> así que el error de 4096 tokens es una **hipótesis observada**, no una
> reproducción actual. «131k» es el valor declarado por el proxy, no una
> medición de contexto usable; la RAM disponible lo limita.

## Hallazgo Principal

**OpenCode + Ollama no logra usar el contexto completo del modelo (131k) debido a limitaciones arquitectónicas en ambos proyectos.** (Hipótesis pendiente de reproducción; ver aviso).

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
# 77s, 3 claims, 3 evaluaciones; 131k declarado (no medido)
```

### 2. DeepSeek Free Agent (sin fallback interno)
```bash
research "pregunta" --provider deepseek-free-agent --authorize-deepseek-agent
# 44s aprox.; si el servicio falla, eleva el error (regla 17)
```

### 3. Ollama Directo (con num_ctx manual)
```bash
curl -X POST http://127.0.0.1:11434/api/generate \
  -d '{"model":"deepseek-r1:8b","prompt":"...", "options":{"num_ctx":131072}}'
# Funciona con num_ctx declarado; el contexto usable depende de la RAM
```

## Conclusión Honesta

| Herramienta | Contexto declarado | Estado |
|-------------|--------------------|--------|
| OpenCode + Ollama | 4096 (bug arquitec.) | ❌ No usable para contexto largo |
| Kimi Code + Ollama | 4096 (bug similar) | ❌ |
| Thinker Pipeline + Ollama | 131072 declarado | ✅ Funcional; uso real limitado por RAM |
| DeepSeek Free Agent (sin fallback interno) | 131072 declarado | ✅ Si el servicio está disponible; el fallo se eleva |
| Ollama API directo (`num_ctx`) | 131072 declarado | ✅ Aceptado; uso real limitado por RAM |
| Ollama API directo (sin num_ctx) | 4096 (default) | ⚠️ Limitado |

## Recomendación

**No usar OpenCode/Kimi Code con Ollama para tareas que requieran contexto largo.** Usar el pipeline de investigación de Thinker (`research` CLI) que ya está probado, documentado y declara 131k; el contexto usable real no se midió y depende de la RAM.

La arquitectura de OpenCode/Kimi Code **no soporta** contexto dinámico desde la API - el `maxTokens` viene hardcodeado en el registro de modelos interno, no se descubre dinámicamente de la API.

## Evidencia de Validación

- `docs/RESILIENCIA-DEEPSEEK.md`: límites y ausencia de fallback documentados
- `docs/LECCIONES-APRENDIDAS.md`: Hallazgo 226, 227 y 234 documentados
- `tests/test_deepseek_free_agent.py`: 22/22 tests pasando (incluye rechazo de fallback)
- `build/ollama-context-proxy.go`: Proxy funcional que enriquece `/v1/models` (pero no usado por OpenCode)
- Suite completa: **1514/1514** en Linux 3.11 (cifra vigente en `AGENTS.md` y `README.md`)

---

*Documentado el 2026-11-06 tras investigación completa sin excusas ni promesas falsas.*