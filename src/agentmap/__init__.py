# src/agentmap/__init__.py
"""
AgentMap: Build and deploy LangGraph workflows from CSV files.

This package provides clean architecture with separated concerns:
- Models: Domain entities and validation
- Services: Business logic and orchestration
- Agents: Execution units for business logic processing
- Core: Application entry points (CLI, API, handlers)
- Infrastructure: External integrations and persistence
- DI: Dependency injection and service wiring
"""

# Lazy imports using __getattr__ to avoid 12.85s DI container initialization
# at module load time. Imports are deferred until actually accessed.

import importlib

# Map module paths to the names they export
_LAZY_IMPORTS = {
    # CLI and serverless handlers
    "agentmap.deployment.cli": ["main_cli"],
    "agentmap.deployment.serverless.aws_lambda": ["lambda_handler"],
    "agentmap.deployment.serverless.azure_functions": ["azure_http_handler"],
    "agentmap.deployment.serverless.gcp_functions": ["gcp_http_handler"],
    # Core service adapter
    "agentmap.deployment.service_adapter": ["ServiceAdapter", "create_service_adapter"],
    # Runtime API exceptions
    "agentmap.exceptions.runtime_exceptions": [
        "AgentMapError",
        "AgentMapNotInitialized",
        "GraphNotFound",
        "InvalidInputs",
    ],
    # Runtime API functions (triggers DI container init)
    "agentmap.runtime_api": [
        "agentmap_initialize",
        "ensure_initialized",
        "run_workflow",
        "list_graphs",
        "resume_workflow",
    ],
}

# Invert mapping: name -> module path for O(1) lookup
_NAME_TO_MODULE = {
    name: module for module, names in _LAZY_IMPORTS.items() for name in names
}


def __getattr__(name: str):
    """Lazy import handler for AgentMap exports."""
    if module_path := _NAME_TO_MODULE.get(name):
        module = importlib.import_module(module_path)
        return getattr(module, name)

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__author__ = "John Welborn"
__license__ = "MIT"
__copyright__ = "Copyright 2025 John Welborn"
__description__ = "A Python package for creating LangGraph maps from CSV files for agentic ai workflows."

__all__ = [
    # Core service adapter
    "ServiceAdapter",
    "create_service_adapter",
    # CLI and serverless handlers
    "main_cli",
    "lambda_handler",
    "gcp_http_handler",
    "azure_http_handler",
    # Runtime API
    "agentmap_initialize",  # Recommended for external apps
    "ensure_initialized",  # Internal/legacy name
    "run_workflow",
    "list_graphs",
    "resume_workflow",
    # Runtime API exceptions
    "AgentMapError",
    "AgentMapNotInitialized",
    "GraphNotFound",
    "InvalidInputs",
]
