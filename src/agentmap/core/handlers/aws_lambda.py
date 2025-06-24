"""
AWS Lambda handler using the new service architecture.

This module provides AWS Lambda function handlers that maintain
compatibility with existing interfaces while using GraphRunnerService.
"""

from typing import Any, Dict, Optional

from agentmap.core.handlers.base_handler import BaseHandler, RequestParser
from agentmap.di import ApplicationContainer


class AWSLambdaHandler(BaseHandler):
    """AWS Lambda handler for AgentMap graph execution."""

    def _parse_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse AWS Lambda event format.

        Args:
            event: AWS Lambda event object

        Returns:
            Dict containing parsed request data
        """
        # Handle different Lambda trigger types
        if "httpMethod" in event:
            # API Gateway trigger
            return self._parse_api_gateway_event(event)
        elif "Records" in event:
            # S3, SQS, SNS, etc. trigger
            return self._parse_records_event(event)
        else:
            # Direct invocation
            return self._parse_direct_invocation(event)

    def _parse_api_gateway_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Parse API Gateway event."""
        method = RequestParser.get_http_method(event)

        if method == "POST":
            # Parse body for POST requests
            body = event.get("body", "{}")
            request_data = RequestParser.parse_json_body(body)
        else:
            # Use query parameters for GET requests
            request_data = RequestParser.extract_query_params(event)

        # Add path parameters
        path_params = RequestParser.extract_path_params(event)
        request_data.update(path_params)

        return request_data

    def _parse_records_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Parse event with Records (S3, SQS, etc.)."""
        # For records events, extract the first record and parse its content
        records = event.get("Records", [])
        if not records:
            return {}

        first_record = records[0]

        # Handle different record types
        if "s3" in first_record:
            # S3 event - could trigger graph execution based on file upload
            s3_info = first_record["s3"]
            return {
                "action": "run",
                "csv": s3_info.get("object", {}).get("key"),
                "trigger": "s3_upload",
            }
        elif "body" in first_record:
            # SQS message
            return RequestParser.parse_json_body(first_record["body"])
        else:
            # Other record types
            return first_record

    def _parse_direct_invocation(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Parse direct Lambda invocation."""
        # For direct invocation, the event is the request data
        return event

    def lambda_handler(self, event: Dict[str, Any], context: Any) -> Dict[str, Any]:
        """
        AWS Lambda entry point.

        Args:
            event: AWS Lambda event object
            context: AWS Lambda context object

        Returns:
            Dict containing response for AWS Lambda
        """
        return self.handle_request(event, context)


# Global handler instance for Lambda runtime
_lambda_handler_instance: Optional[AWSLambdaHandler] = None


def get_lambda_handler(
    container: Optional[ApplicationContainer] = None,
) -> AWSLambdaHandler:
    """
    Get or create Lambda handler instance.

    Args:
        container: Optional DI container

    Returns:
        AWSLambdaHandler instance
    """
    global _lambda_handler_instance

    if _lambda_handler_instance is None:
        _lambda_handler_instance = AWSLambdaHandler(container)

    return _lambda_handler_instance


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler function.

    This is the entry point that AWS Lambda will call.

    Args:
        event: AWS Lambda event object
        context: AWS Lambda context object

    Returns:
        Dict containing response for AWS Lambda
    """
    handler = get_lambda_handler()
    return handler.lambda_handler(event, context)


def lambda_handler_with_config(config_file: str):
    """
    Create a Lambda handler with custom configuration.

    Args:
        config_file: Path to custom config file

    Returns:
        Lambda handler function
    """
    from agentmap.di import initialize_di

    container = initialize_di(config_file)
    handler = AWSLambdaHandler(container)

    def configured_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
        return handler.lambda_handler(event, context)

    return configured_handler


# Example usage patterns for different Lambda configurations:


def run_graph_lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda handler specifically for graph execution."""
    # Add default action for this specific handler
    if "action" not in event:
        event["action"] = "run"

    return lambda_handler(event, context)


def validate_graph_lambda_handler(
    event: Dict[str, Any], context: Any
) -> Dict[str, Any]:
    """Lambda handler specifically for graph validation."""
    # Add default action for this specific handler
    if "action" not in event:
        event["action"] = "validate"

    return lambda_handler(event, context)


def compile_graph_lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda handler specifically for graph compilation."""
    # Add default action for this specific handler
    if "action" not in event:
        event["action"] = "compile"

    return lambda_handler(event, context)
