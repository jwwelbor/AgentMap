# agentmap/agents/builtins/storage/document_writer_agent.py

from typing import Any, Dict, Optional, Union

from agentmap.agents.builtins.storage.base_storage_agent import (
    BaseStorageAgent, DocumentResult, WriteMode, log_operation)
from agentmap.logging import get_logger

logger = get_logger(__name__)


class DocumentWriterAgent(BaseStorageAgent):
    """
    Generic document writer agent.
    
    Base class for writing documents to various storage backends.
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