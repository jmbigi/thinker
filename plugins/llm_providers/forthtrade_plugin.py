"""Plugin para Free AI Gateway (ia.forthtrade.com), OpenAI-compatible.

Requiere API key del gateway (`FT_AI_API_KEY` u otros aceptados por el gateway).
No usar claves upstream. `auto` usa fallback/caché/FREE_ONLY del gateway;
gratis/controlado ≠ ilimitado (cuotas, rate limits, capacidad).
"""

import time
from typing import List

from plugins.interfaces import LLMProviderPlugin, PluginMetadata, PluginType
from plugins.registry import plugin_registry


class ForthtradeGatewayPlugin(LLMProviderPlugin):
    """Free AI Gateway (forthtrade) como proveedor LLM opt-in."""

    def _get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="forthtrade",
            version="1.0.0",
            plugin_type=PluginType.LLM_PROVIDER,
            description=(
                "Free AI Gateway OpenAI-compatible (ia.forthtrade.com), "
                "modelo auto por defecto; requiere FT_AI_API_KEY del gateway"
            ),
            author="Deep Research System",
            dependencies=["openai"],
            config_schema={
                "type": "object",
                "properties": {
                    "model": {"type": "string", "default": "auto"},
                    "base_url": {
                        "type": "string",
                        "default": "https://ia.forthtrade.com/v1",
                    },
                    "max_retries": {"type": "integer", "default": 3},
                    "timeout": {"type": "number", "default": 60.0},
                    "use_cache": {"type": "boolean", "default": True},
                },
            },
        )

    def initialize(self) -> bool:
        try:
            from llm_providers import ForthtradeGatewayLLM

            self._llm = ForthtradeGatewayLLM(
                model=self.config.params.get("model", "auto"),
                base_url=self.config.params.get("base_url"),
                max_retries=int(self.config.params.get("max_retries", 3)),
                timeout=float(self.config.params.get("timeout", 60.0)),
                use_cache=bool(self.config.params.get("use_cache", True)),
            )
            self._initialized = True
            return True
        except Exception as exc:
            self.metadata.error_message = str(exc)
            return False

    def shutdown(self) -> None:
        self._initialized = False

    def generate(self, prompt: str, model: str = None, **kwargs) -> str:
        if not self._initialized:
            raise RuntimeError("Plugin forthtrade no inicializado")
        self.metadata.usage_count += 1
        self.metadata.last_used = time.time()
        return self._llm.generate(prompt, model=model, **kwargs)

    def get_available_models(self) -> List[str]:
        return ["auto"]

    def estimate_cost(self, prompt: str, model: str = None) -> float:
        # El gateway aplica política FREE_ONLY/cuotas; coste monetario directo
        # para el cliente no se infiere aquí.
        return 0.0


plugin_registry._register_plugin_class(ForthtradeGatewayPlugin, __file__)
