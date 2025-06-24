"""
Google Cloud Function handler using the new service architecture.

This module provides Google Cloud Function handlers that maintain
compatibility with existing interfaces while using GraphRunnerService.
"""

import json
from typing import Any, Dict, Optional

from agentmap.core.handlers.base_handler import BaseHandler
from agentmap.di import ApplicationContainer


class GCPFunctionHandler(BaseHandler):
    """Google Cloud Function handler for AgentMap graph execution."""

    def _parse_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse Google Cloud Function request format.

        Args:
            event: GCP request object or event data

        Returns:
            Dict containing parsed request data
        """
        # Handle different GCP trigger types
        if hasattr(event, "method"):
            # HTTP trigger (Flask request object)
            return self._parse_http_request(event)
        elif isinstance(event, dict) and "data" in event:
            # Pub/Sub trigger
            return self._parse_pubsub_event(event)
        elif isinstance(event, dict) and "bucket" in event:
            # Cloud Storage trigger
            return self._parse_storage_event(event)
        else:
            # Direct call or other event type
            return event if isinstance(event, dict) else {}

    def _parse_http_request(self, request) -> Dict[str, Any]:
        """Parse HTTP request from Cloud Functions."""
        try:
            if request.method == "POST":
                # Parse JSON body
                request_json = request.get_json(silent=True)
                if request_json:
                    return request_json

                # Fallback to form data
                return dict(request.form)
            else:
                # GET request - use query parameters
                return dict(request.args)

        except Exception:
            # Fallback to empty dict if parsing fails
            return {}

    def _parse_pubsub_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Pub/Sub event."""
        try:
            # Decode Pub/Sub message
            import base64

            data = event.get("data", "")
            if data:
                decoded_data = base64.b64decode(data).decode("utf-8")
                return json.loads(decoded_data)

            # Fallback to attributes
            return event.get("attributes", {})

        except Exception:
            return {"action": "run", "trigger": "pubsub"}

    def _parse_storage_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Cloud Storage event."""
        return {
            "action": "run",
            "csv": event.get("name"),  # File name
            "bucket": event.get("bucket"),
            "trigger": "storage_upload",
        }

    def gcp_handler(self, request) -> Dict[str, Any]:
        """
        Google Cloud Function entry point for HTTP triggers.

        Args:
            request: Flask request object

        Returns:
            Dict containing response data
        """
        # Convert Flask request to our standard format
        event_data = self._parse_event(request)
        result = self.handle_request(event_data)

        # Return the body content for HTTP response
        if "body" in result:
            response_data = json.loads(result["body"])
            return response_data

        return result


# Global handler instance for Cloud Functions runtime
_gcp_handler_instance: Optional[GCPFunctionHandler] = None


def get_gcp_handler(
    container: Optional[ApplicationContainer] = None,
) -> GCPFunctionHandler:
    """
    Get or create GCP handler instance.

    Args:
        container: Optional DI container

    Returns:
        GCPFunctionHandler instance
    """
    global _gcp_handler_instance

    if _gcp_handler_instance is None:
        _gcp_handler_instance = GCPFunctionHandler(container)

    return _gcp_handler_instance


def gcp_http_handler(request):
    """
    Main GCP HTTP Cloud Function handler.

    This is the entry point for HTTP-triggered Cloud Functions.

    Args:
        request: Flask request object

    Returns:
        Response data for Cloud Function
    """
    handler = get_gcp_handler()
    return handler.gcp_handler(request)


def gcp_pubsub_handler(event, context):
    """
    Main GCP Pub/Sub Cloud Function handler.

    This is the entry point for Pub/Sub-triggered Cloud Functions.

    Args:
        event: Pub/Sub event data
        context: Cloud Function context

    Returns:
        None (Pub/Sub functions don't return responses)
    """
    handler = get_gcp_handler()
    result = handler.handle_request(event, context)

    # Log result for Pub/Sub (no HTTP response)
    print(f"Pub/Sub handler result: {result}")


def gcp_storage_handler(event, context):
    """
    Main GCP Cloud Storage Cloud Function handler.

    This is the entry point for Storage-triggered Cloud Functions.

    Args:
        event: Storage event data
        context: Cloud Function context

    Returns:
        None (Storage functions don't return responses)
    """
    handler = get_gcp_handler()
    result = handler.handle_request(event, context)

    # Log result for Storage trigger (no HTTP response)
    print(f"Storage handler result: {result}")


def gcp_handler_with_config(config_file: str):
    """
    Create GCP handlers with custom configuration.

    Args:
        config_file: Path to custom config file

    Returns:
        Tuple of handler functions (http, pubsub, storage)
    """
    from agentmap.di import initialize_di

    container = initialize_di(config_file)
    handler = GCPFunctionHandler(container)

    def configured_http_handler(request):
        return handler.gcp_handler(request)

    def configured_pubsub_handler(event, context):
        result = handler.handle_request(event, context)
        print(f"Configured Pub/Sub handler result: {result}")

    def configured_storage_handler(event, context):
        result = handler.handle_request(event, context)
        print(f"Configured Storage handler result: {result}")

    return (
        configured_http_handler,
        configured_pubsub_handler,
        configured_storage_handler,
    )


# Example usage patterns for different GCP configurations:


def run_graph_gcp_handler(request):
    """GCP HTTP handler specifically for graph execution."""
    handler = get_gcp_handler()

    # Ensure action is set to run
    event_data = handler._parse_event(request)
    if "action" not in event_data:
        event_data["action"] = "run"

    result = handler.handle_request(event_data)

    if "body" in result:
        return json.loads(result["body"])
    return result


def validate_graph_gcp_handler(request):
    """GCP HTTP handler specifically for graph validation."""
    handler = get_gcp_handler()

    # Ensure action is set to validate
    event_data = handler._parse_event(request)
    if "action" not in event_data:
        event_data["action"] = "validate"

    result = handler.handle_request(event_data)

    if "body" in result:
        return json.loads(result["body"])
    return result


def compile_graph_gcp_handler(request):
    """GCP HTTP handler specifically for graph compilation."""
    handler = get_gcp_handler()

    # Ensure action is set to compile
    event_data = handler._parse_event(request)
    if "action" not in event_data:
        event_data["action"] = "compile"

    result = handler.handle_request(event_data)

    if "body" in result:
        return json.loads(result["body"])
    return result
