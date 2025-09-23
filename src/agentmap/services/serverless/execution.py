"""
Execution service for coordinating graph execution.

This service handles the execution of graphs using the workflow orchestration
service and provides a clean interface for the serverless handler.
"""

from agentmap.models.serverless_models import ExecutionParams, ExecutionResult
from agentmap.services.workflow_orchestration_service import (
    WorkflowOrchestrationService,
)


class ExecutionService:
    """Service for executing graphs via the workflow orchestration service."""

    def __init__(self, container, adapter):
        """Initialize with DI container and adapter."""
        self.container = container
        self.adapter = adapter

    async def run(self, params: ExecutionParams) -> ExecutionResult:
        """
        Execute graph with given parameters.

        Args:
            params: Execution parameters

        Returns:
            ExecutionResult with success/failure information
        """
        try:
            # Use the workflow orchestration service for execution
            result = WorkflowOrchestrationService.execute_workflow(
                workflow=params.csv,
                graph_name=params.graph,
                initial_state=params.state,
                config_file=None,  # Use default config
                validate_csv=False,  # Skip validation in serverless
                csv_override=None,
            )

            # Convert workflow result to execution result
            if result.success:
                return ExecutionResult(
                    success=True, data=result.final_state, status_code=200
                )
            else:
                return ExecutionResult(
                    success=False, error=result.error, status_code=500
                )

        except Exception as e:
            # Use adapter for consistent error handling
            error_info = self.adapter.handle_execution_error(e)
            return ExecutionResult(
                success=False,
                error=error_info["error"],
                status_code=error_info["status_code"],
            )

    async def _maybe_async(self, fn, *args, **kwargs):
        """
        Helper to handle potentially async functions.

        Args:
            fn: Function to call
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function result, awaited if necessary
        """
        result = fn(*args, **kwargs)
        if hasattr(result, "__await__"):
            return await result
        return result
