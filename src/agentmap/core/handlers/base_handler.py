"""
Base serverless handler with shared logic.

This module provides the base class for serverless function handlers
that use the new service architecture through dependency injection.
"""

import json
import traceback
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from agentmap.core.adapters import create_service_adapter, validate_run_parameters
from agentmap.di import ApplicationContainer, initialize_di


class BaseHandler(ABC):
    """Base serverless handler with shared logic."""

    def __init__(self, container: Optional[ApplicationContainer] = None):
        """Initialize base handler."""
        self.container = container or initialize_di()
        self.adapter = create_service_adapter(self.container)

    def handle_request(
        self, event: Dict[str, Any], context: Any = None
    ) -> Dict[str, Any]:
        """
        Common request handling logic for all serverless platforms.

        Args:
            event: Event data from serverless platform
            context: Context object from serverless platform

        Returns:
            Dict containing response data
        """
        try:
            # Parse request data
            request_data = self._parse_event(event)

            # Validate parameters
            self._validate_request(request_data)

            # Route to appropriate handler
            action = request_data.get("action", "run")

            if action == "run":
                return self._handle_run_request(request_data, context)
            elif action == "validate":
                return self._handle_validate_request(request_data, context)
            elif action == "compile":
                return self._handle_compile_request(request_data, context)
            elif action == "info":
                return self._handle_info_request(request_data, context)
            else:
                return self._create_error_response(f"Unknown action: {action}", 400)

        except Exception as e:
            return self._handle_error(e)

    def _handle_run_request(
        self, request_data: Dict[str, Any], context: Any = None
    ) -> Dict[str, Any]:
        """Handle graph execution request."""
        try:
            # Get services
            graph_runner_service, _, logging_service = (
                self.adapter.initialize_services()
            )
            logger = logging_service.get_logger("agentmap.serverless.run")

            # Create run options
            run_options = self.adapter.create_run_options(
                graph=request_data.get("graph"),
                csv=request_data.get("csv"),
                state=request_data.get("state", {}),
                autocompile=request_data.get("autocompile", False),
                execution_id=request_data.get("execution_id"),
            )

            logger.info(
                f"Serverless executing graph: {run_options.graph_name or 'default'}"
            )

            # Execute graph
            result = graph_runner_service.run_graph(run_options)

            # Convert result
            output = self.adapter.extract_result_state(result)

            if result.success:
                return self._create_success_response(output)
            else:
                return self._create_error_response(result.error_message, 500)

        except Exception as e:
            return self._handle_error(e)

    def _handle_validate_request(
        self, request_data: Dict[str, Any], context: Any = None
    ) -> Dict[str, Any]:
        """Handle validation request."""
        try:
            from agentmap.core.cli.validation_commands import validate_csv_command

            result = validate_csv_command(
                csv_path=request_data.get("csv"),
                no_cache=request_data.get("no_cache", False),
            )

            return self._create_success_response(result)

        except Exception as e:
            return self._handle_error(e)

    def _handle_compile_request(
        self, request_data: Dict[str, Any], context: Any = None
    ) -> Dict[str, Any]:
        """Handle compilation request."""
        try:
            from agentmap.core.cli.run_commands import compile_graph_command

            result = compile_graph_command(
                graph=request_data.get("graph"),
                csv=request_data.get("csv"),
                output_dir=request_data.get("output_dir"),
                state_schema=request_data.get("state_schema", "dict"),
                validate_first=request_data.get("validate", True),
            )

            return self._create_success_response(result)

        except Exception as e:
            return self._handle_error(e)

    def _handle_info_request(
        self, request_data: Dict[str, Any], context: Any = None
    ) -> Dict[str, Any]:
        """Handle system information request."""
        try:
            from agentmap.core.cli.diagnostic_commands import get_system_info_command

            info = get_system_info_command()
            return self._create_success_response(info)

        except Exception as e:
            return self._handle_error(e)

    @abstractmethod
    def _parse_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Parse platform-specific event format."""

    def _validate_request(self, request_data: Dict[str, Any]) -> None:
        """Validate common request parameters."""
        if "csv" in request_data and "state" in request_data:
            validate_run_parameters(
                csv=request_data["csv"], state=request_data["state"]
            )

    def _create_success_response(self, data: Any) -> Dict[str, Any]:
        """Create standardized success response."""
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            },
            "body": json.dumps({"success": True, "data": data}),
        }

    def _create_error_response(
        self, error_message: str, status_code: int = 500
    ) -> Dict[str, Any]:
        """Create standardized error response."""
        return {
            "statusCode": status_code,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            },
            "body": json.dumps({"success": False, "error": error_message}),
        }

    def _handle_error(self, error: Exception) -> Dict[str, Any]:
        """Handle errors with proper logging and response formatting."""
        try:
            # Try to get logger if services are available
            _, _, logging_service = self.adapter.initialize_services()
            logger = logging_service.get_logger("agentmap.serverless.error")
            logger.error(f"Serverless handler error: {error}", exc_info=True)
        except:
            # Fallback if logging service unavailable
            print(f"Serverless handler error: {error}")
            print(traceback.format_exc())

        # Use adapter for consistent error handling
        error_info = self.adapter.handle_execution_error(error)

        return self._create_error_response(
            error_info["error"], error_info["status_code"]
        )


class RequestParser:
    """Utility class for parsing different request formats."""

    @staticmethod
    def parse_json_body(body: str) -> Dict[str, Any]:
        """Parse JSON body with error handling."""
        if not body:
            return {}

        try:
            return json.loads(body)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in request body: {e}")

    @staticmethod
    def extract_query_params(event: Dict[str, Any]) -> Dict[str, Any]:
        """Extract query parameters from event."""
        return event.get("queryStringParameters") or {}

    @staticmethod
    def extract_path_params(event: Dict[str, Any]) -> Dict[str, Any]:
        """Extract path parameters from event."""
        return event.get("pathParameters") or {}

    @staticmethod
    def get_http_method(event: Dict[str, Any]) -> str:
        """Get HTTP method from event."""
        return event.get("httpMethod", "POST").upper()
