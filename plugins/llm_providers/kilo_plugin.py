"""Plugin de Kilo AI Gateway (modelos gratuitos con acceso anónimo).

- `cohere/north-mini-code:free` y los IDs `:free` no requieren API key (Kilo limita el
  acceso anónimo a 200 peticiones/hora por IP).
- Con `KILO_API_KEY` se puede usar cualquier modelo del catálogo.
- Es un servicio remoto: no es privado ni ilimitado.
"""

import time
from typing import List

from plugins.interfaces import LLMProviderPlugin, PluginMetadata, PluginType
from plugins.registry import plugin_registry


class KiloPlugin(LLMProviderPlugin):
    """Kilo Gateway como proveedor LLM opt-in."""

    def _get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="kilo",
            version="1.0.0",
            plugin_type=PluginType.LLM_PROVIDER,
            description=(
                "Kilo AI Gateway: modelos gratuitos anónimos o catálogo "
                "completo con KILO_API_KEY; servicio remoto"
            ),
            author="Deep Research System",
            dependencies=["openai"],
            config_schema={
                "type": "object",
                "properties": {
                    "model": {"type": "string", "default": "cohere/north-mini-code:free"},
                    "base_url": {
                        "type": "string",
                        "default": "https://ai-gateway.kilo.ai/api/v1",
                    },
                    "max_retries": {"type": "integer", "default": 3},
                    "timeout": {"type": "number", "default": 60.0},
                    "use_cache": {"type": "boolean", "default": True},
                },
            },
        )

    def initialize(self) -> bool:
        try:
            from llm_providers import KiloGatewayLLM

            self._llm = KiloGatewayLLM(
                model=self.config.params.get("model", "cohere/north-mini-code:free"),
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
            raise RuntimeError("Plugin Kilo no inicializado")
        self.metadata.usage_count += 1
        self.metadata.last_used = time.time()
        return self._llm.generate(prompt, model=model, **kwargs)

    def get_available_models(self) -> List[str]:
        return ["cohere/north-mini-code:free"]

    def estimate_cost(self, prompt: str, model: str = None) -> float:
        # Solo es exacto para los modelos gratuitos; con una key y un modelo
        # de pago, Kilo factura según su catálogo.
        modelo = model or self.config.params.get("model", "cohere/north-mini-code:free")
        return 0.0 if "free" in modelo.lower() else float("nan")


plugin_registry._register_plugin_class(KiloPlugin, __file__)
