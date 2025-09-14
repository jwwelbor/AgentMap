"""
AWS SNS/SQS messaging adapter for AgentMap.

This module provides an AWS-specific implementation of the CloudMessageAdapter
interface for publishing messages to AWS SNS topics or SQS queues.
"""

import json
from typing import Any, Dict, Optional

from agentmap.exceptions import MessagingConnectionError, MessagingOperationError
from agentmap.models.storage.types import StorageResult


class AWSMessageAdapter:
    """
    AWS SNS/SQS messaging adapter.

    This adapter implements the CloudMessageAdapter interface for
    AWS messaging services, supporting both SNS and SQS.
    """

    def __init__(self, config: Dict[str, Any], logger):
        """
        Initialize the AWS messaging adapter.

        Args:
            config: AWS configuration with connection details
            logger: Logger instance for logging operations
        """
        self.config = config or {}
        self.logger = logger
        self._sns_client = None
        self._sqs_client = None
        self.region_name = None
        self.service_type = None  # 'sns' or 'sqs'

        # Initialize clients
        self._initialize_clients()

    def _initialize_clients(self) -> None:
        """
        Initialize the AWS SNS and SQS clients.

        Raises:
            MessagingConnectionError: If client initialization fails
        """
        try:
            # Import AWS SDK
            try:
                import boto3
                from botocore.exceptions import (
                    BotoCoreError,
                    ClientError,
                    NoCredentialsError,
                )
            except ImportError:
                raise MessagingConnectionError(
                    "AWS SDK (boto3) not installed. "
                    "Please install with: pip install boto3"
                )

            # Get configuration
            self.region_name = self.config.get("region_name", "us-east-1")
            self.service_type = self.config.get("service_type", "sns").lower()

            # Validate service type
            if self.service_type not in ["sns", "sqs"]:
                raise MessagingConnectionError(
                    f"Invalid service_type: {self.service_type}. Must be 'sns' or 'sqs'"
                )

            try:
                # Create session with optional profile
                session_kwargs = {}
                if "profile_name" in self.config:
                    session_kwargs["profile_name"] = self.config["profile_name"]

                session = boto3.Session(**session_kwargs)

                # Create clients based on service type
                if self.service_type == "sns":
                    self._sns_client = session.client(
                        "sns", region_name=self.region_name
                    )
                    self.logger.debug(
                        f"AWS SNS client initialized for region: {self.region_name}"
                    )
                elif self.service_type == "sqs":
                    self._sqs_client = session.client(
                        "sqs", region_name=self.region_name
                    )
                    self.logger.debug(
                        f"AWS SQS client initialized for region: {self.region_name}"
                    )

            except NoCredentialsError:
                raise MessagingConnectionError(
                    "AWS credentials not configured. Please configure AWS credentials."
                )
            except Exception as e:
                raise MessagingConnectionError(
                    f"Failed to initialize AWS clients: {str(e)}"
                )

        except Exception as e:
            self.logger.error(f"Failed to initialize AWS messaging client: {str(e)}")
            raise MessagingConnectionError(
                f"Failed to initialize AWS messaging client: {str(e)}"
            )

    async def publish(
        self,
        topic: str,
        message: Dict[str, Any],
        attributes: Optional[Dict[str, str]] = None,
    ) -> StorageResult:
        """
        Publish a message to AWS SNS topic or SQS queue.

        Args:
            topic: Topic/queue name to publish to
            message: Message payload
            attributes: Optional message attributes

        Returns:
            StorageResult indicating success/failure
        """
        try:
            if self.service_type == "sns":
                return await self._publish_sns(topic, message, attributes)
            elif self.service_type == "sqs":
                return await self._publish_sqs(topic, message, attributes)
            else:
                return StorageResult(
                    success=False,
                    error=f"Unsupported service type: {self.service_type}",
                    operation="publish_message",
                )

        except Exception as e:
            self.logger.error(f"Error in AWS publish operation: {str(e)}")
            return StorageResult(
                success=False,
                error=f"AWS publish error: {str(e)}",
                operation="publish_message",
            )

    async def _publish_sns(
        self,
        topic: str,
        message: Dict[str, Any],
        attributes: Optional[Dict[str, str]] = None,
    ) -> StorageResult:
        """Publish message to SNS topic."""
        try:
            # Get or create topic ARN
            topic_arn = await self._get_topic_arn(topic)
            if not topic_arn:
                return StorageResult(
                    success=False,
                    error=f"Failed to get topic ARN for: {topic}",
                    operation="publish_message",
                )

            # Prepare message
            message_body = json.dumps(message)

            # Prepare message attributes for SNS
            message_attributes = {}
            if attributes:
                for key, value in attributes.items():
                    message_attributes[key] = {
                        "DataType": "String",
                        "StringValue": str(value),
                    }

            # Publish to SNS
            response = self._sns_client.publish(
                TopicArn=topic_arn,
                Message=message_body,
                MessageAttributes=message_attributes,
            )

            message_id = response.get("MessageId")
            self.logger.debug(f"Published SNS message to {topic}: {message_id}")

            return StorageResult(
                success=True,
                data={"message_id": message_id, "topic": topic, "service": "sns"},
                operation="publish_message",
            )

        except Exception as e:
            self.logger.error(f"Failed to publish SNS message to {topic}: {str(e)}")
            return StorageResult(
                success=False,
                error=f"SNS publish failed: {str(e)}",
                operation="publish_message",
            )

    async def _publish_sqs(
        self,
        queue: str,
        message: Dict[str, Any],
        attributes: Optional[Dict[str, str]] = None,
    ) -> StorageResult:
        """Publish message to SQS queue."""
        try:
            # Get queue URL
            queue_url = await self._get_queue_url(queue)
            if not queue_url:
                return StorageResult(
                    success=False,
                    error=f"Failed to get queue URL for: {queue}",
                    operation="publish_message",
                )

            # Prepare message
            message_body = json.dumps(message)

            # Prepare message attributes for SQS
            message_attributes = {}
            if attributes:
                for key, value in attributes.items():
                    message_attributes[key] = {
                        "DataType": "String",
                        "StringValue": str(value),
                    }

            # Send to SQS
            response = self._sqs_client.send_message(
                QueueUrl=queue_url,
                MessageBody=message_body,
                MessageAttributes=message_attributes,
            )

            message_id = response.get("MessageId")
            self.logger.debug(f"Published SQS message to {queue}: {message_id}")

            return StorageResult(
                success=True,
                data={"message_id": message_id, "queue": queue, "service": "sqs"},
                operation="publish_message",
            )

        except Exception as e:
            self.logger.error(f"Failed to publish SQS message to {queue}: {str(e)}")
            return StorageResult(
                success=False,
                error=f"SQS publish failed: {str(e)}",
                operation="publish_message",
            )

    async def create_topic(self, topic_name: str) -> StorageResult:
        """
        Create a topic/queue if it doesn't exist.

        Args:
            topic_name: Name of the topic/queue to create

        Returns:
            StorageResult indicating success/failure
        """
        try:
            if self.service_type == "sns":
                return await self._create_sns_topic(topic_name)
            elif self.service_type == "sqs":
                return await self._create_sqs_queue(topic_name)
            else:
                return StorageResult(
                    success=False,
                    error=f"Unsupported service type: {self.service_type}",
                    operation="create_topic",
                )

        except Exception as e:
            self.logger.error(f"Error in AWS create_topic operation: {str(e)}")
            return StorageResult(
                success=False,
                error=f"AWS create_topic error: {str(e)}",
                operation="create_topic",
            )

    async def _create_sns_topic(self, topic_name: str) -> StorageResult:
        """Create SNS topic."""
        try:
            response = self._sns_client.create_topic(Name=topic_name)
            topic_arn = response["TopicArn"]

            self.logger.info(f"Created/verified AWS SNS topic: {topic_name}")

            return StorageResult(
                success=True,
                data={"topic_name": topic_name, "topic_arn": topic_arn},
                operation="create_topic",
            )

        except Exception as e:
            self.logger.error(f"Failed to create SNS topic {topic_name}: {str(e)}")
            return StorageResult(
                success=False,
                error=f"Failed to create SNS topic: {str(e)}",
                operation="create_topic",
            )

    async def _create_sqs_queue(self, queue_name: str) -> StorageResult:
        """Create SQS queue."""
        try:
            response = self._sqs_client.create_queue(QueueName=queue_name)
            queue_url = response["QueueUrl"]

            self.logger.info(f"Created/verified AWS SQS queue: {queue_name}")

            return StorageResult(
                success=True,
                data={"queue_name": queue_name, "queue_url": queue_url},
                operation="create_topic",
            )

        except Exception as e:
            self.logger.error(f"Failed to create SQS queue {queue_name}: {str(e)}")
            return StorageResult(
                success=False,
                error=f"Failed to create SQS queue: {str(e)}",
                operation="create_topic",
            )

    async def _get_topic_arn(self, topic_name: str) -> Optional[str]:
        """Get SNS topic ARN, creating topic if needed."""
        try:
            # First try to find existing topic
            paginator = self._sns_client.get_paginator("list_topics")
            for page in paginator.paginate():
                for topic in page["Topics"]:
                    arn = topic["TopicArn"]
                    if arn.endswith(f":{topic_name}"):
                        return arn

            # Topic not found, create it
            result = await self._create_sns_topic(topic_name)
            if result.success:
                return result.data.get("topic_arn")

            return None

        except Exception as e:
            self.logger.error(f"Failed to get topic ARN for {topic_name}: {str(e)}")
            return None

    async def _get_queue_url(self, queue_name: str) -> Optional[str]:
        """Get SQS queue URL, creating queue if needed."""
        try:
            # Try to get existing queue
            try:
                response = self._sqs_client.get_queue_url(QueueName=queue_name)
                return response["QueueUrl"]
            except self._sqs_client.exceptions.QueueDoesNotExist:
                # Queue doesn't exist, create it
                result = await self._create_sqs_queue(queue_name)
                if result.success:
                    return result.data.get("queue_url")
                return None

        except Exception as e:
            self.logger.error(f"Failed to get queue URL for {queue_name}: {str(e)}")
            return None

    def get_provider(self):
        """Get the cloud provider type."""
        from agentmap.services.messaging.messaging_service import CloudProvider

        return CloudProvider.AWS
