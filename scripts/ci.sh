#!/usr/bin/env bash
# CI local sin proveedores externos (P1.9): exporta HEAD a una copia limpia y
# verifica ALLÍ. Detecta dependencias de archivos no versionados: si algo pasa
# solo por lo que tienes sin comitear, aquí falla.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
destino=$(mktemp -d)
trap 'rm -rf "$destino"' EXIT

echo "[ci] exportando HEAD a copia limpia: $destino"
git archive HEAD | tar -x -C "$destino"

cd "$destino"

echo "[ci] ruff check"
if command -v ruff >/dev/null 2>&1; then
    ruff check .
else
    echo "  ruff no instalado: OMITIDO"
fi

echo "[ci] py_compile"
for f in *.py tests/*.py; do
    python3 -m py_compile "$f"
done

echo "[ci] unittest (copia limpia, sin red)"
python3 -m unittest discover -s tests -q

echo "[ci] escaneo de secretos"
bash scripts/scan-secrets.sh

echo "[ci] OK: la copia limpia de HEAD verifica entera"
