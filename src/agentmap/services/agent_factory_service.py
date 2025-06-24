"""
AgentFactoryService for AgentMap.

Service containing business logic for agent creation and instantiation.
This extracts and wraps the core functionality from the original AgentLoader class.
"""

from typing import Any, Dict, List, Optional, Tuple, Type

from agentmap.services.agent_registry_service import AgentRegistryService
from agentmap.services.features_registry_service import FeaturesRegistryService
from agentmap.services.logging_service import LoggingService


class AgentFactoryService:
    """
    Factory service for creating and managing agent instances.

    Contains all agent creation business logic extracted from the original AgentLoader class.
    Uses dependency injection and coordinates between registry and features services.
    Follows Factory pattern naming to match existing test fixtures.
    """

    def __init__(
        self,
        agent_registry_service: AgentRegistryService,
        features_registry_service: FeaturesRegistryService,
        logging_service: LoggingService,
    ):
        """Initialize service with dependency injection."""
        self.agent_registry = agent_registry_service
        self.features = features_registry_service
        self.logger = logging_service.get_class_logger(self)
        self.logger.debug("[AgentFactoryService] Initialized")

    def resolve_agent_class(self, agent_type: str) -> Type:
        """
        Resolve an agent class by type with dependency validation.

        Args:
            agent_type: The type identifier for the agent

        Returns:
            Agent class ready for instantiation

        Raises:
            ValueError: If agent type is not found or dependencies are missing
        """
        agent_type.lower()

        self.logger.debug(
            f"[AgentFactoryService] Resolving agent class: type='{agent_type}'"
        )

        # Validate dependencies before resolving class
        dependencies_valid, missing_deps = self.validate_agent_dependencies(agent_type)
        if not dependencies_valid:
            error_msg = self._get_dependency_error_message(agent_type, missing_deps)
            self.logger.error(f"[AgentFactoryService] {error_msg}")
            raise ValueError(error_msg)

        # Get the agent class from registry
        agent_class = self.agent_registry.get_agent_class(agent_type)
        if not agent_class:
            self.logger.error(
                f"[AgentFactoryService] Agent type '{agent_type}' not found"
            )
            raise ValueError(f"Agent type '{agent_type}' not found.")

        self.logger.debug(
            f"[AgentFactoryService] Successfully resolved agent class '{agent_type}' "
            f"to {agent_class.__name__}"
        )
        return agent_class

    def get_agent_class(self, agent_type: str) -> Optional[Type]:
        """
        Get an agent class by type without dependency validation.

        Use resolve_agent_class() instead for full validation.

        Args:
            agent_type: Type identifier to look up

        Returns:
            The agent class or None if not found
        """
        return self.agent_registry.get_agent_class(agent_type)

    def can_resolve_agent_type(self, agent_type: str) -> bool:
        """
        Check if an agent type can be resolved (has valid dependencies).

        Args:
            agent_type: The agent type to check

        Returns:
            True if agent type can be resolved
        """
        try:
            self.resolve_agent_class(agent_type)
            return True
        except ValueError:
            return False

    def validate_agent_dependencies(self, agent_type: str) -> Tuple[bool, List[str]]:
        """
        Validate that all dependencies for an agent type are available.

        Args:
            agent_type: The agent type to validate

        Returns:
            Tuple of (dependencies_valid, missing_dependencies)
        """
        agent_type_lower = agent_type.lower()
        missing_deps = []

        # Check LLM dependencies for LLM-related agents
        if self._is_llm_agent(agent_type_lower):
            if not self._check_llm_dependencies(agent_type_lower):
                missing_deps.append("llm")

        # Check storage dependencies for storage-related agents
        if self._is_storage_agent(agent_type_lower):
            if not self._check_storage_dependencies(agent_type_lower):
                missing_deps.append("storage")

        dependencies_valid = len(missing_deps) == 0

        if dependencies_valid:
            self.logger.debug(
                f"[AgentFactoryService] All dependencies valid for agent type '{agent_type}'"
            )
        else:
            self.logger.debug(
                f"[AgentFactoryService] Missing dependencies for '{agent_type}': {missing_deps}"
            )

        return dependencies_valid, missing_deps

    def list_available_agent_types(self) -> List[str]:
        """
        Get a list of all available agent types that can be resolved.

        Returns:
            List of agent type names that have valid dependencies
        """
        all_types = self.agent_registry.get_registered_agent_types()
        available_types = []

        for agent_type in all_types:
            if self.can_resolve_agent_type(agent_type):
                available_types.append(agent_type)

        self.logger.debug(
            f"[AgentFactoryService] Available agent types: {available_types}"
        )
        return available_types

    def get_agent_resolution_context(self, agent_type: str) -> Dict[str, Any]:
        """
        Get comprehensive context for agent class resolution.

        Args:
            agent_type: Agent type to get context for

        Returns:
            Dictionary with resolution context and metadata
        """
        try:
            agent_class = self.resolve_agent_class(agent_type)
            dependencies_valid, missing_deps = self.validate_agent_dependencies(
                agent_type
            )

            return {
                "agent_type": agent_type,
                "agent_class": agent_class,
                "class_name": agent_class.__name__,
                "resolvable": True,
                "dependencies_valid": dependencies_valid,
                "missing_dependencies": missing_deps,
                "_factory_version": "2.0",
                "_resolution_method": "AgentFactoryService.resolve_agent_class",
            }
        except ValueError as e:
            dependencies_valid, missing_deps = self.validate_agent_dependencies(
                agent_type
            )
            return {
                "agent_type": agent_type,
                "agent_class": None,
                "class_name": None,
                "resolvable": False,
                "dependencies_valid": dependencies_valid,
                "missing_dependencies": missing_deps,
                "resolution_error": str(e),
                "_factory_version": "2.0",
                "_resolution_method": "AgentFactoryService.resolve_agent_class",
            }

    def _is_llm_agent(self, agent_type: str) -> bool:
        """Check if an agent type requires LLM dependencies."""
        llm_agent_types = {
            "openai",
            "anthropic",
            "google",
            "gpt",
            "claude",
            "gemini",
            "llm",
            "chat",
            "conversation",
            "text_generation",
        }
        return agent_type in llm_agent_types

    def _is_storage_agent(self, agent_type: str) -> bool:
        """Check if an agent type requires storage dependencies."""
        storage_agent_types = {
            "csv_reader",
            "csv_writer",
            "json_reader",
            "json_writer",
            "file_reader",
            "file_writer",
            "vector_reader",
            "vector_writer",
            "storage",
            "database",
            "persist",
        }
        return agent_type in storage_agent_types

    def _check_llm_dependencies(self, agent_type: str) -> bool:
        """Check if LLM dependencies are available for the agent type."""
        # For specific LLM providers, check that provider specifically
        if agent_type in ("openai", "gpt"):
            return self.features.is_provider_available("llm", "openai")
        elif agent_type in ("anthropic", "claude"):
            return self.features.is_provider_available("llm", "anthropic")
        elif agent_type in ("google", "gemini"):
            return self.features.is_provider_available("llm", "google")
        else:
            # For generic LLM agents, check if any LLM provider is available
            available_providers = self.features.get_available_providers("llm")
            return len(available_providers) > 0

    def _check_storage_dependencies(self, agent_type: str) -> bool:
        """Check if storage dependencies are available for the agent type."""
        # For specific storage types, check those specifically
        if "csv" in agent_type:
            return self.features.is_provider_available("storage", "csv")
        elif "json" in agent_type:
            return self.features.is_provider_available("storage", "json")
        elif "file" in agent_type:
            return self.features.is_provider_available("storage", "file")
        elif "vector" in agent_type:
            return self.features.is_provider_available("storage", "vector")
        else:
            # For generic storage agents, check if core storage is available
            return self.features.is_provider_available("storage", "csv")

    def _get_dependency_error_message(
        self, agent_type: str, missing_deps: List[str]
    ) -> str:
        """Generate a helpful error message for missing dependencies."""
        agent_type_lower = agent_type.lower()

        # Handle multiple dependencies first
        if len(missing_deps) > 1:
            return (
                f"Agent '{agent_type}' requires additional dependencies: {missing_deps}. "
                "Install with: pip install agentmap[llm,storage]"
            )

        # Handle single LLM dependency
        if "llm" in missing_deps:
            if agent_type_lower in ("openai", "gpt"):
                return (
                    f"LLM agent '{agent_type}' requires OpenAI dependencies. "
                    "Install with: pip install agentmap[openai]"
                )
            elif agent_type_lower in ("anthropic", "claude"):
                return (
                    f"LLM agent '{agent_type}' requires Anthropic dependencies. "
                    "Install with: pip install agentmap[anthropic]"
                )
            elif agent_type_lower in ("google", "gemini"):
                return (
                    f"LLM agent '{agent_type}' requires Google dependencies. "
                    "Install with: pip install agentmap[google]"
                )
            else:
                return (
                    f"LLM agent '{agent_type}' requires additional dependencies. "
                    "Install with: pip install agentmap[llm]"
                )

        # Handle single storage dependency
        if "storage" in missing_deps:
            if "vector" in agent_type_lower:
                return (
                    f"Storage agent '{agent_type}' requires vector dependencies. "
                    "Install with: pip install agentmap[vector]"
                )
            else:
                return (
                    f"Storage agent '{agent_type}' requires additional dependencies. "
                    "Install with: pip install agentmap[storage]"
                )

        # Generic fallback (shouldn't be reached with current logic)
        return (
            f"Agent '{agent_type}' requires additional dependencies: {missing_deps}. "
            "Install with: pip install agentmap[llm,storage]"
        )
