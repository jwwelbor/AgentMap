"""
Interaction handling middleware for AgentMap.

This service provides infrastructure for managing human-in-the-loop interactions
by catching ExecutionInterruptedException, storing thread metadata, and coordinating
with CLI handlers for interaction display and resumption.
"""

import time
from typing import Any, Dict, Optional

from agentmap.deployment.cli.cli_handler import CLIInteractionHandler
from agentmap.exceptions.agent_exceptions import ExecutionInterruptedException
from agentmap.models.graph_bundle import GraphBundle
from agentmap.models.human_interaction import HumanInteractionRequest
from agentmap.services.logging_service import LoggingService
from agentmap.services.storage.protocols import StorageService
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
        storage_service: StorageService,
        cli_handler: CLIInteractionHandler,
        logging_service: LoggingService,
    ):
        """
        Initialize the interaction handler service.

        Args:
            storage_service: Storage service for persisting interaction data
            cli_handler: CLI handler for displaying interactions to users
            logging_service: Service for logging operations
        """
        self.storage_service = storage_service
        self.cli_handler = cli_handler
        self.logger = logging_service.get_class_logger(self)

        # Collection names for structured storage
        self.interactions_collection = "interactions"
        self.threads_collection = "interactions_threads"
        self.responses_collection = "interactions_responses"

    def handle_execution_interruption(
        self,
        exception: ExecutionInterruptedException,
        bundle: Optional[GraphBundle] = None,
        bundle_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Handle execution interruption for human interaction.

        This method processes ExecutionInterruptedException by storing all necessary
        metadata and displaying the interaction request to the user.

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

            # Step 3: Display interaction to user via CLI
            self.cli_handler.display_interaction_request(interaction_request)

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
        Store interaction request to persistent storage.

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

        result = self.storage_service.write(
            collection=self.interactions_collection,
            data=request_data,
            document_id=str(request.id),
            mode=WriteMode.WRITE,
        )

        if not result.success:
            raise RuntimeError(f"Failed to store interaction request: {result.error}")

        self.logger.debug(
            f"📝 Stored interaction request: {request.id} for thread: {request.thread_id}"
        )

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
        thread_metadata = {
            "thread_id": thread_id,
            "graph_name": checkpoint_data.get("node_name")
            or interaction_request.node_name,
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

        result = self.storage_service.write(
            collection=self.threads_collection,
            data=thread_metadata,
            document_id=thread_id,
            mode=WriteMode.WRITE,
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
            thread_data = self.storage_service.read(
                collection=self.threads_collection, document_id=thread_id
            )

            if thread_data:
                self.logger.debug(f"📖 Retrieved thread metadata for: {thread_id}")
                return thread_data
            else:
                self.logger.warning(f"❌ No thread metadata found for: {thread_id}")
                return None

        except Exception as e:
            self.logger.error(
                f"❌ Failed to retrieve thread metadata for {thread_id}: {str(e)}"
            )
            return None

    def mark_thread_resuming(self, thread_id: str) -> bool:
        """
        Mark a thread as resuming after user response.

        Args:
            thread_id: Thread ID to update

        Returns:
            True if update successful, False otherwise
        """
        try:
            result = self.storage_service.write(
                collection=self.threads_collection,
                data={
                    "status": "resuming",
                    "resumed_at": time.time(),
                },
                document_id=thread_id,
                mode=WriteMode.UPDATE,
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
            result = self.storage_service.write(
                collection=self.threads_collection,
                data={
                    "status": "completed",
                    "completed_at": time.time(),
                    "pending_interaction_id": None,
                },
                document_id=thread_id,
                mode=WriteMode.UPDATE,
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
            "storage_service_available": self.storage_service is not None,
            "cli_handler_available": self.cli_handler is not None,
            "collections": {
                "interactions": self.interactions_collection,
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
            },
        }
