#!/usr/bin/env bash
# Wrapper de compatibilidad: la implementación portable es Python
# (scripts/scan_secrets.py), que funciona también en Windows sin bash.
set -euo pipefail
cd "$(git rev-parse --show-toplevel 2>/dev/null || echo .)"
exec python3 scripts/scan_secrets.py "$@"
