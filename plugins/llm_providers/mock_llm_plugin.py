"""
Mock LLM Provider Plugin.

Provides deterministic offline responses for testing and demos.
"""

import json
import re
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
        self._initialized = True
        return True

    def shutdown(self) -> None:
        self._initialized = False

    def generate(self, prompt: str, model: str = None, **kwargs) -> str:
        if not self._initialized:
            raise RuntimeError("Plugin not initialized")
        self.metadata.usage_count += 1
        self.metadata.last_used = time.time()
        p = prompt.lower()

        if "decompose this into" in p:
            return "\n".join([
                "¿Cuáles son los avances recientes documentados sobre el tema?",
                "¿Qué fuentes primarias describen el estado actual?",
                "¿Qué limitaciones, riesgos e incertidumbres se reportan?",
            ])

        if "extract factual claims" in p:
            return json.dumps([{
                "claim": "Afirmación simulada extraída del snippet por MockLLM",
                "confidence": 0.7,
                "source_url": "https://example.com/mock-source",
            }], ensure_ascii=False)

        if "evaluate this claim" in p:
            return json.dumps({
                "verdict": "supported",
                "credibility": 0.75,
                "confidence": 0.7,
                "reasoning": "Evaluación simulada por MockLLM (offline, sin modelo real)",
            }, ensure_ascii=False)

        if "generate a comprehensive research report" in p:
            return (
                "# Informe de investigación (SIMULADO por MockLLM)\n\n"
                "## Resumen ejecutivo\n\n"
                "Este informe fue generado offline por MockLLM, sin modelo real ni "
                "llamadas de red. Sirve para verificar que el pipeline completo "
                "(descomposición, recuperación, extracción, evaluación y reporte) "
                "funciona de extremo a extremo.\n\n"
                "## Hallazgos\n\n"
                "Los hallazgos reales requieren configurar un proveedor LLM "
                "(OpenAILLM, OpenRouterLLM, KiloGatewayLLM u OllamaLLM).\n\n"
                "## Conclusiones\n\n"
                "Pipeline verificado. Sustituir MockLLM por un proveedor real "
                "para obtener contenido genuino.\n"
            )

        paso = re.search(r"paso (\d)", p)
        if paso:
            n = paso.group(1)
            return json.dumps({
                "paso": int(n),
                "contenido": f"Respuesta simulada por MockLLM para el paso {n}",
                "confianza": 0.7,
                "nota": "Salida offline determinista, sin modelo real",
            }, ensure_ascii=False)

        return ("Respuesta simulada por MockLLM (offline): "
                "el prompt no corresponde a un patrón conocido.")

    def get_available_models(self) -> List[str]:
        return ["mock-llm"]

    def estimate_cost(self, prompt: str, model: str = None) -> float:
        return 0.0


# Register on import
plugin_registry._register_plugin_class(MockLLMPlugin, __file__)