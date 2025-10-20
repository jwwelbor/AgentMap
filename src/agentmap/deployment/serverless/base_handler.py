"""
Enhanced base serverless handler supporting multiple trigger types (run-only).

This module follows SPEC-DEP-001 by using only the runtime facade and
providing a clean, consistent interface for all serverless platforms.
"""

import asyncio
import json
import traceback
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from agentmap.deployment.serverless.trigger_strategies import (
    AwsDdbStreamStrategy,
    AwsEventBridgeTimerStrategy,
    AwsS3Strategy,
    AwsSqsStrategy,
    AzureEventGridStrategy,
    GcpPubSubStrategy,
    HttpStrategy,
)
from agentmap.exceptions.runtime_exceptions import (
    AgentMapNotInitialized,
    GraphNotFound,
    InvalidInputs,
)

# Models and utilities (not services)
from agentmap.models.serverless_models import (
    ExecutionParams,
    ExecutionRequest,
    ExecutionResult,
    RequestContext,
)
from agentmap.models.serverless_models import TriggerType as NewTriggerType

# ✅ FACADE PATTERN: Only import from runtime facade
from agentmap.runtime_api import ensure_initialized, run_workflow


# Legacy TriggerType enum for backward compatibility
class TriggerType(Enum):
    """Supported trigger types for serverless functions."""

    HTTP = "http"
    MESSAGE_QUEUE = "queue"
    DATABASE = "database"
    TIMER = "timer"
    STORAGE = "storage"


# CORS headers used by both handlers
CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


class TriggerParser:
    """Simple trigger parser that determines trigger type and extracts data."""

    def __init__(self, strategies=None):
        """Initialize with parsing strategies."""
        self.strategies = strategies or [
            HttpStrategy(),
            AwsSqsStrategy(),
            AwsS3Strategy(),
            AwsDdbStreamStrategy(),
            AwsEventBridgeTimerStrategy(),
            AzureEventGridStrategy(),
            GcpPubSubStrategy(),
        ]

    def parse(self, event: Dict[str, Any]) -> tuple[NewTriggerType, Dict[str, Any]]:
        """Parse event and return trigger type and normalized data."""
        for strategy in self.strategies:
            if strategy.can_handle(event):
                return strategy.parse(event)

        # Default to HTTP if no strategy matches
        return NewTriggerType.HTTP, {
            "graph": event.get("graph"),
            "state": event.get("state", {}),
            "csv": event.get("csv"),
        }


class BaseHandler:
    """Serverless handler following facade pattern (run-only)."""

    def __init__(self, config_file: Optional[str] = None):
        """Initialize handler using facade pattern."""
        self.config_file = config_file

        # Initialize trigger parser with all strategies
        self.trigger_parser = TriggerParser()

        # ✅ FACADE PATTERN: Ensure runtime is initialized once
        ensure_initialized(config_file=config_file)

    async def handle_request(
        self, event: Dict[str, Any], context: Any = None
    ) -> Dict[str, Any]:
        """
        Enhanced async request handling using facade pattern.

        Args:
            event: Event data from serverless platform
            context: Context object from serverless platform

        Returns:
            Dict containing response data
        """
        correlation_id = str(uuid.uuid4())

        try:
            # Parse trigger using strategy pattern
            trigger_type, parsed_data = self.trigger_parser.parse(event)

            # Log trigger information
            self._log_trigger_info(trigger_type, correlation_id, parsed_data)

            # Check for resume action (auto-resume via message)
            if parsed_data.get("action") == "resume":
                return await self._handle_resume_action(parsed_data, correlation_id)

            # Build execution parameters
            graph_name = parsed_data.get("graph")
            if not graph_name:
                raise InvalidInputs("Graph name is required")

            # Handle special database trigger case
            if (
                trigger_type == NewTriggerType.DATABASE
                and "database_event" in parsed_data
            ):
                inputs = parsed_data["database_event"].get("data", {})
            else:
                inputs = parsed_data.get("state", {})

            # ✅ FACADE PATTERN: Use only runtime facade
            result = run_workflow(
                graph_name=graph_name,
                inputs=inputs,
                config_file=self.config_file,
            )

            # Format HTTP response
            response = self._format_http_response(result, correlation_id)

            # TODO: Optional result publishing for async triggers
            # This would need to be implemented through the facade if needed

            return response

        except (GraphNotFound, InvalidInputs, AgentMapNotInitialized) as e:
            return self._handle_facade_error(e, correlation_id)
        except Exception as e:
            return self._handle_error(e, correlation_id)

    def handle_request_sync(
        self, event: Dict[str, Any], context: Any = None
    ) -> Dict[str, Any]:
        """Synchronous wrapper for platforms requiring sync entrypoint."""
        return asyncio.run(self.handle_request(event, context))

    def _log_trigger_info(
        self,
        trigger_type: NewTriggerType,
        correlation_id: str,
        parsed_data: Dict[str, Any],
    ) -> None:
        """Log trigger information for debugging."""
        # Simple logging since we can't access services directly
        print(
            f"Serverless trigger: {trigger_type.value}, "
            f"Correlation: {correlation_id}, "
            f"Graph: {parsed_data.get('graph', 'unknown')}"
        )

    def _format_http_response(
        self, result: Dict[str, Any], correlation_id: str
    ) -> Dict[str, Any]:
        """Format execution result as HTTP response."""
        if result.get("success", False):
            body = {
                "success": True,
                "data": result.get("outputs", {}),
                "correlation_id": correlation_id,
                "metadata": result.get("metadata", {}),
            }
            return {
                "statusCode": 200,
                "headers": CORS_HEADERS,
                "body": json.dumps(body),
            }
        else:
            return self._format_error_response(
                result.get("error", "Unknown error"), 500, correlation_id
            )

    def _format_error_response(
        self, message: str, status_code: int, correlation_id: str
    ) -> Dict[str, Any]:
        """Format error as HTTP response."""
        body = {"success": False, "error": message, "correlation_id": correlation_id}
        return {
            "statusCode": status_code,
            "headers": CORS_HEADERS,
            "body": json.dumps(body),
        }

    def _handle_facade_error(
        self, error: Exception, correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Handle facade exceptions with proper status codes."""
        correlation_id = correlation_id or "unknown"

        # Map facade exceptions to HTTP status codes per SPEC-EXC-000
        if isinstance(error, GraphNotFound):
            return self._format_error_response(str(error), 404, correlation_id)
        elif isinstance(error, InvalidInputs):
            return self._format_error_response(str(error), 400, correlation_id)
        elif isinstance(error, AgentMapNotInitialized):
            return self._format_error_response(str(error), 503, correlation_id)
        else:
            return self._format_error_response(str(error), 500, correlation_id)

    def _handle_error(
        self, error: Exception, correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Handle unexpected errors with proper logging."""
        correlation_id = correlation_id or "unknown"

        # Simple error logging
        print(f"Serverless handler error: {error} (Correlation: {correlation_id})")
        print(traceback.format_exc())

        return self._format_error_response("Internal server error", 500, correlation_id)

    async def _handle_resume_action(
        self, parsed_data: Dict[str, Any], correlation_id: str
    ) -> Dict[str, Any]:
        """
        Handle resume action from message broker (auto-resume pattern).

        Args:
            parsed_data: Parsed event data containing resume information
            correlation_id: Request correlation ID for logging

        Returns:
            Dict containing HTTP response data
        """
        thread_id = parsed_data.get("thread_id")
        if not thread_id:
            raise InvalidInputs("Resume action requires thread_id")

        resume_value = parsed_data.get("resume_value")

        # Build resume token for runtime facade
        import json

        resume_token = json.dumps(
            {
                "thread_id": thread_id,
                "response_action": "continue",
                "response_data": resume_value,
            }
        )

        # ✅ FACADE PATTERN: Use runtime facade for resume
        from agentmap.runtime_api import resume_workflow

        result = resume_workflow(
            resume_token=resume_token, config_file=self.config_file
        )

        # Format HTTP response
        return self._format_http_response(result, correlation_id)
