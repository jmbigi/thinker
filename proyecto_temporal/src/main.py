#!/usr/bin/env python3
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(module)s: %(message)s"
)
logger = logging.getLogger("proyecto_temporal.forthtrade")

ft_llm = None
ft_key = os.environ.get("FT_AI_API_KEY", "")
try:
    from llm_providers import ForthtradeGatewayLLM
    if ft_key:
        ft_llm = ForthtradeGatewayLLM()
        logger.info(f"ForthtradeGatewayLLM inicializado: model={ft_llm.model}")
    else:
        logger.warning("FT_AI_API_KEY no definida - modo offline")
except ImportError:
    logger.warning("llm_providers no disponible - modo offline")

def pensar_codigo(prompt: str) -> str:
    if not os.path.exists("pyproject.toml"):
        return "❌ pyproject.toml no encontrado"
    if ft_llm is None:
        return "❌ ForthtradeGatewayLLM no disponible - configure FT_AI_API_KEY"
    try:
        resultado = ft_llm.generate(prompt)
        return resultado
    except Exception as e:
        return f"❌ Error: {type(e).__name__}"

if __name__ == "__main__":
    print("Proyecto temporal Forthtrade + Thinker")
    print("=" * 50)
