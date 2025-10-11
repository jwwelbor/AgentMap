"""
Graph checkpoint service for managing workflow execution checkpoints.

This service handles saving and loading execution checkpoints for graph workflows,
enabling pause/resume functionality for various scenarios like human intervention,
debugging, or long-running processes.

Now implements LangGraph's BaseCheckpointSaver for direct integration.

Uses SystemStorageManager with FileStorageService for binary pickle storage
in cache/checkpoints/ namespace. This avoids magic strings and follows
AgentMap's centralized path management patterns.
"""

import pickle
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4

from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)

from agentmap.models.storage.types import StorageResult, WriteMode
from agentmap.services.logging_service import LoggingService
from agentmap.services.storage.system_manager import SystemStorageManager


class GraphCheckpointService(BaseCheckpointSaver):
    """Service for managing graph execution checkpoints with pickle serialization."""

    def __init__(
        self,
        system_storage_manager: SystemStorageManager,
        logging_service: LoggingService,
    ):
        """
        Initialize the graph checkpoint service.

        Args:
            system_storage_manager: System storage manager for checkpoint file storage
            logging_service: Logging service for obtaining logger instances
        """
        super().__init__()
        self.logger = logging_service.get_class_logger(self)

        # Get file storage for checkpoints namespace
        # This creates: cache/checkpoints/ directory
        self.file_storage = system_storage_manager.get_file_storage("checkpoints")

        self.logger.info("[GraphCheckpointService] Initialized with pickle serialization")

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

        try:
            # Serialize checkpoint to pickle bytes
            checkpoint_bytes = self._serialize_checkpoint(checkpoint)

            # Serialize metadata to pickle bytes
            metadata_bytes = self._serialize_metadata(metadata)

            # Create checkpoint document
            checkpoint_doc = {
                "checkpoint": checkpoint_bytes,
                "metadata": metadata_bytes,
                "timestamp": datetime.utcnow().isoformat(),
                "version": "2.0",
                "new_versions": new_versions or {},
            }

            # Serialize entire document
            document_bytes = pickle.dumps(checkpoint_doc)

            # Save to file storage
            # collection="" means use namespace root (checkpoints/)
            # document_id is the filename
            result = self.file_storage.write(
                collection="",  # Use namespace root
                data=document_bytes,
                document_id=f"{thread_id}_{checkpoint_id}.pkl",
                mode=WriteMode.WRITE,
                binary_mode=True,
            )

            if result.success:
                self.logger.debug(
                    f"Checkpoint saved: thread={thread_id}, id={checkpoint_id}, "
                    f"size={len(document_bytes)} bytes"
                )
                return {"success": True, "checkpoint_id": checkpoint_id}
            else:
                raise Exception(f"Checkpoint save failed: {result.error}")

        except Exception as e:
            error_msg = f"Failed to save checkpoint: {str(e)}"
            self.logger.error(error_msg)
            return {"success": False, "error": error_msg}

    def get_tuple(self, config: Dict[str, Any]) -> Optional[CheckpointTuple]:
        """Load the latest checkpoint for a thread (LangGraph interface)."""
        thread_id = config["configurable"]["thread_id"]

        try:
            # List all checkpoint files for this thread
            # FileStorageService.read() with no document_id lists files
            files = self.file_storage.read(collection="")

            if not files:
                return None

            # Filter files by thread_id prefix
            thread_files = [f for f in files if f.startswith(f"{thread_id}_")]

            if not thread_files:
                return None

            # Find the latest checkpoint file
            # We need to get file metadata to sort by timestamp
            latest_file = None
            latest_timestamp = None

            for filename in thread_files:
                # Read the file
                file_data = self.file_storage.read(
                    collection="", document_id=filename, binary_mode=True
                )

                if file_data:
                    # Deserialize document
                    checkpoint_doc = pickle.loads(file_data)
                    timestamp = checkpoint_doc.get("timestamp", "")

                    if latest_timestamp is None or timestamp > latest_timestamp:
                        latest_timestamp = timestamp
                        latest_file = checkpoint_doc

            if not latest_file:
                return None

            # Deserialize checkpoint and metadata
            checkpoint = self._deserialize_checkpoint(latest_file["checkpoint"])
            metadata = self._deserialize_metadata(latest_file["metadata"])

            return CheckpointTuple(
                config=config,
                checkpoint=checkpoint,
                metadata=metadata,
                parent_config=None,
            )

        except Exception as e:
            self.logger.error(f"Failed to load checkpoint for thread {thread_id}: {str(e)}")
            return None

    # ===== Helper Methods for Pickle Serialization =====

    def _serialize_checkpoint(self, checkpoint: Checkpoint) -> bytes:
        """Serialize checkpoint using pickle.

        Args:
            checkpoint: LangGraph Checkpoint (TypedDict/dict with channel_values,
                       channel_versions, versions_seen)

        Returns:
            Binary pickle data
        """
        return pickle.dumps(checkpoint)

    def _deserialize_checkpoint(self, data: bytes) -> Checkpoint:
        """Deserialize checkpoint from pickle.

        Args:
            data: Binary pickle data

        Returns:
            Checkpoint dict
        """
        return pickle.loads(data)

    def _serialize_metadata(self, metadata: CheckpointMetadata) -> bytes:
        """Serialize metadata using pickle."""
        return pickle.dumps(metadata)

    def _deserialize_metadata(self, data: bytes) -> CheckpointMetadata:
        """Deserialize metadata from pickle."""
        return pickle.loads(data)

    # ===== GraphCheckpointServiceProtocol Implementation =====

    def save_checkpoint(
        self,
        thread_id: str,
        node_name: str,
        checkpoint_type: str,
        metadata: Dict[str, Any],
        execution_state: Dict[str, Any],
    ) -> StorageResult:
        """
        Save a checkpoint using the protocol interface.

        Maps simple protocol parameters to LangGraph's checkpoint format.

        Args:
            thread_id: Unique identifier for the execution thread
            node_name: Name of the node where checkpoint occurs
            checkpoint_type: Type of checkpoint (e.g., "suspend", "human_interaction")
            metadata: Type-specific metadata
            execution_state: Current execution state data

        Returns:
            StorageResult indicating success/failure
        """
        try:
            # Create LangGraph config
            config = {"configurable": {"thread_id": thread_id}}

            # Map execution_state to LangGraph checkpoint format
            # The execution_state becomes the channel_values in LangGraph
            checkpoint = Checkpoint(
                channel_values=execution_state,
                channel_versions={"execution_state": 1},
                versions_seen={"execution_state": 1},
            )

            # Combine protocol metadata with checkpoint-specific metadata
            combined_metadata = {
                "node_name": node_name,
                "checkpoint_type": checkpoint_type,
                "protocol_version": "1.0",
                **metadata,
            }

            # Use the LangGraph interface
            result = self.put(config, checkpoint, combined_metadata)

            if result.get("success"):
                self.logger.info(
                    f"Protocol checkpoint saved: thread_id={thread_id}, "
                    f"node={node_name}, type={checkpoint_type}"
                )
                return StorageResult(
                    success=True,
                    data={"checkpoint_id": result["checkpoint_id"]},
                    error=None,
                )
            else:
                return StorageResult(
                    success=False, data=None, error="LangGraph put() returned failure"
                )

        except Exception as e:
            error_msg = f"Failed to save checkpoint: {str(e)}"
            self.logger.error(error_msg)
            return StorageResult(success=False, data=None, error=error_msg)

    def load_checkpoint(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """
        Load the latest checkpoint for a thread using the protocol interface.

        Args:
            thread_id: Thread ID to load checkpoint for

        Returns:
            Checkpoint data or None if not found
        """
        try:
            config = {"configurable": {"thread_id": thread_id}}
            tuple_result = self.get_tuple(config)

            if tuple_result is None:
                self.logger.debug(f"No checkpoint found for thread_id={thread_id}")
                return None

            # Extract the execution state from channel_values
            # Note: Checkpoint is a TypedDict (dict), so use dict access
            execution_state = tuple_result.checkpoint["channel_values"]

            # Combine checkpoint data with metadata for protocol consumers
            checkpoint_data = {
                "thread_id": thread_id,
                "execution_state": execution_state,
                "metadata": tuple_result.metadata,
                "config": tuple_result.config,
                "channel_versions": tuple_result.checkpoint["channel_versions"],
                "versions_seen": tuple_result.checkpoint["versions_seen"],
            }

            self.logger.debug(f"Loaded checkpoint for thread_id={thread_id}")
            return checkpoint_data

        except Exception as e:
            error_msg = f"Failed to load checkpoint for thread_id={thread_id}: {str(e)}"
            self.logger.error(error_msg)
            return None

    def get_service_info(self) -> Dict[str, Any]:
        """
        Get information about the service for debugging.

        Returns:
            Dictionary with service information
        """
        return {
            "service_name": "GraphCheckpointService",
            "storage_type": "pickle",
            "storage_namespace": "checkpoints",
            "storage_available": self.file_storage.is_healthy(),
            "capabilities": {
                # LangGraph capabilities
                "langgraph_put": True,
                "langgraph_get_tuple": True,
                # Protocol capabilities
                "protocol_save_checkpoint": True,
                "protocol_load_checkpoint": True,
                # Serialization
                "handles_sets": True,
                "binary_storage": True,
            },
            "implements_base_checkpoint_saver": True,
            "implements_protocol": True,
        }
