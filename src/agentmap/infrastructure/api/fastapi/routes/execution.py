"""
Execution routes for FastAPI server.

This module provides API endpoints for running and resuming workflows
using the new service architecture with RESTful routing patterns.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from agentmap.core.adapters import create_service_adapter
from agentmap.di import ApplicationContainer
from agentmap.infrastructure.api.fastapi.validation.common_validation import (
    ErrorHandler,
    RequestValidator,
    ValidatedResumeWorkflowRequest,
    ValidatedStateExecutionRequest,
    validate_request_size,
)
from agentmap.infrastructure.interaction.cli_handler import CLIInteractionHandler


# Request models (enhanced with validation)
class StateExecutionRequest(ValidatedStateExecutionRequest):
    """Request model for path-based execution with just state."""

    class Config:
        schema_extra = {
            "example": {
                "state": {
                    "user_input": "Process customer inquiry about pricing",
                    "customer_id": "CUST-12345",
                    "priority": "high",
                    "metadata": {"source": "api", "timestamp": "2024-01-15T10:30:00Z"},
                },
                "autocompile": True,
                "execution_id": "exec-2024-0115-001",
            },
            "description": "Execute a workflow graph with initial state and optional compilation",
        }


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
    autocompile: bool = Field(
        default=False,
        description="Whether to automatically compile the graph if missing",
    )
    execution_id: Optional[str] = Field(
        None, description="Optional execution tracking identifier"
    )

    class Config:
        schema_extra = {
            "example": {
                "graph": "customer_support_flow",
                "workflow": "customer_service",
                "state": {
                    "ticket_id": "TICKET-7890",
                    "customer_message": "I need help with my order",
                    "urgency": "medium",
                },
                "autocompile": True,
                "execution_id": "legacy-exec-001",
            },
            "description": "Legacy endpoint supporting flexible parameter combinations for backward compatibility",
        }


class ResumeWorkflowRequest(ValidatedResumeWorkflowRequest):
    """Request model for resuming an interrupted workflow."""

    class Config:
        schema_extra = {
            "example": {
                "thread_id": "thread-uuid-12345",
                "response_action": "approve",
                "response_data": {
                    "user_decision": "approved",
                    "comments": "Looks good, proceed with processing",
                    "reviewer_id": "USER-456",
                },
            },
            "description": "Resume a paused workflow by providing user response or decision",
        }


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

    class Config:
        schema_extra = {
            "examples": [
                {
                    "name": "Successful Execution",
                    "value": {
                        "success": True,
                        "output": {
                            "final_response": "Customer inquiry has been processed successfully",
                            "ticket_status": "resolved",
                            "resolution_time": "00:03:45",
                            "assigned_agent": "AI-Agent-Support",
                        },
                        "execution_id": "exec-2024-0115-001",
                        "execution_time": 3.45,
                        "metadata": {
                            "nodes_executed": 7,
                            "llm_calls_made": 3,
                            "total_tokens": 1250,
                        },
                    },
                },
                {
                    "name": "Failed Execution",
                    "value": {
                        "success": False,
                        "output": None,
                        "error": "Graph compilation failed: Missing required agent type 'custom_llm'",
                        "execution_id": "exec-2024-0115-002",
                        "execution_time": 0.15,
                        "metadata": {
                            "error_node": "process_inquiry",
                            "error_type": "AgentNotFound",
                        },
                    },
                },
            ]
        }


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


# Import dependency injection functions from shared dependencies module
from agentmap.infrastructure.api.fastapi.dependencies import (
    get_app_config_service,
    get_container,
    get_service_adapter,
    get_storage_service_manager,
)

# Create router
router = APIRouter(prefix="/execution", tags=["Execution"])


# Use enhanced validation from common_validation module
_validate_workflow_name = RequestValidator.validate_workflow_name
_validate_graph_name = RequestValidator.validate_graph_name


def _resolve_workflow_path(workflow_name: str, app_config_service) -> Path:
    """
    Resolve workflow name to full CSV file path.

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


@router.post(
    "/{workflow}/{graph}",
    response_model=GraphRunResponse,
    summary="Execute Workflow Graph",
    description="Run a specific graph from a workflow stored in the CSV repository",
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
async def run_workflow_graph(
    workflow: str,
    graph: str,
    request: StateExecutionRequest,
    adapter=Depends(get_service_adapter),
    app_config_service=Depends(get_app_config_service),
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
    - `autocompile`: Whether to compile the graph if not already compiled
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
           "autocompile": true,
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
    logger = None  # Initialize logger to None

    try:
        # Enhanced validation
        validated_workflow = _validate_workflow_name(workflow)
        validated_graph = _validate_graph_name(graph)

        # Resolve workflow path with size validation
        workflow_path = _resolve_workflow_path(validated_workflow, app_config_service)

        # Validate resolved CSV file size (skips path traversal checks since path is system-resolved)
        RequestValidator.validate_system_file_path(
            workflow_path, RequestValidator.MAX_CSV_SIZE
        )

        # Get services
        graph_runner_service, _, logging_service = adapter.initialize_services()

        # Safely get logger, handling None logging_service
        if logging_service is not None:
            logger = logging_service.get_logger("agentmap.api.execution")

        # Create run options
        run_options = adapter.create_run_options(
            graph=validated_graph,
            csv=str(workflow_path),
            state=request.state,
            autocompile=request.autocompile,
            execution_id=request.execution_id,
        )

        if logger:
            logger.info(
                f"API executing workflow '{validated_workflow}' graph '{validated_graph}'"
            )

        # Execute graph with timeout handling
        if graph_runner_service is None:
            raise HTTPException(
                status_code=503, detail="Graph runner service not available"
            )

        try:
            result = graph_runner_service.run_graph(run_options)
        except TimeoutError:
            raise ErrorHandler.create_error_response(
                error_message="Execution timeout",
                error_code="TIMEOUT",
                status_code=408,
                detail="Graph execution exceeded maximum allowed time",
            )

        # Convert to response format
        if result.success:
            output_data = adapter.extract_result_state(result)
            return GraphRunResponse(
                success=True,
                output=output_data["final_state"],
                execution_id=request.execution_id,  # Pass through from request
                execution_time=result.total_duration,
                metadata=output_data["metadata"],
            )
        else:
            return GraphRunResponse(
                success=False,
                error=result.error,
                execution_id=request.execution_id,  # Pass through from request
                execution_time=result.total_duration,
            )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except ValueError as e:
        raise ErrorHandler.handle_validation_error("request", str(e))
    except FileNotFoundError as e:
        raise ErrorHandler.handle_file_not_found(str(e), "workflow")
    except Exception as e:
        # Safely log error only if logger is available
        if logger:
            logger.error(f"API execution error: {e}")
        raise ErrorHandler.handle_service_error("execution", e)


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
async def run_graph_legacy(
    request: GraphRunRequest,
    adapter=Depends(get_service_adapter),
    app_config_service=Depends(get_app_config_service),
):
    """
    **Legacy Graph Execution Endpoint**
    
    This endpoint maintains backward compatibility while supporting both
    CSV path specification and workflow repository lookup. Use the RESTful
    `/{workflow}/{graph}` endpoint for new integrations.
    
    **Parameter Priority:**
    1. `csv` parameter (direct file path)
    2. `workflow` parameter (repository lookup)
    3. Default configuration file
    
    **Example Request with Workflow:**
    ```bash
    curl -X POST "http://localhost:8000/execution/run" \\
         -H "Content-Type: application/json" \\
         -d '{
           "graph": "support_flow",
           "workflow": "customer_service",
           "state": {"priority": "high"},
           "autocompile": true
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
    
    **Authentication:** Same as other execution endpoints
    """
    logger = None  # Initialize logger to None

    try:
        # Get services
        graph_runner_service, _, logging_service = adapter.initialize_services()

        # Safely get logger, handling None logging_service
        if logging_service is not None:
            logger = logging_service.get_logger("agentmap.api.execution")

        # Determine CSV path - priority: csv parameter, workflow lookup, default config
        csv_path = None
        if request.csv:
            csv_path = request.csv
        elif request.workflow:
            workflow_path = _resolve_workflow_path(request.workflow, app_config_service)
            csv_path = str(workflow_path)
        # If neither csv nor workflow specified, adapter will use default from config

        # Create run options
        run_options = adapter.create_run_options(
            graph=request.graph,
            csv=csv_path,
            state=request.state,
            autocompile=request.autocompile,
            execution_id=request.execution_id,
        )

        if logger:
            logger.info(f"API executing graph: {request.graph or 'default'}")

        # Execute graph
        if graph_runner_service is None:
            raise HTTPException(
                status_code=503, detail="Graph runner service not available"
            )

        result = graph_runner_service.run_graph(run_options)

        # Convert to response format
        if result.success:
            output_data = adapter.extract_result_state(result)
            return GraphRunResponse(
                success=True,
                output=output_data["final_state"],
                execution_id=request.execution_id,  # Pass through from request
                execution_time=result.total_duration,
                metadata=output_data["metadata"],
            )
        else:
            return GraphRunResponse(
                success=False,
                error=result.error,
                execution_id=request.execution_id,  # Pass through from request
                execution_time=result.total_duration,
            )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        # Safely log error only if logger is available
        if logger:
            logger.error(f"API execution error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
async def resume_workflow(
    request: ResumeWorkflowRequest,
    storage_manager=Depends(get_storage_service_manager),
    container: ApplicationContainer = Depends(get_container),
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
    logger = None  # Initialize logger to None

    try:
        # Check if storage is available
        if not storage_manager:
            raise HTTPException(
                status_code=503,
                detail="Storage services are not available. Please check your configuration.",
            )

        # Get the JSON storage service for structured data
        storage_service = storage_manager.get_service("json")
        logging_service = container.logging_service()

        # Safely get logger, handling None logging_service
        if logging_service is not None:
            logger = logging_service.get_logger("agentmap.api.resume")

        # Create CLI interaction handler instance
        handler = CLIInteractionHandler(storage_service)

        # Log the resume attempt
        if logger:
            logger.info(
                f"Resuming thread '{request.thread_id}' with action '{request.response_action}'"
            )

        # Call handler.resume_execution()
        result = handler.resume_execution(
            thread_id=request.thread_id,
            response_action=request.response_action,
            response_data=request.response_data,
        )

        # Return success response
        return ResumeWorkflowResponse(
            success=True,
            thread_id=request.thread_id,
            response_action=request.response_action,
            message=f"Successfully resumed thread '{request.thread_id}' with action '{request.response_action}'",
        )

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except ValueError as e:
        # Handle not found errors gracefully
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        # Handle storage errors
        raise HTTPException(status_code=503, detail=f"Storage error: {e}")
    except Exception as e:
        # Handle unexpected errors
        # Safely log error only if logger is available
        if logger:
            logger.error(f"Unexpected error in resume endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")
