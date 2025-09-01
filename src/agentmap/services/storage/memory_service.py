"""
Memory Storage Service implementation for AgentMap.

This module provides a concrete implementation of the storage service
for in-memory data operations. Ideal for testing, caching, and temporary data storage.
"""

import json
import time
from copy import deepcopy
from typing import Any, Dict, List, Optional

from agentmap.services.storage.base import BaseStorageService
from agentmap.services.storage.types import StorageResult, WriteMode


class MemoryStorageService(BaseStorageService):
    """
    Memory storage service implementation.

    Provides fast in-memory storage operations with support for:
    - Collection-based data organization
    - Document-level operations
    - Path-based access for nested data
    - Query filtering and document management
    - Optional persistence to prevent data loss during development
    """

    def __init__(
        self,
        provider_name: str,
        configuration: Any,
        logging_service: Any,
        file_path_service: Any = None,
        base_directory: str = None,
    ):
        """Initialize memory storage service."""
        super().__init__(
            provider_name,
            configuration,
            logging_service,
            file_path_service,
            base_directory,
        )
        # In-memory storage structure: {collection_name: {document_id: data}}
        self._storage: Dict[str, Dict[str, Any]] = {}
        # Metadata tracking
        self._metadata: Dict[str, Dict[str, Dict[str, Any]]] = {}
        # Operation counters for statistics
        self._stats = {
            "reads": 0,
            "writes": 0,
            "deletes": 0,
            "collections_created": 0,
            "documents_created": 0,
        }
        self._created_at = time.time()

    def _initialize_client(self) -> Dict[str, Any]:
        """
        Initialize memory storage client configuration.

        Returns:
            Configuration dict for memory operations
        """
        # Extract configuration options
        config = {
            "max_collections": self._config.get_option("max_collections", 1000),
            "max_documents_per_collection": self._config.get_option(
                "max_documents_per_collection", 10000
            ),
            "max_document_size": self._config.get_option(
                "max_document_size", 1048576
            ),  # 1MB
            "auto_generate_ids": self._config.get_option("auto_generate_ids", True),
            "deep_copy_on_read": self._config.get_option("deep_copy_on_read", True),
            "deep_copy_on_write": self._config.get_option("deep_copy_on_write", True),
            "track_metadata": self._config.get_option("track_metadata", True),
            "case_sensitive_collections": self._config.get_option(
                "case_sensitive_collections", True
            ),
            "persistence_file": self._config.get_option(
                "persistence_file"
            ),  # Optional file for persistence
        }

        # Load from persistence file if specified
        if config.get("persistence_file"):
            self._load_from_persistence(config["persistence_file"])

        return config

    def _perform_health_check(self) -> bool:
        """
        Perform health check for memory storage.

        Memory storage is always healthy unless we exceed configured limits.

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Check collection count limits
            max_collections = self.client.get("max_collections", 1000)
            if len(self._storage) > max_collections:
                self._logger.warning(
                    f"Collection count ({len(self._storage)}) exceeds limit ({max_collections})"
                )
                return False

            # Check document count limits per collection
            max_docs_per_collection = self.client.get(
                "max_documents_per_collection", 10000
            )
            for collection_name, collection_data in self._storage.items():
                if len(collection_data) > max_docs_per_collection:
                    self._logger.warning(
                        f"Collection '{collection_name}' document count ({len(collection_data)}) exceeds limit ({max_docs_per_collection})"
                    )
                    return False

            # Test basic operations
            test_collection = "__health_check__"
            test_doc_id = "test"
            test_data = {"test": True, "timestamp": time.time()}

            # Test write
            self._storage.setdefault(test_collection, {})[test_doc_id] = test_data

            # Test read
            retrieved = self._storage[test_collection].get(test_doc_id)
            if not retrieved or retrieved.get("test") is not True:
                return False

            # Test delete
            del self._storage[test_collection][test_doc_id]
            if test_collection in self._storage and not self._storage[test_collection]:
                del self._storage[test_collection]

            return True

        except Exception as e:
            self._logger.debug(f"Memory health check failed: {e}")
            return False

    def _normalize_collection_name(self, collection: str) -> str:
        """
        Normalize collection name based on case sensitivity setting.

        Args:
            collection: Collection name

        Returns:
            Normalized collection name
        """
        if self.client.get("case_sensitive_collections", True):
            return collection
        else:
            return collection.lower()

    def _generate_document_id(self, collection: str) -> str:
        """
        Generate a unique document ID for a collection.

        Args:
            collection: Collection name

        Returns:
            Generated document ID
        """
        collection_data = self._storage.get(collection, {})

        # Simple incremental ID generation
        max_id = 0
        for doc_id in collection_data.keys():
            if doc_id.isdigit():
                max_id = max(max_id, int(doc_id))

        return str(max_id + 1)

    def _apply_path(self, data: Any, path: str) -> Any:
        """
        Extract data from nested structure using dot notation.

        Args:
            data: Data structure to traverse
            path: Dot-notation path (e.g., "user.address.city")

        Returns:
            Value at the specified path or None if not found
        """
        if not path:
            return data

        components = path.split(".")
        current = data

        for component in components:
            if current is None:
                return None

            # Handle arrays with numeric indices
            if component.isdigit() and isinstance(current, list):
                index = int(component)
                if 0 <= index < len(current):
                    current = current[index]
                else:
                    return None
            # Handle dictionaries
            elif isinstance(current, dict):
                current = current.get(component)
            else:
                return None

        return current

    def _update_path(self, data: Any, path: str, value: Any) -> Any:
        """
        Update data at a specified path.

        Args:
            data: Data structure to modify
            path: Dot-notation path
            value: New value to set

        Returns:
            Updated data structure
        """
        if not path:
            return value

        # Make a copy to avoid modifying original
        if isinstance(data, dict):
            result = data.copy()
        elif isinstance(data, list):
            result = data.copy()
        else:
            # If data is not a container, start with empty dict
            result = {}

        components = path.split(".")
        current = result

        # Navigate to the parent of the target
        for i, component in enumerate(components[:-1]):
            # Handle array indices
            if component.isdigit() and isinstance(current, list):
                index = int(component)
                # Extend the list if needed
                while len(current) <= index:
                    current.append({})

                if current[index] is None:
                    if i < len(components) - 2 and components[i + 1].isdigit():
                        current[index] = []
                    else:
                        current[index] = {}

                current = current[index]

            # Handle dictionary keys
            else:
                if not isinstance(current, dict):
                    current = {}

                if component not in current:
                    if i < len(components) - 2 and components[i + 1].isdigit():
                        current[component] = []
                    else:
                        current[component] = {}

                current = current[component]

        # Set the value at the final path component
        last_component = components[-1]

        if last_component.isdigit() and isinstance(current, list):
            index = int(last_component)
            while len(current) <= index:
                current.append(None)
            current[index] = value
        elif isinstance(current, dict):
            current[last_component] = value

        return result

    def _apply_query_filter(
        self, data: Dict[str, Any], query: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply query filtering to collection data.

        Args:
            data: Collection data (document_id -> document)
            query: Query parameters

        Returns:
            Filtered data matching query criteria
        """
        if not query:
            return data

        # Extract special query parameters
        limit = query.pop("limit", None)
        offset = query.pop("offset", 0)
        sort_field = query.pop("sort", None)
        sort_order = query.pop("order", "asc").lower()

        # Apply field filtering
        filtered_data = {}
        for doc_id, doc_data in data.items():
            if not isinstance(doc_data, dict):
                continue

            matches = True
            for field, value in query.items():
                if doc_data.get(field) != value:
                    matches = False
                    break

            if matches:
                filtered_data[doc_id] = doc_data

        # Convert to list for sorting and pagination
        items = list(filtered_data.items())

        # Apply sorting
        if sort_field:
            reverse = sort_order == "desc"
            items.sort(
                key=lambda x: x[1].get(sort_field) if isinstance(x[1], dict) else None,
                reverse=reverse,
            )

        # Apply pagination
        if offset and isinstance(offset, int) and offset > 0:
            items = items[offset:]

        if limit and isinstance(limit, int) and limit > 0:
            items = items[:limit]

        # Convert back to dict
        return dict(items)

    def _update_metadata(
        self, collection: str, document_id: str, operation: str
    ) -> None:
        """
        Update metadata for a document.

        Args:
            collection: Collection name
            document_id: Document ID
            operation: Operation type (create, update, delete)
        """
        if not self.client.get("track_metadata", True):
            return

        collection = self._normalize_collection_name(collection)

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

    def _save_to_persistence(self, file_path: str) -> None:
        """
        Save current storage state to persistence file.

        Args:
            file_path: Path to persistence file
        """
        try:
            import os

            persistence_data = {
                "storage": self._storage,
                "metadata": self._metadata,
                "stats": self._stats,
                "saved_at": time.time(),
            }

            # Ensure directory exists
            os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(persistence_data, f, indent=2, default=str)

            self._logger.debug(f"Saved memory storage to {file_path}")
        except Exception as e:
            self._logger.warning(f"Failed to save persistence data: {e}")

    def _load_from_persistence(self, file_path: str) -> None:
        """
        Load storage state from persistence file.

        Args:
            file_path: Path to persistence file
        """
        try:
            import os

            if not os.path.exists(file_path):
                self._logger.debug(f"Persistence file not found: {file_path}")
                return

            with open(file_path, "r", encoding="utf-8") as f:
                persistence_data = json.load(f)

            self._storage = persistence_data.get("storage", {})
            self._metadata = persistence_data.get("metadata", {})
            self._stats = persistence_data.get("stats", self._stats)

            self._logger.debug(f"Loaded memory storage from {file_path}")
        except Exception as e:
            self._logger.warning(f"Failed to load persistence data: {e}")

    def read(
        self,
        collection: str,
        document_id: Optional[str] = None,
        query: Optional[Dict[str, Any]] = None,
        path: Optional[str] = None,
        **kwargs,
    ) -> Any:
        """
        Read data from memory storage.

        Args:
            collection: Collection name
            document_id: Document ID (optional)
            query: Query parameters for filtering
            path: Dot-notation path for nested access
            **kwargs: Additional parameters

        Returns:
            Document data based on query and path
        """
        try:
            self._stats["reads"] += 1
            collection = self._normalize_collection_name(collection)

            # Get collection data
            collection_data = self._storage.get(collection, {})

            # Handle specific document request
            if document_id is not None:
                if document_id not in collection_data:
                    return None

                document = collection_data[document_id]

                # Update metadata
                self._update_metadata(collection, document_id, "read")

                # Apply path extraction if needed
                if path:
                    result = self._apply_path(document, path)
                else:
                    result = document

                # Return deep copy if configured
                if self.client.get("deep_copy_on_read", True) and result is not None:
                    return deepcopy(result)
                else:
                    return result

            # Handle collection-level queries
            data = collection_data

            # Apply query filters
            if query:
                # Make a copy before modifying for filtering
                query_copy = query.copy()
                data = self._apply_query_filter(data, query_copy)

            # Apply path extraction at collection level
            if path:
                result = {}
                for doc_id, doc_data in data.items():
                    path_result = self._apply_path(doc_data, path)
                    if path_result is not None:
                        result[doc_id] = path_result
                data = result

            # Return deep copy if configured
            if self.client.get("deep_copy_on_read", True):
                return deepcopy(data)
            else:
                return data

        except Exception as e:
            self._handle_error(
                "read", e, collection=collection, document_id=document_id
            )

    def write(
        self,
        collection: str,
        data: Any,
        document_id: Optional[str] = None,
        mode: WriteMode = WriteMode.WRITE,
        path: Optional[str] = None,
        **kwargs,
    ) -> StorageResult:
        """
        Write data to memory storage.

        Args:
            collection: Collection name
            data: Data to write
            document_id: Document ID (optional, will be generated if not provided)
            mode: Write mode (write, append, update)
            path: Dot-notation path for nested updates
            **kwargs: Additional parameters

        Returns:
            StorageResult with operation details
        """
        try:
            self._stats["writes"] += 1
            collection = self._normalize_collection_name(collection)

            # Check collection limit
            max_collections = self.client.get("max_collections", 1000)
            if (
                collection not in self._storage
                and len(self._storage) >= max_collections
            ):
                return self._create_error_result(
                    "write",
                    f"Maximum collections limit ({max_collections}) exceeded",
                    collection=collection,
                )

            # Initialize collection if it doesn't exist
            if collection not in self._storage:
                self._storage[collection] = {}
                self._stats["collections_created"] += 1

            collection_data = self._storage[collection]

            # Generate document ID if not provided and auto-generation is enabled
            if document_id is None and self.client.get("auto_generate_ids", True):
                document_id = self._generate_document_id(collection)
            elif document_id is None:
                return self._create_error_result(
                    "write",
                    "document_id is required when auto_generate_ids is disabled",
                    collection=collection,
                )

            # Check document limit per collection
            max_docs = self.client.get("max_documents_per_collection", 10000)
            if document_id not in collection_data and len(collection_data) >= max_docs:
                return self._create_error_result(
                    "write",
                    f"Maximum documents per collection limit ({max_docs}) exceeded",
                    collection=collection,
                    document_id=document_id,
                )

            # Check document size limit
            max_size = self.client.get("max_document_size", 1048576)
            if max_size and len(str(data)) > max_size:
                return self._create_error_result(
                    "write",
                    f"Document size exceeds limit ({max_size} bytes)",
                    collection=collection,
                    document_id=document_id,
                )

            # Track if this is a new document
            created_new = document_id not in collection_data

            # Make deep copy of data if configured
            if self.client.get("deep_copy_on_write", True):
                data_to_store = deepcopy(data)
            else:
                data_to_store = data

            if mode == WriteMode.WRITE:
                # Simple write operation (create or overwrite)
                if path:
                    # Path-based write
                    if document_id in collection_data:
                        # Update existing document at path
                        collection_data[document_id] = self._update_path(
                            collection_data[document_id], path, data_to_store
                        )
                    else:
                        # Create new document with path
                        new_doc = {}
                        collection_data[document_id] = self._update_path(
                            new_doc, path, data_to_store
                        )
                        created_new = True
                else:
                    # Direct write
                    collection_data[document_id] = data_to_store
                    if created_new:
                        self._stats["documents_created"] += 1

                # Update metadata
                self._update_metadata(
                    collection, document_id, "create" if created_new else "update"
                )

                return self._create_success_result(
                    "write",
                    collection=collection,
                    document_id=document_id,
                    created_new=created_new,
                )

            elif mode == WriteMode.UPDATE:
                # Update operation
                if document_id not in collection_data:
                    return self._create_error_result(
                        "update",
                        f"Document '{document_id}' not found for update",
                        collection=collection,
                        document_id=document_id,
                    )

                current_doc = collection_data[document_id]

                if path:
                    # Path-based update
                    collection_data[document_id] = self._update_path(
                        current_doc, path, data_to_store
                    )
                else:
                    # Document-level update (merge if both are dicts)
                    if isinstance(current_doc, dict) and isinstance(
                        data_to_store, dict
                    ):
                        current_doc.update(data_to_store)
                    else:
                        collection_data[document_id] = data_to_store

                # Update metadata
                self._update_metadata(collection, document_id, "update")

                return self._create_success_result(
                    "update", collection=collection, document_id=document_id
                )

            elif mode == WriteMode.APPEND:
                # Append operation
                if document_id not in collection_data:
                    # Create new document with data as initial content
                    collection_data[document_id] = data_to_store
                    created_new = True
                    self._stats["documents_created"] += 1
                else:
                    current_doc = collection_data[document_id]

                    if isinstance(current_doc, list) and isinstance(
                        data_to_store, list
                    ):
                        # Append lists
                        current_doc.extend(data_to_store)
                    elif isinstance(current_doc, list):
                        # Append single item to list
                        current_doc.append(data_to_store)
                    elif isinstance(current_doc, dict) and isinstance(
                        data_to_store, dict
                    ):
                        # Merge dictionaries
                        current_doc.update(data_to_store)
                    else:
                        # Convert to list and append
                        collection_data[document_id] = [current_doc, data_to_store]

                # Update metadata
                self._update_metadata(
                    collection, document_id, "create" if created_new else "update"
                )

                return self._create_success_result(
                    "append",
                    collection=collection,
                    document_id=document_id,
                    created_new=created_new,
                )

            else:
                return self._create_error_result(
                    "write",
                    f"Unsupported write mode: {mode}",
                    collection=collection,
                    document_id=document_id,
                )

        except Exception as e:
            self._handle_error(
                "write",
                e,
                collection=collection,
                document_id=document_id,
                mode=mode.value,
            )

    def delete(
        self,
        collection: str,
        document_id: Optional[str] = None,
        path: Optional[str] = None,
        query: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> StorageResult:
        """
        Delete from memory storage.

        Args:
            collection: Collection name
            document_id: Document ID (optional)
            path: Dot-notation path to delete
            query: Query for batch delete
            **kwargs: Additional parameters

        Returns:
            StorageResult with operation details
        """
        try:
            self._stats["deletes"] += 1
            collection = self._normalize_collection_name(collection)

            if collection not in self._storage:
                return self._create_error_result(
                    "delete",
                    f"Collection '{collection}' not found",
                    collection=collection,
                )

            collection_data = self._storage[collection]

            # Handle deleting entire collection
            if document_id is None and path is None and not query:
                del self._storage[collection]
                if collection in self._metadata:
                    del self._metadata[collection]

                return self._create_success_result(
                    "delete",
                    collection=collection,
                    collection_deleted=True,
                    total_affected=len(collection_data),
                )

            # Handle deleting specific document
            if document_id is not None:
                if document_id not in collection_data:
                    return self._create_error_result(
                        "delete",
                        f"Document '{document_id}' not found",
                        collection=collection,
                        document_id=document_id,
                    )

                if path:
                    # Delete path within document
                    current_doc = collection_data[document_id]

                    # For simple path deletion, we'll recreate the document without the path
                    # This is a simplified implementation
                    if "." not in path:
                        # Simple key deletion
                        if isinstance(current_doc, dict) and path in current_doc:
                            del current_doc[path]
                        elif isinstance(current_doc, list) and path.isdigit():
                            index = int(path)
                            if 0 <= index < len(current_doc):
                                current_doc.pop(index)

                    # Update metadata
                    self._update_metadata(collection, document_id, "update")
                else:
                    # Delete entire document
                    del collection_data[document_id]

                    # Clean up metadata
                    if (
                        collection in self._metadata
                        and document_id in self._metadata[collection]
                    ):
                        del self._metadata[collection][document_id]

                return self._create_success_result(
                    "delete", collection=collection, document_id=document_id, path=path
                )

            # Handle batch delete with query
            if query:
                # Apply query filter to find documents to delete
                filtered_data = self._apply_query_filter(collection_data, query.copy())
                deleted_ids = list(filtered_data.keys())

                # Delete the documents
                for doc_id in deleted_ids:
                    del collection_data[doc_id]
                    if (
                        collection in self._metadata
                        and doc_id in self._metadata[collection]
                    ):
                        del self._metadata[collection][doc_id]

                return self._create_success_result(
                    "delete",
                    collection=collection,
                    total_affected=len(deleted_ids),
                    deleted_ids=deleted_ids,
                )

            return self._create_error_result(
                "delete", "Invalid delete operation", collection=collection
            )

        except Exception as e:
            self._handle_error(
                "delete", e, collection=collection, document_id=document_id
            )

    def exists(
        self, collection: str, document_id: Optional[str] = None, **kwargs
    ) -> bool:
        """
        Check if collection or document exists in memory storage.

        Args:
            collection: Collection name
            document_id: Document ID (optional)
            **kwargs: Additional parameters

        Returns:
            True if exists, False otherwise
        """
        try:
            collection = self._normalize_collection_name(collection)

            if collection not in self._storage:
                return False

            if document_id is None:
                return True  # Collection exists

            return document_id in self._storage[collection]

        except Exception as e:
            self._logger.debug(f"Error checking existence: {e}")
            return False

    def count(
        self, collection: str, query: Optional[Dict[str, Any]] = None, **kwargs
    ) -> int:
        """
        Count documents in memory storage.

        Args:
            collection: Collection name
            query: Query parameters for filtering
            **kwargs: Additional parameters

        Returns:
            Count of documents
        """
        try:
            collection = self._normalize_collection_name(collection)

            if collection not in self._storage:
                return 0

            collection_data = self._storage[collection]

            if query:
                filtered_data = self._apply_query_filter(collection_data, query.copy())
                return len(filtered_data)

            return len(collection_data)

        except Exception as e:
            self._logger.debug(f"Error counting documents: {e}")
            return 0

    def list_collections(self, **kwargs) -> List[str]:
        """
        List all collections in memory storage.

        Args:
            **kwargs: Additional parameters

        Returns:
            List of collection names
        """
        try:
            return sorted(list(self._storage.keys()))
        except Exception as e:
            self._logger.debug(f"Error listing collections: {e}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        """
        Get memory storage statistics.

        Returns:
            Dictionary with storage statistics
        """
        total_documents = sum(len(collection) for collection in self._storage.values())
        total_collections = len(self._storage)

        return {
            **self._stats,
            "total_collections": total_collections,
            "total_documents": total_documents,
            "uptime_seconds": time.time() - self._created_at,
            "memory_usage": {
                "collections": total_collections,
                "documents": total_documents,
                "largest_collection": max(
                    (len(collection) for collection in self._storage.values()),
                    default=0,
                ),
            },
        }

    def clear_all(self) -> StorageResult:
        """
        Clear all data from memory storage.

        Returns:
            StorageResult with operation details
        """
        try:
            collections_cleared = len(self._storage)
            documents_cleared = sum(
                len(collection) for collection in self._storage.values()
            )

            self._storage.clear()
            self._metadata.clear()

            # Reset stats but keep operation history
            self._stats["collections_created"] = 0
            self._stats["documents_created"] = 0

            return self._create_success_result(
                "clear_all",
                total_affected=documents_cleared,
                message=f"Cleared {collections_cleared} collections and {documents_cleared} documents",
            )

        except Exception as e:
            self._handle_error("clear_all", e)

    def save_persistence(self) -> StorageResult:
        """
        Save current storage state to persistence file (if configured).

        Returns:
            StorageResult with operation details
        """
        try:
            persistence_file = self.client.get("persistence_file")
            if not persistence_file:
                return self._create_error_result(
                    "save_persistence", "No persistence file configured"
                )

            self._save_to_persistence(persistence_file)

            return self._create_success_result(
                "save_persistence", file_path=persistence_file
            )

        except Exception as e:
            self._handle_error("save_persistence", e)
