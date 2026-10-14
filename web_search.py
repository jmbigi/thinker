#!/usr/bin/env python3
"""
Proveedores de búsqueda para el sistema de investigación.

Todos son gratuitos y sin API key (P2.1):
- `MockSearchAPI`: offline, determinista (demos y tests sin red).
- `WikipediaSearchAPI`: API oficial de MediaWiki (JSON estructurado).
- `DuckDuckGoSearchAPI`: endpoint HTML público de DuckDuckGo (búsqueda web).

Los errores de red o de formato se elevan (P1.19): nunca se devuelve una
lista vacía silenciosamente cuando la causa es un fallo.
"""

import html
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List
from urllib.parse import parse_qs, unquote, urlparse

import requests

USER_AGENT = "research-agent/1.0 (+https://github.com/jmbigi/thinker)"

# Palabras vacías (es/en) para formular consultas de búsqueda a partir de
# preguntas naturales. Los buscadores por palabras clave no entienden
# preguntas largas: devuelven 0 resultados (verificado 2026-10-14).
STOPWORDS = {
    # español
    "que", "qué", "cual", "cuál", "cuales", "cuáles", "como", "cómo", "donde",
    "dónde", "cuando", "cuándo", "por", "para", "con", "sin", "los", "las",
    "del", "de", "la", "el", "en", "y", "o", "u", "a", "al", "un", "una",
    "unos", "unas", "es", "son", "esta", "está", "estan", "están", "se", "su",
    "sus", "mas", "más", "pero", "sobre", "entre", "hay", "han", "ha", "fue",
    "ser", "tiene", "tienen", "existe", "existen", "actual", "actualmente",
    "actuales", "principales", "diferentes", "posibles", "según", "tras",
    "durante", "desde", "hasta", "tanto", "cada", "otros", "otras", "este",
    "esta", "estos", "estas", "ese", "esa", "esos", "esas",
    # inglés
    "the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "is", "are",
    "was", "were", "what", "which", "who", "how", "why", "when", "where",
    "that", "this", "these", "those", "with", "from", "by", "at", "as", "it",
    "its", "be", "been", "has", "have", "had", "do", "does", "did", "about",
}


def formulate_query(question: str, max_terms: int = 4,
                    anchor_terms: List[str] = None) -> str:
    """Convierte una pregunta natural en una consulta de palabras clave.

    Los motores de búsqueda por palabras clave devuelven 0 resultados ante
    preguntas largas y multi-cláusula; esta función extrae los términos con
    contenido (sin palabras vacías ni interrogativos) preservando el orden.
    Con 4 términos se maximizó el recall en las pruebas del 2026-10-14
    (24 resultados frente a 8 con 8 términos).

    `anchor_terms` son términos del tema general (p. ej. de la pregunta
    original) que se colocan AL PRINCIPIO: sin ellos, una subpregunta larga
    pierde el tema y la búsqueda devuelve resultados irrelevantes
    (verificado: sin anclas aparecía "Cine experimental"). Si no queda ningún
    término, devuelve la pregunta original.
    """
    words = re.findall(r"[^\W\d_]+", question.lower(), flags=re.UNICODE)
    terms, seen = [], set()
    for word in (anchor_terms or []):
        word = word.lower()
        if len(word) > 2 and word not in STOPWORDS and word not in seen:
            seen.add(word)
            terms.append(word)
    for word in words:
        if len(word) > 2 and word not in STOPWORDS and word not in seen:
            seen.add(word)
            terms.append(word)
    return " ".join(terms[:max_terms]) or question.strip()


class SearchAPI(ABC):
    """Interfaz de proveedores de búsqueda."""

    @abstractmethod
    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Devuelve una lista de {title, url, snippet, source}."""


def _strip_html(text: str) -> str:
    """Quita etiquetas HTML y normaliza espacios."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", text or ""))).strip()


class MockSearchAPI(SearchAPI):
    """Búsqueda simulada, offline y determinista (NO usa red).

    Declarada como simulada: sus fuentes son ficticias y sirven para probar
    el pipeline sin conexión.
    """

    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        return [{
            "title": f"Article about {query}",
            "url": f"https://example.com/{query.replace(' ', '-')}",
            "snippet": (f"Este es contenido de ejemplo sobre {query}. "
                        f"Incluye datos ficticios para demostración."),
            "source": "mock-search",
        }][:max_results]


class WikipediaSearchAPI(SearchAPI):
    """Búsqueda real en Wikipedia vía la API de MediaWiki (sin API key).

    Verificado en vivo: HTTP 200 + JSON estructurado.
    """

    def __init__(self, language: str = "es", timeout: int = 20):
        self.endpoint = f"https://{language}.wikipedia.org/w/api.php"
        self.timeout = timeout

    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        response = requests.get(
            self.endpoint,
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "format": "json",
                "srlimit": max_results,
            },
            headers={"User-Agent": USER_AGENT},
            timeout=self.timeout,
        )
        response.raise_for_status()
        try:
            hits = response.json()["query"]["search"]
        except (KeyError, ValueError) as exc:
            raise RuntimeError(
                f"Respuesta inesperada de la API de Wikipedia: {exc}"
            ) from exc

        results = []
        for hit in hits:
            title = hit.get("title", "")
            results.append({
                "title": title,
                "url": f"https://{urlparse(self.endpoint).netloc}/wiki/{title.replace(' ', '_')}",
                "snippet": _strip_html(hit.get("snippet", "")),
                "source": "wikipedia",
            })
        return results


class DuckDuckGoSearchAPI(SearchAPI):
    """Búsqueda web real en DuckDuckGo (endpoint HTML público, sin API key).

    El HTML puede cambiar sin aviso: si la respuesta es 200 pero no se extrae
    ningún resultado, se eleva RuntimeError en vez de devolver vacío en
    silencio (P1.19).

    Sólo permite URLs con esquema http/https de hosts públicos: descarta
    cualquier otra (evita SSRF/javascript:, P0.13).
    """

    def __init__(self, timeout: int = 20):
        self.endpoint = "https://html.duckduckgo.com/html/"
        self.timeout = timeout

    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        response = requests.post(
            self.endpoint,
            data={"q": query},
            headers={"User-Agent": USER_AGENT},
            timeout=self.timeout,
        )
        response.raise_for_status()

        pattern = re.compile(
            r'<a[^>]+class="result__a"[^>]+href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>'
            r'.*?class="result__snippet"[^>]*>(?P<snippet>.*?)</a>',
            re.DOTALL,
        )
        results = []
        for match in pattern.finditer(response.text):
            url = self._clean_url(match.group("href"))
            if not url:
                continue
            results.append({
                "title": _strip_html(match.group("title")),
                "url": url,
                "snippet": _strip_html(match.group("snippet")),
                "source": "duckduckgo",
            })
            if len(results) >= max_results:
                break

        if not results:
            raise RuntimeError(
                "DuckDuckGo devolvió 200 pero no se extrajo ningún resultado: "
                "el formato HTML puede haber cambiado."
            )
        return results

    @staticmethod
    def _clean_url(href: str) -> str:
        """Resuelve el redireccionamiento de DDG y valida el esquema."""
        href = html.unescape(href)
        if href.startswith("//"):
            href = "https:" + href
        if "duckduckgo.com/l/" in href:
            uddg = parse_qs(urlparse(href).query).get("uddg")
            if uddg:
                href = unquote(uddg[0])
        parsed = urlparse(href)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return ""
        return href
