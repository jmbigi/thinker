# Comandos del proyecto (P2.1: herramientas libres, sin cuentas en la nube).
.PHONY: help lint preflight docs-check test coverage secrets lock sbom vuln-scan mutation check ci hook install

help:
	@echo "make lint        - ruff check ."
	@echo "make preflight   - gates deterministas (imports, silencios, duplicados, tareas)"
	@echo "make docs-check  - cifras de estado presente en docs vs realidad"
	@echo "make test        - suite unittest (stdlib)"
	@echo "make coverage    - cobertura de los módulos de producción"
	@echo "make secrets     - escaneo de secretos/datos personales (P0.6/P0.9)"
	@echo "make lock        - regenera requirements.lock con hashes (uv)"
	@echo "make sbom        - SBOM (syft si está; si no, inventario propio)"
	@echo "make vuln-scan   - pip-audit sobre requirements.lock"
	@echo "make mutation    - pruebas de mutación (mutmut): miden la fuerza de la suite"
	@echo "make ci          - CI local: verifica una copia limpia de HEAD"
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

secrets:
	bash scripts/scan-secrets.sh

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
