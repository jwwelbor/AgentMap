# agentmap/agents/builtins/storage/json_document_writer_agent.py

import functools
import os
from typing import Any, Dict, Optional, Tuple, Union

from agentmap.agents.builtins.storage.base_document_storage_agent import (
    DocumentResult, WriteMode)
from agentmap.agents.builtins.storage.document_writer_agent import \
    DocumentWriterAgent
from agentmap.agents.builtins.storage.json_document_agent import \
    JSONDocumentAgent
from agentmap.logging import get_logger

logger = get_logger(__name__)


def log_operation(func):
    """Decorator to log document operations."""
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        logger.debug(f"[{self.__class__.__name__}] Starting {func.__name__}")
        try:
            result = func(self, *args, **kwargs)
            logger.debug(f"[{self.__class__.__name__}] Completed {func.__name__}")
            return result
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] Error in {func.__name__}: {str(e)}")
            raise
    return wrapper


class JSONDocumentWriterAgent(DocumentWriterAgent, JSONDocumentAgent):
    """
    Agent for writing data to JSON documents.
    
    Provides functionality for writing to JSON files, including
    document creation, updates, merges, and deletions.
    """
    
    @log_operation
    def _write_document(
        self, 
        collection: str, 
        data: Any, 
        document_id: Optional[str] = None,
        mode: Union[WriteMode, str] = WriteMode.WRITE, 
        path: Optional[str] = None
    ) -> DocumentResult:
        """
        Write a document to a JSON file.
        
        Args:
            collection: Path to the JSON file
            data: Data to write
            document_id: Optional document ID
            mode: Write mode (write, update, merge, delete)
            path: Optional path within document
            
        Returns:
            Result of the write operation
        """
        # Convert string mode to enum if needed
        if isinstance(mode, str):
            mode = WriteMode.from_string(mode)
        
        # Mode dispatch dictionary
        mode_handlers = {
            WriteMode.WRITE.value: self._write_mode_create,
            WriteMode.UPDATE.value: self._write_mode_update,
            WriteMode.MERGE.value: self._write_mode_merge,
            WriteMode.DELETE.value: self._write_mode_delete
        }
        
        # Look up handler by mode value
        handler = mode_handlers.get(mode.value)
        
        if handler:
            if handler in [self._write_mode_update, self._write_mode_merge, self._write_mode_delete]:
                return handler(collection, data, document_id, path)
            else:
                return handler(collection, data, document_id)
        else:
            self._handle_error("Invalid Mode", f"Unsupported write mode: {mode}")
    
    def _write_mode_create(
        self, 
        collection: str, 
        data: Any, 
        document_id: Optional[str] = None
    ) -> DocumentResult:
        """
        Write mode: Create or overwrite.
        
        Args:
            collection: Path to the JSON file
            data: Data to write
            document_id: Optional document ID
            
        Returns:
            Result of the write operation
        """
        file_exists = os.path.exists(collection)
        
        # Handle document ID
        if document_id:
            # If file exists, read and update specific document
            if file_exists:
                current_data = self._read_json_file(collection)
                if current_data is None:
                    current_data = {}
                    
                updated_data = self._add_document_to_structure(
                    current_data, data, document_id
                )
                self._write_json_file(collection, updated_data)
            else:
                # Create new file with document
                self._write_json_file(
                    collection, 
                    self._create_initial_structure(data, document_id)
                )
        else:
            # No document ID - write directly
            self._write_json_file(collection, data)
        
        return DocumentResult({
            "success": True,
            "mode": "write",
            "file_path": collection,
            "document_id": document_id,
            "created_new": not file_exists
        })
    
    def _write_mode_update(
        self, 
        collection: str, 
        data: Any, 
        document_id: Optional[str] = None,
        path: Optional[str] = None
    ) -> DocumentResult:
        """
        Write mode: Update existing data.
        
        Args:
            collection: Path to the JSON file
            data: Data to write
            document_id: Optional document ID
            path: Optional path within document
            
        Returns:
            Result of the write operation
        """
        file_exists = os.path.exists(collection)
        
        # Handle path updates
        if path:
            return self._update_document_path_at_file(
                collection, data, document_id, path, file_exists
            )
        
        # Handle document ID updates
        if document_id:
            return self._update_document_by_id(
                collection, data, document_id, file_exists
            )
        
        # Direct file update (overwrite)
        self._write_json_file(collection, data)
        return DocumentResult({
            "success": True,
            "mode": "update",
            "file_path": collection,
            "created_new": not file_exists
        })
    
    def _update_document_path_at_file(
        self, 
        collection: str, 
        data: Any, 
        document_id: Optional[str],
        path: str, 
        file_exists: bool
    ) -> DocumentResult:
        """
        Update a specific path in a document or file.
        
        Args:
            collection: Path to the JSON file
            data: Data to write
            document_id: Optional document ID
            path: Path within document
            file_exists: Whether the file exists
            
        Returns:
            Result of the update operation
        """
        if file_exists:
            current_data = self._read_json_file(collection)
            if current_data is None:
                current_data = {} if not document_id else []
                
            # If document ID provided, update that specific document
            if document_id:
                doc = self._find_document_by_id(current_data, document_id)
                if doc is None:
                    # Document not found, create it
                    if isinstance(current_data, list):
                        new_doc = {"id": document_id}
                        new_doc = self._update_path(new_doc, path, data)
                        current_data.append(new_doc)
                    else:
                        current_data[document_id] = self._update_path({}, path, data)
                else:
                    # Update document at path
                    self._update_document_in_place(
                        current_data, doc, document_id, path, data
                    )
            else:
                # Update whole file at path
                current_data = self._update_path(current_data, path, data)
                
            self._write_json_file(collection, current_data)
        else:
            # File doesn't exist, create with nested structure
            if document_id:
                new_doc = {"id": document_id}
                new_doc = self._update_path(new_doc, path, data)
                self._write_json_file(collection, [new_doc])
            else:
                new_data = self._update_path({}, path, data)
                self._write_json_file(collection, new_data)
        
        return DocumentResult({
            "success": True,
            "mode": "update",
            "file_path": collection,
            "document_id": document_id,
            "path": path,
            "created_new": not file_exists
        })
    
    def _update_document_by_id(
        self, 
        collection: str, 
        data: Any, 
        document_id: str,
        file_exists: bool
    ) -> DocumentResult:
        """Update a document by ID."""
        if not file_exists:
            # For new files, create with a single document
            new_doc = self._ensure_id_in_document(data, document_id)
            self._write_json_file(collection, [new_doc] if isinstance(new_doc, dict) else {document_id: data})
            return DocumentResult({
                "success": True,
                "mode": "update",
                "file_path": collection,
                "document_id": document_id,
                "created_new": True
            })
        
        # Handle existing files
        current_data = self._read_json_file(collection)
        if current_data is None:
            current_data = [] if self._should_use_list_format(data) else {}
        
        created_new = False
        
        # Handle list vs dictionary formats differently
        if isinstance(current_data, list):
            created_new = self._update_document_in_list(current_data, data, document_id)
        else:
            # Dictionary format
            created_new = document_id not in current_data
            current_data[document_id] = data
        
        # Write the updated data back to file
        self._write_json_file(collection, current_data)
        
        return DocumentResult({
            "success": True,
            "mode": "update",
            "file_path": collection,
            "document_id": document_id,
            "document_created": created_new
        })

    def _update_document_in_list(self, documents: list, data: Any, document_id: str) -> bool:
        """Update a document in a list structure, returning whether a new document was created."""
        # Find the document index
        for i, doc in enumerate(documents):
            if isinstance(doc, dict) and doc.get("id") == document_id:
                # Found the document, update it
                documents[i] = self._ensure_id_in_document(data, document_id)
                return False  # Not a new document
        
        # Document not found, append it
        documents.append(self._ensure_id_in_document(data, document_id))
        return True  # New document created

    def _ensure_id_in_document(self, data: Any, document_id: str) -> dict:
        """Ensure the document has the correct ID field."""
        if not isinstance(data, dict):
            return {"id": document_id, "value": data}
        
        result = data.copy()
        result["id"] = document_id
        return result

    def _should_use_list_format(self, data: Any) -> bool:
        """Determine if we should use list format based on data type."""
        return isinstance(data, dict)    
    def _write_mode_merge(
        self, 
        collection: str, 
        data: Any, 
        document_id: Optional[str] = None,
        path: Optional[str] = None
    ) -> DocumentResult:
        """
        Write mode: Merge with existing data.
        
        Args:
            collection: Path to the JSON file
            data: Data to write
            document_id: Optional document ID
            path: Optional path within document
            
        Returns:
            Result of the merge operation
        """
        file_exists = os.path.exists(collection)
        
        if file_exists:
            current_data = self._read_json_file(collection)
            if current_data is None:
                current_data = {}
                
            # Handle path-specific merge
            if path:
                return self._merge_document_at_path(
                    collection, current_data, data, document_id, path
                )
            
            # Handle document ID merge
            if document_id:
                return self._merge_document_by_id(
                    collection, current_data, data, document_id
                )
            
            # Merge with entire file
            if isinstance(current_data, dict) and isinstance(data, dict):
                merged_data = self._merge_documents(current_data, data)
                self._write_json_file(collection, merged_data)
            else:
                # Can't merge incompatible types, overwrite
                self._write_json_file(collection, data)
        else:
            # File doesn't exist, create new
            if document_id:
                self._write_json_file(
                    collection, 
                    self._create_initial_structure(data, document_id)
                )
            else:
                self._write_json_file(collection, data)
        
        return DocumentResult({
            "success": True,
            "mode": "merge",
            "file_path": collection,
            "document_id": document_id,
            "created_new": not file_exists
        })
    
    def _merge_document_at_path(
        self, 
        collection: str, 
        current_data: Any, 
        data: Any, 
        document_id: Optional[str],
        path: str
    ) -> DocumentResult:
        """
        Merge data at a specific path.
        
        Args:
            collection: Path to the JSON file
            current_data: Current file data
            data: Data to merge
            document_id: Optional document ID
            path: Path within document
            
        Returns:
            Result of the merge operation
        """
        # Extract current path value
        if document_id:
            doc = self._find_document_by_id(current_data, document_id)
            if doc is None:
                # Document not found, create it
                if isinstance(current_data, list):
                    new_doc = {"id": document_id}
                    new_doc = self._update_path(new_doc, path, data)
                    current_data.append(new_doc)
                else:
                    current_data[document_id] = self._update_path({}, path, data)
            else:
                # Get current value at path
                current_value = self._apply_path(doc, path)
                
                # Merge if both are dictionaries
                if isinstance(current_value, dict) and isinstance(data, dict):
                    merged_value = self._merge_documents(current_value, data)
                    self._update_document_in_place(
                        current_data, doc, document_id, path, merged_value
                    )
                else:
                    # Otherwise, just update
                    self._update_document_in_place(
                        current_data, doc, document_id, path, data
                    )
        else:
            # Get current value at path
            current_value = self._apply_path(current_data, path)
            
            # Merge if both are dictionaries
            if isinstance(current_value, dict) and isinstance(data, dict):
                merged_value = self._merge_documents(current_value, data)
                current_data = self._update_path(current_data, path, merged_value)
            else:
                # Otherwise, just update
                current_data = self._update_path(current_data, path, data)
        
        # Write back to file
        self._write_json_file(collection, current_data)
        
        return DocumentResult({
            "success": True,
            "mode": "merge",
            "file_path": collection,
            "document_id": document_id,
            "path": path
        })
    
    def _merge_document_by_id(
        self, 
        collection: str, 
        current_data: Any, 
        data: Any, 
        document_id: str
    ) -> DocumentResult:
        """
        Merge a document by ID.
        
        Args:
            collection: Path to the JSON file
            current_data: Current file data
            data: Data to merge
            document_id: Document ID
            
        Returns:
            Result of the merge operation
        """
        # Find existing document
        doc = self._find_document_by_id(current_data, document_id)
        
        if doc is None:
            # Document not found, create it
            updated_data, _ = self._update_or_create_document(
                current_data, data, document_id
            )
        else:
            # Merge with existing document
            if isinstance(doc, dict) and isinstance(data, dict):
                merged_doc = self._merge_documents(doc, data)
                self._update_document_in_place(
                    current_data, doc, document_id, None, merged_doc
                )
                updated_data = current_data
            else:
                # Can't merge incompatible types, overwrite
                updated_data, _ = self._update_or_create_document(
                    current_data, data, document_id
                )
        
        # Write back to file
        self._write_json_file(collection, updated_data)
        
        return DocumentResult({
            "success": True,
            "mode": "merge",
            "file_path": collection,
            "document_id": document_id
        })
    
    def _write_mode_delete(
        self, 
        collection: str, 
        data: Any, 
        document_id: Optional[str] = None,
        path: Optional[str] = None
    ) -> DocumentResult:
        """
        Write mode: Delete data.
        
        Args:
            collection: Path to the JSON file
            data: Query data for batch deletes
            document_id: Optional document ID
            path: Optional path within document
            
        Returns:
            Result of the delete operation
        """
        if not os.path.exists(collection):
            return DocumentResult({
                "success": False,
                "mode": "delete",
                "file_path": collection,
                "error": "File not found"
            })
        
        current_data = self._read_json_file(collection)
        if current_data is None:
            return DocumentResult({
                "success": False,
                "mode": "delete",
                "file_path": collection,
                "error": "Invalid JSON data"
            })
        
        # Handle deleting specific path
        if path:
            return self._delete_document_path_at_file(
                collection, current_data, document_id, path
            )
        
        # Handle deleting document by ID
        if document_id:
            return self._delete_document_by_id(
                collection, current_data, document_id
            )
        
        # Handle batch delete with query
        if isinstance(data, dict) and data:
            return self._delete_documents_by_query(
                collection, current_data, data
            )
        
        # Delete entire file
        os.remove(collection)
        return DocumentResult({
            "success": True,
            "mode": "delete",
            "file_path": collection,
            "file_deleted": True
        })
    
    def _delete_document_path_at_file(
        self, 
        collection: str, 
        current_data: Any, 
        document_id: Optional[str],
        path: str
    ) -> DocumentResult:
        """
        Delete data at a specific path.
        
        Args:
            collection: Path to the JSON file
            current_data: Current file data
            document_id: Optional document ID
            path: Path within document
            
        Returns:
            Result of the delete operation
        """
        if document_id:
            # Delete path in specific document
            doc = self._find_document_by_id(current_data, document_id)
            if doc is None:
                return DocumentResult({
                    "success": False,
                    "mode": "delete",
                    "file_path": collection,
                    "document_id": document_id,
                    "path": path,
                    "error": "Document not found"
                })
            
            # Delete path in document
            updated_doc = self._delete_path(doc, path)
            self._update_document_in_place(
                current_data, doc, document_id, None, updated_doc
            )
        else:
            # Delete path in entire file
            current_data = self._delete_path(current_data, path)
        
        # Write back to file
        self._write_json_file(collection, current_data)
        
        return DocumentResult({
            "success": True,
            "mode": "delete",
            "file_path": collection,
            "document_id": document_id,
            "path": path
        })
    
    def _delete_document_by_id(
        self, 
        collection: str, 
        current_data: Any, 
        document_id: str
    ) -> DocumentResult:
        """
        Delete a document by ID.
        
        Args:
            collection: Path to the JSON file
            current_data: Current file data
            document_id: Document ID
            
        Returns:
            Result of the delete operation
        """
        if isinstance(current_data, dict):
            # Dictionary with ID keys
            if document_id in current_data:
                del current_data[document_id]
                self._write_json_file(collection, current_data)
                return DocumentResult({
                    "success": True,
                    "mode": "delete",
                    "file_path": collection,
                    "document_id": document_id
                })
            else:
                return DocumentResult({
                    "success": False,
                    "mode": "delete",
                    "file_path": collection,
                    "document_id": document_id,
                    "error": "Document not found"
                })
        
        elif isinstance(current_data, list):
            # List of documents
            original_length = len(current_data)
            current_data = [
                item for item in current_data 
                if not (isinstance(item, dict) and item.get("id") == document_id)
            ]
            
            if len(current_data) < original_length:
                self._write_json_file(collection, current_data)
                return DocumentResult({
                    "success": True,
                    "mode": "delete",
                    "file_path": collection,
                    "document_id": document_id
                })
            else:
                return DocumentResult({
                    "success": False,
                    "mode": "delete",
                    "file_path": collection,
                    "document_id": document_id,
                    "error": "Document not found"
                })
        
        return DocumentResult({
            "success": False,
            "mode": "delete",
            "file_path": collection,
            "document_id": document_id,
            "error": "Invalid collection format"
        })
    
    def _delete_documents_by_query(
        self, 
        collection: str, 
        current_data: Any, 
        query: Dict[str, Any]
    ) -> DocumentResult:
        """
        Delete documents matching a query.
        
        Args:
            collection: Path to the JSON file
            current_data: Current file data
            query: Query parameters
            
        Returns:
            Result of the delete operation
        """
        if isinstance(current_data, list):
            # Filter out items that match the query
            original_length = len(current_data)
            remaining_items = []
            deleted_ids = []
            
            for item in current_data:
                if isinstance(item, dict):
                    # Check if item matches all query conditions
                    matches = True
                    for field, value in query.items():
                        if item.get(field) != value:
                            matches = False
                            break
                    
                    if matches:
                        # Item matched query, mark for deletion
                        if "id" in item:
                            deleted_ids.append(item["id"])
                    else:
                        # Item didn't match, keep it
                        remaining_items.append(item)
                else:
                    # Not a dict, keep it
                    remaining_items.append(item)
            
            if len(remaining_items) < original_length:
                self._write_json_file(collection, remaining_items)
                return DocumentResult({
                    "success": True,
                    "mode": "delete",
                    "file_path": collection,
                    "deleted_ids": deleted_ids,
                    "count": len(deleted_ids)
                })
            else:
                return DocumentResult({
                    "success": True,
                    "mode": "delete",
                    "file_path": collection,
                    "deleted_ids": [],
                    "count": 0,
                    "message": "No documents matched query"
                })
        
        return DocumentResult({
            "success": False,
            "mode": "delete",
            "file_path": collection,
            "error": "Collection format does not support query deletes"
        })
    
    # Helper methods for document operations
    
    def _find_document_by_id(self, data: Any, document_id: str) -> Optional[Dict]:
        """
        Find a document by ID in different data structures.
        
        Args:
            data: JSON data structure
            document_id: Document ID to find
            
        Returns:
            Document data or None if not found
        """
        if isinstance(data, dict):
            # Direct key lookup
            if document_id in data:
                return data[document_id]
        
        elif isinstance(data, list):
            # Find in array by id field
            for item in data:
                if isinstance(item, dict) and item.get("id") == document_id:
                    return item
        
        return None
    
    def _update_document_in_place(
        self, 
        container: Any, 
        doc: Dict, 
        document_id: str,
        path: Optional[str], 
        value: Any
    ) -> None:
        """
        Update a document in-place within its container.
        
        Args:
            container: Container holding the document
            doc: Document to update
            document_id: Document ID
            path: Optional path within document
            value: New value
        """
        if path:
            # Update at path
            new_doc = self._update_path(doc, path, value)
            
            # Update in container
            if isinstance(container, dict):
                container[document_id] = new_doc
            elif isinstance(container, list):
                # Find and replace in list
                for i, item in enumerate(container):
                    if isinstance(item, dict) and item.get("id") == document_id:
                        container[i] = new_doc
                        break
        else:
            # Replace entire document
            if isinstance(container, dict):
                container[document_id] = value
            elif isinstance(container, list):
                # Find and replace in list
                for i, item in enumerate(container):
                    if isinstance(item, dict) and item.get("id") == document_id:
                        container[i] = value
                        break
    
    def _update_or_create_document(
        self, 
        data: Any, 
        doc_data: Any, 
        document_id: str
    ) -> Tuple[Any, bool]:
        """
        Update a document or create it if it doesn't exist.
        
        Args:
            data: Current data structure
            doc_data: Document data
            document_id: Document ID
            
        Returns:
            Tuple of (updated data, whether document was created)
        """
        # Find existing document
        existing_doc = self._find_document_by_id(data, document_id)
        created_new = False
        
        if existing_doc is None:
            # Document not found, add it
            created_new = True
            data = self._add_document_to_structure(data, doc_data, document_id)
        else:
            # Document exists, update it
            self._update_document_in_place(data, existing_doc, document_id, None, doc_data)
        
        return data, created_new
    
    def _add_document_to_structure(
        self, 
        data: Any, 
        doc_data: Any, 
        document_id: str
    ) -> Any:
        """
        Add a document to an existing data structure.
        
        Args:
            data: Current data structure
            doc_data: Document data
            document_id: Document ID
            
        Returns:
            Updated data structure
        """
        if isinstance(data, dict):
            # Add to dictionary
            data[document_id] = doc_data
            return data
        
        elif isinstance(data, list):
            # Add to list with ID
            if isinstance(doc_data, dict):
                # Make sure document has ID
                doc_with_id = doc_data.copy()
                doc_with_id["id"] = document_id
                data.append(doc_with_id)
            else:
                # Wrap non-dict data
                data.append({"id": document_id, "value": doc_data})
            return data
        
        else:
            # Create new structure
            return self._create_initial_structure(doc_data, document_id)
    
    def _create_initial_structure(self, data: Any, document_id: str) -> Any:
        """
        Create an initial data structure for a document.
        
        Args:
            data: Document data
            document_id: Document ID
            
        Returns:
            New data structure
        """
        if isinstance(data, dict):
            # For dict data, create a list with ID field
            doc_with_id = data.copy()
            doc_with_id["id"] = document_id
            return [doc_with_id]
        else:
            # For other data, use a dict with document ID as key
            return {document_id: data}