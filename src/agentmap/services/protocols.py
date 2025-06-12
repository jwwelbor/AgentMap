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


@runtime_checkable
class PromptManagerServiceProtocol(Protocol):
    """Protocol for prompt manager service interface used by agents."""
    
    def resolve_prompt(self, prompt_ref: str) -> str:
        """
        Resolve prompt reference to actual prompt text.
        
        Args:
            prompt_ref: Prompt reference (prompt:name, file:path, yaml:path#key, or plain text)
            
        Returns:
            Resolved prompt text
        """
        ...
    
    def format_prompt(self, prompt_ref_or_text: str, values: Dict[str, Any]) -> str:
        """
        Format prompt with variable substitution.
        
        Args:
            prompt_ref_or_text: Prompt reference or text to format
            values: Dictionary of values for variable substitution
            
        Returns:
            Formatted prompt text
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
    """Protocol for agents that can use unified storage services."""
    
    def configure_storage_service(self, storage_service: StorageServiceProtocol) -> None:
        """Configure storage service for this agent."""
        ...


# Separate storage service protocols for fine-grained dependency injection
@runtime_checkable
class CSVCapableAgent(Protocol):
    """Protocol for agents that can use CSV storage services."""
    
    def configure_csv_service(self, csv_service: Any) -> None:
        """Configure CSV storage service for this agent."""
        ...


@runtime_checkable
class JSONCapableAgent(Protocol):
    """Protocol for agents that can use JSON storage services."""
    
    def configure_json_service(self, json_service: Any) -> None:
        """Configure JSON storage service for this agent."""
        ...


@runtime_checkable
class FileCapableAgent(Protocol):
    """Protocol for agents that can use file storage services."""
    
    def configure_file_service(self, file_service: Any) -> None:
        """Configure file storage service for this agent."""
        ...


@runtime_checkable
class VectorCapableAgent(Protocol):
    """Protocol for agents that can use vector services."""
    
    def configure_vector_service(self, vector_service: Any) -> None:
        """Configure vector service for this agent."""
        ...


@runtime_checkable
class MemoryCapableAgent(Protocol):
    """Protocol for agents that can use memory storage services."""
    
    def configure_memory_service(self, memory_service: Any) -> None:
        """Configure memory storage service for this agent."""
        ...


@runtime_checkable
class DatabaseCapableAgent(Protocol):
    """Protocol for agents that can use database services."""
    
    def configure_database_service(self, database_service: Any) -> None:
        """Configure database service for this agent."""
        ...


@runtime_checkable
class PromptCapableAgent(Protocol):
    """Protocol for agents that can use prompt manager services."""
    
    def configure_prompt_service(self, prompt_service: PromptManagerServiceProtocol) -> None:
        """Configure prompt manager service for this agent."""
        ...


# # Legacy compatibility - these might be referenced in existing code
# LLMServiceUser = LLMCapableAgent
# StorageServiceUser = StorageCapableAgent

# # Additional compatibility mappings for separate services approach
# CSVServiceUser = CSVCapableAgent
# JSONServiceUser = JSONCapableAgent
# FileServiceUser = FileCapableAgent
# VectorServiceUser = VectorCapableAgent
# MemoryServiceUser = MemoryCapableAgent