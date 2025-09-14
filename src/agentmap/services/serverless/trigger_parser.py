"""
Trigger parser service using strategy pattern.

This module provides pluggable strategies for parsing different cloud
platform events into standardized request data.
"""

import base64
from typing import Any, Dict, List, Protocol, Tuple

from ....models.serverless_models import TriggerType
from .utils import ddb_image_to_dict, safe_json_loads


class TriggerStrategy(Protocol):
    """Protocol for trigger parsing strategies."""

    def matches(self, event: Dict[str, Any]) -> bool:
        """Check if this strategy can handle the given event."""
        ...

    def parse(self, event: Dict[str, Any]) -> Tuple[TriggerType, Dict[str, Any]]:
        """Parse the event into trigger type and normalized data."""
        ...


class TriggerParser:
    """Parser that uses strategies to handle different trigger types."""

    def __init__(self, strategies: List[TriggerStrategy]):
        """Initialize with list of parsing strategies."""
        self._strategies = strategies

    def parse(self, event: Dict[str, Any]) -> Tuple[TriggerType, Dict[str, Any]]:
        """
        Parse event using first matching strategy.

        Args:
            event: Raw cloud platform event

        Returns:
            Tuple of (TriggerType, normalized_data)
        """
        for strategy in self._strategies:
            if strategy.matches(event):
                return strategy.parse(event)

        # Default: treat as HTTP-like event
        body = event.get("body", event)
        data = safe_json_loads(body)

        # Merge path and query parameters if present
        if isinstance(event.get("pathParameters"), dict):
            data.update(event["pathParameters"])
        if isinstance(event.get("queryStringParameters"), dict):
            data.update(event["queryStringParameters"])

        return TriggerType.HTTP, data


# --- Strategy Implementations ---


class AwsHttpApiStrategy:
    """Strategy for AWS API Gateway HTTP events."""

    def matches(self, event: Dict[str, Any]) -> bool:
        return any(key in event for key in ("httpMethod", "requestContext", "headers"))

    def parse(self, event: Dict[str, Any]) -> Tuple[TriggerType, Dict[str, Any]]:
        method = (event.get("httpMethod") or event.get("method") or "POST").upper()

        if method == "POST":
            data = safe_json_loads(event.get("body", "{}"))
        else:
            data = event.get("queryStringParameters") or {}

        # Add path parameters
        if isinstance(event.get("pathParameters"), dict):
            data.update(event["pathParameters"])

        return TriggerType.HTTP, data


class AwsSqsStrategy:
    """Strategy for AWS SQS message events."""

    def matches(self, event: Dict[str, Any]) -> bool:
        return "Records" in event and any(
            "sqs" in record.get("eventSource", "") for record in event["Records"]
        )

    def parse(self, event: Dict[str, Any]) -> Tuple[TriggerType, Dict[str, Any]]:
        record = event["Records"][0]  # Process first message
        data = safe_json_loads(record.get("body", "{}"))
        return TriggerType.MESSAGE_QUEUE, data


class AwsS3Strategy:
    """Strategy for AWS S3 bucket events."""

    def matches(self, event: Dict[str, Any]) -> bool:
        return "Records" in event and any("s3" in record for record in event["Records"])

    def parse(self, event: Dict[str, Any]) -> Tuple[TriggerType, Dict[str, Any]]:
        record = event["Records"][0]
        s3_data = record["s3"]

        payload = {
            "csv": s3_data["object"]["key"],
            "storage_event": {
                "bucket": s3_data["bucket"]["name"],
                "key": s3_data["object"]["key"],
                "event_name": record.get("eventName", ""),
            },
        }
        payload.setdefault("action", "run")

        return TriggerType.STORAGE, payload


class AwsDdbStreamStrategy:
    """Strategy for AWS DynamoDB Stream events."""

    def matches(self, event: Dict[str, Any]) -> bool:
        return "Records" in event and any(
            "dynamodb" in record for record in event["Records"]
        )

    def parse(self, event: Dict[str, Any]) -> Tuple[TriggerType, Dict[str, Any]]:
        record = event["Records"][0]
        operation = record.get("eventName", "")

        # Get appropriate image based on operation
        dynamo_data = record.get("dynamodb", {})
        if operation in ("INSERT", "MODIFY"):
            image = dynamo_data.get("NewImage", {})
        else:
            image = dynamo_data.get("OldImage", {})

        data = ddb_image_to_dict(image)
        table = record.get("eventSourceARN", "").split("/")[-1]

        payload = {
            "action": "run",
            "database_event": {"operation": operation, "data": data, "table": table},
        }

        return TriggerType.DATABASE, payload


class AwsEventBridgeTimerStrategy:
    """Strategy for AWS EventBridge timer events."""

    def matches(self, event: Dict[str, Any]) -> bool:
        return event.get("source", "").startswith("aws.events")

    def parse(self, event: Dict[str, Any]) -> Tuple[TriggerType, Dict[str, Any]]:
        payload = {
            "action": "run",
            "scheduled_event": {
                "source": event.get("source", ""),
                "detail_type": event.get("detail-type", ""),
                "time": event.get("time", ""),
                "detail": event.get("detail", {}),
            },
        }

        return TriggerType.TIMER, payload


class AzureEventGridStrategy:
    """Strategy for Azure Event Grid events."""

    def matches(self, event: Dict[str, Any]) -> bool:
        return all(key in event for key in ("data", "eventType", "subject"))

    def parse(self, event: Dict[str, Any]) -> Tuple[TriggerType, Dict[str, Any]]:
        data = event.get("execution_params") or event
        return TriggerType.MESSAGE_QUEUE, data


class GcpPubSubStrategy:
    """Strategy for Google Cloud Pub/Sub events."""

    def matches(self, event: Dict[str, Any]) -> bool:
        return "data" in event and "@type" in event

    def parse(self, event: Dict[str, Any]) -> Tuple[TriggerType, Dict[str, Any]]:
        raw_data = event.get("data")

        if isinstance(raw_data, str):
            try:
                decoded = base64.b64decode(raw_data).decode("utf-8")
                data = safe_json_loads(decoded)
            except Exception:
                data = {"raw_data": raw_data, "action": "run"}
        else:
            data = raw_data or {"action": "run"}

        return TriggerType.MESSAGE_QUEUE, data
