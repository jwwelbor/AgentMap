"""
Result publisher service for async triggers.

This service handles optional publishing of execution results back to
message queues or other destinations for async trigger types.
"""

from typing import Any, Dict


class ResultPublisher:
    """Service for publishing execution results to external systems."""

    def __init__(self, container):
        """Initialize with DI container."""
        self._container = container

    async def publish_if_requested(
        self, request_payload: Dict[str, Any], response_body: Dict[str, Any]
    ) -> None:
        """
        Publish execution results if requested in the payload.

        Args:
            request_payload: Original request data that may contain publish_result config
            response_body: Execution response to publish
        """
        publish_config = request_payload.get("publish_result")
        if not publish_config:
            return

        try:
            messaging_service = self._container.messaging_service()

            await messaging_service.publish_message(
                topic=publish_config.get("topic", "agentmap-results"),
                message_type="execution_result",
                payload=response_body,
                metadata={
                    "correlation_id": request_payload.get("correlation_id"),
                    "original_action": request_payload.get("action", "run"),
                    "trigger_type": request_payload.get("trigger_type"),
                },
            )
        except Exception as e:
            # Non-fatal error - don't fail the main execution
            print(f"Failed to publish result: {e}")
