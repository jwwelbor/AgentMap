"""
Google Cloud Function handler using the runtime facade pattern.

This module provides Google Cloud Function handlers that follow SPEC-DEP-001
by using only the runtime facade for consistent behavior across all deployment adapters.
"""

import json
from typing import Any, Callable, Dict, Optional, Tuple

from agentmap.deployment.serverless.base_handler import BaseHandler


class GCPFunctionHandler(BaseHandler):
    """Google Cloud Function handler using facade pattern through BaseHandler."""

    def gcp_handler(self, request: Any) -> Dict[str, Any]:
        """
        Google Cloud Function entry point for HTTP triggers using facade pattern.

        Args:
            request: Flask request object

        Returns:
            Dict containing response data
        """
        # Convert Flask request to our standard format
        event_data = self._convert_gcp_request(request)

        # Use BaseHandler's facade-based request handling
        result = self.handle_request_sync(event_data)

        # Return the body content for HTTP response
        if "body" in result:
            try:
                response_data = json.loads(result["body"])
                return response_data if isinstance(response_data, dict) else result
            except json.JSONDecodeError:
                return result

        return result

    def _convert_gcp_request(self, request: Any) -> Dict[str, Any]:
        """Convert GCP Cloud Functions request to standard event format."""
        try:
            if hasattr(request, "method") and request.method == "POST":
                # Parse JSON body
                request_json = request.get_json(silent=True)
                if isinstance(request_json, dict) and request_json:
                    return request_json

                # Fallback to form data
                if hasattr(request, "form"):
                    return dict(request.form)

                return {}
            elif hasattr(request, "args"):
                # GET request - use query parameters
                return dict(request.args)
            else:
                # Direct call or other event type
                return request if isinstance(request, dict) else {}

        except Exception:
            # Fallback to empty dict if parsing fails
            return {}


# Global handler instance for Cloud Functions runtime
_gcp_handler_instance: Optional[GCPFunctionHandler] = None


def get_gcp_handler(config_file: Optional[str] = None) -> GCPFunctionHandler:
    """
    Get or create GCP handler instance using facade pattern.

    Args:
        config_file: Optional config file path

    Returns:
        GCPFunctionHandler instance
    """
    global _gcp_handler_instance

    if _gcp_handler_instance is None:
        _gcp_handler_instance = GCPFunctionHandler(config_file=config_file)

    return _gcp_handler_instance


def gcp_http_handler(request: Any) -> Dict[str, Any]:
    """
    Main GCP HTTP Cloud Function handler using facade pattern.

    This is the entry point for HTTP-triggered Cloud Functions.

    Args:
        request: Flask request object

    Returns:
        Response data for Cloud Function
    """
    handler = get_gcp_handler()
    return handler.gcp_handler(request)


def gcp_pubsub_handler(event: Any, context: Any) -> None:
    """
    Main GCP Pub/Sub Cloud Function handler using facade pattern.

    This is the entry point for Pub/Sub-triggered Cloud Functions.

    Args:
        event: Pub/Sub event data
        context: Cloud Function context

    Returns:
        None (Pub/Sub functions don't return responses)
    """
    handler = get_gcp_handler()

    # Convert Pub/Sub event to standard format
    try:
        # Decode Pub/Sub message
        import base64

        event_data: Dict[str, Any] = {}
        if "data" in event:
            decoded_data = base64.b64decode(event["data"]).decode("utf-8")
            parsed_data = json.loads(decoded_data)
            event_data = parsed_data if isinstance(parsed_data, dict) else {}
        else:
            # Fallback to attributes
            attributes = event.get("attributes", {})
            event_data = attributes if isinstance(attributes, dict) else {}

    except Exception:
        event_data = {"graph": "default", "state": {}}

    result = handler.handle_request_sync(event_data, context)

    # Log result for Pub/Sub (no HTTP response)
    print(f"Pub/Sub handler result: {result}")


def gcp_storage_handler(event: Any, context: Any) -> None:
    """
    Main GCP Cloud Storage Cloud Function handler using facade pattern.

    This is the entry point for Storage-triggered Cloud Functions.

    Args:
        event: Storage event data
        context: Cloud Function context

    Returns:
        None (Storage functions don't return responses)
    """
    handler = get_gcp_handler()

    # Convert Storage event to standard format compatible with trigger strategies
    event_data = {
        "Records": [
            {
                "s3": {  # Use S3-like format for compatibility
                    "object": {"key": event.get("name", "")}
                }
            }
        ]
    }

    result = handler.handle_request_sync(event_data, context)

    # Log result for Storage trigger (no HTTP response)
    print(f"Storage handler result: {result}")


def gcp_handler_with_config(
    config_file: str,
) -> Tuple[
    Callable[[Any], Dict[str, Any]],
    Callable[[Any, Any], None],
    Callable[[Any, Any], None],
]:
    """
    Create GCP handlers with custom configuration using facade pattern.

    Args:
        config_file: Path to custom config file

    Returns:
        Tuple of handler functions (http, pubsub, storage)
    """
    handler = GCPFunctionHandler(config_file=config_file)

    def configured_http_handler(request: Any) -> Dict[str, Any]:
        return handler.gcp_handler(request)

    def configured_pubsub_handler(event: Any, context: Any) -> None:
        try:
            import base64

            event_data: Dict[str, Any] = {}
            if "data" in event:
                decoded_data = base64.b64decode(event["data"]).decode("utf-8")
                parsed_data = json.loads(decoded_data)
                event_data = parsed_data if isinstance(parsed_data, dict) else {}
            else:
                attributes = event.get("attributes", {})
                event_data = attributes if isinstance(attributes, dict) else {}

        except Exception:
            event_data = {"graph": "default", "state": {}}

        result = handler.handle_request_sync(event_data, context)
        print(f"Configured Pub/Sub handler result: {result}")

    def configured_storage_handler(event: Any, context: Any) -> None:
        event_data = {"Records": [{"s3": {"object": {"key": event.get("name", "")}}}]}
        result = handler.handle_request_sync(event_data, context)
        print(f"Configured Storage handler result: {result}")

    return (
        configured_http_handler,
        configured_pubsub_handler,
        configured_storage_handler,
    )


# Example usage patterns for different GCP configurations:


def run_graph_gcp_handler(request: Any) -> Dict[str, Any]:
    """GCP HTTP handler specifically for graph execution."""
    handler = get_gcp_handler()

    # Parse request and ensure graph is specified
    event_data = handler._convert_gcp_request(request)
    if "graph" not in event_data:
        event_data["graph"] = "default"

    result = handler.handle_request_sync(event_data)

    if "body" in result:
        try:
            response_data = json.loads(result["body"])
            return response_data if isinstance(response_data, dict) else result
        except json.JSONDecodeError:
            return result
    return result
