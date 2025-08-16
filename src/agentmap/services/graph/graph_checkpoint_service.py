"""
Graph checkpoint service for managing workflow execution checkpoints.

This service handles saving and loading execution checkpoints for graph workflows,
enabling pause/resume functionality for various scenarios like human intervention,
debugging, or long-running processes.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from agentmap.models.storage.types import StorageResult, WriteMode
from agentmap.services.logging_service import LoggingService
from agentmap.services.storage.json_service import JSONStorageService


class GraphCheckpointService:
    """Service for managing graph execution checkpoints."""

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
        self.storage = json_storage_service
        self.logger = logging_service.get_class_logger(self)
        self.checkpoint_collection = "graph_checkpoints"

    def save_checkpoint(
        self,
        thread_id: str,
        node_name: str,
        checkpoint_type: str,
        metadata: Dict[str, Any],
        execution_state: Dict[str, Any],
    ) -> StorageResult:
        """
        Save a graph execution checkpoint.

        Args:
            thread_id: Unique identifier for the execution thread
            node_name: Name of the node where checkpoint occurs
            checkpoint_type: Type of checkpoint (e.g., "human_intervention", "debug", "scheduled")
            metadata: Type-specific metadata (e.g., interaction request for human intervention)
            execution_state: Current execution state data

        Returns:
            StorageResult indicating success or failure
        """
        try:
            checkpoint_doc = {
                "thread_id": thread_id,
                "node_name": node_name,
                "checkpoint_type": checkpoint_type,
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": metadata,
                "execution_state": execution_state,
                "version": "1.0",  # For future compatibility
            }

            result = self.storage.write(
                collection=self.checkpoint_collection,
                data=checkpoint_doc,
                document_id=thread_id,
                mode=WriteMode.WRITE,
            )

            if result.success:
                self.logger.info(
                    f"Checkpoint saved: thread_id={thread_id}, type={checkpoint_type}, node={node_name}"
                )
            else:
                self.logger.error(f"Failed to save checkpoint: {result.error}")

            return result

        except Exception as e:
            error_msg = f"Error saving checkpoint: {str(e)}"
            self.logger.error(error_msg)
            return StorageResult(
                success=False,
                error=error_msg,
                operation="save_checkpoint",
                collection=self.checkpoint_collection,
            )

    def load_checkpoint(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """
        Load the latest checkpoint for a thread.

        Args:
            thread_id: Thread ID to load checkpoint for

        Returns:
            Checkpoint data or None if not found
        """
        try:
            checkpoint = self.storage.read(
                collection=self.checkpoint_collection,
                document_id=thread_id,
            )

            if checkpoint:
                self.logger.info(f"Checkpoint loaded for thread_id={thread_id}")
                return checkpoint
            else:
                self.logger.debug(f"No checkpoint found for thread_id={thread_id}")
                return None

        except Exception as e:
            self.logger.error(f"Error loading checkpoint: {str(e)}")
            return None

    def list_checkpoints(
        self,
        checkpoint_type: Optional[str] = None,
        thread_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        List checkpoints with optional filtering.

        Args:
            checkpoint_type: Filter by checkpoint type
            thread_id: Filter by thread ID
            limit: Maximum number of checkpoints to return

        Returns:
            List of checkpoint summaries
        """
        try:
            # Build query
            query = {"limit": limit}
            if checkpoint_type:
                query["checkpoint_type"] = checkpoint_type
            if thread_id:
                query["thread_id"] = thread_id

            # Read all checkpoints with query
            checkpoints = self.storage.read(
                collection=self.checkpoint_collection,
                query=query,
            )

            if not checkpoints:
                return []

            # Convert to list if dict
            if isinstance(checkpoints, dict):
                checkpoints = list(checkpoints.values())
            elif not isinstance(checkpoints, list):
                checkpoints = [checkpoints]

            # Sort by timestamp (newest first)
            checkpoints.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

            # Return summary info
            summaries = []
            for cp in checkpoints:
                summaries.append(
                    {
                        "thread_id": cp.get("thread_id"),
                        "node_name": cp.get("node_name"),
                        "checkpoint_type": cp.get("checkpoint_type"),
                        "timestamp": cp.get("timestamp"),
                        "has_metadata": bool(cp.get("metadata")),
                        "has_execution_state": bool(cp.get("execution_state")),
                    }
                )

            return summaries

        except Exception as e:
            self.logger.error(f"Error listing checkpoints: {str(e)}")
            return []

    def delete_checkpoint(self, thread_id: str) -> StorageResult:
        """
        Delete a checkpoint by thread ID.

        Args:
            thread_id: Thread ID of checkpoint to delete

        Returns:
            StorageResult indicating success or failure
        """
        try:
            result = self.storage.delete(
                collection=self.checkpoint_collection,
                document_id=thread_id,
            )

            if result.success:
                self.logger.info(f"Checkpoint deleted for thread_id={thread_id}")
            else:
                self.logger.error(f"Failed to delete checkpoint: {result.error}")

            return result

        except Exception as e:
            error_msg = f"Error deleting checkpoint: {str(e)}"
            self.logger.error(error_msg)
            return StorageResult(
                success=False,
                error=error_msg,
                operation="delete_checkpoint",
                collection=self.checkpoint_collection,
            )

    def checkpoint_exists(self, thread_id: str) -> bool:
        """
        Check if a checkpoint exists for a thread.

        Args:
            thread_id: Thread ID to check

        Returns:
            True if checkpoint exists, False otherwise
        """
        try:
            return self.storage.exists(
                collection=self.checkpoint_collection,
                document_id=thread_id,
            )
        except Exception as e:
            self.logger.error(f"Error checking checkpoint existence: {str(e)}")
            return False

    def update_checkpoint_metadata(
        self,
        thread_id: str,
        metadata_updates: Dict[str, Any],
    ) -> StorageResult:
        """
        Update metadata for an existing checkpoint.

        Args:
            thread_id: Thread ID of checkpoint to update
            metadata_updates: Metadata fields to update

        Returns:
            StorageResult indicating success or failure
        """
        try:
            # Load existing checkpoint
            checkpoint = self.load_checkpoint(thread_id)
            if not checkpoint:
                return StorageResult(
                    success=False,
                    error=f"Checkpoint not found for thread_id={thread_id}",
                    operation="update_checkpoint_metadata",
                    collection=self.checkpoint_collection,
                )

            # Update metadata
            current_metadata = checkpoint.get("metadata", {})
            current_metadata.update(metadata_updates)
            checkpoint["metadata"] = current_metadata
            checkpoint["last_updated"] = datetime.utcnow().isoformat()

            # Save updated checkpoint
            result = self.storage.write(
                collection=self.checkpoint_collection,
                data=checkpoint,
                document_id=thread_id,
                mode=WriteMode.UPDATE,
            )

            if result.success:
                self.logger.info(
                    f"Checkpoint metadata updated for thread_id={thread_id}"
                )

            return result

        except Exception as e:
            error_msg = f"Error updating checkpoint metadata: {str(e)}"
            self.logger.error(error_msg)
            return StorageResult(
                success=False,
                error=error_msg,
                operation="update_checkpoint_metadata",
                collection=self.checkpoint_collection,
            )

    def get_service_info(self) -> Dict[str, Any]:
        """
        Get information about the service for debugging.

        Returns:
            Dictionary with service information
        """
        return {
            "service_name": "GraphCheckpointService",
            "checkpoint_collection": self.checkpoint_collection,
            "storage_available": self.storage.is_healthy(),
            "capabilities": {
                "save_checkpoint": True,
                "load_checkpoint": True,
                "list_checkpoints": True,
                "delete_checkpoint": True,
                "update_metadata": True,
            },
        }
