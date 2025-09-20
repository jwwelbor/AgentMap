"""
Core adapter functions for workflow orchestration and serverless functions.

This module provides utilities for result extraction, error handling, and response
formatting that will be used across CLI, API, and serverless handlers.

Updated to work with WorkflowOrchestrationService while preserving useful
conversion and formatting functionality.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional, Union

from dependency_injector.containers import Container

from agentmap.models.execution.result import ExecutionResult


class ServiceAdapter:
    """Adapter for result conversion, error handling, and response formatting."""

    def __init__(self, container: Container):
        """Initialize adapter with DI container."""
        self.container = container

    # REMOVED: create_run_options() - was deprecated, WorkflowOrchestrationService handles this

    def extract_result_state(self, result: ExecutionResult) -> Dict[str, Any]:
        """
        Convert ExecutionResult to standardized format for APIs and serverless.

        Args:
            result: ExecutionResult from WorkflowOrchestrationService.execute_workflow()

        Returns:
            Dict containing standardized result format
        """
        return {
            "final_state": result.final_state,
            "success": result.success,
            "error": result.error,
            "execution_time": result.total_duration,
            "metadata": {
                "graph_name": result.graph_name,
                "execution_summary": result.execution_summary,
            },
        }

    def handle_execution_error(self, error: Exception) -> Dict[str, Any]:
        """
        Standardize error responses across entry points.

        Args:
            error: Exception that occurred during execution

        Returns:
            Dict containing standardized error response
        """
        error_type = type(error).__name__

        # Map specific exceptions to appropriate status information
        status_info = {
            "ValueError": {"code": 400, "category": "validation"},
            "FileNotFoundError": {"code": 404, "category": "file"},
            "PermissionError": {"code": 403, "category": "permission"},
            "TimeoutError": {"code": 408, "category": "timeout"},
        }

        info = status_info.get(error_type, {"code": 500, "category": "internal"})

        return {
            "success": False,
            "error": str(error),
            "error_type": error_type,
            "error_category": info["category"],
            "status_code": info["code"],
        }

    def format_http_response(
        self,
        result: Union[ExecutionResult, Dict[str, Any]],
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Format ExecutionResult or resume result for HTTP response.

        Args:
            result: ExecutionResult from workflow execution or dict from resume
            correlation_id: Optional correlation ID for tracking

        Returns:
            Dict containing HTTP response format
        """
        if isinstance(result, ExecutionResult):
            # Handle workflow execution result
            if result.success:
                status_code = 200
                body = {"success": True, "data": self.extract_result_state(result)}
            else:
                status_code = 500
                body = {
                    "success": False,
                    "error": result.error,
                    "graph_name": result.graph_name,
                }
        else:
            # Handle resume result (dict format)
            if result.get("success"):
                status_code = 200
                body = {
                    "success": True,
                    "message": f"Successfully processed operation",
                    "data": result,
                }
            else:
                status_code = 500
                body = {
                    "success": False,
                    "error": result.get("error", "Operation failed"),
                }

        if correlation_id:
            body["correlation_id"] = correlation_id

        return {
            "statusCode": status_code,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            },
            "body": json.dumps(body),
        }

    def initialize_services(self):
        """
        Initialize services from DI container.

        Note: With WorkflowOrchestrationService, this is less commonly needed
        since the orchestration service handles DI internally.

        Returns:
            Tuple of commonly used services
        """
        try:
            graph_runner_service = self.container.graph_runner_service()
            app_config_service = self.container.app_config_service()
            logging_service = self.container.logging_service()

            return graph_runner_service, app_config_service, logging_service

        except Exception as e:
            raise RuntimeError(f"Failed to initialize services from DI container: {e}")

    # NEW: Helper methods for working with WorkflowOrchestrationService

    def validate_workflow_parameters(
        self,
        csv_or_workflow: Optional[str] = None,
        graph_name: Optional[str] = None,
        initial_state: Optional[Union[str, Dict[str, Any]]] = None,
    ) -> None:
        """
        Validate parameters for WorkflowOrchestrationService.execute_workflow()

        Args:
            csv_or_workflow: CSV file path or workflow name
            graph_name: Graph name to execute
            initial_state: Initial state dict or JSON string

        Raises:
            ValueError: If validation fails
        """
        # Validate initial_state if it's a JSON string
        if isinstance(initial_state, str) and initial_state.strip():
            try:
                json.loads(initial_state)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in initial_state: {e}")

        # Validate CSV file if it's a file path (not workflow name)
        if (
            csv_or_workflow
            and "/" in csv_or_workflow
            and csv_or_workflow.endswith(".csv")
        ):
            csv_path = Path(csv_or_workflow)
            if not csv_path.exists():
                raise ValueError(f"CSV file not found: {csv_path}")

    def validate_resume_parameters(
        self,
        thread_id: str,
        response_action: str,
        response_data: Optional[Union[str, Dict[str, Any]]] = None,
    ) -> None:
        """
        Validate parameters for WorkflowOrchestrationService.resume_workflow()

        Args:
            thread_id: Thread ID to resume
            response_action: Response action
            response_data: Response data dict or JSON string

        Raises:
            ValueError: If validation fails
        """
        if not thread_id or not thread_id.strip():
            raise ValueError("thread_id is required and cannot be empty")

        if not response_action or not response_action.strip():
            raise ValueError("response_action is required and cannot be empty")

        # Validate response_data if it's a JSON string
        if isinstance(response_data, str) and response_data.strip():
            try:
                json.loads(response_data)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in response_data: {e}")


def create_service_adapter(container: Container) -> ServiceAdapter:
    """
    Factory function to create ServiceAdapter instance.

    Args:
        container: DI container with configured services

    Returns:
        ServiceAdapter: Configured adapter instance
    """
    return ServiceAdapter(container)


# Legacy validation function - kept for backward compatibility
def validate_run_parameters(**params) -> None:
    """
    Validate common run parameters before processing.

    Note: This is kept for backward compatibility. New code should use
    ServiceAdapter.validate_workflow_parameters() instead.

    Args:
        **params: Parameters to validate

    Raises:
        ValueError: If validation fails
    """
    if "csv" in params and params["csv"]:
        csv_path = Path(params["csv"])
        if not csv_path.exists():
            raise ValueError(f"CSV file not found: {csv_path}")
        if not csv_path.suffix.lower() == ".csv":
            raise ValueError(f"File must have .csv extension: {csv_path}")

    if "state" in params and isinstance(params["state"], str):
        try:
            json.loads(params["state"])
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in state parameter: {e}")

    if "bundle_path" in params and params["bundle_path"]:
        bundle_path = Path(params["bundle_path"])
        if not bundle_path.exists():
            raise ValueError(f"Bundle file not found: {bundle_path}")


# NEW: Trigger parameter extraction helpers for serverless functions
class TriggerParameterExtractor:
    """Helper to extract parameters from serverless trigger events."""

    @staticmethod
    def extract_workflow_parameters(event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract workflow execution parameters from trigger event.

        Args:
            event: Trigger event from serverless platform

        Returns:
            Dict with parameters for WorkflowOrchestrationService.execute_workflow()
        """
        # HTTP triggers
        if "httpMethod" in event:
            if event.get("httpMethod").upper() == "POST":
                body = event.get("body", "{}")
                if isinstance(body, str):
                    try:
                        params = json.loads(body)
                    except json.JSONDecodeError:
                        params = {}
                else:
                    params = body or {}
            else:
                params = event.get("queryStringParameters") or {}

            # Add path parameters
            path_params = event.get("pathParameters") or {}
            params.update(path_params)

            return params

        # SQS/Queue triggers
        elif "Records" in event:
            record = event["Records"][0]
            body = record.get("body", "{}")
            if isinstance(body, str):
                try:
                    return json.loads(body)
                except json.JSONDecodeError:
                    return {"csv_or_workflow": "default"}
            return body

        # Direct invocation
        else:
            return event

    @staticmethod
    def extract_resume_parameters(event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract resume parameters from trigger event.

        Args:
            event: Trigger event from serverless platform

        Returns:
            Dict with parameters for WorkflowOrchestrationService.resume_workflow()
        """
        # Use same extraction logic but expect resume-specific fields
        params = TriggerParameterExtractor.extract_workflow_parameters(event)

        # Ensure we have required resume fields
        if "thread_id" not in params:
            # Try to get from path parameters
            path_params = event.get("pathParameters") or {}
            params["thread_id"] = path_params.get("thread_id")

        return params


# NEW: Response formatters for different contexts
class ResponseFormatter:
    """Helper to format responses for different contexts."""

    @staticmethod
    def for_cli(result: Union[ExecutionResult, Dict[str, Any]]) -> str:
        """Format result for CLI display."""
        if isinstance(result, ExecutionResult):
            if result.success:
                return f"✅ Execution completed: {result.final_state}"
            else:
                return f"❌ Execution failed: {result.error}"
        else:
            if result.get("success"):
                return f"✅ Operation completed successfully"
            else:
                return f"❌ Operation failed: {result.get('error', 'Unknown error')}"

    @staticmethod
    def for_api(result: Union[ExecutionResult, Dict[str, Any]]) -> Dict[str, Any]:
        """Format result for FastAPI response."""
        adapter = ServiceAdapter(None)  # No container needed for formatting
        return (
            adapter.extract_result_state(result)
            if isinstance(result, ExecutionResult)
            else result
        )

    @staticmethod
    def for_serverless(
        result: Union[ExecutionResult, Dict[str, Any]], correlation_id: str = None
    ) -> Dict[str, Any]:
        """Format result for serverless HTTP response."""
        adapter = ServiceAdapter(None)  # No container needed for formatting
        return adapter.format_http_response(result, correlation_id)
