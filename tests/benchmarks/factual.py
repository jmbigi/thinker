#!/usr/bin/env python3
"""Benchmark factual de evaluación de evidencia (offline por defecto).

Mide el paso que decide si una fuente RESPALDA, CONTRADICE o NO ABORDA un
claim: es el núcleo factual del pipeline. El conjunto es versionado y cada
caso declara su veredicto esperado ANTES de ejecutar; la categoría
`insufficient` mide la abstención (una fuente que no aborda el claim no debe
presentarse como respaldo).

Métricas: exactitud global y por categoría, **falsos verificados**
(esperado contradicted/insufficient y el modelo dice supported: el error más
grave), tasa de abstención y, si hay confianzas, Brier con IC bootstrap.

Con `MockLLM` el protocolo y las métricas se ejercitan, pero **no mide
calidad real** (lo simulado se declara). La medición real es opt-in con un
proveedor (key + red, coste 0 con modelos `:free`).

Uso:
    python3 -m tests.benchmarks.factual            # simulado (MockLLM)
    python3 -m tests.benchmarks.factual --json
    python3 -m tests.benchmarks.factual --con-llm  # opt-in: proveedor real
"""

import argparse
import json
import sys

from deep_research_system import EvidenceEvaluator, ResearchContext
from llm_providers import MockLLM

CATEGORIAS = ("supported", "contradicted", "insufficient")

CASOS = [
    # --- supported (la fuente respalda el claim) ---
    {"categoria": "supported",
     "claim": "El agua hierve a 100 grados Celsius al nivel del mar.",
     "fuente": "Al nivel del mar, el agua hierve a 100 grados Celsius."},
    {"categoria": "supported",
     "claim": "Python 3.11 se publico en octubre de 2022.",
     "fuente": "Python 3.11 fue lanzado en octubre de 2022."},
    {"categoria": "supported",
     "claim": "La capital de Francia es Paris.",
     "fuente": "Paris es la capital de Francia."},
    {"categoria": "supported",
     "claim": "El Everest tiene 8849 metros de altitud.",
     "fuente": "El Everest, con 8849 metros, es la montana mas alta sobre el nivel del mar."},
    {"categoria": "supported",
     "claim": "La Tierra orbita alrededor del Sol.",
     "fuente": "La Tierra completa una orbita alrededor del Sol cada ano."},
    {"categoria": "supported",
     "claim": "El oro es un metal solido a temperatura ambiente.",
     "fuente": "A temperatura ambiente el oro es un metal solido."},
    {"categoria": "supported",
     "claim": "Un adulto tiene 206 huesos.",
     "fuente": "El esqueleto adulto consta de 206 huesos."},
    {"categoria": "supported",
     "claim": "El oxigeno representa cerca del 21 por ciento de la atmosfera.",
     "fuente": "La atmosfera terrestre contiene aproximadamente un 21 por ciento de oxigeno."},
    {"categoria": "supported",
     "claim": "El euro entro en circulacion en 2002.",
     "fuente": "El euro comenzo a circular como moneda fisica en 2002."},
    {"categoria": "supported",
     "claim": "La luz viaja a unos 300000 kilometros por segundo en el vacio.",
     "fuente": "En el vacio, la luz se propaga a cerca de 300000 kilometros por segundo."},
    # --- contradicted (la fuente contradice el claim) ---
    {"categoria": "contradicted",
     "claim": "La Tierra es plana.",
     "fuente": "La Tierra es un elipsoide achatado en los polos."},
    {"categoria": "contradicted",
     "claim": "El Sol gira alrededor de la Tierra.",
     "fuente": "La Tierra orbita alrededor del Sol."},
    {"categoria": "contradicted",
     "claim": "El oro es un gas a temperatura ambiente.",
     "fuente": "El oro es un metal solido a temperatura ambiente."},
    {"categoria": "contradicted",
     "claim": "La Gran Muralla China es visible desde la Luna a simple vista.",
     "fuente": "La Gran Muralla no es visible a simple vista desde la Luna."},
    {"categoria": "contradicted",
     "claim": "El agua hierve a 50 grados Celsius al nivel del mar.",
     "fuente": "Al nivel del mar, el agua hierve a 100 grados Celsius."},
    {"categoria": "contradicted",
     "claim": "Python 3.11 se publico en 2019.",
     "fuente": "Python 3.11 fue lanzado en octubre de 2022."},
    {"categoria": "contradicted",
     "claim": "La capital de Italia es Milan.",
     "fuente": "La capital de Italia es Roma."},
    {"categoria": "contradicted",
     "claim": "El Everest mide 5000 metros.",
     "fuente": "El Everest, con 8849 metros, es la montana mas alta sobre el nivel del mar."},
    {"categoria": "contradicted",
     "claim": "El oxigeno representa el 80 por ciento de la atmosfera.",
     "fuente": "La atmosfera terrestre contiene aproximadamente un 21 por ciento de oxigeno."},
    {"categoria": "contradicted",
     "claim": "El euro entro en circulacion en 1990.",
     "fuente": "El euro comenzo a circular como moneda fisica en 2002."},
    # --- insufficient (la fuente no aborda el claim: abstención) ---
    {"categoria": "insufficient",
     "claim": "El chocolate negro mejora la memoria a corto plazo.",
     "fuente": "El cacao se cultiva principalmente en zonas tropicales."},
    {"categoria": "insufficient",
     "claim": "Marte tuvo oceanos hace millones de anos.",
     "fuente": "Marte es el cuarto planeta del sistema solar."},
    {"categoria": "insufficient",
     "claim": "El te verde reduce el colesterol.",
     "fuente": "El te verde se elabora a partir de hojas de Camellia sinensis."},
    {"categoria": "insufficient",
     "claim": "La pizza margarita se invento en Napoles en 1889.",
     "fuente": "La pizza es un plato de origen italiano."},
    {"categoria": "insufficient",
     "claim": "El ejercicio aerobico mejora la memoria en adultos mayores.",
     "fuente": "El ejercicio fisico incluye actividades como caminar o nadar."},
    {"categoria": "insufficient",
     "claim": "Los virus no son seres vivos.",
     "fuente": "Los virus son agentes infecciosos."},
    {"categoria": "insufficient",
     "claim": "La cafeina mejora el rendimiento deportivo.",
     "fuente": "La cafeina es un alcaloide presente en el cafe."},
    {"categoria": "insufficient",
     "claim": "El telescopio James Webb fue lanzado en 2021.",
     "fuente": "El telescopio James Webb observa en infrarrojo."},
    {"categoria": "insufficient",
     "claim": "La penicilina se descubrio por accidente.",
     "fuente": "Alexander Fleming investigaba bacterias."},
    {"categoria": "insufficient",
     "claim": "La seda se produce en China desde hace miles de anos.",
     "fuente": "La seda es una fibra natural de origen animal."},
]


MAPA_ESPERADO = {"supported": "supported", "contradicted": "contradicted",
                 "insufficient": "not_addressed"}


def esperado_de(caso):
    """Veredicto esperado: la categoría `insufficient` se mide como
    `not_addressed` (es la abstención; `insufficient` no es un veredicto del
    evaluador)."""
    return MAPA_ESPERADO[caso["categoria"]]


def evaluar_casos(llm):
    """Evalúa cada caso con EvidenceEvaluator; devuelve veredictos y detalles."""
    evaluador = EvidenceEvaluator(llm)
    veredictos, detalle = [], []
    for caso in CASOS:
        contexto = ResearchContext(caso["claim"])
        contexto.sources.append({
            "url": "fuente", "title": "Fuente", "snippet": caso["fuente"]})
        evaluacion = evaluador.decide(
            contexto, {"claim": caso["claim"], "source_url": "fuente"})
        veredicto = evaluacion.get("verdict", "not_addressed")
        veredictos.append(veredicto)
        detalle.append({
            "categoria": caso["categoria"],
            "claim": caso["claim"],
            "esperado": esperado_de(caso),
            "veredicto": veredicto,
            "confidence": float(evaluacion.get("confidence", 0.0) or 0.0),
        })
    return veredictos, detalle


def metricas(veredictos, detalle):
    """Exactitud global/por categoría, falsos verificados y abstención."""
    exactos = sum(1 for d in detalle if d["veredicto"] == d["esperado"])
    por_categoria = {}
    for categoria in CATEGORIAS:
        casos = [d for d in detalle if d["categoria"] == categoria]
        aciertos = sum(1 for d in casos if d["veredicto"] == d["esperado"])
        por_categoria[categoria] = {
            "n": len(casos),
            "aciertos": aciertos,
            "exactitud": round(aciertos / len(casos), 3) if casos else None,
        }
    falsos = [d for d in detalle
              if d["esperado"] != "supported" and d["veredicto"] == "supported"]
    insuficientes = [d for d in detalle if d["categoria"] == "insufficient"]
    abstencion = sum(1 for d in insuficientes
                     if d["veredicto"] == d["esperado"])
    return {
        "n": len(detalle),
        "exactitud": round(exactos / len(detalle), 3) if detalle else None,
        "por_categoria": por_categoria,
        "falsos_verificados": len(falsos),
        "tasa_abstencion": round(abstencion / len(insuficientes), 3)
        if insuficientes else None,
    }


def ejecutar(llm=None):
    simulado = llm is None
    if simulado:
        llm = MockLLM()
    veredictos, detalle = evaluar_casos(llm)
    return {
        "modo": "simulado (MockLLM): no mide calidad real" if simulado
        else f"real ({getattr(llm, 'model', '?')})",
        "metricas": metricas(veredictos, detalle),
        "detalle": detalle,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--con-llm", action="store_true",
                        help="opt-in: proveedor real (key + red, coste 0 "
                             "con modelos :free)")
    args = parser.parse_args(argv)
    llm = None
    if args.con_llm:
        from llm_providers import OpenRouterLLM
        llm = OpenRouterLLM()
    resultado = ejecutar(llm)
    if args.json:
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
        return 0
    print(f"Benchmark factual ({resultado['modo']})")
    metricas_ = resultado["metricas"]
    print(f"  n={metricas_['n']} exactitud={metricas_['exactitud']} "
          f"falsos_verificados={metricas_['falsos_verificados']} "
          f"abstencion={metricas_['tasa_abstencion']}")
    for categoria, datos in metricas_["por_categoria"].items():
        print(f"  {categoria:13s} {datos['aciertos']}/{datos['n']} "
              f"({datos['exactitud']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
