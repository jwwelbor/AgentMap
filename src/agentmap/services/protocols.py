"""
Service protocols for AgentMap dependency injection.

Defines the interfaces that agents expect from injected services.
These protocols enable type-safe dependency injection and clear service contracts.
"""
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class LLMServiceProtocol(Protocol):
    """Protocol for LLM service interface used by agents."""
    
    def call_llm(
        self, 
        provider: str, 
        messages: List[Dict[str, str]], 
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        routing_context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> str:
        """
        Call LLM with specified provider and messages.
        
        Args:
            provider: LLM provider ("openai", "anthropic", "google", etc.)
            messages: List of message dictionaries with role and content
            model: Optional model override
            temperature: Optional temperature override  
            routing_context: Optional routing context for intelligent routing
            **kwargs: Additional provider-specific parameters
            
        Returns:
            LLM response as string
        """
        ...


@runtime_checkable 
class StorageServiceProtocol(Protocol):
    """Protocol for storage service interface used by agents."""
    
    def read(self, collection: str, **kwargs) -> Any:
        """
        Read from storage collection.
        
        Args:
            collection: Storage collection identifier
            **kwargs: Collection-specific parameters
            
        Returns:
            Data from storage
        """
        ...
    
    def write(self, collection: str, data: Any, **kwargs) -> Any:
        """
        Write to storage collection.
        
        Args:
            collection: Storage collection identifier
            data: Data to write
            **kwargs: Collection-specific parameters
            
        Returns:
            Write result or confirmation
        """
        ...


@runtime_checkable
class StateAdapterServiceProtocol(Protocol):
    """Protocol for state adapter service interface used by agents."""
    
    def get_inputs(self, state: Any, input_fields: List[str]) -> Dict[str, Any]:
        """
        Extract input values from state.
        
        Args:
            state: Current state object
            input_fields: List of field names to extract
            
        Returns:
            Dictionary of extracted input values
        """
        ...
    
    def set_value(self, state: Any, field: str, value: Any) -> Any:
        """
        Set a value in the state.
        
        Args:
            state: Current state object
            field: Field name to set
            value: Value to set
            
        Returns:
            Updated state object
        """
        ...


@runtime_checkable
class ExecutionTrackingServiceProtocol(Protocol):
    """Protocol for execution tracking service interface used by agents."""
    
    def record_node_start(self, node_name: str, inputs: Dict[str, Any]) -> None:
        """
        Record the start of node execution.
        
        Args:
            node_name: Name of the node being executed
            inputs: Input values for the node
        """
        ...
    
    def record_node_result(
        self, 
        node_name: str, 
        success: bool, 
        result: Any = None, 
        error: Optional[str] = None
    ) -> None:
        """
        Record the result of node execution.
        
        Args:
            node_name: Name of the node that was executed
            success: Whether execution was successful
            result: Result value (if successful)
            error: Error message (if failed)
        """
        ...
    
    def update_graph_success(self) -> bool:
        """
        Update and return overall graph success status.
        
        Returns:
            True if graph execution is successful overall
        """
        ...


# Agent capability protocols for service configuration
@runtime_checkable
class LLMCapableAgent(Protocol):
    """Protocol for agents that can use LLM services."""
    
    def configure_llm_service(self, llm_service: LLMServiceProtocol) -> None:
        """Configure LLM service for this agent."""
        ...


@runtime_checkable
class StorageCapableAgent(Protocol):
    """Protocol for agents that can use storage services."""
    
    def configure_storage_service(self, storage_service: StorageServiceProtocol) -> None:
        """Configure storage service for this agent."""
        ...


@runtime_checkable
class VectorCapableAgent(Protocol):
    """Protocol for agents that can use vector services."""
    
    def configure_vector_service(self, vector_service: Any) -> None:
        """Configure vector service for this agent."""
        ...


@runtime_checkable
class DatabaseCapableAgent(Protocol):
    """Protocol for agents that can use database services."""
    
    def configure_database_service(self, database_service: Any) -> None:
        """Configure database service for this agent."""
        ...


# Legacy compatibility - these might be referenced in existing code
LLMServiceUser = LLMCapableAgent
StorageServiceUser = StorageCapableAgent