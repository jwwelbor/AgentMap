"""
Google Cloud Pub/Sub messaging adapter for AgentMap.

This module provides a GCP-specific implementation of the CloudMessageAdapter
interface for publishing messages to Google Cloud Pub/Sub topics.
"""

import json
from typing import Any, Dict, Optional

from agentmap.exceptions import MessagingConnectionError, MessagingOperationError
from agentmap.models.storage.types import StorageResult


class GCPMessageAdapter:
    """
    Google Cloud Pub/Sub messaging adapter.

    This adapter implements the CloudMessageAdapter interface for
    Google Cloud Pub/Sub, supporting topic creation and message publishing.
    """

    def __init__(self, config: Dict[str, Any], logger):
        """
        Initialize the GCP Pub/Sub adapter.

        Args:
            config: GCP configuration with connection details
            logger: Logger instance for logging operations
        """
        self.config = config or {}
        self.logger = logger
        self._client = None
        self._publisher = None
        self.project_id = None

        # Initialize client
        self._initialize_client()

    def _initialize_client(self) -> None:
        """
        Initialize the Google Cloud Pub/Sub client.

        Raises:
            MessagingConnectionError: If client initialization fails
        """
        try:
            # Import Google Cloud SDK
            try:
                import google.auth.exceptions
                from google.auth import default
                from google.cloud import pubsub_v1
            except ImportError:
                raise MessagingConnectionError(
                    "Google Cloud Pub/Sub SDK not installed. "
                    "Please install with: pip install google-cloud-pubsub"
                )

            # Get project ID from config or environment
            self.project_id = self.config.get("project_id")
            if not self.project_id:
                try:
                    _, self.project_id = default()
                except google.auth.exceptions.DefaultCredentialsError:
                    raise MessagingConnectionError(
                        "GCP project ID not configured and no default credentials found. "
                        "Please set project_id in config or configure default credentials."
                    )

            # Create publisher client
            try:
                self._publisher = pubsub_v1.PublisherClient()
                self.logger.debug(
                    f"GCP Pub/Sub client initialized for project: {self.project_id}"
                )
            except Exception as e:
                raise MessagingConnectionError(
                    f"Failed to initialize GCP Pub/Sub publisher client: {str(e)}"
                )

        except Exception as e:
            self.logger.error(f"Failed to initialize GCP Pub/Sub client: {str(e)}")
            raise MessagingConnectionError(
                f"Failed to initialize GCP Pub/Sub client: {str(e)}"
            )

    async def publish(
        self,
        topic: str,
        message: Dict[str, Any],
        attributes: Optional[Dict[str, str]] = None,
    ) -> StorageResult:
        """
        Publish a message to a GCP Pub/Sub topic.

        Args:
            topic: Topic name to publish to
            message: Message payload
            attributes: Optional message attributes

        Returns:
            StorageResult indicating success/failure
        """
        try:
            # Construct topic path
            topic_path = self._publisher.topic_path(self.project_id, topic)

            # Serialize message to JSON bytes
            message_data = json.dumps(message).encode("utf-8")

            # Prepare attributes (Pub/Sub requires string values)
            pub_attributes = {}
            if attributes:
                for key, value in attributes.items():
                    pub_attributes[key] = str(value)

            # Publish message
            try:
                future = self._publisher.publish(
                    topic_path, data=message_data, **pub_attributes
                )

                # Wait for publish to complete
                message_id = future.result()

                self.logger.debug(f"Published message to {topic}: {message_id}")

                return StorageResult(
                    success=True,
                    data={"message_id": message_id, "topic": topic},
                    operation="publish_message",
                )

            except Exception as e:
                self.logger.error(f"Failed to publish message to {topic}: {str(e)}")
                return StorageResult(
                    success=False,
                    error=f"Failed to publish message: {str(e)}",
                    operation="publish_message",
                )

        except Exception as e:
            self.logger.error(f"Error in GCP publish operation: {str(e)}")
            return StorageResult(
                success=False,
                error=f"GCP publish error: {str(e)}",
                operation="publish_message",
            )

    async def create_topic(self, topic_name: str) -> StorageResult:
        """
        Create a topic if it doesn't exist.

        Args:
            topic_name: Name of the topic to create

        Returns:
            StorageResult indicating success/failure
        """
        try:
            # Construct topic path
            topic_path = self._publisher.topic_path(self.project_id, topic_name)

            try:
                # Try to create the topic
                topic = self._publisher.create_topic(request={"name": topic_path})
                self.logger.info(f"Created GCP Pub/Sub topic: {topic_name}")

                return StorageResult(
                    success=True,
                    data={"topic_name": topic_name, "topic_path": topic.name},
                    operation="create_topic",
                )

            except Exception as e:
                # Check if topic already exists
                error_msg = str(e).lower()
                if (
                    "already exists" in error_msg
                    or "resource already exists" in error_msg
                ):
                    self.logger.debug(f"GCP Pub/Sub topic already exists: {topic_name}")
                    return StorageResult(
                        success=True,
                        data={"topic_name": topic_name, "already_exists": True},
                        operation="create_topic",
                    )
                else:
                    self.logger.error(
                        f"Failed to create GCP Pub/Sub topic {topic_name}: {str(e)}"
                    )
                    return StorageResult(
                        success=False,
                        error=f"Failed to create topic: {str(e)}",
                        operation="create_topic",
                    )

        except Exception as e:
            self.logger.error(f"Error in GCP create_topic operation: {str(e)}")
            return StorageResult(
                success=False,
                error=f"GCP create_topic error: {str(e)}",
                operation="create_topic",
            )

    def get_provider(self):
        """Get the cloud provider type."""
        from agentmap.services.messaging.messaging_service import CloudProvider

        return CloudProvider.GCP
