"""
Service protocols for AgentMap dependency injection.

Defines the interfaces that agents expect from injected services.
These protocols enable type-safe dependency injection and clear service contracts.
"""

from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    Optional,
    Protocol,
    Set,
    runtime_checkable,
)

# Declaration system imports
from agentmap.models.declaration_models import AgentDeclaration, ServiceDeclaration

if TYPE_CHECKING:
    from agentmap.services.declaration_sources import DeclarationSource


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
        **kwargs,
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
        error: Optional[str] = None,
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


@runtime_checkable
class GraphBundleServiceProtocol(Protocol):
    """Protocol for graph bundle service interface used by agents."""

    def get_or_create_bundle(
        self,
        csv_path: Any,  # Path
        graph_name: Optional[str] = None,
        config_path: Optional[str] = None,
    ) -> Any:  # GraphBundle
        """
        Get existing bundle from cache or create a new one.

        This method encapsulates the bundle caching logic, checking for
        existing bundles using composite keys (csv_hash, graph_name) and
        creating new ones as needed. Bundles are created per-graph, not per-CSV.

        Args:
            csv_path: Path to CSV file
            graph_name: Optional graph name (used for composite key lookup)
            config_path: Optional path to configuration file

        Returns:
            GraphBundle ready for execution or scaffolding
        """
        ...


@runtime_checkable
class GraphBundleCapableAgent(Protocol):
    """Protocol for agents that can use graph bundle services."""

    def configure_graph_bundle_service(
        self, graph_bundle_service: GraphBundleServiceProtocol
    ) -> None:
        """Configure graph bundle service for this agent."""
        ...


@runtime_checkable
class GraphCheckpointServiceProtocol(Protocol):
    """Protocol for graph checkpoint service interface used by agents."""

    def save_checkpoint(
        self,
        thread_id: str,
        node_name: str,
        checkpoint_type: str,
        metadata: Dict[str, Any],
        execution_state: Dict[str, Any],
    ) -> Any:
        """
        Save a graph execution checkpoint.

        Args:
            thread_id: Unique identifier for the execution thread
            node_name: Name of the node where checkpoint occurs
            checkpoint_type: Type of checkpoint
            metadata: Type-specific metadata
            execution_state: Current execution state data

        Returns:
            Result of the save operation
        """
        ...

    def load_checkpoint(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """
        Load the latest checkpoint for a thread.

        Args:
            thread_id: Thread ID to load checkpoint for

        Returns:
            Checkpoint data or None if not found
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

    def configure_storage_service(
        self, storage_service: StorageServiceProtocol
    ) -> None:
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
class BlobStorageServiceProtocol(Protocol):
    """Protocol for blob storage service interface used by agents."""

    def read_blob(self, uri: str, **kwargs) -> bytes:
        """
        Read blob from storage.

        Args:
            uri: URI of the blob to read (azure://, s3://, gs://, or local path)
            **kwargs: Provider-specific parameters

        Returns:
            Blob content as bytes
        """
        ...

    def write_blob(self, uri: str, data: bytes, **kwargs) -> Dict[str, Any]:
        """
        Write blob to storage.

        Args:
            uri: URI where the blob should be written
            data: Blob content as bytes
            **kwargs: Provider-specific parameters

        Returns:
            Write result with operation details
        """
        ...

    def blob_exists(self, uri: str) -> bool:
        """
        Check if a blob exists.

        Args:
            uri: URI to check

        Returns:
            True if the blob exists, False otherwise
        """
        ...

    def list_blobs(self, prefix: str, **kwargs) -> List[str]:
        """
        List blobs with given prefix.

        Args:
            prefix: URI prefix to search (e.g., "azure://container/path/")
            **kwargs: Provider-specific parameters

        Returns:
            List of blob URIs
        """
        ...

    def delete_blob(self, uri: str, **kwargs) -> Dict[str, Any]:
        """
        Delete a blob.

        Args:
            uri: URI of the blob to delete
            **kwargs: Provider-specific parameters

        Returns:
            Delete result with operation details
        """
        ...

    def get_available_providers(self) -> List[str]:
        """
        Get list of available storage providers.

        Returns:
            List of provider names that are available
        """
        ...

    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on blob storage service.

        Returns:
            Health check results for all providers
        """
        ...


@runtime_checkable
class BlobStorageCapableAgent(Protocol):
    """Protocol for agents that can use blob storage services."""

    def configure_blob_storage_service(
        self, blob_service: BlobStorageServiceProtocol
    ) -> None:
        """Configure blob storage service for this agent."""
        ...


@runtime_checkable
class PromptCapableAgent(Protocol):
    """Protocol for agents that can use prompt manager services."""

    def configure_prompt_service(
        self, prompt_service: PromptManagerServiceProtocol
    ) -> None:
        """Configure prompt manager service for this agent."""
        ...


@runtime_checkable
class CheckpointCapableAgent(Protocol):
    """Protocol for agents that can use graph checkpoint services."""

    def configure_checkpoint_service(
        self, checkpoint_service: GraphCheckpointServiceProtocol
    ) -> None:
        """Configure graph checkpoint service for this agent."""
        ...


@runtime_checkable
class OrchestrationCapableAgent(Protocol):
    """Protocol for agents that can use orchestration services."""

    def configure_orchestrator_service(
        self, orchestrator_service: Any  # OrchestratorService
    ) -> None:
        """Configure orchestrator service for this agent."""
        ...
