"""
Mock Search Provider Plugin.

Provides deterministic offline search results for testing and demos.
"""

import time
from typing import Any, Dict, List

from plugins.interfaces import SearchProviderPlugin, PluginMetadata, PluginType
from plugins.registry import plugin_registry


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
            config_schema={},
        )

    def initialize(self) -> bool:
        self._initialized = True
        return True

    def shutdown(self) -> None:
        self._initialized = False

    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        if not self._initialized:
            raise RuntimeError("Plugin not initialized")
        self.metadata.usage_count += 1
        self.metadata.last_used = time.time()
        
        # Return deterministic mock results
        results = []
        for i in range(min(max_results, 3)):
            results.append({
                "title": f"Mock Result {i+1} for: {query[:50]}",
                "url": f"https://example.com/mock-result-{i+1}",
                "snippet": f"This is a simulated search result for query: {query}. "
                           f"Result number {i+1} contains relevant information about the topic.",
                "source": "MockSearchAPI",
            })
        return results

    def get_source_name(self) -> str:
        return "MockSearchAPI"


# Register on import
plugin_registry._register_plugin_class(MockSearchPlugin, __file__)