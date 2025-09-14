"""
Enhanced base serverless handler supporting multiple trigger types (run and resume only).

This module provides the base class for serverless function handlers
that support HTTP, message queue, and database triggers using the
workflow orchestration service for execution coordination.
"""

import asyncio
import json
import traceback
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from agentmap.deployment.service_adapter import create_service_adapter
from agentmap.di import ApplicationContainer, initialize_di
from agentmap.services.workflow_orchestration_service import (
    execute_workflow,
    resume_workflow,
)


class TriggerType(Enum):
    """Supported trigger types for serverless functions."""

    HTTP = "http"
    MESSAGE_QUEUE = "queue"
    DATABASE = "database"
    TIMER = "timer"
    STORAGE = "storage"


class BaseHandler:
    """Enhanced base serverless handler supporting multiple trigger types (run and resume only)."""

    def __init__(self, container: Optional[ApplicationContainer] = None):
        """Initialize enhanced base handler for run and resume operations."""
        self.container = container or initialize_di()
        self.adapter = create_service_adapter(self.container)

    async def handle_request(
        self, event: Dict[str, Any], context: Any = None
    ) -> Dict[str, Any]:
        """
        Enhanced async request handling logic for all trigger types (run and resume only).

        Args:
            event: Event data from serverless platform
            context: Context object from serverless platform

        Returns:
            Dict containing response data
        """
        correlation_id = str(uuid.uuid4())

        try:
            # Detect trigger type and parse event
            trigger_type = self._detect_trigger_type(event)
            request_data = self._parse_event_by_trigger_type(event, trigger_type)

            # Add correlation tracking
            request_data["correlation_id"] = correlation_id
            request_data["trigger_type"] = trigger_type.value
            request_data["timestamp"] = datetime.utcnow().isoformat()

            # Log trigger information
            self._log_trigger_info(trigger_type, request_data, correlation_id)

            # Basic request validation
            self._basic_request_validation(request_data, trigger_type)

            # Route to appropriate handler based on action (run and resume only)
            action = request_data.get("action", "run")

            if action == "run":
                result = await self._handle_run_request(request_data, context)
            elif action == "resume":
                result = await self._handle_resume_request(request_data, context)
            else:
                result = self._create_error_response(
                    f"Unsupported action: {action}. Only 'run' and 'resume' are supported.",
                    400,
                )

            # Add correlation ID to response
            if isinstance(result.get("body"), str):
                body_data = json.loads(result["body"])
                body_data["correlation_id"] = correlation_id
                result["body"] = json.dumps(body_data)

            # Handle result publishing for async triggers
            if trigger_type in [TriggerType.MESSAGE_QUEUE, TriggerType.DATABASE]:
                await self._publish_result_if_needed(request_data, result)

            return result

        except Exception as e:
            return self._handle_error(e, correlation_id)

    def handle_request_sync(
        self, event: Dict[str, Any], context: Any = None
    ) -> Dict[str, Any]:
        """
        Synchronous wrapper for platforms that require sync entrypoint.

        Args:
            event: Event data from serverless platform
            context: Context object from serverless platform

        Returns:
            Dict containing response data
        """
        return asyncio.run(self.handle_request(event, context))

    def _detect_trigger_type(self, event: Dict[str, Any]) -> TriggerType:
        """
        Detect the trigger type from the event structure.

        Args:
            event: Raw event from cloud platform

        Returns:
            TriggerType enum value
        """
        # Check for HTTP triggers (API Gateway, HTTP functions)
        if any(key in event for key in ["httpMethod", "requestContext", "headers"]):
            return TriggerType.HTTP

        # Check for message queue triggers
        if "Records" in event:
            records = event["Records"]
            if any(
                "eventSource" in record and "sqs" in record.get("eventSource", "")
                for record in records
            ):
                return TriggerType.MESSAGE_QUEUE
            if any(
                "eventSource" in record and "aws:s3" in record.get("eventSource", "")
                for record in records
            ):
                return TriggerType.STORAGE

        # Check for database triggers
        if any(key in event for key in ["eventName", "dynamodb", "cosmosdb"]):
            return TriggerType.DATABASE

        # Check for timer triggers
        if any(key in event for key in ["source"]) and "aws.events" in event.get(
            "source", ""
        ):
            return TriggerType.TIMER

        # Check for Azure Service Bus
        if "data" in event and "subject" in event and "eventType" in event:
            return TriggerType.MESSAGE_QUEUE

        # Check for GCP Pub/Sub
        if "data" in event and "@type" in event:
            return TriggerType.MESSAGE_QUEUE

        # Default to HTTP for unknown patterns
        return TriggerType.HTTP

    def _parse_event_by_trigger_type(
        self, event: Dict[str, Any], trigger_type: TriggerType
    ) -> Dict[str, Any]:
        """
        Parse event based on detected trigger type.

        Args:
            event: Raw event from cloud platform
            trigger_type: Detected trigger type

        Returns:
            Standardized request data
        """
        if trigger_type == TriggerType.HTTP:
            return self._parse_http_event(event)
        elif trigger_type == TriggerType.MESSAGE_QUEUE:
            return self._parse_message_queue_event(event)
        elif trigger_type == TriggerType.DATABASE:
            return self._parse_database_event(event)
        elif trigger_type == TriggerType.TIMER:
            return self._parse_timer_event(event)
        elif trigger_type == TriggerType.STORAGE:
            return self._parse_storage_event(event)
        else:
            return self._parse_direct_invocation(event)

    def _parse_http_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Parse HTTP trigger event (API Gateway, etc.)."""
        method = event.get("httpMethod", event.get("method", "POST")).upper()

        if method == "POST":
            body = event.get("body", "{}")
            if isinstance(body, str):
                try:
                    request_data = json.loads(body)
                except json.JSONDecodeError:
                    request_data = {"raw_body": body}
            else:
                request_data = body or {}
        else:
            request_data = event.get("queryStringParameters") or {}

        # Add path parameters
        path_params = event.get("pathParameters") or {}
        request_data.update(path_params)

        return request_data

    def _parse_message_queue_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Parse message queue trigger event (SQS, Service Bus, Pub/Sub)."""
        if "Records" in event:
            # AWS SQS format
            record = event["Records"][0]  # Process first message
            body = record.get("body", "{}")
            if isinstance(body, str):
                try:
                    message_data = json.loads(body)
                except json.JSONDecodeError:
                    message_data = {"raw_message": body}
            else:
                message_data = body
        elif "data" in event:
            # GCP Pub/Sub or Azure Event Grid format
            if isinstance(event["data"], str):
                import base64

                try:
                    decoded_data = base64.b64decode(event["data"]).decode("utf-8")
                    message_data = json.loads(decoded_data)
                except:
                    message_data = {"raw_data": event["data"]}
            else:
                message_data = event["data"]
        else:
            # Direct message format
            message_data = event

        # Ensure we have execution parameters
        if "execution_params" in message_data:
            return message_data["execution_params"]
        else:
            return message_data

    def _parse_database_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Parse database trigger event (DynamoDB Streams, etc.)."""
        if "Records" in event:
            # DynamoDB Streams format
            record = event["Records"][0]
            event_name = record.get("eventName", "")

            # Extract relevant data based on operation
            if "dynamodb" in record:
                dynamo_data = record["dynamodb"]

                # Get the data based on operation type
                if event_name in ["INSERT", "MODIFY"]:
                    new_image = dynamo_data.get("NewImage", {})
                    # Convert DynamoDB format to regular dict
                    extracted_data = self._convert_dynamodb_to_dict(new_image)
                else:
                    old_image = dynamo_data.get("OldImage", {})
                    extracted_data = self._convert_dynamodb_to_dict(old_image)

                return {
                    "action": "run",
                    "database_event": {
                        "operation": event_name,
                        "data": extracted_data,
                        "table": record.get("eventSourceARN", "").split("/")[-1],
                    },
                }

        # Generic database event format
        return {"action": "run", "database_event": event}

    def _parse_timer_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Parse timer/scheduled trigger event."""
        return {
            "action": "run",
            "scheduled_event": {
                "source": event.get("source", ""),
                "detail_type": event.get("detail-type", ""),
                "time": event.get("time", ""),
                "detail": event.get("detail", {}),
            },
        }

    def _parse_storage_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Parse storage trigger event (S3, Blob Storage)."""
        if "Records" in event:
            record = event["Records"][0]
            if "s3" in record:
                s3_data = record["s3"]
                return {
                    "action": "run",
                    "csv": s3_data["object"]["key"],
                    "storage_event": {
                        "bucket": s3_data["bucket"]["name"],
                        "key": s3_data["object"]["key"],
                        "event_name": record.get("eventName", ""),
                    },
                }

        return {"action": "run", "storage_event": event}

    def _parse_direct_invocation(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Parse direct function invocation."""
        return event

    def _convert_dynamodb_to_dict(
        self, dynamodb_item: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Convert DynamoDB attribute format to regular dictionary."""
        result = {}
        for key, value in dynamodb_item.items():
            if isinstance(value, dict) and len(value) == 1:
                type_key, type_value = next(iter(value.items()))
                if type_key == "S":  # String
                    result[key] = type_value
                elif type_key == "N":  # Number
                    result[key] = (
                        float(type_value) if "." in type_value else int(type_value)
                    )
                elif type_key == "BOOL":  # Boolean
                    result[key] = type_value
                elif type_key == "M":  # Map
                    result[key] = self._convert_dynamodb_to_dict(type_value)
                elif type_key == "L":  # List
                    result[key] = [
                        self._convert_dynamodb_to_dict({"item": item})["item"]
                        for item in type_value
                    ]
                else:
                    result[key] = type_value
            else:
                result[key] = value
        return result

    def _basic_request_validation(
        self, request_data: Dict[str, Any], trigger_type: TriggerType
    ) -> None:
        """Basic request validation for run and resume actions."""
        # Set default action if not specified
        if "action" not in request_data:
            request_data["action"] = "run"

        # Database trigger validation
        if (
            trigger_type == TriggerType.DATABASE
            and "database_event" not in request_data
        ):
            raise ValueError("Database event data missing from trigger")

        # Resume action validation
        if request_data.get("action") == "resume":
            if "thread_id" not in request_data:
                raise ValueError("thread_id required for resume action")
            if "response_action" not in request_data:
                raise ValueError("response_action required for resume action")

    def _log_trigger_info(
        self,
        trigger_type: TriggerType,
        request_data: Dict[str, Any],
        correlation_id: str,
    ) -> None:
        """Log trigger information for debugging."""
        try:
            _, _, logging_service = self.adapter.initialize_services()
            logger = logging_service.get_logger("agentmap.serverless.trigger")

            logger.info(
                f"Processing {trigger_type.value} trigger",
                extra={
                    "correlation_id": correlation_id,
                    "trigger_type": trigger_type.value,
                    "action": request_data.get("action", "unknown"),
                    "has_csv": "csv" in request_data,
                    "has_state": "state" in request_data,
                },
            )
        except:
            # Fallback logging
            print(f"Trigger: {trigger_type.value}, Correlation: {correlation_id}")

    async def _publish_result_if_needed(
        self, request_data: Dict[str, Any], result: Dict[str, Any]
    ) -> None:
        """Publish execution results back to message queues if configured."""
        try:
            # Check if result publishing is requested
            publish_config = request_data.get("publish_result")
            if not publish_config:
                return

            # Get messaging service
            messaging_service = self.container.messaging_service()

            # Extract result data
            result_body = json.loads(result.get("body", "{}"))

            # Publish result - handle both sync and async messaging services
            publish_method = messaging_service.publish_message
            if asyncio.iscoroutinefunction(publish_method):
                await publish_method(
                    topic=publish_config.get("topic", "agentmap-results"),
                    message_type="execution_result",
                    payload=result_body,
                    metadata={
                        "correlation_id": request_data.get("correlation_id"),
                        "original_action": request_data.get("action"),
                        "trigger_type": request_data.get("trigger_type"),
                    },
                )
            else:
                publish_method(
                    topic=publish_config.get("topic", "agentmap-results"),
                    message_type="execution_result",
                    payload=result_body,
                    metadata={
                        "correlation_id": request_data.get("correlation_id"),
                        "original_action": request_data.get("action"),
                        "trigger_type": request_data.get("trigger_type"),
                    },
                )

        except Exception as e:
            # Don't fail the main execution if result publishing fails
            print(f"Failed to publish result: {e}")

    async def _handle_run_request(
        self, request_data: Dict[str, Any], context: Any = None
    ) -> Dict[str, Any]:
        """Handle graph execution request using workflow orchestration service."""
        try:
            # Get logging service for logging
            _, _, logging_service = self.adapter.initialize_services()
            logger = logging_service.get_logger("agentmap.serverless.run")

            # Handle different trigger types
            trigger_type = request_data.get("trigger_type")

            if trigger_type == "database":
                # For database triggers, extract execution params from the event
                db_event = request_data.get("database_event", {})
                initial_state = db_event.get("data", {})
                graph_name = request_data.get("graph")
                csv_or_workflow = None  # Database triggers typically don't use CSV
            else:
                # Standard execution parameters
                graph_name = request_data.get("graph")
                csv_or_workflow = request_data.get("csv")
                initial_state = request_data.get("state", {})

            logger.info(
                f"Serverless executing graph via {trigger_type} trigger",
                extra={"correlation_id": request_data.get("correlation_id")},
            )

            # Execute using workflow orchestration service
            result = execute_workflow(
                csv_or_workflow=csv_or_workflow,
                graph_name=graph_name,
                initial_state=initial_state,
                validate_csv=False,  # Skip validation in serverless context
            )

            if result.success:
                return self._create_success_response(result.final_state)
            else:
                return self._create_error_response(result.error, 500)

        except Exception as e:
            return self._handle_error(e, request_data.get("correlation_id"))

    async def _handle_resume_request(
        self, request_data: Dict[str, Any], context: Any = None
    ) -> Dict[str, Any]:
        """Handle workflow resume request using workflow orchestration service."""
        try:
            # Get logging service for logging
            _, _, logging_service = self.adapter.initialize_services()
            logger = logging_service.get_logger("agentmap.serverless.resume")

            thread_id = request_data.get("thread_id")
            response_action = request_data.get("response_action")
            response_data = request_data.get("response_data")
            data_file_path = request_data.get("data_file_path")

            logger.info(
                f"Serverless resuming workflow for thread {thread_id}",
                extra={"correlation_id": request_data.get("correlation_id")},
            )

            # Resume using workflow orchestration service
            result = resume_workflow(
                thread_id=thread_id,
                response_action=response_action,
                response_data=response_data,
                data_file_path=data_file_path,
            )

            return self._create_success_response(result)

        except Exception as e:
            return self._handle_error(e, request_data.get("correlation_id"))

    def _parse_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Legacy method for backward compatibility.
        New implementations should rely on _parse_event_by_trigger_type.
        """
        return self._parse_event_by_trigger_type(
            event, self._detect_trigger_type(event)
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

    def _handle_error(
        self, error: Exception, correlation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Handle errors with proper logging and correlation tracking."""
        try:
            # Try to get logger if services are available
            _, _, logging_service = self.adapter.initialize_services()
            logger = logging_service.get_logger("agentmap.serverless.error")
            logger.error(
                f"Serverless handler error: {error}",
                exc_info=True,
                extra={"correlation_id": correlation_id},
            )
        except:
            # Fallback if logging service unavailable
            print(f"Serverless handler error: {error} (Correlation: {correlation_id})")
            print(traceback.format_exc())

        # Use adapter for consistent error handling
        error_info = self.adapter.handle_execution_error(error)

        # Add correlation ID to error response
        error_response = self._create_error_response(
            error_info["error"], error_info["status_code"]
        )

        if correlation_id:
            body_data = json.loads(error_response["body"])
            body_data["correlation_id"] = correlation_id
            error_response["body"] = json.dumps(body_data)

        return error_response
