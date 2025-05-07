# agentmap/agents/builtins/storage/base_document_storage_agent.py

from enum import Enum
from typing import Any, Dict, Optional, TypeVar, Union

from agentmap.agents.builtins.storage.base_storage_agent import \
    BaseStorageAgent
from agentmap.logging import get_logger

logger = get_logger(__name__)

T = TypeVar('T')  # Generic type for document data


class WriteMode(Enum):
    """Document write operation modes."""
    WRITE = "write"    # Create or overwrite document
    UPDATE = "update"  # Update existing document fields
    MERGE = "merge"    # Merge with existing document
    DELETE = "delete"  # Delete document or field
    
    @classmethod
    def from_string(cls, mode: str) -> "WriteMode":
        """Convert string to enum value, case-insensitive."""
        try:
            return cls(mode.lower())
        except ValueError:
            valid_modes = [m.value for m in cls]
            raise ValueError(f"Invalid write mode: {mode}. Valid modes: {valid_modes}")


class DocumentResult(Dict[str, Any]):
    """Typed document operation result."""
    @property
    def success(self) -> bool:
        """Whether the operation succeeded."""
        return self.get("success", False)
    
    @property
    def document_id(self) -> Optional[str]:
        """ID of the affected document, if any."""
        return self.get("document_id")


class BaseDocumentStorageAgent(BaseStorageAgent):
    """
    Base class for document storage agents.
    
    Provides a common interface for working with document-oriented storage
    systems like JSON files, Firebase, Supabase, CosmosDB, etc.
    
    This abstract class defines the contract that all document storage
    implementations must follow.
    """
    
    def __init__(self, name: str, prompt: str, context: Optional[Dict[str, Any]] = None):
        """
        Initialize the document storage agent.
        
        Args:
            name: Name of the agent node
            prompt: Prompt or instruction
            context: Additional context including input/output field configuration
        """
        super().__init__(name, prompt, context)
        self._client = None
    
    @property
    def client(self) -> Any:
        """
        Access the document storage client connection.
        
        Returns:
            Storage client instance
        
        Note:
            This property should initialize the client on first access
            if it doesn't already exist.
        """
        if self._client is None:
            self._initialize_client()
        return self._client
    
    def _initialize_client(self) -> None:
        """
        Initialize the storage client connection.
        
        Subclasses should implement this to set up their specific client connection.
        """
        raise NotImplementedError("Subclasses must implement _initialize_client")
    
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
    
    # Shared utility methods
    
    def _handle_error(
        self, 
        error_type: str, 
        message: str, 
        exception: Optional[Exception] = None
    ) -> None:
        """
        Handle errors with consistent logging.
        
        Args:
            error_type: Type of error
            message: Error message
            exception: Optional exception objectf
            
        Raises:
            ValueError: For input/validation errors
            RuntimeError: For other errors
        """
        error_msg = f"{error_type}: {message}"
        if exception:
            error_msg += f" - {str(exception)}"
            
        logger.error(f"[DocumentStorage] {error_msg}")
        
        if isinstance(exception, (ValueError, TypeError)):
            raise ValueError(error_msg)
        else:
            raise RuntimeError(error_msg)
    
    def _normalize_document_id(self, document_id: Any) -> Optional[str]:
        """
        Normalize document ID to string format.
        
        Args:
            document_id: Document ID in any format
            
        Returns:
            String document ID or None
        """
        if document_id is None:
            return None
        return str(document_id)