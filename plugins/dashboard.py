"""
Plugin Dashboard for Deep Research System.

Provides CLI and data structures for monitoring plugin health, performance, and usage.
"""

import time
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

from .registry import plugin_registry


@dataclass
class DashboardMetrics:
    """Aggregated metrics for the dashboard."""
    timestamp: float
    total_plugins: int
    loaded_plugins: int
    active_llm: Optional[str]
    active_search: Optional[str]
    total_requests: int
    total_errors: int
    plugins: List[Dict[str, Any]]


class PluginDashboard:
    """Dashboard for monitoring plugin system health and performance."""

    def __init__(self, registry=None):
        self.registry = registry or plugin_registry
        self._start_time = time.time()
        self._request_counts: Dict[str, int] = {}
        self._error_counts: Dict[str, int] = {}

    def record_request(self, plugin_name: str) -> None:
        """Record a request to a plugin."""
        self._request_counts[plugin_name] = self._request_counts.get(plugin_name, 0) + 1

    def record_error(self, plugin_name: str) -> None:
        """Record an error from a plugin."""
        self._error_counts[plugin_name] = self._error_counts.get(plugin_name, 0) + 1

    def get_metrics(self) -> DashboardMetrics:
        """Get current dashboard metrics."""
        plugins_data = self.registry.get_dashboard_data()
        
        total_requests = sum(self._request_counts.values())
        total_errors = sum(self._error_counts.values())
        
        # Enhance plugin data with request/error counts
        for plugin in plugins_data["plugins"]:
            name = plugin["name"]
            plugin["requests"] = self._request_counts.get(name, 0)
            plugin["errors"] = self._error_counts.get(name, 0)
            plugin["uptime"] = time.time() - self._start_time if plugin["status"] == "loaded" else 0

        return DashboardMetrics(
            timestamp=time.time(),
            total_plugins=plugins_data["total_plugins"],
            loaded_plugins=plugins_data["loaded_plugins"],
            active_llm=plugins_data["active_llm"],
            active_search=plugins_data["active_search"],
            total_requests=total_requests,
            total_errors=total_errors,
            plugins=plugins_data["plugins"],
        )

    def print_cli_dashboard(self) -> None:
        """Print a CLI-friendly dashboard."""
        metrics = self.get_metrics()
        
        print("\n" + "=" * 70)
        print("PLUGIN SYSTEM DASHBOARD")
        print("=" * 70)
        print(f"Uptime: {time.time() - self._start_time:.1f}s")
        print(f"Total Plugins: {metrics.total_plugins} | Loaded: {metrics.loaded_plugins}")
        print(f"Active LLM: {metrics.active_llm or 'N/A'}")
        print(f"Active Search: {metrics.active_search or 'N/A'}")
        print(f"Total Requests: {metrics.total_requests} | Errors: {metrics.total_errors}")
        print("-" * 70)
        
        if not metrics.plugins:
            print("No plugins discovered.")
            return
        
        print(f"{'NAME':<20} {'TYPE':<15} {'STATUS':<12} {'REQS':>6} {'ERRS':>6} {'ACTIVE':>6}")
        print("-" * 70)
        
        for p in metrics.plugins:
            status = p["status"]
            if p.get("active"):
                status += " ★"
            print(f"{p['name']:<20} {p['type']:<15} {status:<12} "
                  f"{p.get('requests', 0):>6} {p.get('errors', 0):>6} "
                  f"{'★' if p.get('active') else '':>6}")
        
        print("=" * 70)

    def export_json(self) -> str:
        """Export dashboard data as JSON."""
        metrics = self.get_metrics()
        return json.dumps(asdict(metrics), indent=2)

    def health_summary(self) -> Dict[str, Any]:
        """Get a health summary for monitoring systems."""
        metrics = self.get_metrics()
        
        healthy = sum(1 for p in metrics.plugins if p["status"] == "loaded")
        degraded = sum(1 for p in metrics.plugins if p["status"] == "error")
        unloaded = sum(1 for p in metrics.plugins if p["status"] == "unloaded")
        
        return {
            "status": "healthy" if degraded == 0 else "degraded",
            "healthy_plugins": healthy,
            "degraded_plugins": degraded,
            "unloaded_plugins": unloaded,
            "active_llm": metrics.active_llm,
            "active_search": metrics.active_search,
            "total_requests": metrics.total_requests,
            "error_rate": metrics.total_errors / max(metrics.total_requests, 1),
            "uptime_seconds": time.time() - self._start_time,
        }


# Global dashboard instance
dashboard = PluginDashboard()