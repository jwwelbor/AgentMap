"""
FastAPI server using services through dependency injection.

This module provides FastAPI endpoints that maintain compatibility with
existing API interfaces while using the new service architecture.
"""

import sys
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any
import uvicorn

from agentmap.di import initialize_di, ApplicationContainer
from agentmap.core.adapters import create_service_adapter


# Request/Response Models
class GraphRunRequest(BaseModel):
    """Request model for running a graph."""
    graph: Optional[str] = None  # Optional graph name (defaults to first graph in CSV)
    csv: Optional[str] = None    # Optional CSV path override
    state: Dict[str, Any] = {}   # Initial state (defaults to empty dict)
    autocompile: bool = False    # Whether to autocompile the graph if missing
    execution_id: Optional[str] = None  # Optional execution ID for tracking


class GraphRunResponse(BaseModel):
    """Response model for graph execution."""
    success: bool
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_id: Optional[str] = None
    execution_time: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class AgentsInfoResponse(BaseModel):
    """Response model for agent information."""
    core_agents: bool
    llm_agents: bool
    storage_agents: bool
    install_instructions: Dict[str, str]


class SystemInfoResponse(BaseModel):
    """Response model for system information."""
    agentmap_version: str
    configuration: Dict[str, Any]
    paths: Dict[str, str]


# Dependency injection for FastAPI
def get_container() -> ApplicationContainer:
    """Get DI container for FastAPI dependency injection."""
    return initialize_di()


def get_service_adapter(container: ApplicationContainer = Depends(get_container)):
    """Get service adapter for FastAPI dependency injection."""
    return create_service_adapter(container)


class FastAPIServer:
    """FastAPI server using services through DI."""
    
    def __init__(self, container: Optional[ApplicationContainer] = None):
        """Initialize FastAPI server."""
        self.container = container or initialize_di()
        self.adapter = create_service_adapter(self.container)
        self.app = self.create_app()
    
    def create_app(self) -> FastAPI:
        """Create FastAPI app with service-backed routes."""
        app = FastAPI(
            title="AgentMap Graph API",
            description="AgentMap API for graph execution and management",
            version="2.0"
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
    
    def _add_routes(self, app: FastAPI):
        """Add all routes to the FastAPI app."""
        
        @app.post("/run", response_model=GraphRunResponse)
        async def run_graph_endpoint(
            request: GraphRunRequest,
            adapter = Depends(get_service_adapter)
        ):
            """Run a graph with the provided parameters."""
            try:
                # Get services
                graph_runner_service, _, logging_service = adapter.initialize_services()
                logger = logging_service.get_logger("agentmap.api.run")
                
                # Create run options
                run_options = adapter.create_run_options(
                    graph=request.graph,
                    csv=request.csv,
                    state=request.state,
                    autocompile=request.autocompile,
                    execution_id=request.execution_id
                )
                
                logger.info(f"API executing graph: {request.graph or 'default'}")
                
                # Execute graph
                result = graph_runner_service.run_graph(run_options)
                
                # Convert to response format
                if result.success:
                    output_data = adapter.extract_result_state(result)
                    return GraphRunResponse(
                        success=True,
                        output=output_data["final_state"],
                        execution_id=result.execution_id,
                        execution_time=result.execution_time,
                        metadata=output_data["metadata"]
                    )
                else:
                    return GraphRunResponse(
                        success=False,
                        error=result.error_message,
                        execution_id=result.execution_id,
                        execution_time=result.execution_time
                    )
                    
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            except FileNotFoundError as e:
                raise HTTPException(status_code=404, detail=str(e))
            except Exception as e:
                logger.error(f"API execution error: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @app.get("/agents/available", response_model=AgentsInfoResponse)
        async def list_available_agents():
            """Return information about available agents in this environment."""
            from agentmap.services.features_registry_service import FeaturesRegistryService, is_storage_enabled
            
            return AgentsInfoResponse(
                core_agents=True,  # Always available
                llm_agents=self.features_registry.is_feature_enabled("llm")(),
                storage_agents=is_storage_enabled(),
                install_instructions={
                    "llm": "pip install agentmap[llm]",
                    "storage": "pip install agentmap[storage]",
                    "all": "pip install agentmap[all]"
                }
            )
        
        @app.get("/info", response_model=SystemInfoResponse)
        async def get_system_info(adapter = Depends(get_service_adapter)):
            """Get system information and configuration."""
            from agentmap.core.cli.diagnostic_commands import get_system_info_command
            
            try:
                info = get_system_info_command()
                return SystemInfoResponse(**info)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to get system info: {e}")
        
        @app.get("/health")
        async def health_check():
            """Health check endpoint."""
            return {"status": "healthy", "service": "agentmap-api"}
        
        @app.get("/")
        async def root():
            """Root endpoint with API information."""
            return {
                "message": "AgentMap Graph API",
                "version": "2.0",
                "endpoints": [
                    "/run - Execute graphs",
                    "/agents/available - List available agents",
                    "/info - System information",
                    "/health - Health check"
                ]
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


def run_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    reload: bool = False,
    config_file: Optional[str] = None
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
            host=args.host,
            port=args.port,
            reload=args.reload,
            config_file=args.config
        )
    except KeyboardInterrupt:
        print("\nServer stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
