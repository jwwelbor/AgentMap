"""
Firebase document reader agent implementation.

This module provides an agent for reading data from Firebase databases,
with support for Firestore and Realtime Database.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from firebase_admin import firestore, db

from agentmap.agents.builtins.storage.document.base_agent import (  DocumentResult, log_operation)
from agentmap.agents.builtins.storage.document import DocumentReaderAgent
from agentmap.agents.builtins.storage.firebase.base_agent import FirebaseDocumentAgent
from agentmap.agents.mixins import ReaderOperationsMixin
from agentmap.logging import get_logger

logger = get_logger(__name__)


class FirebaseDocumentReaderAgent(DocumentReaderAgent, FirebaseDocumentAgent, ReaderOperationsMixin):
    """
    Agent for reading data from Firebase databases.
    
    Provides functionality for reading from both Firestore and Realtime Database,
    with support for document lookups, query filtering, and path extraction.
    """
    
    def _execute_operation(self, collection: str, inputs: Dict[str, Any]) -> Any:
        """
        Execute read operation for Firebase.
        
        Args:
            collection: Collection name
            inputs: Input dictionary
            
        Returns:
            Read operation result
        """
        # Extract parameters
        document_id = inputs.get("document_id")
        query = inputs.get("query")
        path = inputs.get("path")
        
        # Log the read operation
        self._log_read_operation(collection, document_id, query, path)
        
        # Perform the read operation
        return self._read_document(collection, document_id, query, path)
    
    @log_operation
    def _read_document(
        self, 
        collection: str, 
        document_id: Optional[str] = None, 
        query: Optional[Dict[str, Any]] = None, 
        path: Optional[str] = None
    ) -> Any:
        """
        Read document(s) from Firebase.
        
        Args:
            collection: Collection identifier from storage config
            document_id: Optional document ID for direct lookup
            query: Optional query parameters for filtering
            path: Optional path within document for field extraction
            
        Returns:
            Document data, filtered and processed according to parameters
        """
        try:
            # Get database reference
            db_ref, db_path, config = self._get_db_reference(collection)
            
            # Determine if we're working with Firestore or Realtime DB
            if isinstance(db_ref, firestore.CollectionReference):
                return self._read_from_firestore(db_ref, document_id, query, path)
            else:
                return self._read_from_realtime_db(db_ref, document_id, query, path)
                
        except Exception as e:
            # Convert Firebase errors to standard exceptions
            error = self._convert_firebase_error(e)
            self.log_error(f"Firebase read error: {str(error)}")
            raise error
    
    def _read_from_firestore(
        self, 
        collection_ref: firestore.CollectionReference,
        document_id: Optional[str] = None, 
        query: Optional[Dict[str, Any]] = None, 
        path: Optional[str] = None
    ) -> Any:
        """
        Read document(s) from Firestore.
        
        Args:
            collection_ref: Firestore collection reference
            document_id: Optional document ID
            query: Optional query parameters
            path: Optional path within document
            
        Returns:
            Document data
        """
        # Single document lookup by ID
        if document_id:
            doc_ref = collection_ref.document(document_id)
            doc_snapshot = doc_ref.get()
            
            if not doc_snapshot.exists:
                return None
                
            data = doc_snapshot.to_dict()
            data["id"] = doc_snapshot.id  # Ensure ID is included
            
            # Apply path extraction if specified
            if path:
                return self._apply_path(data, path)
                
            return DocumentResult(
                success=True,
                document_id=document_id,
                data=data,
                is_collection=False
            ).to_dict()
        
        # Collection query
        if query:
            return self._apply_firestore_query(collection_ref, query, path)
        
        # Get all documents in collection
        docs = collection_ref.stream()
        results = []
        
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id  # Ensure ID is included
            results.append(data)
        
        # Apply path extraction if specified
        if path:
            results = [self._apply_path(doc, path) for doc in results]
            results = [r for r in results if r is not None]  # Filter out None values
            
        return DocumentResult(
            success=True,
            data=results,
            is_collection=True
        ).to_dict()
    
    def _apply_firestore_query(
        self,
        collection_ref: firestore.CollectionReference,
        query: Dict[str, Any],
        path: Optional[str] = None
    ) -> Any:
        """
        Apply query filtering to Firestore collection.
        
        Args:
            collection_ref: Firestore collection reference
            query: Query parameters
            path: Optional path within documents
            
        Returns:
            Filtered query results
        """
        # Extract special query parameters
        limit_val = query.pop("limit", None)
        offset_val = query.pop("offset", None)
        order_by = query.pop("orderBy", None)
        order_dir = query.pop("orderDir", "asc").lower()
        
        # Build the Firestore query
        fs_query = collection_ref
        
        # Apply field filters
        for field, value in query.items():
            fs_query = fs_query.where(field, "==", value)
        
        # Apply ordering
        if order_by:
            direction = firestore.Query.ASCENDING if order_dir == "asc" else firestore.Query.DESCENDING
            fs_query = fs_query.order_by(order_by, direction=direction)
        
        # Apply offset
        if offset_val and isinstance(offset_val, int):
            fs_query = fs_query.offset(offset_val)
        
        # Apply limit
        if limit_val and isinstance(limit_val, int):
            fs_query = fs_query.limit(limit_val)
        
        # Execute query
        docs = fs_query.stream()
        results = []
        
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id  # Ensure ID is included
            
            # Apply path extraction if specified
            if path:
                value = self._apply_path(data, path)
                if value is not None:
                    results.append(value)
            else:
                results.append(data)
        
        return DocumentResult(
            success=True,
            data=results,
            count=len(results),
            is_collection=True
        ).to_dict()
    
    def _read_from_realtime_db(
        self, 
        ref: db.Reference,
        document_id: Optional[str] = None, 
        query: Optional[Dict[str, Any]] = None, 
        path: Optional[str] = None
    ) -> Any:
        """
        Read data from Realtime Database.
        
        Args:
            ref: Realtime DB reference
            document_id: Optional child key
            query: Optional query parameters
            path: Optional path within data
            
        Returns:
            Database data
        """
        # Single child lookup by ID
        if document_id:
            child_ref = ref.child(document_id)
            data = child_ref.get()
            
            if data is None:
                return None
            
            # Ensure data has ID if it's a dictionary
            if isinstance(data, dict):
                data["id"] = document_id
            
            # Apply path extraction if specified
            if path:
                return self._apply_path(data, path)
                
            return DocumentResult(
                success=True,
                document_id=document_id,
                data=data,
                is_collection=False
            ).to_dict()
        
        # Get all data at reference
        data = ref.get()
        
        # Handle empty data
        if data is None:
            return []
        
        # Apply query filtering if specified
        if query:
            return self._apply_realtime_query(data, query, path)
        
        # Apply path extraction if specified
        if path:
            return self._apply_path(data, path)
        
        # Convert Realtime DB data to standard format
        if isinstance(data, dict):
            # Convert dictionary to list of documents with keys as IDs
            results = []
            for key, value in data.items():
                if isinstance(value, dict):
                    value["id"] = key
                    results.append(value)
                else:
                    results.append({"id": key, "value": value})
                    
            return DocumentResult(
                success=True,
                data=results,
                is_collection=True
            ).to_dict()
        
        # Return data as is if not a dictionary
        return DocumentResult(
            success=True,
            data=data,
            is_collection=isinstance(data, list)
        ).to_dict()
    
    def _apply_realtime_query(
        self,
        data: Any,
        query: Dict[str, Any],
        path: Optional[str] = None
    ) -> Any:
        """
        Apply query filtering to Realtime DB data.
        
        Args:
            data: Realtime DB data
            query: Query parameters
            path: Optional path within data
            
        Returns:
            Filtered query results
        """
        # Extract special query parameters
        limit_val = query.pop("limit", None)
        offset_val = query.pop("offset", 0)
        order_by = query.pop("orderBy", None)
        order_dir = query.pop("orderDir", "asc").lower()
        
        # Handle different data structures
        if isinstance(data, dict):
            # Convert dictionary to list of documents with keys as IDs
            items = []
            for key, value in data.items():
                if isinstance(value, dict):
                    value["id"] = key
                    items.append(value)
                else:
                    items.append({"id": key, "value": value})
        elif isinstance(data, list):
            items = data
        else:
            items = [{"value": data}]
        
        # Apply field filters
        results = []
        for item in items:
            if isinstance(item, dict) and all(
                item.get(field) == value for field, value in query.items()
            ):
                results.append(item)
        
        # Apply sorting
        if order_by:
            reverse = (order_dir == "desc")
            results.sort(
                key=lambda x: x.get(order_by) if isinstance(x, dict) else None,
                reverse=reverse
            )
        
        # Apply pagination
        if offset_val and isinstance(offset_val, int):
            results = results[offset_val:]
            
        if limit_val and isinstance(limit_val, int):
            results = results[:limit_val]
        
        # Apply path extraction if specified
        if path:
            results = [self._apply_path(item, path) for item in results]
            results = [r for r in results if r is not None]  # Filter out None values
        
        return DocumentResult(
            success=True,
            data=results,
            count=len(results),
            is_collection=True
        ).to_dict()
