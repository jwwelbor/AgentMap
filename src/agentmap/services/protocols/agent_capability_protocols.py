"""
Agent capability protocols for AgentMap dependency injection.

Defines the capability protocols that agents can implement to receive
specific services through dependency injection.
"""

from typing import TYPE_CHECKING, Any, Dict, List, Protocol, runtime_checkable

from langchain_core.tools import Tool

from agentmap.services.protocols.service_protocols import (
    BlobStorageServiceProtocol,
    EmbeddingServiceProtocol,
    GraphBundleServiceProtocol,
    GraphRunnerServiceProtocol,
    LLMServiceProtocol,
    MessagingServiceProtocol,
    PromptManagerServiceProtocol,
    StorageServiceProtocol,
    VectorStorageServiceProtocol,
)

if TYPE_CHECKING:
    from agentmap.services.orchestrator_service import OrchestratorService
    from agentmap.services.storage.csv_service import CSVStorageService
    from agentmap.services.storage.file_service import FileStorageService
    from agentmap.services.storage.json_service import JSONStorageService
    from agentmap.services.storage.memory_service import MemoryStorageService
    from agentmap.services.storage.vector_service import VectorStorageService


@runtime_checkable
class GraphBundleCapableAgent(Protocol):
    """Protocol for agents that can use graph bundle services."""

    def configure_graph_bundle_service(
        self, graph_bundle_service: GraphBundleServiceProtocol
    ) -> None:
        """Configure graph bundle service for this agent."""
        ...


@runtime_checkable
class GraphRunnerCapableAgent(Protocol):
    """Protocol for agents that can execute subgraphs via graph runner service."""

    def configure_graph_runner_service(
        self, graph_runner_service: GraphRunnerServiceProtocol
    ) -> None:
        """Configure graph runner service for this agent."""
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

    def configure_csv_service(self, csv_service: "CSVStorageService") -> None:
        """Configure CSV storage service for this agent."""
        ...


@runtime_checkable
class JSONCapableAgent(Protocol):
    """Protocol for agents that can use JSON storage services."""

    def configure_json_service(self, json_service: "JSONStorageService") -> None:
        """Configure JSON storage service for this agent."""
        ...


@runtime_checkable
class FileCapableAgent(Protocol):
    """Protocol for agents that can use file storage services."""

    def configure_file_service(self, file_service: "FileStorageService") -> None:
        """Configure file storage service for this agent."""
        ...


@runtime_checkable
class VectorCapableAgent(Protocol):
    """Protocol for agents that can use vector services."""

    def configure_vector_service(self, vector_service: "VectorStorageService") -> None:
        """Configure vector service for this agent."""
        ...


@runtime_checkable
class MemoryCapableAgent(Protocol):
    """Protocol for agents that can use memory storage services."""

    def configure_memory_service(self, memory_service: "MemoryStorageService") -> None:
        """Configure memory storage service for this agent."""
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
        self, orchestrator_service: "OrchestratorService"
    ) -> None:
        """Configure orchestrator service for this agent."""
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
        self, orchestrator_service: "OrchestratorService"
    ) -> None:
        """
        Configure orchestrator service for this agent.

        Args:
            orchestrator_service: OrchestratorService instance for tool selection and routing
        """
        ...
