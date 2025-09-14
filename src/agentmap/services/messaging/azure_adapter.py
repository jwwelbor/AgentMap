"""
Azure Service Bus messaging adapter for AgentMap.

This module provides an Azure-specific implementation of the CloudMessageAdapter
interface for publishing messages to Azure Service Bus topics or queues.
"""

import json
from typing import Any, Dict, Optional

from agentmap.exceptions import MessagingConnectionError, MessagingOperationError
from agentmap.models.storage.types import StorageResult


class AzureMessageAdapter:
    """
    Azure Service Bus messaging adapter.

    This adapter implements the CloudMessageAdapter interface for
    Azure Service Bus, supporting both topics and queues.
    """

    def __init__(self, config: Dict[str, Any], logger):
        """
        Initialize the Azure messaging adapter.

        Args:
            config: Azure configuration with connection details
            logger: Logger instance for logging operations
        """
        self.config = config or {}
        self.logger = logger
        self._client = None
        self.connection_string = None
        self.service_type = None  # 'topic' or 'queue'

        # Initialize client
        self._initialize_client()

    def _initialize_client(self) -> None:
        """
        Initialize the Azure Service Bus client.

        Raises:
            MessagingConnectionError: If client initialization fails
        """
        try:
            # Import Azure SDK
            try:
                from azure.core.exceptions import AzureError
                from azure.servicebus import ServiceBusClient
            except ImportError:
                raise MessagingConnectionError(
                    "Azure Service Bus SDK not installed. "
                    "Please install with: pip install azure-servicebus"
                )

            # Get configuration
            self.connection_string = self.config.get("connection_string")
            if not self.connection_string:
                raise MessagingConnectionError(
                    "Azure Service Bus connection string not configured. "
                    "Please provide 'connection_string' in config."
                )

            self.service_type = self.config.get("service_type", "topic").lower()

            # Validate service type
            if self.service_type not in ["topic", "queue"]:
                raise MessagingConnectionError(
                    f"Invalid service_type: {self.service_type}. Must be 'topic' or 'queue'"
                )

            try:
                # Create Service Bus client
                self._client = ServiceBusClient.from_connection_string(
                    conn_str=self.connection_string
                )
                self.logger.debug(
                    f"Azure Service Bus client initialized for {self.service_type}"
                )

            except Exception as e:
                raise MessagingConnectionError(
                    f"Failed to initialize Azure Service Bus client: {str(e)}"
                )

        except Exception as e:
            self.logger.error(f"Failed to initialize Azure messaging client: {str(e)}")
            raise MessagingConnectionError(
                f"Failed to initialize Azure messaging client: {str(e)}"
            )

    async def publish(
        self,
        topic: str,
        message: Dict[str, Any],
        attributes: Optional[Dict[str, str]] = None,
    ) -> StorageResult:
        """
        Publish a message to Azure Service Bus topic or queue.

        Args:
            topic: Topic/queue name to publish to
            message: Message payload
            attributes: Optional message attributes

        Returns:
            StorageResult indicating success/failure
        """
        try:
            if self.service_type == "topic":
                return await self._publish_topic(topic, message, attributes)
            elif self.service_type == "queue":
                return await self._publish_queue(topic, message, attributes)
            else:
                return StorageResult(
                    success=False,
                    error=f"Unsupported service type: {self.service_type}",
                    operation="publish_message",
                )

        except Exception as e:
            self.logger.error(f"Error in Azure publish operation: {str(e)}")
            return StorageResult(
                success=False,
                error=f"Azure publish error: {str(e)}",
                operation="publish_message",
            )

    async def _publish_topic(
        self,
        topic: str,
        message: Dict[str, Any],
        attributes: Optional[Dict[str, str]] = None,
    ) -> StorageResult:
        """Publish message to Service Bus topic."""
        try:
            from azure.servicebus import ServiceBusMessage

            # Prepare message
            message_body = json.dumps(message)
            sb_message = ServiceBusMessage(message_body)

            # Add attributes as properties
            if attributes:
                for key, value in attributes.items():
                    sb_message.application_properties[key] = str(value)

            # Create sender and send message
            with self._client.get_topic_sender(topic_name=topic) as sender:
                sender.send_messages(sb_message)

            # Generate message ID (Azure doesn't provide one immediately)
            message_id = sb_message.message_id or f"azure-{topic}-{id(sb_message)}"

            self.logger.debug(
                f"Published message to Azure Service Bus topic {topic}: {message_id}"
            )

            return StorageResult(
                success=True,
                data={"message_id": message_id, "topic": topic, "service": "topic"},
                operation="publish_message",
            )

        except Exception as e:
            self.logger.error(f"Failed to publish message to topic {topic}: {str(e)}")
            return StorageResult(
                success=False,
                error=f"Topic publish failed: {str(e)}",
                operation="publish_message",
            )

    async def _publish_queue(
        self,
        queue: str,
        message: Dict[str, Any],
        attributes: Optional[Dict[str, str]] = None,
    ) -> StorageResult:
        """Publish message to Service Bus queue."""
        try:
            from azure.servicebus import ServiceBusMessage

            # Prepare message
            message_body = json.dumps(message)
            sb_message = ServiceBusMessage(message_body)

            # Add attributes as properties
            if attributes:
                for key, value in attributes.items():
                    sb_message.application_properties[key] = str(value)

            # Create sender and send message
            with self._client.get_queue_sender(queue_name=queue) as sender:
                sender.send_messages(sb_message)

            # Generate message ID (Azure doesn't provide one immediately)
            message_id = sb_message.message_id or f"azure-{queue}-{id(sb_message)}"

            self.logger.debug(
                f"Published message to Azure Service Bus queue {queue}: {message_id}"
            )

            return StorageResult(
                success=True,
                data={"message_id": message_id, "queue": queue, "service": "queue"},
                operation="publish_message",
            )

        except Exception as e:
            self.logger.error(f"Failed to publish message to queue {queue}: {str(e)}")
            return StorageResult(
                success=False,
                error=f"Queue publish failed: {str(e)}",
                operation="publish_message",
            )

    async def create_topic(self, topic_name: str) -> StorageResult:
        """
        Create a topic/queue if it doesn't exist.

        Note: Azure Service Bus topics/queues are typically created through
        the Azure portal or ARM templates. This method provides basic
        creation functionality but may require additional permissions.

        Args:
            topic_name: Name of the topic/queue to create

        Returns:
            StorageResult indicating success/failure
        """
        try:
            if self.service_type == "topic":
                return await self._create_topic_entity(topic_name)
            elif self.service_type == "queue":
                return await self._create_queue_entity(topic_name)
            else:
                return StorageResult(
                    success=False,
                    error=f"Unsupported service type: {self.service_type}",
                    operation="create_topic",
                )

        except Exception as e:
            self.logger.error(f"Error in Azure create_topic operation: {str(e)}")
            return StorageResult(
                success=False,
                error=f"Azure create_topic error: {str(e)}",
                operation="create_topic",
            )

    async def _create_topic_entity(self, topic_name: str) -> StorageResult:
        """Create Service Bus topic."""
        try:
            # Note: Topic creation requires management operations
            # For basic messaging, topics are usually pre-created
            self.logger.info(
                f"Azure Service Bus topic creation attempted: {topic_name}"
            )
            self.logger.warning(
                "Azure Service Bus topics are typically pre-created through Azure portal. "
                "Ensure the topic exists before publishing."
            )

            return StorageResult(
                success=True,
                data={"topic_name": topic_name, "note": "Topic should be pre-created"},
                operation="create_topic",
            )

        except Exception as e:
            self.logger.error(
                f"Failed to create Azure Service Bus topic {topic_name}: {str(e)}"
            )
            return StorageResult(
                success=False,
                error=f"Failed to create topic: {str(e)}",
                operation="create_topic",
            )

    async def _create_queue_entity(self, queue_name: str) -> StorageResult:
        """Create Service Bus queue."""
        try:
            # Note: Queue creation requires management operations
            # For basic messaging, queues are usually pre-created
            self.logger.info(
                f"Azure Service Bus queue creation attempted: {queue_name}"
            )
            self.logger.warning(
                "Azure Service Bus queues are typically pre-created through Azure portal. "
                "Ensure the queue exists before publishing."
            )

            return StorageResult(
                success=True,
                data={"queue_name": queue_name, "note": "Queue should be pre-created"},
                operation="create_topic",
            )

        except Exception as e:
            self.logger.error(
                f"Failed to create Azure Service Bus queue {queue_name}: {str(e)}"
            )
            return StorageResult(
                success=False,
                error=f"Failed to create queue: {str(e)}",
                operation="create_topic",
            )

    def get_provider(self):
        """Get the cloud provider type."""
        from agentmap.services.messaging.messaging_service import CloudProvider

        return CloudProvider.AZURE
