"""
Plugin System for Deep Research System.

Provides hot-swappable providers, declarative configuration, and a monitoring dashboard.
"""

from .interfaces import CorePlugin, LLMProviderPlugin, SearchProviderPlugin
from .registry import PluginRegistry, plugin_registry

__all__ = [
    "CorePlugin",
    "LLMProviderPlugin",
    "PluginRegistry",
    "SearchProviderPlugin",
    "plugin_registry",
]