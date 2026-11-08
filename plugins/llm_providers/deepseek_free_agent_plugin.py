"""Plugin opt-in para el servicio local deepseek-free-agent."""

import time
from typing import List

from plugins.interfaces import LLMProviderPlugin, PluginMetadata, PluginType
from plugins.registry import plugin_registry


class DeepSeekFreeAgentPlugin(LLMProviderPlugin):
    def _get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="deepseek_free_agent",
            version="1.0.0",
            plugin_type=PluginType.LLM_PROVIDER,
            description=(
                "deepseek-free-agent por HTTP loopback; reenvía prompts a DeepSeek web"
            ),
            author="Deep Research System",
            dependencies=["requests"],
            config_schema={
                "type": "object",
                "properties": {
                    "base_url": {"type": "string", "default": "http://127.0.0.1:9527"},
                    "timeout": {"type": "number", "default": 300.0},
                    "authorized": {"type": "boolean", "default": False},
                },
            },
        )

    def initialize(self) -> bool:
        try:
            from llm_providers import DeepSeekFreeAgentLLM
            authorized = self.config.params.get("authorized", False) is True
            if not authorized:
                # Fail-closed: sin autorización explícita el plugin no queda
                # activo, aunque el servicio local esté disponible.
                self.metadata.error_message = (
                    "deepseek-free-agent requiere authorized: true explícito; "
                    "reenvía prompts a chat.deepseek.com")
                return False
            self._llm = DeepSeekFreeAgentLLM(
                base_url=self.config.params.get("base_url", "http://127.0.0.1:9527"),
                timeout=self.config.params.get("timeout", 300.0),
                authorized=True,
            )
            self._initialized = True
            return True
        except Exception as exc:
            self.metadata.error_message = str(exc)
            return False

    def generate(self, prompt: str, model: str = None, **kwargs) -> str:
        if not self._initialized:
            raise RuntimeError("Plugin not initialized")
        self.metadata.usage_count += 1
        self.metadata.last_used = time.time()
        return self._llm.generate(prompt, model=model, **kwargs)

    def get_available_models(self) -> List[str]:
        return ["deepseek-free-agent"]

    def estimate_cost(self, prompt: str, model: str = None) -> float:
        return 0.0


plugin_registry._register_plugin_class(DeepSeekFreeAgentPlugin, __file__)
