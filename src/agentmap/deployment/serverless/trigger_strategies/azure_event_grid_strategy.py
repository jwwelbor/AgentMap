"""Azure Event Grid strategy for trigger parsing."""

from typing import Any, Dict, Tuple

from agentmap.models.serverless_models import TriggerType


class AzureEventGridStrategy:
    """Strategy for Azure Event Grid events."""

    def matches(self, event: Dict[str, Any]) -> bool:
        return all(key in event for key in ("data", "eventType", "subject"))

    def parse(self, event: Dict[str, Any]) -> Tuple[TriggerType, Dict[str, Any]]:
        data = event.get("execution_params") or event
        return TriggerType.MESSAGE_QUEUE, data
