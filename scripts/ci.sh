#!/usr/bin/env bash
# CI local sin proveedores externos (P1.9): exporta HEAD a una copia limpia y
# verifica ALLÍ. Detecta dependencias de archivos no versionados: si algo pasa
# solo por lo que tienes sin comitear, aquí falla.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# Un TMPDIR heredado y no escribible no debe romper la CI: se declara y se cae
# a /tmp, que es el temporal estándar del sistema.
if [ ! -d "${TMPDIR:-/tmp}" ]; then
    echo "[ci] TMPDIR no existe (${TMPDIR:-}); usando /tmp" >&2
    TMPDIR=/tmp
    export TMPDIR
fi
if ! destino=$(mktemp -d); then
    echo "[ci] mktemp falló; reintentando con TMPDIR=/tmp" >&2
    destino=$(TMPDIR=/tmp mktemp -d)
fi
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
for f in *.py tests/*.py scripts/*.py holdout/*.py; do
    [ -e "$f" ] || continue
    python3 -m py_compile "$f"
done

echo "[ci] preflight"
python3 scripts/preflight.py

echo "[ci] docs-check"
python3 scripts/check_docs.py

echo "[ci] unittest (copia limpia, sin red)"
python3 -m unittest discover -s tests -q

echo "[ci] holdout (hashes + tests)"
python3 scripts/run_holdout.py

echo "[ci] escaneo de secretos"
bash scripts/scan-secrets.sh

echo "[ci] OK: la copia limpia de HEAD verifica entera"
