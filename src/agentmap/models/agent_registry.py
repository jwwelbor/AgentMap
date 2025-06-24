"""
AgentRegistry domain model for AgentMap.

Pure data container for agent class mappings and registration state.
All business logic belongs in services, not in this domain model.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Type


@dataclass
class AgentRegistry:
    """
    Pure data container for agent registry state.

    This model only holds data - all business logic belongs in AgentRegistryService.

    Attributes:
        agents: Dictionary mapping agent type names to agent classes
        default_agent_class: Optional default agent class for fallback behavior
    """

    agents: Dict[str, Type] = field(default_factory=dict)
    default_agent_class: Optional[Type] = None

    def add_agent(self, agent_type: str, agent_class: Type) -> None:
        """
        Store an agent class mapping.

        Simple data storage method similar to Node.add_edge().

        Args:
            agent_type: String identifier for the agent type (stored lowercase)
            agent_class: Agent class to store
        """
        normalized_type = agent_type.lower()
        self.agents[normalized_type] = agent_class

        # Store as default if this is the default agent type
        if normalized_type == "default":
            self.default_agent_class = agent_class

    def remove_agent(self, agent_type: str) -> None:
        """
        Remove an agent class mapping.

        Simple data removal method for agent state.

        Args:
            agent_type: String identifier for the agent type to remove
        """
        normalized_type = agent_type.lower()
        if normalized_type in self.agents:
            # Clear default if removing the default agent
            if normalized_type == "default":
                self.default_agent_class = None
            del self.agents[normalized_type]

    def get_agent_class(self, agent_type: str) -> Optional[Type]:
        """
        Get an agent class by type.

        Simple query method similar to Node.has_conditional_routing().

        Args:
            agent_type: Type identifier to look up

        Returns:
            The agent class or None if not found
        """
        if not agent_type:
            return self.default_agent_class
        return self.agents.get(agent_type.lower())

    def has_agent(self, agent_type: str) -> bool:
        """
        Check if an agent type is registered.

        Simple query method for agent type existence.

        Args:
            agent_type: Type identifier to check

        Returns:
            True if agent type is registered, False otherwise
        """
        return agent_type.lower() in self.agents

    def list_agents(self) -> Dict[str, Type]:
        """
        Get a copy of all registered agent mappings.

        Simple query method for all agent data.

        Returns:
            Dictionary copy of agent type to class mappings
        """
        return self.agents.copy()

    def __repr__(self) -> str:
        """String representation of the agent registry."""
        agent_count = len(self.agents)
        default_info = (
            f" (default: {self.default_agent_class.__name__})"
            if self.default_agent_class
            else ""
        )
        return f"<AgentRegistry {agent_count} agents{default_info}>"
