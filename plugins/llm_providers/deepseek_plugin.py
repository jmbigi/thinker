"""
DeepSeek LLM Provider Plugin.

Wraps the existing DeepSeekLLM for plugin system compatibility.
"""

import time
from typing import List

from plugins.interfaces import LLMProviderPlugin, PluginMetadata, PluginType
from plugins.registry import plugin_registry


class DeepSeekPlugin(LLMProviderPlugin):
    """DeepSeek API provider as a plugin."""

    def _get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="deepseek",
            version="1.0.0",
            plugin_type=PluginType.LLM_PROVIDER,
            description="DeepSeek API provider (deepseek-chat, deepseek-coder, deepseek-reasoner)",
            author="Deep Research System",
            dependencies=["openai", "python-dotenv"],
            config_schema={
                "type": "object",
                "properties": {
                    "model": {"type": "string", "default": "deepseek-chat"},
                    "max_retries": {"type": "integer", "default": 3},
                    "base_url": {"type": "string", "default": "https://api.deepseek.com/v1"},
                },
            },
        )

    def initialize(self) -> bool:
        try:
            from llm_providers import DeepSeekLLM
            model = self.config.params.get("model", "deepseek-chat")
            max_retries = self.config.params.get("max_retries", 3)
            base_url = self.config.params.get("base_url", "https://api.deepseek.com/v1")
            
            self._llm = DeepSeekLLM(
                model=model,
                max_retries=max_retries,
                base_url=base_url,
            )
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
        return ["deepseek-chat", "deepseek-coder", "deepseek-reasoner"]

    def estimate_cost(self, prompt: str, model: str = None) -> float:
        # DeepSeek pricing: ~$0.14/1M input, $0.28/1M output tokens
        # Rough estimate: 4 chars per token
        tokens = len(prompt) / 4
        return (tokens / 1_000_000) * 0.14


# Register on import
plugin_registry._register_plugin_class(DeepSeekPlugin, __file__)