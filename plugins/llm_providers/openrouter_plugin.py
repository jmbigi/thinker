"""
OpenRouter LLM Provider Plugin.

Wraps the existing OpenRouterLLM for plugin system compatibility.
"""

import time
from typing import List

from plugins.interfaces import LLMProviderPlugin, PluginMetadata, PluginType
from plugins.registry import plugin_registry


class OpenRouterPlugin(LLMProviderPlugin):
    """OpenRouter LLM provider as a plugin."""

    def _get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="openrouter",
            version="1.0.0",
            plugin_type=PluginType.LLM_PROVIDER,
            description="OpenRouter API provider with automatic fallback chain",
            author="Deep Research System",
            dependencies=["openai", "python-dotenv"],
            config_schema={
                "type": "object",
                "properties": {
                    "model": {"type": "string", "default": "poolside/laguna-xs-2.1:free"},
                    "use_fallback": {"type": "boolean", "default": True},
                    "max_retries": {"type": "integer", "default": 3},
                },
            },
        )

    def initialize(self) -> bool:
        try:
            from llm_providers import OpenRouterLLM
            model = self.config.params.get("model")
            use_fallback = self.config.params.get("use_fallback", True)
            max_retries = self.config.params.get("max_retries", 3)
            
            self._llm = OpenRouterLLM(
                model=model,
                use_fallback=use_fallback,
            )
            self._llm.max_retries = max_retries
            self._initialized = True
            return True
        except Exception as e:
            self.metadata.error_message = str(e)
            return False

    def shutdown(self) -> None:
        self._initialized = False

    def generate(self, prompt: str, model: str = None, **kwargs) -> str:
        if not self._initialized:
            raise RuntimeError("Plugin not initialized")
        self.metadata.usage_count += 1
        self.metadata.last_used = time.time()
        return self._llm.generate(prompt, model=model, **kwargs)

    def get_available_models(self) -> List[str]:
        # Return the fallback chain from OpenRouterLLM
        from llm_providers import OPENROUTER_FALLBACK_CHAIN
        return OPENROUTER_FALLBACK_CHAIN

    def estimate_cost(self, prompt: str, model: str = None) -> float:
        # OpenRouter free models have 0 cost
        return 0.0


# Register on import
plugin_registry._register_plugin_class(OpenRouterPlugin, __file__)