"""Plugin para Olla proxy — unifica Ollama, vLLM, llama.cpp, LM Studio.

Olla es un proxy y balanceador de carga para backends LLM locales, escrito en
Go y con licencia Apache 2.0 (https://github.com/thushan/olla). Ofrece
enrutamiento, failover, catálogo unificado y health checks.

Rutas reales de Olla (v0.0.x):
- salud:    GET  {base}/internal/health
- modelos:  GET  {base}/olla/proxy/v1/models
- chat:     POST {base}/olla/proxy/v1/chat/completions

No se debe confundir con el puerto 11435 (proxy de contexto de este repo) ni
con el 9527 (deepseek-free-agent).
"""

import sys
import time
from typing import List

import requests

from plugins.interfaces import LLMProviderPlugin, PluginMetadata, PluginType
from plugins.registry import plugin_registry


class OllaPlugin(LLMProviderPlugin):
    """Olla LLM provider plugin — proxy unificado para backends locales."""

    def _get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="olla",
            version="1.0.0",
            plugin_type=PluginType.LLM_PROVIDER,
            description=(
                "Olla proxy: routing inteligente, failover automático, "
                "catálogo unificado de modelos (Ollama, vLLM, llama.cpp, LM Studio)"
            ),
            author="Deep Research System",
            dependencies=["openai", "requests"],
            config_schema={
                "type": "object",
                "properties": {
                    "base_url": {
                        "type": "string",
                        "default": "http://localhost:40114",
                        "description": "URL base del proxy Olla (puerto por defecto 40114)"
                    },
                    "model": {
                        "type": "string",
                        "default": "",
                        "description": "Modelo por defecto (vacío = usar el configurado en Olla)"
                    },
                    "timeout": {
                        "type": "number",
                        "default": 120.0,
                        "description": "Timeout por petición en segundos"
                    },
                    "max_retries": {
                        "type": "integer",
                        "default": 3,
                        "description": "Reintentos ante errores transitorios"
                    },
                    "use_cache": {
                        "type": "boolean",
                        "default": True,
                        "description": "Activar caché de respuestas por (modelo, prompt)"
                    },
                    "health_check_interval": {
                        "type": "integer",
                        "default": 30,
                        "description": "Intervalo de health checks en segundos (0 = desactivado)"
                    },
                },
            },
        )

    def initialize(self) -> bool:
        try:
            from llm_providers import OpenAILLM

            self._base_url = str(
                self.config.params.get("base_url", "http://localhost:40114")
            ).rstrip("/")
            model = self.config.params.get("model", "")
            timeout = float(self.config.params.get("timeout", 120.0))
            max_retries = int(self.config.params.get("max_retries", 3))
            use_cache = bool(self.config.params.get("use_cache", True))
            self._health_check_interval = int(
                self.config.params.get("health_check_interval", 30))

            health_url = self._base_url + "/internal/health"
            resp = requests.get(health_url, timeout=5)
            if resp.status_code != 200:
                self.metadata.error_message = (
                    f"Olla health check falló: HTTP {resp.status_code} en {health_url}"
                )
                return False

            self._available_models = []
            self._last_models_refresh = 0.0
            self._refresh_models()

            modelo = model or (self._available_models[0]
                               if self._available_models else "")
            if not modelo:
                self.metadata.error_message = (
                    "Olla no anuncia modelos y no se configuró 'model'")
                return False

            self._llm = OpenAILLM(
                api_key="olla-local",  # Olla no requiere auth por defecto
                model=modelo,
                base_url=self._base_url + "/olla/proxy/v1",
                max_retries=max_retries,
                timeout=timeout,
                use_cache=use_cache,
            )
            self._initialized = True
            return True
        except Exception as exc:
            self.metadata.error_message = str(exc)
            return False

    def _refresh_models(self) -> None:
        """Actualiza el catálogo; un fallo se reporta, no se silencia."""
        try:
            resp = requests.get(
                self._base_url + "/olla/proxy/v1/models", timeout=3)
            if resp.status_code == 200:
                self._available_models = [
                    m.get("id", "") for m in resp.json().get("data", [])
                    if m.get("id")
                ]
                self._last_models_refresh = time.time()
            else:
                print(f"[OllaPlugin] /models respondió HTTP {resp.status_code}",
                      file=sys.stderr)
        except Exception as exc:  # noqa: BLE001 - se reporta y se conserva la caché
            print(f"[OllaPlugin] no se pudo refrescar modelos: {exc}",
                  file=sys.stderr)

    def shutdown(self) -> None:
        self._initialized = False

    def generate(self, prompt: str, model: str = None, **kwargs) -> str:
        if not self._initialized:
            raise RuntimeError("Plugin Olla no inicializado")
        self.metadata.usage_count += 1
        self.metadata.last_used = time.time()
        return self._llm.generate(prompt, model=model, **kwargs)

    def get_available_models(self) -> List[str]:
        if not self._initialized:
            return []
        if (self._health_check_interval > 0
                and time.time() - self._last_models_refresh
                >= self._health_check_interval):
            self._refresh_models()
        return list(self._available_models)

    def estimate_cost(self, prompt: str, model: str = None) -> float:
        # Olla proxy a backends locales = coste 0
        return 0.0


# Register on import
plugin_registry._register_plugin_class(OllaPlugin, __file__)