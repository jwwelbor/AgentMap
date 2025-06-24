"""
Azure Function handler using the new service architecture.

This module provides Azure Function handlers that maintain
compatibility with existing interfaces while using GraphRunnerService.
"""

import json
import logging
from typing import Any, Dict, Optional

from agentmap.core.handlers.base_handler import BaseHandler, RequestParser
from agentmap.di import ApplicationContainer


class AzureFunctionHandler(BaseHandler):
    """Azure Function handler for AgentMap graph execution."""

    def _parse_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse Azure Function request format.

        Args:
            event: Azure Function request data

        Returns:
            Dict containing parsed request data
        """
        # Handle different Azure trigger types
        if hasattr(event, "method"):
            # HTTP trigger (Azure Functions request object)
            return self._parse_http_request(event)
        elif isinstance(event, dict) and "blob" in event:
            # Blob storage trigger
            return self._parse_blob_event(event)
        elif isinstance(event, dict) and "queueItem" in event:
            # Queue trigger
            return self._parse_queue_event(event)
        elif isinstance(event, dict) and "eventGridEvent" in event:
            # Event Grid trigger
            return self._parse_event_grid_event(event)
        else:
            # Direct call or other event type
            return event if isinstance(event, dict) else {}

    def _parse_http_request(self, req) -> Dict[str, Any]:
        """Parse HTTP request from Azure Functions."""
        try:
            if req.method == "POST":
                # Parse JSON body
                try:
                    request_json = req.get_json()
                    if request_json:
                        return request_json
                except ValueError:
                    pass

                # Fallback to raw body
                body = req.get_body().decode("utf-8")
                if body:
                    return RequestParser.parse_json_body(body)

                return {}
            else:
                # GET request - use query parameters
                return dict(req.params)

        except Exception:
            # Fallback to empty dict if parsing fails
            return {}

    def _parse_blob_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Azure Blob Storage event."""
        blob_info = event.get("blob", {})
        return {
            "action": "run",
            "csv": blob_info.get("name"),  # Blob name
            "container": blob_info.get("container"),
            "trigger": "blob_upload",
        }

    def _parse_queue_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Azure Queue event."""
        try:
            queue_item = event.get("queueItem", "")
            if isinstance(queue_item, str):
                return json.loads(queue_item)
            return queue_item
        except Exception:
            return {"action": "run", "trigger": "queue"}

    def _parse_event_grid_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Azure Event Grid event."""
        event_data = event.get("eventGridEvent", {})
        return {
            "action": "run",
            "data": event_data.get("data", {}),
            "subject": event_data.get("subject"),
            "trigger": "event_grid",
        }

    def azure_handler(self, req) -> Dict[str, Any]:
        """
        Azure Function entry point for HTTP triggers.

        Args:
            req: Azure Functions request object

        Returns:
        Dict containing response data
        """
        # Convert Azure request to our standard format
        event_data = self._parse_event(req)
        result = self.handle_request(event_data)

        # Azure Functions expects different response format
        return self._convert_to_azure_response(result)

    def _convert_to_azure_response(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Convert standard response to Azure Function format."""
        # Azure Functions can return the response directly
        if "body" in result:
            body_data = json.loads(result["body"])
            return {
                "statusCode": result.get("statusCode", 200),
                "headers": result.get("headers", {}),
                "body": body_data,
            }

        return result


# Global handler instance for Azure Functions runtime
_azure_handler_instance: Optional[AzureFunctionHandler] = None


def get_azure_handler(
    container: Optional[ApplicationContainer] = None,
) -> AzureFunctionHandler:
    """
    Get or create Azure handler instance.

    Args:
        container: Optional DI container

    Returns:
        AzureFunctionHandler instance
    """
    global _azure_handler_instance

    if _azure_handler_instance is None:
        _azure_handler_instance = AzureFunctionHandler(container)

    return _azure_handler_instance


def azure_http_handler(req):
    """
    Main Azure HTTP Function handler.

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
    Main Azure Blob Storage Function handler.

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
        "blob": {
            "name": context.get("bindingData", {}).get("name", ""),
            "container": context.get("bindingData", {}).get("containerName", ""),
        }
    }

    result = handler.handle_request(event_data, context)

    # Log result for Blob trigger (no HTTP response)
    logging.info(f"Blob handler result: {result}")


def azure_queue_handler(queueItem, context):
    """
    Main Azure Queue Function handler.

    This is the entry point for Queue-triggered Azure Functions.

    Args:
        queueItem: Queue message data
        context: Azure Function context

    Returns:
        None (Queue functions don't return HTTP responses)
    """
    handler = get_azure_handler()

    # Create event data for queue trigger
    event_data = {"queueItem": queueItem}

    result = handler.handle_request(event_data, context)

    # Log result for Queue trigger (no HTTP response)
    logging.info(f"Queue handler result: {result}")


def azure_event_grid_handler(eventGridEvent, context):
    """
    Main Azure Event Grid Function handler.

    This is the entry point for Event Grid-triggered Azure Functions.

    Args:
        eventGridEvent: Event Grid event data
        context: Azure Function context

    Returns:
        None (Event Grid functions don't return HTTP responses)
    """
    handler = get_azure_handler()

    # Create event data for Event Grid trigger
    event_data = {"eventGridEvent": eventGridEvent}

    result = handler.handle_request(event_data, context)

    # Log result for Event Grid trigger (no HTTP response)
    logging.info(f"Event Grid handler result: {result}")


def azure_handler_with_config(config_file: str):
    """
    Create Azure handlers with custom configuration.

    Args:
        config_file: Path to custom config file

    Returns:
        Tuple of handler functions (http, blob, queue, event_grid)
    """
    from agentmap.di import initialize_di

    container = initialize_di(config_file)
    handler = AzureFunctionHandler(container)

    def configured_http_handler(req):
        return handler.azure_handler(req)

    def configured_blob_handler(blob, context):
        event_data = {
            "blob": {
                "name": context.get("bindingData", {}).get("name", ""),
                "container": context.get("bindingData", {}).get("containerName", ""),
            }
        }
        result = handler.handle_request(event_data, context)
        logging.info(f"Configured Blob handler result: {result}")

    def configured_queue_handler(queueItem, context):
        event_data = {"queueItem": queueItem}
        result = handler.handle_request(event_data, context)
        logging.info(f"Configured Queue handler result: {result}")

    def configured_event_grid_handler(eventGridEvent, context):
        event_data = {"eventGridEvent": eventGridEvent}
        result = handler.handle_request(event_data, context)
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

    # Ensure action is set to run
    event_data = handler._parse_event(req)
    if "action" not in event_data:
        event_data["action"] = "run"

    result = handler.handle_request(event_data)
    return handler._convert_to_azure_response(result)


def validate_graph_azure_handler(req):
    """Azure HTTP handler specifically for graph validation."""
    handler = get_azure_handler()

    # Ensure action is set to validate
    event_data = handler._parse_event(req)
    if "action" not in event_data:
        event_data["action"] = "validate"

    result = handler.handle_request(event_data)
    return handler._convert_to_azure_response(result)


def compile_graph_azure_handler(req):
    """Azure HTTP handler specifically for graph compilation."""
    handler = get_azure_handler()

    # Ensure action is set to compile
    event_data = handler._parse_event(req)
    if "action" not in event_data:
        event_data["action"] = "compile"

    result = handler.handle_request(event_data)
    return handler._convert_to_azure_response(result)
