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

from langchain_core.tools import Tool

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
class MessagingServiceProtocol(Protocol):
    """Protocol for messaging service interface used by agents."""

    async def publish_message(
        self,
        topic: str,
        message_type: str,
        payload: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        provider: Optional[Any] = None,  # CloudProvider
        priority: Any = None,  # MessagePriority
        thread_id: Optional[str] = None,
    ) -> Any:  # StorageResult
        """
        Publish a message to a cloud topic.

        Args:
            topic: Topic/queue name to publish to
            message_type: Type of message (e.g., "task_request", "graph_trigger")
            payload: Message payload data
            metadata: Optional metadata for the message
            provider: Specific provider to use (or use default)
            priority: Message priority
            thread_id: Thread ID for correlation

        Returns:
            StorageResult indicating success/failure
        """
        ...

    def apply_template(
        self, template_name: str, variables: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Apply a message template with variables.

        Args:
            template_name: Name of the template to apply
            variables: Variables to substitute in the template

        Returns:
            Processed template with variables applied
        """
        ...

    def get_service_info(self) -> Dict[str, Any]:
        """
        Get service information for debugging.

        Returns:
            Service information including available providers and configuration
        """
        ...

    def get_available_providers(self) -> List[str]:
        """
        Get list of available messaging providers.

        Returns:
            List of provider names that are available
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


# Agent capability protocols for service configuration
@runtime_checkable
class LLMCapableAgent(Protocol):
    """Protocol for agents that can use LLM services."""

    def configure_llm_service(self, llm_service: LLMServiceProtocol) -> None:
        """Configure LLM service for this agent."""
        ...


@runtime_checkable
class MessagingCapableAgent(Protocol):
    """Protocol for agents that can use messaging services."""

    def configure_messaging_service(
        self, messaging_service: MessagingServiceProtocol
    ) -> None:
        """Configure messaging service for this agent."""
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
class OrchestrationCapableAgent(Protocol):
    """Protocol for agents that can use orchestration services for dynamic routing.

    Distinguishing feature: Orchestration agents have a node_registry attribute
    that stores available routing targets, while ToolSelectionCapableAgent
    agents use the orchestrator only for tool selection, not dynamic routing.
    """

    node_registry: Dict[str, Any]  # Registry of available nodes for routing

    def configure_orchestrator_service(
        self, orchestrator_service: Any  # OrchestratorService
    ) -> None:
        """Configure orchestrator service for this agent."""
        ...


@runtime_checkable
class EmbeddingServiceProtocol(Protocol):
    """Protocol for embedding service interface used by agents."""

    def embed_batch(
        self,
        items: Any,  # Iterable[EmbeddingInput]
        model: str,
        metric: str = "cosine",
        normalize: bool = True,
    ) -> List[Any]:  # List[EmbeddingOutput]
        """
        Embed a batch of texts.

        Args:
            items: Iterable of EmbeddingInput objects
            model: Model name to use for embeddings
            metric: Distance metric ("cosine", "ip", "l2")
            normalize: Whether to normalize vectors

        Returns:
            List of EmbeddingOutput objects
        """
        ...


@runtime_checkable
class VectorStorageServiceProtocol(Protocol):
    """Protocol for vector storage service interface used by agents."""

    def write_embedded(
        self,
        collection: str,
        vectors: Any,  # Iterable[EmbeddingOutput]
        metadatas: Optional[Any] = None,  # Iterable[dict[str, Any]]
    ) -> Any:  # UpsertResult
        """
        Write pre-embedded vectors to storage.

        Args:
            collection: Collection name
            vectors: Iterable of EmbeddingOutput objects
            metadatas: Optional metadata for each vector

        Returns:
            UpsertResult with operation details
        """
        ...

    def query(
        self,
        query_vector: List[float],
        k: int = 8,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Any]:  # List[tuple[str, float, dict[str, Any]]]
        """
        Query vectors by similarity.

        Args:
            query_vector: Query vector
            k: Number of results to return
            filters: Optional metadata filters

        Returns:
            List of (id, score, metadata) tuples
        """
        ...


@runtime_checkable
class EmbeddingCapableAgent(Protocol):
    """Protocol for agents that can use embedding services."""

    def configure_embedding_service(
        self, embedding_service: EmbeddingServiceProtocol
    ) -> None:
        """Configure embedding service for this agent."""
        ...


@runtime_checkable
class VectorStorageCapableAgent(Protocol):
    """Protocol for agents that can use vector storage services."""

    def configure_vector_storage_service(
        self, vector_service: VectorStorageServiceProtocol
    ) -> None:
        """Configure vector storage service for this agent."""
        ...


@runtime_checkable
class ToolCapableAgent(Protocol):
    """
    Protocol for agents that can be configured with tools.

    Agents implementing this protocol can receive and use LangChain tools
    for enhanced functionality like web search, calculations, or custom operations.
    """

    def configure_tools(self, tools: List[Tool]) -> None:
        """
        Configure tools for this agent.

        Args:
            tools: List of LangChain Tool instances to make available to the agent
        """
        ...


@runtime_checkable
class ToolSelectionCapableAgent(Protocol):
    """
    Protocol for agents that need orchestrator service for tool selection.

    Agents implementing this protocol can leverage the OrchestratorService
    to intelligently select and route tool execution based on context.
    """

    def configure_orchestrator_service(
        self, orchestrator_service: Any  # OrchestratorService
    ) -> None:
        """
        Configure orchestrator service for this agent.

        Args:
            orchestrator_service: OrchestratorService instance for tool selection and routing
        """
        ...
