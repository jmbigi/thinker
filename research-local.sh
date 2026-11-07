#!/bin/bash
# research-local.sh - Investigación 100% local, privada, 131k ctx
# Uso: ./research-local.sh "tu pregunta de investigación"

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
PROXY_URL_ALT="http://127.0.0.1:11434"
MODEL="deepseek-r1:8b"
CORPUS_DIR="${RESEARCH_DIR}/build/deepseek-free-agent-runtime/workspace"

# Verificar argumentos
if [ $# -eq 0 ]; then
    echo "Uso: $0 \"tu pregunta de investigación\""
    echo "Ejemplo: $0 \"¿Qué es la fotosíntesis y qué papel tiene la clorofila?\""
    exit 1
fi

QUERY="$1"
shift
EXTRA_ARGS="$@"

log_info "🔬 Iniciando investigación local: $QUERY"

# Verificar/Iniciar proxy
ensure_proxy() {
    if curl -sf http://127.0.0.1:11435/v1/models >/dev/null 2>&1; then
        log_ok "Proxy contexto activo"
        return 0
    fi
    
    log_warn "Proxy no responde, iniciando..."
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

# Función principal de investigación
run_research() {
    local query="$1"
    shift
    local extra_args="$@"
    
    log_info "🔬 Iniciando investigación: $QUERY"
    
    # Verificar prerrequisitos
    ensure_ollama || return 1
    ensure_proxy || return 1
    
    # Verificar corpus
    if [ ! -d "$CORPUS_DIR" ]; then
        log_warn "Directorio corpus no existe: $CORPUS_DIR"
        log_info "Creando directorio y documento de prueba..."
        mkdir -p "$CORPUS_DIR"
        cat > "$CORPUS_DIR/fotosintesis.txt" <<'EOF'
La fotosíntesis es el proceso mediante el cual las plantas, las algas y algunas bacterias convierten la energía luminosa en energía química. Durante este proceso se utiliza dióxido de carbono y agua, y se liberan oxígeno y compuestos orgánicos. La clorofila participa en la captura de la luz. Esta descripción es material público de prueba y no contiene datos sensibles.
EOF
        log_ok "Documento de prueba creado"
    fi
    
    # Ejecutar investigación
    log_info "🔬 Ejecutando investigación: $QUERY"
    
    cd "${RESEARCH_DIR}"
    
    # Construir argumentos para research
    RESEARCH_ARGS=(
        "$QUERY"
        --provider ollama
        --model deepseek-r1:8b
        --search local
        --documents "${CORPUS_DIR}"
        --privacy private-documents
        --max-iterations 2
        --max-llm-calls 10
        --format json
    )
    
    # Añadir argumentos extra
    if [ $# -gt 1 ]; then
        RESEARCH_ARGS+=("$@")
    fi
    
    log_info "Ejecutando: research ${RESEARCH_ARGS[*]}"
    
    # Ejecutar con timeout
    timeout 300 research "${RESEARCH_ARGS[@]}" 2>&1 | tee /tmp/research-output.log
    
    local exit_code=${PIPESTATUS[0]}
    
    if [ $exit_code -eq 0 ]; then
        log_ok "Investigación completada exitosamente"
        return 0
    elif [ $exit_code -eq 124 ]; then
        log_error "Timeout (300s) excedido"
        return 1
    else
        log_error "Investigación falló (código: $exit_code)"
        return 1
    fi
}

# Main
QUERY="${1:-}"
if [ -z "$QUERY" ]; then
    echo "Uso: $0 \"tu pregunta de investigación\""
    echo "Ejemplo: $0 \"¿Qué es la fotosíntesis y qué papel tiene la clorofila?\""
    exit 1
fi

QUERY="${1}"
shift

log_info "🔬 Iniciando investigación local: $1"

# Verificar prerrequisitos
ensure_ollama || exit 1
ensure_proxy || exit 1

# Ejecutar
run_research "$@"
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "\n${GREEN}✅ Investigación completada exitosamente${NC}"
else
    log_error "Investigación falló (código: $EXIT_CODE)"
fi

exit $EXIT_CODE