#!/usr/bin/env python3
"""Sonda de latencia de un modelo (opt-in: requiere key y red).

Mide cuánto tarda un modelo gratuito en responder al prompt mínimo "Helo" y
dictamina si es APTO según la regla de mínima calidad del proyecto: un modelo
que tarda SIEMPRE más de 1 minuto no es práctico ni realista.

- Coste 0 con modelos `:free` de OpenRouter (por defecto, el del proyecto).
- Sin key definida NO se prueba: se reporta y se sale sin llamar (P1.29).
- Nunca imprime la key.
- Usa el SDK directamente con timeout explícito por muestra: así mide la
  llamada cruda, sin la caché ni los reintentos del cliente del proyecto.

Uso:
    python3 scripts/probe_model.py                      # 5 muestras del defecto
    python3 scripts/probe_model.py --model otro/x:free --samples 3

Salida: latencias por muestra, resumen y veredicto. Códigos: 0 = APTO,
1 = NO APTO, 2 = sin key (no se prueba).
"""

import argparse
import os
import statistics
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from llm_providers import DEFAULT_FREE_MODEL  # noqa: E402

PROMPT = "Helo"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sonda de latencia de un modelo (regla de mínima calidad).")
    parser.add_argument("--model", default=None,
                        help="modelo a sondear (por defecto: OPENROUTER_MODEL "
                             "o el modelo gratis del proyecto)")
    parser.add_argument("--samples", type=int, default=5,
                        help="número de muestras (por defecto 5)")
    parser.add_argument("--interval", type=float, default=15.0,
                        help="segundos entre muestras (por defecto 15)")
    parser.add_argument("--timeout", type=float, default=30.0,
                        help="timeout por muestra, en segundos (por defecto 30)")
    parser.add_argument("--threshold", type=float, default=60.0,
                        help="umbral de la regla de mínima calidad, en segundos")
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env")
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        print("SIN KEY definida: no se prueba (regla del programador).")
        return 2

    model = args.model or os.environ.get("OPENROUTER_MODEL", DEFAULT_FREE_MODEL)
    from openai import OpenAI

    client = OpenAI(api_key=key, base_url="https://openrouter.ai/api/v1",
                    timeout=args.timeout)

    print(f"modelo: {model}")
    print(f"key presente: sí ({len(key)} caracteres, no se imprime)")
    print(f"sonda: {PROMPT!r} x{args.samples} cada {args.interval:.0f}s "
          f"(umbral {args.threshold:.0f}s)\n")

    latencias = []
    fallos = []
    for i in range(args.samples):
        t0 = time.time()
        try:
            respuesta = client.chat.completions.create(
                model=model, messages=[{"role": "user", "content": PROMPT}])
            dt = round(time.time() - t0, 2)
            latencias.append(dt)
            texto = (respuesta.choices[0].message.content or "").strip()[:40]
            print(f"  {i + 1}/{args.samples} OK    {dt:6.2f}s  {texto!r}")
        except Exception as exc:  # noqa: BLE001 - se reporta por muestra
            dt = round(time.time() - t0, 2)
            status = getattr(exc, "status_code", None)
            fallos.append(f"{status or type(exc).__name__}")
            print(f"  {i + 1}/{args.samples} FALLO {dt:6.2f}s  "
                  f"status={status} {type(exc).__name__}")
        if i < args.samples - 1:
            time.sleep(args.interval)

    print()
    if not latencias:
        print(f"VEREDICTO: NO APTO — 0/{args.samples} respuestas; "
              f"fallos: {', '.join(fallos)}")
        return 1

    lentas = [dt for dt in latencias if dt > args.threshold]
    print(f"respuestas: {len(latencias)}/{args.samples} | "
          f"mín {min(latencias):.2f}s | mediana {statistics.median(latencias):.2f}s"
          f" | máx {max(latencias):.2f}s | lentas (>{args.threshold:.0f}s): "
          f"{len(lentas)}")
    if len(lentas) == len(latencias):
        print(f"VEREDICTO: NO APTO — TODAS las respuestas superaron "
              f"{args.threshold:.0f}s (regla de mínima calidad).")
        return 1

    print(f"VEREDICTO: APTO — {len(latencias) - len(lentas)}/{len(latencias)} "
          f"respuestas por debajo de {args.threshold:.0f}s.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
