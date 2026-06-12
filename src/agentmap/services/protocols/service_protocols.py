"""
Service protocols for AgentMap dependency injection.

Defines the service interfaces that agents expect from injected services.
These protocols define what services must provide.
"""

from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterator,
    List,
    Optional,
    Protocol,
    Union,
    runtime_checkable,
)

from agentmap.models.llm_execution import (
    BatchPollResult,
    LLMBatchHandle,
    LLMBatchResult,
    LLMBatchSubmitRequest,
    LLMFanoutResult,
    LLMMessage,
    LLMRequest,
    LLMResponse,
)

# Declaration system imports

if TYPE_CHECKING:
    pass


@runtime_checkable
class BatchAdapterProtocol(Protocol):
    """
    Protocol for provider-specific batch adapters.

    Each adapter encapsulates all provider I/O and status normalization for one
    LLM provider's batch API.  The service layer dispatches through this
    interface; no provider-specific logic leaks into the service.

    Members
    -------
    provider_name : str
        Canonical provider key (e.g. ``"anthropic"``, ``"openai"``,
        ``"google"``).  Must match the registry key used in DI wiring.
    supports_cancel : bool
        ``True`` when the provider API supports cancelling an in-flight batch.
    """

    provider_name: str
    supports_cancel: bool

    def submit(
        self,
        specs: List[LLMRequest],
        resolved_params: List[Dict[str, Any]],
    ) -> "tuple[str, Dict[str, str], Optional[str]]":
        """
        Submit a batch and return ``(provider_batch_id, request_id_map, expires_at)``.

        ``specs`` carries messages and ``request_id``; all *parameter* values
        (model, max_tokens, temperature, pass-through options) are delivered
        via ``resolved_params[i]`` which corresponds to ``specs[i]``.  The
        dict is already conflict-free — adapters must not merge or apply
        ``setdefault`` against any other source.

        ``request_id_map`` maps each caller ``request_id`` to the provider-side
        request identifier so that ``fetch_results`` can demultiplex responses
        back to the original spec.  ``expires_at`` is an ISO-8601 string or
        ``None`` if the provider does not return one.

        Decision: D-8 (spec.md § Canonical Parameter Resolution).
        """
        ...

    def poll(self, provider_batch_id: str) -> BatchPollResult:
        """
        Return a ``BatchPollResult`` with *already-normalized* status.

        The provider→``LLMBatchStatus`` mapping lives entirely inside each
        adapter; the service never performs enum lookups on the returned value.
        """
        ...

    def cancel(self, provider_batch_id: str) -> None:
        """
        Request cancellation of an in-flight batch.

        Only called when ``supports_cancel`` is ``True`` and the batch is not
        already in a terminal status.
        """
        ...

    def fetch_results(
        self,
        provider_batch_id: str,
        request_id_map: Dict[str, str],
        result_ref: Optional[str],
    ) -> Iterator[LLMBatchResult]:
        """
        Iterate completed results and key them by caller ``request_id``.

        ``result_ref`` carries the provider output reference (e.g. OpenAI
        ``output_file_id``).  Adapters that fetch by ``provider_batch_id``
        (e.g. Anthropic) ignore it.  Adapters that serve inline results (e.g.
        Gemini) may also ignore it.
        """
        ...


@runtime_checkable
class LLMServiceProtocol(Protocol):
    """Protocol for LLM service interface used by agents."""

    def call_llm(
        self,
        provider: str,
        messages: List[LLMMessage],
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

    def ask_vision(
        self,
        prompt: str,
        image: Union[str, bytes],
        image_type: str = "image/png",
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        routing_context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> str:
        """
        Ask the LLM a question about an image.

        Args:
            prompt: The prompt text describing what to analyze
            image: Image as file path (str) or raw bytes
            image_type: MIME type when image is bytes (default: image/png)
            provider: Optional provider name
            model: Optional model override
            temperature: Optional temperature override
            routing_context: Optional routing context for intelligent routing
            **kwargs: Additional provider-specific parameters

        Returns:
            LLM response as string
        """
        ...

    async def call_llm_async(
        self,
        messages: List[LLMMessage],
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        routing_context: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> LLMResponse:
        """
        Call LLM asynchronously and return a rich ``LLMResponse``.

        ``LLMResponse.text`` carries the response text; ``.resolved_provider``
        and ``.resolved_model`` reflect the provider and model that actually
        handled the request (after routing or fallback); ``.usage`` carries
        normalized token counts when the provider returned usage metadata.

        Args:
            messages: List of message dictionaries with role and content
            provider: Optional LLM provider ("openai", "anthropic", "google", etc.)
            model: Optional model override
            temperature: Optional temperature override
            routing_context: Optional routing context for intelligent routing
            **kwargs: Additional provider-specific parameters

        Returns:
            LLMResponse with text, resolved provider/model, and usage
        """
        ...

    async def ask_async(
        self,
        prompt: str,
        provider: Optional[str] = None,
        **kwargs,
    ) -> str:
        """
        Ask the LLM a question asynchronously using the text-only interface.

        Args:
            prompt: The prompt text to send
            provider: Optional provider name
            **kwargs: Additional provider-specific parameters

        Returns:
            LLM response as string
        """
        ...

    async def call_llm_many_async(
        self,
        requests: List[LLMRequest],
        max_concurrency: int,
    ) -> List[LLMFanoutResult]:
        """
        Submit many LLM call specs and receive one terminal result per spec.

        Submission is validated before any provider execution begins:
        - ``requests`` must not be empty.
        - ``request_id`` values must be unique within one submission.
        - ``max_concurrency`` must be an integer >= 1.

        Once execution starts, per-item failures are captured as ``LLMFanoutResult``
        records with ``status="failed"`` rather than aborting the whole submission.
        The returned list preserves the same positional order as ``requests``.

        Args:
            requests: Non-empty list of ``LLMRequest`` items.
            max_concurrency: Maximum number of in-flight provider calls at once.

        Returns:
            List of ``LLMFanoutResult`` in the same order as ``requests``.

        Raises:
            LLMServiceError: For invalid submissions (before any execution).
        """
        ...

    # ------------------------------------------------------------------
    # Batch lifecycle methods (E05-F03) — additive, provider-agnostic
    # ------------------------------------------------------------------

    def submit_batch(self, request: LLMBatchSubmitRequest) -> LLMBatchHandle:
        """
        Submit a provider-native batch and return a serializable handle.

        Validates the request, delegates to the provider adapter, persists the
        handle, and returns it.  Supported providers: ``"anthropic"``,
        ``"openai"``, ``"google"``.

        Raises:
            LLMServiceError: For validation failures (empty specs, duplicate
                request_ids, batch-incompatible params).
            LLMBatchUnsupportedProviderError: For unsupported providers.
        """
        ...

    def restore_batch(self, handle_data: dict) -> LLMBatchHandle:
        """
        Restore a batch handle from a serialized dict after process restart.

        The dict must be the output of a previous ``handle.to_dict()`` call.
        Validates that the dict contains all required fields.

        Raises:
            LLMServiceError: If the dict is missing required fields.
        """
        ...

    def poll_batch(self, handle: LLMBatchHandle) -> LLMBatchHandle:
        """
        Poll the provider for current batch status and return an updated handle.

        Maps provider-specific status strings to the normalized
        ``LLMBatchStatus`` set.  Persists the updated handle.

        Returns:
            Updated ``LLMBatchHandle`` with current status and request counts.
        """
        ...

    def cancel_batch(self, handle: LLMBatchHandle) -> LLMBatchHandle:
        """
        Request cancellation of an active batch.

        Raises:
            LLMBatchCancelNotSupportedError: If the handle is in a terminal
                status (``"ended"`` or ``"expired"``).
        """
        ...

    def fetch_batch_results(self, handle: LLMBatchHandle) -> List[LLMBatchResult]:
        """
        Retrieve completed batch results keyed by caller ``request_id``.

        Raises:
            LLMBatchNotReadyError: If the handle status is not ``"ended"``.
        """
        ...

    # ------------------------------------------------------------------
    # Async batch surface (E05-F04) — asyncio.to_thread wrappers
    # ------------------------------------------------------------------

    async def asubmit_batch(self, request: LLMBatchSubmitRequest) -> LLMBatchHandle:
        """Async variant of ``submit_batch``; runs blocking SDK call off-thread."""
        ...

    async def apoll_batch(self, handle: LLMBatchHandle) -> LLMBatchHandle:
        """Async variant of ``poll_batch``; runs blocking SDK call off-thread."""
        ...

    async def acancel_batch(self, handle: LLMBatchHandle) -> LLMBatchHandle:
        """Async variant of ``cancel_batch``; runs blocking SDK call off-thread."""
        ...

    async def afetch_batch_results(
        self, handle: LLMBatchHandle
    ) -> List[LLMBatchResult]:
        """Async variant of ``fetch_batch_results``; runs blocking SDK call off-thread."""
        ...

    async def wait_for_batch(
        self,
        handle: LLMBatchHandle,
        *,
        poll_interval: float = 5.0,
        timeout: Optional[float] = None,
    ) -> LLMBatchHandle:
        """
        Poll ``apoll_batch`` with capped exponential backoff until the batch
        reaches a terminal status or ``timeout`` seconds elapse.

        Raises:
            TimeoutError: If ``timeout`` is set and the batch has not completed.
        """
        ...

    def submit_and_wait(
        self,
        request: LLMBatchSubmitRequest,
        *,
        poll_interval: float = 5.0,
        timeout: Optional[float] = None,
    ) -> LLMBatchHandle:
        """
        Synchronous convenience: submit a batch then block until terminal.

        Internally runs an event loop and delegates to ``wait_for_batch``.
        """
        ...

    def batch_capabilities(self, provider: str) -> Dict[str, Any]:
        """
        Return capability metadata for a registered provider adapter.

        Keys include at minimum: ``"supports_cancel"`` (bool),
        ``"provider_name"`` (str).

        Raises:
            LLMBatchUnsupportedProviderError: If ``provider`` has no registered
                adapter.
        """
        ...

    def results_by_request_id(
        self, records: List[LLMBatchResult]
    ) -> Dict[str, LLMBatchResult]:
        """
        Index ``records`` by ``request_id`` for O(1) lookups.

        Any record whose ``request_id`` is ``None`` or empty is excluded.
        """
        ...

    def reconcile_batch_results(
        self,
        submitted_request_ids: List[str],
        records: List[LLMBatchResult],
    ) -> Dict[str, Optional[LLMBatchResult]]:
        """
        Reconcile submitted request_ids against returned records (REQ-F-009c).

        Returns a dict mapping every submitted ``request_id`` to its
        ``LLMBatchResult`` if one was returned, or ``None`` if the
        provider returned no result for that request_id.  A ``None`` value signals
        possible silent data loss and should be investigated by the caller.

        Args:
            submitted_request_ids: The request_ids supplied at submit time.
            records: Records returned by :meth:`fetch_batch_results`.
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

    def get_inputs(
        self,
        state: Any,
        input_fields: List[str],
        expected_params: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Extract input values from state with mode detection.

        Args:
            state: Current state object
            input_fields: List of field names to extract
            expected_params: Optional list of agent parameter names for
                positional binding.

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
    """Protocol for graph runner service interface used by agents.

    Includes both sync members (compatibility shims during staged migration)
    and async siblings introduced by E04-F04 (REQ-F-007).
    """

    def run(
        self,
        bundle: Any,  # GraphBundle
        initial_state: Optional[dict] = None,
        **kwargs,
    ) -> Any:  # ExecutionResult
        """Execute a graph bundle and return the result."""
        ...

    async def run_async(
        self,
        bundle: Any,  # GraphBundle
        initial_state: Optional[dict] = None,
        parent_graph_name: Optional[str] = None,
        parent_tracker: Optional[Any] = None,
        is_subgraph: bool = False,
        validate_agents: bool = False,
    ) -> Any:  # ExecutionResult
        """Execute a graph bundle asynchronously and return the result (REQ-F-004)."""
        ...

    async def resume_from_checkpoint_async(
        self,
        bundle: Any,  # GraphBundle
        thread_id: str,
        checkpoint_state: Dict[str, Any],
        resume_node: Optional[str] = None,
        _cancel_unmark_claimed: Optional[Any] = None,  # threading.Event; Any to avoid import
    ) -> Any:  # ExecutionResult
        """Resume graph execution from a checkpoint asynchronously (REQ-F-005)."""
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
