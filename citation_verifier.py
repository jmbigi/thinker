#!/usr/bin/env python3
"""Verificación de citas de un informe contra las fuentes recuperadas.

Este módulo separa dos preguntas que no son la misma:

1. **Existencia**: ¿la cita ``[n]`` apunta a una fuente recuperada y el
   fragmento citado aparece en ella?
2. **Soporte**: ¿el contenido de esa fuente respalda el claim?

La respuesta es una comprobación **léxica y determinista**, no una prueba
semántica ni una medida de verdad. Un ``SUPPORTED`` significa que el claim
comparte términos suficientes con la fuente y que no se detecta una negación
opuesta; sigue siendo revisable por un humano. Lo que no se puede comprobar se
declara ``UNVERIFIABLE`` y nunca se convierte en éxito (P0.1/P0.2).

Uso:
    python3 citation_verifier.py --report informe.md --sources fuentes.json
    python3 citation_verifier.py --report informe.md --sources fuentes.json --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

CITA_RE = re.compile(r"\[(\d{1,3})\]")
_TOKEN_RE = re.compile(r"[a-záéíóúüñ0-9]+", re.IGNORECASE)
_NEGACIONES = {
    "no", "nunca", "jamas", "jamás", "ningun", "ningún", "ninguna",
    "sin", "tampoco", "ni", "falta", "falso", "falsa",
}
# Términos demasiado frecuentes para decidir si una fuente respalda un claim.
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

ESTADOS = ("EXACT_MATCH", "FOUND", "NOT_FOUND", "UNVERIFIABLE")
SOPORTES = ("SUPPORTED", "PARTIALLY_SUPPORTED", "CONTRADICTED", "UNVERIFIABLE")
UMBRAL_SOPORTE = 0.6


def _tokens(texto: str) -> set[str]:
    return {
        token.lower()
        for token in _TOKEN_RE.findall(texto or "")
        if token.lower() not in _STOPWORDS and len(token) > 1
    }


def _cobertura(claim: str, contenido: str) -> float:
    """Fracción de términos del claim presentes en el contenido."""
    terminos = _tokens(claim)
    if not terminos:
        return 0.0
    return len(terminos & _tokens(contenido)) / len(terminos)


def _tiene_negacion(texto: str) -> bool:
    # No se usa `_tokens`: esa función elimina stopwords y "no"/"sin"/"ni"
    # están precisamente entre las negaciones que hay que detectar.
    return bool({token.lower() for token in _TOKEN_RE.findall(texto or "")}
                & _NEGACIONES)


def _texto_fuente(source: Dict[str, Any]) -> str:
    """Contenido verificable de una fuente, sin inventar campos."""
    partes = []
    for clave in ("content", "texto", "snippet", "summary", "abstract"):
        valor = source.get(clave)
        if isinstance(valor, str) and valor.strip():
            partes.append(valor)
    return "\n".join(partes)


def _normalizar_url(url: str) -> str:
    """Agrupa duplicados sin descartar partes que pueden identificar el recurso."""
    if not isinstance(url, str) or not url.strip():
        return ""
    try:
        parsed = urlparse(url.strip())
        autoridad = parsed.netloc.rsplit("@", 1)[-1]
        if autoridad.lower().startswith("www."):
            autoridad = autoridad[4:]
        parametros = [
            (clave, valor)
            for clave, valor in parse_qsl(parsed.query, keep_blank_values=True)
            if not (clave.lower().startswith("utm_")
                    or clave.lower() in ("ref", "fbclid", "gclid"))
        ]
        return urlunparse((parsed.scheme.lower(), autoridad.lower(),
                           parsed.path.rstrip("/"), "", urlencode(parametros), ""))
    except ValueError:
        return ""


def extraer_citas(texto: str) -> List[int]:
    """Números de cita en orden de aparición (puede haber repetidos)."""
    return [int(numero) for numero in CITA_RE.findall(texto or "")]


def _claim_para_fuente(source: Dict[str, Any],
                       claims: Optional[Sequence[Dict[str, Any]]]) -> str:
    """Asocia un claim a la fuente por URL o por ``source_id``.

    No inventa una asociación: si no hay coincidencia, devuelve "".
    """
    if not claims:
        return ""
    url = _normalizar_url(source.get("url", ""))
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        candidato = _normalizar_url(
            claim.get("source_url") or claim.get("url") or "")
        if url and candidato and url == candidato:
            return str(claim.get("claim") or "").strip()
        candidato_id = _normalizar_url(str(claim.get("source_id") or ""))
        if url and candidato_id and url == candidato_id:
            return str(claim.get("claim") or "").strip()
        if (source.get("id") is not None
                and claim.get("source_id") == source.get("id")):
            return str(claim.get("claim") or "").strip()
    return ""


def _clasificar_soporte(claim: str, contenido: str) -> tuple[str, float, str]:
    if not claim.strip() or not contenido.strip():
        return "UNVERIFIABLE", 0.0, "sin claim o sin contenido verificable"
    cobertura = _cobertura(claim, contenido)
    negacion_claim = _tiene_negacion(claim)
    negacion_fuente = _tiene_negacion(contenido)
    if cobertura >= 0.5 and negacion_claim != negacion_fuente:
        return ("CONTRADICTED", round(cobertura, 3),
                "cobertura alta con negación opuesta entre claim y fuente")
    if cobertura >= UMBRAL_SOPORTE:
        return ("SUPPORTED", round(cobertura, 3),
                "el claim comparte términos suficientes con la fuente")
    if cobertura > 0:
        return ("PARTIALLY_SUPPORTED", round(cobertura, 3),
                "solo parte del claim aparece en la fuente")
    return ("UNVERIFIABLE", 0.0,
            "sin solapamiento léxico: no se puede afirmar ni negar respaldo")


@dataclass
class CitationCheck:
    numero: int
    ocurrencias: int
    estado: str
    soporte: str
    cobertura: float
    url: str
    motivo: str
    fragmento_verificado: bool = False
    claim: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def verificar_cita(numero: int, sources: Sequence[Dict[str, Any]],
                   claim: str = "", fragmento: str = "",
                   ocurrencias: int = 1) -> CitationCheck:
    """Verifica una cita ``[numero]`` contra la lista de fuentes (1-based)."""
    if numero < 1 or numero > len(sources):
        return CitationCheck(
            numero=numero, ocurrencias=ocurrencias, estado="NOT_FOUND",
            soporte="UNVERIFIABLE", cobertura=0.0, url="",
            motivo=f"la cita apunta fuera del rango 1..{len(sources)}",
            claim=claim)
    source = sources[numero - 1]
    url = str(source.get("url", "") or "")
    contenido = _texto_fuente(source)
    if not contenido:
        return CitationCheck(
            numero=numero, ocurrencias=ocurrencias, estado="UNVERIFIABLE",
            soporte="UNVERIFIABLE", cobertura=0.0, url=url,
            motivo="la fuente no tiene contenido verificable (content/snippet)",
            claim=claim)

    estado = "FOUND"
    fragmento_verificado = False
    motivo = "fuente localizada con contenido verificable"
    if fragmento.strip():
        normalizado_fuente = " ".join(contenido.split()).lower()
        normalizado_fragmento = " ".join(fragmento.split()).lower()
        if normalizado_fragmento in normalizado_fuente:
            estado = "EXACT_MATCH"
            fragmento_verificado = True
            motivo = "el fragmento citado aparece literalmente en la fuente"
        else:
            estado = "NOT_FOUND"
            motivo = "el fragmento citado no aparece en la fuente"

    soporte, cobertura, razon_soporte = _clasificar_soporte(claim, contenido)
    if razon_soporte:
        motivo = f"{motivo}; {razon_soporte}"
    return CitationCheck(
        numero=numero, ocurrencias=ocurrencias, estado=estado,
        soporte=soporte, cobertura=cobertura, url=url, motivo=motivo,
        fragmento_verificado=fragmento_verificado, claim=claim)


def _grupos_duplicados(sources: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grupos: Dict[str, List[int]] = {}
    for indice, source in enumerate(sources, 1):
        clave = _normalizar_url(str(source.get("url", "") or ""))
        if clave:
            grupos.setdefault(clave, []).append(indice)
    return [
        {"url_normalizada": clave, "indices": indices}
        for clave, indices in sorted(grupos.items()) if len(indices) > 1
    ]


def verificar_informe(report: str, sources: Sequence[Dict[str, Any]],
                      claims: Optional[Sequence[Dict[str, Any]]] = None,
                      verificado_en: Optional[str] = None) -> Dict[str, Any]:
    """Verifica todas las citas de un informe y devuelve un resumen explícito."""
    numeros = extraer_citas(report)
    ocurrencias: Dict[int, int] = {}
    for numero in numeros:
        ocurrencias[numero] = ocurrencias.get(numero, 0) + 1

    checks = []
    for numero in sorted(ocurrencias):
        source = sources[numero - 1] if 1 <= numero <= len(sources) else {}
        claim = _claim_para_fuente(source, claims) if source else ""
        checks.append(verificar_cita(
            numero, sources, claim=claim, ocurrencias=ocurrencias[numero]))

    estados = {estado: 0 for estado in ESTADOS}
    soportes = {soporte: 0 for soporte in SOPORTES}
    for check in checks:
        estados[check.estado] += 1
        soportes[check.soporte] += 1

    citadas = {check.numero for check in checks if check.numero >= 1}
    fuentes_citadas = len(citadas & set(range(1, len(sources) + 1)))
    duplicadas = _grupos_duplicados(sources)
    advertencias = []
    if not numeros:
        advertencias.append("el informe no contiene citas [n]")
    if estados["NOT_FOUND"]:
        advertencias.append(
            f"{estados['NOT_FOUND']} citas no localizadas o fuera de rango")
    if estados["UNVERIFIABLE"]:
        advertencias.append(
            f"{estados['UNVERIFIABLE']} citas sin contenido verificable")
    if soportes["CONTRADICTED"]:
        advertencias.append(
            f"{soportes['CONTRADICTED']} claims con negación opuesta a la fuente")
    if duplicadas:
        advertencias.append(
            f"{len(duplicadas)} grupos de fuentes duplicadas por URL")
    if sources and fuentes_citadas < len(sources):
        advertencias.append(
            f"{len(sources) - fuentes_citadas} fuentes recuperadas no citadas")

    return {
        "verificado_en": verificado_en or datetime.now(timezone.utc).isoformat(
            timespec="seconds"),
        "metodo": ("comprobación léxica determinista; no es una prueba "
                   "semántica ni una medida de verdad"),
        "citas_totales": len(numeros),
        "fuentes_recuperadas": len(sources),
        "fuentes_citadas": fuentes_citadas,
        "cobertura_citas": round(fuentes_citadas / len(sources), 3)
        if sources else None,
        "estados": estados,
        "soportes": soportes,
        "checks": [check.to_dict() for check in checks],
        "duplicadas": duplicadas,
        "advertencias": advertencias,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verifica citas de un informe contra fuentes JSON.")
    parser.add_argument("--report", required=True, help="informe Markdown/TXT")
    parser.add_argument("--sources", required=True,
                        help="JSON con una lista de fuentes")
    parser.add_argument("--claims", help="JSON opcional con una lista de claims")
    parser.add_argument("--json", action="store_true", help="salida JSON")
    args = parser.parse_args(argv)

    report = Path(args.report).read_text(encoding="utf-8")
    sources = json.loads(Path(args.sources).read_text(encoding="utf-8"))
    claims = (json.loads(Path(args.claims).read_text(encoding="utf-8"))
              if args.claims else None)
    if not isinstance(sources, list):
        print("ERROR: --sources debe contener una lista JSON", file=sys.stderr)
        return 2
    resultado = verificar_informe(report, sources, claims)
    if args.json:
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
    else:
        print(f"Citas: {resultado['citas_totales']} | "
              f"fuentes citadas: {resultado['fuentes_citadas']}/"
              f"{resultado['fuentes_recuperadas']}")
        for check in resultado["checks"]:
            print(f"  [{check['numero']}] {check['estado']:12s} "
                  f"{check['soporte']:20s} cobertura={check['cobertura']:.2f} "
                  f"{check['url']}")
        for advertencia in resultado["advertencias"]:
            print(f"  AVISO: {advertencia}")
        print(resultado["metodo"])
    return 0 if not any(check["estado"] == "NOT_FOUND"
                        for check in resultado["checks"]) else 1


if __name__ == "__main__":
    sys.exit(main())
