"""
JSON Storage Service implementation for AgentMap.

This module provides a concrete implementation of the storage service
for JSON files, with support for path-based operations and nested documents.

Configuration Integration:
- Uses StorageConfigService for domain-specific configuration access
- Leverages named domain methods: get_json_config(), get_json_data_path(), etc.
- Supports collection-specific configuration via get_collection_config()
- Implements fail-fast behavior when JSON storage is disabled
- Follows established configuration architecture patterns
"""

import contextlib
import json
import os
from collections.abc import Generator
from typing import Any, Dict, List, Optional, TextIO

from agentmap.services.config.storage_config_service import StorageConfigService
from agentmap.services.file_path_service import FilePathService
from agentmap.services.logging_service import LoggingService
from agentmap.services.storage.base import BaseStorageService
from agentmap.services.storage.types import StorageResult, WriteMode


class JSONStorageService(BaseStorageService):
    """
    JSON storage service implementation.

    Provides storage operations for JSON files with support for
    path-based access, nested documents, and query filtering.

    Configuration Pattern:
    - Uses StorageConfigService named domain methods instead of generic access
    - Leverages get_json_config(), get_json_data_path(), is_json_storage_enabled()
    - Supports collection-specific configuration via get_collection_config()
    - Follows configuration architecture patterns from docs/contributing/architecture/configuration-patterns.md
    """

    def __init__(
        self,
        provider_name: str,
        configuration: StorageConfigService,  # StorageConfigService (avoid circular import)
        logging_service: LoggingService,  # LoggingService (avoid circular import)
        file_path_service: Optional[FilePathService] = None,
        base_directory: Optional[str] = None,
    ):
        """
        Initialize JSONStorageService.

        Args:
            provider_name: Name of the storage provider
            configuration: Storage configuration service
            logging_service: Logging service for creating loggers
            file_path_service: Optional file path service for path validation
            base_directory: Optional base directory for system storage operations
        """
        # Call parent's __init__ with all parameters for injection support
        super().__init__(
            provider_name,
            configuration,
            logging_service,
            file_path_service,
            base_directory,
        )

    # NOTE: This method is included for backward compatibility
    # The base class uses health_check(), but some code expects is_healthy()
    def is_healthy(self) -> bool:
        """
        Check if the service is healthy and ready to use.

        Returns:
            True if the service is healthy, False otherwise
        """
        return self.health_check()

    def _initialize_client(self) -> Any:
        """
        Initialize JSON client.

        For JSON operations, we don't need a complex client.
        Just ensure base directory exists and return a simple config.

        Handles two storage configurations:
        - System storage (base_directory injection): files go directly in base_directory
        - User storage (StorageConfigService): files go in configured paths

        Returns:
            Configuration dict for JSON operations

        Raises:
            OSError: If base directory cannot be created or accessed
        """
        # Use StorageConfigService named domain methods for configuration

        if self.provider_name.startswith("system_json"):
            base_dir = self.configuration["base_directory"]
            encoding = self.configuration["encoding"] or "utf-8"
            indent = self.configuration["indent"] or 2

        else:

            json_config = self.configuration.get_json_config()

            encoding = json_config.get("encoding", "utf-8")
            indent = json_config.get("indent", 2)

            # Determine base directory based on injection or configuration
            if self._base_directory:
                # System storage: use injected base_directory directly
                base_dir = self._base_directory
                self._logger.debug(
                    f"[{self.provider_name}] Using injected base directory: {base_dir}"
                )
            else:
                # User storage: use StorageConfigService paths
                # Additional validation for fail-fast behavior
                if not self.configuration.is_json_storage_enabled():
                    raise OSError("JSON storage is not enabled in configuration")

                # Use the path accessor with business logic (already ensures directory exists)
                base_dir = str(self.configuration.get_json_data_path())
                self._logger.debug(
                    f"[{self.provider_name}] Using configured base directory: {base_dir}"
                )

        return {
            "base_directory": base_dir,
            "encoding": encoding,
            "indent": indent,
        }

    def _perform_health_check(self) -> bool:
        """
        Perform health check for JSON storage.

        Checks if base directory is accessible and we can perform
        basic JSON operations.

        Returns:
            True if healthy, False otherwise
        """
        try:
            base_dir = self.client["base_directory"]

            # Check if directory exists and is writable
            if not os.path.exists(base_dir):
                return False

            if not os.access(base_dir, os.W_OK):
                return False

            # Test basic JSON operation
            test_data = {"test": [1, 2, 3]}
            test_str = json.dumps(test_data)
            test_parsed = json.loads(test_str)

            if test_parsed.get("test")[0] != 1:
                return False

            return True
        except Exception as e:
            self._logger.debug(f"JSON health check failed: {e}")
            return False

    def _get_file_path(self, collection: str) -> str:
        """
        Get full file path for a collection.

        Uses base class path resolution with file_path_service validation.
        Enhanced with StorageConfigService collection support.

        Args:
            collection: Collection name (can be relative or absolute path)

        Returns:
            Full file path validated by file_path_service
        """
        # Handle absolute paths directly (legacy support)
        if os.path.isabs(collection):
            return collection

        # Check if this collection has specific configuration (user storage)
        if not self._base_directory and self.configuration.has_collection(
            "json", collection
        ):
            collection_path = self.configuration.get_json_collection_file_path(
                collection
            )
            return str(collection_path)

        # Ensure .json extension for file-based collections
        if not collection.lower().endswith(".json"):
            collection = f"{collection}.json"

        # Use base class get_full_path for proper path resolution and validation
        try:
            return self.get_full_path(collection)
        except ValueError as e:
            self._logger.error(
                f"[{self.provider_name}] Invalid collection path '{collection}': {e}"
            )
            raise

    def _ensure_directory_exists(self, file_path: str) -> None:
        """
        Ensure the directory for a file path exists.

        Args:
            file_path: Path to file
        """
        directory = os.path.dirname(os.path.abspath(file_path))
        os.makedirs(directory, exist_ok=True)

    @contextlib.contextmanager
    def _open_json_file(
        self, file_path: str, mode: str = "r"
    ) -> Generator[TextIO, None, None]:
        """
        Context manager for safely opening JSON files.

        Args:
            file_path: Path to the JSON file
            mode: File open mode ('r' for reading, 'w' for writing)

        Yields:
            File object

        Raises:
            FileNotFoundError: If the file doesn't exist (in read mode)
            PermissionError: If the file can't be accessed
            IOError: For other file-related errors
        """
        try:
            # Ensure directory exists for write operations
            if "w" in mode:
                self._ensure_directory_exists(file_path)

            with open(file_path, mode, encoding=self.client["encoding"]) as f:
                yield f
        except FileNotFoundError:
            if "r" in mode:
                self._logger.debug(f"JSON file not found: {file_path}")
                raise
            else:
                # For write mode, create the file
                self._ensure_directory_exists(file_path)
                with open(file_path, "w", encoding=self.client["encoding"]) as f:
                    yield f
        except (PermissionError, IOError) as e:
            self._logger.error(f"File access error for {file_path}: {str(e)}")
            raise

    def _read_json_file(self, file_path: str, **kwargs) -> Any:
        """
        Read and parse a JSON file.

        Args:
            file_path: Path to the JSON file
            **kwargs: Additional json.load parameters

        Returns:
            Parsed JSON data

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the file contains invalid JSON
        """
        try:
            with self._open_json_file(file_path, "r") as f:
                return json.load(f, **kwargs)
        except FileNotFoundError:
            self._logger.debug(f"JSON file not found: {file_path}")
            raise FileNotFoundError(f"File not found: {file_path}")
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in {file_path}: {str(e)}"
            self._logger.error(error_msg)
            raise ValueError(error_msg)

    def _write_json_file(self, file_path: str, data: Any, **kwargs) -> None:
        """
        Write data to a JSON file.

        Args:
            file_path: Path to the JSON file
            data: Data to write
            **kwargs: Additional json.dump parameters

        Raises:
            PermissionError: If the file can't be written
            TypeError: If the data contains non-serializable objects
        """
        try:
            # Extract indent from client config if not provided
            indent = kwargs.pop("indent", self.client.get("indent", 2))

            with self._open_json_file(file_path, "w") as f:
                json.dump(data, f, indent=indent, **kwargs)
            self._logger.debug(f"Successfully wrote to {file_path}")
        except TypeError as e:
            error_msg = f"Cannot serialize to JSON: {str(e)}"
            self._logger.error(error_msg)
            raise ValueError(error_msg)

    def _apply_path(self, data: Any, path: str) -> Any:
        """
        Extract data from a nested structure using dot notation.

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
            path: Dot-notation path (e.g., "user.address.city")
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

                # Create a nested structure if needed
                if current[index] is None:
                    if i + 1 < len(components) and components[i + 1].isdigit():
                        current[index] = []  # Next level is array
                    else:
                        current[index] = {}  # Next level is dict

                current = current[index]

            # Handle dictionary keys
            else:
                # Create nested structure if needed
                if not isinstance(current, dict):
                    if isinstance(current, list):
                        # We can't modify the structure type
                        return result
                    else:
                        # Replace with dict
                        current = {}

                # Create the next level if it doesn't exist
                if component not in current:
                    if i + 1 < len(components) and components[i + 1].isdigit():
                        current[component] = []  # Next level is array
                    else:
                        current[component] = {}  # Next level is dict

                current = current[component]

        # Set the value at the final path component
        last_component = components[-1]

        # Handle array indices
        if last_component.isdigit() and isinstance(current, list):
            index = int(last_component)
            # Extend the list if needed
            while len(current) <= index:
                current.append(None)
            current[index] = value
        # Handle dictionary keys
        elif isinstance(current, dict):
            current[last_component] = value
        # Can't set the value in this structure
        else:
            return result

        return result

    def _delete_path(self, data: Any, path: str) -> Any:
        """
        Delete data at a specified path.

        Args:
            data: Data structure to modify
            path: Dot-notation path (e.g., "user.address.city")

        Returns:
            Updated data structure with value removed
        """
        if not path or data is None:
            return data

        # Make a copy to avoid modifying original
        if isinstance(data, dict):
            result = data.copy()
        elif isinstance(data, list):
            result = data.copy()
        else:
            # Cannot delete from non-container
            return data

        components = path.split(".")

        # Special case: direct key in dict
        if len(components) == 1 and isinstance(result, dict):
            if components[0] in result:
                del result[components[0]]
            return result

        # Special case: direct index in list
        if (
            len(components) == 1
            and components[0].isdigit()
            and isinstance(result, list)
        ):
            index = int(components[0])
            if 0 <= index < len(result):
                result.pop(index)
            return result

        # For nested paths, navigate to the parent
        current = result
        for i, component in enumerate(components[:-1]):
            # Handle array indices
            if component.isdigit() and isinstance(current, list):
                index = int(component)
                if 0 <= index < len(current):
                    current = current[index]
                else:
                    # Path doesn't exist
                    return result
            # Handle dictionary keys
            elif isinstance(current, dict) and component in current:
                current = current[component]
            else:
                # Path doesn't exist
                return result

        # Delete from parent
        last_component = components[-1]

        # Handle array indices
        if last_component.isdigit() and isinstance(current, list):
            index = int(last_component)
            if 0 <= index < len(current):
                current.pop(index)
        # Handle dictionary keys
        elif isinstance(current, dict) and last_component in current:
            del current[last_component]

        return result

    def _find_document_by_id(
        self, data: Any, document_id: str, id_field: str = "id"
    ) -> Optional[Any]:
        """
        Find a document by ID in direct storage.

        With direct storage, the document_id is the storage key and user data
        is stored directly as the value. No wrapping or unwrapping needed.

        Args:
            data: JSON data structure
            document_id: Document ID to find (storage key)
            id_field: Unused parameter (kept for backwards compatibility)

        Returns:
            Document data or None if not found
        """
        if not data:
            return None

        if isinstance(data, dict):
            # Direct storage: Direct key lookup
            # document_id is the storage key, user data is stored directly
            if document_id in data:
                return data[document_id]

        # For direct storage, lists don't support direct ID lookup
        # List-based searching should use query mechanisms instead
        return None

    def _ensure_id_in_document(
        self, data: Any, document_id: str, id_field: str = "id"
    ) -> Any:
        """
        Return document data as-is for direct storage.

        With direct storage, user data is stored exactly as provided without wrapping.
        The document_id serves as the storage key, and user data is the value.

        Args:
            data: Document data (any type)
            document_id: Document ID (used only as storage key)
            id_field: Field name (ignored - legacy parameter)

        Returns:
            Document data unchanged
        """
        # Direct storage: return user data as-is
        return data

    def _create_initial_structure(
        self, data: Any, document_id: str, id_field: str = "id"
    ) -> Any:
        """
        Create an initial data structure for a document using direct storage.

        Creates a simple dict structure with document_id as key and data as value.

        Args:
            data: Document data
            document_id: Document ID
            id_field: Field name to use as document identifier (unused)

        Returns:
            New data structure: {document_id: data}
        """
        # Direct storage: store data as-is
        processed_data = self._ensure_id_in_document(data, document_id, id_field)

        # Create dict structure with document_id as key
        return {document_id: processed_data}

    def _add_document_to_structure(
        self, data: Any, doc_data: Any, document_id: str, id_field: str = "id"
    ) -> Any:
        """
        Add a document to an existing data structure using direct storage.

        Args:
            data: Current data structure
            doc_data: Document data
            document_id: Document ID
            id_field: Field name to use as document identifier (unused)

        Returns:
            Updated data structure
        """
        # Direct storage: store document data as-is
        processed_doc = self._ensure_id_in_document(doc_data, document_id, id_field)

        if isinstance(data, dict):
            # For dict structures, store under document_id key
            data[document_id] = processed_doc
            return data
        elif isinstance(data, list):
            # For list structures, append document
            data.append(processed_doc)
            return data
        else:
            # Create new dictionary structure
            return {document_id: processed_doc}

    def _add_document_to_structure_simple(
        self, data: Any, doc_data: Any, document_id: str
    ) -> Any:
        """
        Add a document to an existing data structure (simple version).

        Args:
            data: Current data structure
            doc_data: Document data
            document_id: Document ID

        Returns:
            Updated data structure
        """
        # Use the main method with default id_field
        return self._add_document_to_structure(data, doc_data, document_id)

    def _update_document_in_structure(
        self,
        data: Any,
        doc_data: Any,
        document_id: str,
        id_field: str = "id",
        merge: bool = True,
    ) -> tuple[Any, bool]:
        """
        Update a document in an existing data structure.

        Args:
            data: Current data structure
            doc_data: Document data
            document_id: Document ID
            id_field: Field name to use as document identifier
            merge: Whether to merge with existing document or replace entirely

        Returns:
            Tuple of (updated data, whether document was created)
        """
        # Find existing document
        doc = self._find_document_by_id(data, document_id, id_field)
        created_new = False

        # Direct storage: store document data as-is
        processed_doc = self._ensure_id_in_document(doc_data, document_id, id_field)

        if doc is None:
            # Document not found, add it
            created_new = True
            data = self._add_document_to_structure(
                data, doc_data, document_id, id_field
            )
        else:
            # Document exists, update it
            if isinstance(data, dict):
                # Dictionary with direct keys
                if document_id in data:
                    # Merge existing document with new data for UPDATE operations
                    existing_doc = data[document_id]
                    if (
                        isinstance(existing_doc, dict)
                        and isinstance(processed_doc, dict)
                        and merge
                    ):
                        data[document_id] = self._merge_documents(
                            existing_doc, processed_doc
                        )
                    else:
                        # Replace entirely
                        data[document_id] = processed_doc
                else:
                    # Find and update by ID field
                    for key, value in data.items():
                        if (
                            isinstance(value, dict)
                            and value.get(id_field) == document_id
                        ):
                            if (
                                isinstance(value, dict)
                                and isinstance(processed_doc, dict)
                                and merge
                            ):
                                merged_doc = self._merge_documents(value, processed_doc)
                                data[key] = merged_doc
                            else:
                                data[key] = processed_doc
                            break

            elif isinstance(data, list):
                # Direct storage doesn't support ID-based updates in lists
                # List updates should use query mechanisms or direct indexing
                pass

        return data, created_new

    def _merge_documents(
        self, doc1: Dict[str, Any], doc2: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge two documents recursively.

        Args:
            doc1: First document
            doc2: Second document

        Returns:
            Merged document
        """
        if not isinstance(doc1, dict) or not isinstance(doc2, dict):
            return doc2

        result = doc1.copy()

        for key, value in doc2.items():
            # If both values are dicts, merge recursively
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._merge_documents(result[key], value)
            # Otherwise, overwrite or add
            else:
                result[key] = value

        return result

    def _apply_query_filter(self, data: Any, query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply query filtering to document data.

        Args:
            data: Document data
            query: Query parameters

        Returns:
            Dict with filtered data and metadata
        """
        # Extract special query parameters
        limit = query.pop("limit", None)
        offset = query.pop("offset", 0)
        sort_field = query.pop("sort", None)
        sort_order = query.pop("order", "asc").lower()

        # Handle empty data
        if data is None:
            return {"data": None, "count": 0, "is_collection": False}

        # Handle different data structures
        if isinstance(data, list):
            # Apply field filtering
            result = data
            if query:  # Only filter if there are query parameters remaining
                result = [
                    item
                    for item in result
                    if isinstance(item, dict)
                    and all(item.get(field) == value for field, value in query.items())
                ]

            # Apply sorting
            if sort_field and result:
                reverse = sort_order == "desc"
                result.sort(
                    key=lambda x: x.get(sort_field) if isinstance(x, dict) else None,
                    reverse=reverse,
                )

            # Apply pagination
            if offset and isinstance(offset, int) and offset > 0:
                result = result[offset:]

            if limit and isinstance(limit, int) and limit > 0:
                result = result[:limit]

            return {"data": result, "count": len(result), "is_collection": True}

        elif isinstance(data, dict):
            # Filter based on field values
            result = {}
            for key, value in data.items():
                if isinstance(value, dict) and all(
                    value.get(field) == query_value
                    for field, query_value in query.items()
                ):
                    result[key] = value

            # Apply pagination to keys
            keys = list(result.keys())

            if offset and isinstance(offset, int) and offset > 0:
                keys = keys[offset:]

            if limit and isinstance(limit, int) and limit > 0:
                keys = keys[:limit]

            # Rebuild filtered dictionary
            if offset or limit:
                result = {k: result[k] for k in keys}

            return {"data": result, "count": len(result), "is_collection": True}

        # Other data types can't be filtered
        return {"data": data, "count": 0, "is_collection": False}

    def read(
        self,
        collection: str,
        document_id: Optional[str] = None,
        query: Optional[Dict[str, Any]] = None,
        path: Optional[str] = None,
        **kwargs,
    ) -> Any:
        """
        Read data from JSON file.

        Args:
            collection: JSON file name/path
            document_id: Document ID to read
            query: Query parameters for filtering
            path: Dot-notation path for nested access
            **kwargs: Additional parameters

        Returns:
            Document data based on query and path
        """
        try:
            file_path = self._get_file_path(collection)

            if not os.path.exists(file_path):
                self._logger.debug(f"JSON file does not exist: {file_path}")
                return None

            # Extract service-specific parameters
            format_type = kwargs.pop("format", "raw")
            id_field = kwargs.pop("id_field", "id")

            # Read the JSON file
            data = self._read_json_file(file_path, **kwargs)

            # Apply document_id filter
            if document_id is not None:
                doc = self._find_document_by_id(data, document_id, id_field)
                if doc is None:
                    return None

                # With direct storage, return document data as-is
                # Apply path extraction if needed
                if path:
                    return self._apply_path(doc, path)

                return doc

            # Apply path extraction (at collection level)
            if path:
                data = self._apply_path(data, path)
                if data is None:
                    return None

            # Apply query filters
            if query:
                filtered_result = self._apply_query_filter(data, query)
                data = filtered_result.get("data", data)

            # Return format based on request
            if format_type == "records" and isinstance(data, dict):
                return list(data.values())
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
        Write data to JSON file.

        Args:
            collection: JSON file name/path
            data: Data to write
            document_id: Document ID
            mode: Write mode (write, append, update, merge)
            path: Dot-notation path for nested updates
            **kwargs: Additional parameters

        Returns:
            StorageResult with operation details
        """
        # Validate mode parameter
        if not isinstance(mode, WriteMode):
            return self._create_error_result(
                "write", f"Unsupported write mode: {mode}", collection=collection
            )

        try:
            file_path = self._get_file_path(collection)

            # Extract service-specific parameters
            id_field = kwargs.pop("id_field", "id")

            file_existed = os.path.exists(file_path)

            if mode == WriteMode.WRITE:
                # Simple write operation
                if document_id is not None:
                    # For document-based writes, read existing file and add/update document
                    current_data = None
                    if file_existed:
                        try:
                            current_data = self._read_json_file(file_path)
                        except (FileNotFoundError, ValueError):
                            current_data = None

                    # Create initial structure if needed
                    if current_data is None:
                        current_data = self._create_initial_structure(
                            data, document_id, id_field
                        )
                    else:
                        # Add document to existing structure with user data unchanged
                        current_data = self._add_document_to_structure_simple(
                            current_data, data, document_id
                        )

                    self._write_json_file(file_path, current_data, **kwargs)
                else:
                    # Direct write (overwrite entire file)
                    self._write_json_file(file_path, data, **kwargs)

                return self._create_success_result(
                    "write",
                    collection=collection,
                    document_id=document_id,
                    file_path=file_path,
                    created_new=not file_existed,
                )

            # Handle updating existing files
            current_data = None
            if file_existed:
                try:
                    current_data = self._read_json_file(file_path)
                except (FileNotFoundError, ValueError):
                    current_data = None

            if mode == WriteMode.UPDATE:
                # Update operation - fail if file or document doesn't exist
                if not file_existed:
                    return self._create_error_result(
                        "update",
                        f"File not found for update: {file_path}",
                        collection=collection,
                    )

                if current_data is None:
                    return self._create_error_result(
                        "update",
                        f"Invalid JSON data in file: {file_path}",
                        collection=collection,
                    )

                if path:
                    # Path-based update
                    if document_id:
                        # Update path in specific document
                        doc = self._find_document_by_id(
                            current_data, document_id, id_field
                        )
                        if doc is None:
                            return self._create_error_result(
                                "update",
                                f"Document with ID '{document_id}' not found for update",
                                collection=collection,
                                document_id=document_id,
                            )

                        # Update existing document
                        updated_doc = self._update_path(doc, path, data)
                        current_data = self._update_document_in_structure(
                            current_data, updated_doc, document_id, id_field
                        )[0]
                    else:
                        # Update path in entire file
                        current_data = self._update_path(current_data, path, data)
                else:
                    # Direct document update
                    if document_id is not None:
                        # Update specific document - must exist
                        doc = self._find_document_by_id(
                            current_data, document_id, id_field
                        )
                        if doc is None:
                            return self._create_error_result(
                                "update",
                                f"Document with ID '{document_id}' not found for update",
                                collection=collection,
                                document_id=document_id,
                            )

                        current_data, created_new = self._update_document_in_structure(
                            current_data, data, document_id, id_field
                        )
                    else:
                        # Update entire file
                        current_data = data

                self._write_json_file(file_path, current_data, **kwargs)
                return self._create_success_result(
                    "update",
                    collection=collection,
                    document_id=document_id,
                    file_path=file_path,
                    created_new=not file_existed,
                )

            # Use appropriate structure if file doesn't exist or has invalid data
            # (Only for non-UPDATE modes)
            if current_data is None:
                if document_id is not None:
                    current_data = self._create_initial_structure(
                        data, document_id, id_field
                    )
                else:
                    current_data = [] if isinstance(data, list) else {}

            elif mode == WriteMode.APPEND:
                # Append operation
                if isinstance(current_data, list) and isinstance(data, list):
                    # Append to list
                    current_data.extend(data)
                elif isinstance(current_data, list):
                    # Append single item to list
                    current_data.append(data)
                elif isinstance(current_data, dict) and isinstance(data, dict):
                    # Merge dictionaries
                    current_data.update(data)
                elif document_id is not None:
                    # Add document with ID - store user data unchanged
                    current_data = self._add_document_to_structure_simple(
                        current_data, data, document_id
                    )
                else:
                    # Can't append to incompatible structures
                    return self._create_error_result(
                        "append",
                        "Cannot append to incompatible data structure",
                        collection=collection,
                    )

                self._write_json_file(file_path, current_data, **kwargs)
                return self._create_success_result(
                    "append",
                    collection=collection,
                    document_id=document_id,
                    file_path=file_path,
                )

            else:
                return self._create_error_result(
                    "write", f"Unsupported write mode: {mode}", collection=collection
                )

        except Exception as e:
            error_msg = f"Write operation failed: {str(e)}"
            self._logger.error(
                f"[{self.provider_name}] {error_msg} (collection={collection}, mode={mode.value})"
            )
            return self._create_error_result("write", error_msg, collection=collection)

    def delete(
        self,
        collection: str,
        document_id: Optional[str] = None,
        path: Optional[str] = None,
        query: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> StorageResult:
        """
        Delete from JSON file.

        Args:
            collection: JSON file name/path
            document_id: Document ID to delete
            path: Dot-notation path to delete
            query: Query for batch delete
            **kwargs: Additional parameters

        Returns:
            StorageResult with operation details
        """
        try:
            file_path = self._get_file_path(collection)

            # Extract service-specific parameters
            id_field = kwargs.pop("id_field", "id")

            if not os.path.exists(file_path):
                return self._create_error_result(
                    "delete", f"File not found: {file_path}", collection=collection
                )

            # Read current data
            current_data = self._read_json_file(file_path)
            if current_data is None:
                return self._create_error_result(
                    "delete",
                    f"Invalid JSON data in file: {file_path}",
                    collection=collection,
                )

            # Handle deleting entire file
            if document_id is None and path is None and not query:
                os.remove(file_path)
                return self._create_success_result(
                    "delete",
                    collection=collection,
                    file_path=file_path,
                    collection_deleted=True,
                )

            # Handle deleting specific path
            if path:
                if document_id:
                    # Delete path in specific document
                    doc = self._find_document_by_id(current_data, document_id, id_field)
                    if doc is None:
                        return self._create_error_result(
                            "delete",
                            f"Document with ID '{document_id}' not found",
                            collection=collection,
                            document_id=document_id,
                        )

                    # For direct storage: delete path from document data directly
                    updated_doc = self._delete_path(doc, path)

                    current_data = self._update_document_in_structure(
                        current_data, updated_doc, document_id, id_field, merge=False
                    )[0]
                else:
                    # Delete path in entire file
                    current_data = self._delete_path(current_data, path)

                self._write_json_file(file_path, current_data)
                return self._create_success_result(
                    "delete",
                    collection=collection,
                    document_id=document_id,
                    file_path=file_path,
                    path=path,
                )

            # Handle deleting document by ID
            if document_id is not None:
                deleted = False

                if isinstance(current_data, dict):
                    # Remove from dictionary
                    if document_id in current_data:
                        del current_data[document_id]
                        deleted = True
                    else:
                        # Look for document with matching ID field
                        keys_to_delete = []
                        for key, value in current_data.items():
                            if (
                                isinstance(value, dict)
                                and value.get(id_field) == document_id
                            ):
                                keys_to_delete.append(key)
                                deleted = True

                        for key in keys_to_delete:
                            del current_data[key]

                elif isinstance(current_data, list):
                    # Remove from list
                    original_length = len(current_data)
                    current_data = [
                        item
                        for item in current_data
                        if not (
                            isinstance(item, dict) and item.get(id_field) == document_id
                        )
                    ]
                    deleted = len(current_data) < original_length

                if not deleted:
                    return self._create_error_result(
                        "delete",
                        f"Document with ID '{document_id}' not found",
                        collection=collection,
                        document_id=document_id,
                    )

                self._write_json_file(file_path, current_data)
                return self._create_success_result(
                    "delete",
                    collection=collection,
                    file_path=file_path,
                    document_id=document_id,
                )

            # Handle batch delete with query
            if query and isinstance(current_data, list):
                original_length = len(current_data)

                # Apply query filters
                filtered_result = self._apply_query_filter(current_data, query)
                filtered_data = filtered_result.get("data", [])

                # Keep track of deleted documents
                deleted_ids = []
                for item in current_data:
                    if (
                        isinstance(item, dict)
                        and item.get(id_field)
                        and item not in filtered_data
                    ):
                        deleted_ids.append(item.get(id_field))

                # Write back the filtered data
                self._write_json_file(file_path, filtered_data)

                return self._create_success_result(
                    "delete",
                    collection=collection,
                    file_path=file_path,
                    total_affected=original_length - len(filtered_data),
                    deleted_ids=deleted_ids,
                )

            return self._create_error_result(
                "delete", "Invalid delete operation", collection=collection
            )

        except Exception as e:
            error_msg = f"Delete operation failed: {str(e)}"
            self._logger.error(
                f"[{self.provider_name}] {error_msg} (collection={collection})"
            )
            return self._create_error_result("delete", error_msg, collection=collection)

    def exists(
        self,
        collection: str,
        document_id: Optional[str] = None,
        path: Optional[str] = None,
        **kwargs,
    ) -> bool:
        """
        Check if JSON file, document, or path exists.

        Args:
            collection: JSON file name/path
            document_id: Document ID to check
            path: Dot-notation path to check
            **kwargs: Additional parameters

        Returns:
            True if exists, False otherwise
        """
        try:
            file_path = self._get_file_path(collection)

            if not os.path.exists(file_path):
                return False

            # Extract service-specific parameters
            id_field = kwargs.pop("id_field", "id")

            # Check file existence only
            if document_id is None and path is None:
                return True

            # Read the file
            data = self._read_json_file(file_path)
            if data is None:
                return False

            # Check document existence
            if document_id is not None:
                doc = self._find_document_by_id(data, document_id, id_field)
                if doc is None:
                    return False

                # Check path in document
                if path:
                    value = self._apply_path(doc, path)
                    return value is not None

                return True

            # Check path existence in file
            if path:
                value = self._apply_path(data, path)
                return value is not None

            return True

        except Exception as e:
            self._logger.debug(f"Error checking existence: {e}")
            return False

    def count(
        self,
        collection: str,
        query: Optional[Dict[str, Any]] = None,
        path: Optional[str] = None,
        **kwargs,
    ) -> int:
        """
        Count documents or items in JSON file.

        Args:
            collection: JSON file name/path
            query: Optional query parameters for filtering
            path: Optional path for nested counting
            **kwargs: Additional parameters

        Returns:
            Count of items
        """
        try:
            file_path = self._get_file_path(collection)

            if not os.path.exists(file_path):
                return 0

            # Read the file
            data = self._read_json_file(file_path)
            if data is None:
                return 0

            # Apply path extraction
            if path:
                data = self._apply_path(data, path)
                if data is None:
                    return 0

            # Apply query filtering
            if query:
                filtered_result = self._apply_query_filter(data, query)
                data = filtered_result.get("data", data)
                return filtered_result.get("count", 0)

            # Count based on data type
            if isinstance(data, list):
                return len(data)
            elif isinstance(data, dict):
                return len(data)
            else:
                return 1  # Scalar values count as 1

        except Exception as e:
            self._logger.debug(f"Error counting items: {e}")
            return 0

    def list_collections(self, **kwargs) -> List[str]:
        """
        List all JSON collections, including both configured collections and discovered files.

        Enhanced with StorageConfigService integration to include:
        - Configured collections from StorageConfigService
        - JSON files found in the data directory

        Args:
            **kwargs: Additional parameters

        Returns:
            List of JSON collection names (without .json extension for configured collections)
        """
        try:
            collections = set()

            # Add configured collections from StorageConfigService
            try:
                configured_collections = self.configuration.list_collections("json")
                collections.update(configured_collections)
            except Exception as e:
                self._logger.debug(f"Could not load configured JSON collections: {e}")

            # Add JSON files found in directory
            base_dir = self.client["base_directory"]
            if os.path.exists(base_dir):
                for item in os.listdir(base_dir):
                    if item.lower().endswith(".json"):
                        # Remove .json extension for consistency with configured collections
                        collection_name = (
                            item[:-5] if item.lower().endswith(".json") else item
                        )
                        collections.add(collection_name)

            return sorted(list(collections))

        except Exception as e:
            self._logger.debug(f"Error listing collections: {e}")
            return []
