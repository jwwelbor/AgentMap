"""Execution routes for the HTTP adapter.

These routes mirror the runtime facade that powers the CLI, including
the richer suspend/resume behavior (status reporting, summaries, thread ids).
"""

from dataclasses import asdict, is_dataclass
from datetime import datetime
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

    inputs: Dict[str, Any] = Field(
        default_factory=dict, description="Input state passed into the workflow"
    )
    execution_id: Optional[str] = Field(
        None, description="Optional client supplied tracking identifier"
    )
    force_create: bool = Field(
        False,
        description="Force recreation of bundle even if cached version exists",
    )


class ExecuteResponse(BaseModel):
    """Structured response from workflow execution."""

    success: bool = Field(..., description="True when the workflow completed")
    status: str = Field(
        ..., description="Execution status: completed | suspended | failed"
    )
    message: Optional[str] = Field(None, description="Human friendly status message")
    thread_id: Optional[str] = Field(
        None, description="Thread identifier when execution is suspended"
    )
    outputs: Optional[Any] = Field(
        None, description="Final workflow outputs (if available)"
    )
    execution_summary: Optional[Dict[str, Any]] = Field(
        None, description="Serialized execution summary"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional metadata returned by the runtime"
    )
    interrupt_info: Optional[Dict[str, Any]] = Field(
        None, description="Details about the interruption when suspended"
    )
    error: Optional[str] = Field(None, description="Error message when failed")
    execution_id: Optional[str] = Field(
        None, description="Echo of the supplied execution identifier"
    )


class ResumeRequest(BaseModel):
    """Request to resume a paused execution."""

    action: Optional[str] = Field(
        None, description="Action to take (approve, reject, respond, etc)"
    )
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional data associated with the resume action",
    )


class ResumeResponse(BaseModel):
    """Response from resuming execution."""

    success: bool = Field(..., description="True when the resume completed")
    status: str = Field(..., description="Execution status after resume")
    message: Optional[str] = Field(None, description="Human friendly status message")
    thread_id: Optional[str] = Field(
        None, description="Thread identifier for the resumed execution"
    )
    outputs: Optional[Any] = Field(
        None, description="Final workflow outputs if available"
    )
    execution_summary: Optional[Dict[str, Any]] = Field(
        None, description="Serialized execution summary"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional runtime metadata"
    )
    error: Optional[str] = Field(None, description="Error message if resume failed")


# Router
router = APIRouter(tags=["Execution"])


def _normalize_graph_identifier(identifier: str) -> str:
    """Normalize graph identifier to standard format."""
    # Handle URL encoding and alternative separators
    return identifier.replace("%3A%3A", "::").replace("/", "::")


def _to_serializable(value: Any) -> Any:
    """Convert dataclasses, datetimes, and nested structures into JSON-friendly values."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return _to_serializable(asdict(value))
    if isinstance(value, dict):
        return {key: _to_serializable(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_serializable(item) for item in value]
    return value


def _extract_execution_summary(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract and serialize an execution summary from a runtime payload."""
    summary = payload.get("execution_summary")
    if summary:
        return _to_serializable(summary)

    outputs = payload.get("outputs")
    if isinstance(outputs, dict) and outputs.get("__execution_summary"):
        return _to_serializable(outputs.get("__execution_summary"))

    final_state = payload.get("final_state")
    if isinstance(final_state, dict) and final_state.get("__execution_summary"):
        return _to_serializable(final_state.get("__execution_summary"))

    return None


def _sanitize_outputs(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return workflow outputs without the embedded execution summary."""
    outputs = payload.get("outputs")
    if outputs is None:
        return None

    if isinstance(outputs, dict):
        cleaned = dict(outputs)
        cleaned.pop("__execution_summary", None)
        return _to_serializable(cleaned)

    return _to_serializable(outputs)


def _build_execution_message(status: str, graph_identifier: str) -> str:
    """Create a user-friendly message for the execution response."""
    if status == "completed":
        return f"Graph '{graph_identifier}' completed successfully"
    if status == "suspended":
        return f"Graph '{graph_identifier}' suspended awaiting resume"
    return f"Graph '{graph_identifier}' failed to execute"


def _build_execute_response(
    graph_identifier: str,
    runtime_result: Dict[str, Any],
    execution_id: Optional[str],
) -> ExecuteResponse:
    """Normalize runtime facade response into ExecuteResponse."""
    interrupted = runtime_result.get("interrupted", False)
    success = bool(runtime_result.get("success")) and not interrupted
    status = "completed" if success else "suspended" if interrupted else "failed"

    response = ExecuteResponse(
        success=success,
        status=status,
        message=_build_execution_message(status, graph_identifier),
        thread_id=runtime_result.get("thread_id"),
        outputs=_sanitize_outputs(runtime_result),
        execution_summary=_extract_execution_summary(runtime_result),
        metadata=_to_serializable(runtime_result.get("metadata")),
        interrupt_info=_to_serializable(runtime_result.get("interrupt_info")),
        error=runtime_result.get("error"),
        execution_id=execution_id,
    )

    return response


def _build_resume_response(
    thread_id: str,
    runtime_result: Dict[str, Any],
) -> ResumeResponse:
    """Normalize runtime facade response into ResumeResponse."""
    success = bool(runtime_result.get("success"))
    summary = _extract_execution_summary(runtime_result)
    status = "completed"

    if summary and isinstance(summary, dict):
        status = summary.get("status", status)

    if not success and status == "completed":
        status = "failed"

    return ResumeResponse(
        success=success,
        status=status,
        message=(
            f"Successfully resumed thread '{thread_id}'"
            if success
            else f"Failed to resume thread '{thread_id}'"
        ),
        thread_id=thread_id,
        outputs=_sanitize_outputs(runtime_result),
        execution_summary=summary,
        metadata=_to_serializable(runtime_result.get("metadata")),
        error=runtime_result.get("error"),
    )


def _execute_workflow_internal(
    graph_identifier: str,
    request_body: ExecuteRequest,
    config_file: Optional[str] = None,
) -> ExecuteResponse:
    """Internal execution logic shared by all endpoints."""
    try:
        ensure_initialized(config_file=config_file)

        # Normalize identifier
        graph_identifier = _normalize_graph_identifier(graph_identifier)

        # Validate format
        if not graph_identifier or graph_identifier.count("::") > 1:
            raise InvalidInputs(f"Invalid graph identifier format: {graph_identifier}")

        # Execute using runtime facade
        result = run_workflow(
            graph_name=graph_identifier,
            inputs=request_body.inputs,
            force_create=request_body.force_create,
        )

        return _build_execute_response(
            graph_identifier, result, request_body.execution_id
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
    config_file = getattr(request.app.state, "config_file", None)
    return _execute_workflow_internal(graph_id, request_body, config_file)


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
    config_file = getattr(request.app.state, "config_file", None)
    return _execute_workflow_internal(graph_identifier, request_body, config_file)


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

    config_file = getattr(request.app.state, "config_file", None)
    return _execute_workflow_internal(graph_identifier, request_body, config_file)


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
        config_file = getattr(request.app.state, "config_file", None)
        ensure_initialized(config_file=config_file)

        # Validate thread_id
        if not thread_id or len(thread_id) < 10:
            raise InvalidInputs("Invalid thread ID")

        # Build resume token
        import json

        resume_payload = {
            "thread_id": thread_id,
            "response_action": request_body.action,
        }
        if request_body.data:
            resume_payload["response_data"] = request_body.data

        resume_token = json.dumps(resume_payload)

        # Resume using runtime facade
        result = resume_workflow(resume_token=resume_token, config_file=config_file)

        return _build_resume_response(thread_id, result)

    except InvalidInputs as e:
        raise HTTPException(status_code=400, detail=str(e))
    except AgentMapNotInitialized as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
