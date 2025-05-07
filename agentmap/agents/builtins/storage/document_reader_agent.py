# agentmap/agents/builtins/storage/document_reader_agent.py

from typing import Any, Dict, Optional

from agentmap.agents.builtins.storage.base_storage_agent import (
    BaseStorageAgent, log_operation)
from agentmap.logging import get_logger

logger = get_logger(__name__)


class DocumentReaderAgent(BaseStorageAgent):
    """
    Generic document reader agent.
    
    Base class for reading documents from various storage backends.
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