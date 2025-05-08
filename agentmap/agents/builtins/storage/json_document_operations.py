"""
JSON document operations for storage agents.

This module provides operations for creating, updating, merging,
and deleting JSON documents.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple, Union

from agentmap.agents.builtins.storage.base_document_storage_agent import DocumentResult, WriteMode
from agentmap.agents.builtins.storage.document_path_mixin import DocumentPathMixin
from agentmap.agents.builtins.storage.json_utils import (
    add_document_to_structure, create_initial_structure, ensure_id_in_document,
    find_document_by_id, read_json_file, write_json_file)
from agentmap.logging import get_logger

logger = get_logger(__name__)


class JSONDocumentOperations(DocumentPathMixin):
    """
    Core operations for JSON document storage.
    
    This class provides methods for creating, updating, merging,
    and deleting JSON documents.
    """
    
    def create_document(
        self, 
        collection: str, 
        data: Any, 
        document_id: Optional[str] = None
    ) -> DocumentResult:
        """
        Create a new document or overwrite an existing one.
        
        Args:
            collection: Path to the JSON file
            data: Data to write
            document_id: Optional document ID
            
        Returns:
            Result of the create operation
        """
        file_exists = os.path.exists(collection)
        
        try:
            # Handle document ID
            if document_id:
                # If file exists, read and update specific document
                if file_exists:
                    current_data = read_json_file(collection)
                    if current_data is None:
                        current_data = {}
                        
                    updated_data = add_document_to_structure(
                        current_data, data, document_id
                    )
                    write_json_file(collection, updated_data)
                else:
                    # Create new file with document
                    write_json_file(
                        collection, 
                        create_initial_structure(data, document_id)
                    )
            else:
                # No document ID - write directly
                write_json_file(collection, data)
                
            return DocumentResult(
                success=True,
                mode=WriteMode.WRITE.value,
                file_path=collection,
                document_id=document_id,
                created_new=not file_exists
            )
            
        except Exception as e:
            return DocumentResult(
                success=False,
                mode=WriteMode.WRITE.value,
                file_path=collection,
                document_id=document_id,
                error=str(e)
            )
    
    def update_document(
        self, 
        collection: str, 
        data: Any, 
        document_id: Optional[str] = None,
        path: Optional[str] = None
    ) -> DocumentResult:
        """
        Update an existing document or create a new one.
        
        Args:
            collection: Path to the JSON file
            data: Data to write
            document_id: Optional document ID
            path: Optional path within document
            
        Returns:
            Result of the update operation
        """
        file_exists = os.path.exists(collection)
        
        # Handle path updates
        if path:
            return self._update_document_path(
                collection, data, document_id, path, file_exists
            )
        
        # Handle document ID updates
        if document_id:
            return self._update_document_by_id(
                collection, data, document_id, file_exists
            )
        
        try:
            # Direct file update (overwrite)
            write_json_file(collection, data)
            return DocumentResult(
                success=True,
                mode=WriteMode.UPDATE.value,
                file_path=collection,
                created_new=not file_exists
            )
        except Exception as e:
            return DocumentResult(
                success=False,
                mode=WriteMode.UPDATE.value,
                file_path=collection,
                error=str(e)
            )
    
    def _update_document_path(
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
        try:
            if file_exists:
                current_data = read_json_file(collection)
                if current_data is None:
                    current_data = {} if not document_id else []
                    
                # If document ID provided, update that specific document
                if document_id:
                    doc = find_document_by_id(current_data, document_id)
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
                    
                write_json_file(collection, current_data)
            else:
                # File doesn't exist, create with nested structure
                if document_id:
                    new_doc = {"id": document_id}
                    new_doc = self._update_path(new_doc, path, data)
                    write_json_file(collection, [new_doc])
                else:
                    new_data = self._update_path({}, path, data)
                    write_json_file(collection, new_data)
            
            return DocumentResult(
                success=True,
                mode=WriteMode.UPDATE.value,
                file_path=collection,
                document_id=document_id,
                path=path,
                created_new=not file_exists
            )
        except Exception as e:
            return DocumentResult(
                success=False,
                mode=WriteMode.UPDATE.value,
                file_path=collection,
                document_id=document_id,
                path=path,
                error=str(e)
            )
    
    def _update_document_by_id(
        self, 
        collection: str, 
        data: Any, 
        document_id: str,
        file_exists: bool
    ) -> DocumentResult:
        """
        Update a document by ID.
        
        Args:
            collection: Path to the JSON file
            data: Data to write
            document_id: Document ID
            file_exists: Whether the file exists
            
        Returns:
            Result of the update operation
        """
        try:
            if not file_exists:
                # For new files, create with a single document
                new_doc = ensure_id_in_document(data, document_id)
                write_json_file(
                    collection, 
                    [new_doc] if isinstance(new_doc, dict) else {document_id: data}
                )
                return DocumentResult(
                    success=True,
                    mode=WriteMode.UPDATE.value,
                    file_path=collection,
                    document_id=document_id,
                    created_new=True
                )
            
            # Handle existing files
            current_data = read_json_file(collection)
            if current_data is None:
                current_data = [] if isinstance(data, dict) else {}
            
            created_new = False
            
            # Handle list vs dictionary formats differently
            if isinstance(current_data, list):
                created_new = self._update_document_in_list(current_data, data, document_id)
            else:
                # Dictionary format
                created_new = document_id not in current_data
                current_data[document_id] = data
            
            # Write the updated data back to file
            write_json_file(collection, current_data)
            
            return DocumentResult(
                success=True,
                mode=WriteMode.UPDATE.value,
                file_path=collection,
                document_id=document_id,
                document_created=created_new
            )
        except Exception as e:
            return DocumentResult(
                success=False,
                mode=WriteMode.UPDATE.value,
                file_path=collection,
                document_id=document_id,
                error=str(e)
            )

    def _update_document_in_list(self, documents: list, data: Any, document_id: str) -> bool:
        """
        Update a document in a list structure, returning whether a new document was created.
        
        Args:
            documents: List of documents
            data: New document data
            document_id: Document ID
            
        Returns:
            True if a new document was created, False if an existing one was updated
        """
        # Find the document index
        for i, doc in enumerate(documents):
            if isinstance(doc, dict) and doc.get("id") == document_id:
                # Found the document, update it
                documents[i] = ensure_id_in_document(data, document_id)
                return False  # Not a new document
        
        # Document not found, append it
        documents.append(ensure_id_in_document(data, document_id))
        return True  # New document created
    
    def merge_document(
        self, 
        collection: str, 
        data: Any, 
        document_id: Optional[str] = None,
        path: Optional[str] = None
    ) -> DocumentResult:
        """
        Merge data with existing document.
        
        Args:
            collection: Path to the JSON file
            data: Data to merge
            document_id: Optional document ID
            path: Optional path within document
            
        Returns:
            Result of the merge operation
        """
        file_exists = os.path.exists(collection)
        
        try:
            if file_exists:
                current_data = read_json_file(collection)
                if current_data is None:
                    current_data = {}
                    
                # Handle path-specific merge
                if path:
                    return self._merge_document_path(
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
                    write_json_file(collection, merged_data)
                else:
                    # Can't merge incompatible types, overwrite
                    write_json_file(collection, data)
            else:
                # File doesn't exist, create new
                if document_id:
                    write_json_file(
                        collection, 
                        create_initial_structure(data, document_id)
                    )
                else:
                    write_json_file(collection, data)
            
            return DocumentResult(
                success=True,
                mode=WriteMode.MERGE.value,
                file_path=collection,
                document_id=document_id,
                created_new=not file_exists
            )
        except Exception as e:
            return DocumentResult(
                success=False,
                mode=WriteMode.MERGE.value,
                file_path=collection,
                document_id=document_id,
                error=str(e)
            )
    
    def _merge_document_path(
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
        try:
            # Extract current path value
            if document_id:
                doc = find_document_by_id(current_data, document_id)
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
            write_json_file(collection, current_data)
            
            return DocumentResult(
                success=True,
                mode=WriteMode.MERGE.value,
                file_path=collection,
                document_id=document_id,
                path=path
            )
        except Exception as e:
            return DocumentResult(
                success=False, 
                mode=WriteMode.MERGE.value,
                file_path=collection,
                document_id=document_id,
                path=path,
                error=str(e)
            )
    
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
        try:
            # Find existing document
            doc = find_document_by_id(current_data, document_id)
            
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
            write_json_file(collection, updated_data)
            
            return DocumentResult(
                success=True,
                mode=WriteMode.MERGE.value,
                file_path=collection,
                document_id=document_id
            )
        except Exception as e:
            return DocumentResult(
                success=False,
                mode=WriteMode.MERGE.value,
                file_path=collection,
                document_id=document_id,
                error=str(e)
            )
    
    def delete_document(
        self, 
        collection: str, 
        data: Any, 
        document_id: Optional[str] = None,
        path: Optional[str] = None
    ) -> DocumentResult:
        """
        Delete a document or data at a path.
        
        Args:
            collection: Path to the JSON file
            data: Query for batch delete operations
            document_id: Optional document ID
            path: Optional path within document
            
        Returns:
            Result of the delete operation
        """
        if not os.path.exists(collection):
            return DocumentResult(
                success=False,
                mode=WriteMode.DELETE.value,
                file_path=collection,
                error="File not found"
            )
        
        try:
            current_data = read_json_file(collection)
            if current_data is None:
                return DocumentResult(
                    success=False,
                    mode=WriteMode.DELETE.value,
                    file_path=collection,
                    error="Invalid JSON data"
                )
            
            # Handle deleting specific path
            if path:
                return self._delete_document_path(
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
            return DocumentResult(
                success=True,
                mode=WriteMode.DELETE.value,
                file_path=collection,
                file_deleted=True
            )
        except Exception as e:
            return DocumentResult(
                success=False,
                mode=WriteMode.DELETE.value,
                file_path=collection,
                error=str(e)
            )
    
    def _delete_document_path(
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
        try:
            if document_id:
                # Delete path in specific document
                doc = find_document_by_id(current_data, document_id)
                if doc is None:
                    return DocumentResult(
                        success=False,
                        mode=WriteMode.DELETE.value,
                        file_path=collection,
                        document_id=document_id,
                        path=path,
                        error="Document not found"
                    )
                
                # Delete path in document
                updated_doc = self._delete_path(doc, path)
                self._update_document_in_place(
                    current_data, doc, document_id, None, updated_doc
                )
            else:
                # Delete path in entire file
                current_data = self._delete_path(current_data, path)
            
            # Write back to file
            write_json_file(collection, current_data)
            
            return DocumentResult(
                success=True,
                mode=WriteMode.DELETE.value,
                file_path=collection,
                document_id=document_id,
                path=path
            )
        except Exception as e:
            return DocumentResult(
                success=False,
                mode=WriteMode.DELETE.value,
                file_path=collection,
                document_id=document_id,
                path=path,
                error=str(e)
            )
    
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
        try:
            if isinstance(current_data, dict):
                # Dictionary with ID keys
                if document_id in current_data:
                    del current_data[document_id]
                    write_json_file(collection, current_data)
                    return DocumentResult(
                        success=True,
                        mode=WriteMode.DELETE.value,
                        file_path=collection,
                        document_id=document_id
                    )
                else:
                    return DocumentResult(
                        success=False,
                        mode=WriteMode.DELETE.value,
                        file_path=collection,
                        document_id=document_id,
                        error="Document not found"
                    )
            
            elif isinstance(current_data, list):
                # List of documents
                original_length = len(current_data)
                current_data = [
                    item for item in current_data 
                    if not (isinstance(item, dict) and item.get("id") == document_id)
                ]
                
                if len(current_data) < original_length:
                    write_json_file(collection, current_data)
                    return DocumentResult(
                        success=True,
                        mode=WriteMode.DELETE.value,
                        file_path=collection,
                        document_id=document_id
                    )
                else:
                    return DocumentResult(
                        success=False,
                        mode=WriteMode.DELETE.value,
                        file_path=collection,
                        document_id=document_id,
                        error="Document not found"
                    )
            
            return DocumentResult(
                success=False,
                mode=WriteMode.DELETE.value,
                file_path=collection,
                document_id=document_id,
                error="Invalid collection format"
            )
        except Exception as e:
            return DocumentResult(
                success=False,
                mode=WriteMode.DELETE.value,
                file_path=collection,
                document_id=document_id,
                error=str(e)
            )
    
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
        try:
            if isinstance(current_data, list):
                # Filter out items that match the query
                original_length = len(current_data)
                remaining_items = []
                deleted_ids = []
                
                for item in current_data:
                    if isinstance(item, dict):
                        # Check if item matches all query conditions
                        matches = True
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
                    write_json_file(collection, remaining_items)
                    return DocumentResult(
                        success=True,
                        mode=WriteMode.DELETE.value,
                        file_path=collection,
                        deleted_ids=deleted_ids,
                        count=len(deleted_ids)
                    )
                else:
                    return DocumentResult(
                        success=True,
                        mode=WriteMode.DELETE.value,
                        file_path=collection,
                        deleted_ids=[],
                        count=0,
                        message="No documents matched query"
                    )
            
            return DocumentResult(
                success=False,
                mode=WriteMode.DELETE.value,
                file_path=collection,
                error="Collection format does not support query deletes"
            )
        except Exception as e:
            return DocumentResult(
                success=False,
                mode=WriteMode.DELETE.value,
                file_path=collection,
                error=str(e)
            )
    
    # Helper methods for document operations

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
        existing_doc = find_document_by_id(data, document_id)
        created_new = False
        
        if existing_doc is None:
            # Document not found, add it
            created_new = True
            data = add_document_to_structure(data, doc_data, document_id)
        else:
            # Document exists, update it
            self._update_document_in_place(data, existing_doc, document_id, None, doc_data)
        
        return data, created_new