# thinker

Sistema de investigación profunda con LLM: descompone una pregunta, recupera
fuentes reales, extrae afirmaciones, evalúa la evidencia y redacta un informe
trazable. Incluye una capa de **pensamiento estructurado** en pasos validados y
herramientas de análisis estático de código.

> Estado honesto: es una **herramienta funcional de demostración**, reparada,
> verificada y con las limitaciones documentadas al final. No es un producto
> listo para producción.

## Qué contiene

| Módulo | Función |
|---|---|
| `deep_research_system.py` | Pipeline de investigación: descomposición, recuperación, extracción de claims, evaluación y reporte. |
| `llm_providers.py` | Proveedores LLM (OpenAI, OpenRouter, Kilo, Ollama, Mock) con reintentos y backoff. |
| `thinking_engine.py` | Motor común de ciclos de pensamiento por pasos con validación antes de avanzar (sin duplicación) + Tree of Thoughts (BFS/DFS/Beam). |
| `pensamiento_layer.py` | Los 7 pasos de pensamiento para investigación + orquestador con pensamiento. |
| `code_design_improvement_tools.py` | Análisis estático de Python (AST) y ciclo de pensamiento para decisiones de diseño. |
| `web_search.py` | Búsqueda real sin API key (Wikipedia, DuckDuckGo) y mock offline, con formulación de consulta. |
| `plugins/` | Sistema de plugins con hot-swap (proveedores LLM y búsqueda, extensiones del núcleo) + CLI de gestión. Config: `config/plugins.yaml`; guía: `docs/PLUGINS.md`. |
| `tests/benchmarks/` | Framework de benchmark por dominio con rúbricas y LLM-as-judge opcional (`--list` para ver las tareas). |
| `docs/LECCIONES-APRENDIDAS.md` | Memoria del proyecto: hallazgos, causas y soluciones. |
| `docs/REFERENCIAS-IA.md` | Teoría y práctica de IA (referencias verificadas contra arXiv y guías de ingeniería) con propuestas medidas por el benchmark. |
| `AGENTS.md` | Reglas de trabajo para agentes de IA (ruleset P0/P1/P2 + reglas propias). |

## Requisitos

- Python 3.11 o superior (verificado en 3.11 y 3.12).
- Dependencias: `requests`, `openai>=1.0`, `python-dotenv` (ver `requirements.txt`).
- Opcional: [Ollama](https://ollama.com/) para modelos locales.

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate

# Opción reproducible (versiones fijadas con hashes):
python3 -m pip install --require-hashes -r requirements.lock

# Opción rápida (rangos de versión):
pip install -r requirements.txt
```

## Uso rápido (offline, sin red ni API keys)

```bash
python3 deep_research_system.py            # pipeline completo (LLM y búsqueda simulados)
python3 pensamiento_layer.py               # ciclo de pensamiento de 7 pasos
python3 code_design_improvement_tools.py   # análisis estático + decisiones de diseño
```

Los proveedores simulados (`MockLLM`, `MockSearchAPI`) están declarados como
simulados: sirven para verificar el pipeline, no producen investigación real.

## Uso real (OpenRouter con modelos gratuitos)

1. Copia `.env.example` a `.env` y pon tu clave de OpenRouter:
   `OPENROUTER_API_KEY=...` (el archivo `.env` está en `.gitignore`).
2. Opcional: elige otro modelo gratuito con `OPENROUTER_MODEL`
   (por defecto `poolside/laguna-xs-2.1:free`, coste 0).
3. Ejecuta la verificación real de extremo a extremo:

```bash
python3 test_openrouter_real.py     # conexión + pensamiento + pipeline (modelo :free)
python3 test_env_usage.py --real    # integración de la clave .env
python3 openrouter_integration_demo.py --real
```

Con **Ollama local** (sin API key, sin coste; requiere `ollama serve`):

```bash
python3 test_ollama_real.py         # conexión + pensamiento + pipeline con LLM local
OLLAMA_MODEL=qwen3:8b python3 test_ollama_real.py   # otro modelo local
```

Para usar búsqueda web real en el pipeline:

```python
from deep_research_system import OpenRouterLLM, ResearchOrchestrator
from web_search import WikipediaSearchAPI      # o DuckDuckGoSearchAPI

report, ctx = ResearchOrchestrator(OpenRouterLLM(), WikipediaSearchAPI()).research(
    "¿Cuál es el estado actual de la fusión nuclear?"
)
```

## Verificación

```bash
make check                                    # lint + tests + escaneo de secretos + hook
make lint                                     # ruff check .
make test                                     # suite unittest (stdlib)
make coverage                                 # cobertura de los módulos de producción
make secrets                                  # escaneo de secretos/datos personales
make sbom                                     # inventario de dependencias (syft si está)
make vuln-scan                                # pip-audit sobre requirements.lock
make mutation                                 # pruebas de mutación (mutmut)
make ci                                       # CI local: verifica una copia limpia de HEAD
make lock                                     # regenera requirements.lock con hashes
make hook                                     # instala el hook pre-commit de git
```

Equivalente sin `make`:

```bash
ruff check .
python3 -m unittest discover -s tests -v
coverage run --source=. -m unittest discover -s tests && coverage report -m
bash scripts/scan-secrets.sh
python3 honest_test.py                        # comprobación honesta del sistema
```

El hook `.git/hooks/pre-commit` (instalado con `make hook`) ejecuta ruff, el
escaneo de secretos, `py_compile` y la suite antes de cada commit.

## Limitaciones conocidas (sin adornos)

- El pipeline con `MockSearchAPI` **no hace investigación real**: las fuentes son
  ficticias. Con `WikipediaSearchAPI`/`DuckDuckGoSearchAPI` sí recupera fuentes
  reales, pero la calidad depende de esas fuentes.
- Los dos orquestadores (`ResearchOrchestrator` y
  `ResearchOrchestratorWithThinking`) usan **el mismo pipeline real** de
  evidencias; la calidad del informe depende del modelo y del buscador
  configurados, no de heurísticas locales.
- Los modelos gratuitos de OpenRouter tienen límites de tasa y errores 5xx
  transitorios; el código reintenta con backoff, pero la intermitencia persiste.
- No hay integración continua en la nube (la verificación es local, por diseño).
- Verificado en Linux con Python 3.11 y 3.12; no se ha probado en Windows ni
  macOS (los scripts son `bash`; el código Python no usa rutas de sistema).
- La suite mata el **75%** de los mutantes de `mutmut` (65,7% si se incluyen las
  líneas `print`, que solo generan mutantes equivalentes): cobertura alta no
  equivale a tests fuertes.

## Licencia

**GNU General Public License v3.0** (`GPL-3.0-only`). Texto legal completo en
[`LICENSE`](LICENSE) (copia verbatim de
<https://www.gnu.org/licenses/gpl-3.0.txt>).

Las reglas de `AGENTS.md` derivan de
[better-ai](https://github.com/jmbigi/better-ai) (CC BY-SA 4.0) y
[better-project](https://github.com/jmbigi/better-project) (GPL-3.0-or-later),
con atribución conservada. Esto no constituye asesoramiento legal: si vas a
distribuir el proyecto, revisa la compatibilidad de licencias con tu caso.

## Reglas del proyecto

Las reglas de trabajo (verificación con evidencia, no destrucción, no secretos,
alcance, honestidad) están en [`AGENTS.md`](AGENTS.md), derivadas de
[better-ai](https://github.com/jmbigi/better-ai) y
[better-project](https://github.com/jmbigi/better-project).
