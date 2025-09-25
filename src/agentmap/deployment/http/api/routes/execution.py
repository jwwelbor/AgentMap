"""
Execution routes for FastAPI server.

This module provides API endpoints for running and resuming workflows
using the runtime facade pattern per SPEC-DEP-001 for consistent behavior
across all deployment adapters.
"""

from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from agentmap.deployment.http.api.dependencies import requires_auth
from agentmap.deployment.http.api.validation.common_validation import (
    ErrorHandler,
    RequestValidator,
    ValidatedResumeWorkflowRequest,
    ValidatedStateExecutionRequest,
    validate_request_size,
)
from agentmap.exceptions.runtime_exceptions import (
    AgentMapNotInitialized,
    GraphNotFound,
    InvalidInputs,
)

# Use runtime facade instead of direct service access
from agentmap.runtime_api import ensure_initialized, resume_workflow, run_workflow


# Request models (enhanced with validation)
class StateExecutionRequest(ValidatedStateExecutionRequest):
    """Request model for path-based execution with just state."""


class GraphRunRequest(BaseModel):
    """Legacy request model for running a graph with all parameters."""

    graph: Optional[str] = Field(
        None, description="Graph name to execute (defaults to first graph in CSV)"
    )
    csv: Optional[str] = Field(
        None, description="Direct CSV file path (alternative to workflow parameter)"
    )
    workflow: Optional[str] = Field(
        None,
        description="Workflow name for repository lookup (alternative to csv parameter)",
    )
    state: Dict[str, Any] = Field(
        default={}, description="Initial state variables passed to the graph"
    )
    execution_id: Optional[str] = Field(
        None, description="Optional execution tracking identifier"
    )


class ResumeWorkflowRequest(ValidatedResumeWorkflowRequest):
    """Request model for resuming an interrupted workflow."""


# Response models
class GraphRunResponse(BaseModel):
    """Response model for graph execution."""

    success: bool = Field(
        ..., description="Whether the graph execution completed successfully"
    )
    output: Optional[Dict[str, Any]] = Field(
        None, description="Final state and output data from successful execution"
    )
    error: Optional[str] = Field(None, description="Error message if execution failed")
    execution_id: Optional[str] = Field(
        None, description="Unique identifier for this execution"
    )
    execution_time: Optional[float] = Field(
        None, description="Total execution time in seconds"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional execution metadata and statistics"
    )


class ResumeWorkflowResponse(BaseModel):
    """Response model for workflow resumption."""

    success: bool = Field(
        ..., description="Whether the workflow resumption was successful"
    )
    thread_id: str = Field(..., description="Thread ID that was resumed")
    response_action: str = Field(
        ..., description="The response action that was processed"
    )
    message: str = Field(..., description="Human-readable status message")
    error: Optional[str] = Field(None, description="Error message if resumption failed")

    class Config:
        schema_extra = {
            "examples": [
                {
                    "name": "Successful Resumption",
                    "value": {
                        "success": True,
                        "thread_id": "thread-uuid-12345",
                        "response_action": "approve",
                        "message": "Successfully resumed thread 'thread-uuid-12345' with action 'approve'",
                        "error": None,
                    },
                },
                {
                    "name": "Failed Resumption",
                    "value": {
                        "success": False,
                        "thread_id": "thread-uuid-67890",
                        "response_action": "reject",
                        "message": "Failed to resume workflow",
                        "error": "Thread 'thread-uuid-67890' not found or already completed",
                    },
                },
            ]
        }


# Create router
router = APIRouter(prefix="/execution", tags=["Execution"])


# Use enhanced validation from common_validation module
_validate_workflow_name = RequestValidator.validate_workflow_name
_validate_graph_name = RequestValidator.validate_graph_name


# IMPORTANT: Define specific routes BEFORE generic ones to avoid matching conflicts
@router.post(
    "/run",
    response_model=GraphRunResponse,
    summary="Execute Graph (Legacy)",
    description="Legacy endpoint for running graphs with flexible parameter support",
    response_description="Execution results with backward compatibility",
    responses={
        200: {"description": "Graph executed successfully"},
        400: {"description": "Invalid request parameters"},
        404: {"description": "Workflow or CSV file not found"},
        500: {"description": "Internal execution error"},
    },
    tags=["Execution"],
    deprecated=False,  # Still supported for backward compatibility
)
@requires_auth("execute")
async def run_graph_legacy(
    execution_request: GraphRunRequest,
    request: Request,
):
    """
    **Legacy Graph Execution Endpoint**
    
    This endpoint maintains backward compatibility while supporting both
    CSV path specification and workflow repository lookup. Now also supports
    the simplified filename::graph_name syntax in any parameter.
    
    **Supported Syntax Formats:**
    - `filename::graph_name` - Direct CSV file with specific graph
    - Traditional workflow/graph combinations
    - Direct file paths
    
    **Parameter Priority:**
    1. `csv` parameter (direct file path or filename::graph_name)
    2. `workflow` parameter (repository lookup or filename::graph_name)
    3. `graph` parameter (simple name or filename::graph_name)
    4. Default configuration file
    
    **Example Request with Workflow:**
    ```bash
    curl -X POST "http://localhost:8000/execution/run" \\
         -H "Content-Type: application/json" \\
         -d '{
           "graph": "support_flow",
           "workflow": "customer_service",
           "state": {"priority": "high"},
         }'
    ```
    
    **Example Request with Direct CSV:**
    ```bash
    curl -X POST "http://localhost:8000/execution/run" \\
         -H "Content-Type: application/json" \\
         -d '{
           "csv": "/path/to/workflow.csv",
           "graph": "my_graph",
           "state": {"input": "data"}
         }'
    ```
    
    **Example Request with :: Syntax:**
    ```bash
    curl -X POST "http://localhost:8000/execution/run" \\
         -H "Content-Type: application/json" \\
         -d '{
           "workflow": "customer_data::support_flow",
           "state": {"priority": "high"}
         }'
    ```
    
    **Authentication:** Same as other execution endpoints
    """
    try:
        # Ensure runtime is initialized
        ensure_initialized()

        # Determine graph name - now supports :: syntax
        graph_name = None
        if execution_request.csv:
            # Direct CSV path - check for :: syntax
            if execution_request.graph and "::" not in execution_request.csv:
                # Traditional csv + graph combination
                graph_name = f"{execution_request.csv}/{execution_request.graph}"
            else:
                # Either :: syntax already in csv, or no graph specified
                graph_name = execution_request.csv
        elif execution_request.workflow:
            # Workflow repository lookup - check for :: syntax
            if "::" in execution_request.workflow:
                # :: syntax in workflow parameter
                graph_name = execution_request.workflow
            elif execution_request.graph:
                # Traditional workflow + graph combination
                graph_name = f"{execution_request.workflow}/{execution_request.graph}"
            else:
                graph_name = execution_request.workflow
        else:
            # Just graph name or default - support :: syntax
            graph_name = execution_request.graph or "default"

        if not graph_name:
            raise InvalidInputs("No graph specified and no default configured")

        # Execute using runtime facade
        result = run_workflow(
            graph_name=graph_name,
            inputs=execution_request.state,
        )

        # Convert facade result to HTTP response format
        if result.get("success", False):
            outputs = result.get("outputs", {})
            metadata = result.get("metadata", {})

            return GraphRunResponse(
                success=True,
                output=outputs,
                execution_id=execution_request.execution_id,
                execution_time=None,  # Not provided by facade
                metadata=metadata,
            )
        else:
            error_msg = result.get("error", "Unknown execution error")
            return GraphRunResponse(
                success=False,
                error=error_msg,
                execution_id=execution_request.execution_id,
                execution_time=None,
            )

    except GraphNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidInputs as e:
        raise HTTPException(status_code=400, detail=str(e))
    except AgentMapNotInitialized as e:
        raise HTTPException(status_code=503, detail=str(e))
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")


@router.post(
    "/resume",
    response_model=ResumeWorkflowResponse,
    summary="Resume Interrupted Workflow",
    description="Resume a paused workflow by providing user response or decision",
    response_description="Resumption status and updated workflow state",
    responses={
        200: {"description": "Workflow resumed successfully"},
        400: {"description": "Invalid thread ID or response action"},
        404: {"description": "Thread not found or already completed"},
        503: {"description": "Storage services unavailable"},
    },
    tags=["Execution"],
)
@requires_auth("execute")
async def resume_workflow_endpoint(
    resume_request: ResumeWorkflowRequest,
    request: Request,
):
    """
    **Resume an Interrupted Workflow**
    
    This endpoint allows resumption of workflows that were paused for
    user interaction, approval, or decision-making. Workflows pause when
    they encounter nodes requiring human input or validation.
    
    **Request Parameters:**
    - `thread_id`: Unique identifier for the paused workflow thread
    - `response_action`: Action to take (approve, reject, choose, respond, etc.)
    - `response_data`: Additional data required for the response
    
    **Common Response Actions:**
    - `approve`: Approve the current step and continue
    - `reject`: Reject and trigger failure path
    - `choose`: Select from multiple options
    - `respond`: Provide text response
    - `edit`: Modify proposed content
    - `retry`: Retry the current operation
    
    **Example Request:**
    ```bash
    curl -X POST "http://localhost:8000/execution/resume" \\
         -H "Content-Type: application/json" \\
         -H "X-API-Key: your-api-key" \\
         -d '{
           "thread_id": "thread-uuid-12345",
           "response_action": "approve",
           "response_data": {
             "reviewer_comments": "Looks good to proceed",
             "timestamp": "2024-01-15T14:30:00Z"
           }
         }'
    ```
    
    **Success Response:**
    ```json
    {
      "success": true,
      "thread_id": "thread-uuid-12345",
      "response_action": "approve",
      "message": "Successfully resumed thread with approval"
    }
    ```
    
    **Prerequisites:**
    - Storage services must be configured and available
    - Thread must exist and be in a paused state
    - Response action must be valid for the current node type
    
    **Authentication:** Required - workflows contain sensitive state data
    """
    try:
        # Ensure runtime is initialized
        ensure_initialized()

        # Create resume token from request data
        import json

        resume_token_data = {
            "thread_id": resume_request.thread_id,
            "response_action": resume_request.response_action,
        }
        if resume_request.response_data:
            resume_token_data["response_data"] = resume_request.response_data

        resume_token = json.dumps(resume_token_data)

        # Execute using runtime facade
        result = resume_workflow(resume_token=resume_token)

        # Convert facade result to HTTP response format
        if result.get("success", False):
            return ResumeWorkflowResponse(
                success=True,
                thread_id=resume_request.thread_id,
                response_action=resume_request.response_action,
                message=f"Successfully resumed thread '{resume_request.thread_id}' with action '{resume_request.response_action}'",
            )
        else:
            error_msg = result.get("error", "Unknown resume error")
            return ResumeWorkflowResponse(
                success=False,
                thread_id=resume_request.thread_id,
                response_action=resume_request.response_action,
                message="Failed to resume workflow",
                error=error_msg,
            )

    except InvalidInputs as e:
        raise HTTPException(status_code=400, detail=str(e))
    except AgentMapNotInitialized as e:
        raise HTTPException(status_code=503, detail=str(e))
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")


# Now define the two-parameter endpoint
@router.post(
    "/{workflow}/{graph}",
    response_model=GraphRunResponse,
    summary="Execute Workflow Graph",
    description="Run a specific graph from a workflow stored in the CSV repository. Supports both traditional workflow/graph syntax and simplified filename::graph_name syntax (URL encode :: as %3A%3A).",
    response_description="Execution results including output state, metadata, and timing information",
    responses={
        200: {
            "description": "Graph executed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "output": {"result": "Task completed"},
                        "execution_id": "exec-123",
                        "execution_time": 2.5,
                    }
                }
            },
        },
        400: {"description": "Invalid workflow/graph names or request parameters"},
        404: {"description": "Workflow file or graph not found"},
        413: {"description": "Request payload too large (max 5MB)"},
        500: {"description": "Internal execution error"},
    },
    tags=["Execution"],
)
@validate_request_size(max_size=RequestValidator.MAX_JSON_SIZE)
@requires_auth("execute")
async def run_workflow_graph(
    workflow: str,
    graph: str,
    execution_request: StateExecutionRequest,
    request: Request,
):
    """
    **Execute a Specific Graph from Workflow Repository**
    
    This endpoint provides RESTful access to workflow execution by specifying
    both the workflow file and graph name in the URL path. It's the recommended
    approach for production usage as it clearly separates workflow identification
    from execution parameters.
    
    **Path Parameters:**
    - `workflow`: Name of the workflow file (without .csv extension)
    - `graph`: Name of the graph within the workflow to execute
    
    **Request Body:**
    - `state`: Initial state variables to pass to the graph
    - `execution_id`: Optional tracking identifier for monitoring
    
    **Example Request:**
    ```bash
    curl -X POST "http://localhost:8000/execution/customer_service/support_flow" \\
         -H "Content-Type: application/json" \\
         -H "X-API-Key: your-api-key" \\
         -d '{
           "state": {
             "customer_message": "I need help with my order",
             "ticket_id": "TICKET-123"
           },
           "execution_id": "my-execution-001"
         }'
    ```
    
    **Success Response (200):**
    ```json
    {
      "success": true,
      "output": {
        "final_response": "Your order status has been updated",
        "ticket_status": "resolved"
      },
      "execution_id": "my-execution-001",
      "execution_time": 3.2,
      "metadata": {
        "nodes_executed": 5,
        "llm_calls_made": 2
      }
    }
    ```
    
    **Error Response (404):**
    ```json
    {
      "detail": "Workflow file not found: customer_service.csv"
    }
    ```
    
    **Rate Limiting:** 60 requests per minute
    
    **Authentication:** 
    - API Key: `X-API-Key: your-key` (optional)
    - Bearer Token: `Authorization: Bearer token` (optional)
    - Public access allowed for embedded usage
    """
    try:
        # URL decode workflow parameter to handle encoded :: syntax
        from urllib.parse import unquote

        decoded_workflow = unquote(workflow)

        # Check if workflow contains :: syntax (filename::graph_name)
        if "::" in decoded_workflow:
            # Use the decoded workflow parameter as the full graph identifier
            graph_name = decoded_workflow
            # Validate the parts
            parts = decoded_workflow.split("::", 1)
            validated_workflow = _validate_workflow_name(parts[0])
            validated_graph = _validate_graph_name(parts[1])
        else:
            # Traditional workflow/graph syntax
            validated_workflow = _validate_workflow_name(decoded_workflow)
            validated_graph = _validate_graph_name(graph)
            graph_name = f"{validated_workflow}/{validated_graph}"

        # Ensure runtime is initialized
        ensure_initialized()

        # Execute using runtime facade
        result = run_workflow(
            graph_name=graph_name,
            inputs=execution_request.state,
        )

        # Convert facade result to HTTP response format
        if result.get("success", False):
            outputs = result.get("outputs", {})
            metadata = result.get("metadata", {})

            return GraphRunResponse(
                success=True,
                output=outputs,
                execution_id=execution_request.execution_id,
                execution_time=None,  # Not provided by facade
                metadata=metadata,
            )
        else:
            error_msg = result.get("error", "Unknown execution error")
            return GraphRunResponse(
                success=False,
                error=error_msg,
                execution_id=execution_request.execution_id,
                execution_time=None,
            )

    except GraphNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidInputs as e:
        raise HTTPException(status_code=400, detail=str(e))
    except AgentMapNotInitialized as e:
        raise HTTPException(status_code=503, detail=str(e))
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")


# Finally, the most generic single-parameter endpoint (must be last to avoid conflicts)
@router.post(
    "/{workflow_graph}",
    response_model=GraphRunResponse,
    summary="Execute Workflow Graph (Simplified Syntax)",
    description="Execute a graph using simplified filename::graph_name syntax or traditional workflow/graph syntax",
    response_description="Execution results including output state, metadata, and timing information",
    responses={
        200: {"description": "Graph executed successfully"},
        400: {"description": "Invalid workflow/graph syntax or request parameters"},
        404: {"description": "Workflow file or graph not found"},
        413: {"description": "Request payload too large (max 5MB)"},
        500: {"description": "Internal execution error"},
    },
    tags=["Execution"],
)
@validate_request_size(max_size=RequestValidator.MAX_JSON_SIZE)
@requires_auth("execute")
async def run_workflow_graph_simplified(
    workflow_graph: str,
    execution_request: StateExecutionRequest,
    request: Request,
):
    """
    **Execute Graph with Simplified Syntax**
    
    This endpoint accepts either filename::graph_name syntax or traditional workflow/graph syntax
    in a single parameter. URL encode :: as %3A%3A when using filename::graph_name format.
    
    **Supported Formats:**
    - `filename::graph_name` - Direct CSV file with specific graph
    - `workflow/graph` - Repository-based workflow with graph
    - `simple_name` - Defaults to simple_name.csv with graph name simple_name
    
    **Example Requests:**
    ```bash
    # Using :: syntax (URL encoded)
    curl -X POST "http://localhost:8000/execution/customer_data%3A%3Asupport_flow" \\
         -H "Content-Type: application/json" \\
         -d '{"state": {"priority": "high"}}'
    
    # Traditional syntax
    curl -X POST "http://localhost:8000/execution/customer_service/support_flow" \\
         -H "Content-Type: application/json" \\
         -d '{"state": {"priority": "high"}}'
    ```
    
    **Authentication:** Same as other execution endpoints
    """
    try:
        # URL decode the parameter to handle encoded :: syntax
        from urllib.parse import unquote

        decoded_graph_name = unquote(workflow_graph)

        # Validate the graph name format
        if "::" in decoded_graph_name:
            parts = decoded_graph_name.split("::", 1)
            if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
                raise InvalidInputs(
                    "Invalid :: syntax - expected format: filename::graph_name"
                )
            _validate_workflow_name(parts[0])
            _validate_graph_name(parts[1])
        elif "/" in decoded_graph_name:
            parts = decoded_graph_name.split("/")
            if len(parts) < 2:
                raise InvalidInputs(
                    "Invalid / syntax - expected format: workflow/graph"
                )
            _validate_workflow_name(parts[0])
            _validate_graph_name(parts[-1])
        else:
            _validate_workflow_name(decoded_graph_name)

        # Ensure runtime is initialized
        ensure_initialized()

        # Execute using runtime facade with the decoded graph name
        result = run_workflow(
            graph_name=decoded_graph_name,
            inputs=execution_request.state,
        )

        # Convert facade result to HTTP response format
        if result.get("success", False):
            outputs = result.get("outputs", {})
            metadata = result.get("metadata", {})

            return GraphRunResponse(
                success=True,
                output=outputs,
                execution_id=execution_request.execution_id,
                execution_time=None,  # Not provided by facade
                metadata=metadata,
            )
        else:
            error_msg = result.get("error", "Unknown execution error")
            return GraphRunResponse(
                success=False,
                error=error_msg,
                execution_id=execution_request.execution_id,
                execution_time=None,
            )

    except GraphNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidInputs as e:
        raise HTTPException(status_code=400, detail=str(e))
    except AgentMapNotInitialized as e:
        raise HTTPException(status_code=503, detail=str(e))
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")
