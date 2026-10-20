#!/usr/bin/env python3
"""
Test script for the Plugin System.

Verifies plugin discovery, loading, hot-swapping, and dashboard.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from plugins.registry import plugin_registry
from plugins.dashboard import dashboard


def test_discovery():
    """Test plugin discovery."""
    print("=== Testing Plugin Discovery ===")
    count = plugin_registry.discover_plugins()
    print(f"Discovered {count} plugins")
    assert count > 0, "Should discover at least some plugins"
    
    plugins = plugin_registry.list_plugins()
    print(f"Total plugins registered: {len(plugins)}")
    for p in plugins:
        print(f"  - {p['name']} ({p['type']}) v{p['version']}")
    return True


def test_load_llm_plugins():
    """Test loading LLM provider plugins."""
    print("\n=== Testing LLM Plugin Loading ===")
    
    # Load mock_llm first (always works offline)
    success = plugin_registry.load_plugin("mock_llm")
    print(f"mock_llm load: {'OK' if success else 'FAILED'}")
    assert success, "mock_llm should load successfully"
    
    # Try to load openrouter (may fail without API key)
    success = plugin_registry.load_plugin("openrouter")
    print(f"openrouter load: {'OK' if success else 'FAILED (expected without key)'}")
    
    # Try to load deepseek (may fail without API key)
    success = plugin_registry.load_plugin("deepseek")
    print(f"deepseek load: {'OK' if success else 'FAILED (expected without key)'}")
    
    return True


def test_load_search_plugins():
    """Test loading search provider plugins."""
    print("\n=== Testing Search Plugin Loading ===")
    
    # Load mock_search first (always works offline)
    success = plugin_registry.load_plugin("mock_search")
    print(f"mock_search load: {'OK' if success else 'FAILED'}")
    assert success, "mock_search should load successfully"
    
    # Try to load duckduckgo (requires network)
    success = plugin_registry.load_plugin("duckduckgo")
    print(f"duckduckgo load: {'OK' if success else 'FAILED (network may fail)'}")
    
    # Try to load wikipedia (requires network)
    success = plugin_registry.load_plugin("wikipedia")
    print(f"wikipedia load: {'OK' if success else 'FAILED (network may fail)'}")
    
    return True


def test_active_providers():
    """Test active provider selection."""
    print("\n=== Testing Active Provider Selection ===")
    
    active_llm = plugin_registry.get_active_llm()
    print(f"Active LLM: {active_llm.metadata.name if active_llm else 'None'}")
    
    active_search = plugin_registry.get_active_search()
    print(f"Active Search: {active_search.metadata.name if active_search else 'None'}")
    
    # Test switching active LLM
    if plugin_registry.set_active_llm("mock_llm"):
        print("Switched active LLM to mock_llm")
        active_llm = plugin_registry.get_active_llm()
        assert active_llm.metadata.name == "mock_llm"
    
    return True


def test_plugin_execution():
    """Test actual plugin execution."""
    print("\n=== Testing Plugin Execution ===")
    
    # Test mock LLM
    llm = plugin_registry.get_plugin("mock_llm")
    if llm:
        result = llm.generate("Responde exactamente: OK")
        print(f"mock_llm generate: {result[:100]}")
        # MockLLM returns a simulated response
        assert "simulada" in result.lower() or "simulado" in result.lower() or "mock" in result.lower()
    
    # Test mock search
    search = plugin_registry.get_plugin("mock_search")
    if search:
        results = search.search("test query", max_results=2)
        print(f"mock_search results: {len(results)} items")
        assert len(results) > 0
    
    return True


def test_hot_reload():
    """Test hot-reloading a plugin."""
    print("\n=== Testing Hot Reload ===")
    
    # Get initial stats
    plugin = plugin_registry.get_plugin("mock_llm")
    
    # Make some requests
    for _ in range(3):
        plugin.generate("test")
    
    usage_before = plugin.metadata.usage_count
    print(f"Usage before reload: {usage_before}")
    
    # Reload
    success = plugin_registry.reload_plugin("mock_llm")
    print(f"Reload: {'OK' if success else 'FAILED'}")
    assert success, "reload_plugin debería recargar mock_llm"
    assert usage_before >= 3, "el uso previo debería haberse contabilizado"

    # El registro comparte su metadata con la instancia (registry.py), de modo
    # que las estadísticas de uso sobreviven a la recarga por diseño.
    plugin = plugin_registry.get_plugin("mock_llm")
    usage_after = plugin.metadata.usage_count if plugin else 0
    print(f"Usage after reload: {usage_after}")
    assert plugin is not None, "mock_llm debería seguir disponible tras recargar"
    assert usage_after == usage_before, "las estadísticas de uso se conservan al recargar"
    assert "simulad" in plugin.generate("test").lower() or \
        "mock" in plugin.generate("test").lower(), \
        "el plugin recargado debería seguir respondiendo"

    return True


def test_dashboard():
    """Test dashboard functionality."""
    print("\n=== Testing Dashboard ===")
    
    # Record some requests/errors
    dashboard.record_request("mock_llm")
    dashboard.record_request("mock_llm")
    dashboard.record_error("mock_llm")
    dashboard.record_request("mock_search")
    
    # Print CLI dashboard
    dashboard.print_cli_dashboard()
    
    # Get health summary
    health = dashboard.health_summary()
    print(f"\nHealth: {health['status']}")
    print(f"Error rate: {health['error_rate']:.2%}")
    assert "status" in health and "error_rate" in health, \
        "el resumen de salud debería incluir estado y tasa de error"
    assert health["error_rate"] > 0, "el error registrado debería aparecer en la tasa"

    # Export JSON
    json_output = dashboard.export_json()
    print(f"\nJSON export length: {len(json_output)} chars")
    assert "mock_llm" in json_output, "el export JSON debería incluir los plugins registrados"

    return True


def test_config_loading():
    """Test configuration file loading."""
    print("\n=== Testing Config Loading ===")
    
    # The config should be loaded automatically
    plugins = plugin_registry.list_plugins()
    for p in plugins:
        print(f"  {p['name']}: enabled={p.get('active', False)}")
    assert plugins, "la configuración debería registrar al menos un plugin"
    assert all("name" in p for p in plugins), \
        "cada plugin registrado debería tener nombre"

    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("PLUGIN SYSTEM TEST SUITE")
    print("=" * 60)
    
    try:
        test_discovery()
        test_load_llm_plugins()
        test_load_search_plugins()
        test_active_providers()
        test_plugin_execution()
        test_hot_reload()
        test_dashboard()
        test_config_loading()
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED ✓")
        print("=" * 60)
        return 0
        
    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())