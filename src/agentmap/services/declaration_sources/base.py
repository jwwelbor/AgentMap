"""Base declaration source interface."""

from abc import ABC, abstractmethod
from typing import Dict

from agentmap.models.declaration_models import AgentDeclaration, ServiceDeclaration


class DeclarationSource(ABC):
    """
    Abstract base class for declaration sources.

    Provides a common interface for loading agent and service declarations
    from various sources while ensuring consistent return formats.
    """

    @abstractmethod
    def load_agents(self) -> Dict[str, AgentDeclaration]:
        """
        Load agent declarations from this source.

        Returns:
            Dictionary mapping agent types to AgentDeclaration models
        """

    @abstractmethod
    def load_services(self) -> Dict[str, ServiceDeclaration]:
        """
        Load service declarations from this source.

        Returns:
            Dictionary mapping service names to ServiceDeclaration models
        """
