"""
Wikipedia Search Provider Plugin.

Wraps the existing WikipediaSearchAPI for plugin system compatibility.
"""

import time
from typing import Any, Dict, List

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
                    "language": {"type": "string", "default": "en"},
                    "max_results": {"type": "integer", "default": 5},
                    "timeout": {"type": "integer", "default": 10},
                },
            },
        )

    def initialize(self) -> bool:
        try:
            from web_search import WikipediaSearchAPI
            language = self.config.params.get("language", "en")
            timeout = self.config.params.get("timeout", 10)
            self._search = WikipediaSearchAPI(language=language, timeout=timeout)
            self._initialized = True
            return True
        except Exception as e:
            self.metadata.error_message = str(e)
            return False

    def shutdown(self) -> None:
        self._initialized = False

    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        if not self._initialized:
            raise RuntimeError("Plugin not initialized")
        self.metadata.usage_count += 1
        self.metadata.last_used = time.time()
        return self._search.search(query, max_results)

    def get_source_name(self) -> str:
        return "Wikipedia"


# Register on import
plugin_registry._register_plugin_class(WikipediaSearchPlugin, __file__)