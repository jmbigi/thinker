"""
Mock Search Provider Plugin.

Provides deterministic offline search results for testing and demos.
"""

from typing import Any, Dict, List

from plugins.interfaces import SearchProviderPlugin, PluginMetadata, PluginType
from plugins.registry import plugin_registry


class _BusquedaSimulada:
    """Fuente de búsqueda simulada (offline, determinista) con la forma de
    `SearchAPI`: el método `search` común de `SearchProviderPlugin` delega en
    ella, igual que los plugins reales delegan en su API de `web_search`.
    """

    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        return [{
            "title": f"Mock Result {i + 1} for: {query[:50]}",
            "url": f"https://example.com/mock-result-{i + 1}",
            "snippet": f"This is a simulated search result for query: {query}. "
                       f"Result number {i + 1} contains relevant information about the topic.",
            "source": "MockSearchAPI",
        } for i in range(max_results)]


class MockSearchPlugin(SearchProviderPlugin):
    """Mock search provider as a plugin (offline, deterministic)."""

    def _get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="mock_search",
            version="1.0.0",
            plugin_type=PluginType.SEARCH_PROVIDER,
            description="Deterministic offline search for testing and demos",
            author="Deep Research System",
            dependencies=[],
            config_schema={
                "type": "object",
                "properties": {
                    "max_results": {"type": "integer", "default": 5},
                },
            },
        )

    def initialize(self) -> bool:
        # `params.max_results` es el límite por defecto del plugin; un
        # `max_results` explícito en `search()` tiene prioridad (contrato
        # común de `SearchProviderPlugin`).
        self._max_results = int(self.config.params.get("max_results", 5))
        self._search = _BusquedaSimulada()
        self._initialized = True
        return True

    def shutdown(self) -> None:
        self._initialized = False

    def get_source_name(self) -> str:
        return "MockSearchAPI"


# Register on import
plugin_registry._register_plugin_class(MockSearchPlugin, __file__)
