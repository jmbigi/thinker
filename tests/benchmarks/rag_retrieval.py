#!/usr/bin/env python3
"""Benchmark de recuperación léxica local (RAG) con relevancia conocida.

Mide lo que el sistema hace de verdad: BM25 + coseno léxico, sin embeddings.
No prueba calidad semántica; sirve para tener una línea base reproducible y
para decidir con datos si merece la pena añadir recuperación semántica.

Métricas: Recall@k, MRR y nDCG@k con ganancia binaria.

Uso:
    python3 -m tests.benchmarks.rag_retrieval [--json]
"""

from __future__ import annotations

import argparse
import json
import math
from typing import Any, Dict, Iterable, Sequence

from documents import PassageIndex

CORPUS = [
    {"id": "fusion", "snippet": (
        "La fusión nuclear busca reproducir en la Tierra la energía del Sol "
        "uniendo núcleos ligeros y liberando energía.")},
    {"id": "rag", "snippet": (
        "La recuperación aumentada por generación combina un índice de "
        "documentos con un modelo de lenguaje para responder con contexto.")},
    {"id": "mcp", "snippet": (
        "El Protocolo de Contexto de Modelo (MCP) estandariza cómo un cliente "
        "descubre y llama herramientas expuestas por un servidor.")},
    {"id": "ncm", "snippet": (
        "NCM conceptual organiza un esquema en secciones y refinamientos "
        "residuales con trazas hash y reconstrucción determinista.")},
    {"id": "python", "snippet": (
        "Python 3.11 se publicó en octubre de 2022 con mejoras de rendimiento "
        "y mensajes de error más precisos.")},
    {"id": "clima", "snippet": (
        "El cambio climático altera la temperatura media, las precipitaciones "
        "y la frecuencia de fenómenos extremos.")},
    {"id": "cuantica", "snippet": (
        "La computación cuántica usa cúbits y superposición para resolver "
        "ciertos problemas que un ordenador clásico no aborda igual.")},
    {"id": "vacunas", "snippet": (
        "Las vacunas entrenan al sistema inmunitario para reconocer patógenos "
        "sin provocar la enfermedad.")},
    {"id": "inflacion", "snippet": (
        "La inflación mide la subida sostenida de precios y reduce el poder "
        "adquisitivo del dinero.")},
    {"id": "sqlite", "snippet": (
        "SQLite es una base de datos relacional embebida que guarda toda la "
        "información en un único archivo.")},
]

CONSULTAS = [
    {"query": "energía del Sol fusión", "relevant": ["fusion"]},
    {"query": "recuperación de documentos con un modelo de lenguaje",
     "relevant": ["rag"]},
    {"query": "protocolo para llamar herramientas de un servidor",
     "relevant": ["mcp"]},
    {"query": "esquema con refinamientos residuales", "relevant": ["ncm"]},
    {"query": "versión de Python publicada en 2022", "relevant": ["python"]},
    {"query": "temperatura y fenómenos extremos", "relevant": ["clima"]},
    {"query": "cúbits y superposición", "relevant": ["cuantica"]},
    {"query": "sistema inmunitario y patógenos", "relevant": ["vacunas"]},
    {"query": "subida de precios y poder adquisitivo", "relevant": ["inflacion"]},
    {"query": "base de datos en un único archivo", "relevant": ["sqlite"]},
    # Paráfrasis sin términos exactos: la recuperación léxica puede fallar.
    {"query": "energía de las estrellas", "relevant": ["fusion"]},
    {"query": "asistente que consulta documentos", "relevant": ["rag"]},
    {"query": "acuerdo internacional para el clima", "relevant": ["clima"]},
    {"query": "medicina que previene enfermedades", "relevant": ["vacunas"]},
    {"query": "computadora que usa estados superpuestos", "relevant": ["cuantica"]},
    {"query": "motor de base de datos ligero", "relevant": ["sqlite"]},
]


def recall_at_k(ranked: Sequence[str], relevant: Iterable[str], k: int) -> float:
    relevantes = set(relevant)
    if not relevantes:
        return 0.0
    return len(set(ranked[:k]) & relevantes) / len(relevantes)


def reciprocal_rank(ranked: Sequence[str], relevant: Iterable[str]) -> float:
    relevantes = set(relevant)
    for posicion, identificador in enumerate(ranked, 1):
        if identificador in relevantes:
            return 1.0 / posicion
    return 0.0


def ndcg_at_k(ranked: Sequence[str], relevant: Iterable[str], k: int) -> float:
    relevantes = set(relevant)
    if not relevantes:
        return 0.0
    dcg = sum(
        1.0 / math.log2(posicion + 1)
        for posicion, identificador in enumerate(ranked[:k], 1)
        if identificador in relevantes
    )
    idcg = sum(1.0 / math.log2(posicion + 1)
               for posicion in range(1, min(len(relevantes), k) + 1))
    return dcg / idcg if idcg else 0.0


def evaluar_consulta(index: PassageIndex, consulta: Dict[str, Any],
                     k: int = 10) -> Dict[str, Any]:
    resultados = index.search(consulta["query"], max_results=k)
    ranked = [resultado["id"] for resultado in resultados]
    return {
        "query": consulta["query"],
        "relevant": list(consulta["relevant"]),
        "ranked": ranked,
        "recall@1": round(recall_at_k(ranked, consulta["relevant"], 1), 3),
        "recall@3": round(recall_at_k(ranked, consulta["relevant"], 3), 3),
        "recall@5": round(recall_at_k(ranked, consulta["relevant"], 5), 3),
        "recall@10": round(recall_at_k(ranked, consulta["relevant"], 10), 3),
        "mrr": round(reciprocal_rank(ranked, consulta["relevant"]), 3),
        "ndcg@10": round(ndcg_at_k(ranked, consulta["relevant"], 10), 3),
    }


def evaluar(corpus: Sequence[Dict[str, Any]] = CORPUS,
            consultas: Sequence[Dict[str, Any]] = CONSULTAS) -> Dict[str, Any]:
    index = PassageIndex(corpus)
    resultados = [evaluar_consulta(index, consulta) for consulta in consultas]
    metricas = ("recall@1", "recall@3", "recall@5", "recall@10",
                "mrr", "ndcg@10")
    medias = {
        metrica: round(sum(fila[metrica] for fila in resultados)
                       / len(resultados), 3)
        for metrica in metricas
    }
    return {
        "corpus": len(corpus),
        "consultas": len(consultas),
        "metricas": medias,
        "resultados": resultados,
        "metodo": ("BM25 + coseno léxico, sin embeddings; "
                   "relevancia binaria y corpus pequeño"),
        "no_prueba": ("calidad semántica ni rendimiento sobre corpus reales; "
                      "solo línea base reproducible"),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    resultado = evaluar()
    if args.json:
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
        return 0
    print(f"RAG léxico: {resultado['corpus']} pasajes, "
          f"{resultado['consultas']} consultas")
    for metrica, valor in resultado["metricas"].items():
        print(f"  {metrica:10s} {valor:.3f}")
    print(resultado["metodo"])
    print(resultado["no_prueba"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
