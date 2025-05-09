"""
Agent loader for AgentMap.

This module provides utilities for dynamically loading agent classes
and creating agent instances based on type strings.
"""
from typing import Dict, Any

from agentmap.agents.registry import get_agent_class


class AgentLoader:
    """
    Utility for loading and instantiating agent instances.
    
    This class provides convenient methods for creating agent instances
    based on their registered type strings.
    """
    
    def __init__(self, context: Dict[str, Any] = None):
        """
        Initialize the agent loader.
        
        Args:
            context: Context dictionary to pass to created agents
        """
        self.context = context or {}
        
    def get_agent(self, agent_type: str, name: str, prompt: str) -> Any:
        """
        Get an agent instance by type.
        
        Args:
            agent_type: The type identifier for the agent
            name: Name of the agent node
            prompt: Prompt or instruction
            
        Returns:
            Agent instance
            
        Raises:
            ValueError: If agent type not found
        """
        agent_class = get_agent_class(agent_type)
        if not agent_class:
            raise ValueError(f"Agent type '{agent_type}' not found.")
        return agent_class(name=name, prompt=prompt, context=self.context)


def create_agent(agent_type: str, name: str, prompt: str, context: Dict[str, Any] = None) -> Any:
    """
    Create an agent instance with the given parameters.
    
    Args:
        agent_type: The type identifier for the agent
        name: Name of the agent node
        prompt: Prompt or instruction
        context: Context dictionary to pass to the agent
        
    Returns:
        Agent instance
    """
    loader = AgentLoader(context or {})
    return loader.get_agent(agent_type, name, prompt)