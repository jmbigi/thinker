"""
DuckDuckGo Search Provider Plugin.

Wraps the existing DuckDuckGoSearchAPI for plugin system compatibility.
"""

from plugins.interfaces import SearchProviderPlugin, PluginMetadata, PluginType
from plugins.registry import plugin_registry


class DuckDuckGoSearchPlugin(SearchProviderPlugin):
    """DuckDuckGo search provider as a plugin."""

    def _get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="duckduckgo",
            version="1.0.0",
            plugin_type=PluginType.SEARCH_PROVIDER,
            description="DuckDuckGo HTML scraping search (no API key required)",
            author="Deep Research System",
            # El extractor es regex sobre el HTML (web_search.py): no usa
            # BeautifulSoup, así que no se declara como dependencia.
            dependencies=["requests"],
            config_schema={
                "type": "object",
                "properties": {
                    "max_results": {"type": "integer", "default": 5},
                    "timeout": {"type": "integer", "default": 10},
                },
            },
        )

    def initialize(self) -> bool:
        try:
            from web_search import DuckDuckGoSearchAPI
            timeout = self.config.params.get("timeout", 10)
            # `params.max_results` es el límite por defecto del plugin; un
            # `max_results` explícito en `search()` tiene prioridad.
            self._max_results = int(self.config.params.get("max_results", 5))
            self._search = DuckDuckGoSearchAPI(timeout=timeout)
            self._initialized = True
            return True
        except Exception as e:
            self.metadata.error_message = str(e)
            return False

    def shutdown(self) -> None:
        self._initialized = False

    def get_source_name(self) -> str:
        return "DuckDuckGo"


# Register on import
plugin_registry._register_plugin_class(DuckDuckGoSearchPlugin, __file__)