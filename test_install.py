import importlib.util
import sys

print(f"Python version: {sys.version}")
try:
    import requests
    print(f"requests version: {requests.__version__}")
except ImportError:
    print("requests not installed")
print("ollama installed" if importlib.util.find_spec("ollama") else "ollama not installed")
