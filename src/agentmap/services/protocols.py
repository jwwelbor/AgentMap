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
