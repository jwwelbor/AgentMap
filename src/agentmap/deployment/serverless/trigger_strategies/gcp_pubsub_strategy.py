"""Google Cloud Pub/Sub strategy for trigger parsing."""

import base64
from typing import Any, Dict, Tuple

from agentmap.models.serverless_models import TriggerType
from agentmap.services.serverless.utils import safe_json_loads


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
