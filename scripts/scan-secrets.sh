#!/usr/bin/env bash
# Escaneo de secretos y datos personales en archivos VERSIONADOS (P0.6/P0.9/P0.10).
# Uso: bash scripts/scan-secrets.sh     (exit 1 si encuentra algo)
set -uo pipefail

cd "$(git rev-parse --show-toplevel 2>/dev/null || echo .)"

# Patrones de credenciales reales (no placeholders vacíos ni "...")
CREDENCIALES='(sk-[A-Za-z0-9]{16,}|sk-or-v1-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|xox[baprs]-[A-Za-z0-9-]{10,})'
# Datos personales / rutas reales de usuario
PERSONALES='(/home/[a-z][a-z0-9_-]+/|/Users/[a-z][a-z0-9_-]+/|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.(com|net|org|es|io))'

fallo=0
archivos=$(git ls-files 2>/dev/null)

comprobar() {
    local patron="$1" etiqueta="$2"
    local encontrados
    encontrados=$(cd . && grep -lEI "$patron" $archivos 2>/dev/null)
    if [ -n "$encontrados" ]; then
        echo "⚠️  $etiqueta:"
        echo "$encontrados" | while IFS= read -r f; do
            echo "   $f:"
            grep -nEI "$patron" "$f" | head -3 | sed 's/^/     /'
        done
        fallo=1
    fi
}

comprobar "$CREDENCIALES" "Posibles credenciales"
comprobar "$PERSONALES" "Posibles datos personales o rutas reales"

if [ "$fallo" -ne 0 ]; then
    echo
    echo "FALLO: revisa los hallazgos. Si es un falso positivo, documéntalo o ajusta el patrón."
    echo "Ojo: 'API_KEY=' vacío o con '...' es un placeholder y NO debe coincidir."
    exit 1
fi

echo "OK: sin secretos ni datos personales en archivos versionados"
