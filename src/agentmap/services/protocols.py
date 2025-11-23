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

# Re-export storage protocols for backward compatibility
from agentmap.services.storage.protocols import (
    BlobStorageCapableAgent,
    BlobStorageServiceProtocol,
    CSVCapableAgent,
    FileCapableAgent,
    JSONCapableAgent,
    MemoryCapableAgent,
    StorageCapableAgent,
    VectorCapableAgent,
)

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


# ===== AGENT CAPABILITY PROTOCOLS =====
# These protocols define how agents receive service dependencies


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
        self, messaging_service: Any  # MessagingServiceProtocol
    ) -> None:
        """Configure messaging service for this agent."""
        ...


@runtime_checkable
class PromptCapableAgent(Protocol):
    """Protocol for agents that can use prompt manager services."""

    def configure_prompt_service(
        self, prompt_service: Any  # PromptManagerServiceProtocol
    ) -> None:
        """Configure prompt manager service for this agent."""
        ...


@runtime_checkable
class OrchestrationCapableAgent(Protocol):
    """
    Protocol for agents that can use orchestration services for dynamic routing.

    Distinguishing feature: Orchestration agents have a node_registry attribute
    that stores available routing targets, while ToolSelectionCapableAgent
    agents use the orchestrator only for tool selection, not dynamic routing.
    """

    node_registry: Dict[str, Any]  # Registry of available nodes for routing

    def configure_orchestrator_service(
        self, orchestrator_service: Any  # OrchestratorService
    ) -> None:
        """Configure orchestrator service for dynamic node routing."""
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
            tools: List of LangChain Tool instances
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
        """Configure orchestrator service for tool selection."""
        ...


@runtime_checkable
class GraphBundleCapableAgent(Protocol):
    """Protocol for agents that can use graph bundle services."""

    def configure_graph_bundle_service(
        self, graph_bundle_service: Any  # GraphBundleServiceProtocol
    ) -> None:
        """Configure graph bundle service for this agent."""
        ...


@runtime_checkable
class EmbeddingCapableAgent(Protocol):
    """Protocol for agents that can use embedding services."""

    def configure_embedding_service(
        self, embedding_service: Any  # EmbeddingServiceProtocol
    ) -> None:
        """Configure embedding service for this agent."""
        ...


@runtime_checkable
class VectorStorageCapableAgent(Protocol):
    """Protocol for agents that can use vector storage services."""

    def configure_vector_storage_service(
        self, vector_service: Any  # VectorStorageServiceProtocol
    ) -> None:
        """Configure vector storage service for this agent."""
        ...
