"""
Graph checkpoint service for managing workflow execution checkpoints.

This service handles saving and loading execution checkpoints for graph workflows,
enabling pause/resume functionality for various scenarios like human intervention,
debugging, or long-running processes.

Implements LangGraph's BaseCheckpointSaver for direct integration. Uses LangGraph's
serde (JsonPlusSerializer) for checkpoint serialization, which properly handles
complex Python types (sets, dates, UUIDs, etc.) through msgpack/JSON encoding.

Storage: Uses SystemStorageManager with FileStorageService for file-based storage
in cache/checkpoints/ namespace. Checkpoint documents are pickled for fast I/O.
"""

import pickle
from datetime import datetime
from typing import Any, Dict, Optional, Sequence, Tuple
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

        self.logger.info(
            "[GraphCheckpointService] Initialized with serde-based serialization"
        )

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
            # NOTE: LangGraph sometimes creates checkpoints with sets in versions_seen.
            # The serde (JsonPlusSerializer) can handle this, but we need to make a copy
            # first to avoid modifying the original checkpoint passed by LangGraph.
            checkpoint_copy = {**checkpoint}

            # Convert sets to lists in versions_seen for proper serialization
            if "versions_seen" in checkpoint_copy:
                versions_seen = checkpoint_copy["versions_seen"]
                if isinstance(versions_seen, dict):
                    checkpoint_copy["versions_seen"] = {
                        k: list(v) if isinstance(v, set) else v
                        for k, v in versions_seen.items()
                    }

            # Use serde to serialize checkpoint (LangGraph way)
            # This handles complex types properly
            checkpoint_typed = self.serde.dumps_typed(checkpoint_copy)

            # Use serde to serialize metadata
            metadata_typed = self.serde.dumps_typed(metadata)

            # Create checkpoint document
            checkpoint_doc = {
                "checkpoint": checkpoint_typed,  # tuple[str, bytes] from dumps_typed
                "metadata": metadata_typed,  # tuple[str, bytes] from dumps_typed
                "timestamp": datetime.utcnow().isoformat(),
                "version": "2.0",
                "new_versions": new_versions or {},
            }

            # Serialize entire document with pickle
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
        self.logger.trace(f"Loading checkpoint for thread {thread_id}")

        try:
            # List all checkpoint files for this thread
            # FileStorageService.read() with no document_id lists files
            files = self.file_storage.read(collection="")

            if not files:
                self.logger.trace(f"no files found for thread {thread_id}")
                return None

            # Filter files by thread_id prefix
            thread_files = [f for f in files if f.startswith(f"{thread_id}_")]

            if not thread_files:
                self.logger.debug(f"no files found for thread {thread_id}")
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

                    # Use >= to prefer later files when timestamps are identical
                    # (files are in insertion order, so later = more recent)
                    if latest_timestamp is None or timestamp >= latest_timestamp:
                        latest_timestamp = timestamp
                        latest_file = checkpoint_doc

            if not latest_file:
                self.logger.debug(f"no files found for thread {thread_id}")
                return None

            # Deserialize checkpoint and metadata using serde (LangGraph way)
            checkpoint = self.serde.loads_typed(latest_file["checkpoint"])
            metadata = self.serde.loads_typed(latest_file["metadata"])

            self.logger.trace(f"Loaded checkpoint for thread {thread_id}: {checkpoint}")
            self.logger.trace(f"Loaded metadata for thread {thread_id}: {metadata}")

            # NOTE: After deserialization, serde may reconstruct sets from tuples.
            # We need to convert them back to lists for JSON compatibility when
            # LangGraph uses the checkpoint internally.
            if "versions_seen" in checkpoint:
                versions_seen = checkpoint["versions_seen"]
                if isinstance(versions_seen, dict):
                    checkpoint["versions_seen"] = {
                        k: list(v) if isinstance(v, set) else v
                        for k, v in versions_seen.items()
                    }

            return CheckpointTuple(
                config=config,
                checkpoint=checkpoint,
                metadata=metadata,
                parent_config=None,
            )

        except Exception as e:
            self.logger.error(
                f"Failed to load checkpoint for thread {thread_id}: {str(e)}"
            )
            return None

    def put_writes(
        self,
        config: Dict[str, Any],
        writes: Sequence[Tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        """
        Store intermediate writes linked to a checkpoint (LangGraph interface).

        This method is called by LangGraph to store intermediate state updates
        (writes) that occur during graph execution, before they're committed
        to the checkpoint.

        Args:
            config: Configuration containing thread_id for correlation
            writes: List of (channel, value) tuples representing state updates
            task_id: Identifier for the task creating the writes
            task_path: Path of the task creating the writes (optional)
        """
        thread_id = config["configurable"]["thread_id"]

        try:
            # Serialize writes using serde (handles complex types)
            writes_typed = self.serde.dumps_typed(list(writes))

            # Create writes document
            writes_doc = {
                "writes": writes_typed,  # tuple[str, bytes] from dumps_typed
                "task_id": task_id,
                "task_path": task_path,
                "timestamp": datetime.utcnow().isoformat(),
                "version": "2.0",
            }

            # Serialize document with pickle
            document_bytes = pickle.dumps(writes_doc)

            # Generate unique ID for this writes batch
            writes_id = str(uuid4())

            # Save to file storage in writes subdirectory
            # Uses pattern: <thread_id>_writes_<writes_id>.pkl
            result = self.file_storage.write(
                collection="writes",  # Subdirectory for writes
                data=document_bytes,
                document_id=f"{thread_id}_writes_{writes_id}.pkl",
                mode=WriteMode.WRITE,
                binary_mode=True,
            )

            if result.success:
                self.logger.debug(
                    f"Writes saved: thread={thread_id}, task={task_id}, "
                    f"writes_id={writes_id}, count={len(writes)}"
                )
            else:
                self.logger.error(
                    f"Failed to save writes: thread={thread_id}, "
                    f"error={result.error}"
                )

        except Exception as e:
            # Log error but don't raise - LangGraph expects this to be resilient
            self.logger.error(
                f"Error saving writes for thread {thread_id}, "
                f"task {task_id}: {str(e)}"
            )

    # Note: We use self.serde (JsonPlusSerializer by default from BaseCheckpointSaver)
    # for all serialization/deserialization. This handles sets and other complex
    # types properly through dumps_typed/loads_typed methods.

    # ===== GraphCheckpointServiceProtocol Implementation =====

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
            "storage_available": self.file_storage is not None,
            "capabilities": {
                # LangGraph capabilities
                "langgraph_put": True,
                "langgraph_get_tuple": True,
                "langgraph_put_writes": True,
                # Serialization
                "handles_sets": True,
                "binary_storage": True,
            },
            "implements_base_checkpoint_saver": True,
        }
