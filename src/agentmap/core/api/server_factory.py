"""
Generic API server factory for AgentMap.

This module provides a framework-agnostic interface for creating API servers.
It serves as the orchestration layer that delegates to specific infrastructure
implementations while maintaining clean architecture principles.
"""

from typing import Any, Dict, Optional, Protocol

from agentmap.di import ApplicationContainer


class APIServer(Protocol):
    """Protocol defining the interface for all API server implementations."""

    def __init__(self, container: ApplicationContainer) -> None:
        """Initialize server with dependency injection container."""
        ...

    def create_app(self) -> Any:
        """Create and configure the application instance."""
        ...

    def run(self, host: str = "0.0.0.0", port: int = 8000, **kwargs) -> None:
        """Run the server with specified configuration."""
        ...


def create_api_server(
    container: ApplicationContainer,
    server_type: str = "fastapi",
    config: Optional[Dict[str, Any]] = None,
) -> APIServer:
    """
    Create an API server instance based on the specified type.

    This factory method provides a clean interface for creating different
    types of API servers while keeping the core layer independent of
    specific framework implementations.

    Args:
        container: Dependency injection container
        server_type: Type of server to create (default: "fastapi")
        config: Optional server-specific configuration

    Returns:
        API server instance implementing the APIServer protocol

    Raises:
        ValueError: If server_type is not supported
    """
    if server_type == "fastapi":
        from agentmap.infrastructure.api.fastapi.server import FastAPIServer

        return FastAPIServer(container, config=config)

    # Future extension points for other server types
    # elif server_type == "graphql":
    #     from agentmap.infrastructure.api.graphql.server import GraphQLServer
    #     return GraphQLServer(container, config=config)
    # elif server_type == "grpc":
    #     from agentmap.infrastructure.api.grpc.server import GRPCServer
    #     return GRPCServer(container, config=config)

    raise ValueError(
        f"Unsupported server type: {server_type}. " f"Supported types: fastapi"
    )


def create_default_api_server(container: ApplicationContainer) -> APIServer:
    """
    Create the default API server for AgentMap.

    This convenience method creates a FastAPI server with default configuration.

    Args:
        container: Dependency injection container

    Returns:
        Default API server instance
    """
    return create_api_server(container, server_type="fastapi")


# Re-export the protocol for type hints
__all__ = ["APIServer", "create_api_server", "create_default_api_server"]
