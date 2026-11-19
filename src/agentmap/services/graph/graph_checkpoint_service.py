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

import asyncio
import hashlib
import pickle
from datetime import datetime
from typing import Any, Dict, Optional, Sequence, Tuple
from uuid import uuid4

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    WRITES_IDX_MAP,
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)

from agentmap.models.storage.types import WriteMode
from agentmap.services.logging_service import LoggingService
from agentmap.services.storage.system_manager import SystemStorageManager


class GraphCheckpointService(BaseCheckpointSaver[Any]):
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
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """Save a checkpoint (LangGraph interface)."""
        configurable = config["configurable"]
        thread_id = configurable["thread_id"]
        checkpoint_id = str(checkpoint.get("id") or uuid4())
        checkpoint_ns = configurable.get("checkpoint_ns", "")

        try:
            # NOTE: LangGraph sometimes creates checkpoints with sets in versions_seen.
            # The serde (JsonPlusSerializer) can handle this, but we need to make a copy
            # first to avoid modifying the original checkpoint passed by LangGraph.
            checkpoint_copy = {**checkpoint, "id": checkpoint_id}

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
                "checkpoint_id": checkpoint_id,
                "parent_checkpoint_id": configurable.get("checkpoint_id"),
                "checkpoint_ns": checkpoint_ns,
                "new_versions": new_versions,
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

            if not result.success:
                raise RuntimeError(f"Checkpoint save failed: {result.error}")

            self.logger.debug(
                f"Checkpoint saved: thread={thread_id}, id={checkpoint_id}, "
                f"size={len(document_bytes)} bytes"
            )

        except Exception as e:
            error_msg = f"Failed to save checkpoint: {str(e)}"
            self.logger.error(error_msg)
            raise RuntimeError(error_msg) from e

        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        }

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """Load the latest checkpoint for a thread (LangGraph interface)."""
        configurable = config["configurable"]
        thread_id = configurable["thread_id"]
        checkpoint_ns = configurable.get("checkpoint_ns", "")
        requested_checkpoint_id = configurable.get("checkpoint_id")
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
            if requested_checkpoint_id:
                requested_filename = f"{thread_id}_{requested_checkpoint_id}.pkl"
                thread_files = [
                    filename
                    for filename in thread_files
                    if filename == requested_filename
                ]

            if not thread_files:
                self.logger.debug(f"no files found for thread {thread_id}")
                return None

            # Find the latest checkpoint file
            # We need to get file metadata to sort by timestamp
            latest_file: Optional[Dict[str, Any]] = None
            latest_timestamp: Optional[str] = None

            for filename in thread_files:
                try:
                    file_data = self.file_storage.read(
                        collection="", document_id=filename, binary_mode=True
                    )
                    if not file_data:
                        continue

                    checkpoint_doc = pickle.loads(file_data)
                    if not isinstance(checkpoint_doc, dict):
                        continue
                    checkpoint_id = checkpoint_doc.get("checkpoint_id")
                    if (
                        not isinstance(checkpoint_id, str)
                        or filename != f"{thread_id}_{checkpoint_id}.pkl"
                        or checkpoint_doc.get("checkpoint_ns", "") != checkpoint_ns
                    ):
                        continue
                    timestamp = str(checkpoint_doc.get("timestamp", ""))

                    # Use >= to prefer later files when timestamps are identical
                    # (files are in insertion order, so later = more recent)
                    if latest_timestamp is None or timestamp >= latest_timestamp:
                        latest_timestamp = timestamp
                        latest_file = checkpoint_doc
                except Exception as e:
                    self.logger.warning(
                        f"Skipping malformed checkpoint for thread={thread_id}, "
                        f"file={filename}: {e}"
                    )

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

            checkpoint_id = latest_file.get("checkpoint_id")
            pending_writes = (
                self._load_pending_writes(thread_id, checkpoint_ns, checkpoint_id)
                if isinstance(checkpoint_id, str) and checkpoint_id
                else []
            )

            return CheckpointTuple(
                config={
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": latest_file.get("checkpoint_id", ""),
                    }
                },
                checkpoint=checkpoint,
                metadata=metadata,
                parent_config=(
                    {
                        "configurable": {
                            "thread_id": thread_id,
                            "checkpoint_ns": checkpoint_ns,
                            "checkpoint_id": latest_file["parent_checkpoint_id"],
                        }
                    }
                    if latest_file.get("parent_checkpoint_id")
                    else None
                ),
                pending_writes=pending_writes,
            )

        except Exception as e:
            self.logger.error(
                f"Failed to load checkpoint for thread {thread_id}: {str(e)}"
            )
            return None

    @staticmethod
    def _writes_collection(
        thread_id: str, checkpoint_ns: str, checkpoint_id: str
    ) -> str:
        identity = "\0".join((thread_id, checkpoint_ns, checkpoint_id))
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        return f"writes/{digest}"

    def _load_pending_writes(
        self, thread_id: str, checkpoint_ns: str, checkpoint_id: str
    ) -> list[tuple[str, str, Any]]:
        collection = self._writes_collection(thread_id, checkpoint_ns, checkpoint_id)
        filenames = self.file_storage.read(collection=collection) or []
        if not isinstance(filenames, (list, tuple)):
            return []

        task_writes: Dict[str, list[tuple[str, Any]]] = {}
        for filename in filenames:
            if not isinstance(filename, str):
                continue
            try:
                document_bytes = self.file_storage.read(
                    collection=collection, document_id=filename, binary_mode=True
                )
                if not document_bytes:
                    continue
                writes_doc = pickle.loads(document_bytes)
                if (
                    not isinstance(writes_doc, dict)
                    or writes_doc.get("thread_id") != thread_id
                    or writes_doc.get("checkpoint_ns", "") != checkpoint_ns
                    or writes_doc.get("checkpoint_id") != checkpoint_id
                ):
                    continue
                task_id = writes_doc.get("task_id")
                writes_typed = writes_doc.get("writes")
                if not isinstance(task_id, str) or writes_typed is None:
                    continue
                writes = self.serde.loads_typed(writes_typed)
                if not isinstance(writes, list):
                    continue

                valid_writes = []
                for item in writes:
                    if not isinstance(item, (list, tuple)) or len(item) != 2:
                        continue
                    channel, value = item
                    if isinstance(channel, str):
                        valid_writes.append((channel, value))
                task_writes[task_id] = valid_writes
            except Exception as e:
                self.logger.warning(
                    f"Skipping malformed pending writes for thread={thread_id}, "
                    f"checkpoint={checkpoint_id}, file={filename}: {e}"
                )

        return [
            (task_id, channel, value)
            for task_id in sorted(task_writes)
            for channel, value in task_writes[task_id]
        ]

    def put_writes(
        self,
        config: RunnableConfig,
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
        configurable = config["configurable"]
        thread_id = configurable["thread_id"]
        checkpoint_ns = configurable.get("checkpoint_ns", "")
        checkpoint_id = configurable.get("checkpoint_id")

        try:
            if not isinstance(checkpoint_id, str) or not checkpoint_id:
                raise ValueError("Pending writes require a checkpoint_id")
            if not isinstance(checkpoint_ns, str):
                raise ValueError("checkpoint_ns must be a string")

            collection = self._writes_collection(
                thread_id, checkpoint_ns, checkpoint_id
            )
            task_digest = hashlib.sha256(task_id.encode("utf-8")).hexdigest()
            document_id = f"{task_digest}.pkl"
            writes_by_index: Dict[int, Tuple[str, Any]] = {}

            if self.file_storage.exists(collection=collection, document_id=document_id):
                existing_bytes = self.file_storage.read(
                    collection=collection,
                    document_id=document_id,
                    binary_mode=True,
                )
                if existing_bytes:
                    existing_doc = pickle.loads(existing_bytes)
                    if isinstance(existing_doc, dict):
                        existing_writes = self.serde.loads_typed(existing_doc["writes"])
                        for index, (channel, value) in enumerate(existing_writes):
                            write_index = WRITES_IDX_MAP.get(channel, index)
                            writes_by_index[write_index] = (channel, value)

            for index, (channel, value) in enumerate(writes):
                write_index = WRITES_IDX_MAP.get(channel, index)
                if write_index >= 0 and write_index in writes_by_index:
                    continue
                writes_by_index[write_index] = (channel, value)

            writes_doc = {
                "writes": self.serde.dumps_typed(list(writes_by_index.values())),
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
                "task_id": task_id,
                "task_path": task_path,
                "timestamp": datetime.utcnow().isoformat(),
                "version": "2.0",
            }
            document_bytes = pickle.dumps(writes_doc)

            result = self.file_storage.write(
                collection=collection,
                data=document_bytes,
                document_id=document_id,
                mode=WriteMode.WRITE,
                binary_mode=True,
            )

            if result.success:
                self.logger.debug(
                    f"Writes saved: thread={thread_id}, task={task_id}, "
                    f"checkpoint={checkpoint_id}, count={len(writes_by_index)}"
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

    # ===== Async LangGraph interface (T-E04-F04-004) =====
    # LangGraph's ainvoke() calls aget_tuple / aput / aput_writes.
    # BaseCheckpointSaver raises NotImplementedError for all three.
    # We delegate to the sync variants via asyncio.to_thread so the file I/O
    # stays off the event loop without blocking it.

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """Async variant of get_tuple. Delegates via worker-thread seam."""
        return await asyncio.to_thread(self.get_tuple, config)

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """Async variant of put. Delegates via worker-thread seam."""
        return await asyncio.to_thread(
            self.put, config, checkpoint, metadata, new_versions
        )

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[Tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        """Async variant of put_writes. Delegates via worker-thread seam."""
        await asyncio.to_thread(self.put_writes, config, writes, task_id, task_path)

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
