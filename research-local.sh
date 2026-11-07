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
RESEARCH_CLI="${RESEARCH_DIR}/research_cli.py"
PROXY_URL="http://127.0.0.1:11435"
PROXY_URL_ALT="http://127.0.0.1:11434"
MODEL="deepseek-r1:8b"
CORPUS_DIR="${RESEARCH_DIR}/build/deepseek-free-agent-runtime/workspace"

# Verificar/Iniciar proxy
ensure_proxy() {
    if curl -sf http://127.0.0.1:11435/v1/models >/dev/null 2>&1; then
        log_ok "Proxy contexto activo"
        return 0
    fi
    
    log_warn "Proxy no responde, iniciando..."
    cd "${RESEARCH_DIR}/build"
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

# Función principal de investigación
run_research() {
    local query="$1"
    shift

    log_info "🔬 Iniciando investigación: $query"
    
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
    log_info "🔬 Ejecutando investigación: $query"

    cd "${RESEARCH_DIR}"

    # Construir argumentos para el CLI del repo (no el binario instalado, que
    # puede estar desactualizado). El proxy local inyecta num_ctx=131072.
    RESEARCH_ARGS=(
        "$query"
        --provider ollama
        --model "${MODEL}"
        --ollama-base-url "http://127.0.0.1:11435"
        --ollama-api openai
        --search local
        --documents "${CORPUS_DIR}"
        --privacy private-documents
        --max-iterations 2
        --max-llm-calls 10
        --format json
    )

    # Añadir argumentos extra (después del shift, $# son solo los extras)
    if [ $# -gt 0 ]; then
        RESEARCH_ARGS+=("$@")
    fi

    log_info "Ejecutando: python3 ${RESEARCH_CLI} ${RESEARCH_ARGS[*]}"

    # Ejecutar con timeout
    timeout 300 python3 "${RESEARCH_CLI}" "${RESEARCH_ARGS[@]}" 2>&1 | tee /tmp/research-output.log
    
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

log_info "🔬 Iniciando investigación local: $QUERY"

# Ejecutar (run_research verifica Ollama y proxy)
if run_research "$QUERY" "$@"; then
    echo -e "\n${GREEN}✅ Investigación completada exitosamente${NC}"
    exit 0
else
    EXIT_CODE=$?
    log_error "Investigación falló (código: $EXIT_CODE)"
    exit "$EXIT_CODE"
fi