"""
Registry for AgentMap agent components.

This module provides registration and discovery functionality for agents,
serving as a dependency inversion layer to prevent circular imports.
"""
from typing import Dict, Any, Type, Optional


class Registry:
    """
    Registry for managing agent types and their implementations.
    
    This class provides a centralized registry that decouples agent registration
    from agent usage, allowing for a cleaner dependency structure in the codebase.
    """
    
    def __init__(self):
        self._agents: Dict[str, Type] = {}
        self._default_agent_class = None
    
    def register(self, agent_type: str, agent_class: Type) -> None:
        """
        Register an agent class with a given type.
        
        Args:
            agent_type: String identifier for the agent type
            agent_class: Agent class to register
        """
        self._agents[agent_type.lower()] = agent_class
        
        # If this is the default agent, store it separately
        if agent_type.lower() == "default":
            self._default_agent_class = agent_class
        
    def get(self, agent_type: str, default: Optional[Type] = None) -> Optional[Type]:
        """
        Get an agent class by type, with optional default.
        
        Args:
            agent_type: Type identifier to look up
            default: Default value to return if not found
            
        Returns:
            The agent class or the default value if not found
        """
        if not agent_type:
            return self._default_agent_class or default
        return self._agents.get(agent_type.lower(), default)
    
    def list_agents(self) -> Dict[str, Type]:
        """
        Get a dictionary of all registered agent types and classes.
        
        Returns:
            Dictionary mapping agent types to agent classes
        """
        return self._agents.copy()


# Create singleton instance
agent_registry = Registry()


def register_agent(agent_type: str, agent_class: Type) -> None:
    """
    Register an agent class in the global registry.
    
    Args:
        agent_type: String identifier for the agent type
        agent_class: Agent class to register
    """
    agent_registry.register(agent_type, agent_class)


def get_agent_class(agent_type: str) -> Optional[Type]:
    """
    Get an agent class from the global registry.
    
    Args:
        agent_type: Type identifier to look up
        
    Returns:
        The agent class or None if not found
    """
    return agent_registry.get(agent_type)


def get_agent_map() -> Dict[str, Type]:
    """
    Get a dictionary of all registered agent types and classes.
    
    Returns:
        Dictionary mapping agent types to agent classes
    """
    return agent_registry.list_agents()