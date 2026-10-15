"""
Plugin System CLI.

Command-line interface for managing and monitoring plugins.
"""

import sys
import json
import argparse
from typing import List

from .registry import plugin_registry
from .dashboard import dashboard


def cmd_discover(args: argparse.Namespace) -> int:
    """Discover plugins in plugin directories."""
    count = plugin_registry.discover_plugins()
    print(f"Discovered {count} plugins")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """List all plugins with their status."""
    plugin_type = None
    if args.type:
        from .interfaces import PluginType
        plugin_type = PluginType(args.type)
    
    plugins = plugin_registry.list_plugins(plugin_type)
    
    if args.json:
        print(json.dumps(plugins, indent=2))
        return 0
    
    if not plugins:
        print("No plugins found.")
        return 0
    
    print(f"{'NAME':<20} {'TYPE':<15} {'STATUS':<12} {'VERSION':<10} {'ACTIVE'}")
    print("-" * 70)
    for p in plugins:
        active = "★" if p.get("active") else ""
        print(f"{p['name']:<20} {p['type']:<15} {p['status']:<12} "
              f"{p['version']:<10} {active}")
    return 0


def cmd_load(args: argparse.Namespace) -> int:
    """Load a plugin."""
    if args.all:
        results = plugin_registry.load_all()
        for name, success in results.items():
            status = "OK" if success else "FAILED"
            print(f"  {name}: {status}")
        return 0 if all(results.values()) else 1
    
    if not args.name:
        print("Error: plugin name required", file=sys.stderr)
        return 1
    
    success = plugin_registry.load_plugin(args.name)
    print(f"Load {args.name}: {'OK' if success else 'FAILED'}")
    return 0 if success else 1


def cmd_unload(args: argparse.Namespace) -> int:
    """Unload a plugin."""
    if not args.name:
        print("Error: plugin name required", file=sys.stderr)
        return 1
    
    success = plugin_registry.unload_plugin(args.name)
    print(f"Unload {args.name}: {'OK' if success else 'FAILED'}")
    return 0 if success else 1


def cmd_reload(args: argparse.Namespace) -> int:
    """Hot-reload a plugin."""
    if not args.name:
        print("Error: plugin name required", file=sys.stderr)
        return 1
    
    success = plugin_registry.reload_plugin(args.name)
    print(f"Reload {args.name}: {'OK' if success else 'FAILED'}")
    return 0 if success else 1


def cmd_set_active(args: argparse.Namespace) -> int:
    """Set active provider."""
    if args.type == "llm":
        success = plugin_registry.set_active_llm(args.name)
        print(f"Active LLM: {args.name} {'OK' if success else 'FAILED'}")
    elif args.type == "search":
        success = plugin_registry.set_active_search(args.name)
        print(f"Active Search: {args.name} {'OK' if success else 'FAILED'}")
    else:
        print("Error: type must be 'llm' or 'search'", file=sys.stderr)
        return 1
    return 0 if success else 1


def cmd_dashboard(args: argparse.Namespace) -> int:
    """Show dashboard."""
    if args.json:
        print(dashboard.export_json())
    else:
        dashboard.print_cli_dashboard()
    return 0


def cmd_health(args: argparse.Namespace) -> int:
    """Show health summary."""
    health = dashboard.health_summary()
    if args.json:
        print(json.dumps(health, indent=2))
    else:
        print(f"Status: {health['status']}")
        print(f"Healthy: {health['healthy_plugins']}")
        print(f"Degraded: {health['degraded_plugins']}")
        print(f"Unloaded: {health['unloaded_plugins']}")
        print(f"Active LLM: {health['active_llm'] or 'N/A'}")
        print(f"Active Search: {health['active_search'] or 'N/A'}")
        print(f"Requests: {health['total_requests']}")
        print(f"Error Rate: {health['error_rate']:.2%}")
    return 0


def cmd_test(args: argparse.Namespace) -> int:
    """Test a plugin with a sample request."""
    plugin = plugin_registry.get_plugin(args.name)
    if not plugin:
        print(f"Plugin not loaded: {args.name}", file=sys.stderr)
        return 1
    
    from .interfaces import LLMProviderPlugin, SearchProviderPlugin
    
    if isinstance(plugin, LLMProviderPlugin):
        prompt = args.prompt or "Responde exactamente: OK"
        try:
            result = plugin.generate(prompt)
            print(f"Response: {result[:200]}")
            return 0
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    
    elif isinstance(plugin, SearchProviderPlugin):
        query = args.prompt or "test query"
        try:
            results = plugin.search(query, max_results=3)
            for i, r in enumerate(results):
                print(f"  {i+1}. {r.get('title', 'N/A')}")
                print(f"     {r.get('url', 'N/A')}")
                print(f"     {r.get('snippet', 'N/A')[:100]}")
            return 0
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    
    else:
        print("Plugin type not testable via CLI", file=sys.stderr)
        return 1


def main(argv: List[str] = None) -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(prog="plugins", description="Plugin System CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # discover
    subparsers.add_parser("discover", help="Discover plugins")
    
    # list
    list_parser = subparsers.add_parser("list", help="List plugins")
    list_parser.add_argument("--type", choices=["llm_provider", "search_provider", "core"])
    list_parser.add_argument("--json", action="store_true")
    
    # load
    load_parser = subparsers.add_parser("load", help="Load plugin(s)")
    load_parser.add_argument("name", nargs="?", help="Plugin name")
    load_parser.add_argument("--all", action="store_true", help="Load all enabled plugins")
    
    # unload
    unload_parser = subparsers.add_parser("unload", help="Unload plugin")
    unload_parser.add_argument("name", help="Plugin name")
    
    # reload
    reload_parser = subparsers.add_parser("reload", help="Hot-reload plugin")
    reload_parser.add_argument("name", help="Plugin name")
    
    # set-active
    active_parser = subparsers.add_parser("set-active", help="Set active provider")
    active_parser.add_argument("type", choices=["llm", "search"])
    active_parser.add_argument("name", help="Plugin name")
    
    # dashboard
    dash_parser = subparsers.add_parser("dashboard", help="Show dashboard")
    dash_parser.add_argument("--json", action="store_true")
    
    # health
    health_parser = subparsers.add_parser("health", help="Show health summary")
    health_parser.add_argument("--json", action="store_true")
    
    # test
    test_parser = subparsers.add_parser("test", help="Test a plugin")
    test_parser.add_argument("name", help="Plugin name")
    test_parser.add_argument("--prompt", help="Test prompt/query")
    
    args = parser.parse_args(argv)
    
    # Ensure plugins are discovered first
    plugin_registry.discover_plugins()
    
    commands = {
        "discover": cmd_discover,
        "list": cmd_list,
        "load": cmd_load,
        "unload": cmd_unload,
        "reload": cmd_reload,
        "set-active": cmd_set_active,
        "dashboard": cmd_dashboard,
        "health": cmd_health,
        "test": cmd_test,
    }
    
    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())