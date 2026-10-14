#!/usr/bin/env python3
"""Instala los paquetes necesarios y guarda el resultado en install_result.json."""
import importlib.util
import json
import subprocess
import sys

# Install needed packages
packages = ['requests', 'ollama']
installed = []

for pkg in packages:
    try:
        subprocess.run([sys.executable, '-m', 'pip', 'install', pkg, '--quiet'],
                       capture_output=True, timeout=60)
        installed.append(pkg)
        print(f"Installed: {pkg}")
    except Exception as e:
        print(f"Failed to install {pkg}: {e}")

# Verify imports
result = {}
for pkg in ['requests', 'ollama']:
    spec = importlib.util.find_spec(pkg)
    if spec is None:
        result[pkg] = 'not available'
    elif pkg == 'requests':
        import requests
        result[pkg] = requests.__version__
    else:
        result[pkg] = 'available'

# Write result file (ruta local relativa al proyecto)
with open('install_result.json', 'w') as f:
    json.dump(result, f, indent=2)

print("Result:", json.dumps(result, indent=2))
