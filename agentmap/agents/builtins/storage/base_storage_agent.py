# agentmap/agents/builtins/storage/base_storage_agent.py

from enum import Enum
from typing import Any, Dict, Optional, TypeVar

from agentmap.agents.base_agent import BaseAgent
from agentmap.logging import get_logger

logger = get_logger(__name__)

T = TypeVar('T')  # Generic type for document data


class WriteMode(Enum):
    """Document write operation modes."""
    WRITE = "write"    # Create or overwrite document
    UPDATE = "update"  # Update existing document fields
    MERGE = "merge"    # Merge with existing document
    DELETE = "delete"  # Delete document or field
    APPEND = "append"  # Append to existing document
    
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


# Define the decorator here for shared use
def log_operation(func):
    """
    Decorator to log document operations with consistent formatting.
    
    Args:
        func: The function to decorate
        
    Returns:
        Wrapped function with logging
    """
    import functools
    
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


class BaseStorageAgent(BaseAgent):
    """
    Base class for all storage agents in AgentMap.
    """
    
    def __init__(self, name: str, prompt: str, context: Optional[Dict[str, Any]] = None):
        """
        Initialize the storage agent.
        
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
        Access the storage client connection.
        
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
    
    def get_collection(self, inputs: Dict[str, Any]) -> str:
        """
        Get the collection name/path from inputs or configuration.
        
        Args:
            inputs: Dictionary of input values
            
        Returns:
            Collection identifier (typically a file path for CSV)
        """
        # Try to get the collection from inputs
        collection = inputs.get("collection")
        
        # If not in inputs, try to get from prompt (for backward compatibility)
        if collection is None and self.prompt:
            collection = self.prompt
            
        if collection is None:
            raise ValueError("No collection specified in inputs or prompt")
            
        # Resolve configuration-based collection
        return self._resolve_collection_path(collection)
    
    def _resolve_collection_path(self, collection: str) -> str:
        """
        Resolve a collection name to an actual storage path using configuration.
        
        Args:
            collection: Collection name or path
            
        Returns:
            Resolved path
        """
        # This is a basic implementation, subclasses may override
        return collection
    
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
            exception: Optional exception object
            
        Raises:
            ValueError: For input/validation errors
            RuntimeError: For other errors
        """
        error_msg = f"{error_type}: {message}"
        if exception:
            error_msg += f" - {str(exception)}"
            
        logger.error(f"[Storage] {error_msg}")
        
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