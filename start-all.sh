#!/bin/bash
# start-all.sh - Levanta toda la infraestructura IA local
# Uso: ./start-all.sh

set -euo pipefail

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_ok() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Configuración
RESEARCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${RESEARCH_DIR}/build"
OLLAMA_HOST="127.0.0.1"
OLLAMA_PORT=11434
PROXY_PORT=11435
LLAMA_PORT=11436

# PIDs para cleanup
OLLAMA_PID=""
PROXY_PID=""
LLAMA_PID=""

cleanup() {
    log_info "Deteniendo solo los servicios iniciados por este script..."
    for pid in "${OLLAMA_PID}" "${PROXY_PID}" "${LLAMA_PID}"; do
        if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
            kill "${pid}" 2>/dev/null || true
            wait "${pid}" 2>/dev/null || true
        fi
    done
    # Si Ollama ya estaba corriendo, OLLAMA_PID está vacío y no se toca.
    log_ok "Limpieza completada"
}

trap cleanup EXIT INT TERM

log_info "🚀 Iniciando infraestructura IA local completa..."

if ! command -v jq >/dev/null 2>&1; then
    log_error "jq no está instalado; es necesario para leer el estado de Ollama."
    exit 1
fi

# 1. Verificar Ollama
log_info "Verificando Ollama..."
if ! curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    if ! command -v ollama >/dev/null 2>&1; then
        log_error "Ollama no está instalado; instálalo o inicia el servicio."
        exit 1
    fi
    log_info "Iniciando Ollama daemon..."
    ollama serve &
    OLLAMA_PID=$!
    sleep 3
    if ! curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
        log_error "Ollama no respondió. Verifica instalación."
        exit 1
    fi
fi
log_ok "Ollama activo en puerto 11434"

# Verificar modelos
log_info "Modelos disponibles:"
curl -sf http://127.0.0.1:11434/api/tags | jq -r '.models[] | "  - \(.name) (\(.details.parameter_size // "N/A"), \(.details.quantization_level // "N/A"), ctx: \(.details.context_length // "N/A"))"'

# 2. Iniciar Proxy de Contexto (puerto 11435)
if curl -sf http://127.0.0.1:11435/v1/models >/dev/null 2>&1; then
    log_ok "Proxy contexto ya activo en 11435; se reutiliza y no se detendrá"
else
    log_info "Iniciando Proxy de Contexto Ollama (puerto 11435)..."
    cd "${BUILD_DIR}"
    OLLAMA_TARGET=http://127.0.0.1:11434 ./ollama-context-proxy &
    PROXY_PID=$!
    sleep 2

    if curl -sf http://127.0.0.1:11435/v1/models >/dev/null 2>&1; then
        log_ok "Proxy contexto activo en puerto 11435"
        curl -sf http://127.0.0.1:11435/v1/models | jq '.data[] | select(.id | contains("deepseek")) | {id, context_window}'
    else
        log_error "Proxy contexto no responde"
        exit 1
    fi
fi

# 3. Iniciar llama.cpp server (puerto 11436)
if curl -sf http://127.0.0.1:11436/health >/dev/null 2>&1; then
    log_ok "llama.cpp ya activo en 11436; se reutiliza y no se detendrá"
else
    log_info "Iniciando llama.cpp server (puerto 11436)..."
    cd "${BUILD_DIR}"

    # Optimizaciones llama.cpp (comentadas; ajustar a tu hardware):
    # export LLAMA_OPENBLAS=1    # Acelera PREFIll (prompts largos); impacto en generación token-a-token limitado/nulo
    # export LLAMA_N_THREADS=    # Por defecto llama.cpp ya usa núcleos físicos; solo forzar si necesario
    # export LLAMA_N_GPU_LAYERS=999  # Offload all layers to GPU; bajar de 5 en 5 si OOM

    python3 llama-cpp-server.py &
    LLAMA_PID=$!
    sleep 3

    if curl -sf http://127.0.0.1:11436/health >/dev/null 2>&1; then
        log_ok "llama.cpp server activo en puerto 11436"
    else
        log_warn "llama.cpp server no responde (opcional)"
    fi
fi

# 3. Verificar Ollama models
log_info "Modelos disponibles en Ollama:"
curl -sf http://127.0.0.1:11434/api/tags | jq -r '.models[] | "  - \(.name) (\(.details.parameter_size // "N/A"), \(.details.quantization_level // "N/A"), ctx: \(.details.context_length // "N/A"))"'

# 3. Verificar Proxy Contexto
log_info "Verificando Proxy Contexto (puerto 11435):"
if curl -sf http://127.0.0.1:11435/v1/models >/dev/null 2>&1; then
    log_ok "Proxy contexto activo"
    curl -sf http://127.0.0.1:11435/v1/models | jq '.data[] | select(.id | contains("deepseek")) | {id, context_window}'
else
    log_error "Proxy contexto no responde"
    exit 1
fi

# Verificar llama.cpp server
if curl -sf http://127.0.0.1:11436/health >/dev/null 2>&1; then
    log_ok "llama.cpp server activo en puerto 11436"
else
    log_warn "llama.cpp server no responde (opcional)"
fi

# Resumen final
echo ""
echo -e "${GREEN}════════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ INFRAESTRUCTURA IA LOCAL COMPLETA${NC}"
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}Servicios activos:${NC}"
echo "  🟢 Ollama:           http://127.0.0.1:11434"
echo "  🟢 Proxy Contexto:   http://127.0.0.1:11435  (inyecta num_ctx=131072)"
echo "  🟢 llama.cpp server: http://127.0.0.1:11436  (OpenAI-compatible)"
echo ""
echo -e "${BLUE}Modelos disponibles:${NC}"
curl -sf http://127.0.0.1:11434/api/tags | jq -r '.models[] | "  - \(.name) (\(.details.parameter_size // "N/A"), \(.details.quantization_level // "N/A"), ctx: \(.details.context_length // "N/A"))"'
echo ""
echo -e "${BLUE}Configuración OpenCode:${NC}"
echo '  model: "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"'
echo '  (alternativa local: ollama/deepseek-r1:8b en 11435)'
echo ""
echo -e "${BLUE}Configuración Kimi Code:${NC}"
echo '  default_model = "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"'
echo '  (alternativa local: ollama/deepseek-r1:8b vía 11435)'
echo ""
echo -e "${YELLOW}Para detener: Ctrl+C (limpieza automática)${NC}"
echo -e "${GREEN}¡Infraestructura lista! OpenCode/Kimi usan el modelo gratuito; Ollama queda para uso local/offline.${NC}"

# Mantener vivo
wait