"""
Azure Function handler using the runtime facade pattern.

This module provides Azure Function handlers that follow SPEC-DEP-001
by using only the runtime facade for consistent behavior across all deployment adapters.
"""

import json
import logging
from typing import Any, Dict, Optional

from agentmap.deployment.serverless.base_handler import BaseHandler


class AzureFunctionHandler(BaseHandler):
    """Azure Function handler using facade pattern through BaseHandler."""

    def azure_handler(self, req) -> Dict[str, Any]:
        """
        Azure Function entry point for HTTP triggers using facade pattern.

        Args:
            req: Azure Functions request object

        Returns:
            Dict containing response data
        """
        # Convert Azure request to our standard format
        event_data = self._convert_azure_request(req)

        # Use BaseHandler's facade-based request handling
        result = self.handle_request_sync(event_data)

        # Azure Functions expects different response format
        return self._convert_to_azure_response(result)

    def _convert_azure_request(self, req) -> Dict[str, Any]:
        """Convert Azure Functions request to standard event format."""
        try:
            if hasattr(req, "method") and req.method == "POST":
                # Parse JSON body
                try:
                    request_json = req.get_json()
                    if request_json:
                        return request_json
                except ValueError:
                    pass

                # Fallback to raw body
                try:
                    body = req.get_body().decode("utf-8")
                    if body:
                        return json.loads(body)
                except (json.JSONDecodeError, AttributeError):
                    pass

                return {}
            elif hasattr(req, "params"):
                # GET request - use query parameters
                return dict(req.params)
            else:
                # Direct call or other event type
                return req if isinstance(req, dict) else {}

        except Exception:
            # Fallback to empty dict if parsing fails
            return {}

    def _convert_to_azure_response(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Convert standard response to Azure Function format."""
        # Azure Functions can return the response directly
        if "body" in result:
            try:
                body_data = json.loads(result["body"])
                return {
                    "statusCode": result.get("statusCode", 200),
                    "headers": result.get("headers", {}),
                    "body": body_data,
                }
            except json.JSONDecodeError:
                return result

        return result


# Global handler instance for Azure Functions runtime
_azure_handler_instance: Optional[AzureFunctionHandler] = None


def get_azure_handler(config_file: Optional[str] = None) -> AzureFunctionHandler:
    """
    Get or create Azure handler instance using facade pattern.

    Args:
        config_file: Optional config file path

    Returns:
        AzureFunctionHandler instance
    """
    global _azure_handler_instance

    if _azure_handler_instance is None:
        _azure_handler_instance = AzureFunctionHandler(config_file=config_file)

    return _azure_handler_instance


def azure_http_handler(req):
    """
    Main Azure HTTP Function handler using facade pattern.

    This is the entry point for HTTP-triggered Azure Functions.

    Args:
        req: Azure Functions request object

    Returns:
        Response data for Azure Function
    """
    handler = get_azure_handler()
    return handler.azure_handler(req)


def azure_blob_handler(blob, context):
    """
    Main Azure Blob Storage Function handler using facade pattern.

    This is the entry point for Blob-triggered Azure Functions.

    Args:
        blob: Blob data
        context: Azure Function context

    Returns:
        None (Blob functions don't return HTTP responses)
    """
    handler = get_azure_handler()

    # Create event data for blob trigger
    event_data = {
        "Records": [
            {
                "s3": {  # Use S3-like format for compatibility with trigger strategies
                    "object": {"key": context.get("bindingData", {}).get("name", "")}
                }
            }
        ]
    }

    result = handler.handle_request_sync(event_data, context)

    # Log result for Blob trigger (no HTTP response)
    logging.info(f"Blob handler result: {result}")


def azure_queue_handler(queueItem, context):
    """
    Main Azure Queue Function handler using facade pattern.

    This is the entry point for Queue-triggered Azure Functions.

    Args:
        queueItem: Queue message data
        context: Azure Function context

    Returns:
        None (Queue functions don't return HTTP responses)
    """
    handler = get_azure_handler()

    # Create event data for queue trigger in AWS SQS-like format for compatibility
    event_data = {
        "Records": [
            {"body": queueItem if isinstance(queueItem, str) else json.dumps(queueItem)}
        ]
    }

    result = handler.handle_request_sync(event_data, context)

    # Log result for Queue trigger (no HTTP response)
    logging.info(f"Queue handler result: {result}")


def azure_event_grid_handler(eventGridEvent, context):
    """
    Main Azure Event Grid Function handler using facade pattern.

    This is the entry point for Event Grid-triggered Azure Functions.

    Args:
        eventGridEvent: Event Grid event data
        context: Azure Function context

    Returns:
        None (Event Grid functions don't return HTTP responses)
    """
    handler = get_azure_handler()

    # Extract graph information from Event Grid event
    event_data = {
        "graph": eventGridEvent.get("subject", "default"),
        "state": eventGridEvent.get("data", {}),
    }

    result = handler.handle_request_sync(event_data, context)

    # Log result for Event Grid trigger (no HTTP response)
    logging.info(f"Event Grid handler result: {result}")


def azure_handler_with_config(config_file: str):
    """
    Create Azure handlers with custom configuration using facade pattern.

    Args:
        config_file: Path to custom config file

    Returns:
        Tuple of handler functions (http, blob, queue, event_grid)
    """
    handler = AzureFunctionHandler(config_file=config_file)

    def configured_http_handler(req):
        return handler.azure_handler(req)

    def configured_blob_handler(blob, context):
        event_data = {
            "Records": [
                {
                    "s3": {
                        "object": {
                            "key": context.get("bindingData", {}).get("name", "")
                        }
                    }
                }
            ]
        }
        result = handler.handle_request_sync(event_data, context)
        logging.info(f"Configured Blob handler result: {result}")

    def configured_queue_handler(queueItem, context):
        event_data = {
            "Records": [
                {
                    "body": (
                        queueItem
                        if isinstance(queueItem, str)
                        else json.dumps(queueItem)
                    )
                }
            ]
        }
        result = handler.handle_request_sync(event_data, context)
        logging.info(f"Configured Queue handler result: {result}")

    def configured_event_grid_handler(eventGridEvent, context):
        event_data = {
            "graph": eventGridEvent.get("subject", "default"),
            "state": eventGridEvent.get("data", {}),
        }
        result = handler.handle_request_sync(event_data, context)
        logging.info(f"Configured Event Grid handler result: {result}")

    return (
        configured_http_handler,
        configured_blob_handler,
        configured_queue_handler,
        configured_event_grid_handler,
    )


# Example usage patterns for different Azure configurations:


def run_graph_azure_handler(req):
    """Azure HTTP handler specifically for graph execution."""
    handler = get_azure_handler()

    # Parse request and ensure graph is specified
    event_data = handler._convert_azure_request(req)
    if "graph" not in event_data:
        event_data["graph"] = "default"

    result = handler.handle_request_sync(event_data)
    return handler._convert_to_azure_response(result)
