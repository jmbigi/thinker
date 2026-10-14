#!/usr/bin/env python3
"""Verifica la instalación y guarda el resultado en install_check.json (local)."""
import importlib.util
import json
import sys

result = {
    "python_version": sys.version,
    "requests_installed": False,
    "ollama_installed": False
}

try:
    import requests
    result["requests_installed"] = True
    result["requests_version"] = requests.__version__
except ImportError:
    pass

result["ollama_installed"] = importlib.util.find_spec("ollama") is not None

with open("install_check.json", "w") as f:
    json.dump(result, f, indent=2)

print(json.dumps(result, indent=2))
