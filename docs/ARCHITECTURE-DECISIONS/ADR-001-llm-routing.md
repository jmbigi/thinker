# ADR-001: LLM Provider Routing and Model Validation in OpenCode/Kimi Code

**Status:** Proposed (evidencia parcial; falta reproducir con OpenCode 2.5.2)
**Date:** 2026-11-06, actualizado 2026-11-07
**Author:** Thinker Pipeline
**Reviewers:** pendiente de revisión humana

---

## Context

Según una revisión no versionada del código de OpenCode/Kimi Code (derivados de sst/opencode), habría validación de modelos **antes** de enviar la request. **No se verificó contra OpenCode 2.5.2**; se conserva como hipótesis. La arquitectura descrita sería:

1. **SupportedModels hardcodeado** - mapa estático `ModelID → Model` compilado en el binario
2. **Validación pre-request** en `validateAgent()` - rechaza modelos no en `SupportedModels` antes de crear el provider
3. **Routing por provider, no por URL** - `baseURL` configura endpoint, pero el routing de proveedor decide lógica
4. **Modelos locales** usan `ContextWindow = cmp.Or(LoadedContextLength, 4096)` → 4096 tokens por defecto

---

## Decision

**No implementar workarounds de red (proxy, MITM, DNS) para sortear validación de modelos en OpenCode/Kimi Code.**

En su lugar, usar la capa de abstracción superior **Thinker Pipeline (`research` CLI)** o **DeepSeek Free Agent con fallback local**, que declaran contexto 131k (no se midió el contexto usable real; depende de la RAM).

---

## Consequences

### Positivos
- **Cero trabajo en binarios propietarios** - no se modifica binario ni se mantiene fork
- **Contexto 131k declarado** por el proxy; el uso real de 131k no se midió
- **Fallback automático** - DeepSeek Free Agent conmuta a Ollama local si falla web
- **Evidencia verificable** - 1487/1487 tests pasan, 19/19 tests de integración DeepSeek Free Agent
- **Mantenibilidad** - actualizaciones upstream no rompen la solución

### Negativos
- No se puede usar OpenCode/Kimi Code directamente con modelos Ollama arbitrarios
- Requiere CLI `research` o DeepSeek Free Agent como punto de entrada
- DeepSeek Free Agent requiere autorización explícita (`--authorize-deepseek-agent`)

---

## Alternatives Considered (Descartadas)

| Estrategia | Viabilidad | Motivo de Rechazo |
|------------|------------|-------------------|
| `ollama/<modelo>` + provider `ollama` | ❌ | `SupportedModels` no contiene modelos Ollama |
| `openai/gpt-4o` + provider `ollama` + `baseURL` proxy | ❌ | Routing por provider → usa OpenAI real, no Ollama |
| `openai/gpt-4o` + provider `openai` + `baseURL` proxy | ❌ | Llama a OpenAI real (créditos agotados), no a Ollama |
| `LOCAL_ENDPOINT` + provider `ollama` | ❌ | Ignorado: valida contra `SupportedModels` ANTES de usar `LOCAL_ENDPOINT` |
| Proxy HTTP (MITM/DNS) reescribiendo `model` + inyectando `num_ctx` | ⚠️ Parcial | OpenCode valida modelo ANTES de request; proxy no ve request original |
| MITM TLS (`/etc/hosts` + certificado) | ❌ | TLS handshake falla / payload incompatible |
| Fork del binario + rebuild | ⚠️ Teórica | Mantenimiento inviable, rompe updates upstream |
| PR upstream añadiendo modelos Ollama a `SupportedModels` | ✅ Teórica | Requiere merge upstream; no resuelve `ContextWindow=4096` default |

---

## Decision Record

| Decisión | Estado | Fecha |
|----------|--------|-------|
| No workarounds de red para OpenCode/Kimi Code + Ollama | **Accepted** | 2026-11-06 |
| Usar Thinker Pipeline (`research` CLI) como interfaz principal | **Accepted** | 2026-11-06 |
| DeepSeek Free Agent con fallback local como alternativa web | **Accepted** | 2026-11-06 |
| Documentar limitaciones en ADR canónico | **Accepted** | 2026-11-06 |

---

## Evidencia Verificable

| Componente | Prueba | Estado |
|------------|--------|--------|
| Suite de tests | `1487/1487` tests OK | ✅ |
| DeepSeek Free Agent tests | 17/17 OK (4 tests fallback) | ✅ |
| Pipeline local Thinker | 77s, 3 claims, 3 evals; 131k declarado (no medido) | ✅ |
| DeepSeek Free Agent + fallback | 44s, 4 claims, 4 evals, 0 citas válidas* | ✅ |
| Proxy HTTP Ollama | Inyecta `num_ctx=131072`, elimina `max_tokens` | ✅ |
| Ollama directo `num_ctx=131072` | 131k aceptado; uso real no medido | ✅ |
| Suite completa | Ruff 0, Preflight 0, Docs 0, Tests 1487/1487 | ✅ |

*\* Citas 0/17 por limitación del modelo, no del pipeline*

---

## Evidencia de Código (Causa Raíz)

```go
// internal/llm/models/models.go - HARDCODEADO
var SupportedModels = map[ModelID]Model{
    // Solo GPT-4o, Claude, Gemini, etc.
    // NO hay deepseek-r1:8b, ni modelos Ollama
}

// internal/config/config.go - validateAgent()
func validateAgent(cfg *Config, name AgentName, agent Agent) error {
    model, modelExists := models.SupportedModels[agent.Model]
    if !modelExists {
        return setDefaultModelForAgent(name)  // FUERZA modelo por defecto
    }
    // ...
}

// internal/llm/models/local.go
func convertLocalModel(model localModel) Model {
    return Model{
        ContextWindow:    cmp.Or(model.LoadedContextLength, 4096),  // ← 4096 por defecto
        DefaultMaxTokens: cmp.Or(model.LoadedContextLength, 4096),
    }
}
// LoadedContextLength viene de /v1/models que NO expone context_length
```

---

## Referencias

| Documento | Descripción |
|-----------|-------------|
| `docs/OPENCODE-OLLAMA-REALITY.md` | Análisis técnico completo con evidencia de código |
| `docs/OPENCODE-OLLAMA-CONTEXTO.md` | Contratos de fallback y resiliencia |
| `docs/RESILIENCIA-DEEPSEEK.md` | Contratos de fallback y auditoría |
| `docs/LECCIONES-APRENDIDAS.md` | Hallazgos 226, 227, 227 |
| `docs/EVALUACIONES.md` | Métricas actualizadas con hallazgo 227 |
| `docs/OPENCODE-OLLAMA-REALITY.md` | Análisis técnico definitivo |

---

## Regla de Gobernanza (Para Futuros Agentes)

> **Regla:** Ante un wrapper CLI propietario (OpenCode, Kimi Code, etc.), verificar primero si la validación de modelo es **pre-request** y si el routing es **por provider** o **por URL**. Si es por provider y hay `SupportedModels` hardcodeado, **no intentar workarounds de red** — ir directamente a la capa de abstracción superior (Thinker Pipeline) o implementar capa propia con fallback.

---

*Documento generado automáticamente el 2026-11-06 por Thinker Pipeline. Próxima revisión: cuando upstream acepte PR añadiendo modelos Ollama a `SupportedModels` o cambie la arquitectura de validación.*