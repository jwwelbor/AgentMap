"""
Workflow execution API endpoints using bundle-based approach.

This module provides API endpoints that follow the same bundle pattern
as the CLI, resolving workflows from the repository and using cached bundles.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from agentmap.di import initialize_di

# ==========================================
# Request/Response Models
# ==========================================


class WorkflowExecutionRequest(BaseModel):
    """Request model for workflow execution."""

    state: Dict[str, Any] = {}
    config: Optional[Dict[str, Any]] = None
    validate: bool = False


class WorkflowExecutionResponse(BaseModel):
    """Response model for workflow execution."""

    success: bool
    graph_name: str
    workflow_name: str
    final_state: Dict[str, Any]
    error: Optional[str] = None
    bundle_cached: bool = False
    execution_time: Optional[float] = None


class WorkflowInfo(BaseModel):
    """Information about available workflows."""

    name: str
    path: str
    graphs: List[str]
    size_bytes: int


class WorkflowListResponse(BaseModel):
    """Response for listing available workflows."""

    workflows: List[WorkflowInfo]
    repository_path: str


# ==========================================
# API Router Implementation
# ==========================================


def create_workflow_router(container=None) -> APIRouter:
    """
    Create workflow execution router with bundle support.

    This router follows the same pattern as the CLI, using
    GraphBundleService to manage bundle caching and execution.

    Args:
        container: Optional DI container (will be created if not provided)

    Returns:
        Configured APIRouter for workflow execution
    """
    router = APIRouter(prefix="/workflow", tags=["Workflow Execution"])

    # Initialize container if not provided
    if container is None:
        container = initialize_di()

    # ==========================================
    # Main Execution Endpoint
    # ==========================================

    @router.post("/{workflow}/{graph}", response_model=WorkflowExecutionResponse)
    async def execute_workflow_graph(
        workflow: str, graph: str, request: WorkflowExecutionRequest
    ) -> WorkflowExecutionResponse:
        """
        Execute a specific graph from a workflow using cached bundles.

        This endpoint follows the same pattern as the CLI run command:
        1. Resolves the workflow CSV from the repository
        2. Gets or creates a bundle using GraphBundleService
        3. Executes the bundle

        Args:
            workflow: Workflow name (without .csv extension)
            graph: Graph name within the workflow
            request: Execution request with initial state

        Returns:
            Execution response with final state
        """
        try:
            # Get services from container
            app_config_service = container.app_config_service()
            graph_bundle_service = container.graph_bundle_service()
            graph_runner_service = container.graph_runner_service()
            logging_service = container.logging_service()
            logger = logging_service.get_component_logger("workflow_api")

            # Resolve workflow path from repository
            csv_repository = app_config_service.get_csv_repository_path()
            workflow_file = csv_repository / f"{workflow}.csv"

            if not workflow_file.exists():
                # Try with .csv extension if provided
                workflow_file = csv_repository / workflow
                if not workflow_file.exists():
                    raise HTTPException(
                        status_code=404,
                        detail=f"Workflow '{workflow}' not found in repository",
                    )

            logger.info(f"Resolved workflow path: {workflow_file}")

            # Validate CSV if requested
            if request.validate:
                validation_service = container.validation_service()
                try:
                    validation_service.validate_csv_for_bundling(workflow_file)
                    logger.info("CSV validation passed")
                except Exception as e:
                    raise HTTPException(
                        status_code=400, detail=f"CSV validation failed: {str(e)}"
                    )

            # Get or create bundle (same as CLI)
            bundle, from_cache = graph_bundle_service.get_or_create_bundle(
                csv_path=workflow_file,
                graph_name=graph,
                config_path=None,  # Use default config
            )

            # Check if bundle was cached
            bundle_cached = from_cache

            # Execute using bundle
            import time

            start_time = time.time()

            result = graph_runner_service.run(bundle, request.state)

            execution_time = time.time() - start_time

            # Build response
            return WorkflowExecutionResponse(
                success=result.success,
                graph_name=bundle.graph_name or graph,
                workflow_name=workflow,
                final_state=result.final_state,
                error=result.error if not result.success else None,
                bundle_cached=bundle_cached,
                execution_time=execution_time,
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            return WorkflowExecutionResponse(
                success=False,
                graph_name=graph,
                workflow_name=workflow,
                final_state=request.state,
                error=str(e),
            )

    # ==========================================
    # Workflow Discovery Endpoints
    # ==========================================

    @router.get("/list", response_model=WorkflowListResponse)
    async def list_workflows() -> WorkflowListResponse:
        """
        List all available workflows in the repository.

        Returns:
            List of available workflows with their graphs
        """
        try:
            app_config_service = container.app_config_service()
            csv_parser_service = container.csv_graph_parser_service()
            logging_service = container.logging_service()
            logger = logging_service.get_component_logger("workflow_api")

            # Get repository path
            csv_repository = app_config_service.get_csv_repository_path()

            # Find all CSV files
            csv_files = list(csv_repository.glob("*.csv"))

            workflows = []
            for csv_file in csv_files:
                try:
                    # Parse CSV to get available graphs
                    graph_def = csv_parser_service.parse_csv_file(csv_file)

                    # Extract unique graph names
                    graph_names = list(graph_def.keys()) if graph_def else []

                    workflows.append(
                        WorkflowInfo(
                            name=csv_file.stem,
                            path=str(csv_file),
                            graphs=graph_names,
                            size_bytes=csv_file.stat().st_size,
                        )
                    )
                except Exception as e:
                    logger.warning(f"Failed to parse {csv_file}: {e}")
                    # Still include the workflow, just without graph info
                    workflows.append(
                        WorkflowInfo(
                            name=csv_file.stem,
                            path=str(csv_file),
                            graphs=[],
                            size_bytes=csv_file.stat().st_size,
                        )
                    )

            return WorkflowListResponse(
                workflows=workflows, repository_path=str(csv_repository)
            )

        except Exception as e:
            logger.error(f"Failed to list workflows: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to list workflows: {str(e)}"
            )

    @router.get("/{workflow}/graphs", response_model=List[str])
    async def get_workflow_graphs(workflow: str) -> List[str]:
        """
        Get list of graphs available in a specific workflow.

        Args:
            workflow: Workflow name

        Returns:
            List of graph names in the workflow
        """
        try:
            app_config_service = container.app_config_service()
            csv_parser_service = container.csv_graph_parser_service()
            logging_service = container.logging_service()
            logger = logging_service.get_component_logger("workflow_api")

            # Resolve workflow path
            csv_repository = app_config_service.get_csv_repository_path()
            workflow_file = csv_repository / f"{workflow}.csv"

            if not workflow_file.exists():
                workflow_file = csv_repository / workflow
                if not workflow_file.exists():
                    raise HTTPException(
                        status_code=404, detail=f"Workflow '{workflow}' not found"
                    )

            # Parse CSV to get graphs
            graph_def = csv_parser_service.parse_csv_file(workflow_file)

            if not graph_def:
                return []

            return list(graph_def.keys())

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get workflow graphs: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to get workflow graphs: {str(e)}"
            )

    # ==========================================
    # Bundle Management Endpoints
    # ==========================================

    @router.delete("/{workflow}/{graph}/bundle")
    async def clear_workflow_bundle(workflow: str, graph: str) -> Dict[str, Any]:
        """
        Clear cached bundle for a specific workflow/graph combination.

        This forces recreation on next execution.

        Args:
            workflow: Workflow name
            graph: Graph name

        Returns:
            Status of bundle deletion
        """
        try:
            app_config_service = container.app_config_service()
            graph_bundle_service = container.graph_bundle_service()
            graph_registry_service = container.graph_registry_service()
            logging_service = container.logging_service()
            logger = logging_service.get_component_logger("workflow_api")

            # Resolve workflow path to get CSV hash
            csv_repository = app_config_service.get_csv_repository_path()
            workflow_file = csv_repository / f"{workflow}.csv"

            if not workflow_file.exists():
                workflow_file = csv_repository / workflow
                if not workflow_file.exists():
                    raise HTTPException(
                        status_code=404, detail=f"Workflow '{workflow}' not found"
                    )

            # Compute CSV hash
            from agentmap.services.graph.graph_registry_service import (
                GraphRegistryService,
            )

            csv_hash = GraphRegistryService.compute_hash(workflow_file)

            # Look up bundle
            bundle = graph_bundle_service.lookup_bundle(csv_hash, graph)

            if not bundle:
                return {
                    "success": False,
                    "message": f"No cached bundle found for {workflow}/{graph}",
                }

            # Delete bundle file
            deleted = graph_bundle_service.delete_bundle(bundle)

            # Remove from registry
            if deleted:
                graph_registry_service.unregister(csv_hash, graph)

            return {
                "success": deleted,
                "message": (
                    f"Bundle cleared for {workflow}/{graph}"
                    if deleted
                    else "Failed to delete bundle"
                ),
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to clear bundle: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to clear bundle: {str(e)}"
            )

    @router.get("/bundle-info")
    async def get_bundle_info() -> Dict[str, Any]:
        """
        Get information about bundle system performance and capabilities.

        Returns:
            Bundle system information
        """
        try:
            graph_bundle_service = container.graph_bundle_service()
            graph_registry_service = container.graph_registry_service()

            # Get performance info
            perf_info = graph_bundle_service.get_bundle_creation_performance_info()

            # Get registry stats
            registry_stats = graph_registry_service.get_registry_stats()

            return {"bundle_system": perf_info, "registry": registry_stats}

        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to get bundle info: {str(e)}"
            )

    return router


# ==========================================
# CLI-Compatible Execution Function
# ==========================================


def execute_workflow_from_cli_pattern(
    workflow_name: str,
    graph_name: str,
    initial_state: Dict[str, Any],
    config_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Execute workflow using the exact same pattern as the CLI.

    This function can be used for testing or direct execution
    following the CLI pattern exactly.

    Args:
        workflow_name: Name of workflow file (without .csv)
        graph_name: Name of graph within workflow
        initial_state: Initial state for execution
        config_path: Optional config file path

    Returns:
        Execution result dictionary
    """
    # Initialize container
    container = initialize_di(config_path)

    # Get services
    app_config_service = container.app_config_service()
    graph_bundle_service = container.graph_bundle_service()
    graph_runner_service = container.graph_runner_service()

    # Resolve CSV path from repository
    csv_repository = app_config_service.get_csv_repository_path()
    csv_path = csv_repository / f"{workflow_name}.csv"

    if not csv_path.exists():
        raise FileNotFoundError(f"Workflow '{workflow_name}' not found in repository")

    # Get or create bundle (exact same as CLI)
    bundle, _ = graph_bundle_service.get_or_create_bundle(
        csv_path=csv_path, graph_name=graph_name, config_path=config_path
    )

    # Execute using bundle
    result = graph_runner_service.run(bundle, initial_state)

    return {
        "success": result.success,
        "final_state": result.final_state,
        "error": result.error,
        "graph_name": bundle.graph_name,
        "workflow_name": workflow_name,
    }


# ==========================================
# Integration with existing FastAPI app
# ==========================================


def integrate_workflow_routes(app, container=None):
    """
    Integrate workflow routes into existing FastAPI application.

    Args:
        app: FastAPI application instance
        container: Optional DI container
    """
    # Create workflow router
    workflow_router = create_workflow_router(container)

    # Include in app
    app.include_router(workflow_router)

    # Add startup/shutdown events if needed
    @app.on_event("startup")
    async def startup_event():
        """Initialize services on startup."""
        pass  # Services are initialized via DI

    @app.on_event("shutdown")
    async def shutdown_event():
        """Clean up on shutdown."""
        pass  # Clean up if needed
