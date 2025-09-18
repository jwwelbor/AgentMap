"""
Trigger parser service using strategy pattern.

This module provides pluggable strategies for parsing different cloud
platform events into standardized request data.
"""

from typing import Any, Dict, List, Protocol, Tuple

from agentmap.deployment.serverless.trigger_strategies import (
    AwsDdbStreamStrategy,
    AwsEventBridgeTimerStrategy,
    AwsS3Strategy,
    AwsSqsStrategy,
    AzureEventGridStrategy,
    GcpPubSubStrategy,
    HttpStrategy,
)
from agentmap.models.serverless_models import TriggerType
from agentmap.services.serverless.utils import safe_json_loads


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
