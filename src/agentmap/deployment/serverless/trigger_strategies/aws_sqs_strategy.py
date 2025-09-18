"""AWS SQS strategy for trigger parsing."""

from typing import Any, Dict, Tuple

from agentmap.models.serverless_models import TriggerType
from agentmap.services.serverless.utils import safe_json_loads


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
