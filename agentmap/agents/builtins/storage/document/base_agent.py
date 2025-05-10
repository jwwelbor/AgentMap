"""
Base document storage agent implementation.

This module provides the foundation for document-based storage agents,
with methods for reading, writing, and manipulating structured documents.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, TypeVar, Union

from agentmap.agents.builtins.storage.base_storage_agent import (
    BaseStorageAgent, DocumentResult, WriteMode, log_operation)
from agentmap.logging import get_logger

logger = get_logger(__name__)

T = TypeVar('T')  # Generic type for document data


class DocumentStorageAgent(BaseStorageAgent):
    """
    Base class for document storage agents.
    
    Provides a common interface for working with document-oriented storage
    systems like JSON files, Firebase, Supabase, CosmosDB, etc.
    
    This abstract class defines the contract that all document storage
    implementations must follow.
    """
    
    def _read_document(
        self, 
        collection: str, 
        document_id: Optional[str] = None, 
        query: Optional[Dict[str, Any]] = None, 
        path: Optional[str] = None
    ) -> Any:
        """
        Read a document or collection of documents.
        
        Args:
            collection: Collection identifier
            document_id: Optional specific document ID
            query: Optional query parameters
            path: Optional path within document
            
        Returns:
            Document data
            
        Raises:
            NotImplementedError: When not implemented by subclass
        """
        raise NotImplementedError("Subclasses must implement _read_document")
    
    def _write_document(
        self, 
        collection: str, 
        data: Any, 
        document_id: Optional[str] = None,
        mode: Union[WriteMode, str] = WriteMode.WRITE, 
        path: Optional[str] = None
    ) -> DocumentResult:
        """
        Write a document or update an existing one.
        
        Args:
            collection: Collection identifier
            data: Data to write
            document_id: Optional document ID
            mode: Write mode (write, update, merge, delete)
            path: Optional path within document
            
        Returns:
            Operation result
            
        Raises:
            NotImplementedError: When not implemented by subclass
        """
        raise NotImplementedError("Subclasses must implement _write_document")
    
    def _apply_document_query(self, data: Any, query: Dict[str, Any]) -> Any:
        """
        Apply query filtering to document data.
        
        Args:
            data: Document data to filter
            query: Query parameters
            
        Returns:
            Filtered data
            
        Raises:
            NotImplementedError: When not implemented by subclass
        """
        raise NotImplementedError("Subclasses must implement _apply_document_query")
    
    def _apply_document_path(self, data: Any, path: str) -> Any:
        """
        Extract data from a specific path within a document.
        
        Args:
            data: Document data
            path: Path expression (e.g. "users.0.name")
            
        Returns:
            Data at specified path
            
        Raises:
            NotImplementedError: When not implemented by subclass
        """
        raise NotImplementedError("Subclasses must implement _apply_document_path")
    
    def _update_document_path(self, data: Any, path: str, value: Any) -> Any:
        """
        Update data at a specific path within a document.
        
        Args:
            data: Document data
            path: Path expression
            value: New value
            
        Returns:
            Updated document
            
        Raises:
            NotImplementedError: When not implemented by subclass
        """
        raise NotImplementedError("Subclasses must implement _update_document_path")
    
    def _ensure_document_exists(self, collection: str, document_id: str) -> bool:
        """
        Check if a document exists.
        
        Args:
            collection: Collection identifier
            document_id: Document ID
            
        Returns:
            True if document exists
            
        Raises:
            NotImplementedError: When not implemented by subclass
        """
        raise NotImplementedError("Subclasses must implement _ensure_document_exists")


class DocumentReaderAgent(DocumentStorageAgent):
    """
    Base class for document reader agents.
    
    Provides common functionality for reading documents from various storage backends.
    Concrete implementations are provided for JSON, Firebase, etc.
    """
    
    @log_operation
    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Read documents from storage.
        
        This method parses the inputs, validates them, and calls the
        appropriate implementation method to perform the actual read.
        
        Args:
            inputs: Dictionary containing:
                - collection: Document collection identifier
                - document_id: Optional specific document ID
                - query: Optional query parameters
                - path: Optional path within document
                - default: Optional default value if not found
                
        Returns:
            Document data or None if not found
        
        Raises:
            ValueError: If required inputs are missing or invalid
        """
        # Get required collection
        collection = self._get_collection_from_inputs(inputs)
        
        # Extract optional parameters
        document_id = inputs.get("document_id")
        query = inputs.get("query")
        path = inputs.get("path")
        
        # Log the operation details
        self._log_read_operation(collection, document_id, query, path)
        
        try:
            # Perform the actual read operation
            result = self._read_document(collection, document_id, query, path)
            
            # Return default value if result is None and default is provided
            if result is None and "default" in inputs:
                logger.debug(f"[{self.__class__.__name__}] Using default value")
                return inputs["default"]
                
            return result
            
        except Exception as e:
            # Handle the error appropriately
            self._handle_error("Document Read Error", 
                              f"Failed to read from {collection}", e)
    
    def _get_collection_from_inputs(self, inputs: Dict[str, Any]) -> str:
        """
        Extract and validate the collection from inputs.
        
        Args:
            inputs: Input dictionary
            
        Returns:
            Collection identifier
            
        Raises:
            ValueError: If collection is missing
        """
        collection = self.get_collection(inputs)
        if not collection:
            raise ValueError("Missing required 'collection' parameter")
        return collection
    
    def _log_read_operation(
        self, 
        collection: str, 
        document_id: Optional[str] = None,
        query: Optional[Dict[str, Any]] = None,
        path: Optional[str] = None
    ) -> None:
        """
        Log details of a read operation.
        
        Args:
            collection: Collection identifier
            document_id: Optional document ID
            query: Optional query parameters
            path: Optional document path
        """
        operation_type = "collection"
        details = []
        
        if document_id:
            operation_type = "document"
            details.append(f"id={document_id}")
            
        if query:
            operation_type = "query"
            query_str = ", ".join(f"{k}={v}" for k, v in query.items())
            details.append(f"query={{{query_str}}}")
            
        if path:
            details.append(f"path={path}")
            
        detail_str = ", ".join(details) if details else "all"
        logger.info(f"[{self.__class__.__name__}] Reading {operation_type} from {collection} ({detail_str})")


class DocumentWriterAgent(DocumentStorageAgent):
    """
    Base class for document writer agents.
    
    Provides common functionality for writing documents to various storage backends.
    Concrete implementations are provided for JSON, Firebase, etc.
    """
    
    @log_operation
    def process(self, inputs: Dict[str, Any]) -> DocumentResult:
        """
        Write documents to storage.
        
        This method parses the inputs, validates them, and calls the
        appropriate implementation method to perform the actual write.
        
        Args:
            inputs: Dictionary containing:
                - collection: Document collection identifier
                - data: Data to write
                - document_id: Optional document ID
                - mode: Write mode (write, update, merge, delete)
                - path: Optional path within document
                
        Returns:
            DocumentResult containing operation results and metadata
            
        Raises:
            ValueError: If required inputs are missing or invalid
        """
        # Get required collection
        collection = self._get_collection_from_inputs(inputs)
        
        # Get required data for non-delete operations
        data = inputs.get("data")
        mode_str = inputs.get("mode", "write").lower()
        
        try:
            # Convert string mode to enum
            mode = WriteMode.from_string(mode_str)
        except ValueError as e:
            self._handle_error("Invalid Mode", str(e))
        
        # Data is required for non-delete operations
        if mode != WriteMode.DELETE and data is None:
            self._handle_error("Missing Data", "No data provided to write")
        
        # Extract optional parameters
        document_id = inputs.get("document_id")
        path = inputs.get("path")
        
        # Log the operation details
        self._log_write_operation(collection, mode, document_id, path)
        
        try:
            # Perform the actual write operation
            result = self._write_document(collection, data, document_id, mode, path)
            return result
            
        except Exception as e:
            # Handle the error appropriately
            self._handle_error("Document Write Error", 
                              f"Failed to write to {collection}", e)
    
    def _get_collection_from_inputs(self, inputs: Dict[str, Any]) -> str:
        """
        Extract and validate the collection from inputs.
        
        Args:
            inputs: Input dictionary
            
        Returns:
            Collection identifier
            
        Raises:
            ValueError: If collection is missing
        """
        collection = self.get_collection(inputs)
        if not collection:
            raise ValueError("Missing required 'collection' parameter")
        return collection
    
    def _log_write_operation(
        self, 
        collection: str,
        mode: WriteMode,
        document_id: Optional[str] = None,
        path: Optional[str] = None
    ) -> None:
        """
        Log details of a write operation.
        
        Args:
            collection: Collection identifier
            mode: Write operation mode
            document_id: Optional document ID
            path: Optional document path
        """
        operation_type = mode.value.upper()
        target_type = "collection"
        details = []
        
        if document_id:
            target_type = "document"
            details.append(f"id={document_id}")
            
        if path:
            details.append(f"path={path}")
            
        detail_str = ", ".join(details) if details else "all"
        logger.info(f"[{self.__class__.__name__}] {operation_type} {target_type} in {collection} ({detail_str})")