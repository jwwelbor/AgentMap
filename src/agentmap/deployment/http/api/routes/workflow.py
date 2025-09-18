"""
Workflow management routes for FastAPI server.

This module provides API endpoints for managing workflows stored in the
CSV repository using the runtime facade pattern per SPEC-DEP-001 for
consistent behavior across all deployment adapters.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from agentmap.deployment.http.api.dependencies import (
    requires_auth,
)
from agentmap.exceptions.runtime_exceptions import (
    AgentMapNotInitialized,
)

# Use runtime facade instead of direct service access
from agentmap.runtime_api import ensure_initialized, inspect_graph, list_graphs


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


# Create router
router = APIRouter(prefix="/workflows", tags=["Workflow Management"])


# Helper functions removed - using facade pattern instead


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
@requires_auth("admin")
async def list_workflows(request: Request):
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
    
    **Authentication:** Admin permission required
    """
    try:
        # Ensure runtime is initialized
        ensure_initialized()

        # Use facade to list graphs/workflows
        graphs_response = list_graphs()

        # Extract the actual graphs from the structured response
        if not graphs_response.get("success", False):
            raise HTTPException(
                status_code=500, detail="Failed to retrieve graphs from runtime"
            )

        graphs = graphs_response.get("outputs", {}).get("graphs", [])
        repository_path = graphs_response.get("metadata", {}).get("repository_path", "")

        # Group by workflow and build workflow summaries
        workflow_groups = {}
        for graph in graphs:
            workflow_name = graph.get("workflow", "unknown")

            if workflow_name not in workflow_groups:
                workflow_groups[workflow_name] = {
                    "name": workflow_name,
                    "filename": graph.get("filename", f"{workflow_name}.csv"),
                    "file_path": graph.get("file_path", ""),
                    "file_size": graph.get("file_size", 0),
                    "last_modified": graph.get("last_modified", 0),
                    "graphs": [],
                    "total_nodes": 0,
                }

            workflow_groups[workflow_name]["graphs"].append(graph)
            workflow_groups[workflow_name]["total_nodes"] += graph.get("total_nodes", 0)

        # Convert to workflow summaries
        workflows = []

        for workflow_name, workflow_data in workflow_groups.items():
            workflow = WorkflowSummary(
                name=workflow_data["name"],
                filename=workflow_data["filename"],
                file_path=workflow_data["file_path"],
                file_size=workflow_data["file_size"],
                last_modified=str(workflow_data["last_modified"]),
                graph_count=len(workflow_data["graphs"]),
                total_nodes=workflow_data["total_nodes"],
            )
            workflows.append(workflow)

        # Sort workflows by name
        workflows.sort(key=lambda w: w.name)

        return WorkflowListResponse(
            repository_path=repository_path,
            workflows=workflows,
            total_count=len(workflows),
        )

    except AgentMapNotInitialized as e:
        raise HTTPException(status_code=503, detail=str(e))
    except HTTPException:
        # Re-raise HTTP exceptions with their original status codes
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")


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
@requires_auth("admin")
async def get_workflow_details(workflow: str, request: Request):
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
    
    **Authentication:** Admin permission required
    """
    try:
        # Ensure runtime is initialized
        ensure_initialized()

        # Use facade to get graphs for this workflow
        graphs_response = list_graphs()

        # Extract the actual graphs from the structured response
        if not graphs_response.get("success", False):
            raise HTTPException(
                status_code=500, detail="Failed to retrieve graphs from runtime"
            )

        graphs = graphs_response.get("outputs", {}).get("graphs", [])

        # Filter graphs by workflow name
        workflow_graphs = [g for g in graphs if g.get("workflow") == workflow]

        if not workflow_graphs:
            raise HTTPException(
                status_code=404, detail=f"Workflow '{workflow}' not found"
            )

        # Validate CSV file format for the workflow
        first_graph = workflow_graphs[0]
        csv_path = Path(first_graph.get("file_path", ""))
        if csv_path.exists():
            try:
                import pandas as pd

                df = pd.read_csv(csv_path)

                # Validate required columns
                required_columns = [
                    "Node",
                    "Agent_Type",
                    "Description",
                    "Input_Fields",
                    "Output_Field",
                ]
                missing_columns = [
                    col for col in required_columns if col not in df.columns
                ]
                if missing_columns:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid workflow file format: Missing required columns: {missing_columns}",
                    )

            except pd.errors.EmptyDataError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid workflow file format: Empty CSV file",
                )
            except Exception as e:
                if "Missing required columns" in str(e):
                    raise  # Re-raise our validation errors
                # For other parsing errors, return 400
                raise HTTPException(
                    status_code=400, detail=f"Invalid workflow file format: {str(e)}"
                )

        # Get workflow metadata from first graph
        first_graph = workflow_graphs[0]
        repository_path = first_graph.get("meta", {}).get("repository_path", "")

        # Build graph summaries from facade data
        graph_summaries = []
        total_nodes = 0

        for graph_data in workflow_graphs:
            graph_name = graph_data.get("name", "unknown")
            node_count = graph_data.get("total_nodes", 0)
            total_nodes += node_count

            graph_summary = GraphSummary(
                name=graph_name,
                node_count=node_count,
                entry_point=None,  # Not available from facade
                nodes=[],  # Node details not available from facade
            )
            graph_summaries.append(graph_summary)

        # Get file info from first graph
        file_info = {
            "size_bytes": first_graph.get("file_size", 0),
            "last_modified": str(first_graph.get("last_modified", 0)),
            "is_readable": True,
            "extension": ".csv",
        }

        return WorkflowDetailResponse(
            name=workflow,
            filename=first_graph.get("filename", f"{workflow}.csv"),
            file_path=first_graph.get("file_path", ""),
            repository_path=repository_path,
            graphs=graph_summaries,
            total_nodes=total_nodes,
            file_info=file_info,
        )

    except AgentMapNotInitialized as e:
        raise HTTPException(status_code=503, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")


@router.get("/{workflow}/graphs")
@requires_auth("admin")
async def list_workflow_graphs(workflow: str, request: Request):
    """
    List all graphs available in a specific workflow.

    Returns a simple list of graph names and basic information
    for quick reference and navigation.
    """
    try:
        # Ensure runtime is initialized
        ensure_initialized()

        # Use facade to get graphs for this workflow
        graphs_response = list_graphs()

        # Extract the actual graphs from the structured response
        if not graphs_response.get("success", False):
            raise HTTPException(
                status_code=500, detail="Failed to retrieve graphs from runtime"
            )

        all_graphs = graphs_response.get("outputs", {}).get("graphs", [])

        # Filter graphs by workflow name
        workflow_graphs = [g for g in all_graphs if g.get("workflow") == workflow]

        if not workflow_graphs:
            raise HTTPException(
                status_code=404, detail=f"Workflow '{workflow}' not found"
            )

        # Build simple graph list from facade data
        graphs = []
        for graph_data in workflow_graphs:
            graphs.append(
                {
                    "name": graph_data.get("name", "unknown"),
                    "node_count": graph_data.get("total_nodes", 0),
                    "first_node": None,  # Not available from facade
                }
            )

        return {
            "workflow_name": workflow,
            "graphs": graphs,
            "total_graphs": len(graphs),
        }

    except AgentMapNotInitialized as e:
        raise HTTPException(status_code=503, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")


@router.get("/{workflow}/{graph}", response_model=GraphDetailResponse)
@requires_auth("admin")
async def get_graph_details(
    workflow: str,
    graph: str,
    request: Request,
):
    """
    Get detailed information about a specific graph within a workflow.

    Returns comprehensive information about the graph including all nodes,
    their configurations, and the relationships between them.
    """
    try:
        # Ensure runtime is initialized
        ensure_initialized()

        # Use facade to get graphs for this workflow
        graphs_response = list_graphs()

        # Extract the actual graphs from the structured response
        if not graphs_response.get("success", False):
            raise HTTPException(
                status_code=500, detail="Failed to retrieve graphs from runtime"
            )

        all_graphs = graphs_response.get("outputs", {}).get("graphs", [])

        # Find the specific graph to verify it exists
        target_graph = None
        for graph_data in all_graphs:
            if (
                graph_data.get("workflow") == workflow
                and graph_data.get("name") == graph
            ):
                target_graph = graph_data
                break

        if not target_graph:
            # Find available graphs for this workflow
            workflow_graphs = [
                g.get("name") for g in all_graphs if g.get("workflow") == workflow
            ]
            if workflow_graphs:
                raise HTTPException(
                    status_code=404,
                    detail=f"Graph '{graph}' not found in workflow '{workflow}'. "
                    f"Available graphs: {workflow_graphs}",
                )
            else:
                raise HTTPException(
                    status_code=404,
                    detail=f"Workflow '{workflow}' not found",
                )

        # Load CSV directly to get node details since inspect_graph has issues
        try:
            csv_path = Path(target_graph.get("file_path", ""))
            if not csv_path.exists():
                raise HTTPException(
                    status_code=404, detail=f"Workflow file not found: {csv_path}"
                )

            # Parse CSV file directly using pandas
            import pandas as pd

            df = pd.read_csv(csv_path)

            # Validate required columns
            required_columns = [
                "Node",
                "Agent_Type",
                "Description",
                "Input_Fields",
                "Output_Field",
            ]
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid workflow file format: Missing required columns: {missing_columns}",
                )

            # Filter for the specific graph
            if "GraphName" in df.columns:
                graph_df = df[df["GraphName"] == graph]
                if graph_df.empty:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Graph '{graph}' not found in workflow '{workflow}'",
                    )
            else:
                graph_df = df  # Single graph file

            # Convert CSV data to node details
            nodes = []
            edges = []

            for i, (_, row) in enumerate(graph_df.iterrows(), 1):
                # Parse input fields
                input_fields = []
                if pd.notna(row.get("Input_Fields")):
                    input_fields = [
                        field.strip() for field in str(row["Input_Fields"]).split(",")
                    ]

                # Create node detail
                node_detail = NodeDetail(
                    name=str(row["Node"]),
                    agent_type=str(row.get("Agent_Type", "")).strip() or None,
                    description=str(row.get("Description", "")).strip() or None,
                    input_fields=input_fields,
                    output_field=str(row.get("Output_Field", "")).strip() or None,
                    success_next=str(row.get("Success_Next", "")).strip() or None,
                    failure_next=str(row.get("Failure_Next", "")).strip() or None,
                    line_number=i,
                )
                nodes.append(node_detail)

                # Build edges from success_next and failure_next
                if node_detail.success_next:
                    edges.append(
                        {
                            "from": node_detail.name,
                            "to": node_detail.success_next,
                            "type": "success",
                        }
                    )
                if node_detail.failure_next:
                    edges.append(
                        {
                            "from": node_detail.name,
                            "to": node_detail.failure_next,
                            "type": "failure",
                        }
                    )

            # Determine entry point (first node or one without incoming edges)
            entry_point = None
            if nodes:
                # Find nodes that are not targets of any edges
                target_nodes = set()
                for edge in edges:
                    target_nodes.add(edge["to"])

                entry_candidates = [
                    node.name for node in nodes if node.name not in target_nodes
                ]
                if entry_candidates:
                    entry_point = entry_candidates[0]
                else:
                    # Fallback to first node
                    entry_point = nodes[0].name

        except pd.errors.EmptyDataError:
            raise HTTPException(
                status_code=400, detail="Invalid workflow file format: Empty CSV file"
            )
        except KeyError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid workflow file format: Missing required column {e}",
            )
        except Exception as e:
            # If parsing fails, return empty but don't fail the request
            nodes = []
            edges = []
            entry_point = None

        return GraphDetailResponse(
            workflow_name=workflow,
            graph_name=graph,
            nodes=nodes,
            node_count=len(nodes) if nodes else target_graph.get("total_nodes", 0),
            entry_point=entry_point,
            edges=edges,
        )

    except AgentMapNotInitialized as e:
        raise HTTPException(status_code=503, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")
