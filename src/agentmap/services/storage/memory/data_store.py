"""
Memory Data Store for AgentMap.

This module provides core in-memory data storage management,
including storage structures, document ID generation, and statistics tracking.
"""

import time
from typing import Any, Dict


class MemoryDataStore:
    """
    Core in-memory data storage management.

    Manages the in-memory storage structure, document ID generation,
    and operation statistics.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize memory data store.

        Args:
            config: Configuration dictionary with storage settings
        """
        self._config = config
        # In-memory storage structure: {collection_name: {document_id: data}}
        self._storage: Dict[str, Dict[str, Any]] = {}
        # Track maximum numeric ID per collection for O(1) ID generation
        self._max_ids: Dict[str, int] = {}
        # Operation counters for statistics
        self._stats = {
            "reads": 0,
            "writes": 0,
            "deletes": 0,
            "collections_created": 0,
            "documents_created": 0,
            "total_documents": 0,
        }
        self._created_at = time.time()

    @property
    def storage(self) -> Dict[str, Dict[str, Any]]:
        """Get the storage dictionary."""
        return self._storage

    @property
    def stats(self) -> Dict[str, Any]:
        """Get the statistics dictionary."""
        return self._stats

    def normalize_collection_name(self, collection: str) -> str:
        """
        Normalize collection name based on case sensitivity setting.

        Args:
            collection: Collection name

        Returns:
            Normalized collection name
        """
        if self._config.get("case_sensitive_collections", True):
            return collection
        else:
            return collection.lower()

    def generate_document_id(self, collection: str) -> str:
        """
        Generate a unique document ID for a collection.

        Args:
            collection: Collection name

        Returns:
            Generated document ID
        """
        # O(1) ID generation using tracked maximum
        if collection not in self._max_ids:
            self._max_ids[collection] = 0

        self._max_ids[collection] += 1
        return str(self._max_ids[collection])

    def get_collection(self, collection: str) -> Dict[str, Any]:
        """
        Get a collection's data.

        Args:
            collection: Collection name

        Returns:
            Collection data dictionary
        """
        return self._storage.get(collection, {})

    def collection_exists(self, collection: str) -> bool:
        """
        Check if a collection exists.

        Args:
            collection: Collection name

        Returns:
            True if collection exists, False otherwise
        """
        return collection in self._storage

    def document_exists(self, collection: str, document_id: str) -> bool:
        """
        Check if a document exists in a collection.

        Args:
            collection: Collection name
            document_id: Document ID

        Returns:
            True if document exists, False otherwise
        """
        return collection in self._storage and document_id in self._storage[collection]

    def get_document(self, collection: str, document_id: str) -> Any:
        """
        Get a document from a collection.

        Args:
            collection: Collection name
            document_id: Document ID

        Returns:
            Document data or None if not found
        """
        if not self.collection_exists(collection):
            return None
        return self._storage[collection].get(document_id)

    def set_document(self, collection: str, document_id: str, data: Any) -> None:
        """
        Set a document in a collection.

        Args:
            collection: Collection name
            document_id: Document ID
            data: Document data
        """
        is_new_collection = collection not in self._storage
        is_new_document = (
            not is_new_collection and document_id not in self._storage[collection]
        )

        if is_new_collection:
            self._storage[collection] = {}
            self._stats["collections_created"] += 1

        if is_new_document or is_new_collection:
            self._stats["total_documents"] += 1

        self._storage[collection][document_id] = data

        # Update max ID if this is a numeric ID
        if document_id.isdigit():
            numeric_id = int(document_id)
            if collection not in self._max_ids:
                self._max_ids[collection] = numeric_id
            else:
                self._max_ids[collection] = max(self._max_ids[collection], numeric_id)

    def delete_document(self, collection: str, document_id: str) -> bool:
        """
        Delete a document from a collection.

        Args:
            collection: Collection name
            document_id: Document ID

        Returns:
            True if document was deleted, False if not found
        """
        if not self.document_exists(collection, document_id):
            return False

        del self._storage[collection][document_id]
        self._stats["total_documents"] -= 1
        return True

    def delete_collection(self, collection: str) -> int:
        """
        Delete an entire collection.

        Args:
            collection: Collection name

        Returns:
            Number of documents that were deleted
        """
        if not self.collection_exists(collection):
            return 0

        document_count = len(self._storage[collection])
        del self._storage[collection]
        self._stats["total_documents"] -= document_count

        # Clean up max ID tracking
        if collection in self._max_ids:
            del self._max_ids[collection]

        return document_count

    def count_documents(self, collection: str) -> int:
        """
        Count documents in a collection.

        Args:
            collection: Collection name

        Returns:
            Number of documents
        """
        if not self.collection_exists(collection):
            return 0
        return len(self._storage[collection])

    def list_collections(self) -> list:
        """
        List all collection names.

        Returns:
            Sorted list of collection names
        """
        return sorted(list(self._storage.keys()))

    def clear_all(self) -> tuple:
        """
        Clear all data from storage.

        Returns:
            Tuple of (collections_cleared, documents_cleared)
        """
        collections_cleared = len(self._storage)
        documents_cleared = self._stats["total_documents"]

        self._storage.clear()
        self._max_ids.clear()

        # Reset stats but keep operation history
        self._stats["collections_created"] = 0
        self._stats["documents_created"] = 0
        self._stats["total_documents"] = 0

        return (collections_cleared, documents_cleared)

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get storage statistics.

        Returns:
            Dictionary with storage statistics

        Note:
            largest_collection is calculated on-demand and may be expensive
            with many collections.
        """
        total_collections = len(self._storage)

        return {
            **self._stats,
            "total_collections": total_collections,
            "uptime_seconds": time.time() - self._created_at,
            "memory_usage": {
                "collections": total_collections,
                "documents": self._stats["total_documents"],
                "largest_collection": max(
                    (len(collection) for collection in self._storage.values()),
                    default=0,
                ),
            },
        }

    def increment_stat(self, stat_name: str) -> None:
        """
        Increment a statistics counter.

        Args:
            stat_name: Name of the statistic to increment
        """
        if stat_name in self._stats:
            self._stats[stat_name] += 1

    def check_collection_limit(self, collection: str) -> bool:
        """
        Check if adding a new collection would exceed limits.

        Args:
            collection: Collection name to check

        Returns:
            True if within limits, False if would exceed
        """
        max_collections = self._config.get("max_collections", 1000)
        if collection not in self._storage and len(self._storage) >= max_collections:
            return False
        return True

    def check_document_limit(self, collection: str, document_id: str) -> bool:
        """
        Check if adding a new document would exceed limits.

        Args:
            collection: Collection name
            document_id: Document ID to check

        Returns:
            True if within limits, False if would exceed
        """
        if not self.collection_exists(collection):
            return True

        max_docs = self._config.get("max_documents_per_collection", 10000)
        collection_data = self._storage[collection]
        if document_id not in collection_data and len(collection_data) >= max_docs:
            return False
        return True
