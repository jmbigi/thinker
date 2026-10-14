#!/usr/bin/env bash
# Genera el SBOM del proyecto (P0.18).
# Usa syft (SPDX real) si está instalado; si no, el inventario propio.
set -euo pipefail
cd "$(git rev-parse --show-toplevel 2>/dev/null || echo .)"

if command -v syft >/dev/null 2>&1; then
    fecha=$(date +%F)
    syft . -o spdx-json > "docs/SBOM-${fecha}.spdx.json"
    echo "SBOM SPDX escrito en docs/SBOM-${fecha}.spdx.json (syft)"
else
    echo "syft no instalado: se usa el inventario propio (scripts/sbom_fallback.py)"
    python3 scripts/sbom_fallback.py
fi
