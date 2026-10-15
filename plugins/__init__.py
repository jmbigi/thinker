"""
Plugin System for Deep Research System.

Provides hot-swappable providers, declarative configuration, and a monitoring dashboard.
"""

from .registry import PluginRegistry, plugin_registry
from .interfaces import LLMProviderPlugin, SearchProviderPlugin, CorePlugin

__all__ = [
    "PluginRegistry",
    "plugin_registry",
    "LLMProviderPlugin",
    "SearchProviderPlugin",
    "CorePlugin",
]