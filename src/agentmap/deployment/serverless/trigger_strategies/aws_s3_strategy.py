"""AWS S3 bucket events strategy for trigger parsing."""

from typing import Any, Dict, Tuple

from agentmap.models.serverless_models import TriggerType


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
