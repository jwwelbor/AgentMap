"""
AWS Lambda handler using the runtime facade pattern.

This module provides AWS Lambda function handlers that follow SPEC-DEP-001
by using only the runtime facade for consistent behavior across all deployment adapters.
"""

from typing import Any, Dict, Optional

from agentmap.deployment.serverless.base_handler import BaseHandler


class AWSLambdaHandler(BaseHandler):
    """AWS Lambda handler using facade pattern through BaseHandler."""

    def lambda_handler(self, event: Dict[str, Any], context: Any) -> Dict[str, Any]:
        """
        AWS Lambda entry point using facade pattern.

        Args:
            event: AWS Lambda event object
            context: AWS Lambda context object

        Returns:
            Dict containing response for AWS Lambda
        """
        # Use BaseHandler's facade-based request handling
        # BaseHandler will parse the event using trigger strategies
        return self.handle_request_sync(event, context)


# Global handler instance for Lambda runtime
_lambda_handler_instance: Optional[AWSLambdaHandler] = None


def get_lambda_handler(config_file: Optional[str] = None) -> AWSLambdaHandler:
    """
    Get or create Lambda handler instance using facade pattern.

    Args:
        config_file: Optional config file path

    Returns:
        AWSLambdaHandler instance
    """
    global _lambda_handler_instance

    if _lambda_handler_instance is None:
        _lambda_handler_instance = AWSLambdaHandler(config_file=config_file)

    return _lambda_handler_instance


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler function using facade pattern.

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
    Create a Lambda handler with custom configuration using facade pattern.

    Args:
        config_file: Path to custom config file

    Returns:
        Lambda handler function
    """
    handler = AWSLambdaHandler(config_file=config_file)

    def configured_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
        return handler.lambda_handler(event, context)

    return configured_handler


# Example usage patterns for different Lambda configurations:


def run_graph_lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda handler specifically for graph execution."""
    # Add default graph parameter if not present
    if "graph" not in event and "csv" not in event:
        # Set a default graph name for run-only handlers
        event["graph"] = "default"

    return lambda_handler(event, context)


def workflow_lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda handler for workflow execution with graph name validation."""
    # Ensure graph name is specified
    if "graph" not in event:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": '{"success": false, "error": "Graph name is required"}',
        }

    return lambda_handler(event, context)
