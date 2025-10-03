"""
Execution routes - Simple RPC-style operations with backwards compatibility.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from agentmap.deployment.http.api.dependencies import requires_auth
from agentmap.exceptions.runtime_exceptions import (
    AgentMapNotInitialized,
    GraphNotFound,
    InvalidInputs,
)
from agentmap.runtime_api import ensure_initialized, resume_workflow, run_workflow


# Simple request/response models
class ExecuteRequest(BaseModel):
    """Request to execute a workflow."""

    inputs: Dict[str, Any] = Field(default={}, description="Input parameters")
    execution_id: Optional[str] = Field(
        None, description="Optional execution tracking ID"
    )


class ExecuteResponse(BaseModel):
    """Response from workflow execution."""

    success: bool = Field(..., description="Whether execution succeeded")
    outputs: Optional[Dict[str, Any]] = Field(None, description="Execution outputs")
    error: Optional[str] = Field(None, description="Error message if failed")
    execution_id: Optional[str] = Field(None, description="Execution tracking ID")


class ResumeRequest(BaseModel):
    """Request to resume a paused execution."""

    action: str = Field(..., description="Action to take (approve, reject, etc)")
    data: Dict[str, Any] = Field(
        default={}, description="Additional data for the action"
    )


class ResumeResponse(BaseModel):
    """Response from resuming execution."""

    success: bool = Field(..., description="Whether resume succeeded")
    message: str = Field(..., description="Status message")
    error: Optional[str] = Field(None, description="Error message if failed")


# Router
router = APIRouter(tags=["Execution"])


def _normalize_graph_identifier(identifier: str) -> str:
    """Normalize graph identifier to standard format."""
    # Handle URL encoding and alternative separators
    return identifier.replace("%3A%3A", "::").replace("/", "::")


def _execute_workflow_internal(
    graph_identifier: str, request_body: ExecuteRequest
) -> ExecuteResponse:
    """Internal execution logic shared by all endpoints."""
    try:
        ensure_initialized()

        # Normalize identifier
        graph_identifier = _normalize_graph_identifier(graph_identifier)

        # Validate format
        if not graph_identifier or graph_identifier.count("::") > 1:
            raise InvalidInputs(f"Invalid graph identifier format: {graph_identifier}")

        # Execute using runtime facade
        result = run_workflow(graph_name=graph_identifier, inputs=request_body.inputs)

        if result.get("success"):
            return ExecuteResponse(
                success=True,
                outputs=result.get("outputs", {}),
                execution_id=request_body.execution_id,
            )
        else:
            return ExecuteResponse(
                success=False,
                error=result.get("error", "Execution failed"),
                execution_id=request_body.execution_id,
            )

    except GraphNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidInputs as e:
        raise HTTPException(status_code=400, detail=str(e))
    except AgentMapNotInitialized as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute/{graph_id:path}", response_model=ExecuteResponse)
@requires_auth("execute")
async def execute_workflow(
    graph_id: str, request_body: ExecuteRequest, request: Request
):
    """
    Execute a workflow using its graph identifier.

    Graph ID format: workflow::graph (e.g., customer_service::support_flow)
    Also accepts: workflow/graph or URL-encoded workflow%3A%3Agraph
    """
    return _execute_workflow_internal(graph_id, request_body)


@router.post("/execute/{workflow}/{graph}", response_model=ExecuteResponse)
@requires_auth("execute")
async def execute_workflow_two_param(
    workflow: str, graph: str, request_body: ExecuteRequest, request: Request
):
    """
    Execute a workflow using separate workflow and graph parameters.

    This convenience endpoint constructs the graph identifier from workflow and graph names.

    Example: POST /execute/customer_service/support_flow
    """
    # Validate inputs
    if not workflow or not graph:
        raise HTTPException(status_code=400, detail="Workflow and graph names required")

    # Construct graph identifier
    graph_identifier = f"{workflow}::{graph}"
    return _execute_workflow_internal(graph_identifier, request_body)


@router.post("/execute/{workflow_graph:path}", response_model=ExecuteResponse)
@requires_auth("execute")
async def execute_workflow_single_param(
    workflow_graph: str, request_body: ExecuteRequest, request: Request
):
    """
    Execute a workflow using a single parameter that can be:
    - Graph identifier format: workflow::graph
    - Simple name: assumes workflow and graph have same name
    - Path format: workflow/graph (converted to :: format)

    Examples:
    - POST /execute/customer_service::support_flow
    - POST /execute/simple_workflow (becomes simple_workflow::simple_workflow)
    - POST /execute/customer_service/support_flow (becomes customer_service::support_flow)
    """
    # Handle different input formats
    if "::" in workflow_graph:
        # Already in graph identifier format
        graph_identifier = workflow_graph
    elif "/" in workflow_graph:
        # Path format - convert to graph identifier
        parts = workflow_graph.split("/", 1)
        graph_identifier = f"{parts[0]}::{parts[1]}"
    else:
        # Simple name - assume workflow and graph have same name
        graph_identifier = f"{workflow_graph}::{workflow_graph}"

    return _execute_workflow_internal(graph_identifier, request_body)


@router.post("/resume/{thread_id}", response_model=ResumeResponse)
@requires_auth("execute")
async def resume_execution(
    thread_id: str, request_body: ResumeRequest, request: Request
):
    """
    Resume a paused workflow execution.

    Common actions: approve, reject, choose, respond, retry
    """
    try:
        ensure_initialized()

        # Validate thread_id
        if not thread_id or len(thread_id) < 10:
            raise InvalidInputs("Invalid thread ID")

        # Build resume token
        import json

        resume_token = json.dumps(
            {
                "thread_id": thread_id,
                "response_action": request_body.action,
                "response_data": request_body.data,
            }
        )

        # Resume using runtime facade
        result = resume_workflow(resume_token=resume_token)

        if result.get("success"):
            return ResumeResponse(
                success=True,
                message=f"Successfully resumed thread '{thread_id}' with action '{request_body.action}'",
            )
        else:
            return ResumeResponse(
                success=False,
                message="Failed to resume execution",
                error=result.get("error", "Unknown error"),
            )

    except InvalidInputs as e:
        raise HTTPException(status_code=400, detail=str(e))
    except AgentMapNotInitialized as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
