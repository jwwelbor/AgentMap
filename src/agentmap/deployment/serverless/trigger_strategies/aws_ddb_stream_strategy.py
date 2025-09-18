"""AWS DynamoDB Stream events strategy for trigger parsing."""

from typing import Any, Dict, Tuple

from agentmap.models.serverless_models import TriggerType
from agentmap.services.serverless.utils import ddb_image_to_dict


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
