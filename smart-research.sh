#!/bin/bash
# smart-research.sh - Investigación con fallback automático inteligente
# Uso: ./smart-research.sh "tu pregunta de investigación"

set -e

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_ok() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Configuración
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESEARCH_DIR="${SCRIPT_DIR}"
PROXY_URL="http://127.0.0.1:11435"
OLLAMA_URL="http://127.0.0.1:11434"
MODEL="deepseek-r1:8b"
MAX_RETRIES=3
RETRY_DELAY=5

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_ok() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Verificar/Iniciar Ollama
ensure_ollama() {
    if curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
        return 0
    fi
    
    log_warn "Ollama no responde, iniciando..."
    ollama serve &
    OLLAMA_PID=$!
    sleep 3
    
    if curl -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
        log_ok "Ollama iniciado"
        return 0
    else
        log_error "No se pudo iniciar Ollama"
        return 1
    fi
}

# Verificar/Iniciar proxy
ensure_proxy() {
    if curl -sf http://127.0.0.1:11435/v1/models >/dev/null 2>&1; then
        return 0
    fi
    
    log_warn "Proxy no responde, reiniciando..."
    pkill -f "ollama-context-proxy" 2>/dev/null || true
    sleep 1
    
    cd "${RESEARCH_DIR}/build"
    OLLAMA_TARGET=http://127.0.0.1:11434 ./ollama-context-proxy &
    PROXY_PID=$!
    sleep 2
    
    if curl -sf http://127.0.0.1:11435/v1/models >/dev/null 2>&1; then
        log_ok "Proxy reiniciado"
        return 0
    else
        log_error "No se pudo iniciar proxy"
        return 1
    fi
}

# Estrategia 1: Proxy local + Ollama (mejor: 131k ctx, privado, gratis)
try_local_proxy() {
    local query="$1"
    log_info "🔬 Estrategia 1: Proxy local + Ollama (131k ctx, privado, gratis)"
    
    ensure_ollama || return 1
    ensure_proxy || return 1
    
    log_info "Ejecutando investigación vía proxy local..."
    
    cd "${RESEARCH_DIR}"
    timeout 300 research "$QUERY" \
        --provider ollama \
        --model deepseek-r1:8b \
        --search local \
        --documents "${RESEARCH_DIR}/build/deepseek-free-agent-runtime/workspace" \
        --privacy private-documents \
        --max-iterations 2 \
        --max-llm-calls 10 \
        --format json 2>&1 | tee /tmp/research-local.log
    
    return ${PIPESTATUS[0]}
}

# Estrategia 2: DeepSeek Free Agent con fallback local
try_deepseek_free_agent() {
    local query="$1"
    log_info "🔄 Estrategia 2: DeepSeek Free Agent + Fallback local"
    
    ensure_ollama || return 1
    
    log_info "Ejecutando DeepSeek Free Agent con fallback local..."
    
    cd "${RESEARCH_DIR}"
    timeout 300 research "$QUERY" \
        --provider deepseek-free-agent \
        --authorize-deepseek-agent \
        --deepseek-agent-fallback-model deepseek-r1:8b \
        --search wikipedia \
        --max-iterations 2 \
        --max-llm-calls 8 \
        --format json 2>&1 | tee /tmp/research-deepseek.log
    
    return ${PIPESTATUS[0]}
}

# Estrategia 3: Ollama directo (sin proxy)
try_ollama_direct() {
    local query="$1"
    log_info "🔄 Estrategia 3: Ollama directo (sin proxy)"
    
    ensure_ollama || return 1
    
    log_info "Ejecutando con Ollama directo..."
    
    cd "${RESEARCH_DIR}"
    timeout 300 research "$QUERY" \
        --provider ollama \
        --model deepseek-r1:8b \
        --search local \
        --documents "${RESEARCH_DIR}/build/deepseek-free-agent-runtime/workspace" \
        --privacy private-documents \
        --max-iterations 2 \
        --max-llm-calls 10 \
        --format json 2>&1 | tee /tmp/research-direct.log
    
    return ${PIPESTATUS[0]}
}

# Estrategia 4: DeepSeek Free Agent solo web
try_deepseek_web() {
    local query="$1"
    log_info "🔄 Estrategia 4: DeepSeek Free Agent (web)"
    
    log_info "Ejecutando DeepSeek Free Agent (web)..."
    
    cd "${RESEARCH_DIR}"
    timeout 300 research "$QUERY" \
        --provider deepseek-free-agent \
        --authorize-deepseek-agent \
        --search wikipedia \
        --max-iterations 2 \
        --max-llm-calls 8 \
        --format json 2>&1 | tee /tmp/research-web.log
    
    return ${PIPESTATUS[0]}
}

# Función principal
main() {
    QUERY="${1:-}"
    if [ -z "$QUERY" ]; then
        echo "Uso: $0 \"tu pregunta de investigación\""
        echo "Ejemplo: $0 \"¿Qué es la fotosíntesis y qué papel tiene la clorofila?\""
        exit 1
    fi
    
    QUERY="$1"
    shift
    EXTRA_ARGS="$@"
    
    echo -e "\n🧠 \033[1;34mSMART RESEARCH\033[0m - Investigación inteligente con fallback automático"
    echo "================================================================"
    echo -e "Pregunta: \033[1;33m$QUERY\033[0m"
    echo ""
    
    # Verificar prerrequisitos básicos
    if ! command -v research &> /dev/null; then
        echo -e "\033[0;31m[ERROR]\033[0m 'research' no encontrado en PATH"
        exit 1
    fi
    
    if ! command -v ollama &> /dev/null; then
        echo -e "\033[0;31m[ERROR]\033[0m Ollama no instalado"
        exit 1
    fi
    
    # Estrategias en orden de preferencia
    STRATEGIES=(
        "try_local_proxy:Proxy local + Ollama (131k ctx, privado, gratis)"
        "try_deepseek_free_agent:DeepSeek Free Agent + Fallback local"
        "try_ollama_direct:Ollama directo (sin proxy)"
        "try_deepseek_web:DeepSeek Free Agent (solo web)"
    )
    
    for strategy in "${STRATEGIES[@]}"; do
        IFS=':' read -r func desc <<< "$strategy"
        
        echo -e "\n\033[1;34m🔄 ESTRATEGIA: $desc\033[0m"
        log_info "Ejecutando: $func"
        
        if $func "$QUERY"; then
            echo -e "\n\033[0;32m✅ EXITO\033[0m - Estrategia '$desc' completada exitosamente"
            exit 0
        else
            log_warn "Estrategia '$desc' falló, probando siguiente..."
            sleep 3
        fi
    done
    
    echo -e "\n\033[0;31m❌ TODAS LAS ESTRATEGIAS FALLARON\033[0m"
    echo "Revisa logs en /tmp/research-*.log"
    exit 1
}

# Verificar prerrequisitos
if ! command -v research &> /dev/null; then
    echo -e "\033[0;31m[ERROR]\033[0m 'research' no encontrado en PATH"
    exit 1
fi

if ! command -v ollama &> /dev/null; then
    echo -e "\033[0;31m[ERROR]\033[0m Ollama no instalado"
    exit 1
fi

# Verificar modelo
if ! ollama list | grep -q "deepseek-r1:8b"; then
    echo -e "\033[1;33m[WARN]\033[0m Modelo deepseek-r1:8b no encontrado"
    echo "Instalando: ollama pull deepseek-r1:8b"
    ollama pull deepseek-r1:8b
fi

# Ejecutar
main "$@"