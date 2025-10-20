"""
FastAPI server using the runtime facade pattern.

This module follows SPEC-DEP-001 by using only the runtime facade and
providing a clean HTTP interface for workflow operations.
"""

import sys
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, Optional

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agentmap.exceptions.runtime_exceptions import (
    AgentMapNotInitialized,
    GraphNotFound,
    InvalidInputs,
)

# ✅ FACADE PATTERN: Only import from runtime facade
from agentmap.runtime_api import ensure_initialized, get_container


# Legacy Response Models (for backward compatibility)
class AgentsInfoResponse(BaseModel):
    """Response model for agent information (legacy endpoint)."""

    core_agents: bool
    llm_agents: bool
    storage_agents: bool
    install_instructions: Dict[str, str]


def create_lifespan(config_file: Optional[str] = None):
    """Factory function to create lifespan with config file."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """
        FastAPI lifespan hook following SPEC-RUN-002.

        Calls ensure_initialized() once at startup and stores the container
        in app.state for use by dependencies.
        """
        try:
            # ✅ FACADE PATTERN: Use only runtime facade for initialization
            # ✅ FIX: Pass config_file to ensure_initialized
            ensure_initialized(config_file=config_file)

            # ✅ CRITICAL FIX: Store container in app.state for dependencies.py
            container = get_container()
            app.state.container = container

            # ✅ FIX: Pre-warm critical services to prevent race conditions
            # TestClient may send requests immediately, so ensure services are ready
            try:
                _ = container.app_config_service()
                _ = container.auth_service()
            except Exception:
                # Services will be initialized on first use if pre-warm fails
                pass

            print("AgentMap runtime initialized successfully")
            yield
        except Exception as e:
            print(f"Failed to initialize AgentMap runtime: {e}")
            raise
        finally:
            print("AgentMap runtime shutting down")

    return lifespan


class FastAPIServer:
    """FastAPI server using facade pattern only."""

    def __init__(self, config_file: Optional[str] = None):
        """Initialize FastAPI server using facade pattern."""
        self.config_file = config_file
        self.app = self.create_app()

    def create_app(self) -> FastAPI:
        """Create FastAPI app with facade-backed routes."""
        app = FastAPI(
            title="AgentMap Workflow Automation API",
            description=self._get_api_description(),
            version="2.0",
            lifespan=create_lifespan(
                self.config_file
            ),  # ✅ Pass config_file to lifespan
            terms_of_service="https://github.com/jwwelbor/AgentMap",
            contact={
                "name": "AgentMap Support",
                "url": "https://github.com/jwwelbor/AgentMap/issues",
            },
            license_info={
                "name": "MIT License",
                "url": "https://github.com/jwwelbor/AgentMap/blob/main/LICENSE",
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

        # Store config file in app state for routes that need it
        app.state.config_file = self.config_file

        # Add global exception handlers per SPEC-EXC-000
        self._add_exception_handlers(app)

        # Add routes
        self._add_routes(app)

        return app

    def _add_exception_handlers(self, app: FastAPI):
        """Add global exception handlers per SPEC-EXC-000."""
        from fastapi import Request
        from fastapi.responses import JSONResponse

        @app.exception_handler(GraphNotFound)
        async def graph_not_found_handler(request: Request, exc: GraphNotFound):
            return JSONResponse(
                status_code=404,
                content={
                    "error": "Graph not found",
                    "message": str(exc),
                    "type": "GraphNotFound",
                },
            )

        @app.exception_handler(InvalidInputs)
        async def invalid_inputs_handler(request: Request, exc: InvalidInputs):
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Invalid inputs",
                    "message": str(exc),
                    "type": "InvalidInputs",
                },
            )

        @app.exception_handler(AgentMapNotInitialized)
        async def not_initialized_handler(
            request: Request, exc: AgentMapNotInitialized
        ):
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Service unavailable",
                    "message": str(exc),
                    "type": "AgentMapNotInitialized",
                },
            )

    def _get_api_description(self) -> str:
        """Get comprehensive API description for OpenAPI documentation."""
        return """
## AgentMap Workflow Automation API

The AgentMap API provides programmatic access to workflow execution, validation, and management capabilities.
This RESTful API supports both standalone operation and embedded integration within larger applications.

### Key Features

- **Workflow Execution**: Run and resume workflows using the runtime facade
- **Validation**: Validate workflows and configurations
- **Graph Operations**: List and manage available graphs
- **System Diagnostics**: Check system health and dependencies

### Authentication

The API supports multiple authentication modes:

- **Public Mode**: No authentication required (default for embedded usage)
- **API Key**: Use `X-API-Key` header for server-to-server integration
- **Bearer Token**: Use `Authorization: Bearer <token>` for user-based access

### Response Format

All responses follow consistent JSON structure with appropriate HTTP status codes.
Error responses include detailed validation information and suggestions for resolution.

### Getting Started

1. Check API health: `GET /health`
2. List available workflows: `GET /graphs`
3. Run a workflow: `POST /run/{graph_name}`
4. Get system information: `GET /diagnose`
"""

    def _get_openapi_tags(self) -> list:
        """Get OpenAPI tags for endpoint organization."""
        return [
            {
                "name": "Execution",
                "description": "Workflow execution and resumption endpoints",
                "externalDocs": {
                    "description": "Execution Guide",
                    "url": "https://jwwelbor.github.io/AgentMap/docs/intro",
                },
            },
            {
                "name": "Information & Diagnostics",
                "description": "System information, health checks, and diagnostics",
            },
        ]

    def _add_routes(self, app: FastAPI):
        """Add facade-based routes to the FastAPI app."""

        # Import facade-based route modules (these need to be converted)
        try:
            from agentmap.deployment.http.api.routes.admin import router as admin_router
            from agentmap.deployment.http.api.routes.execute import (
                router as execution_router,
            )
            from agentmap.deployment.http.api.routes.workflows import (
                router as workflow_router,
            )

            # Include existing routers
            app.include_router(execution_router)
            app.include_router(workflow_router)
            app.include_router(admin_router)
        except ImportError as e:
            print(f"Warning: Could not import route modules: {e}")

        # Simple facade-based endpoints
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
            description="Get API information and links to interactive documentation",
            response_description="API information with links to standard FastAPI documentation",
            tags=["Information & Diagnostics"],
        )
        async def root():
            """
            **Get AgentMap API Information**

            Returns basic API information and directs users to the standard
            FastAPI-generated documentation endpoints for complete API details.
            """
            return {
                "message": "AgentMap Workflow Automation API",
                "version": "2.0",
                "description": "Workflow execution and management using the runtime facade pattern",
                "documentation": {
                    "interactive_docs": "/docs",
                    "redoc_docs": "/redoc",
                    "openapi_schema": "/openapi.json",
                },
                "authentication": {
                    "modes": ["public", "api_key", "bearer_token"],
                    "details": "See /docs for authentication requirements per endpoint",
                },
                "quick_start": {
                    "1_view_documentation": "GET /docs",
                    "2_check_health": "GET /health",
                    "3_list_workflows": "GET /workflows",
                    "4_run_workflow": "POST /execute/{workflow}/{graph}",
                },
                "repository_structure": {
                    "workflows": "CSV files define workflow graphs",
                    "functions": "Custom function implementations",
                    "agents": "Custom agent implementations",
                },
            }


def create_fastapi_app(config_file: Optional[str] = None) -> FastAPI:
    """
    Factory function to create FastAPI app using facade pattern.

    Args:
        config_file: Optional configuration file path

    Returns:
        FastAPI app instance
    """
    server = FastAPIServer(config_file)
    return server.app


def create_sub_application(
    config_file: Optional[str] = None,
    title: str = "AgentMap API",
    prefix: str = "",
) -> FastAPI:
    """
    Create FastAPI app configured for mounting as a sub-application.

    This function creates a FastAPI app suitable for mounting with app.mount()
    in larger applications using the facade pattern.

    Args:
        config_file: Optional configuration file path
        title: API title for OpenAPI docs
        prefix: URL prefix for the sub-application

    Returns:
        FastAPI app instance configured for sub-application mounting

    Example:
        ```python
        # In host application
        from agentmap.deployment.http.api.server import create_sub_application

        main_app = FastAPI(title="My Application")
        agentmap_app = create_sub_application(title="AgentMap Integration")
        main_app.mount("/agentmap", agentmap_app)
        ```
    """
    # Create FastAPI app with custom configuration for sub-application
    app = FastAPI(
        title=title,
        description="AgentMap workflow execution and management API",
        version="2.0",
        lifespan=create_lifespan(config_file),  # ✅ Pass config_file to lifespan
        openapi_url=f"{prefix}/openapi.json" if prefix else "/openapi.json",
        docs_url=f"{prefix}/docs" if prefix else "/docs",
        redoc_url=f"{prefix}/redoc" if prefix else "/redoc",
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Store config file in app state
    app.state.config_file = config_file

    # Note: Container will be set by lifespan hook during initialization

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
            "facade_pattern": "This API follows SPEC-DEP-001 facade pattern",
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
    Run the FastAPI server using facade pattern.

    Args:
        host: Host to bind to
        port: Port to bind to
        reload: Enable auto-reload
        config_file: Path to custom config file
    """
    # Create FastAPI server using facade pattern
    server = FastAPIServer(config_file=config_file)
    app = server.app

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
