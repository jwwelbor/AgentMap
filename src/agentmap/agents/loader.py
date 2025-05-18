# agentmap/agents/loader.py
"""
Agent loader for AgentMap.

This module provides utilities for dynamically loading agent classes
and creating agent instances based on type strings.
"""
from typing import Dict, Any

from agentmap.agents.features import HAS_LLM_AGENTS, HAS_STORAGE_AGENTS
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
        """Get an agent instance by type."""
        agent_type_lower = agent_type.lower()
        
        # Provide helpful error messages for missing dependencies
        if not HAS_LLM_AGENTS and agent_type_lower in ("openai", "anthropic", "google", "gpt", "claude", "gemini", "llm"):
            raise ValueError(f"LLM agent '{agent_type}' requires additional dependencies. "
                            "Install with: pip install agentmap[llm]")
        
        if not HAS_STORAGE_AGENTS and agent_type_lower in ("csv_reader", "csv_writer", "json_reader", "json_writer", 
                                                          "file_reader", "file_writer", "vector_reader", "vector_writer"):
            raise ValueError(f"Storage agent '{agent_type}' requires additional dependencies. "
                            "Install with: pip install agentmap[storage]")
        
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