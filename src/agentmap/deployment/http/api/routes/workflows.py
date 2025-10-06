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
    """Workflow metadata returned by the list endpoint."""

    name: str = Field(..., description="Workflow name")
    filename: str = Field(..., description="Workflow CSV filename")
    file_path: str = Field(..., description="Absolute path to workflow CSV")
    file_size: int = Field(..., description="Workflow file size in bytes")
    last_modified: float = Field(
        ..., description="Last modified timestamp (epoch seconds)"
    )
    graph_count: int = Field(
        ..., description="Number of graphs defined in the workflow"
    )
    total_nodes: int = Field(..., description="Total nodes across all graphs")


class WorkflowListResponse(BaseModel):
    """List of available workflows."""

    repository_path: str = Field(..., description="CSV repository path")
    workflows: List[WorkflowSummary] = Field(..., description="Available workflows")
    total_count: int = Field(..., description="Total workflow count")


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

        outputs = result.get("outputs", {})
        graphs = outputs.get("graphs", [])
        metadata = result.get("metadata", {})
        repository_path = metadata.get("repository_path", "")

        if not repository_path and graphs:
            for graph in graphs:
                repo_meta = graph.get("meta", {})
                if repo_meta.get("repository_path"):
                    repository_path = repo_meta["repository_path"]
                    break

        workflows_by_name = {}
        for graph in graphs:
            workflow_name = graph.get("workflow") or graph.get("name")
            if not workflow_name:
                continue

            base_data = {
                "name": workflow_name,
                "filename": graph.get("filename", ""),
                "file_path": graph.get("file_path", ""),
                "file_size": int(graph.get("file_size", 0) or 0),
                "last_modified": float(graph.get("last_modified", 0.0) or 0.0),
                "graph_count": int(graph.get("graph_count_in_workflow", 0) or 0),
                "total_nodes": int(graph.get("total_nodes", 0) or 0),
            }

            existing = workflows_by_name.get(workflow_name)
            if existing is None:
                workflows_by_name[workflow_name] = base_data
            else:
                existing["graph_count"] = max(
                    existing["graph_count"], base_data["graph_count"]
                )
                existing["total_nodes"] = max(
                    existing["total_nodes"], base_data["total_nodes"]
                )
                existing["file_size"] = max(
                    existing["file_size"], base_data["file_size"]
                )
                existing["last_modified"] = max(
                    existing["last_modified"], base_data["last_modified"]
                )

        workflows = [
            WorkflowSummary(**data)
            for data in sorted(
                workflows_by_name.values(), key=lambda item: item["name"]
            )
        ]

        return WorkflowListResponse(
            repository_path=str(repository_path),
            workflows=workflows,
            total_count=len(workflows),
        )

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
