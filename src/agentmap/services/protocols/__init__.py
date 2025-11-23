"""
Service protocols for AgentMap dependency injection.

Defines the interfaces that agents expect from injected services.
These protocols enable type-safe dependency injection and clear service contracts.

This module is organized into:
- service_protocols: Service interface protocols (what services provide)
- agent_capability_protocols: Agent capability protocols (what agents can consume)
"""

# Re-export all agent capability protocols
from agentmap.services.protocols.agent_capability_protocols import (
    BlobStorageCapableAgent,
    CSVCapableAgent,
    EmbeddingCapableAgent,
    FileCapableAgent,
    GraphBundleCapableAgent,
    JSONCapableAgent,
    LLMCapableAgent,
    MemoryCapableAgent,
    MessagingCapableAgent,
    OrchestrationCapableAgent,
    PromptCapableAgent,
    StorageCapableAgent,
    ToolCapableAgent,
    ToolSelectionCapableAgent,
    VectorCapableAgent,
    VectorStorageCapableAgent,
)

# Re-export all service protocols
from agentmap.services.protocols.service_protocols import (
    BlobStorageServiceProtocol,
    EmbeddingServiceProtocol,
    ExecutionTrackingServiceProtocol,
    GraphBundleServiceProtocol,
    LLMServiceProtocol,
    MessagingServiceProtocol,
    PromptManagerServiceProtocol,
    StateAdapterServiceProtocol,
    StorageServiceProtocol,
    VectorStorageServiceProtocol,
)

__all__ = [
    # Service protocols
    "BlobStorageServiceProtocol",
    "EmbeddingServiceProtocol",
    "ExecutionTrackingServiceProtocol",
    "GraphBundleServiceProtocol",
    "LLMServiceProtocol",
    "MessagingServiceProtocol",
    "PromptManagerServiceProtocol",
    "StateAdapterServiceProtocol",
    "StorageServiceProtocol",
    "VectorStorageServiceProtocol",
    # Agent capability protocols
    "BlobStorageCapableAgent",
    "CSVCapableAgent",
    "EmbeddingCapableAgent",
    "FileCapableAgent",
    "GraphBundleCapableAgent",
    "JSONCapableAgent",
    "LLMCapableAgent",
    "MemoryCapableAgent",
    "MessagingCapableAgent",
    "OrchestrationCapableAgent",
    "PromptCapableAgent",
    "StorageCapableAgent",
    "ToolCapableAgent",
    "ToolSelectionCapableAgent",
    "VectorCapableAgent",
    "VectorStorageCapableAgent",
]
