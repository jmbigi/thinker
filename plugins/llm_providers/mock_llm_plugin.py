"""
Mock LLM Provider Plugin.

Wraps the existing MockLLM (llm_providers.py) for plugin system compatibility.
"""

import time
from typing import List

from plugins.interfaces import LLMProviderPlugin, PluginMetadata, PluginType
from plugins.registry import plugin_registry


class MockLLMPlugin(LLMProviderPlugin):
    """Mock LLM provider as a plugin (offline, deterministic)."""

    def _get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="mock_llm",
            version="1.0.0",
            plugin_type=PluginType.LLM_PROVIDER,
            description="Deterministic offline LLM for testing and demos",
            author="Deep Research System",
            dependencies=[],
            config_schema={},
        )

    def initialize(self) -> bool:
        # Delega en MockLLM: una sola implementación de la heurística de
        # prompts, sin duplicarla en el plugin (P1.5).
        from llm_providers import MockLLM
        self._mock = MockLLM()
        self._initialized = True
        return True

    def shutdown(self) -> None:
        self._initialized = False

    def generate(self, prompt: str, model: str = None, **kwargs) -> str:
        if not self._initialized:
            raise RuntimeError("Plugin not initialized")
        self.metadata.usage_count += 1
        self.metadata.last_used = time.time()
        return self._mock.generate(prompt, model=model, **kwargs)

    def get_available_models(self) -> List[str]:
        return ["mock-llm"]

    def estimate_cost(self, prompt: str, model: str = None) -> float:
        return 0.0


# Register on import
plugin_registry._register_plugin_class(MockLLMPlugin, __file__)
