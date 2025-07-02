"""
FastAPI server using services through dependency injection.

This module provides FastAPI endpoints that maintain compatibility with
existing API interfaces while using the new service architecture.

Refactored to follow clean architecture patterns with proper separation
of infrastructure concerns.
"""

import sys
from datetime import datetime
from typing import Any, Dict, Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agentmap.core.adapters import create_service_adapter
from agentmap.di import ApplicationContainer, initialize_di
from agentmap.infrastructure.api.fastapi.dependencies import FastAPIDependencyAdapter
from agentmap.infrastructure.api.fastapi.middleware.auth import FastAPIAuthAdapter


# Legacy Response Models (for backward compatibility)
class AgentsInfoResponse(BaseModel):
    """Response model for agent information (legacy endpoint)."""

    core_agents: bool
    llm_agents: bool
    storage_agents: bool
    install_instructions: Dict[str, str]


class FastAPIServer:
    """FastAPI server using services through DI with clean architecture."""

    def __init__(self, container: Optional[ApplicationContainer] = None):
        """Initialize FastAPI server with proper adapters."""
        self.container = container or initialize_di()
        self.adapter = create_service_adapter(self.container)

        # Create dependency adapter for FastAPI-specific dependency injection
        self.dependency_adapter = FastAPIDependencyAdapter(self.container)

        # Create auth adapter for FastAPI-specific authentication
        auth_service = self.container.auth_service()
        self.auth_adapter = FastAPIAuthAdapter(auth_service)

        self.app = self.create_app()

    def create_app(self) -> FastAPI:
        """Create FastAPI app with service-backed routes."""
        app = FastAPI(
            title="AgentMap Workflow Automation API",
            description=self._get_api_description(),
            version="2.0",
            terms_of_service="https://github.com/Agentic-Insights/AgentMap",
            contact={
                "name": "AgentMap Support",
                "url": "https://github.com/Agentic-Insights/AgentMap/issues",
            },
            license_info={
                "name": "MIT License",
                "url": "https://github.com/Agentic-Insights/AgentMap/blob/main/LICENSE",
            },
            openapi_tags=self._get_openapi_tags(),
            servers=[
                {"url": "http://localhost:8000", "description": "Development server"},
                {
                    "url": "https://api.agentmap.dev",
                    "description": "Production server (if hosted)",
                },
            ],
        )

        # CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Add routes
        self._add_routes(app)

        return app

    def _get_api_description(self) -> str:
        """Get comprehensive API description for OpenAPI documentation."""
        return """
## AgentMap Workflow Automation API

The AgentMap API provides programmatic access to workflow execution, validation, and management capabilities.
This RESTful API supports both standalone operation and embedded integration within larger applications.

### Key Features

- **Workflow Execution**: Run and resume workflows stored in CSV repository
- **Validation**: Validate CSV workflow definitions and configuration files  
- **Graph Operations**: Compile, scaffold, and manage workflow graphs
- **Repository Management**: Browse and inspect workflow repository contents
- **System Diagnostics**: Check system health, dependencies, and configuration

### Authentication

The API supports multiple authentication modes:

- **Public Mode**: No authentication required (default for embedded usage)
- **API Key**: Use `X-API-Key` header for server-to-server integration
- **Bearer Token**: Use `Authorization: Bearer <token>` for user-based access

### Workflow Repository Structure

Workflows are stored as CSV files in a configured repository directory:

```
csv_repository/
├── workflow1.csv    # Contains one or more named graphs
├── workflow2.csv    # Each CSV defines nodes, agents, and connections
└── ...
```

### Rate Limiting

API endpoints are rate limited to ensure fair usage:

- **Execution endpoints**: 60 requests per minute
- **Validation endpoints**: 120 requests per minute  
- **Information endpoints**: 300 requests per minute

### Response Format

All responses follow consistent JSON structure with appropriate HTTP status codes.
Error responses include detailed validation information and suggestions for resolution.

### Getting Started

1. Check API health: `GET /health`
2. List available workflows: `GET /workflows`
3. Run a workflow: `POST /execution/{workflow}/{graph}`
4. Get system information: `GET /info/diagnose`
"""

    def _get_openapi_tags(self) -> list:
        """Get OpenAPI tags for endpoint organization."""
        return [
            {
                "name": "Execution",
                "description": "Workflow execution and resumption endpoints",
                "externalDocs": {
                    "description": "Execution Guide",
                    "url": "https://github.com/Agentic-Insights/AgentMap/docs/execution",
                },
            },
            {
                "name": "Workflow Management",
                "description": "Browse and inspect workflows in the CSV repository",
            },
            {
                "name": "Validation",
                "description": "Validate CSV workflow definitions and configuration files",
            },
            {
                "name": "Graph Operations",
                "description": "Graph compilation, scaffolding, and management",
            },
            {
                "name": "Information & Diagnostics",
                "description": "System information, health checks, and diagnostics",
            },
            {
                "name": "Authentication",
                "description": "Authentication and authorization endpoints",
            },
        ]

    def _add_routes(self, app: FastAPI):
        """Add all routes to the FastAPI app using modular routers."""

        # Store adapters in app state for routes to access
        app.state.dependency_adapter = self.dependency_adapter
        app.state.auth_adapter = self.auth_adapter

        # Import routers from infrastructure layer
        from agentmap.infrastructure.api.fastapi.routes.execution import (
            router as execution_router,
        )
        from agentmap.infrastructure.api.fastapi.routes.graph import (
            router as graph_router,
        )
        from agentmap.infrastructure.api.fastapi.routes.info import (
            router as info_router,
        )
        from agentmap.infrastructure.api.fastapi.routes.validation import (
            router as validation_router,
        )
        from agentmap.infrastructure.api.fastapi.routes.workflow import (
            router as workflow_router,
        )

        # Include all router modules
        app.include_router(execution_router)
        app.include_router(workflow_router)
        app.include_router(validation_router)
        app.include_router(graph_router)
        app.include_router(info_router)

        # Keep legacy endpoints for backward compatibility
        @app.get("/agents/available", response_model=AgentsInfoResponse)
        async def list_available_agents():
            """Return information about available agents in this environment."""
            from agentmap.services.features_registry_service import (
                is_storage_enabled,
            )

            return AgentsInfoResponse(
                core_agents=True,  # Always available
                llm_agents=self.container.features_registry_service().is_feature_enabled(
                    "llm"
                ),
                storage_agents=is_storage_enabled(),
                install_instructions={
                    "llm": "pip install agentmap[llm]",
                    "storage": "pip install agentmap[storage]",
                    "all": "pip install agentmap[all]",
                },
            )

        @app.get(
            "/health",
            summary="Health Check",
            description="Basic health check endpoint for monitoring and load balancing",
            response_description="Health status information",
            tags=["Information & Diagnostics"],
        )
        async def health_check():
            """
            **Basic Health Check**
            
            Returns simple health status for monitoring, load balancing, and uptime checks.
            This endpoint is optimized for fast response and minimal resource usage.
            
            **Example Request:**
            ```bash
            curl -X GET "http://localhost:8000/health" \\
                 -H "Accept: application/json"
            ```
            
            **Response Codes:**
            - `200`: Service is healthy and operational
            - `503`: Service is unhealthy or dependencies unavailable
            
            **Authentication:** None required
            """
            return {
                "status": "healthy",
                "service": "agentmap-api",
                "timestamp": datetime.now().isoformat(),
                "version": "2.0",
            }

        @app.get(
            "/",
            summary="API Information",
            description="Get comprehensive API information including available endpoints, authentication options, and getting started guide",
            response_description="API information and endpoint documentation",
            tags=["Information & Diagnostics"],
        )
        async def root():
            """
            **Get AgentMap API Information**
            
            Returns comprehensive information about the API including:
            - Available endpoints and their purposes
            - Authentication configuration
            - Quick start guide with example usage
            - Links to documentation and OpenAPI schema
            
            **Example Request:**
            ```bash
            curl -X GET "http://localhost:8000/" \\
                 -H "Accept: application/json"
            ```
            
            **Authentication:** None required
            """
            return {
                "message": "AgentMap Workflow Automation API",
                "version": "2.0",
                "authentication": {
                    "modes": ["public", "api_key", "bearer_token"],
                    "headers": {
                        "api_key": "X-API-Key: your-api-key",
                        "bearer_token": "Authorization: Bearer your-token",
                    },
                    "embedded_mode": "Authentication disabled for embedded sub-applications",
                },
                "endpoints": {
                    "/workflows": {
                        "description": "Workflow management and repository operations",
                        "methods": ["GET"],
                        "auth_required": False,
                    },
                    "/execution": {
                        "description": "Workflow execution and resumption",
                        "methods": ["POST"],
                        "auth_required": False,
                        "rate_limit": "60/minute",
                    },
                    "/validation": {
                        "description": "CSV and configuration validation",
                        "methods": ["POST"],
                        "auth_required": False,
                        "rate_limit": "120/minute",
                    },
                    "/graph": {
                        "description": "Graph compilation, scaffolding, and operations",
                        "methods": ["GET", "POST"],
                        "auth_required": False,
                    },
                    "/info": {
                        "description": "System information and diagnostics",
                        "methods": ["GET", "DELETE"],
                        "auth_required": False,
                        "rate_limit": "300/minute",
                    },
                },
                "quick_start": {
                    "1_check_health": "GET /health",
                    "2_list_workflows": "GET /workflows",
                    "3_run_workflow": "POST /execution/{workflow}/{graph}",
                    "4_get_diagnostics": "GET /info/diagnose",
                },
                "documentation": {
                    "interactive_docs": "/docs",
                    "redoc": "/redoc",
                    "openapi_schema": "/openapi.json",
                    "github": "https://github.com/Agentic-Insights/AgentMap",
                },
                "repository_structure": {
                    "description": "Workflows stored as CSV files in configured repository",
                    "example_path": "csv_repository/my_workflow.csv",
                    "csv_format": "Each CSV contains GraphName, NodeName, AgentType, etc.",
                },
            }


def create_fastapi_app(container: Optional[ApplicationContainer] = None) -> FastAPI:
    """
    Factory function to create FastAPI app.

    Args:
        container: Optional DI container

    Returns:
        FastAPI app instance
    """
    server = FastAPIServer(container)
    return server.app


def create_sub_application(
    container: Optional[ApplicationContainer] = None,
    title: str = "AgentMap API",
    prefix: str = "",
) -> FastAPI:
    """
    Create FastAPI app configured for mounting as a sub-application.

    This function creates a FastAPI app suitable for mounting with app.mount()
    in larger applications. It includes all AgentMap functionality but allows
    customization of the title and path prefix.

    Args:
        container: Optional DI container
        title: API title for OpenAPI docs
        prefix: URL prefix for the sub-application

    Returns:
        FastAPI app instance configured for sub-application mounting

    Example:
        ```python
        # In host application
        from agentmap.infrastructure.api.fastapi.server import create_sub_application

        main_app = FastAPI(title="My Application")
        agentmap_app = create_sub_application(title="AgentMap Integration")
        main_app.mount("/agentmap", agentmap_app)
        ```
    """
    # Create container if not provided
    if container is None:
        container = initialize_di()

    # Create adapters
    dependency_adapter = FastAPIDependencyAdapter(container)
    auth_service = container.auth_service()
    auth_adapter = FastAPIAuthAdapter(auth_service)

    # Create FastAPI app with custom configuration for sub-application
    app = FastAPI(
        title=title,
        description="AgentMap workflow execution and management API",
        version="2.0",
        openapi_url=f"{prefix}/openapi.json" if prefix else "/openapi.json",
        docs_url=f"{prefix}/docs" if prefix else "/docs",
        redoc_url=f"{prefix}/redoc" if prefix else "/redoc",
    )

    # Note: CORS middleware typically should be configured by the host application
    # to avoid conflicts. If needed for standalone sub-app usage:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Store adapters in app state
    app.state.dependency_adapter = dependency_adapter
    app.state.auth_adapter = auth_adapter

    # Import and add all router modules from infrastructure layer
    from agentmap.infrastructure.api.fastapi.routes.execution import (
        router as execution_router,
    )
    from agentmap.infrastructure.api.fastapi.routes.graph import router as graph_router
    from agentmap.infrastructure.api.fastapi.routes.info import router as info_router
    from agentmap.infrastructure.api.fastapi.routes.validation import (
        router as validation_router,
    )
    from agentmap.infrastructure.api.fastapi.routes.workflow import (
        router as workflow_router,
    )

    app.include_router(execution_router)
    app.include_router(workflow_router)
    app.include_router(validation_router)
    app.include_router(graph_router)
    app.include_router(info_router)

    # Add basic health check and info endpoints
    @app.get("/health")
    async def health_check():
        """Health check endpoint for sub-application."""
        return {"status": "healthy", "service": "agentmap-sub-api"}

    @app.get("/")
    async def sub_app_root():
        """Root endpoint for sub-application."""
        return {
            "message": "AgentMap API Sub-Application",
            "version": "2.0",
            "mounted_at": prefix or "/",
            "routes": {
                "/workflows": "Workflow management and repository operations",
                "/execution": "Workflow execution and resumption",
                "/validation": "CSV and configuration validation",
                "/graph": "Graph compilation, scaffolding, and operations",
                "/info": "System information and diagnostics",
            },
            "docs": f"{prefix}/docs" if prefix else "/docs",
        }

    return app


def run_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    reload: bool = False,
    config_file: Optional[str] = None,
):
    """
    Run the FastAPI server.

    Args:
        host: Host to bind to
        port: Port to bind to
        reload: Enable auto-reload
        config_file: Path to custom config file
    """
    # Initialize DI with config file
    container = initialize_di(config_file)

    # Create app
    app = create_fastapi_app(container)

    # Run with uvicorn
    uvicorn.run(app, host=host, port=port, reload=reload)


def main():
    """Entry point for the AgentMap API server."""
    import argparse

    parser = argparse.ArgumentParser(description="AgentMap API Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--config", help="Path to custom config file")

    args = parser.parse_args()

    try:
        run_server(
            host=args.host, port=args.port, reload=args.reload, config_file=args.config
        )
    except KeyboardInterrupt:
        print("\nServer stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
