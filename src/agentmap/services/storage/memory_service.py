"""
Memory Storage Service implementation for AgentMap.

This module provides a concrete implementation of the storage service
for in-memory data operations. Ideal for testing, caching, and temporary data storage.

Note: This module has been refactored into smaller components:
- memory_helpers.py: Path operations and query filtering
- memory_metadata.py: Metadata tracking and statistics
- memory_persistence.py: Save/load operations
"""

import time
from copy import deepcopy
from typing import Any, Dict, List, Optional

from agentmap.services.storage.base import BaseStorageService
from agentmap.services.storage.memory_helpers import MemoryStorageHelpers
from agentmap.services.storage.memory_metadata import MemoryMetadataManager
from agentmap.services.storage.memory_persistence import MemoryPersistenceManager
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

        # Initialize helper components
        self._helpers = MemoryStorageHelpers()
        self._metadata_manager = MemoryMetadataManager()
        self._persistence_manager = MemoryPersistenceManager(self._logger)

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
            "persistence_file": self._config.get_option("persistence_file"),
        }

        # Load from persistence file if specified
        if config.get("persistence_file"):
            storage, metadata, stats = self._persistence_manager.load_from_file(
                config["persistence_file"]
            )
            self._storage = storage
            self._metadata_manager.set_metadata(metadata)
            if stats:
                self._metadata_manager.set_stats(stats)

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
            self._metadata_manager.increment_stat("reads")
            collection = self._helpers.normalize_collection_name(
                collection, self.client.get("case_sensitive_collections", True)
            )

            # Get collection data
            collection_data = self._storage.get(collection, {})

            # Handle specific document request
            if document_id is not None:
                if document_id not in collection_data:
                    return None

                document = collection_data[document_id]

                # Update metadata
                self._metadata_manager.update_metadata(collection, document_id, "read")

                # Apply path extraction if needed
                if path:
                    result = self._helpers.apply_path(document, path)
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
                data = self._helpers.apply_query_filter(data, query_copy)

            # Apply path extraction at collection level
            if path:
                result = {}
                for doc_id, doc_data in data.items():
                    path_result = self._helpers.apply_path(doc_data, path)
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
            self._metadata_manager.increment_stat("writes")
            collection = self._helpers.normalize_collection_name(
                collection, self.client.get("case_sensitive_collections", True)
            )

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
                self._metadata_manager.increment_stat("collections_created")

            collection_data = self._storage[collection]

            # Generate document ID if not provided and auto-generation is enabled
            if document_id is None and self.client.get("auto_generate_ids", True):
                document_id = self._helpers.generate_document_id(collection_data)
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

            # Delegate to appropriate write handler
            if mode == WriteMode.WRITE:
                return self._handle_write_mode(
                    collection,
                    collection_data,
                    document_id,
                    data_to_store,
                    path,
                    created_new,
                )
            elif mode == WriteMode.UPDATE:
                return self._handle_update_mode(
                    collection, collection_data, document_id, data_to_store, path
                )
            elif mode == WriteMode.APPEND:
                return self._handle_append_mode(
                    collection, collection_data, document_id, data_to_store, created_new
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

    def _handle_write_mode(
        self,
        collection: str,
        collection_data: Dict,
        document_id: str,
        data: Any,
        path: Optional[str],
        created_new: bool,
    ) -> StorageResult:
        """Handle WRITE mode operation."""
        if path:
            # Path-based write
            if document_id in collection_data:
                collection_data[document_id] = self._helpers.update_path(
                    collection_data[document_id], path, data
                )
            else:
                new_doc = {}
                collection_data[document_id] = self._helpers.update_path(
                    new_doc, path, data
                )
                created_new = True
        else:
            # Direct write
            collection_data[document_id] = data
            if created_new:
                self._metadata_manager.increment_stat("documents_created")

        # Update metadata
        self._metadata_manager.update_metadata(
            collection, document_id, "create" if created_new else "update"
        )

        return self._create_success_result(
            "write",
            collection=collection,
            document_id=document_id,
            created_new=created_new,
        )

    def _handle_update_mode(
        self,
        collection: str,
        collection_data: Dict,
        document_id: str,
        data: Any,
        path: Optional[str],
    ) -> StorageResult:
        """Handle UPDATE mode operation."""
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
            collection_data[document_id] = self._helpers.update_path(
                current_doc, path, data
            )
        else:
            # Document-level update (merge if both are dicts)
            if isinstance(current_doc, dict) and isinstance(data, dict):
                current_doc.update(data)
            else:
                collection_data[document_id] = data

        # Update metadata
        self._metadata_manager.update_metadata(collection, document_id, "update")

        return self._create_success_result(
            "update", collection=collection, document_id=document_id
        )

    def _handle_append_mode(
        self,
        collection: str,
        collection_data: Dict,
        document_id: str,
        data: Any,
        created_new: bool,
    ) -> StorageResult:
        """Handle APPEND mode operation."""
        if document_id not in collection_data:
            # Create new document with data as initial content
            collection_data[document_id] = data
            created_new = True
            self._metadata_manager.increment_stat("documents_created")
        else:
            current_doc = collection_data[document_id]

            if isinstance(current_doc, list) and isinstance(data, list):
                # Append lists
                current_doc.extend(data)
            elif isinstance(current_doc, list):
                # Append single item to list
                current_doc.append(data)
            elif isinstance(current_doc, dict) and isinstance(data, dict):
                # Merge dictionaries
                current_doc.update(data)
            else:
                # Convert to list and append
                collection_data[document_id] = [current_doc, data]

        # Update metadata
        self._metadata_manager.update_metadata(
            collection, document_id, "create" if created_new else "update"
        )

        return self._create_success_result(
            "append",
            collection=collection,
            document_id=document_id,
            created_new=created_new,
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
            self._metadata_manager.increment_stat("deletes")
            collection = self._helpers.normalize_collection_name(
                collection, self.client.get("case_sensitive_collections", True)
            )

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
                self._metadata_manager.delete_collection_metadata(collection)

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

                    # For simple path deletion
                    if "." not in path:
                        # Simple key deletion
                        if isinstance(current_doc, dict) and path in current_doc:
                            del current_doc[path]
                        elif isinstance(current_doc, list) and path.isdigit():
                            index = int(path)
                            if 0 <= index < len(current_doc):
                                current_doc.pop(index)

                    # Update metadata
                    self._metadata_manager.update_metadata(
                        collection, document_id, "update"
                    )
                else:
                    # Delete entire document
                    del collection_data[document_id]
                    self._metadata_manager.delete_document_metadata(
                        collection, document_id
                    )

                return self._create_success_result(
                    "delete", collection=collection, document_id=document_id, path=path
                )

            # Handle batch delete with query
            if query:
                # Apply query filter to find documents to delete
                filtered_data = self._helpers.apply_query_filter(
                    collection_data, query.copy()
                )
                deleted_ids = list(filtered_data.keys())

                # Delete the documents
                for doc_id in deleted_ids:
                    del collection_data[doc_id]
                    self._metadata_manager.delete_document_metadata(collection, doc_id)

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
            collection = self._helpers.normalize_collection_name(
                collection, self.client.get("case_sensitive_collections", True)
            )

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
            collection = self._helpers.normalize_collection_name(
                collection, self.client.get("case_sensitive_collections", True)
            )

            if collection not in self._storage:
                return 0

            collection_data = self._storage[collection]

            if query:
                filtered_data = self._helpers.apply_query_filter(
                    collection_data, query.copy()
                )
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
        return self._metadata_manager.get_stats(self._storage)

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
            self._metadata_manager.clear_metadata()
            self._metadata_manager.reset_stats()

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

            self._persistence_manager.save_to_file(
                persistence_file,
                self._storage,
                self._metadata_manager.get_metadata(),
                self._metadata_manager.get_raw_stats(),
            )

            return self._create_success_result(
                "save_persistence", file_path=persistence_file
            )

        except Exception as e:
            self._handle_error("save_persistence", e)
