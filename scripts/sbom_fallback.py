#!/usr/bin/env python3
"""
Generador de SBOM minimalista (sin dependencias externas).

Lee `requirements.lock` (generado con `uv pip compile --generate-hashes`) y
emite un JSON con los paquetes, versiones y hashes sha256 de los artefactos.

NO es un SBOM conforme a SPDX/CycloneDX completo: es un inventario honesto de
la cadena de suministro mientras no se instale `syft` (que produce SPDX real).
"""

import json
import re
import sys
from datetime import date
from pathlib import Path

LOCK = Path("requirements.lock")


def parse_lock(text: str) -> list:
    paquetes = []
    actual = None
    for linea in text.splitlines():
        linea = linea.rstrip()
        m = re.match(r"^([A-Za-z0-9_.\-]+)==([^\s\\]+)", linea)
        if m:
            actual = {"name": m.group(1), "version": m.group(2), "hashes": []}
            paquetes.append(actual)
            continue
        h = re.search(r"--hash=sha256:([0-9a-f]+)", linea)
        if h and actual is not None:
            actual["hashes"].append(h.group(1))
    return paquetes


def main() -> int:
    if not LOCK.exists():
        print("ERROR: no existe requirements.lock (genera con 'make lock')",
              file=sys.stderr)
        return 1

    paquetes = parse_lock(LOCK.read_text(encoding="utf-8"))
    sbom = {
        "sbomFormat": "minimal-json",
        "conformsTo": "ninguno (inventario propio; usar syft para SPDX)",
        "generated": date.today().isoformat(),
        "source": str(LOCK),
        "packageCount": len(paquetes),
        "packages": paquetes,
    }

    destino = Path(f"docs/SBOM-{sbom['generated']}.json")
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(sbom, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    print(f"SBOM escrito en {destino} ({len(paquetes)} paquetes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
