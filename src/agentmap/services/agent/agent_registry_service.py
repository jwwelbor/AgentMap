"""
AgentRegistryService for AgentMap.

Service containing business logic for agent registration and lookup operations.
This extracts and wraps the core functionality from the original Registry class.
"""

from typing import Dict, List, Optional, Type

from agentmap.models.agent_registry import AgentRegistry
from agentmap.services.logging_service import LoggingService


class AgentRegistryService:
    """
    Service for managing agent class registration and lookup.

    Contains all business logic extracted from the original Registry class.
    Uses dependency injection and manages state through the AgentRegistry model.
    """

    def __init__(self, agent_registry: AgentRegistry, logging_service: LoggingService):
        """Initialize service with dependency injection."""
        self.agent_registry = agent_registry
        self.logger = logging_service.get_class_logger(self)
        self.logger.debug("[AgentRegistryService] Initialized")

    def register_agent(self, agent_type: str, agent_class: Type) -> None:
        """
        Register an agent class with a given type.

        Args:
            agent_type: String identifier for the agent type
            agent_class: Agent class to register
        """
        self.agent_registry.add_agent(agent_type, agent_class)

        # Log the registration
        if agent_type.lower() == "default":
            self.logger.debug(
                f"[AgentRegistryService] Registered default agent: {agent_class.__name__}"
            )
        else:
            self.logger.debug(
                f"[AgentRegistryService] Registered agent '{agent_type}': {agent_class.__name__}"
            )

    def unregister_agent(self, agent_type: str) -> None:
        """
        Unregister an agent type.

        Args:
            agent_type: String identifier for the agent type to remove
        """
        if self.agent_registry.has_agent(agent_type):
            self.agent_registry.remove_agent(agent_type)
            self.logger.debug(
                f"[AgentRegistryService] Unregistered agent: {agent_type}"
            )
        else:
            self.logger.warning(
                f"[AgentRegistryService] Attempted to unregister unknown agent: {agent_type}"
            )

    def get_agent_class(
        self, agent_type: str, default: Optional[Type] = None
    ) -> Optional[Type]:
        """
        Get an agent class by type, with optional default.

        Args:
            agent_type: Type identifier to look up
            default: Default value to return if not found

        Returns:
            The agent class or the default value if not found
        """
        # Handle empty/None agent_type by returning default agent or provided default
        if not agent_type:
            result = self.agent_registry.default_agent_class or default
            if result:
                self.logger.debug(
                    f"[AgentRegistryService] Retrieved default agent: {result.__name__}"
                )
            return result

        # Try to get the specific agent type
        agent_class = self.agent_registry.get_agent_class(agent_type)
        if agent_class:
            self.logger.debug(
                f"[AgentRegistryService] Retrieved agent '{agent_type}': {agent_class.__name__}"
            )
            return agent_class

        # Fall back to provided default
        if default:
            self.logger.debug(
                f"[AgentRegistryService] Agent '{agent_type}' not found, using default: {default.__name__}"
            )
        else:
            self.logger.debug(
                f"[AgentRegistryService] Agent '{agent_type}' not found, no default provided"
            )

        return default

    def has_agent(self, agent_type: str) -> bool:
        """
        Check if an agent type is registered.

        Args:
            agent_type: Type identifier to check

        Returns:
            True if agent type is registered, False otherwise
        """
        return self.agent_registry.has_agent(agent_type)

    def list_agents(self) -> Dict[str, Type]:
        """
        Get a dictionary of all registered agent types and classes.

        Returns:
            Dictionary mapping agent types to agent classes (copy for safety)
        """
        agent_map = self.agent_registry.list_agents()
        self.logger.debug(
            f"[AgentRegistryService] Listed {len(agent_map)} registered agents"
        )
        return agent_map

    def get_default_agent_class(self) -> Optional[Type]:
        """
        Get the default agent class if one is registered.

        Returns:
            The default agent class or None if no default is set
        """
        default_agent = self.agent_registry.default_agent_class
        if default_agent:
            self.logger.debug(
                f"[AgentRegistryService] Retrieved default agent class: {default_agent.__name__}"
            )
        else:
            self.logger.debug("[AgentRegistryService] No default agent class is set")
        return default_agent

    def set_default_agent_class(self, agent_class: Type) -> None:
        """
        Set the default agent class by registering it with type 'default'.

        Args:
            agent_class: Agent class to set as default
        """
        self.register_agent("default", agent_class)
        self.logger.debug(
            f"[AgentRegistryService] Set default agent class: {agent_class.__name__}"
        )

    def get_registered_agent_types(self) -> List[str]:
        """
        Get a list of all registered agent type names.

        Returns:
            List of registered agent type names
        """
        agent_types = list(self.agent_registry.agents.keys())
        self.logger.debug(
            f"[AgentRegistryService] Found {len(agent_types)} registered agent types: {agent_types}"
        )
        return agent_types

    def clear_all_agents(self) -> None:
        """
        Clear all registered agents.

        Warning: This removes all agent registrations including the default.
        """
        agent_count = len(self.agent_registry.agents)
        self.agent_registry.agents.clear()
        self.agent_registry.default_agent_class = None

        self.logger.warning(
            f"[AgentRegistryService] Cleared all {agent_count} registered agents"
        )
