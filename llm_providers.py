#!/usr/bin/env python3
"""
Proveedores LLM del sistema (OpenAI, OpenRouter, Kilo, DeepSeek,
deepseek-free-agent, Ollama y Mock).

Separado de `deep_research_system` (que solo orquesta el pipeline) para
mantener la cohesión de módulos: aquí vive todo lo relacionado con hablar con
modelos. `MockLLM` es SIMULADO: offline, determinista, sin red.
"""

import hashlib
import ipaddress
import json
import math
import os
import random
import re
import sys
import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional  # noqa: F401
from urllib.parse import urlparse


# LLM Provider Interface
class LLMProvider(ABC):
    """Interface for LLM providers (Ollama, OpenAI, etc.)."""

    @abstractmethod
    def generate(self, prompt: str, model: str = "llama3.2") -> str:
        pass  # pragma: no cover - cuerpo abstracto, nunca se ejecuta


# Errores transitorios de proveedor que justifican reintento (P1.34)
TRANSIENT_STATUS = {429, 500, 502, 503, 504}

# Timeout explícito por petición (P1.34): el SDK usa 600 s por defecto, que en
# una campaña real es tiempo perdido (una llamada colgada bloquea el pipeline).
DEFAULT_TIMEOUT = 60.0


class ResponseCache:
    """Caché de respuestas por (modelo, prompt), en memoria y por instancia.

    - Solo guarda respuestas EXITOSAS: un error no se cachea (un reintento debe
      volver a la red).
    - Es por cliente: una instancia nueva empieza vacía, así los tests siguen
      siendo deterministas y el efecto se limita a la vida del cliente.
    - `hits`/`entradas` hacen medible el ahorro (eficiencia medida, no supuesta).
    """

    def __init__(self) -> None:
        self.entradas: Dict[str, str] = {}
        self.hits = 0

    @staticmethod
    def _clave(model: str, prompt: str) -> str:
        return hashlib.sha256(f"{model}\x00{prompt}".encode("utf-8")).hexdigest()

    def get(self, model: str, prompt: str) -> Optional[str]:
        respuesta = self.entradas.get(self._clave(model, prompt))
        if respuesta is not None:
            self.hits += 1
        return respuesta

    def set(self, model: str, prompt: str, respuesta: str) -> None:
        self.entradas[self._clave(model, prompt)] = respuesta


def _chat_completion(client, model: str, prompt: str, max_retries: int, label: str,
                     timeout: float = DEFAULT_TIMEOUT,
                     cache: Optional["ResponseCache"] = None) -> str:
    """Llama al endpoint de chat con reintentos, backoff y timeout explícito.

    Reintenta solo errores transitorios (5xx, 429, red/timeout), informando
    cada reintento por stderr. Al agotar los intentos eleva el último error
    (fallo ruidoso, nunca silencioso). P1.34/P1.19.

    Con `cache` (por instancia de cliente), un (modelo, prompt) ya respondido
    con éxito se devuelve sin tocar la red; los errores NO se cachean.
    """
    if max_retries < 1:
        raise ValueError(f"max_retries debe ser >= 1 (recibido {max_retries})")

    if cache is not None:
        guardada = cache.get(model, prompt)
        if guardada is not None:
            return guardada

    for attempt in range(1, max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                timeout=timeout,
            )
            salida = response.choices[0].message.content or ""
            if cache is not None:
                cache.set(model, prompt, salida)
            return salida
        except Exception as exc:  # noqa: BLE001 - se reeleva tras agotar
            status = getattr(exc, "status_code", None)
            transient = status is None or status in TRANSIENT_STATUS
            if attempt >= max_retries or not transient:
                raise
            delay = (2 ** attempt) + random.uniform(0, 1)
            print(f"[{label}] error transitorio ({status or type(exc).__name__}); "
                  f"reintento {attempt}/{max_retries - 1} en {delay:.1f}s",
                  file=sys.stderr)
            time.sleep(delay)


def _cliente_openai(cache_clientes: Dict[Any, Any], key: str,
                    base_url: Optional[str]):
    """Cliente del SDK reutilizado por (clave, base_url).

    Antes se creaba un `OpenAI(...)` por llamada: eso tiraba el pool de
    conexiones keep-alive en cada petición.
    """
    clave = (key, base_url)
    cliente = cache_clientes.get(clave)
    if cliente is None:
        from openai import OpenAI
        cliente = OpenAI(api_key=key, base_url=base_url)
        cache_clientes[clave] = cliente
    return cliente


# OpenAI-compatible implementation (openai>=1.0 SDK)
class OpenAILLM(LLMProvider):
    """Cliente para la API de OpenAI o cualquier endpoint compatible.

    La API key se toma del argumento `api_key`, de kwargs en `generate()`,
    o de las variables de entorno OPENAI_API_KEY / OPENROUTER_API_KEY.

    `timeout` es explícito (por defecto 60 s; el SDK usa 600 s) y `use_cache`
    activa la caché de respuestas por instancia (medible con `self.cache.hits`).
    """

    def __init__(self, api_key: str = None, model: str = "gpt-4o-mini",
                 base_url: str = None, max_retries: int = 3,
                 timeout: float = DEFAULT_TIMEOUT, use_cache: bool = True):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model
        self.base_url = base_url
        self.max_retries = max_retries
        self.timeout = timeout
        self.use_cache = use_cache
        self.cache: Optional[ResponseCache] = ResponseCache() if use_cache else None
        self._clientes: Dict[Any, Any] = {}

    def generate(self, prompt: str, model: str = None, **kwargs) -> str:
        key = kwargs.pop("api_key", None) or self.api_key
        base_url = kwargs.pop("base_url", None) or self.base_url
        if not key:
            raise ValueError(
                "OpenAI API key required. Provide api_key or set OPENAI_API_KEY."
            )
        client = _cliente_openai(self._clientes, key, base_url)
        return _chat_completion(client, model or self.model, prompt,
                                self.max_retries, "OpenAILLM",
                                timeout=self.timeout, cache=self.cache)


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
        
        # Modelo inicial: variable de entorno > parámetro > defecto
        initial_model = model or os.environ.get("OPENROUTER_MODEL", DEFAULT_FREE_MODEL)
        
        super().__init__(
            api_key=api_key or os.environ.get("OPENROUTER_API_KEY", ""),
            model=initial_model,
            base_url=base_url,
        )
        # Igual que en DeepSeekLLM: `OpenAILLM.__init__` cae a OPENAI_API_KEY si
        # la clave es vacía, y este cliente habla con OTRO proveedor
        # (openrouter.ai): no se debe enviar allí la clave de OpenAI.
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")

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
                salida = super().generate(prompt, model=modelo, **kwargs)
                if i > 0:
                    # Recordar el modelo que funcionó: las siguientes llamadas
                    # empiezan por él en vez de repetir la cascada de fallos
                    # (404/403 de modelos retirados son frecuentes).
                    self.model = modelo
                return salida
            except Exception as exc:
                last_error = exc
                status = getattr(exc, "status_code", None)
                if status == 401:
                    print("[OpenRouterLLM] 401: clave inválida; no se "
                          "prueban más modelos", file=sys.stderr)
                    raise
                if status == 429:
                    # La cuota gratuita suele ser por cuenta; probar otro
                    # modelo puede funcionar si el límite es por modelo.
                    print("[OpenRouterLLM] 429/cuota; esperando 2 s y "
                          "probando el siguiente modelo...", file=sys.stderr)
                    time.sleep(2)
                    continue
                if status is not None and status not in TRANSIENT_STATUS:
                    print(f"[OpenRouterLLM] Modelo {modelo} falló con "
                          f"{status}, probando siguiente...", file=sys.stderr)
                    continue
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
KILO_DEFAULT_FREE_MODEL = "cohere/north-mini-code:free"
KILO_DEFAULT_BASE_URL = "https://ai-gateway.kilo.ai/api/v1"


def _kilo_modelo_gratuito(model: str) -> bool:
    """True para los IDs gratuitos conocidos del catálogo de Kilo.

    Los modelos `:free` y los `kilo-auto/free` aceptan acceso anónimo (200
    peticiones/hora por IP según la documentación de Kilo). Los IDs `stealth/*`
    del catálogo son gratuitos y dinámicos.
    """
    m = (model or "").strip().lower()
    return (m.endswith(":free") or m in {
        KILO_DEFAULT_FREE_MODEL, "kilo-auto/free", "openrouter/free",
        "reflection/beam-free",
    } or m.startswith("stealth/"))


class KiloGatewayLLM(LLMProvider):
    """Kilo AI Gateway: cientos de modelos con una sola API compatible OpenAI.

    - Base URL documentada: https://ai-gateway.kilo.ai/api/v1
    - Acceso **anónimo** solo a modelos gratuitos (`:free`, `kilo-auto/free`),
      limitado por Kilo (200 peticiones/hora por IP); no es ilimitado.
    - Con `KILO_API_KEY` se puede usar cualquier modelo del catálogo.
    - BYOK: la clave del proveedor se configura en Kilo, no aquí.
    """

    def __init__(self, api_key: str = None, model: str = None,
                 base_url: str = None, max_retries: int = 3,
                 timeout: float = DEFAULT_TIMEOUT, use_cache: bool = True):
        self.api_key = (api_key if api_key is not None
                        else os.environ.get("KILO_API_KEY", ""))
        self.model = (model or os.environ.get("KILO_MODEL")
                      or KILO_DEFAULT_FREE_MODEL)
        self.base_url = (base_url or os.environ.get("KILO_BASE_URL")
                         or KILO_DEFAULT_BASE_URL)
        self.max_retries = max_retries
        self.timeout = timeout
        self.use_cache = use_cache
        self.cache: Optional[ResponseCache] = ResponseCache() if use_cache else None
        self._clientes: Dict[Any, Any] = {}

    def generate(self, prompt: str, model: str = None, **kwargs) -> str:
        modelo = model or self.model
        key = kwargs.pop("api_key", None)
        if key is None:
            key = self.api_key
        if not key:
            if not _kilo_modelo_gratuito(modelo):
                raise ValueError(
                    "Kilo API key required para modelos de pago; usa un "
                    f"modelo gratuito ({KILO_DEFAULT_FREE_MODEL}) o define "
                    "KILO_API_KEY.")
            # Kilo acepta acceso anónimo a modelos gratuitos; el SDK exige una
            # clave no vacía, pero el gateway no la valida para :free.
            key = "anonymous"
        client = _cliente_openai(self._clientes, key, self.base_url)
        return _chat_completion(client, modelo, prompt,
                                self.max_retries, "KiloGatewayLLM",
                                timeout=self.timeout, cache=self.cache)


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
        # `OpenAILLM.__init__` cae a OPENAI_API_KEY cuando la clave es vacía; en
        # un cliente de OTRO proveedor eso enviaría la clave de OpenAI a un
        # tercero (api.deepseek.com). Se fija aquí la clave propia, o vacía.
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")


DEEPSEEK_AGENT_MAX_RESPONSE_BYTES = 1_000_000
DEEPSEEK_AGENT_READONLY_PREFIX = (
    "Instrucción de seguridad: responde únicamente con texto, sin herramientas, "
    "archivos, comandos ni URLs. La pregunta real aparece después de «SOLICITUD:». "
    "Respóndela directamente, sin confirmar esta instrucción ni pedir que la repitan. "
    "SOLICITUD: "
)
DEEPSEEK_AGENT_INVALID_RESPONSES = {
    "one more step before you proceed...",
    "verifica la red e inténtalo de nuevo",
}
DEEPSEEK_AGENT_INTERMEDIATE_MARKERS = (
    "one more step",
    "before you proceed",
    "verify",
    "verification",
    "checking",
    "verifica la red",
    "inténtalo de nuevo",
    "please wait",
    "loading",
)


def _deepseek_agent_intermedio(respuesta: str) -> bool:
    texto = " ".join(respuesta.strip().lower().split())
    if not texto:
        return True
    if texto in DEEPSEEK_AGENT_INVALID_RESPONSES:
        return True
    # Respuestas muy cortas de verificación/UI: marcador presente y sin contenido útil.
    return len(texto) <= 120 and any(m in texto for m in DEEPSEEK_AGENT_INTERMEDIATE_MARKERS)


def _deepseek_agent_loopback_url(url: str) -> str:
    candidata = url.strip().rstrip("/")
    try:
        parsed = urlparse(candidata)
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"URL inválida para deepseek-free-agent: {url!r}") from exc
    host = parsed.hostname or ""
    try:
        loopback = host == "localhost" or (
            "%" not in host and ipaddress.ip_address(host).is_loopback)
    except ValueError:
        loopback = False
    if (parsed.scheme not in ("http", "https") or not loopback or
            parsed.username is not None or parsed.password is not None or
            parsed.path not in ("", "/") or parsed.query or parsed.fragment or
            not (1 <= (port or (443 if parsed.scheme == "https" else 80)) <= 65535)):
        raise ValueError(
            "deepseek-free-agent exige una URL HTTP(S) loopback sin credenciales, "
            "ruta, query ni fragmento (por ejemplo http://127.0.0.1:9527)")
    return candidata


class DeepSeekFreeAgentLLM(LLMProvider):
    """Adaptador de solo lectura para la API local de deepseek-free-agent.

    El servicio reenvía los prompts a chat.deepseek.com: no es un LLM local ni
    una garantía de disponibilidad ilimitada. Cada llamada abre un chat nuevo.
    """

    def __init__(self, base_url: str = None, model: str = "deepseek-free-agent",
                 timeout: float = 300.0, use_cache: bool = True,
                 authorized: bool = False):
        self.base_url = _deepseek_agent_loopback_url(
            base_url or os.environ.get("DEEPSEEK_AGENT_URL", "http://127.0.0.1:9527"))
        self.model = model
        self.timeout = float(timeout)
        if not math.isfinite(self.timeout) or self.timeout <= 0:
            raise ValueError("timeout de deepseek-free-agent debe ser un número > 0")
        self.use_cache = use_cache
        self.authorized = authorized is True
        self.cache: Optional[ResponseCache] = ResponseCache() if use_cache else None
        self._post = None

    def generate(self, prompt: str, model: str = None, **kwargs) -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt de deepseek-free-agent no puede estar vacío")
        if not self.authorized:
            raise PermissionError(
                "deepseek-free-agent requiere autorización explícita: revisa "
                "docs/DEEPSEEK-FREE-AGENT.md y usa authorized=True o "
                "--authorize-deepseek-agent")
        modelo = model or self.model
        if self.cache is not None:
            guardada = self.cache.get(modelo, prompt)
            if guardada is not None:
                return guardada

        import requests
        post = self._post or requests.post
        tarea = " ".join((DEEPSEEK_AGENT_READONLY_PREFIX + prompt).split())

        def _pedir(abrir_chat_nuevo: bool) -> str:
            response = post(
                f"{self.base_url}/task",
                json={"task": tarea, "newChat": abrir_chat_nuevo},
                timeout=(min(5.0, self.timeout), self.timeout),
                allow_redirects=False,
                stream=True,
            )
            try:
                if response.status_code != 200:
                    raise RuntimeError(
                        f"deepseek-free-agent respondió HTTP {response.status_code}; "
                        "comprueba el servicio local y la sesión de DeepSeek")
                contenido = bytearray()
                for chunk in response.iter_content(chunk_size=65536):
                    contenido.extend(chunk)
                    if len(contenido) > DEEPSEEK_AGENT_MAX_RESPONSE_BYTES:
                        raise RuntimeError(
                            "Respuesta de deepseek-free-agent demasiado grande")
                try:
                    resultado = json.loads(contenido.decode("utf-8"))
                except (UnicodeError, json.JSONDecodeError) as exc:
                    raise RuntimeError(
                        "Respuesta no JSON de deepseek-free-agent") from exc
                if not isinstance(resultado, dict) or resultado.get("status") != "success":
                    raise RuntimeError(
                        "deepseek-free-agent no completó la tarea correctamente")
                respuesta = resultado.get("answer")
                if not isinstance(respuesta, str) or not respuesta.strip():
                    raise RuntimeError(
                        "deepseek-free-agent devolvió una respuesta vacía")
                return respuesta
            finally:
                response.close()

        respuesta = _pedir(True)
        if _deepseek_agent_intermedio(respuesta):
            # El servicio bloqueante devolvió verificación/UI intermedia. Un
            # reintento acotado (misma tarea, sin chat nuevo) puede obtener la
            # respuesta real; nunca se hacen bucles ni reintentos ciegos.
            respuesta = _pedir(False)
        if _deepseek_agent_intermedio(respuesta):
            raise RuntimeError(
                "deepseek-free-agent devolvió una verificación o texto intermedio, "
                "no una respuesta válida del modelo")
        if self.cache is not None:
            self.cache.set(modelo, prompt, respuesta)
        return respuesta


class LocalFallbackLLM(LLMProvider):
    """Conmuta a un modelo local solo ante fallos operativos del proveedor principal."""

    def __init__(self, primary: LLMProvider, fallback: LLMProvider):
        self.primary = primary
        self.fallback = fallback
        self.model = primary.model
        self.base_url = getattr(primary, "base_url", None)
        self.fallback_calls = 0
        self.last_fallback_reason = ""

    def generate(self, prompt: str, model: str = None, **kwargs) -> str:
        try:
            return self.primary.generate(prompt, model=model, **kwargs)
        except (ValueError, PermissionError):
            raise
        except Exception as exc:  # noqa: BLE001 - fallback explícito y registrado
            self.last_fallback_reason = f"{type(exc).__name__}: {exc}"
            self.fallback_calls += 1
            print(f"[LocalFallbackLLM] {self.last_fallback_reason}; "
                  f"usando modelo local {self.fallback.model}", file=sys.stderr)
            return self.fallback.generate(prompt, model=self.fallback.model, **kwargs)


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

        if "evaluador experto" in p:
            return json.dumps({
                "relevance": 8, "depth": 8, "coherence": 8, "reasoning": 8,
                "brief_justification": "Evaluación simulada por MockLLM (offline)",
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


class BudgetLLM(LLMProvider):
    """Decorador con límite de llamadas compartido y seguro entre hilos."""

    def __init__(self, provider: LLMProvider, max_calls: int):
        if not isinstance(max_calls, int) or isinstance(max_calls, bool) or max_calls < 1:
            raise ValueError("max_calls debe ser un entero >= 1")
        import threading
        self.provider = provider
        self.max_calls = max_calls
        self.calls = 0
        self._lock = threading.Lock()

    def generate(self, prompt: str, model: str = None, **kwargs) -> str:
        with self._lock:
            if self.calls >= self.max_calls:
                raise RuntimeError(
                    f"Presupuesto de llamadas LLM agotado ({self.calls}/{self.max_calls})")
            self.calls += 1
        return self.provider.generate(prompt, model=model, **kwargs)


# =============================================================================
# Gate local de tool calls (fail-closed)
# =============================================================================
# `LocalToolGate` reimplementa en Python la POLÍTICA del plugin comunitario
# dsh-agent-gate (AGPL, para DeepSeek Harness): riesgo por herramienta, raíces
# permitidas, límite por minuto y auditoría JSONL. NO es ese plugin, no habla
# por HTTP y no usa el puerto 9527 (ese puerto pertenece a deepseek-free-agent).
# Sirve para agentes que ejecutan herramientas en Python: el agente DEBE llamar
# a `check()`/`gate_check()` ANTES de ejecutar la herramienta; sin esa llamada
# el gate no protege nada.
# =============================================================================


class LocalToolGate:
    """Política local fail-closed para tool calls de un agente.

    - Sin `allowed_roots`, toda herramienta con una ruta se deniega.
    - `run_shell`/`eval`/... están prohibidas; escritura exige confirmación
      humana explícita (callback) y, sin callback, se deniega.
    - Límite deslizante de llamadas por minuto y auditoría JSONL opcional.
    - No accede a la red ni depende de un servicio externo.
    """

    READ_ONLY_TOOLS = frozenset(
        {"read_file", "read", "list_dir", "list", "stat", "search"})
    FORBIDDEN_TOOLS = frozenset(
        {"run_shell", "shell", "execute", "exec", "eval", "subprocess",
         "system", "delete_file"})
    PATH_KEYS = frozenset(
        {"path", "file", "filename", "dir", "directory", "cwd", "target",
         "root", "source", "destination"})

    def __init__(self, allowed_roots=None, allow_tools=None, deny_tools=None,
                 max_calls_per_minute: int = 30, audit_path=None, confirm=None,
                 clock=time.monotonic):
        if allowed_roots is None:
            crudo = os.environ.get("DSH_AGENT_GATE_ROOTS", "")
            allowed_roots = [p for p in crudo.split(os.pathsep) if p] if crudo else []
        self.allowed_roots = tuple(
            Path(p).expanduser().resolve() for p in allowed_roots)
        self.allow_tools = frozenset(allow_tools or ())
        self.deny_tools = frozenset(deny_tools or ())
        self.max_calls_per_minute = int(max_calls_per_minute)
        self.audit_path = Path(audit_path).expanduser() if audit_path else None
        self.confirm = confirm
        self._clock = clock
        self._llamadas = deque()
        self._lock = threading.Lock()

    def _es_clave_de_ruta(self, clave: str) -> bool:
        k = clave.lower()
        if k in self.PATH_KEYS or k.endswith(("_path", "_file", "_dir", "_directory")):
            return True
        # Claves compuestas en español/inglés: `ruta_hija`, `archivo_origen`,
        # `source_dir`... El gate no adivina el significado de la herramienta,
        # pero sí reconoce nombres que declaran una ruta.
        return any(pista in k for pista in
                   ("path", "file", "dir", "ruta", "archivo", "directorio"))

    def _iter_paths(self, valor, clave: str = ""):
        if isinstance(valor, dict):
            for nombre, hijo in valor.items():
                yield from self._iter_paths(hijo, str(nombre))
        elif isinstance(valor, (list, tuple)):
            for hijo in valor:
                yield from self._iter_paths(hijo, clave)
        elif isinstance(valor, str) and self._es_clave_de_ruta(clave):
            yield clave, valor

    def _violacion_de_ruta(self, args: Dict[str, Any]) -> str:
        for clave, valor in self._iter_paths(args):
            if not valor.strip():
                continue
            if "\x00" in valor:
                return f"ruta con byte NUL en '{clave}'"
            if not self.allowed_roots:
                return f"sin allowed_roots: '{clave}' denegado (fail-closed)"
            try:
                resuelta = Path(valor).expanduser().resolve(strict=False)
            except (OSError, RuntimeError, ValueError) as exc:
                return f"ruta '{valor}' no resoluble: {exc}"
            if not any(resuelta == raiz or raiz in resuelta.parents
                       for raiz in self.allowed_roots):
                return f"'{valor}' fuera de allowed_roots"
        return ""

    def _riesgo(self, tool: str) -> str:
        if tool in self.deny_tools or tool in self.FORBIDDEN_TOOLS:
            return "forbidden"
        if self.allow_tools and tool not in self.allow_tools:
            return "forbidden"
        if tool in self.READ_ONLY_TOOLS:
            return "read_only"
        return "confirm"

    def _permitir_llamada(self) -> bool:
        if self.max_calls_per_minute <= 0:
            return False
        ahora = self._clock()
        with self._lock:
            while self._llamadas and ahora - self._llamadas[0] >= 60:
                self._llamadas.popleft()
            if len(self._llamadas) >= self.max_calls_per_minute:
                return False
            self._llamadas.append(ahora)
        return True

    def _auditar(self, resultado: "GateResult") -> str:
        if self.audit_path is None:
            return ""
        resumen = json.dumps(resultado.args, sort_keys=True,
                             ensure_ascii=False, default=str)
        registro = {
            "ts": time.time(),
            "tool": resultado.tool,
            "decision": resultado.decision.value,
            "risk": resultado.risk_level,
            "reason": resultado.reason,
            "args_sha256": hashlib.sha256(resumen.encode("utf-8")).hexdigest(),
        }
        try:
            self.audit_path.parent.mkdir(parents=True, exist_ok=True)
            with self.audit_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(registro, ensure_ascii=False) + "\n")
        except OSError as exc:
            return f"auditoría no escribible ({self.audit_path}): {exc}"
        return ""

    def check(self, tool: str, args: Dict[str, Any] = None) -> "GateResult":
        """Evalúa una tool call. Nunca lanza por datos del llamante."""
        tool = str(tool)
        args = dict(args or {})
        riesgo = self._riesgo(tool)

        if not self._permitir_llamada():
            resultado = GateResult(
                GateDecision.DENY,
                f"límite de {self.max_calls_per_minute} llamadas/minuto excedido",
                riesgo, tool, args)
        elif riesgo == "forbidden":
            resultado = GateResult(
                GateDecision.DENY, f"herramienta '{tool}' prohibida",
                riesgo, tool, args)
        else:
            violacion = self._violacion_de_ruta(args)
            if violacion:
                resultado = GateResult(
                    GateDecision.DENY, violacion, riesgo, tool, args)
            elif riesgo == "confirm":
                aprobado = False
                motivo = f"'{tool}' requiere confirmación humana (sin callback: fail-closed)"
                if self.confirm is not None:
                    try:
                        aprobado = bool(self.confirm(tool, args))
                    except Exception as exc:  # noqa: BLE001 - fallo de confirmación = denegar
                        motivo = f"confirmación falló para '{tool}': {exc}"
                    else:
                        motivo = f"'{tool}' no confirmado por el operador"
                resultado = GateResult(
                    GateDecision.ALLOW if aprobado else GateDecision.DENY,
                    "confirmado" if aprobado else motivo,
                    riesgo, tool, args)
            else:
                resultado = GateResult(
                    GateDecision.ALLOW, "permitido", riesgo, tool, args)

        error_auditoria = self._auditar(resultado)
        if error_auditoria:
            return GateResult(GateDecision.DENY, error_auditoria,
                              riesgo, tool, args)
        return resultado


_gate_por_defecto: Optional[LocalToolGate] = None
_gate_lock = threading.Lock()


def _obtener_gate_por_defecto() -> LocalToolGate:
    global _gate_por_defecto
    with _gate_lock:
        if _gate_por_defecto is None:
            _gate_por_defecto = LocalToolGate()
        return _gate_por_defecto


def gate_check(tool: str, args: Dict[str, Any] = None,
               gate: LocalToolGate = None) -> "GateResult":
    """Verifica una tool call con un `LocalToolGate`.

    El agente DEBE llamar a esta función (o a `GateCheckedLLM.check_tool`)
    antes de ejecutar la herramienta. Sin esa llamada, el gate no protege.
    """
    return (gate or _obtener_gate_por_defecto()).check(tool, args)


class GateDecision(Enum):
    """Decisiones del gate de seguridad."""
    ALLOW = "allow"           # Permitido (read_only o confirm aprobado)
    DENY = "deny"             # Denegado (forbidden, ruta fuera, cuota o confirm)
    ERROR = "error"           # Error interno; se trata como denegado


@dataclass
class GateResult:
    """Resultado de una verificación del gate."""
    decision: GateDecision
    reason: str
    risk_level: str = ""          # "read_only" | "confirm" | "forbidden"
    tool: str = ""
    args: Dict[str, Any] = field(default_factory=dict)
    raw_response: Optional[Dict[str, Any]] = None

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "GateResult":
        """Convierte respuesta JSON del gate a GateResult."""
        decision_str = str(data.get("decision", "error")).lower()
        if decision_str == "allow":
            decision = GateDecision.ALLOW
        elif decision_str in ("deny", "need_confirm", "forbidden"):
            decision = GateDecision.DENY
        else:
            decision = GateDecision.ERROR
        return cls(
            decision=decision,
            reason=data.get("reason", ""),
            risk_level=data.get("risk_level", ""),
            tool=data.get("tool", ""),
            args=data.get("args", {}),
            raw_response=data,
        )

    @classmethod
    def error(cls, reason: str) -> "GateResult":
        """Crea un resultado de error (fail-closed: trata error como denegado)."""
        return cls(decision=GateDecision.ERROR, reason=reason)


class GateCheckedLLM(LLMProvider):
    """Wrapper que fuerza la verificación del gate antes de cada tool call.

    Uso:
        llm = DeepSeekFreeAgentLLM(..., authorized=True)
        safe_llm = GateCheckedLLM(llm, gate=LocalToolGate(allowed_roots=["/tmp/work"]))

    `generate()` solo devuelve texto: el proveedor no ejecuta herramientas. La
    verificación se hace en `check_tool()`, que el agente DEBE llamar antes de
    ejecutar cualquier herramienta sugerida por el modelo. Sin esa llamada, el
    gate no protege nada.
    """

    def __init__(
        self,
        provider: LLMProvider,
        gate: LocalToolGate = None,
        fail_closed: bool = True,
    ):
        self.provider = provider
        self.gate = gate or LocalToolGate()
        self.fail_closed = fail_closed
        self.model = provider.model
        self.base_url = getattr(provider, "base_url", None)

    def generate(self, prompt: str, model: str = None, **kwargs) -> str:
        """Genera respuesta SIN verificación de gate (solo texto)."""
        return self.provider.generate(prompt, model=model, **kwargs)

    def check_tool(self, tool: str, args: Dict[str, Any] = None) -> GateResult:
        """Verifica una tool call con el gate. DEBE llamarse antes de ejecutar."""
        result = self.gate.check(tool, args)
        if self.fail_closed and result.decision != GateDecision.ALLOW:
            raise PermissionError(f"Gate denegó {tool}: {result.reason}")
        return result

    def get_available_models(self) -> list:
        return getattr(self.provider, "get_available_models", lambda: [])()

    def estimate_cost(self, prompt: str, model: str = None) -> float:
        return getattr(self.provider, "estimate_cost", lambda *a, **k: 0.0)(prompt, model)


