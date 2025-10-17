"""
Interaction handling middleware for AgentMap.

This service provides infrastructure for managing human-in-the-loop interactions
by catching ExecutionInterruptedException, storing thread metadata, and coordinating
with CLI handlers for interaction display and resumption.

Uses pickle-based storage via FileStorageService to handle complex objects like
GraphBundle that contain non-JSON-serializable types (e.g., sets).
"""

import pickle
import time
from pathlib import Path
from typing import Any, Dict, Optional

from agentmap.exceptions.agent_exceptions import ExecutionInterruptedException
from agentmap.models.graph_bundle import GraphBundle
from agentmap.models.human_interaction import HumanInteractionRequest
from agentmap.services.logging_service import LoggingService
from agentmap.services.storage.system_manager import SystemStorageManager
from agentmap.services.storage.types import WriteMode


class InteractionHandlerService:
    """
    Service for managing human-in-the-loop interaction workflows.

    This service acts as middleware that:
    1. Catches ExecutionInterruptedException from graph execution
    2. Stores thread metadata and bundle context for resumption
    3. Persists interaction requests to storage
    4. Coordinates with CLI handlers for user interaction
    5. Manages interaction lifecycle (pending → responding → completed)
    """

    def __init__(
        self,
        system_storage_manager: SystemStorageManager,
        logging_service: LoggingService,
    ):
        """
        Initialize the interaction handler service.

        Args:
            system_storage_manager: System storage manager for file-based storage
            logging_service: Service for logging operations
        """
        self.logger = logging_service.get_class_logger(self)

        # Get file storage for interactions namespace
        # This creates: cache/interactions/ directory
        self.file_storage = system_storage_manager.get_file_storage("interactions")

        # Collection names for structured storage (subdirectories)
        self.requests_collection = "requests"
        self.threads_collection = "threads"
        self.responses_collection = "responses"

        self.logger.info(
            "[InteractionHandlerService] Initialized with pickle serialization"
        )

    def handle_execution_interruption(
        self,
        exception: ExecutionInterruptedException,
        bundle: Optional[GraphBundle] = None,
        bundle_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Handle execution interruption for suspend or human interaction.

        This method processes ExecutionInterruptedException by storing all necessary
        metadata. If interaction_request is present (HumanAgent), it stores and
        displays the interaction. If None (SuspendAgent), it only stores thread metadata.

        Args:
            exception: The ExecutionInterruptedException containing interaction data
            bundle: Optional GraphBundle for context extraction
            bundle_context: Optional bundle context metadata
        """
        interaction_request = exception.interaction_request
        thread_id = exception.thread_id
        checkpoint_data = exception.checkpoint_data

        self.logger.info(f"🔄 Handling execution interruption for thread: {thread_id}")

        try:
            # Check if this is a suspend-only interruption (no human interaction)
            if interaction_request is None:
                self.logger.debug(
                    f"Suspend-only interruption detected (no interaction_request) for thread: {thread_id}"
                )

                # For suspend-only, just store basic thread metadata
                self._store_thread_metadata_suspend_only(
                    thread_id=thread_id,
                    checkpoint_data=checkpoint_data,
                    bundle=bundle,
                    bundle_context=bundle_context,
                )

                self.logger.info(
                    f"✅ Suspend checkpoint stored for thread: {thread_id}"
                )
                return

            # Human interaction path (interaction_request is present)
            # Step 1: Store interaction request
            self._store_interaction_request(interaction_request)

            # Step 2: Create and store thread metadata with bundle context
            self._store_thread_metadata(
                thread_id=thread_id,
                interaction_request=interaction_request,
                checkpoint_data=checkpoint_data,
                bundle=bundle,
                bundle_context=bundle_context,
            )

            # Step 3: Display interaction using simple utility function
            from agentmap.deployment.cli.display_utils import (
                display_interaction_request,
            )

            display_interaction_request(interaction_request)

            self.logger.info(
                f"✅ Interaction stored and displayed for thread: {thread_id}"
            )

        except Exception as e:
            self.logger.error(
                f"❌ Failed to handle interaction for thread {thread_id}: {str(e)}"
            )
            raise RuntimeError(f"Interaction handling failed: {str(e)}") from e

    def _store_interaction_request(self, request: HumanInteractionRequest) -> None:
        """
        Store interaction request to persistent storage using pickle.

        Args:
            request: The human interaction request to store
        """
        request_data = {
            "id": str(request.id),
            "thread_id": request.thread_id,
            "node_name": request.node_name,
            "interaction_type": request.interaction_type.value,
            "prompt": request.prompt,
            "context": request.context or {},
            "options": request.options or [],
            "timeout_seconds": request.timeout_seconds,
            "created_at": request.created_at.isoformat(),
            "status": "pending",
        }

        # Serialize to pickle
        data_bytes = pickle.dumps(request_data)

        result = self._write_collection(
            collection=self.requests_collection,
            data=data_bytes,
            document_id=f"{request.id}.pkl",
            mode=WriteMode.WRITE,
            binary_mode=True,
        )

        if not result.success:
            raise RuntimeError(f"Failed to store interaction request: {result.error}")

        self.logger.debug(
            f"📝 Stored interaction request: {request.id} for thread: {request.thread_id}"
        )

    def _normalize_collection_name(self, collection: str) -> str:
        """Normalize storage collection to be relative to the base directory."""

        if not collection:
            return ""

        base_dir = str(self.file_storage.client.get("base_directory", ""))
        base_dir_normalized = base_dir.replace("\\", "/").rstrip("/")
        collection_normalized = str(collection).replace("\\", "/").strip("/")

        if base_dir_normalized and collection_normalized.startswith(
            base_dir_normalized
        ):
            remainder = collection_normalized[len(base_dir_normalized) :].lstrip("/")
            return remainder or ""

        return collection_normalized

    def _write_collection(self, collection: str, **kwargs):
        normalized_collection = self._normalize_collection_name(collection)
        return self.file_storage.write(collection=normalized_collection, **kwargs)

    def _read_collection(self, collection: str, **kwargs):
        normalized_collection = self._normalize_collection_name(collection)
        return self.file_storage.read(collection=normalized_collection, **kwargs)

    def _find_legacy_thread_file(self, thread_id: str) -> Optional[Path]:
        """Locate legacy-stored thread metadata files within the interactions namespace."""

        base_dir_value = self.file_storage.client.get("base_directory")
        if not base_dir_value:
            return None

        base_dir = Path(base_dir_value)
        expected_dir = base_dir / self._normalize_collection_name(
            self.threads_collection
        )
        expected_path = expected_dir / f"{thread_id}.pkl"
        if expected_path.exists():
            return expected_path

        if not base_dir.exists():
            return None

        for path in base_dir.rglob(f"{thread_id}.pkl"):
            if path != expected_path:
                return path

        return None

    def _store_thread_metadata_suspend_only(
        self,
        thread_id: str,
        checkpoint_data: Dict[str, Any],
        bundle: Optional[GraphBundle] = None,
        bundle_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Store thread metadata for suspend-only interruption (no human interaction).

        This is used by SuspendAgent which doesn't require user interaction
        but still needs to save checkpoint metadata for potential resumption.

        Args:
            thread_id: Thread ID for the execution
            checkpoint_data: Checkpoint data from the exception
            bundle: Optional GraphBundle for context extraction
            bundle_context: Optional bundle context metadata
        """
        # Extract bundle information for rehydration
        bundle_info = {}

        if bundle_context:
            bundle_info = bundle_context.copy()
        elif bundle:
            bundle_info = {
                "csv_hash": getattr(bundle, "csv_hash", None),
                "bundle_path": (
                    str(bundle.bundle_path)
                    if hasattr(bundle, "bundle_path") and bundle.bundle_path
                    else None
                ),
                "csv_path": (
                    str(bundle.csv_path)
                    if hasattr(bundle, "csv_path") and bundle.csv_path
                    else None
                ),
            }

        # Create thread metadata for suspend-only (no interaction request)
        # Get graph name from bundle, fallback to bundle_context, then checkpoint_data
        graph_name = "unknown"
        if bundle and hasattr(bundle, "graph_name"):
            graph_name = bundle.graph_name
        elif bundle_context and "graph_name" in bundle_context:
            graph_name = bundle_context["graph_name"]
        else:
            # Last resort: try checkpoint_data (but this is usually the node name)
            graph_name = checkpoint_data.get("graph_name", "unknown")

        thread_metadata = {
            "thread_id": thread_id,
            "graph_name": graph_name,
            "bundle_info": bundle_info,
            "node_name": checkpoint_data.get("node_name", "unknown"),
            "pending_interaction_id": None,  # No interaction for suspend-only
            "status": "suspended",  # Different status for suspend vs paused
            "created_at": time.time(),
            "checkpoint_data": {
                "inputs": checkpoint_data.get("inputs", {}),
                "agent_context": checkpoint_data.get("agent_context", {}),
                "execution_tracker": checkpoint_data.get("execution_tracker"),
            },
        }

        # Serialize to pickle
        data_bytes = pickle.dumps(thread_metadata)

        result = self._write_collection(
            collection=self.threads_collection,
            data=data_bytes,
            document_id=f"{thread_id}.pkl",
            mode=WriteMode.WRITE,
            binary_mode=True,
        )

        if not result.success:
            raise RuntimeError(
                f"Failed to store suspend thread metadata: {result.error}"
            )

        self.logger.debug(f"📝 Stored suspend-only thread metadata for: {thread_id}")

    def _store_thread_metadata(
        self,
        thread_id: str,
        interaction_request: HumanInteractionRequest,
        checkpoint_data: Dict[str, Any],
        bundle: Optional[GraphBundle] = None,
        bundle_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Store thread metadata with bundle context for resumption.

        Args:
            thread_id: Thread ID for the execution
            interaction_request: The interaction request
            checkpoint_data: Checkpoint data from the exception
            bundle: Optional GraphBundle for context extraction
            bundle_context: Optional bundle context metadata
        """
        # Extract bundle information for rehydration
        bundle_info = {}

        if bundle_context:
            # Use provided bundle context
            bundle_info = bundle_context.copy()
        elif bundle:
            # Extract from GraphBundle
            bundle_info = {
                "csv_hash": getattr(bundle, "csv_hash", None),
                "bundle_path": (
                    str(bundle.bundle_path)
                    if hasattr(bundle, "bundle_path") and bundle.bundle_path
                    else None
                ),
                "csv_path": (
                    str(bundle.csv_path)
                    if hasattr(bundle, "csv_path") and bundle.csv_path
                    else None
                ),
            }

        # Create thread metadata
        # Get graph name from bundle, fallback to bundle_context, then checkpoint_data
        graph_name = interaction_request.node_name  # Fallback to node name
        if bundle and hasattr(bundle, "graph_name"):
            graph_name = bundle.graph_name
        elif bundle_context and "graph_name" in bundle_context:
            graph_name = bundle_context["graph_name"]
        elif "graph_name" in checkpoint_data:
            graph_name = checkpoint_data["graph_name"]

        thread_metadata = {
            "thread_id": thread_id,
            "graph_name": graph_name,
            "bundle_info": bundle_info,
            "node_name": interaction_request.node_name,
            "pending_interaction_id": str(interaction_request.id),
            "status": "paused",
            "created_at": time.time(),
            "checkpoint_data": {
                "inputs": checkpoint_data.get("inputs", {}),
                "agent_context": checkpoint_data.get("agent_context", {}),
                "execution_tracker": checkpoint_data.get("execution_tracker"),
            },
        }

        # Serialize to pickle
        data_bytes = pickle.dumps(thread_metadata)

        result = self._write_collection(
            collection=self.threads_collection,
            data=data_bytes,
            document_id=f"{thread_id}.pkl",
            mode=WriteMode.WRITE,
            binary_mode=True,
        )

        if not result.success:
            raise RuntimeError(f"Failed to store thread metadata: {result.error}")

        self.logger.debug(
            f"📝 Stored thread metadata for: {thread_id} with bundle info: {bool(bundle_info)}"
        )

    def get_thread_metadata(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve thread metadata for resumption.

        Args:
            thread_id: Thread ID to lookup

        Returns:
            Thread metadata dictionary if found, None otherwise
        """
        try:
            file_data = self._read_collection(
                collection=self.threads_collection,
                document_id=f"{thread_id}.pkl",
                binary_mode=True,
            )

            if file_data:
                thread_data = pickle.loads(file_data)
                self.logger.debug(f"📖 Retrieved thread metadata for: {thread_id}")
                return thread_data

            # Fallback for legacy storage paths (nested collection names)
            legacy_file = self._find_legacy_thread_file(thread_id)
            if legacy_file is None:
                self.logger.warning(f"❌ No thread metadata found for: {thread_id}")
                return None

            with legacy_file.open("rb") as f:
                thread_data = pickle.load(f)

            self.logger.debug(
                f"📦 Migrating legacy thread metadata for {thread_id} from {legacy_file}"
            )

            # Rewrite to normalized location for future accesses
            self._write_collection(
                collection=self.threads_collection,
                data=pickle.dumps(thread_data),
                document_id=f"{thread_id}.pkl",
                mode=WriteMode.WRITE,
                binary_mode=True,
            )

            return thread_data

        except Exception as e:
            self.logger.error(
                f"❌ Failed to retrieve thread metadata for {thread_id}: {str(e)}"
            )
            return None

    def save_interaction_response(
        self,
        response_id: str,
        thread_id: str,
        action: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Save user interaction response to storage.

        Args:
            response_id: Unique response ID
            thread_id: Thread ID this response belongs to
            action: User action (approve, reject, choose, respond, edit)
            data: Optional additional response data

        Returns:
            True if save successful, False otherwise
        """
        try:
            response_data = {
                "response_id": response_id,
                "thread_id": thread_id,
                "action": action,
                "data": data or {},
                "timestamp": time.time(),
            }

            # Serialize to pickle
            data_bytes = pickle.dumps(response_data)

            result = self._write_collection(
                collection=self.responses_collection,
                data=data_bytes,
                document_id=f"{response_id}.pkl",
                mode=WriteMode.WRITE,
                binary_mode=True,
            )

            if result.success:
                self.logger.debug(
                    f"📝 Saved interaction response: {response_id} for thread: {thread_id}"
                )
                return True
            else:
                self.logger.error(
                    f"❌ Failed to save interaction response: {result.error}"
                )
                return False

        except Exception as e:
            self.logger.error(
                f"❌ Error saving interaction response {response_id}: {str(e)}"
            )
            return False

    def mark_thread_resuming(
        self, thread_id: str, last_response_id: Optional[str] = None
    ) -> bool:
        """
        Mark a thread as resuming after user response.

        Args:
            thread_id: Thread ID to update
            last_response_id: Optional response ID to record

        Returns:
            True if update successful, False otherwise
        """
        try:
            # Read existing thread metadata
            file_data = self._read_collection(
                collection=self.threads_collection,
                document_id=f"{thread_id}.pkl",
                binary_mode=True,
            )

            if not file_data:
                legacy_file = self._find_legacy_thread_file(thread_id)
                if not legacy_file:
                    self.logger.error(
                        f"❌ Cannot mark thread as resuming - thread not found: {thread_id}"
                    )
                    return False
                with legacy_file.open("rb") as f:
                    file_data = f.read()
                self.logger.debug(
                    f"📦 Migrating legacy thread metadata for resuming: {thread_id}"
                )

            # Deserialize, update, and reserialize
            thread_data = pickle.loads(file_data)
            thread_data["status"] = "resuming"
            thread_data["resumed_at"] = time.time()
            thread_data["pending_interaction_id"] = None

            if last_response_id:
                thread_data["last_response_id"] = last_response_id

            data_bytes = pickle.dumps(thread_data)

            result = self._write_collection(
                collection=self.threads_collection,
                data=data_bytes,
                document_id=f"{thread_id}.pkl",
                mode=WriteMode.WRITE,
                binary_mode=True,
            )

            if result.success:
                self.logger.debug(f"🔄 Marked thread as resuming: {thread_id}")
                return True
            else:
                self.logger.error(
                    f"❌ Failed to mark thread as resuming: {result.error}"
                )
                return False

        except Exception as e:
            self.logger.error(
                f"❌ Error marking thread as resuming {thread_id}: {str(e)}"
            )
            return False

    def mark_thread_completed(self, thread_id: str) -> bool:
        """
        Mark a thread as completed after successful resumption.

        Args:
            thread_id: Thread ID to update

        Returns:
            True if update successful, False otherwise
        """
        try:
            # Read existing thread metadata
            file_data = self._read_collection(
                collection=self.threads_collection,
                document_id=f"{thread_id}.pkl",
                binary_mode=True,
            )

            if not file_data:
                legacy_file = self._find_legacy_thread_file(thread_id)
                if not legacy_file:
                    self.logger.error(
                        f"❌ Cannot mark thread as completed - thread not found: {thread_id}"
                    )
                    return False
                with legacy_file.open("rb") as f:
                    file_data = f.read()
                self.logger.debug(
                    f"📦 Migrating legacy thread metadata for completion: {thread_id}"
                )

            # Deserialize, update, and reserialize
            thread_data = pickle.loads(file_data)
            thread_data["status"] = "completed"
            thread_data["completed_at"] = time.time()
            thread_data["pending_interaction_id"] = None

            data_bytes = pickle.dumps(thread_data)

            result = self._write_collection(
                collection=self.threads_collection,
                data=data_bytes,
                document_id=f"{thread_id}.pkl",
                mode=WriteMode.WRITE,
                binary_mode=True,
            )

            if result.success:
                self.logger.debug(f"✅ Marked thread as completed: {thread_id}")
                return True
            else:
                self.logger.error(
                    f"❌ Failed to mark thread as completed: {result.error}"
                )
                return False

        except Exception as e:
            self.logger.error(
                f"❌ Error marking thread as completed {thread_id}: {str(e)}"
            )
            return False

    def cleanup_expired_threads(self, max_age_hours: int = 24) -> int:
        """
        Clean up expired thread metadata.

        Args:
            max_age_hours: Maximum age in hours before cleanup

        Returns:
            Number of threads cleaned up
        """
        try:
            # This is a simplified cleanup - in a real implementation,
            # you'd query for threads older than max_age_hours
            self.logger.info(f"🧹 Thread cleanup triggered (max age: {max_age_hours}h)")
            # Implementation would depend on storage service capabilities
            return 0
        except Exception as e:
            self.logger.error(f"❌ Thread cleanup failed: {str(e)}")
            return 0

    def get_service_info(self) -> Dict[str, Any]:
        """
        Get service information for debugging.

        Returns:
            Dictionary with service status and configuration
        """
        return {
            "service": "InteractionHandlerService",
            "storage_type": "pickle",
            "storage_namespace": "interactions",
            "file_storage_available": self.file_storage.is_healthy(),
            "collections": {
                "requests": self.requests_collection,
                "threads": self.threads_collection,
                "responses": self.responses_collection,
            },
            "capabilities": {
                "exception_handling": True,
                "thread_metadata_storage": True,
                "bundle_context_preservation": True,
                "cli_interaction_display": True,
                "lifecycle_management": True,
                "cleanup_support": True,
                "handles_sets": True,
                "binary_storage": True,
            },
        }
