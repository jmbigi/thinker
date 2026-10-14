#!/usr/bin/env python3
"""Test Kilo integration with LLM systems (offline: sin llamadas reales)."""
import inspect
import sys

sys.path.insert(0, '.')

results = []


def check(name, fn):
    try:
        fn()
        results.append((name, True))
        print(f"  ✓ {name}")
    except Exception as e:
        results.append((name, False))
        print(f"  ✗ {name} -> {type(e).__name__}: {e}")


print("=" * 60)
print("KILO INTEGRATION TEST (offline)")
print("=" * 60)

# Test 1: Import LLM classes
print("\n[1] Importing LLM classes...")


def t1():
    from deep_research_system import (OllamaLLM, OpenAILLM, OpenRouterLLM,
                                      KiloGatewayLLM, LLMProvider, MockLLM)
    assert issubclass(MockLLM, LLMProvider)
    ollama = OllamaLLM()
    assert ollama.base_url == "http://localhost:11434"
    kilo = KiloGatewayLLM(api_key="clave-ficticia-de-test")
    assert kilo.base_url == "https://api.kilo.ai/api/gateway"
    openai_llm = OpenAILLM(api_key="clave-ficticia-de-test")
    assert openai_llm.api_key == "clave-ficticia-de-test"
    router = OpenRouterLLM(api_key="clave-ficticia-de-test")
    assert router.base_url == "https://openrouter.ai/api/v1"
check("All LLM classes import and instantiate", t1)

# Test 2: Check generate method compatibility
print("\n[2] Checking generate method compatibility...")


def t2():
    from deep_research_system import OllamaLLM, KiloGatewayLLM, OpenAILLM, MockLLM
    for cls in (OllamaLLM, KiloGatewayLLM, OpenAILLM, MockLLM):
        sig = inspect.signature(cls.generate)
        has_kwargs = any(p.kind == inspect.Parameter.VAR_KEYWORD
                         for p in sig.parameters.values())
        assert has_kwargs, f"{cls.__name__}.generate no acepta **kwargs"
check("All generate() accept **kwargs", t2)

# Test 3: ThinkingLayer con MockLLM (offline)
print("\n[3] Checking ThinkingLayer compatibility (MockLLM, offline)...")


def t3():
    from pensamiento_layer import DeepResearchThinkingLayer
    from deep_research_system import MockLLM
    result = DeepResearchThinkingLayer(MockLLM(), name="test").think("test prompt")
    assert result["valid"] and result["step_count"] == 7
check("thinking.think() works offline with MockLLM", t3)

# Test 4: CodeDesign tools
print("\n[4] Checking CodeDesign improvement tools...")


def t4():
    from code_design_improvement_tools import CodeDesignThinker, CodeAnalysisContext
    from deep_research_system import MockLLM
    thinker = CodeDesignThinker(name="test", llm_provider=MockLLM())
    context = CodeAnalysisContext("test_project")
    assert context.to_dict()["total_issues"] == 0
    result = thinker.decide(context, "código de prueba")
    assert result["valid"], f"ciclo inválido: {result.get('error')}"
check("CodeDesignThinker runs 7-step cycle offline", t4)

print("\n" + "=" * 60)
passed = sum(1 for _, ok in results if ok)
print(f"RESULTADO: {passed}/{len(results)} tests pasaron")
print("Nota: llamadas REALES a Kilo/OpenRouter no se prueban aquí (opt-in,")
print("requieren API key y red; ver test_openrouter_real.py).")
print("=" * 60)
sys.exit(0 if passed == len(results) else 1)
