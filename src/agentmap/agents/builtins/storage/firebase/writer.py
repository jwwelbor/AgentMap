"""
Firebase document writer agent implementation.

This module provides an agent for writing data to Firebase databases,
with support for Firestore and Realtime Database.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from firebase_admin import firestore, db
from google.cloud import firestore_v1
from agentmap.agents.builtins.storage.document.writer import DocumentWriterAgent

from agentmap.agents.builtins.storage.document.base_agent import (
    DocumentResult,  WriteMode, log_operation)
from agentmap.agents.builtins.storage.firebase.base_agent import FirebaseDocumentAgent
from agentmap.agents.builtins.storage.mixins import WriterOperationsMixin
from agentmap.logging import get_logger

logger = get_logger(__name__)


class FirebaseDocumentWriterAgent(DocumentWriterAgent, FirebaseDocumentAgent, WriterOperationsMixin):
    """
    Agent for writing data to Firebase databases.
    
    Provides functionality for writing to both Firestore and Realtime Database,
    with support for document creation, updates, merges, and deletions.
    """
    
    def _execute_operation(self, collection: str, inputs: Dict[str, Any]) -> DocumentResult:
        """
        Execute write operation for Firebase.
        
        Args:
            collection: Collection identifier
            inputs: Input dictionary
            
        Returns:
            Write operation result
        """
        # Get required data
        data = inputs.get("data")
        mode_str = inputs.get("mode", "write").lower()
        
        # Convert string mode to enum
        try:
            mode = WriteMode.from_string(mode_str)
        except ValueError as e:
            return DocumentResult(
                success=False,
                error=str(e)
            )
        
        # Extract optional parameters
        document_id = inputs.get("document_id")
        path = inputs.get("path")
        
        # Log the write operation
        self._log_write_operation(collection, mode, document_id, path)
        
        # Perform the write operation
        return self._write_document(collection, data, document_id, mode, path)
    
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
        Write a document to Firebase.
        
        Args:
            collection: Collection identifier from storage config
            data: Data to write
            document_id: Optional document ID
            mode: Write mode (write, update, merge, delete)
            path: Optional path within document
            
        Returns:
            Result of the write operation
        """
        try:
            # Convert string mode to enum if needed
            if isinstance(mode, str):
                mode = WriteMode.from_string(mode)
            
            # Get database reference
            db_ref, db_path, config = self._get_db_reference(collection)
            
            # Determine if we're working with Firestore or Realtime DB
            if isinstance(db_ref, firestore.CollectionReference):
                return self._write_to_firestore(db_ref, data, document_id, mode, path)
            else:
                return self._write_to_realtime_db(db_ref, data, document_id, mode, path)
                
        except Exception as e:
            # Convert Firebase errors to standard exceptions
            error = self._convert_firebase_error(e)
            self.log_error(f"Firebase write error: {str(error)}")
            
            return DocumentResult(
                success=False,
                mode=str(mode),
                document_id=document_id,
                path=path,
                error=str(error)
            )
    
        
    def _update_firestore_path(
        self,
        doc_ref: firestore.DocumentReference,
        data: Any,
        mode: WriteMode,
        path: str,
        existed: bool
    ) -> DocumentResult:
        """
        Update data at a specific path in a Firestore document.
        
        Args:
            doc_ref: Firestore document reference
            data: Data to write
            mode: Write mode
            path: Path within document
            existed: Whether document already existed
            
        Returns:
            Result of the update operation
        """
        document_id = doc_ref.id
        
        if not existed:
            # Document doesn't exist, create it with nested data
            nested_data = {}
            current_dict = nested_data
            
            # Build nested structure based on path
            parts = path.split(".")
            for i, part in enumerate(parts[:-1]):
                current_dict[part] = {}
                current_dict = current_dict[part]
            
            # Set the data at the leaf
            current_dict[parts[-1]] = data
            
            # Create the document
            doc_ref.set(nested_data)
            
            return DocumentResult(
                success=True,
                mode=str(mode),
                document_id=document_id,
                path=path,
                created_new=True
            )
        
        # Convert dot notation path to Firestore field path
        field_path = path.replace(".", ".")
        
        if mode == WriteMode.WRITE or mode == WriteMode.UPDATE:
            # Update specific field
            doc_ref.update({field_path: data})
            
        elif mode == WriteMode.MERGE:
            # For merge at path, we need to get the existing data first
            @firestore.transactional
            def merge_field_in_transaction(transaction: firestore_v1.Transaction, doc_ref, field_path, data):
                doc_snapshot = doc_ref.get(transaction=transaction)
                doc_data = doc_snapshot.to_dict() or {}
                
                # Get existing value at path
                existing_value = self._apply_path(doc_data, path)
                
                # Merge if both are dictionaries
                if isinstance(existing_value, dict) and isinstance(data, dict):
                    merged_data = self._merge_documents(existing_value, data)
                    transaction.update(doc_ref, {field_path: merged_data})
                else:
                    # Otherwise just update
                    transaction.update(doc_ref, {field_path: data})
                
                return True
            
            # Execute the transaction
            transaction = doc_ref._client.transaction()
            merge_field_in_transaction(transaction, doc_ref, field_path, data)
        
        return DocumentResult(
            success=True,
            mode=str(mode),
            document_id=document_id,
            path=path
        )
    
    def _write_to_realtime_db(
        self, 
        ref: db.Reference,
        data: Any, 
        document_id: Optional[str] = None,
        mode: WriteMode = WriteMode.WRITE, 
        path: Optional[str] = None
    ) -> DocumentResult:
        """
        Write data to Realtime Database.
        
        Args:
            ref: Realtime DB reference
            data: Data to write
            document_id: Optional child key
            mode: Write mode
            path: Optional path within data
            
        Returns:
            Result of the write operation
        """
        # Handle document ID (child nodes)
        if document_id:
            child_ref = ref.child(document_id)
            
            # Check if node exists
            existed = child_ref.get() is not None
            
            # Handle path updates
            if path and mode != WriteMode.DELETE:
                return self._update_realtime_path(child_ref, data, mode, path, existed)
            
            # Handle different write modes
            if mode == WriteMode.WRITE:
                # Create or overwrite child node
                child_ref.set(data)
                return DocumentResult(
                    success=True,
                    mode=str(mode),
                    document_id=document_id,
                    created_new=not existed
                )
                
            elif mode == WriteMode.UPDATE:
                # Update existing node
                if isinstance(data, dict):
                    child_ref.update(data)
                else:
                    child_ref.set(data)
                    
                return DocumentResult(
                    success=True,
                    mode=str(mode),
                    document_id=document_id,
                    created_new=not existed
                )
                
            elif mode == WriteMode.MERGE:
                # Merge with existing node
                if existed and isinstance(data, dict):
                    current_data = child_ref.get()
                    if isinstance(current_data, dict):
                        merged_data = self._merge_documents(current_data, data)
                        child_ref.set(merged_data)
                    else:
                        # Can't merge with non-dict, overwrite
                        child_ref.set(data)
                else:
                    # Node doesn't exist, create it
                    child_ref.set(data)
                    
                return DocumentResult(
                    success=True,
                    mode=str(mode),
                    document_id=document_id,
                    created_new=not existed
                )
                
            elif mode == WriteMode.DELETE:
                # Delete node or field
                if path:
                    # Delete specific field
                    return self._delete_realtime_path(child_ref, path, existed)
                else:
                    # Delete entire node
                    child_ref.delete()
                    return DocumentResult(
                        success=True,
                        mode=str(mode),
                        document_id=document_id
                    )
        else:
            # No document ID, operating on the reference directly
            
            # Handle path updates
            if path and mode != WriteMode.DELETE:
                return self._update_realtime_path(ref, data, mode, path, True)
            
            # Handle different write modes
            if mode == WriteMode.WRITE:
                # Overwrite all data
                ref.set(data)
                return DocumentResult(
                    success=True,
                    mode=str(mode)
                )
                
            elif mode == WriteMode.UPDATE:
                # Update fields
                if isinstance(data, dict):
                    ref.update(data)
                else:
                    ref.set(data)
                    
                return DocumentResult(
                    success=True,
                    mode=str(mode)
                )
                
            elif mode == WriteMode.MERGE:
                # Merge with existing data
                current_data = ref.get()
                if isinstance(current_data, dict) and isinstance(data, dict):
                    merged_data = self._merge_documents(current_data, data)
                    ref.set(merged_data)
                else:
                    # Can't merge, overwrite
                    ref.set(data)
                    
                return DocumentResult(
                    success=True,
                    mode=str(mode)
                )
                
            elif mode == WriteMode.DELETE:
                # Delete path or all data
                if path:
                    # Delete specific path
                    return self._delete_realtime_path(ref, path, True)
                else:
                    # Delete everything
                    ref.delete()
                    return DocumentResult(
                        success=True,
                        mode=str(mode)
                    )
        
        # Unsupported mode
        return DocumentResult(
            success=False,
            mode=str(mode),
            document_id=document_id,
            error=f"Unsupported write mode: {mode}"
        )
    
    def _update_realtime_path(
        self,
        ref: db.Reference,
        data: Any,
        mode: WriteMode,
        path: str,
        existed: bool
    ) -> DocumentResult:
        """
        Update data at a specific path in a Realtime DB node.
        
        Args:
            ref: Realtime DB reference
            data: Data to write
            mode: Write mode
            path: Path within node
            existed: Whether node already existed
            
        Returns:
            Result of the update operation
        """
        document_id = ref.path.split('/')[-1] if '/' in ref.path else None
        
        # Using update mode for path updates
        if mode in [WriteMode.WRITE, WriteMode.UPDATE]:
            # Build nested path for update
            update_data = {}
            update_data[path.replace(".", "/")] = data
            
            # Update the path
            ref.update(update_data)
            
        elif mode == WriteMode.MERGE:
            # For merge at path, we need to get existing data
            current_data = ref.get() or {}
            
            # Get value at path
            existing_value = self._apply_path(current_data, path)
            
            if isinstance(existing_value, dict) and isinstance(data, dict):
                # Merge dictionaries
                merged_value = self._merge_documents(existing_value, data)
                
                # Build update with merged value
                update_data = {}
                update_data[path.replace(".", "/")] = merged_value
                
                # Update the path
                ref.update(update_data)
            else:
                # Can't merge, just update
                update_data = {}
                update_data[path.replace(".", "/")] = data
                ref.update(update_data)
        
        return DocumentResult(
            success=True,
            mode=str(mode),
            document_id=document_id,
            path=path
        )
    
    def _delete_realtime_path(
        self,
        ref: db.Reference,
        path: str,
        existed: bool
    ) -> DocumentResult:
        """
        Delete data at a specific path in a Realtime DB node.
        
        Args:
            ref: Realtime DB reference
            path: Path within node
            existed: Whether node already existed
            
        Returns:
            Result of the delete operation
        """
        document_id = ref.path.split('/')[-1] if '/' in ref.path else None
        
        if not existed:
            return DocumentResult(
                success=False,
                mode=str(WriteMode.DELETE),
                document_id=document_id,
                path=path,
                error="Node does not exist"
            )
        
        # Convert dot notation to path notation
        db_path = path.replace(".", "/")
        
        # Set the path to null to delete it
        update_data = {}
        update_data[db_path] = None
        
        # Update to delete the path
        ref.update(update_data)
        
        return DocumentResult(
            success=True,
            mode=str(WriteMode.DELETE),
            document_id=document_id,
            path=path
        )
    
    def _delete_firestore_path(
        self,
        doc_ref: firestore.DocumentReference,
        path: str,
        existed: bool
    ) -> DocumentResult:
        """
        Delete data at a specific path in a Firestore document.
        
        Args:
            doc_ref: Firestore document reference
            path: Path within document
            existed: Whether document already existed
            
        Returns:
            Result of the delete operation
        """
        document_id = doc_ref.id
        
        if not existed:
            return DocumentResult(
                success=False,
                mode=str(WriteMode.DELETE),
                document_id=document_id,
                path=path,
                error="Document does not exist"
            )
        
        try:
            # Convert dot notation path to Firestore field path
            # Note: In Firestore, field paths with dots use the same notation
            field_path = path
            
            # Delete the field using Firestore's DELETE_FIELD sentinel
            doc_ref.update({field_path: firestore.DELETE_FIELD})
            
            return DocumentResult(
                success=True,
                mode=str(WriteMode.DELETE),
                document_id=document_id,
                path=path
            )
        except Exception as e:
            return DocumentResult(
                success=False,
                mode=str(WriteMode.DELETE),
                document_id=document_id,
                path=path,
                error=f"Failed to delete field: {str(e)}"
            )