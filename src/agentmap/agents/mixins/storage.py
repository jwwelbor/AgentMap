"""
Storage agent mixins for common functionality.

This module provides mixins that can be used to compose storage agents
with common behaviors for input processing, error handling, etc.
"""
from typing import Any, Dict, Optional

from agentmap.agents.builtins.storage.base_storage_agent import DocumentResult, WriteMode
from agentmap.logging import get_logger

logger = get_logger(__name__)


class StorageInputProcessorMixin:
    """Mixin for processing common storage inputs."""
    
    def extract_common_params(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract common parameters from inputs.
        
        Args:
            inputs: Input dictionary
            
        Returns:
            Dictionary of extracted parameters
        """
        return {
            "collection": self.get_collection(inputs),
            "document_id": inputs.get("document_id"),
            "query": inputs.get("query"),
            "path": inputs.get("path"),
            "mode": inputs.get("mode", "read")
        }


class ReaderOperationsMixin:
    """Mixin for common reader operations."""
    
    def _validate_reader_inputs(self, inputs: Dict[str, Any]) -> None:
        """
        Validate inputs for read operations.
        
        Args:
            inputs: Input dictionary
            
        Raises:
            ValueError: If required inputs are missing
        """
        collection = self.get_collection(inputs)
        if not collection:
            raise ValueError("Missing required 'collection' parameter")
    
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
        self.log_info(f"[{self.__class__.__name__}] Reading {operation_type} from {collection} ({detail_str})")
    
    def _format_read_result(self, result: Any, inputs: Dict[str, Any]) -> Any:
        """
        Format read operation result.
        
        Args:
            result: Read operation result
            inputs: Input dictionary
            
        Returns:
            Formatted result
        """
        # Return default value if result is None and default is provided
        if result is None and "default" in inputs:
            return inputs["default"]
            
        return result


class WriterOperationsMixin:
    """Mixin for common writer operations."""
    
    def _validate_writer_inputs(self, inputs: Dict[str, Any]) -> None:
        """
        Validate inputs for write operations.
        
        Args:
            inputs: Input dictionary
            
        Raises:
            ValueError: If required inputs are missing
        """
        collection = self.get_collection(inputs)
        if not collection:
            raise ValueError("Missing required 'collection' parameter")
        
        mode_str = inputs.get("mode", "write").lower()
        try:
            mode = WriteMode.from_string(mode_str)
        except ValueError as e:
            raise ValueError(f"Invalid mode: {mode_str}")
        
        # Data is required for non-delete operations
        if mode != WriteMode.DELETE and inputs.get("data") is None:
            raise ValueError("No data provided to write")
    
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
        self.log_info(f"[{self.__class__.__name__}] {operation_type} {target_type} in {collection} ({detail_str})")


class StorageErrorHandlerMixin:
    """Mixin for standardized storage error handling."""
    
    def _handle_storage_error(
        self, 
        error: Exception, 
        operation_type: str, 
        collection: str,
        **context
    ) -> DocumentResult:
        """
        Handle storage operation errors consistently.
        
        Args:
            error: The exception that occurred
            operation_type: Type of operation (read, write, etc.)
            collection: Collection identifier
            **context: Additional error context
            
        Returns:
            DocumentResult with error information
        """
        error_msg = f"Failed to {operation_type} from {collection}: {str(error)}"
        self.log_error(f"[{self.__class__.__name__}] {error_msg}")
        
        # Create standardized error result
        return DocumentResult(
            success=False,
            error=error_msg,
            **context
        )
