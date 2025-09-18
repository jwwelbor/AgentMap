"""AWS HTTP API Gateway strategy for trigger parsing."""

from typing import Any, Dict, Tuple

from agentmap.models.serverless_models import TriggerType
from agentmap.services.serverless.utils import safe_json_loads


class HttpStrategy:
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
