# Fixed AWS Lambda adapter for AgentMap
# Supports SNS/SQS event triggers and API Gateway HTTP (optional).

import json
import logging

# Configure logging for CloudWatch
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    """AWS Lambda entrypoint.

    Automatically routes based on event shape:
    - API Gateway HTTP -> agentmap AWS HTTP handler
    - SNS/SQS/EventBridge -> agentmap AWS event handler

    Expects the message payload (for SNS/SQS) to be JSON with:
      {"graph":"MyGraph","state":{...},"action":"run"}
    """
    logger.info(f"Received event: {json.dumps(event, default=str)}")
    
    try:
        # Try to import AgentMap's AWS handlers
        from agentmap.deployment.serverless.aws_lambda import (
            aws_event_handler,
            aws_http_handler,
        )
    except ImportError as e:
        logger.error(f"Failed to import AgentMap AWS handlers: {e}")
        # Fallback - try alternative import paths
        try:
            from agentmap.handlers.aws_lambda import (
                aws_event_handler,
                aws_http_handler,
            )
        except ImportError:
            try:
                from agentmap.aws import (
                    aws_event_handler,
                    aws_http_handler,
                )
            except ImportError:
                logger.error("Could not find AgentMap AWS handlers in any expected location")
                return {
                    "statusCode": 500,
                    "body": json.dumps({"error": "AgentMap AWS handlers not found"})
                }

    try:
        # Detect event type and route accordingly
        if _is_http_event(event):
            logger.info("Routing to HTTP handler")
            return aws_http_handler(event, context)
        else:
            logger.info("Routing to event handler")
            return aws_event_handler(event, context)
            
    except Exception as e:
        logger.error(f"Error processing event: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }

def _is_http_event(event):
    """Detect if this is an HTTP event from API Gateway or ALB."""
    if not isinstance(event, dict):
        return False
        
    # API Gateway v2
    if "requestContext" in event and "http" in event.get("requestContext", {}):
        return True
        
    # API Gateway v1
    if "httpMethod" in event and "path" in event:
        return True
        
    # ALB
    if "requestContext" in event and "elb" in event.get("requestContext", {}):
        return True
        
    # Lambda Function URLs
    if "rawPath" in event and "requestContext" in event:
        return True
        
    return False
