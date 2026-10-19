"""
Plugin Registry for the Deep Research System.

Handles plugin discovery, loading, unloading, hot-swapping, and configuration management.
"""

import os
import sys
import time
import tomllib
import importlib
import importlib.util
from typing import Any, Dict, List, Optional, Type, Callable
from dataclasses import dataclass
from collections import defaultdict

from .interfaces import (
    PluginBase,
    PluginMetadata,
    PluginConfig,
    PluginType,
    PluginStatus,
    LLMProviderPlugin,
    SearchProviderPlugin,
    CorePlugin,
)


@dataclass
class PluginEntry:
    """Registry entry for a plugin."""
    metadata: PluginMetadata
    plugin_class: Type[PluginBase]
    config: PluginConfig
    instance: Optional[PluginBase] = None
    module_path: str = ""


class PluginRegistry:
    """
    Central plugin registry.
    
    Manages plugin lifecycle: discovery, loading, initialization, hot-swapping, and shutdown.
    Supports declarative configuration via config files.
    """

    def __init__(self, plugin_dirs: List[str] = None, config_path: str = None):
        self.plugin_dirs = plugin_dirs or [
            "plugins/llm_providers",
            "plugins/search_providers",
            "plugins/core",
        ]
        self.config_path = config_path or "config/plugins.yaml"
        
        self._plugins: Dict[str, PluginEntry] = {}
        self._hooks: Dict[str, List[Callable]] = defaultdict(list)
        self._plugin_hooks: Dict[str, Dict[str, Callable]] = {}
        self._active_llm: Optional[str] = None
        self._active_search: Optional[str] = None
        self._config_cache: Dict[str, Any] = {}
        
        # Los directorios de plugins NO se crean aquí: `discover_plugins` ya
        # omite los que no existen, y crear carpetas al importar el módulo
        # ensuciaba el árbol de trabajo como efecto colateral (P0.3).

    def discover_plugins(self) -> int:
        """
        Discover all plugins in plugin directories.
        
        Returns number of plugins discovered.
        """
        count = 0
        for plugin_dir in self.plugin_dirs:
            if not os.path.isdir(plugin_dir):
                continue
            for file in os.listdir(plugin_dir):
                if file.endswith(".py") and not file.startswith("__"):
                    module_path = os.path.join(plugin_dir, file)
                    module_name = file[:-3]
                    try:
                        discovered = self._load_plugin_module(module_name, module_path)
                        count += discovered
                    except Exception as e:
                        print(f"[PluginRegistry] Failed to load {module_name}: {e}", file=sys.stderr)
        return count

    def _load_plugin_module(self, module_name: str, module_path: str) -> int:
        """Load a plugin module and register any plugin classes found."""
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec is None or spec.loader is None:
            return 0
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        
        count = 0
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type) and issubclass(attr, PluginBase) 
                and attr is not PluginBase
                and attr is not LLMProviderPlugin
                and attr is not SearchProviderPlugin
                and attr is not CorePlugin):
                # Only register concrete classes (no abstract methods)
                if not getattr(attr, '__abstractmethods__', None):
                    self._register_plugin_class(attr, module_path)
                    count += 1
        return count

    def _register_plugin_class(self, plugin_class: Type[PluginBase], module_path: str) -> None:
        """Register a plugin class (not instance)."""
        # Create temporary instance to get metadata
        temp_instance = plugin_class()
        metadata = temp_instance.metadata
        metadata.status = PluginStatus.UNLOADED

        existing = self._plugins.get(metadata.name)
        if existing and existing.metadata.status in (PluginStatus.LOADED,
                                                     PluginStatus.LOADING):
            # Un descubrimiento posterior NO debe pisar una entrada viva:
            # se perdería la instancia cargada (y sus hooks quedarían huérfanos).
            return
        
        entry = PluginEntry(
            metadata=metadata,
            plugin_class=plugin_class,
            config=PluginConfig(),
            module_path=module_path,
        )
        self._plugins[metadata.name] = entry

    def load_plugin(self, name: str, config: PluginConfig = None) -> bool:
        """
        Load and initialize a plugin by name.
        
        Returns True on success.
        """
        if name not in self._plugins:
            print(f"[PluginRegistry] Plugin not found: {name}", file=sys.stderr)
            return False
        
        entry = self._plugins[name]
        if entry.metadata.status == PluginStatus.LOADED:
            return True  # Already loaded
        
        entry.metadata.status = PluginStatus.LOADING
        start_time = time.time()
        
        try:
            # Merge with config file if available
            final_config = self._merge_config(name, config)
            entry.config = final_config
            
            # Create instance
            instance = entry.plugin_class(final_config)
            entry.instance = instance
            # Una única fuente de metadatos: el instance comparte el objeto
            # `metadata` del registro, de modo que `get_stats()` (dashboard/CLI)
            # y el ciclo de vida (status, load_time, error) no puedan divergir.
            instance.metadata = entry.metadata
            
            # Initialize
            if not instance.initialize():
                entry.metadata.status = PluginStatus.ERROR
                entry.metadata.error_message = "Initialization returned False"
                return False
            
            entry.metadata.status = PluginStatus.LOADED
            entry.metadata.load_time = time.time() - start_time
            entry.metadata.error_message = ""
            
            # Register hooks if CorePlugin
            if isinstance(instance, CorePlugin):
                self._register_hooks(instance)
            
            # Set as active if first of its type
            if isinstance(instance, LLMProviderPlugin) and not self._active_llm:
                self._active_llm = name
            elif isinstance(instance, SearchProviderPlugin) and not self._active_search:
                self._active_search = name
            
            print(f"[PluginRegistry] Loaded plugin: {name} v{entry.metadata.version}")
            return True
            
        except Exception as e:
            entry.metadata.status = PluginStatus.ERROR
            entry.metadata.error_message = str(e)
            print(f"[PluginRegistry] Failed to load {name}: {e}", file=sys.stderr)
            return False

    def unload_plugin(self, name: str) -> bool:
        """Unload a plugin by name."""
        if name not in self._plugins:
            return False
        
        entry = self._plugins[name]
        if entry.instance:
            try:
                entry.instance.shutdown()
            except Exception as e:
                print(f"[PluginRegistry] Error shutting down {name}: {e}", file=sys.stderr)
        
        # Unregister hooks
        if entry.instance and isinstance(entry.instance, CorePlugin):
            self._unregister_hooks(entry.instance)
        
        entry.instance = None
        entry.metadata.status = PluginStatus.UNLOADED
        
        # Clear active if this was active
        if self._active_llm == name:
            self._active_llm = self._find_first_loaded(PluginType.LLM_PROVIDER)
        if self._active_search == name:
            self._active_search = self._find_first_loaded(PluginType.SEARCH_PROVIDER)
        
        return True

    def reload_plugin(self, name: str) -> bool:
        """Hot-reload a plugin."""
        config = self._plugins[name].config if name in self._plugins else None
        self.unload_plugin(name)
        return self.load_plugin(name, config)

    def _merge_config(self, name: str, config: PluginConfig = None) -> PluginConfig:
        """Merge plugin config with config file."""
        file_config = self._load_config_file().get(name, {})
        
        base_config = PluginConfig(
            enabled=file_config.get("enabled", True),
            priority=file_config.get("priority", 0),
            params=file_config.get("params", {}),
        )
        
        if config:
            base_config.enabled = config.enabled
            base_config.priority = config.priority
            base_config.params.update(config.params)
        
        return base_config

    def _load_config_file(self) -> Dict[str, Any]:
        """Load plugin configuration from YAML/TOML file.

        Un archivo ilegible o una dependencia ausente NO se ignoran en
        silencio (P1.19/P1.26): se eleva un RuntimeError con el motivo, en vez
        de seguir con los valores por defecto como si la config fuera válida.
        """
        if self._config_cache:
            return self._config_cache
        
        config = {}
        if os.path.exists(self.config_path):
            try:
                if self.config_path.endswith(".yaml") or self.config_path.endswith(".yml"):
                    import yaml
                    with open(self.config_path, "r") as f:
                        config = yaml.safe_load(f) or {}
                elif self.config_path.endswith(".toml"):
                    with open(self.config_path, "rb") as f:
                        config = tomllib.load(f)
            except ImportError as e:
                raise RuntimeError(
                    f"No se puede leer {self.config_path}: falta la dependencia "
                    f"de YAML ({e}). Instala PyYAML (ver requirements.txt) o usa "
                    "un archivo .toml."
                ) from e
            except Exception as e:
                raise RuntimeError(
                    f"No se pudo leer la configuración de plugins "
                    f"({self.config_path}): {e}"
                ) from e
        
        self._config_cache = config.get("plugins", {})
        return self._config_cache

    def _register_hooks(self, plugin: CorePlugin) -> None:
        """Register plugin hooks.

        Se guardan los callables EXACTOS que se registran: `get_hooks()` puede
        devolver objetos nuevos en cada llamada (p. ej. lambdas), así que dar
        de baja con una llamada nueva no encontraría nada y el hook seguiría
        activo tras el hot-swap.
        """
        hooks = dict(plugin.get_hooks())
        self._plugin_hooks[plugin.metadata.name] = hooks
        for hook_name, hook_func in hooks.items():
            self._hooks[hook_name].append(hook_func)

    def _unregister_hooks(self, plugin: CorePlugin) -> None:
        """Unregister plugin hooks (los registrados exactamente al cargar)."""
        registered = self._plugin_hooks.pop(plugin.metadata.name, {})
        for hook_name, hook_func in registered.items():
            if hook_func in self._hooks[hook_name]:
                self._hooks[hook_name].remove(hook_func)

    def _find_first_loaded(self, plugin_type: PluginType) -> Optional[str]:
        """Find first loaded plugin of given type."""
        for name, entry in self._plugins.items():
            if (entry.metadata.plugin_type == plugin_type 
                and entry.metadata.status == PluginStatus.LOADED):
                return name
        return None

    def get_plugin(self, name: str) -> Optional[PluginBase]:
        """Get a loaded plugin instance."""
        entry = self._plugins.get(name)
        return entry.instance if entry else None

    def get_active_llm(self) -> Optional[LLMProviderPlugin]:
        """Get the currently active LLM provider."""
        if self._active_llm:
            entry = self._plugins.get(self._active_llm)
            if entry and entry.metadata.status == PluginStatus.LOADED:
                return entry.instance
        # Fallback: find any loaded LLM provider
        self._active_llm = self._find_first_loaded(PluginType.LLM_PROVIDER)
        if self._active_llm:
            return self._plugins[self._active_llm].instance
        return None

    def get_active_search(self) -> Optional[SearchProviderPlugin]:
        """Get the currently active search provider."""
        if self._active_search:
            entry = self._plugins.get(self._active_search)
            if entry and entry.metadata.status == PluginStatus.LOADED:
                return entry.instance
        self._active_search = self._find_first_loaded(PluginType.SEARCH_PROVIDER)
        if self._active_search:
            return self._plugins[self._active_search].instance
        return None

    def set_active_llm(self, name: str) -> bool:
        """Set the active LLM provider."""
        if name not in self._plugins:
            return False
        entry = self._plugins[name]
        if entry.metadata.plugin_type != PluginType.LLM_PROVIDER:
            return False
        if entry.metadata.status != PluginStatus.LOADED:
            return False
        self._active_llm = name
        return True

    def set_active_search(self, name: str) -> bool:
        """Set the active search provider."""
        if name not in self._plugins:
            return False
        entry = self._plugins[name]
        if entry.metadata.plugin_type != PluginType.SEARCH_PROVIDER:
            return False
        if entry.metadata.status != PluginStatus.LOADED:
            return False
        self._active_search = name
        return True

    def trigger_hook(self, hook_name: str, *args, **kwargs) -> List[Any]:
        """Trigger all registered hooks for a given name."""
        results = []
        for hook in self._hooks.get(hook_name, []):
            try:
                result = hook(*args, **kwargs)
                results.append(result)
            except Exception as e:
                print(f"[PluginRegistry] Hook {hook_name} failed: {e}", file=sys.stderr)
        return results

    def list_plugins(self, plugin_type: PluginType = None) -> List[Dict[str, Any]]:
        """List all plugins with their status."""
        result = []
        for name, entry in self._plugins.items():
            if plugin_type is None or entry.metadata.plugin_type == plugin_type:
                stats = entry.instance.get_stats() if entry.instance else {
                    "name": entry.metadata.name,
                    "version": entry.metadata.version,
                    "type": entry.metadata.plugin_type.value,
                    "status": entry.metadata.status.value,
                    "error_message": entry.metadata.error_message,
                }
                stats["active"] = (
                    (name == self._active_llm and entry.metadata.plugin_type == PluginType.LLM_PROVIDER) or
                    (name == self._active_search and entry.metadata.plugin_type == PluginType.SEARCH_PROVIDER)
                )
                result.append(stats)
        return result

    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get comprehensive dashboard data."""
        return {
            "plugins": self.list_plugins(),
            "active_llm": self._active_llm,
            "active_search": self._active_search,
            "hooks": {k: len(v) for k, v in self._hooks.items()},
            "total_plugins": len(self._plugins),
            "loaded_plugins": sum(
                1 for e in self._plugins.values() 
                if e.metadata.status == PluginStatus.LOADED
            ),
        }

    def load_all(self, plugin_type: PluginType = None) -> Dict[str, bool]:
        """Load all discovered plugins that are enabled (or of specific type).

        El `enabled` se consulta en la configuración YA FUSIONADA con el
        archivo: en el descubrimiento aún no se ha leído `config/plugins.yaml`,
        y comprobar `entry.config.enabled` ahí cargaba plugins deshabilitados.
        Una llamada explícita a `load_plugin(name)` sigue cargando el plugin
        aunque esté deshabilitado (la acción es deliberada).
        """
        results = {}
        for name, entry in self._plugins.items():
            if plugin_type is None or entry.metadata.plugin_type == plugin_type:
                if self._merge_config(name).enabled:
                    results[name] = self.load_plugin(name)
        return results

    def shutdown_all(self) -> None:
        """Shutdown all loaded plugins."""
        for name in list(self._plugins.keys()):
            self.unload_plugin(name)


# Global registry instance
plugin_registry = PluginRegistry()