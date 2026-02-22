"""
Service protocols for AgentMap dependency injection.

Defines the service interfaces that agents expect from injected services.
These protocols define what services must provide.
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
class GraphRunnerServiceProtocol(Protocol):
    """Protocol for graph runner service interface used by agents."""

    def run(
        self,
        bundle: Any,  # GraphBundle
        initial_state: Optional[dict] = None,
        **kwargs,
    ) -> Any:  # ExecutionResult
        """Execute a graph bundle and return the result."""
        ...


@runtime_checkable
class PromptManagerServiceProtocol(Protocol):
    """Protocol for prompt manager service interface used by agents."""

    def get_prompt(
        self, prompt_name: str, variables: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Get a prompt template and optionally fill it with variables.

        Args:
            prompt_name: Name of the prompt template
            variables: Optional variables to substitute in the template

        Returns:
            Prompt string (with variables substituted if provided)
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
