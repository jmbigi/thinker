"""
Wikipedia Search Provider Plugin.

Wraps the existing WikipediaSearchAPI for plugin system compatibility.
"""

from plugins.interfaces import SearchProviderPlugin, PluginMetadata, PluginType
from plugins.registry import plugin_registry


class WikipediaSearchPlugin(SearchProviderPlugin):
    """Wikipedia search provider as a plugin."""

    def _get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="wikipedia",
            version="1.0.0",
            plugin_type=PluginType.SEARCH_PROVIDER,
            description="Wikipedia API search (no API key required)",
            author="Deep Research System",
            dependencies=["requests"],
            config_schema={
                "type": "object",
                "properties": {
                    "language": {"type": "string", "default": "es"},
                    "max_results": {"type": "integer", "default": 5},
                    "timeout": {"type": "integer", "default": 10},
                },
            },
        )

    def initialize(self) -> bool:
        try:
            from web_search import WikipediaSearchAPI
            language = self.config.params.get("language", "es")
            timeout = self.config.params.get("timeout", 10)
            # `params.max_results` es el límite por defecto del plugin; un
            # `max_results` explícito en `search()` tiene prioridad.
            self._max_results = int(self.config.params.get("max_results", 5))
            self._search = WikipediaSearchAPI(language=language, timeout=timeout)
            self._initialized = True
            return True
        except Exception as e:
            self.metadata.error_message = str(e)
            return False

    def shutdown(self) -> None:
        self._initialized = False

    def get_source_name(self) -> str:
        return "Wikipedia"


# Register on import
plugin_registry._register_plugin_class(WikipediaSearchPlugin, __file__)