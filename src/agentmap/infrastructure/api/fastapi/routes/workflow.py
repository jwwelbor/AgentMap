"""
Workflow management routes for FastAPI server.

This module provides API endpoints for managing workflows stored in the
CSV repository, including listing, inspection, and detailed graph information.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from agentmap.di import ApplicationContainer
from agentmap.infrastructure.api.fastapi.dependencies import (
    get_app_config_service,
    get_container,
)
from agentmap.infrastructure.api.fastapi.middleware.auth import require_admin_permission
from agentmap.services.auth_service import AuthContext


# Response models
class WorkflowSummary(BaseModel):
    """Summary information for a workflow."""

    name: str = Field(..., description="Workflow name (filename without extension)")
    filename: str = Field(..., description="Full filename including .csv extension")
    file_path: str = Field(..., description="Complete file path to the workflow CSV")
    file_size: int = Field(..., description="File size in bytes")
    last_modified: str = Field(..., description="Last modification timestamp")
    graph_count: int = Field(
        ..., description="Number of graphs defined in this workflow"
    )
    total_nodes: int = Field(..., description="Total number of nodes across all graphs")

    class Config:
        schema_extra = {
            "example": {
                "name": "customer_service",
                "filename": "customer_service.csv",
                "file_path": "csv_repository/customer_service.csv",
                "file_size": 15420,
                "last_modified": "2024-01-15T14:30:00Z",
                "graph_count": 3,
                "total_nodes": 12,
            }
        }


class GraphSummary(BaseModel):
    """Summary information for a graph within a workflow."""

    name: str = Field(..., description="Graph name as defined in the CSV")
    node_count: int = Field(..., description="Number of nodes in this graph")
    entry_point: Optional[str] = Field(
        None, description="First node or identified entry point"
    )
    nodes: List[str] = Field(
        default=[], description="List of all node names in this graph"
    )

    class Config:
        schema_extra = {
            "example": {
                "name": "support_flow",
                "node_count": 5,
                "entry_point": "receive_inquiry",
                "nodes": [
                    "receive_inquiry",
                    "classify_request",
                    "route_to_agent",
                    "generate_response",
                    "close_ticket",
                ],
            }
        }


class NodeDetail(BaseModel):
    """Detailed information for a node."""

    name: str = Field(..., description="Node name as defined in the CSV")
    agent_type: Optional[str] = Field(
        None, description="Type of agent (e.g., openai, echo, branching)"
    )
    description: Optional[str] = Field(
        None, description="Human-readable description of the node's purpose"
    )
    input_fields: List[str] = Field(
        default=[], description="List of input field names expected by this node"
    )
    output_field: Optional[str] = Field(None, description="Primary output field name")
    success_next: Optional[str] = Field(
        None, description="Next node on successful execution"
    )
    failure_next: Optional[str] = Field(
        None, description="Next node on execution failure"
    )
    line_number: int = Field(..., description="Line number in the original CSV file")

    class Config:
        schema_extra = {
            "example": {
                "name": "classify_request",
                "agent_type": "openai",
                "description": "Classify customer inquiry into predefined categories",
                "input_fields": ["customer_message", "context"],
                "output_field": "category",
                "success_next": "route_to_agent",
                "failure_next": "escalate_to_human",
                "line_number": 3,
            }
        }


class WorkflowListResponse(BaseModel):
    """Response model for workflow listing."""

    repository_path: str = Field(..., description="Path to the CSV workflow repository")
    workflows: List[WorkflowSummary] = Field(
        ..., description="List of available workflows"
    )
    total_count: int = Field(..., description="Total number of workflows found")

    class Config:
        schema_extra = {
            "example": {
                "repository_path": "csv_repository",
                "workflows": [
                    {
                        "name": "customer_service",
                        "filename": "customer_service.csv",
                        "file_path": "csv_repository/customer_service.csv",
                        "file_size": 15420,
                        "last_modified": "2024-01-15T14:30:00Z",
                        "graph_count": 3,
                        "total_nodes": 12,
                    }
                ],
                "total_count": 1,
            }
        }


class WorkflowDetailResponse(BaseModel):
    """Response model for workflow details."""

    name: str = Field(..., description="Workflow name")
    filename: str = Field(..., description="CSV filename")
    file_path: str = Field(..., description="Complete file path")
    repository_path: str = Field(..., description="Repository root path")
    graphs: List[GraphSummary] = Field(
        ..., description="List of graphs in this workflow"
    )
    total_nodes: int = Field(..., description="Total nodes across all graphs")
    file_info: Dict[str, Any] = Field(..., description="Additional file metadata")

    class Config:
        schema_extra = {
            "example": {
                "name": "customer_service",
                "filename": "customer_service.csv",
                "file_path": "csv_repository/customer_service.csv",
                "repository_path": "csv_repository",
                "graphs": [
                    {
                        "name": "support_flow",
                        "node_count": 5,
                        "entry_point": "receive_inquiry",
                        "nodes": [
                            "receive_inquiry",
                            "classify_request",
                            "route_to_agent",
                            "generate_response",
                            "close_ticket",
                        ],
                    }
                ],
                "total_nodes": 12,
                "file_info": {
                    "size_bytes": 15420,
                    "last_modified": "2024-01-15T14:30:00Z",
                    "is_readable": True,
                    "extension": ".csv",
                },
            }
        }


class GraphDetailResponse(BaseModel):
    """Response model for graph details."""

    workflow_name: str = Field(..., description="Name of the parent workflow")
    graph_name: str = Field(..., description="Name of this specific graph")
    nodes: List[NodeDetail] = Field(
        ..., description="Detailed information for each node"
    )
    node_count: int = Field(..., description="Total number of nodes in this graph")
    entry_point: Optional[str] = Field(None, description="Identified entry point node")
    edges: List[Dict[str, str]] = Field(
        default=[], description="Node connections and relationships"
    )

    class Config:
        schema_extra = {
            "example": {
                "workflow_name": "customer_service",
                "graph_name": "support_flow",
                "nodes": [
                    {
                        "name": "receive_inquiry",
                        "agent_type": "input",
                        "description": "Receive customer inquiry",
                        "input_fields": ["customer_message"],
                        "output_field": "inquiry_data",
                        "success_next": "classify_request",
                        "failure_next": None,
                        "line_number": 1,
                    }
                ],
                "node_count": 5,
                "entry_point": "receive_inquiry",
                "edges": [
                    {
                        "from": "receive_inquiry",
                        "to": "classify_request",
                        "type": "success",
                    },
                    {
                        "from": "classify_request",
                        "to": "route_to_agent",
                        "type": "success",
                    },
                ],
            }
        }


def get_csv_parser_service(container: ApplicationContainer = Depends(get_container)):
    """Get CSVGraphParserService through DI container."""
    return container.csv_graph_parser_service()


# Create security scheme for bearer tokens
security = HTTPBearer(auto_error=False)


def get_admin_auth_dependency():
    """Create admin auth dependency function for workflow routes."""

    def admin_auth_dependency(
        request: Request,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
        container: ApplicationContainer = Depends(get_container),
    ) -> AuthContext:
        try:
            auth_service = container.auth_service()
        except Exception as e:
            # Handle auth service creation errors gracefully
            raise HTTPException(
                status_code=503,
                detail=f"Authentication service unavailable: {str(e)}",
            )

        # Require admin permission for all workflow endpoints
        return require_admin_permission(auth_service)(request, credentials)

    return admin_auth_dependency


# Create router
router = APIRouter(prefix="/workflows", tags=["Workflow Management"])


def _validate_workflow_name(workflow_name: str) -> str:
    """
    Validate workflow name to prevent path traversal attacks.

    Args:
        workflow_name: The workflow name to validate

    Returns:
        Validated workflow name

    Raises:
        HTTPException: If workflow name is invalid
    """
    # Remove any path separators and invalid characters
    clean_name = re.sub(r"[^\w\-_.]", "", workflow_name)

    # Check for path traversal attempts
    if ".." in workflow_name or "/" in workflow_name or "\\" in workflow_name:
        raise HTTPException(
            status_code=400, detail="Invalid workflow name: path traversal not allowed"
        )

    # Ensure it's not empty after cleaning
    if not clean_name:
        raise HTTPException(
            status_code=400,
            detail="Invalid workflow name: contains only invalid characters",
        )

    return clean_name


def _get_workflow_path(workflow_name: str, app_config_service) -> Path:
    """
    Get full path to workflow file in repository.

    Args:
        workflow_name: Name of the workflow
        app_config_service: Configuration service instance

    Returns:
        Path to the workflow CSV file

    Raises:
        HTTPException: If workflow file not found
    """
    # Validate workflow name
    clean_name = _validate_workflow_name(workflow_name)

    # Get CSV repository path from configuration
    csv_repository = app_config_service.get_csv_repository_path()

    # Add .csv extension if not present
    if not clean_name.endswith(".csv"):
        clean_name += ".csv"

    # Build full path
    workflow_path = csv_repository / clean_name

    # Check if file exists
    if not workflow_path.exists():
        raise HTTPException(
            status_code=404, detail=f"Workflow file not found: {clean_name}"
        )

    return workflow_path


def _parse_workflow_file(workflow_path: Path, csv_parser_service) -> Any:
    """
    Parse workflow CSV file and return GraphSpec.

    Args:
        workflow_path: Path to the workflow CSV file
        csv_parser_service: CSV parser service instance

    Returns:
        GraphSpec containing parsed workflow data

    Raises:
        HTTPException: If parsing fails
    """
    try:
        return csv_parser_service.parse_csv_to_graph_spec(workflow_path)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404, detail=f"Workflow file not found: {workflow_path.name}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400, detail=f"Invalid workflow file format: {e}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parsing workflow file: {e}")


@router.get(
    "",
    response_model=WorkflowListResponse,
    summary="List Available Workflows",
    description="Get a summary of all workflow files in the CSV repository",
    response_description="List of workflows with metadata and statistics",
    responses={
        200: {"description": "Workflows retrieved successfully"},
        500: {"description": "Error accessing workflow repository"},
    },
    tags=["Workflow Management"],
)
async def list_workflows(
    auth_context: AuthContext = Depends(get_admin_auth_dependency()),
    app_config_service=Depends(get_app_config_service),
):
    """
    **List All Available Workflows**
    
    Returns a comprehensive summary of all CSV workflow files found in the configured
    repository directory. This endpoint provides metadata, statistics, and basic
    information about each workflow without loading the full content.
    
    **Repository Structure:**
    ```
    csv_repository/
    ├── customer_service.csv    # Customer support workflows
    ├── sales_automation.csv    # Sales process automation
    ├── onboarding.csv          # User onboarding flows
    └── ...
    ```
    
    **Example Request:**
    ```bash
    curl -X GET "http://localhost:8000/workflows" \\
         -H "Accept: application/json"
    ```
    
    **Success Response:**
    ```json
    {
      "repository_path": "csv_repository",
      "workflows": [
        {
          "name": "customer_service",
          "filename": "customer_service.csv",
          "file_path": "csv_repository/customer_service.csv",
          "file_size": 15420,
          "last_modified": "2024-01-15T14:30:00Z",
          "graph_count": 3,
          "total_nodes": 12
        }
      ],
      "total_count": 1
    }
    ```
    
    **Use Cases:**
    - Browse available workflows for execution
    - Monitor repository contents and file sizes
    - Get workflow statistics for dashboard display
    - Discover workflow naming patterns
    
    **Performance:** Fast operation using file metadata only
    
    **Authentication:** None required
    """
    try:
        # Get CSV repository path
        csv_repository = app_config_service.get_csv_repository_path()

        # Find all CSV files in repository
        csv_files = list(csv_repository.glob("*.csv"))

        # Get basic file info and workflow summaries
        workflows = []
        for csv_file in csv_files:
            try:
                # Get file stats
                file_stat = csv_file.stat()

                # Try to parse CSV to get graph count (but handle errors gracefully)
                graph_count = 0
                total_nodes = 0
                try:
                    # Just get basic info without full parsing for performance
                    import pandas as pd

                    df = pd.read_csv(csv_file)
                    if "GraphName" in df.columns:
                        graph_count = df["GraphName"].nunique()
                    total_nodes = len(df)
                except Exception:
                    # If parsing fails, just use default values
                    pass

                # Create workflow summary
                workflow_name = csv_file.stem  # filename without extension
                workflow = WorkflowSummary(
                    name=workflow_name,
                    filename=csv_file.name,
                    file_path=str(csv_file),
                    file_size=file_stat.st_size,
                    last_modified=file_stat.st_mtime.__str__(),
                    graph_count=graph_count,
                    total_nodes=total_nodes,
                )
                workflows.append(workflow)

            except Exception as e:
                # Log error but continue with other files
                continue

        # Sort workflows by name
        workflows.sort(key=lambda w: w.name)

        return WorkflowListResponse(
            repository_path=str(csv_repository),
            workflows=workflows,
            total_count=len(workflows),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing workflows: {e}")


@router.get(
    "/{workflow}",
    response_model=WorkflowDetailResponse,
    summary="Get Workflow Details",
    description="Get comprehensive information about a specific workflow",
    response_description="Detailed workflow information including graphs and nodes",
    responses={
        200: {"description": "Workflow details retrieved successfully"},
        400: {"description": "Invalid workflow name"},
        404: {"description": "Workflow not found"},
    },
    tags=["Workflow Management"],
)
async def get_workflow_details(
    workflow: str,
    auth_context: AuthContext = Depends(get_admin_auth_dependency()),
    app_config_service=Depends(get_app_config_service),
    csv_parser_service=Depends(get_csv_parser_service),
):
    """
    **Get Comprehensive Workflow Information**
    
    Returns detailed information about a specific workflow including
    all graphs contained within it, node summaries, and metadata.
    This endpoint parses the CSV file to provide structural information.
    
    **Path Parameters:**
    - `workflow`: Name of the workflow (without .csv extension)
    
    **Example Request:**
    ```bash
    curl -X GET "http://localhost:8000/workflows/customer_service" \\
         -H "Accept: application/json"
    ```
    
    **Success Response:**
    ```json
    {
      "name": "customer_service",
      "filename": "customer_service.csv",
      "file_path": "csv_repository/customer_service.csv",
      "repository_path": "csv_repository",
      "graphs": [
        {
          "name": "support_flow",
          "node_count": 5,
          "entry_point": "receive_inquiry",
          "nodes": ["receive_inquiry", "classify_request", "route_to_agent", "generate_response", "close_ticket"]
        }
      ],
      "total_nodes": 12,
      "file_info": {
        "size_bytes": 15420,
        "last_modified": "2024-01-15T14:30:00Z",
        "is_readable": true,
        "extension": ".csv"
      }
    }
    ```
    
    **Use Cases:**
    - Inspect workflow structure before execution
    - Understand graph relationships and node counts
    - Get metadata for workflow management interfaces
    - Validate workflow integrity
    
    **Performance:** Parses CSV file - may take longer for large workflows
    
    **Authentication:** None required
    """
    # Get workflow path and validate existence
    workflow_path = _get_workflow_path(workflow, app_config_service)
    csv_repository = app_config_service.get_csv_repository_path()

    # Parse workflow file
    graph_spec = _parse_workflow_file(workflow_path, csv_parser_service)

    # Build graph summaries
    graphs = []
    total_nodes = 0

    for graph_name, nodes in graph_spec.graphs.items():
        # Find entry point (first node or node without incoming edges)
        entry_point = None
        if nodes:
            # Simple heuristic: use first node as entry point
            entry_point = nodes[0].name

        # Get node names
        node_names = [node.name for node in nodes]
        total_nodes += len(nodes)

        graph_summary = GraphSummary(
            name=graph_name,
            node_count=len(nodes),
            entry_point=entry_point,
            nodes=node_names,
        )
        graphs.append(graph_summary)

    # Get file info
    file_stat = workflow_path.stat()
    file_info = {
        "size_bytes": file_stat.st_size,
        "last_modified": file_stat.st_mtime.__str__(),
        "is_readable": workflow_path.is_file(),
        "extension": workflow_path.suffix,
    }

    return WorkflowDetailResponse(
        name=workflow,
        filename=workflow_path.name,
        file_path=str(workflow_path),
        repository_path=str(csv_repository),
        graphs=graphs,
        total_nodes=total_nodes,
        file_info=file_info,
    )


@router.get("/{workflow}/graphs")
async def list_workflow_graphs(
    workflow: str,
    auth_context: AuthContext = Depends(get_admin_auth_dependency()),
    app_config_service=Depends(get_app_config_service),
    csv_parser_service=Depends(get_csv_parser_service),
):
    """
    List all graphs available in a specific workflow.

    Returns a simple list of graph names and basic information
    for quick reference and navigation.
    """
    # Get workflow path and validate existence
    workflow_path = _get_workflow_path(workflow, app_config_service)

    # Parse workflow file
    graph_spec = _parse_workflow_file(workflow_path, csv_parser_service)

    # Build simple graph list
    graphs = []
    for graph_name, nodes in graph_spec.graphs.items():
        graphs.append(
            {
                "name": graph_name,
                "node_count": len(nodes),
                "first_node": nodes[0].name if nodes else None,
            }
        )

    return {"workflow_name": workflow, "graphs": graphs, "total_graphs": len(graphs)}


@router.get("/{workflow}/{graph}", response_model=GraphDetailResponse)
async def get_graph_details(
    workflow: str,
    graph: str,
    auth_context: AuthContext = Depends(get_admin_auth_dependency()),
    app_config_service=Depends(get_app_config_service),
    csv_parser_service=Depends(get_csv_parser_service),
):
    """
    Get detailed information about a specific graph within a workflow.

    Returns comprehensive information about the graph including all nodes,
    their configurations, and the relationships between them.
    """
    # Get workflow path and validate existence
    workflow_path = _get_workflow_path(workflow, app_config_service)

    # Parse workflow file
    graph_spec = _parse_workflow_file(workflow_path, csv_parser_service)

    # Check if graph exists
    if graph not in graph_spec.graphs:
        available_graphs = list(graph_spec.graphs.keys())
        raise HTTPException(
            status_code=404,
            detail=f"Graph '{graph}' not found in workflow '{workflow}'. "
            f"Available graphs: {available_graphs}",
        )

    # Get nodes for the specified graph
    nodes = graph_spec.graphs[graph]

    # Convert NodeSpec objects to NodeDetail response models
    node_details = []
    edges = []
    entry_point = None

    for node in nodes:
        # Create node detail
        node_detail = NodeDetail(
            name=node.name,
            agent_type=node.agent_type,
            description=node.description,
            input_fields=node.input_fields or [],
            output_field=node.output_field,
            success_next=node.success_next,
            failure_next=node.failure_next,
            line_number=node.line_number,
        )
        node_details.append(node_detail)

        # Track edges for visualization
        if node.success_next:
            edges.append(
                {"from": node.name, "to": node.success_next, "type": "success"}
            )
        if node.failure_next:
            edges.append(
                {"from": node.name, "to": node.failure_next, "type": "failure"}
            )

        # Determine entry point (simple heuristic: first node)
        if entry_point is None:
            entry_point = node.name

    return GraphDetailResponse(
        workflow_name=workflow,
        graph_name=graph,
        nodes=node_details,
        node_count=len(node_details),
        entry_point=entry_point,
        edges=edges,
    )
