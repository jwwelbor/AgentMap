"""Composable container parts used by the AgentMap DI container.

Container parts are loaded lazily via __getattr__ to improve startup performance.
Direct imports from individual modules (e.g., from .core import CoreContainer)
bypass this lazy loading and load immediately.
"""

# Lazy loading mapping
_CONTAINER_MODULES = {
    "CoreContainer": "core",
    "StorageContainer": "storage",
    "BootstrapContainer": "bootstrap",
    "LLMContainer": "llm",
    "HostRegistryContainer": "host_registry",
    "GraphCoreContainer": "graph_core",
    "GraphAgentContainer": "graph_agent",
}

# Cache for loaded containers
_loaded_containers = {}


def __getattr__(name: str):
    """Lazy load container parts on demand."""
    if name in _CONTAINER_MODULES:
        if name not in _loaded_containers:
            module_name = _CONTAINER_MODULES[name]
            # Import the specific module
            import importlib

            module = importlib.import_module(f".{module_name}", __package__)
            _loaded_containers[name] = getattr(module, name)
        return _loaded_containers[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    """Support dir() for discoverability."""
    return list(_CONTAINER_MODULES.keys())


__all__ = [
    "CoreContainer",
    "StorageContainer",
    "BootstrapContainer",
    "LLMContainer",
    "HostRegistryContainer",
    "GraphCoreContainer",
    "GraphAgentContainer",
]
