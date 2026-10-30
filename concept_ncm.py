#!/usr/bin/env python3
"""Jerarquía residual de conceptos inspirada en NCM (no es el modelo del paper).

Niveles: esquema global → secciones → evidencia residual. Las unidades de un
mismo nivel se procesan en paralelo acotado y se reconstruyen en orden. Los
códigos son hashes de trazabilidad, no códigos VQ aprendidos.
"""

import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, Dict, List


def _hash(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]


def _tokens(texto: str) -> set:
    return {token for token in re.findall(r"[^\W\d_]+", texto.casefold())
            if len(token) > 2}


def _cubierto(claim: str, contenido: str) -> bool:
    terminos = _tokens(claim)
    if not terminos:
        return True
    presentes = _tokens(contenido)
    return len(terminos & presentes) / len(terminos) >= 0.6


@dataclass
class ConceptResult:
    report: str
    traces: List[Dict[str, Any]]
    generated_sections: int


class ResidualConceptGenerator:
    """Genera y refina conceptos por niveles, con trazas hash encadenadas."""

    def __init__(self, llm_provider, max_workers: int = 1):
        if not isinstance(max_workers, int) or isinstance(max_workers, bool) \
                or max_workers < 1:
            raise ValueError("max_workers debe ser un entero >= 1")
        self.llm = llm_provider
        self.max_workers = max_workers

    def _map(self, func: Callable, items: List[Any]) -> List[Any]:
        if self.max_workers == 1:
            return [func(item) for item in items]
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            return list(executor.map(func, items))

    def _nivel_seccion(self, item):
        indice, seccion, context, fuentes, claims, prompt_builder, cleaner = item
        try:
            contenido = self.llm.generate(
                prompt_builder(seccion, context, fuentes, claims)).strip()
            if cleaner is not None:
                contenido = cleaner(context, contenido, seccion["titulo"]).strip()
            return {"indice": indice, "seccion": seccion, "contenido": contenido,
                    "error": ""}
        except Exception as exc:
            return {"indice": indice, "seccion": seccion, "contenido": "",
                    "error": f"{type(exc).__name__}: {exc}"}

    def _nivel_residual(self, item):
        entrada, context, fuentes, claims = item
        seccion = entrada["seccion"]
        titulo = seccion["titulo"]
        faltantes = [claim for claim in seccion["claims"]
                     if not _cubierto(claim, entrada["contenido"])]
        if not faltantes:
            return {**entrada, "refinamiento": "", "faltantes": [], "estado": "sin_residual"}
        seleccion = "\n".join(
            linea for linea in claims.splitlines()
            if any(claim.casefold() in linea.casefold() for claim in faltantes))
        prompt = f"""Add ONLY the missing evidence for the concept "{titulo}".

Parent concept content (do not repeat it):
{entrada['contenido']}

Missing claims to address now:
{seleccion}

Retrieved sources; cite as [n]:
{fuentes}

Return only the residual addition in markdown. Do not add a section title,
new topic, introduction, conclusion, or information already in the parent."""
        try:
            refinamiento = self.llm.generate(prompt).strip()
            if refinamiento and _cubierto(refinamiento, entrada["contenido"]):
                return {**entrada, "refinamiento": "", "faltantes": faltantes,
                        "estado": "duplicado"}
            return {**entrada, "refinamiento": refinamiento,
                    "faltantes": faltantes, "estado": "generated" if refinamiento else "empty"}
        except Exception as exc:
            return {**entrada, "refinamiento": "", "faltantes": faltantes,
                    "estado": "error", "error_residual": f"{type(exc).__name__}: {exc}"}

    def generate(self, context, secciones: List[Dict[str, Any]], fuentes_txt: str,
                 claims_txt: str, prompt_builder: Callable,
                 content_cleaner: Callable = None) -> ConceptResult:
        """Produce niveles residuales y una reconstrucción determinista."""
        raiz = _hash(context.question + json.dumps(secciones, sort_keys=True,
                                                    ensure_ascii=False))
        trazas = [{
            "level": 0, "code": f"outline:{raiz}", "parent": "",
            "residual": [s["titulo"] for s in secciones],
            "content_hash": raiz, "status": "generated", "workers": 1,
        }]
        trabajos = [(indice, seccion, context, fuentes_txt, claims_txt, prompt_builder,
                     content_cleaner) for indice, seccion in enumerate(secciones)]
        nivel1 = self._map(self._nivel_seccion, trabajos)
        generadas = 0
        entradas_residuales = []
        for entrada in nivel1:
            seccion = entrada["seccion"]
            titulo = seccion["titulo"]
            contenido = entrada["contenido"]
            if contenido:
                generadas += 1
            estado = "generated" if contenido else ("error" if entrada["error"] else "empty")
            padre = trazas[0]["content_hash"]
            entrada["hash"] = _hash(padre + titulo + contenido)
            entrada["traza"] = {
                "level": 1, "code": f"section:{entrada['indice']}:{_hash(titulo)}",
                "parent": padre, "residual": seccion["claims"],
                "content_hash": entrada["hash"], "status": estado,
                "workers": self.max_workers,
            }
            if entrada["error"]:
                entrada["traza"]["error"] = entrada["error"]
            trazas.append(entrada["traza"])
            if contenido:
                entradas_residuales.append((entrada, context, fuentes_txt, claims_txt))
        if not generadas:
            return ConceptResult("", trazas, 0)

        nivel2 = self._map(self._nivel_residual, entradas_residuales)
        cuerpos = {entrada["indice"]: entrada for entrada in nivel1}
        for entrada in nivel2:
            indice = entrada["indice"]
            refinamiento = entrada["refinamiento"]
            if refinamiento:
                cuerpos[indice]["contenido"] += f"\n\n{refinamiento}"
            traza = {
                "level": 2,
                "code": f"residual:{indice}:{_hash(str(entrada['faltantes']))}",
                "parent": entrada["hash"],
                "residual": entrada["faltantes"],
                "content_hash": _hash(entrada["hash"] + refinamiento),
                "status": entrada["estado"],
                "workers": self.max_workers,
            }
            if entrada.get("error_residual"):
                traza["error"] = entrada["error_residual"]
            trazas.append(traza)

        partes = [f"# Research Report: {context.question}"]
        for entrada in nivel1:
            titulo = entrada["seccion"]["titulo"]
            contenido = cuerpos[entrada["indice"]]["contenido"] or \
                "(No content generated for this section.)"
            partes.append(f"## {titulo}\n\n{contenido}")
        informe = "\n\n".join(partes)
        trazas.append({
            "level": 3, "code": f"reconstruction:{_hash(informe)}",
            "parent": trazas[0]["content_hash"], "residual": [],
            "content_hash": _hash(informe), "status": "generated",
            "workers": self.max_workers,
        })
        return ConceptResult(informe, trazas, generadas)
