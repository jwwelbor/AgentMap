"""
Workflow query routes - Simple and clean.
"""

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from agentmap.deployment.http.api.dependencies import requires_auth
from agentmap.exceptions.runtime_exceptions import (
    AgentMapNotInitialized,
    GraphNotFound,
)
from agentmap.runtime_api import ensure_initialized, inspect_graph, list_graphs


# Simple response models without Config classes
class WorkflowSummary(BaseModel):
    """Summary of a workflow/graph."""

    graph_id: str = Field(..., description="Graph identifier (workflow::graph)")
    workflow: str = Field(..., description="Workflow name")
    graph: str = Field(..., description="Graph name")
    node_count: int = Field(..., description="Number of nodes")
    description: Optional[str] = Field(None, description="Description")


class WorkflowListResponse(BaseModel):
    """List of available workflows."""

    workflows: List[WorkflowSummary] = Field(..., description="Available workflows")
    total: int = Field(..., description="Total count")


class NodeInfo(BaseModel):
    """Information about a node."""

    name: str = Field(..., description="Node name")
    agent_type: str = Field(..., description="Agent type")
    description: Optional[str] = Field(None, description="Description")


class WorkflowDetailResponse(BaseModel):
    """Detailed workflow information."""

    graph_id: str = Field(..., description="Graph identifier")
    workflow: str = Field(..., description="Workflow name")
    graph: str = Field(..., description="Graph name")
    nodes: List[NodeInfo] = Field(..., description="Graph nodes")
    node_count: int = Field(..., description="Node count")
    entry_point: Optional[str] = Field(None, description="Entry node")


# Router
router = APIRouter(prefix="/workflows", tags=["Workflows"])


@router.get("", response_model=WorkflowListResponse)
@requires_auth("read")
async def list_workflows(request: Request):
    """List all available workflows."""
    try:
        ensure_initialized()

        result = list_graphs()
        if not result.get("success"):
            raise HTTPException(
                status_code=500, detail=result.get("error", "Failed to list graphs")
            )

        graphs = result.get("outputs", {}).get("graphs", [])

        # Transform to our simple response format
        workflows = []
        for graph in graphs:
            graph_id = f"{graph.get('workflow', '')}::{graph.get('name', '')}"
            workflows.append(
                WorkflowSummary(
                    graph_id=graph_id,
                    workflow=graph.get("workflow", ""),
                    graph=graph.get("name", ""),
                    node_count=graph.get("node_count", 0),
                    description=graph.get("description"),
                )
            )

        return WorkflowListResponse(workflows=workflows, total=len(workflows))

    except AgentMapNotInitialized as e:
        raise HTTPException(status_code=503, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{graph_id:path}", response_model=WorkflowDetailResponse)
@requires_auth("read")
async def get_workflow_details(graph_id: str, request: Request):
    """Get details for a specific workflow."""
    try:
        ensure_initialized()

        # Handle URL encoding and alternative separators
        graph_id = graph_id.replace("%3A%3A", "::").replace("/", "::")

        result = inspect_graph(graph_id)
        if not result.get("success"):
            error = result.get("error", "")
            if "not found" in error.lower():
                raise HTTPException(
                    status_code=404, detail=f"Workflow '{graph_id}' not found"
                )
            raise HTTPException(status_code=500, detail=error)

        outputs = result.get("outputs", {})
        structure = outputs.get("structure", {})

        # Parse graph_id
        if "::" in graph_id:
            workflow, graph = graph_id.split("::", 1)
        else:
            workflow = graph = graph_id

        # Transform nodes
        nodes = []
        for node in structure.get("nodes", []):
            nodes.append(
                NodeInfo(
                    name=node.get("name", ""),
                    agent_type=node.get("agent_type", ""),
                    description=node.get("description"),
                )
            )

        return WorkflowDetailResponse(
            graph_id=graph_id,
            workflow=workflow,
            graph=graph,
            nodes=nodes,
            node_count=len(nodes),
            entry_point=structure.get("entry_point"),
        )

    except GraphNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except AgentMapNotInitialized as e:
        raise HTTPException(status_code=503, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
