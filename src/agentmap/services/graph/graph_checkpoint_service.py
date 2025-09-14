"""
Graph checkpoint service for managing workflow execution checkpoints.

This service handles saving and loading execution checkpoints for graph workflows,
enabling pause/resume functionality for various scenarios like human intervention,
debugging, or long-running processes.

Now implements LangGraph's BaseCheckpointSaver for direct integration.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)

from agentmap.models.storage.types import StorageResult, WriteMode
from agentmap.services.logging_service import LoggingService
from agentmap.services.storage.json_service import JSONStorageService


class GraphCheckpointService(BaseCheckpointSaver):
    """Service for managing graph execution checkpoints with direct LangGraph integration."""

    def __init__(
        self,
        json_storage_service: JSONStorageService,
        logging_service: LoggingService,
    ):
        """
        Initialize the graph checkpoint service.

        Args:
            json_storage_service: JSON storage service for checkpoint persistence
            logging_service: Logging service for obtaining logger instances
        """
        super().__init__()
        self.storage = json_storage_service
        self.logger = logging_service.get_class_logger(self)
        self.checkpoint_collection = "langgraph_checkpoints"

    # ===== LangGraph BaseCheckpointSaver Implementation =====

    def put(
        self,
        config: Dict[str, Any],
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Save a checkpoint (LangGraph interface)."""
        thread_id = config["configurable"]["thread_id"]
        checkpoint_id = str(uuid4())

        checkpoint_doc = {
            "checkpoint_id": checkpoint_id,
            "thread_id": thread_id,
            "checkpoint_data": self._serialize_checkpoint(checkpoint),
            "metadata": self._serialize_metadata(metadata),
            "timestamp": datetime.utcnow().isoformat(),
            "version": "2.0",
            "new_versions": new_versions or {},
        }

        result = self.storage.write(
            collection=self.checkpoint_collection,
            data=checkpoint_doc,
            document_id=f"{thread_id}_{checkpoint_id}",
            mode=WriteMode.WRITE,
        )

        if result.success:
            self.logger.debug(
                f"LangGraph checkpoint saved: thread_id={thread_id}, checkpoint_id={checkpoint_id}"
            )
            return {"success": True, "checkpoint_id": checkpoint_id}
        else:
            raise Exception(f"Checkpoint save failed: {result.error}")

    def get_tuple(self, config: Dict[str, Any]) -> Optional[CheckpointTuple]:
        """Load the latest checkpoint for a thread (LangGraph interface)."""
        thread_id = config["configurable"]["thread_id"]

        checkpoints = self._get_thread_checkpoints(thread_id)
        if not checkpoints:
            return None

        latest = max(checkpoints, key=lambda x: x.get("timestamp", ""))

        checkpoint = self._deserialize_checkpoint(latest["checkpoint_data"])
        metadata = self._deserialize_metadata(latest["metadata"])

        return CheckpointTuple(
            config=config, checkpoint=checkpoint, metadata=metadata, parent_config=None
        )

    # ===== Helper Methods for LangGraph Integration =====

    def _serialize_checkpoint(self, checkpoint: Checkpoint) -> str:
        """Serialize checkpoint to JSON string."""
        serializable = {
            "channel_values": checkpoint.channel_values,
            "channel_versions": checkpoint.channel_versions,
            "versions_seen": checkpoint.versions_seen,
        }
        return json.dumps(serializable)

    def _deserialize_checkpoint(self, checkpoint_data: str) -> Checkpoint:
        """Deserialize checkpoint from JSON string."""
        data = json.loads(checkpoint_data)
        return Checkpoint(
            channel_values=data["channel_values"],
            channel_versions=data["channel_versions"],
            versions_seen=data["versions_seen"],
        )

    def _serialize_metadata(self, metadata: CheckpointMetadata) -> str:
        """Serialize metadata to JSON string."""
        return json.dumps(metadata)

    def _deserialize_metadata(self, metadata_data: str) -> CheckpointMetadata:
        """Deserialize metadata from JSON string."""
        return json.loads(metadata_data)

    def _get_thread_checkpoints(self, thread_id: str) -> List[Dict[str, Any]]:
        """Get all checkpoints for a thread."""
        try:
            # Query for all checkpoints with this thread_id
            query = {"thread_id": thread_id}
            results = self.storage.read(
                collection=self.checkpoint_collection,
                query=query,
            )

            if not results:
                return []

            # Convert to list if dict
            if isinstance(results, dict):
                return list(results.values())
            elif isinstance(results, list):
                return results
            else:
                return [results]

        except Exception as e:
            self.logger.error(f"Error getting thread checkpoints: {str(e)}")
            return []

    def get_service_info(self) -> Dict[str, Any]:
        """
        Get information about the service for debugging.

        Returns:
            Dictionary with service information
        """
        return {
            "service_name": "GraphCheckpointService",
            "langgraph_collection": self.checkpoint_collection,
            "storage_available": self.storage.is_healthy(),
            "capabilities": {
                # LangGraph capabilities
                "langgraph_put": True,
                "langgraph_get_tuple": True,
            },
            "implements_base_checkpoint_saver": True,
        }
