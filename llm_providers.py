#!/usr/bin/env python3
"""
Proveedores LLM del sistema (OpenAI, OpenRouter, Kilo, Ollama y Mock).

Separado de `deep_research_system` (que solo orquesta el pipeline) para
mantener la cohesión de módulos: aquí vive todo lo relacionado con hablar con
modelos. `MockLLM` es SIMULADO: offline, determinista, sin red.
"""

import json
import os
import random
import re
import sys
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List  # noqa: F401


# LLM Provider Interface
class LLMProvider(ABC):
    """Interface for LLM providers (Ollama, OpenAI, etc.)."""

    @abstractmethod
    def generate(self, prompt: str, model: str = "llama3.2") -> str:
        pass


# Errores transitorios de proveedor que justifican reintento (P1.34)
TRANSIENT_STATUS = {429, 500, 502, 503, 504}


def _chat_completion(client, model: str, prompt: str, max_retries: int, label: str) -> str:
    """Llama al endpoint de chat con reintentos y backoff exponencial + jitter.

    Reintenta solo errores transitorios (5xx, 429, red/timeout), informando
    cada reintento por stderr. Al agotar los intentos eleva el último error
    (fallo ruidoso, nunca silencioso). P1.34/P1.19.
    """
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content or ""
        except Exception as exc:  # noqa: BLE001 - se reeleva tras agotar
            last_error = exc
            status = getattr(exc, "status_code", None)
            transient = status is None or status in TRANSIENT_STATUS
            if attempt >= max_retries or not transient:
                raise
            delay = (2 ** attempt) + random.uniform(0, 1)
            print(f"[{label}] error transitorio ({status or type(exc).__name__}); "
                  f"reintento {attempt}/{max_retries - 1} en {delay:.1f}s",
                  file=sys.stderr)
            time.sleep(delay)
    raise last_error


# OpenAI-compatible implementation (openai>=1.0 SDK)
class OpenAILLM(LLMProvider):
    """Cliente para la API de OpenAI o cualquier endpoint compatible.

    La API key se toma del argumento `api_key`, de kwargs en `generate()`,
    o de las variables de entorno OPENAI_API_KEY / OPENROUTER_API_KEY.
    """

    def __init__(self, api_key: str = None, model: str = "gpt-4o-mini",
                 base_url: str = None, max_retries: int = 3):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model
        self.base_url = base_url
        self.max_retries = max_retries

    def generate(self, prompt: str, model: str = None, **kwargs) -> str:
        key = kwargs.pop("api_key", None) or self.api_key
        base_url = kwargs.pop("base_url", None) or self.base_url
        if not key:
            raise ValueError(
                "OpenAI API key required. Provide api_key or set OPENAI_API_KEY."
            )
        from openai import OpenAI
        client = OpenAI(api_key=key, base_url=base_url)
        return _chat_completion(client, model or self.model, prompt,
                                self.max_retries, "OpenAILLM")


# OpenRouter implementation (endpoint compatible con OpenAI)
# Modelo gratuito por defecto: el más rápido medido (1,58 s) en el benchmark
# real (Hallazgo 42). Se sobreescribe con la variable OPENROUTER_MODEL.
DEFAULT_FREE_MODEL = "poolside/laguna-xs-2.1:free"

# Lista de fallback ordenada por velocidad (benchmark 2026-10-15).
# Se recorre en orden hasta que uno responde (fallo ruidoso tras agotar).
OPENROUTER_FALLBACK_CHAIN = [
    "poolside/laguna-xs-2.1:free",                    # 1.58s — Small, más rápido
    "cohere/north-mini-code:free",                    # 1.64s — Small, código
    "nvidia/nemotron-3-ultra-550b-a55b:free",        # 1.65s — Frontier, potente
    "liquid/lfm-2.5-2.6b:free",                       # 2.27s — Small
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",  # 2.93s — Mid-size, reasoning
    "google/gemma-4-26b-a4b-it:free",                 # 4.24s — Mid-size
    "nvidia/nemotron-3.5-lightning:free",             # 5.04s — Mid-size
    "poolside/laguna-s-2.1:free",                     # 5.77s — Small
    "nvidia/nemotron-3-super-120b-a12b:free",         # 10.97s — Frontier (original)
]


class OpenRouterLLM(OpenAILLM):
    """Cliente para OpenRouter (https://openrouter.ai/api/v1).

    Usa OPENROUTER_API_KEY del entorno si no se pasa `api_key`.
    Modelo por defecto: OPENROUTER_MODEL si está definido, si no un modelo
    GRATUITO (`:free`, coste 0). Modelos con formato "proveedor/modelo".

    Incluye FALLBACK AUTOMÁTICO: si el modelo principal falla con error
    no transitorio (403, 404, 401, etc.), prueba el siguiente en la cadena
    OPENROUTER_FALLBACK_CHAIN hasta agotar opciones (fallo ruidoso).
    """

    def __init__(self, api_key: str = None, model: str = None,
                 base_url: str = "https://openrouter.ai/api/v1",
                 use_fallback: bool = True):
        self._fallback_chain = OPENROUTER_FALLBACK_CHAIN
        self._use_fallback = use_fallback
        self._current_model_index = 0
        
        # Modelo inicial: variable de entorno > parámetro > defecto
        initial_model = model or os.environ.get("OPENROUTER_MODEL", DEFAULT_FREE_MODEL)
        
        super().__init__(
            api_key=api_key or os.environ.get("OPENROUTER_API_KEY", ""),
            model=initial_model,
            base_url=base_url,
        )

    def generate(self, prompt: str, model: str = None, **kwargs) -> str:
        # Si se pasa modelo explícito, usarlo sin fallback (compatibilidad)
        if model is not None:
            return super().generate(prompt, model=model, **kwargs)
        
        if not self._use_fallback:
            return super().generate(prompt, model=self.model, **kwargs)

        # Cadena de fallback: modelo actual + resto de la cadena
        modelos_a_probar = [self.model] + [m for m in self._fallback_chain if m != self.model]
        
        last_error = None
        for i, modelo in enumerate(modelos_a_probar):
            try:
                if i > 0:
                    print(f"[OpenRouterLLM] Fallback a modelo: {modelo}", file=sys.stderr)
                return super().generate(prompt, model=modelo, **kwargs)
            except Exception as exc:
                last_error = exc
                status = getattr(exc, "status_code", None)
                # Fallback también en 429 tras agotar reintentos (rate limit del modelo gratis)
                # y en errores no transitorios (403, 404, 401, etc.)
                if status and (status == 429 or status not in {429, 500, 502, 503, 504}):
                    print(f"[OpenRouterLLM] Modelo {modelo} falló con {status}, probando siguiente...", file=sys.stderr)
                    continue  # Probar siguiente modelo
                else:
                    # Error de red/timeout (sin status) o 5xx tras reintentos: elevar
                    raise
        
        # Agotados todos los modelos
        raise last_error


# Ollama implementation (local)
class OllamaLLM(LLMProvider):
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.2"):
        self.base_url = base_url
        self.model = model

    def generate(self, prompt: str, model: str = None, **kwargs) -> str:
        import requests
        url = f"{self.base_url}/api/generate"
        payload = {"model": model or self.model, "prompt": prompt, "stream": False}
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        return response.json().get("response", "")


# Kilo AI Gateway implementation (unified API with BYOK)
class KiloGatewayLLM(LLMProvider):
    """Conecta al Kilo AI Gateway para acceder a cientos de modelos con una sola key.

    Base URL: https://api.kilo.ai/api/gateway
    Características:
    - BYOK (Bring Your Own Key): usa tu propia API key de proveedores
    - Acceso a cientos de modelos (Anthropic, OpenAI, Google, Mistral, etc.)
    - API compatible con OpenAI: mismo formato de petición
    - Tracking de uso y costos
    """

    def __init__(self, api_key: str = None, model: str = None,
                 base_url: str = "https://api.kilo.ai/api/gateway",
                 max_retries: int = 3):
        self.api_key = api_key or os.environ.get("KILO_API_KEY", "")
        self.model = model or "anthropic/claude-sonnet-4"
        self.base_url = base_url
        self.max_retries = max_retries

    def generate(self, prompt: str, model: str = None, **kwargs) -> str:
        key = kwargs.pop("api_key", None) or self.api_key
        if not key:
            raise ValueError(
                "Kilo API key required for KiloGatewayLLM. "
                "Provide api_key parameter or set KILO_API_KEY environment variable."
            )
        from openai import OpenAI
        client = OpenAI(api_key=key, base_url=self.base_url)
        return _chat_completion(client, model or self.model, prompt,
                                self.max_retries, "KiloGatewayLLM")


# DeepSeek implementation (OpenAI-compatible API)
class DeepSeekLLM(OpenAILLM):
    """Cliente para DeepSeek API (https://api.deepseek.com).

    Compatible con OpenAI SDK. Usa DEEPSEEK_API_KEY del entorno si no se pasa `api_key`.
    Modelos principales: deepseek-chat, deepseek-coder, deepseek-reasoner.
    """

    def __init__(self, api_key: str = None, model: str = "deepseek-chat",
                 base_url: str = "https://api.deepseek.com/v1",
                 max_retries: int = 3):
        super().__init__(
            api_key=api_key or os.environ.get("DEEPSEEK_API_KEY", ""),
            model=model,
            base_url=base_url,
            max_retries=max_retries,
        )


# Mock LLM for offline demos and tests
class MockLLM(LLMProvider):
    """LLM determinista y offline para demos y tests.

    SIMULADO: no realiza llamadas de red ni usa un modelo real. Devuelve
    respuestas fijas según el tipo de prompt recibido, con el formato que
    cada componente espera (JSON para extractores/evaluadores, texto para
    descomposición e informes).
    """

    def __init__(self, model: str = "mock-llm"):
        self.model = model

    def generate(self, prompt: str, model: str = None, **kwargs) -> str:
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


