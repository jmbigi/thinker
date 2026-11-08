#!/bin/bash
# smart-research.sh - Investigación con fallback automático inteligente
# Uso: ./smart-research.sh "tu pregunta de investigación"
# DeepSeek (externo) es opt-in: SMART_ALLOW_DEEPSEEK=1 ./smart-research.sh "..."

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
RESEARCH_CLI="${RESEARCH_DIR}/research_cli.py"
PROXY_URL="http://127.0.0.1:11435"
OLLAMA_URL="http://127.0.0.1:11434"
MODEL="deepseek-r1:8b"
# DeepSeek reenvía prompts a un servicio externo: solo opt-in explícito.
ALLOW_DEEPSEEK="${SMART_ALLOW_DEEPSEEK:-0}"

# Solo se detienen los procesos que inició este script; si Ollama ya estaba
# corriendo, su PID queda vacío y no se toca.
OLLAMA_PID=""
PROXY_PID=""
cleanup() {
    for pid in "${OLLAMA_PID:-}" "${PROXY_PID:-}"; do
        if [ -n "${pid}" ] && kill -0 "${pid}" 2>/dev/null; then
            kill "${pid}" 2>/dev/null || true
            wait "${pid}" 2>/dev/null || true
        fi
    done
}
trap cleanup EXIT INT TERM

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
    
    log_warn "Proxy no responde, iniciando..."
    cd "${RESEARCH_DIR}/build"
    if [ ! -x ./ollama-context-proxy ]; then
        log_error "No existe build/ollama-context-proxy; compílalo o usa la estrategia Ollama directo."
        return 1
    fi
    OLLAMA_TARGET=http://127.0.0.1:11434 ./ollama-context-proxy &
    PROXY_PID=$!
    sleep 2

    if curl -sf http://127.0.0.1:11435/v1/models >/dev/null 2>&1; then
        log_ok "Proxy iniciado"
        return 0
    else
        log_error "No se pudo iniciar el proxy (¿puerto 11435 ocupado?). No se mata ningún proceso ajeno."
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
    timeout 300 python3 "${RESEARCH_CLI}" "$query" \
        --provider ollama \
        --model "${MODEL}" \
        --ollama-base-url "${PROXY_URL}" \
        --ollama-api openai \
        --search local \
        --documents "${RESEARCH_DIR}/build/deepseek-free-agent-runtime/workspace" \
        --privacy private-documents \
        --max-iterations 2 \
        --max-llm-calls 10 \
        --format json 2>&1 | tee /tmp/research-local.log
    
    return ${PIPESTATUS[0]}
}

# Estrategia 2: DeepSeek Free Agent (sin fallback interno: el fallo se eleva)
try_deepseek_free_agent() {
    local query="$1"
    log_info "🔄 Estrategia 2: DeepSeek Free Agent (sin fallback interno)"
    
    log_info "Ejecutando DeepSeek Free Agent..."
    
    cd "${RESEARCH_DIR}"
    timeout 300 python3 "${RESEARCH_CLI}" "$query" \
        --provider deepseek-free-agent \
        --authorize-deepseek-agent \
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
    timeout 300 python3 "${RESEARCH_CLI}" "$query" \
        --provider ollama \
        --model "${MODEL}" \
        --ollama-base-url "${OLLAMA_URL}" \
        --ollama-api native \
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
    timeout 300 python3 "${RESEARCH_CLI}" "$query" \
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
        echo "DeepSeek opt-in: SMART_ALLOW_DEEPSEEK=1 $0 \"...\""
        exit 1
    fi
    
    QUERY="$1"
    shift

    echo -e "\n🧠 \033[1;34mSMART RESEARCH\033[0m - Investigación inteligente con fallback automático"
    echo "================================================================"
    echo -e "Pregunta: \033[1;33m$QUERY\033[0m"
    echo ""

    # Verificar prerrequisitos básicos
    if [ ! -f "${RESEARCH_CLI}" ]; then
        echo -e "\033[0;31m[ERROR]\033[0m research_cli.py no encontrado en ${RESEARCH_CLI}"
        exit 1
    fi

    if ! command -v python3 &> /dev/null; then
        echo -e "\033[0;31m[ERROR]\033[0m python3 no encontrado en PATH"
        exit 1
    fi

    if ! command -v ollama &> /dev/null; then
        echo -e "\033[0;31m[ERROR]\033[0m Ollama no instalado"
        exit 1
    fi

    # Estrategias en orden de preferencia. Las locales primero; DeepSeek solo
    # con autorización explícita porque reenvía prompts a un servicio externo.
    STRATEGIES=(
        "try_local_proxy:Proxy local + Ollama (131k ctx, privado, gratis)"
        "try_ollama_direct:Ollama directo (sin proxy)"
    )
    if [ "$ALLOW_DEEPSEEK" = "1" ]; then
        log_warn "DeepSeek habilitado (SMART_ALLOW_DEEPSEEK=1): egreso a servicio externo"
        STRATEGIES+=(
            "try_deepseek_free_agent:DeepSeek Free Agent (sin fallback interno)"
            "try_deepseek_web:DeepSeek Free Agent (solo web)"
        )
    else
        log_info "DeepSeek omitido; para autorizarlo: SMART_ALLOW_DEEPSEEK=1 $0 ..."
    fi
    
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
if [ ! -f "${RESEARCH_CLI}" ]; then
    echo -e "\033[0;31m[ERROR]\033[0m research_cli.py no encontrado en ${RESEARCH_CLI}"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo -e "\033[0;31m[ERROR]\033[0m python3 no encontrado en PATH"
    exit 1
fi

if ! command -v ollama &> /dev/null; then
    echo -e "\033[0;31m[ERROR]\033[0m Ollama no instalado"
    exit 1
fi

# Verificar modelo
if ! ollama list | grep -qF "${MODEL} "; then
    echo -e "\033[1;33m[WARN]\033[0m Modelo ${MODEL} no encontrado"
    echo "Instalando: ollama pull ${MODEL}"
    ollama pull "${MODEL}"
fi

# Ejecutar
main "$@"