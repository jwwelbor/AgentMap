"""AWS EventBridge timer events strategy for trigger parsing."""

from typing import Any, Dict, Tuple

from agentmap.models.serverless_models import TriggerType


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
