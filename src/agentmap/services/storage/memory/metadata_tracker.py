"""
Metadata Tracker for AgentMap Memory Storage.

This module provides document metadata tracking including creation time,
update time, access count, and version tracking.
"""

import time
from typing import Any, Dict, Optional


class MetadataTracker:
    """
    Document metadata tracking for memory storage.

    Tracks creation time, update time, access count, and version
    for each document in each collection.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize metadata tracker.

        Args:
            config: Configuration dictionary with tracking settings
        """
        self._config = config
        # Metadata structure: {collection: {document_id: metadata}}
        self._metadata: Dict[str, Dict[str, Dict[str, Any]]] = {}

    @property
    def metadata(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """Get the metadata dictionary."""
        return self._metadata

    def is_tracking_enabled(self) -> bool:
        """
        Check if metadata tracking is enabled.

        Returns:
            True if tracking is enabled, False otherwise
        """
        return self._config.get("track_metadata", True)

    def update_metadata(
        self, collection: str, document_id: str, operation: str
    ) -> None:
        """
        Update metadata for a document.

        Args:
            collection: Collection name
            document_id: Document ID
            operation: Operation type (create, update, read)
        """
        if not self.is_tracking_enabled():
            return

        # Initialize metadata structure
        if collection not in self._metadata:
            self._metadata[collection] = {}

        if document_id not in self._metadata[collection]:
            self._metadata[collection][document_id] = {
                "created_at": time.time(),
                "updated_at": time.time(),
                "access_count": 0,
                "version": 1,
            }
        else:
            self._metadata[collection][document_id]["updated_at"] = time.time()
            if operation == "read":
                self._metadata[collection][document_id]["access_count"] += 1
            elif operation in ["write", "update"]:
                self._metadata[collection][document_id]["version"] += 1

    def get_document_metadata(
        self, collection: str, document_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a specific document.

        Args:
            collection: Collection name
            document_id: Document ID

        Returns:
            Metadata dictionary or None if not found
        """
        if collection not in self._metadata:
            return None
        return self._metadata[collection].get(document_id)

    def delete_document_metadata(
        self, collection: str, document_id: str
    ) -> None:
        """
        Delete metadata for a document.

        Args:
            collection: Collection name
            document_id: Document ID
        """
        if (
            collection in self._metadata
            and document_id in self._metadata[collection]
        ):
            del self._metadata[collection][document_id]

    def delete_collection_metadata(self, collection: str) -> None:
        """
        Delete metadata for an entire collection.

        Args:
            collection: Collection name
        """
        if collection in self._metadata:
            del self._metadata[collection]

    def clear_all(self) -> None:
        """Clear all metadata."""
        self._metadata.clear()
