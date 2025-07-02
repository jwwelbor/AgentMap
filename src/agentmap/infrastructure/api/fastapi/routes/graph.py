"""
Graph execution routes for FastAPI server.

This module provides graph-specific API endpoints for execution, validation,
and compilation using the new service architecture.

FIXED: Updated to use correct service interfaces and properly handle return types.
"""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agentmap.core.adapters import create_service_adapter
from agentmap.di import ApplicationContainer


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


# Import shared dependency functions
from agentmap.infrastructure.api.fastapi.dependencies import (
    get_container,
)
from agentmap.infrastructure.api.fastapi.dependencies import (
    get_service_adapter as get_adapter,
)

# Create router
router = APIRouter(prefix="/graph", tags=["Graph Operations"])


@router.post("/compile", response_model=CompileGraphResponse)
async def compile_graph(
    request: CompileGraphRequest,
    container: ApplicationContainer = Depends(get_container),
):
    """Compile a graph to executable format."""
    try:
        # ✅ FIXED: Use compilation service with proper CompilationOptions
        compilation_service = container.compilation_service()
        app_config_service = container.app_config_service()

        # Create compilation options with all parameters
        from agentmap.services.compilation_service import CompilationOptions

        compilation_options = CompilationOptions()

        # Set CSV path in options
        if request.csv:
            compilation_options.csv_path = Path(request.csv)
        else:
            compilation_options.csv_path = app_config_service.get_csv_path()

        # Set other options
        if request.output_dir:
            compilation_options.output_dir = Path(request.output_dir)
        else:
            compilation_options.output_dir = (
                app_config_service.get_compiled_graphs_path()
            )

        compilation_options.state_schema = request.state_schema

        # Execute compilation with correct service interface
        if request.graph:
            # Single graph compilation
            result = compilation_service.compile_graph(
                graph_name=request.graph, options=compilation_options
            )
        else:
            # All graphs compilation - get first result
            results = compilation_service.compile_all_graphs(
                options=compilation_options
            )
            result = results[0] if results else None

        if not result:
            raise ValueError("No compilation result returned")

        # Convert result to response format using actual CompilationResult attributes
        return CompileGraphResponse(
            success=result.success,
            bundle_path=str(result.output_path) if result.output_path else None,
            source_path=str(result.source_path) if result.source_path else None,
            compilation_time=result.compilation_time,
            error=result.error,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate", response_model=ValidateGraphResponse)
async def validate_graph(
    request: ValidateGraphRequest,
    container: ApplicationContainer = Depends(get_container),
):
    """Validate a graph CSV file."""
    try:
        # ✅ FIXED: Use validation service with correct attribute names
        validation_service = container.validation_service()
        app_config_service = container.app_config_service()

        # Determine CSV path
        csv_path = (
            Path(request.csv) if request.csv else app_config_service.get_csv_path()
        )

        # Execute validation
        result = validation_service.validate_csv(
            csv_path, use_cache=not request.no_cache
        )

        # ✅ FIXED: Map ValidationResult attributes correctly
        return ValidateGraphResponse(
            success=result.is_valid,  # Use is_valid instead of success
            has_warnings=result.has_warnings,
            has_errors=result.has_errors,
            file_path=str(csv_path),
            message="Validation completed",
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
    container: ApplicationContainer = Depends(get_container),
):
    """Scaffold agents for a graph."""
    try:
        # ✅ FIXED: Use graph scaffold service with correct result handling
        graph_scaffold_service = container.graph_scaffold_service()
        app_config_service = container.app_config_service()

        # Determine CSV path
        csv_path = (
            Path(request.csv) if request.csv else app_config_service.get_csv_path()
        )

        # Create scaffold options
        from agentmap.services.graph_scaffold_service import ScaffoldOptions

        scaffold_options = ScaffoldOptions(
            graph_name=request.graph,
            output_path=Path(request.output_dir) if request.output_dir else None,
            function_path=Path(request.func_dir) if request.func_dir else None,
            overwrite_existing=False,
        )

        # Execute scaffolding
        result = graph_scaffold_service.scaffold_agents_from_csv(
            csv_path, scaffold_options
        )

        # ✅ FIXED: Map ScaffoldResult attributes correctly
        # ScaffoldResult doesn't have success attribute, derive from scaffolded_count
        success = result.scaffolded_count > 0 and len(result.errors) == 0

        # Get paths from scaffold options or use defaults
        output_path = (
            str(scaffold_options.output_path)
            if scaffold_options.output_path
            else str(app_config_service.get_custom_agents_path())
        )
        functions_path = (
            str(scaffold_options.function_path)
            if scaffold_options.function_path
            else str(app_config_service.get_functions_path())
        )

        return ScaffoldGraphResponse(
            success=success,
            scaffolded_count=result.scaffolded_count,
            output_path=output_path,
            functions_path=functions_path,
        )

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{graph_name}")
async def get_graph_status(
    graph_name: str,
    csv: Optional[str] = None,
    container: ApplicationContainer = Depends(get_container),
):
    """Get status information for a specific graph."""
    try:
        # ✅ FIXED: Use correct service names and handle Graph object properly
        graph_definition_service = container.graph_definition_service()
        graph_runner_service = container.graph_runner_service()
        app_config_service = container.app_config_service()

        # Determine CSV path
        csv_path = Path(csv) if csv else app_config_service.get_csv_path()

        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        # Build graph to check status
        graph_obj = graph_definition_service.build_from_csv(csv_path, graph_name)

        # Get agent resolution status
        agent_status = graph_runner_service.get_agent_resolution_status(graph_obj)

        # ✅ FIXED: Handle Graph object node count properly
        node_count = 0
        if hasattr(graph_obj, "nodes") and graph_obj.nodes is not None:
            if hasattr(graph_obj.nodes, "__len__"):
                # If nodes has __len__, use it directly
                node_count = len(graph_obj.nodes)
            elif hasattr(graph_obj.nodes, "keys"):
                # If nodes is dict-like, count keys
                node_count = len(list(graph_obj.nodes.keys()))
            else:
                # Try to convert to dict or count iteratively
                try:
                    nodes_dict = dict(graph_obj.nodes) if graph_obj.nodes else {}
                    node_count = len(nodes_dict)
                except (TypeError, ValueError):
                    # Fallback: count by iteration
                    try:
                        node_count = sum(1 for _ in graph_obj.nodes)
                    except (TypeError, AttributeError):
                        node_count = 0

        return {
            "graph_name": graph_name,
            "exists": True,
            "csv_path": str(csv_path),
            "node_count": node_count,
            "entry_point": getattr(graph_obj, "entry_point", None),
            "agent_status": agent_status,
        }

    except ValueError as e:
        if "not found" in str(e).lower():
            return {"graph_name": graph_name, "exists": False, "error": str(e)}
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_graphs(
    csv: Optional[str] = None, container: ApplicationContainer = Depends(get_container)
):
    """List all available graphs in the CSV file."""
    try:
        # ✅ FIXED: Use correct service names and handle Graph objects properly
        graph_definition_service = container.graph_definition_service()
        app_config_service = container.app_config_service()

        # Determine CSV path
        csv_path = Path(csv) if csv else app_config_service.get_csv_path()

        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        # Build all graphs to get list
        all_graphs = graph_definition_service.build_all_from_csv(csv_path)

        graphs_list = []
        for graph_name, graph_obj in all_graphs.items():
            # ✅ FIXED: Handle Graph object node count properly
            node_count = 0
            if hasattr(graph_obj, "nodes") and graph_obj.nodes is not None:
                if hasattr(graph_obj.nodes, "__len__"):
                    node_count = len(graph_obj.nodes)
                elif hasattr(graph_obj.nodes, "keys"):
                    node_count = len(list(graph_obj.nodes.keys()))
                else:
                    try:
                        nodes_dict = dict(graph_obj.nodes) if graph_obj.nodes else {}
                        node_count = len(nodes_dict)
                    except (TypeError, ValueError):
                        try:
                            node_count = sum(1 for _ in graph_obj.nodes)
                        except (TypeError, AttributeError):
                            node_count = 0

            graphs_list.append(
                {
                    "name": graph_name,
                    "entry_point": getattr(graph_obj, "entry_point", None),
                    "node_count": node_count,
                }
            )

        return {
            "csv_path": str(csv_path),
            "graphs": graphs_list,
        }

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
