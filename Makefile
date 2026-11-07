# Comandos del proyecto (P2.1: herramientas libres, sin cuentas en la nube).
.PHONY: help lint preflight docs-check test coverage audit-diff holdout secrets lock sbom vuln-scan mutation check ci hook install verify-install doctor ai-check

help:
	@echo "make lint        - ruff check ."
	@echo "make preflight   - gates deterministas (imports, silencios, duplicados, tareas)"
	@echo "make docs-check  - cifras de estado presente en docs vs realidad"
	@echo "make test        - suite unittest (stdlib)"
	@echo "make coverage    - cobertura de los módulos de producción"
	@echo "make audit-diff  - audita el diff contra BASE (defecto origin/main)"
	@echo "make holdout     - verifica hashes y ejecuta los tests holdout"
	@echo "make secrets     - escaneo de secretos/datos personales (P0.6/P0.9)"
	@echo "make lock        - regenera requirements.lock con hashes (uv)"
	@echo "make sbom        - SBOM (syft si está; si no, inventario propio)"
	@echo "make vuln-scan   - pip-audit sobre requirements.lock"
	@echo "make mutation    - pruebas de mutación (mutmut): miden la fuerza de la suite"
	@echo "make ci          - CI local: verifica una copia limpia de HEAD"
	@echo "make verify-install - instalación limpia del paquete en venv temporal"
	@echo "make doctor      - autodiagnóstico del entorno (offline por defecto)"
	@echo "make ai-check    - verifica Kimi/OpenCode y el modelo gratuito"
	@echo "make check       - todo lo anterior + hook pre-commit"
	@echo "make hook        - instala el hook pre-commit de git"
	@echo "make install     - instala el paquete (pip install .) con sus comandos"

lint:
	ruff check .

preflight:
	python3 scripts/preflight.py

docs-check:
	python3 scripts/check_docs.py

test:
	python3 -m unittest discover -s tests -v

coverage:
	python3 -m coverage run --source=. -m unittest discover -s tests
	python3 -m coverage report -m

audit-diff:
	python3 scripts/audit_changes.py --base $${BASE:-origin/main}

holdout:
	python3 scripts/run_holdout.py

secrets:
	python3 scripts/scan_secrets.py

lock:
	# --upgrade es deliberado: cada regeneración sube TODAS las dependencias a
	# la última versión compatible (así se hicieron los bumps de
	# certifi/openai/requests); sin él, uv conserva los pines del lock
	# existente y `make lock` parecería actualizar sin hacerlo (Hallazgo 96).
	uv pip compile --generate-hashes --upgrade requirements.txt -o requirements.lock

sbom:
	bash scripts/generate-sbom.sh

vuln-scan:
	bash scripts/vuln-scan.sh

mutation:
	mutmut run
	@echo "Supervivientes:" && mutmut results

ci:
	bash scripts/ci.sh

check: lint preflight docs-check test secrets ci
	bash scripts/hooks/pre-commit

hook:
	cp scripts/hooks/pre-commit .git/hooks/pre-commit
	chmod +x .git/hooks/pre-commit
	@echo "hook instalado en .git/hooks/pre-commit"

install:
	python3 -m pip install .

verify-install:
	python3 scripts/verificar_instalacion.py

doctor:
	python3 scripts/doctor.py

# ============================================================
# Infraestructura IA local (opt-in; no sustituye los gates)
# ============================================================
# Requiere ./start-all.sh (Ollama + proxy 11435 + llama.cpp) y los scripts
# locales del repo. Sin Q, los targets de investigación fallan con uso claro.
Q ?=

.PHONY: local-status local-doctor local-up local-research local-smart
local-status:
	@echo "=== Estado de servicios locales ==="
	@printf 'Ollama (11434):          '; curl -sf http://127.0.0.1:11434/api/tags >/dev/null && echo UP || echo DOWN
	@printf 'Proxy contexto (11435):  '; curl -sf http://127.0.0.1:11435/v1/models >/dev/null && echo UP || echo DOWN
	@printf 'llama.cpp (11436):       '; curl -sf http://127.0.0.1:11436/health >/dev/null && echo UP || echo DOWN

local-doctor: local-status
	@echo "=== Modelos Ollama ==="
	@ollama list 2>/dev/null || echo "ollama no disponible"

local-up:
	@echo "Levantando infraestructura local (bloquea; Ctrl+C detiene)..."
	@bash ./start-all.sh

local-research:
	@test -n "$(Q)" || { echo 'Uso: make local-research Q="tu pregunta"'; exit 2; }
	@bash ./research-local.sh "$(Q)"

local-smart:
	@test -n "$(Q)" || { echo 'Uso: make local-smart Q="tu pregunta"'; exit 2; }
	@bash ./smart-research.sh "$(Q)"

ai-check:
	@printf 'Kimi Code:   '
	@if grep -q '^default_model = "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"' "$$HOME/.kimi-code/config.toml" 2>/dev/null; then echo "modelo gratuito por defecto"; else echo "revisar $$HOME/.kimi-code/config.toml"; exit 1; fi
	@printf 'OpenCode:    '
	@if grep -q '"model": "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"' "$$HOME/.config/opencode/opencode.jsonc" 2>/dev/null; then echo "modelo gratuito configurado"; else echo "revisar $$HOME/.config/opencode/opencode.jsonc"; exit 1; fi
	@printf 'kimi doctor: '
	@if command -v kimi >/dev/null 2>&1; then kimi doctor >/dev/null 2>&1 && echo OK || { echo "revisar"; exit 1; }; else echo "kimi no disponible"; fi
