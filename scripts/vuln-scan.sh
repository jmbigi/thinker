#!/usr/bin/env bash
# Escaneo de vulnerabilidades de las dependencias fijadas (P0.18).
# Requiere pip-audit; sin él, informa y no falla la verificación.
set -euo pipefail
cd "$(git rev-parse --show-toplevel 2>/dev/null || echo .)"

if ! python3 -m pip_audit --version >/dev/null 2>&1; then
    echo "pip-audit no instalado: OMITIDO (instala con 'pip install pip-audit')"
    exit 0
fi

echo "Auditando requirements.lock con pip-audit..."
python3 -m pip_audit -r requirements.lock --progress-spinner off
