# Guía del Sistema de Plugins

Sistema de plugins con intercambio en caliente (hot-swap) para proveedores LLM,
buscadores y extensiones del núcleo. Configuración declarativa en YAML,
dashboard de monitorización y CLI de gestión.

## Estructura de directorios

```
plugins/
├── __init__.py            # API pública
├── interfaces.py          # Interfaces base (PluginBase, LLMProviderPlugin, ...)
├── registry.py            # PluginRegistry: descubrimiento, carga, hot-swap
├── dashboard.py           # Dashboard de métricas y salud
├── cli.py                 # CLI de gestión
├── llm_providers/         # Plugins de proveedores LLM
│   ├── openrouter_plugin.py
│   ├── deepseek_plugin.py
│   └── mock_llm_plugin.py
└── search_providers/      # Plugins de búsqueda
    ├── duckduckgo_plugin.py
    ├── wikipedia_plugin.py
    └── mock_search_plugin.py
config/
└── plugins.yaml           # Configuración declarativa (enabled/priority/params)
```

## Interfaces (plugins/interfaces.py)

### Tipos y estados

- `PluginType`: `LLM_PROVIDER` | `SEARCH_PROVIDER` | `CORE`
- `PluginStatus`: `UNLOADED` | `LOADING` | `LOADED` | `ACTIVE` | `ERROR` | `DISABLED`

### Metadatos y configuración

- `PluginMetadata(name, version, plugin_type, description, author, dependencies,
  config_schema, status, error_message, load_time, last_used, usage_count)`
- `PluginConfig(enabled=True, priority=0, params={})` — a mayor `priority`,
  preferencia al activar.

### Clases base

`PluginBase(config=None)` — métodos comunes:

| Método | Descripción |
|--------|-------------|
| `initialize()` | Se llama al cargar el plugin |
| `shutdown()` | Se llama al descargar el plugin |
| `health_check()` | Estado de salud (bool/dict) |
| `get_stats()` | Estadísticas de uso |

`LLMProviderPlugin` (para proveedores LLM):

| Método | Firma |
|--------|-------|
| `generate` | `generate(prompt, model=None, **kwargs) -> str` |
| `get_available_models` | `get_available_models() -> list` |
| `estimate_cost` | `estimate_cost(prompt, model=None) -> float` |

`SearchProviderPlugin` (para buscadores):

| Método | Firma |
|--------|-------|
| `search` | `search(query, max_results=None) -> list[dict]` (None usa `params.max_results`, defecto 5) |
| `get_source_name` | `get_source_name() -> str` |

`CorePlugin` (extensiones del núcleo) — devuelve hooks en `get_hooks()`:

Hooks disponibles: `pre_research`, `post_research`, `pre_thinking_step`,
`post_thinking_step`, `pre_claim_extraction`, `post_claim_extraction`,
`pre_evaluation`, `post_evaluation`, `pre_report`, `post_report`.

## Registro (plugins/registry.py)

```python
from plugins import PluginRegistry, plugin_registry
```

Instancia global `plugin_registry` con directorios por defecto
(`plugins/llm_providers`, `plugins/search_providers`, `plugins/core`) y
`config/plugins.yaml`.

| Método | Descripción |
|--------|-------------|
| `discover_plugins()` | Escanea directorios y registra clases (→ int) |
| `load_plugin(name, config=None)` | Carga un plugin (→ bool) |
| `unload_plugin(name)` | Descarga un plugin |
| `reload_plugin(name)` | Hot-swap: descarga, relee `config/plugins.yaml` y recarga |
| `set_active_llm(name)` / `set_active_search(name)` | Cambia el proveedor activo |
| `get_active_llm()` / `get_active_search()` | Consulta el activo |
| `get_plugin(name)` | Instancia del plugin |
| `list_plugins(plugin_type=None)` | Metadatos de plugins |
| `load_all(plugin_type=None)` | Carga todos (o de un tipo) |
| `trigger_hook(hook_name, *args)` | Ejecuta hooks de CorePlugins |
| `shutdown_all()` | Descarga todo |
| `get_dashboard_data()` | Datos para el dashboard |

La configuración se fusiona: YAML (`config/plugins.yaml` → clave `plugins:`
con `enabled`, `priority`, `params`) + `PluginConfig` pasado por parámetro.
El hot-reload relee el YAML: los cambios de `priority` y `params` se aplican
sin reiniciar; `enabled` rige `load_all` (una carga o recarga explícita es
deliberada). Un `PluginConfig` pasado explícitamente por código se conserva
como override.

`params.max_results` (buscadores) fija el límite por defecto:
`search(query)` lo usa y `search(query, N)` lo sobreescribe. Sin el parámetro,
el defecto es 5.

## Configuración (config/plugins.yaml)

```yaml
plugins:
  openrouter:
    enabled: true
    priority: 100
    params:
      model: poolside/laguna-xs-2.1:free
      use_fallback: true
      max_retries: 3
  deepseek:
    enabled: true
    priority: 90
    params:
      model: deepseek-chat
      base_url: https://api.deepseek.com/v1
  mock_llm:
    enabled: true
    priority: 10
  duckduckgo:
    enabled: true
    priority: 100
    params:
      max_results: 5
  wikipedia:
    enabled: true
    priority: 90
    params:
      language: es
      max_results: 5
  mock_search:
    enabled: true
    priority: 10
```

## CLI (python -m plugins.cli ...)

| Comando | Descripción |
|---------|-------------|
| `discover` | Escanea y registra plugins |
| `list [--type llm_provider\|search_provider\|core] [--json]` | Lista plugins |
| `load [nombre\|--all]` | Carga un plugin (o todos) |
| `unload nombre` | Descarga un plugin |
| `reload nombre` | Hot-swap de un plugin |
| `set-active llm\|search nombre` | Cambia el proveedor activo |
| `dashboard [--json]` | Métricas y salud |
| `health [--json]` | Estado de salud |
| `test nombre [--prompt ...]` | Prueba un plugin |

Ejemplos:

```bash
python -m plugins.cli discover
python -m plugins.cli load --all
python -m plugins.cli list --type llm_provider
python -m plugins.cli set-active llm deepseek
python -m plugins.cli test deepseek --prompt "Responde: OK"
python -m plugins.cli dashboard
```

## Crear un plugin

1. Crea el archivo en el directorio correspondiente
   (`plugins/llm_providers/`, `plugins/search_providers/` o `plugins/core/`).
2. Hereda de la interfaz adecuada e implementa sus métodos.
3. Declara los metadatos sobrescribiendo `_get_metadata()`.
4. Registra la clase al final del archivo:

```python
class MiPlugin(LLMProviderPlugin):
    def _get_metadata(self):
        return PluginMetadata(
            name="miplugin",
            version="1.0.0",
            plugin_type=PluginType.LLM_PROVIDER,
            description="Mi proveedor personalizado",
            author="...",
        )

    def initialize(self):
        ...
        return True

    def generate(self, prompt, model=None, **kwargs):
        return "..."

    def get_available_models(self):
        return ["mi-modelo"]

    def estimate_cost(self, prompt, model=None):
        return 0.0


plugin_registry._register_plugin_class(MiPlugin, __file__)
```

Ojo: los metadatos se declaran en `_get_metadata()`, **no** como atributo de
clase `metadata = PluginMetadata(...)`. `PluginBase.__init__` asigna
`self.metadata` con el resultado de `_get_metadata()`, así que el atributo de
clase quedaría anulado y el plugin se registraría con el nombre de la clase y
versión `0.0.0` (verificado).

Nota (Python ≤3.13): las anotaciones de tipo se evalúan al importar el módulo;
si usas `List`, `Dict`, `Any`, etc. en firmas, IMPÓRTALOS de `typing` en el
mismo archivo. En Python 3.14 (PEP 649) son perezosas y el fallo queda oculto.

## Dashboard (plugins/dashboard.py)

`PluginDashboard` agrega métricas por plugin: peticiones, errores, tasa de
error, tiempo de carga, uso; estado global de salud; export JSON. Se consulta
vía CLI (`dashboard`, `health`) o programáticamente con
`plugin_registry.get_dashboard_data()`.

## Verificación

- `python3 -m unittest discover -s tests -p "test_plugin_*.py"` — 63 pruebas
  automatizadas (descubrimiento, config YAML y hot-reload, ciclo de vida,
  hooks, dashboard, CLI, proveedores envueltos y plugins simulados offline).
  Forman parte de la suite: `make test`.
- `python test_plugin_system.py` — 8 pruebas de humo: descubrimiento, carga,
  proveedor activo, ejecución, hot-reload, dashboard, config, apagado.
- `ruff check plugins/ config/` — sin errores.
