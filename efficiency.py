#!/usr/bin/env python3
"""Optimización de orquestación y RAG, con límites explícitos.

No modifica pesos del LLM. MoE aquí significa expertos a nivel de aplicación y
SpeculativeLLM significa draft-verificación, no decodificación especulativa.
"""

import math
import re
import struct
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Tuple

from documents import PassageIndex
from llm_providers import LLMProvider


def _tokens(text: str) -> List[str]:
    return [word for word in re.findall(r"[^\W\d_]+", text.casefold()) if len(word) > 1]


@dataclass(frozen=True)
class AdaptivePlan:
    level: str
    score: float
    reasons: Tuple[str, ...]
    max_iterations: int
    verificacion_independiente: bool
    muestras_consenso: int
    ncm_residual: bool
    use_tot: bool

    def orchestrator_options(self) -> Dict[str, Any]:
        return {
            "max_iterations": self.max_iterations,
            "verificacion_independiente": self.verificacion_independiente,
            "muestras_consenso": self.muestras_consenso,
            "informe_ncm_residual": self.ncm_residual,
        }


class AdaptiveRouter:
    """Router heurístico declarado, no un clasificador de dificultad calibrado."""

    def plan(self, question: str) -> AdaptivePlan:
        words = _tokens(question)
        score = 0.0
        reasons = []
        if len(words) > 45:
            score += 0.25
            reasons.append("pregunta extensa")
        if len(words) > 100:
            score += 0.2
            reasons.append("alcance muy amplio")
        comparadores = ("compara", "versus", "contrasta", "evalúa", "evalua",
                        "analiza", "diferencias", "ventajas", "desventajas")
        if any(term in question.casefold() for term in comparadores):
            score += 0.25
            reasons.append("comparación o evaluación")
        if question.count("?") + question.count("¿") > 1 or " y " in question.casefold():
            score += 0.15
            reasons.append("múltiples dimensiones")
        tecnicos = ("arquitectura", "protocolo", "algoritmo", "cuántico", "quantum",
                    "clinical", "macroecon", "transformer", "rag", "mcp")
        if any(term in question.casefold() for term in tecnicos):
            score += 0.2
            reasons.append("terminología técnica")
        score = min(score, 1.0)
        if score >= 0.65:
            return AdaptivePlan("deep", score, tuple(reasons) or ("complejidad estimada",),
                                7, True, 2, True, True)
        if score >= 0.3:
            return AdaptivePlan("standard", score, tuple(reasons), 5, False, 1, False, False)
        return AdaptivePlan("basic", score, tuple(reasons), 3, False, 1, False, False)


class ContextPruner:
    """Poda recuperación por relevancia y presupuesto, con métricas reales."""

    def __init__(self, max_passages: int = 6, max_chars: int = 2400,
                 min_score: float = 0.0):
        if max_passages < 1 or max_chars < 100 or min_score < 0:
            raise ValueError("Presupuesto de contexto inválido")
        self.max_passages = max_passages
        self.max_chars = max_chars
        self.min_score = min_score

    def prune(self, query: str, sources: Iterable[Dict[str, Any]]):
        originales = list(sources)
        if not originales:
            return [], {"input_passages": 0, "output_passages": 0,
                        "input_chars": 0, "output_chars": 0, "savings_ratio": 0.0}
        utilizables = [s for s in originales if s.get("snippet", "").strip()]
        if not utilizables:
            return [], {"input_passages": len(originales), "output_passages": 0,
                        "input_chars": sum(len(s.get("snippet", "")) for s in originales),
                        "output_chars": 0, "savings_ratio": 1.0}
        candidatos = PassageIndex(utilizables).search(query, len(utilizables))
        seleccion = []
        usados = 0
        for source in candidatos:
            score = source.get("relevance_score", 0.0)
            texto = source["snippet"]
            if len(seleccion) >= self.max_passages or score < self.min_score:
                continue
            if seleccion and usados + len(texto) > self.max_chars:
                continue
            if not seleccion and len(texto) > self.max_chars:
                source = dict(source)
                source["snippet"] = texto[:self.max_chars]
                source["content"] = source["snippet"]
                source["truncated"] = True
            seleccion.append(source)
            usados += len(source["snippet"])
        entrada = sum(len(s.get("snippet", "")) for s in originales)
        metricas = {
            "input_passages": len(originales),
            "output_passages": len(seleccion),
            "input_chars": entrada,
            "output_chars": usados,
            "savings_ratio": round(1 - usados / entrada, 6) if entrada else 0.0,
        }
        return seleccion, metricas


class QuantizedVector:
    """Vector denso cuantizado INT8/INT4 con escala y reconstrucción."""

    def __init__(self, values: Iterable[float], bits: int = 8):
        if bits not in (4, 8):
            raise ValueError("bits debe ser 4 u 8")
        valores = list(values)
        if not valores or not all(math.isfinite(v) for v in valores):
            raise ValueError("Vector vacío o no finito")
        self.bits = bits
        self.scale = max(abs(v) for v in valores)
        if self.scale == 0:
            self.scale = 1.0
        limite = 7 if bits == 4 else 127
        self.values = [max(-limite, min(limite, round(v / self.scale * limite)))
                       for v in valores]

    @classmethod
    def from_text(cls, text: str, bits: int = 8):
        frecuencias = Counter(_tokens(text))
        if not frecuencias:
            raise ValueError("No hay términos para vectorizar")
        claves = sorted(frecuencias)
        normas = {k: 1 + math.log(frecuencias[k]) for k in claves}
        norma = math.sqrt(sum(v * v for v in normas.values()))
        vector = [normas[k] / norma for k in claves]
        return cls(vector, bits), claves

    def pack(self) -> bytes:
        if self.bits == 8:
            return struct.pack(f"{len(self.values)}b", *self.values)
        datos = bytearray()
        for indice in range(0, len(self.values), 2):
            alto = self.values[indice] & 0x0F
            bajo = self.values[indice + 1] & 0x0F if indice + 1 < len(self.values) else 0
            datos.append((alto << 4) | bajo)
        return bytes(datos)

    def dequantize(self) -> List[float]:
        limite = 7 if self.bits == 4 else 127
        return [v / limite * self.scale for v in self.values]

    def cosine(self, other: "QuantizedVector") -> float:
        if len(self.values) != len(other.values):
            raise ValueError("Vectores de dimensiones distintas")
        a, b = self.dequantize(), other.dequantize()
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(x * x for x in b))
        return dot / (na * nb) if na and nb else 0.0

    def memory_bytes(self) -> Dict[str, Any]:
        comprimido = len(self.pack())
        original = len(self.values) * 8
        return {"float64": original, "compressed": comprimido,
                "savings_ratio": round(1 - comprimido / original, 6)}


class SemanticResponseCache:
    """Caché exacta y, opt-in, semántica léxica con vectores cuantizados."""

    def __init__(self, max_entries: int = 128, bits: int = 8):
        self.max_entries = max_entries
        self.bits = bits
        self.entries: Dict[Tuple[str, str], str] = {}
        self.vectors: Dict[Tuple[str, str], Tuple[QuantizedVector, List[str]]] = {}
        self.hits_exact = 0
        self.hits_semantic = 0
        self.misses = 0

    def get(self, model: str, prompt: str, semantic_threshold: float = None):
        clave = (model, prompt)
        if clave in self.entries:
            self.hits_exact += 1
            return self.entries[clave], "exact"
        if semantic_threshold is None or not self.entries:
            self.misses += 1
            return None
        consulta, claves = QuantizedVector.from_text(prompt, self.bits)
        mejor = None
        for (modelo, texto), (vector, _) in self.vectors.items():
            if modelo != model or len(vector.values) != len(consulta.values):
                continue
            claves_guardadas = self.vectors[(modelo, texto)][1]
            if claves_guardadas != claves:
                continue
            score = consulta.cosine(vector)
            if mejor is None or score > mejor[0]:
                mejor = (score, (modelo, texto))
        if mejor and mejor[0] >= semantic_threshold:
            self.hits_semantic += 1
            return self.entries[mejor[1]], "semantic"
        self.misses += 1
        return None

    def set(self, model: str, prompt: str, response: str) -> None:
        if len(self.entries) >= self.max_entries:
            vieja = next(iter(self.entries))
            self.entries.pop(vieja)
            self.vectors.pop(vieja, None)
        clave = (model, prompt)
        self.entries[clave] = response
        self.vectors[clave] = QuantizedVector.from_text(prompt, self.bits)


class CachedLLM(LLMProvider):
    def __init__(self, provider: LLMProvider, cache: SemanticResponseCache,
                 semantic_threshold: float = None):
        if semantic_threshold is not None and not 0 <= semantic_threshold <= 1:
            raise ValueError("semantic_threshold debe estar entre 0 y 1")
        self.provider = provider
        self.cache = cache
        self.semantic_threshold = semantic_threshold

    def generate(self, prompt: str, model: str = None, **kwargs) -> str:
        modelo = model or getattr(self.provider, "model", "unknown")
        encontrado = self.cache.get(modelo, prompt, self.semantic_threshold)
        if encontrado is not None:
            return encontrado[0]
        respuesta = self.provider.generate(prompt, model=model, **kwargs)
        self.cache.set(modelo, prompt, respuesta)
        return respuesta


class ExpertRouterLLM(LLMProvider):
    """Enrutamiento a expertos por dominio; no es MoE dentro de la red."""

    def __init__(self, experts: Dict[str, Tuple[LLMProvider, Tuple[str, ...]]],
                 fallback: LLMProvider):
        if not experts:
            raise ValueError("Se exige al menos un experto")
        self.experts = experts
        self.fallback = fallback
        self.routes: List[str] = []

    def generate(self, prompt: str, model: str = None, **kwargs) -> str:
        texto = prompt.casefold()
        puntuaciones = {nombre: sum(texto.count(k.casefold()) for k in keywords)
                          for nombre, (_, keywords) in self.experts.items()}
        nombre = max(puntuaciones, key=puntuaciones.get)
        if puntuaciones[nombre] == 0:
            provider = self.fallback
            nombre = "fallback"
        else:
            provider = self.experts[nombre][0]
        self.routes.append(nombre)
        return provider.generate(prompt, model=model, **kwargs)


class SpeculativeLLM(LLMProvider):
    """Draft-verificación con dos modelos; puede aumentar coste y latencia."""

    def __init__(self, draft: LLMProvider, verifier: LLMProvider):
        self.draft = draft
        self.verifier = verifier
        self.drafts = 0
        self.verifications = 0

    def generate(self, prompt: str, model: str = None, **kwargs) -> str:
        self.drafts += 1
        candidato = self.draft.generate(prompt, model=model, **kwargs)
        self.verifications += 1
        verificacion = self.verifier.generate(
            "Verify and correct the draft answer. Return only the final answer.\n\n"
            f"Task:\n{prompt}\n\nDraft:\n{candidato}", model=model, **kwargs)
        if not verificacion.strip():
            raise RuntimeError("El verificador devolvió una respuesta vacía")
        return verificacion
