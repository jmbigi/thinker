"""
Plugin interfaces for the Deep Research System.

All plugins must implement one of these interfaces for type safety and hot-swappability.
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List
from enum import Enum


class PluginType(Enum):
    """Types of plugins supported by the system."""
    LLM_PROVIDER = "llm_provider"
    SEARCH_PROVIDER = "search_provider"
    CORE = "core"


class PluginStatus(Enum):
    """Runtime status of a plugin."""
    UNLOADED = "unloaded"
    LOADING = "loading"
    LOADED = "loaded"
    ACTIVE = "active"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass
class PluginMetadata:
    """Metadata for a plugin."""
    name: str
    version: str
    plugin_type: PluginType
    description: str = ""
    author: str = ""
    dependencies: List[str] = field(default_factory=list)
    config_schema: Dict[str, Any] = field(default_factory=dict)
    status: PluginStatus = PluginStatus.UNLOADED
    error_message: str = ""
    load_time: float = 0.0
    last_used: float = 0.0
    usage_count: int = 0


@dataclass
class PluginConfig:
    """Runtime configuration for a plugin instance."""
    enabled: bool = True
    priority: int = 0  # Higher = preferred
    params: Dict[str, Any] = field(default_factory=dict)


class PluginBase(ABC):
    """Base class for all plugins."""

    def __init__(self, config: PluginConfig = None):
        self.config = config or PluginConfig()
        self.metadata = self._get_metadata()
        self._initialized = False

    def _get_metadata(self) -> PluginMetadata:
        """Return plugin metadata. Override in subclasses."""
        return PluginMetadata(
            name=self.__class__.__name__,
            version="0.0.0",
            plugin_type=PluginType.CORE,
            description="Base plugin",
        )

    def initialize(self) -> bool:
        """Initialize the plugin. Return True on success."""
        self._initialized = True
        return True

    def shutdown(self) -> None:
        """Clean shutdown of the plugin."""
        self._initialized = False

    def health_check(self) -> Dict[str, Any]:
        """Return health status. Override for custom checks."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "plugin": self.metadata.name,
            "version": self.metadata.version,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Return usage statistics."""
        return {
            "name": self.metadata.name,
            "version": self.metadata.version,
            "type": self.metadata.plugin_type.value,
            "status": self.metadata.status.value,
            "usage_count": self.metadata.usage_count,
            "load_time": self.metadata.load_time,
            "last_used": self.metadata.last_used,
            "error_message": self.metadata.error_message,
        }


class LLMProviderPlugin(PluginBase):
    """Interface for LLM provider plugins."""

    def __init__(self, config: PluginConfig = None):
        super().__init__(config)
        self.metadata.plugin_type = PluginType.LLM_PROVIDER

    @abstractmethod
    def generate(self, prompt: str, model: str = None, **kwargs) -> str:
        """Generate a response from the LLM."""
        pass

    @abstractmethod
    def get_available_models(self) -> List[str]:
        """Return list of available model names."""
        pass

    @abstractmethod
    def estimate_cost(self, prompt: str, model: str = None) -> float:
        """Estimate cost in USD for a prompt. Return 0 for free models."""
        pass


class SearchProviderPlugin(PluginBase):
    """Interface for search provider plugins.

    El método `search` se implementa UNA vez aquí (validación, métricas y
    límite común); el plugin solo asigna `self._search` en `initialize()`.
    """

    def __init__(self, config: PluginConfig = None):
        super().__init__(config)
        self.metadata.plugin_type = PluginType.SEARCH_PROVIDER
        self._search = None

    def search(self, query: str, max_results: int = None) -> List[Dict[str, Any]]:
        """Perform a web search and return results.

        `max_results` explícito tiene prioridad; si es `None` se usa
        `params.max_results` (defecto 5).
        """
        if not self._initialized or self._search is None:
            raise RuntimeError(f"{self.metadata.name} not initialized")
        self.metadata.usage_count += 1
        self.metadata.last_used = time.time()
        limite = getattr(self, "_max_results", 5) if max_results is None else max_results
        return self._search.search(query, limite)

    @abstractmethod
    def get_source_name(self) -> str:
        """Return the name of the search source (e.g., 'DuckDuckGo', 'Wikipedia')."""
        pass


class CorePlugin(PluginBase):
    """Interface for core system extension plugins."""

    def __init__(self, config: PluginConfig = None):
        super().__init__(config)
        self.metadata.plugin_type = PluginType.CORE

    @abstractmethod
    def get_hooks(self) -> Dict[str, Callable]:
        """
        Return a dict of hook_name -> callable.
        
        Supported hooks:
        - 'pre_research': called before research starts
        - 'post_research': called after research completes
        - 'pre_thinking_step': called before each thinking step
        - 'post_thinking_step': called after each thinking step
        - 'pre_claim_extraction': called before claim extraction
        - 'post_claim_extraction': called after claim extraction
        - 'pre_evaluation': called before evidence evaluation
        - 'post_evaluation': called after evidence evaluation
        - 'pre_report': called before report generation
        - 'post_report': called after report generation
        """
        pass