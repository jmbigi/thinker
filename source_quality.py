#!/usr/bin/env python3
"""Calidad y diversidad de fuentes, sin fundirla con la confianza del claim.

El módulo devuelve **dimensiones separadas** (autoridad, independencia,
actualidad, relevancia, soporte, trazabilidad y posible contradicción). No
calcula una nota única: mezclar "fuente reputada" con "fuente que respalda este
claim" produce una cifra que parece más precisa de lo que es.

Todas las señales son heurísticas declaradas. La autoridad por dominio no mide
veracidad; la independencia por URL no detecta copias de la misma nota de
prensa en dominios distintos; la relevancia y el soporte son léxicos. Sirven
para ordenar la revisión humana y para detectar duplicados evidentes, no para
sustituirla (P0.1/P0.2).

Uso:
    python3 source_quality.py --sources fuentes.json [--query "..."] [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_TOKEN_RE = re.compile(r"[a-záéíóúüñ0-9]+", re.IGNORECASE)
_STOPWORDS = {
    "a", "al", "algo", "algun", "algún", "algunas", "algunos", "ante",
    "antes", "como", "con", "contra", "cual", "cuales", "cuando", "de",
    "del", "desde", "donde", "dos", "el", "ella", "ellas", "ellos", "en",
    "entre", "era", "es", "esa", "ese", "eso", "esta", "este", "esto",
    "fue", "ha", "han", "hasta", "hay", "la", "las", "le", "les", "lo",
    "los", "mas", "más", "mediante", "muy", "ni", "no", "o", "para",
    "pero", "por", "que", "qué", "se", "ser", "si", "sí", "sin", "sobre",
    "son", "su", "sus", "tambien", "también", "tanto", "tiene", "tienen",
    "todo", "todos", "un", "una", "uno", "unos", "y", "ya",
}
_NEGACIONES = {
    "no", "nunca", "jamas", "jamás", "ningun", "ningún", "ninguna",
    "sin", "tampoco", "ni", "falta", "falso", "falsa",
}

# Heurística de dominio: reputación general, NO veracidad del contenido.
_AUTORIDAD_ALTA = (
    ".gov", ".edu", "who.int", "nature.com", "science.org", "nejm.org",
    "arxiv.org", "pubmed.ncbi.nlm.nih.gov", "ncbi.nlm.nih.gov",
    "semanticscholar.org", "ieee.org", "acm.org",
)
_AUTORIDAD_MEDIA = (
    "wikipedia.org", "reuters.com", "apnews.com", "bbc.com", "elpais.com",
    "nytimes.com", "theguardian.com", "github.com", "python.org",
    "docs.python.org", "mozilla.org",
)
_AUTORIDAD_BAJA = ("twitter.com", "x.com", "facebook.com", "tiktok.com")


def _tokens(texto: str) -> set[str]:
    return {
        token.lower()
        for token in _TOKEN_RE.findall(texto or "")
        if token.lower() not in _STOPWORDS and len(token) > 1
    }


def _cobertura(objetivo: str, contenido: str) -> float:
    terminos = _tokens(objetivo)
    if not terminos:
        return 0.0
    return round(len(terminos & _tokens(contenido)) / len(terminos), 3)


def _tiene_negacion(texto: str) -> bool:
    return bool({token.lower() for token in _TOKEN_RE.findall(texto or "")}
                & _NEGACIONES)


def _host(url: str) -> str:
    if not isinstance(url, str) or not url.strip():
        return ""
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _normalizar_url(url: str) -> str:
    """Normaliza host, esquema y parámetros de seguimiento."""
    if not isinstance(url, str) or not url.strip():
        return ""
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    ruta = parsed.path.rstrip("/")
    parametros = [
        (clave, valor) for clave, valor in parse_qsl(parsed.query)
        if not clave.lower().startswith(("utm_", "ref", "fbclid", "gclid"))
    ]
    return urlunparse((parsed.scheme.lower(), host, ruta, "", urlencode(parametros), ""))


def _coincide(host: str, sufijos: Sequence[str]) -> bool:
    return any(host == sufijo or host.endswith("." + sufijo)
               or (sufijo.startswith(".") and host.endswith(sufijo))
               for sufijo in sufijos)


def _autoridad(url: str) -> Dict[str, Any]:
    host = _host(url)
    if not host:
        return {"valor": None, "metodo": "heurística de dominio",
                "detalle": "sin URL: no evaluable"}
    if _coincide(host, _AUTORIDAD_ALTA):
        return {"valor": 0.9, "metodo": "heurística de dominio",
                "detalle": f"dominio institucional/académico: {host}"}
    if _coincide(host, _AUTORIDAD_MEDIA):
        return {"valor": 0.6, "metodo": "heurística de dominio",
                "detalle": f"dominio de referencia o medio conocido: {host}"}
    if _coincide(host, _AUTORIDAD_BAJA):
        return {"valor": 0.15, "metodo": "heurística de dominio",
                "detalle": f"red social: {host}"}
    return {"valor": 0.3, "metodo": "heurística de dominio",
            "detalle": f"dominio no clasificado: {host}"}


def _parse_fecha(source: Dict[str, Any]) -> Optional[datetime]:
    for clave in ("published_at", "publicado", "date", "fecha",
                  "fetched_at", "recuperado_en"):
        valor = source.get(clave)
        if not isinstance(valor, str) or not valor.strip():
            continue
        texto = valor.strip().replace("Z", "+00:00")
        try:
            fecha = datetime.fromisoformat(texto)
        except ValueError:
            coincidencia = re.search(r"\b(19|20)\d{2}\b", texto)
            if not coincidencia:
                continue
            fecha = datetime(int(coincidencia.group()), 1, 1,
                             tzinfo=timezone.utc)
        if fecha.tzinfo is None:
            fecha = fecha.replace(tzinfo=timezone.utc)
        return fecha
    return None


def _actualidad(source: Dict[str, Any]) -> Dict[str, Any]:
    fecha = _parse_fecha(source)
    if fecha is None:
        return {"valor": None, "dias": None, "metodo": "fecha declarada",
                "detalle": "sin fecha legible: no evaluable"}
    dias = (datetime.now(timezone.utc) - fecha).days
    if dias < 0:
        return {"valor": 1.0, "dias": dias, "metodo": "fecha declarada",
                "detalle": "fecha futura: se declara y no se usa como vigencia"}
    if dias <= 30:
        valor, detalle = 1.0, "<= 30 días"
    elif dias <= 365:
        valor, detalle = 0.8, "<= 1 año"
    elif dias <= 1825:
        valor, detalle = 0.5, "<= 5 años"
    else:
        valor, detalle = 0.2, "> 5 años"
    return {"valor": valor, "dias": dias, "metodo": "fecha declarada",
            "detalle": detalle}


def _texto(source: Dict[str, Any]) -> str:
    partes = []
    for clave in ("title", "titulo", "snippet", "content", "texto",
                  "summary", "abstract"):
        valor = source.get(clave)
        if isinstance(valor, str) and valor.strip():
            partes.append(valor)
    return "\n".join(partes)


def _claims_para_fuente(source: Dict[str, Any],
                        claims: Optional[Sequence[Dict[str, Any]]]) -> List[str]:
    if not claims:
        return []
    url = _normalizar_url(str(source.get("url", "") or ""))
    propios = []
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        texto = str(claim.get("claim") or "").strip()
        if not texto:
            continue
        claim_url = _normalizar_url(
            str(claim.get("source_url") or claim.get("url") or ""))
        claim_id = _normalizar_url(str(claim.get("source_id") or ""))
        if ((claim_url and url and claim_url == url)
                or (claim_id and url and claim_id == url)
                or (not claim_url and claim.get("source_id") == source.get("id"))):
            propios.append(texto)
    return propios


def _dimension_soporte(claims: Sequence[str], contenido: str) -> Dict[str, Any]:
    if not claims:
        return {"valor": None, "cobertura": None,
                "metodo": "solapamiento léxico",
                "detalle": "sin claim asociado: no evaluable"}
    coberturas = [_cobertura(claim, contenido) for claim in claims]
    mejor = max(coberturas)
    posibles = [
        claim for claim, cobertura in zip(claims, coberturas)
        if cobertura >= 0.5 and _tiene_negacion(claim) != _tiene_negacion(contenido)
    ]
    return {
        "valor": mejor,
        "cobertura": mejor,
        "claims_evaluados": len(claims),
        "posible_contradiccion": posibles,
        "metodo": "solapamiento léxico + negación",
        "detalle": ("cobertura máxima del claim en la fuente; "
                    "no prueba respaldo semántico"),
    }


def _trazabilidad(source: Dict[str, Any]) -> Dict[str, Any]:
    campos = [clave for clave in ("url", "snippet", "content", "sha256")
              if source.get(clave)]
    tiene_url = bool(source.get("url"))
    tiene_texto = bool(_texto(source).strip())
    return {
        "valor": bool(tiene_url and tiene_texto),
        "campos": campos,
        "metodo": "presencia de URL, texto y hash",
        "detalle": ("permite localizar el fragmento" if tiene_url and tiene_texto
                    else "falta URL o texto verificable"),
    }


def evaluar_fuentes(sources: Sequence[Dict[str, Any]], query: str = "",
                    claims: Optional[Sequence[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Devuelve dimensiones separadas por fuente y un resumen de diversidad."""
    grupos_url: Dict[str, List[int]] = {}
    grupos_independencia: Dict[str, List[int]] = {}
    fuentes = []
    for indice, source in enumerate(sources, 1):
        url = str(source.get("url", "") or "")
        url_normalizada = _normalizar_url(url)
        host = _host(url)
        grupo = host or str(source.get("title") or source.get("titulo") or "")
        if url_normalizada:
            grupos_url.setdefault(url_normalizada, []).append(indice)
        if grupo:
            grupos_independencia.setdefault(grupo, []).append(indice)
        contenido = _texto(source)
        propios = _claims_para_fuente(source, claims)
        dimensiones = {
            "autoridad": _autoridad(url),
            "actualidad": _actualidad(source),
            "relevancia": ({
                "valor": _cobertura(query, contenido),
                "cobertura": _cobertura(query, contenido),
                "metodo": "solapamiento léxico",
                "detalle": "cobertura de términos de la consulta",
            } if query.strip() else {
                "valor": None, "cobertura": None,
                "metodo": "solapamiento léxico",
                "detalle": "sin consulta: no evaluable",
            }),
            "soporte": _dimension_soporte(propios, contenido),
            "trazabilidad": _trazabilidad(source),
        }
        fuentes.append({
            "indice": indice,
            "titulo": source.get("title") or source.get("titulo") or "",
            "url": url,
            "grupo_independencia": grupo or "(sin título ni URL)",
            "dimensiones": dimensiones,
        })

    for fuente in fuentes:
        indices = grupos_independencia.get(fuente["grupo_independencia"], [])
        otras = [indice for indice in indices if indice != fuente["indice"]]
        fuente["dimensiones"]["independencia"] = {
            "grupo": fuente["grupo_independencia"],
            "otras_en_grupo": otras,
            "valor": round(1 / (1 + len(otras)), 3) if otras else 1.0,
            "metodo": "agrupación por dominio o título",
            "detalle": ("mismo dominio/título que otras fuentes: "
                        "no son independientes por sí solas" if otras
                        else "sin otra fuente del mismo dominio/título"),
        }

    duplicadas = [
        {"url_normalizada": url, "indices": indices}
        for url, indices in sorted(grupos_url.items()) if len(indices) > 1
    ]
    grupos_dominio = [
        {"grupo": grupo, "indices": indices}
        for grupo, indices in sorted(grupos_independencia.items())
        if len(indices) > 1
    ]
    sin_url = sum(1 for source in sources if not source.get("url"))
    sin_texto = sum(1 for source in sources
                    if not _texto(source).strip())
    dominios = {_host(str(source.get("url", "") or "")) for source in sources}
    dominios.discard("")
    advertencias = []
    if sin_url:
        advertencias.append(f"{sin_url} fuentes sin URL")
    if sin_texto:
        advertencias.append(f"{sin_texto} fuentes sin texto verificable")
    if duplicadas:
        advertencias.append(
            f"{len(duplicadas)} URLs normalizadas apuntan a la misma página")
    if grupos_dominio:
        advertencias.append(
            f"{len(grupos_dominio)} grupos comparten dominio o título; "
            "pueden no ser evidencias independientes")
    if sources and len(dominios) < len(sources):
        advertencias.append(
            "hay más fuentes que dominios únicos: la diversidad es limitada")
    return {
        "consulta": query,
        "total": len(sources),
        "dominios_unicos": len(dominios),
        "diversidad_dominios": round(len(dominios) / len(sources), 3)
        if sources else None,
        "sin_url": sin_url,
        "sin_texto": sin_texto,
        "grupos_duplicados": duplicadas,
        "grupos_independencia": grupos_dominio,
        "advertencias": advertencias,
        "fuentes": fuentes,
        "nota": ("dimensiones heurísticas y separadas; no hay una nota única "
                 "de calidad de fuente ni de confianza en el claim"),
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Evalúa dimensiones separadas de calidad de fuentes.")
    parser.add_argument("--sources", required=True,
                        help="JSON con una lista de fuentes")
    parser.add_argument("--query", default="", help="consulta de referencia")
    parser.add_argument("--claims", help="JSON opcional con claims")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    sources = json.loads(Path(args.sources).read_text(encoding="utf-8"))
    claims = (json.loads(Path(args.claims).read_text(encoding="utf-8"))
              if args.claims else None)
    if not isinstance(sources, list):
        print("ERROR: --sources debe contener una lista JSON", file=sys.stderr)
        return 2
    resultado = evaluar_fuentes(sources, args.query, claims)
    if args.json:
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
    else:
        print(f"Fuentes: {resultado['total']} | "
              f"dominios únicos: {resultado['dominios_unicos']} | "
              f"diversidad: {resultado['diversidad_dominios']}")
        for fuente in resultado["fuentes"]:
            dimensiones = fuente["dimensiones"]
            print(f"  [{fuente['indice']}] {fuente['titulo'][:60]!r} "
                  f"autoridad={dimensiones['autoridad']['valor']} "
                  f"relevancia={dimensiones['relevancia']['valor']} "
                  f"soporte={dimensiones['soporte']['valor']}")
        for advertencia in resultado["advertencias"]:
            print(f"  AVISO: {advertencia}")
        print(resultado["nota"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
