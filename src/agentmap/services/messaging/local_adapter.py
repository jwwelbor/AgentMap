"""
Local file-based messaging adapter for AgentMap.

This module provides a local file-based implementation of the CloudMessageAdapter
interface for testing and development purposes. Messages are stored as JSON files
in a local directory structure.
"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from agentmap.exceptions import MessagingConnectionError, MessagingOperationError
from agentmap.models.storage.types import StorageResult


class LocalMessageAdapter:
    """
    Local file-based messaging adapter.

    This adapter implements the CloudMessageAdapter interface for
    local development and testing, storing messages as JSON files
    in a directory structure organized by topic.
    """

    def __init__(self, config: Dict[str, Any], logger):
        """
        Initialize the local messaging adapter.

        Args:
            config: Local configuration with storage path
            logger: Logger instance for logging operations
        """
        self.config = config or {}
        self.logger = logger
        self.storage_path = None

        # Initialize storage
        self._initialize_storage()

    def _initialize_storage(self) -> None:
        """
        Initialize the local storage directory.

        Raises:
            MessagingConnectionError: If storage initialization fails
        """
        try:
            # Get storage path from config
            self.storage_path = self.config.get("storage_path", "data/messages")

            # Convert to Path object for easier manipulation
            self.storage_path = Path(self.storage_path).resolve()

            # Create storage directory if it doesn't exist
            try:
                self.storage_path.mkdir(parents=True, exist_ok=True)
                self.logger.debug(
                    f"Local message storage initialized at: {self.storage_path}"
                )
            except Exception as e:
                raise MessagingConnectionError(
                    f"Failed to create storage directory {self.storage_path}: {str(e)}"
                )

            # Verify write access
            try:
                test_file = self.storage_path / ".test_write"
                test_file.write_text("test")
                test_file.unlink()
            except Exception as e:
                raise MessagingConnectionError(
                    f"No write access to storage directory {self.storage_path}: {str(e)}"
                )

        except Exception as e:
            self.logger.error(f"Failed to initialize local messaging storage: {str(e)}")
            raise MessagingConnectionError(
                f"Failed to initialize local messaging storage: {str(e)}"
            )

    async def publish(
        self,
        topic: str,
        message: Dict[str, Any],
        attributes: Optional[Dict[str, str]] = None,
    ) -> StorageResult:
        """
        Publish a message to local storage.

        Args:
            topic: Topic name (becomes subdirectory)
            message: Message payload
            attributes: Optional message attributes

        Returns:
            StorageResult indicating success/failure
        """
        try:
            # Generate unique message ID
            message_id = str(uuid.uuid4())
            timestamp = datetime.utcnow().isoformat()

            # Create topic directory if it doesn't exist
            topic_dir = self.storage_path / topic
            topic_dir.mkdir(parents=True, exist_ok=True)

            # Build complete message structure
            complete_message = {
                "message_id": message_id,
                "timestamp": timestamp,
                "topic": topic,
                "payload": message,
                "attributes": attributes or {},
                "source": "local_adapter",
            }

            # Create filename with timestamp and message ID
            filename = (
                f"{timestamp.replace(':', '-').replace('.', '-')}_{message_id}.json"
            )
            message_file = topic_dir / filename

            # Write message to file
            try:
                with open(message_file, "w", encoding="utf-8") as f:
                    json.dump(complete_message, f, indent=2, ensure_ascii=False)

                self.logger.debug(f"Published local message to {topic}: {message_id}")

                return StorageResult(
                    success=True,
                    data={
                        "message_id": message_id,
                        "topic": topic,
                        "file_path": str(message_file),
                        "timestamp": timestamp,
                    },
                    operation="publish_message",
                )

            except Exception as e:
                self.logger.error(
                    f"Failed to write message file {message_file}: {str(e)}"
                )
                return StorageResult(
                    success=False,
                    error=f"Failed to write message file: {str(e)}",
                    operation="publish_message",
                )

        except Exception as e:
            self.logger.error(f"Error in local publish operation: {str(e)}")
            return StorageResult(
                success=False,
                error=f"Local publish error: {str(e)}",
                operation="publish_message",
            )

    async def create_topic(self, topic_name: str) -> StorageResult:
        """
        Create a topic directory if it doesn't exist.

        Args:
            topic_name: Name of the topic to create

        Returns:
            StorageResult indicating success/failure
        """
        try:
            # Create topic directory
            topic_dir = self.storage_path / topic_name
            topic_dir.mkdir(parents=True, exist_ok=True)

            # Create a topic metadata file
            metadata_file = topic_dir / ".topic_metadata.json"
            metadata = {
                "topic_name": topic_name,
                "created_at": datetime.utcnow().isoformat(),
                "message_count": 0,
                "adapter_type": "local",
            }

            # Only create metadata if it doesn't exist
            if not metadata_file.exists():
                with open(metadata_file, "w", encoding="utf-8") as f:
                    json.dump(metadata, f, indent=2)

                self.logger.info(f"Created local topic directory: {topic_name}")
            else:
                self.logger.debug(f"Local topic directory already exists: {topic_name}")

            return StorageResult(
                success=True,
                data={
                    "topic_name": topic_name,
                    "topic_path": str(topic_dir),
                    "metadata_file": str(metadata_file),
                },
                operation="create_topic",
            )

        except Exception as e:
            self.logger.error(f"Failed to create local topic {topic_name}: {str(e)}")
            return StorageResult(
                success=False,
                error=f"Failed to create topic: {str(e)}",
                operation="create_topic",
            )

    def list_topics(self) -> list[str]:
        """
        List all available topics (directories) in storage.

        Returns:
            List of topic names
        """
        try:
            topics = []
            if self.storage_path.exists():
                for item in self.storage_path.iterdir():
                    if item.is_dir() and not item.name.startswith("."):
                        topics.append(item.name)
            return sorted(topics)
        except Exception as e:
            self.logger.error(f"Failed to list topics: {str(e)}")
            return []

    def list_messages(
        self, topic: str, limit: Optional[int] = None
    ) -> list[Dict[str, Any]]:
        """
        List messages in a topic.

        Args:
            topic: Topic name to list messages from
            limit: Optional limit on number of messages to return

        Returns:
            List of message metadata
        """
        try:
            topic_dir = self.storage_path / topic
            if not topic_dir.exists():
                return []

            messages = []
            message_files = sorted(
                [
                    f
                    for f in topic_dir.iterdir()
                    if f.is_file()
                    and f.suffix == ".json"
                    and not f.name.startswith(".")
                ],
                key=lambda x: x.stat().st_mtime,
                reverse=True,  # Most recent first
            )

            for message_file in message_files:
                if limit and len(messages) >= limit:
                    break

                try:
                    with open(message_file, "r", encoding="utf-8") as f:
                        message_data = json.load(f)
                        messages.append(
                            {
                                "message_id": message_data.get("message_id"),
                                "timestamp": message_data.get("timestamp"),
                                "topic": message_data.get("topic"),
                                "file_path": str(message_file),
                                "attributes": message_data.get("attributes", {}),
                            }
                        )
                except Exception as e:
                    self.logger.warning(
                        f"Failed to read message file {message_file}: {str(e)}"
                    )
                    continue

            return messages

        except Exception as e:
            self.logger.error(f"Failed to list messages for topic {topic}: {str(e)}")
            return []

    def read_message(self, topic: str, message_id: str) -> Optional[Dict[str, Any]]:
        """
        Read a specific message by ID.

        Args:
            topic: Topic name
            message_id: Message ID to read

        Returns:
            Message data or None if not found
        """
        try:
            topic_dir = self.storage_path / topic
            if not topic_dir.exists():
                return None

            # Find message file containing the message ID
            for message_file in topic_dir.iterdir():
                if message_file.is_file() and message_file.suffix == ".json":
                    try:
                        with open(message_file, "r", encoding="utf-8") as f:
                            message_data = json.load(f)
                            if message_data.get("message_id") == message_id:
                                return message_data
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to read message file {message_file}: {str(e)}"
                        )
                        continue

            return None

        except Exception as e:
            self.logger.error(
                f"Failed to read message {message_id} from topic {topic}: {str(e)}"
            )
            return None

    def get_storage_info(self) -> Dict[str, Any]:
        """
        Get information about local storage usage.

        Returns:
            Storage information dictionary
        """
        try:
            info = {
                "storage_path": str(self.storage_path),
                "topics": [],
                "total_messages": 0,
                "storage_size_bytes": 0,
            }

            if self.storage_path.exists():
                for topic_dir in self.storage_path.iterdir():
                    if topic_dir.is_dir() and not topic_dir.name.startswith("."):
                        topic_info = {
                            "name": topic_dir.name,
                            "message_count": 0,
                            "size_bytes": 0,
                        }

                        for message_file in topic_dir.iterdir():
                            if (
                                message_file.is_file()
                                and message_file.suffix == ".json"
                            ):
                                topic_info["message_count"] += 1
                                topic_info["size_bytes"] += message_file.stat().st_size

                        info["topics"].append(topic_info)
                        info["total_messages"] += topic_info["message_count"]
                        info["storage_size_bytes"] += topic_info["size_bytes"]

            return info

        except Exception as e:
            self.logger.error(f"Failed to get storage info: {str(e)}")
            return {"error": str(e)}

    def cleanup_old_messages(self, topic: str, max_age_days: int = 30) -> int:
        """
        Clean up old messages from a topic.

        Args:
            topic: Topic name to clean up
            max_age_days: Maximum age of messages to keep (in days)

        Returns:
            Number of messages deleted
        """
        try:
            topic_dir = self.storage_path / topic
            if not topic_dir.exists():
                return 0

            import time

            cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)
            deleted_count = 0

            for message_file in topic_dir.iterdir():
                if message_file.is_file() and message_file.suffix == ".json":
                    if message_file.stat().st_mtime < cutoff_time:
                        try:
                            message_file.unlink()
                            deleted_count += 1
                        except Exception as e:
                            self.logger.warning(
                                f"Failed to delete old message file {message_file}: {str(e)}"
                            )

            self.logger.info(
                f"Cleaned up {deleted_count} old messages from topic {topic}"
            )
            return deleted_count

        except Exception as e:
            self.logger.error(f"Failed to cleanup messages for topic {topic}: {str(e)}")
            return 0

    def get_provider(self):
        """Get the cloud provider type."""
        from agentmap.services.messaging.messaging_service import CloudProvider

        return CloudProvider.LOCAL
