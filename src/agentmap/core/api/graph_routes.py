"""
Graph execution routes for FastAPI server.

This module provides graph-specific API endpoints for execution, validation,
and compilation using the new service architecture.
"""

from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from agentmap.di import ApplicationContainer
from agentmap.core.adapters import create_service_adapter


# Request models
class CompileGraphRequest(BaseModel):
    """Request model for graph compilation."""
    graph: Optional[str] = None
    csv: Optional[str] = None
    output_dir: Optional[str] = None
    state_schema: str = "dict"
    validate: bool = True


class ValidateGraphRequest(BaseModel):
    """Request model for graph validation."""
    csv: Optional[str] = None
    no_cache: bool = False


class ScaffoldGraphRequest(BaseModel):
    """Request model for graph scaffolding."""
    graph: Optional[str] = None
    csv: Optional[str] = None
    output_dir: Optional[str] = None
    func_dir: Optional[str] = None


# Response models
class CompileGraphResponse(BaseModel):
    """Response model for graph compilation."""
    success: bool
    bundle_path: Optional[str] = None
    source_path: Optional[str] = None
    compilation_time: Optional[float] = None
    error: Optional[str] = None


class ValidateGraphResponse(BaseModel):
    """Response model for graph validation."""
    success: bool
    has_warnings: bool
    has_errors: bool
    file_path: str
    message: Optional[str] = None


class ScaffoldGraphResponse(BaseModel):
    """Response model for graph scaffolding."""
    success: bool
    scaffolded_count: int
    output_path: str
    functions_path: str


def get_container() -> ApplicationContainer:
    """Get DI container for dependency injection."""
    from agentmap.di import initialize_di
    return initialize_di()


def get_adapter(container: ApplicationContainer = Depends(get_container)):
    """Get service adapter for dependency injection."""
    return create_service_adapter(container)


# Create router
router = APIRouter(prefix="/graph", tags=["Graph Operations"])


@router.post("/compile", response_model=CompileGraphResponse)
async def compile_graph(
    request: CompileGraphRequest,
    adapter = Depends(get_adapter)
):
    """Compile a graph to executable format."""
    try:
        from agentmap.core.cli.run_commands import compile_graph_command
        
        result = compile_graph_command(
            graph=request.graph,
            csv=request.csv,
            output_dir=request.output_dir,
            state_schema=request.state_schema,
            validate_first=request.validate
        )
        
        return CompileGraphResponse(**result)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate", response_model=ValidateGraphResponse)
async def validate_graph(
    request: ValidateGraphRequest,
    adapter = Depends(get_adapter)
):
    """Validate a graph CSV file."""
    try:
        from agentmap.core.cli.validation_commands import validate_csv_command
        
        result = validate_csv_command(
            csv_path=request.csv,
            no_cache=request.no_cache
        )
        
        return ValidateGraphResponse(
            success=result["success"],
            has_warnings=result["has_warnings"],
            has_errors=result["has_errors"],
            file_path=result["file_path"],
            message="Validation completed"
        )
        
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scaffold", response_model=ScaffoldGraphResponse)
async def scaffold_graph(
    request: ScaffoldGraphRequest,
    adapter = Depends(get_adapter)
):
    """Scaffold agents for a graph."""
    try:
        from agentmap.core.cli.run_commands import scaffold_graph_command
        
        result = scaffold_graph_command(
            graph=request.graph,
            csv=request.csv,
            output_dir=request.output_dir,
            func_dir=request.func_dir
        )
        
        return ScaffoldGraphResponse(**result)
        
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{graph_name}")
async def get_graph_status(
    graph_name: str,
    csv: Optional[str] = None,
    adapter = Depends(get_adapter)
):
    """Get status information for a specific graph."""
    try:
        # Get services
        graph_runner_service, app_config_service, _ = adapter.initialize_services()
        
        # Determine CSV path
        csv_path = Path(csv) if csv else app_config_service.get_csv_path()
        
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")
        
        # Get graph builder service
        container = adapter.container
        graph_builder_service = container.graph_builder_service()
        
        # Build graph to check status
        graph_obj = graph_builder_service.build_from_csv(csv_path, graph_name)
        
        # Get agent resolution status
        agent_status = graph_runner_service.get_agent_resolution_status(graph_obj)
        
        return {
            "graph_name": graph_name,
            "exists": True,
            "csv_path": str(csv_path),
            "node_count": len(graph_obj.nodes),
            "entry_point": graph_obj.entry_point,
            "agent_status": agent_status
        }
        
    except ValueError as e:
        if "not found" in str(e).lower():
            return {
                "graph_name": graph_name,
                "exists": False,
                "error": str(e)
            }
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_graphs(
    csv: Optional[str] = None,
    adapter = Depends(get_adapter)
):
    """List all available graphs in the CSV file."""
    try:
        # Get services
        _, app_config_service, _ = adapter.initialize_services()
        
        # Determine CSV path
        csv_path = Path(csv) if csv else app_config_service.get_csv_path()
        
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")
        
        # Get graph builder service
        container = adapter.container
        graph_builder_service = container.graph_builder_service()
        
        # Build all graphs to get list
        graph_obj = graph_builder_service.build_from_csv(csv_path)
        
        return {
            "csv_path": str(csv_path),
            "graphs": [
                {
                    "name": graph_obj.name,
                    "entry_point": graph_obj.entry_point,
                    "node_count": len(graph_obj.nodes)
                }
            ]
        }
        
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
