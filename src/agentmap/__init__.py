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

def __getattr__(name: str):
    """Lazy import handler for AgentMap exports."""
    # CLI and serverless handlers
    if name == "main_cli":
        from agentmap.deployment.cli import main_cli
        return main_cli
    elif name == "lambda_handler":
        from agentmap.deployment.serverless.aws_lambda import lambda_handler
        return lambda_handler
    elif name == "azure_http_handler":
        from agentmap.deployment.serverless.azure_functions import azure_http_handler
        return azure_http_handler
    elif name == "gcp_http_handler":
        from agentmap.deployment.serverless.gcp_functions import gcp_http_handler
        return gcp_http_handler

    # Core service adapter
    elif name == "ServiceAdapter":
        from agentmap.deployment.service_adapter import ServiceAdapter
        return ServiceAdapter
    elif name == "create_service_adapter":
        from agentmap.deployment.service_adapter import create_service_adapter
        return create_service_adapter

    # Runtime API exceptions
    elif name == "AgentMapError":
        from agentmap.exceptions.runtime_exceptions import AgentMapError
        return AgentMapError
    elif name == "AgentMapNotInitialized":
        from agentmap.exceptions.runtime_exceptions import AgentMapNotInitialized
        return AgentMapNotInitialized
    elif name == "GraphNotFound":
        from agentmap.exceptions.runtime_exceptions import GraphNotFound
        return GraphNotFound
    elif name == "InvalidInputs":
        from agentmap.exceptions.runtime_exceptions import InvalidInputs
        return InvalidInputs

    # Runtime API functions (triggers DI container init)
    elif name == "agentmap_initialize":
        from agentmap.runtime_api import agentmap_initialize
        return agentmap_initialize
    elif name == "ensure_initialized":
        from agentmap.runtime_api import ensure_initialized
        return ensure_initialized
    elif name == "run_workflow":
        from agentmap.runtime_api import run_workflow
        return run_workflow
    elif name == "list_graphs":
        from agentmap.runtime_api import list_graphs
        return list_graphs
    elif name == "resume_workflow":
        from agentmap.runtime_api import resume_workflow
        return resume_workflow

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
