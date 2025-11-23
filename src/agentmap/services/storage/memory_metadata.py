"""
Metadata and statistics management for memory storage.

This module handles tracking document metadata, access patterns,
and storage statistics.
"""

import time
from typing import Any, Dict


class MemoryMetadataManager:
    """
    Manages metadata tracking and statistics for memory storage.

    Tracks:
    - Document creation and modification times
    - Access counts
    - Document versions
    - Storage statistics
    """

    def __init__(self, track_metadata: bool = True):
        """
        Initialize metadata manager.

        Args:
            track_metadata: Whether to track metadata
        """
        self._metadata: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self._stats = {
            "reads": 0,
            "writes": 0,
            "deletes": 0,
            "collections_created": 0,
            "documents_created": 0,
        }
        self._created_at = time.time()
        self._track_metadata = track_metadata

    def update_metadata(
        self, collection: str, document_id: str, operation: str
    ) -> None:
        """
        Update metadata for a document.

        Args:
            collection: Collection name
            document_id: Document ID
            operation: Operation type (create, update, delete, read)
        """
        if not self._track_metadata:
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

    def increment_stat(self, stat_name: str, amount: int = 1) -> None:
        """
        Increment a statistics counter.

        Args:
            stat_name: Name of the stat to increment
            amount: Amount to increment by
        """
        if stat_name in self._stats:
            self._stats[stat_name] += amount
        else:
            self._stats[stat_name] = amount

    def delete_collection_metadata(self, collection: str) -> None:
        """
        Delete metadata for an entire collection.

        Args:
            collection: Collection name
        """
        if collection in self._metadata:
            del self._metadata[collection]

    def delete_document_metadata(self, collection: str, document_id: str) -> None:
        """
        Delete metadata for a specific document.

        Args:
            collection: Collection name
            document_id: Document ID
        """
        if collection in self._metadata and document_id in self._metadata[collection]:
            del self._metadata[collection][document_id]

    def get_stats(self, storage: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Get storage statistics.

        Args:
            storage: Current storage data structure

        Returns:
            Dictionary with storage statistics
        """
        total_documents = sum(len(collection) for collection in storage.values())
        total_collections = len(storage)

        return {
            **self._stats,
            "total_collections": total_collections,
            "total_documents": total_documents,
            "uptime_seconds": time.time() - self._created_at,
            "memory_usage": {
                "collections": total_collections,
                "documents": total_documents,
                "largest_collection": max(
                    (len(collection) for collection in storage.values()),
                    default=0,
                ),
            },
        }

    def clear_metadata(self) -> None:
        """Clear all metadata."""
        self._metadata.clear()

    def reset_stats(self) -> None:
        """Reset creation statistics while keeping operation counts."""
        self._stats["collections_created"] = 0
        self._stats["documents_created"] = 0

    def get_metadata(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """
        Get all metadata.

        Returns:
            Complete metadata structure
        """
        return self._metadata

    def set_metadata(self, metadata: Dict[str, Dict[str, Dict[str, Any]]]) -> None:
        """
        Set metadata (used for persistence loading).

        Args:
            metadata: Metadata structure to set
        """
        self._metadata = metadata

    def get_raw_stats(self) -> Dict[str, Any]:
        """
        Get raw statistics dictionary.

        Returns:
            Statistics dictionary
        """
        return self._stats

    def set_stats(self, stats: Dict[str, Any]) -> None:
        """
        Set statistics (used for persistence loading).

        Args:
            stats: Statistics dictionary to set
        """
        self._stats = stats
