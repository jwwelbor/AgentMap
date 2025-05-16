"""
Vector storage module for AgentMap.

This module provides integration with vector databases through LangChain,
supporting similarity search and document storage operations.
"""

from agentmap.agents.builtins.storage.vector.base_agent import VectorAgent
from agentmap.agents.builtins.storage.vector.reader import VectorReaderAgent
from agentmap.agents.builtins.storage.vector.writer import VectorWriterAgent

# Register agents with the registry when available
try:
    from agentmap.agents.registry import register_agent
    
    # Register the vector agents
    register_agent("vector_reader", VectorReaderAgent)
    register_agent("vector_writer", VectorWriterAgent)
    
    _registry_available = True
except ImportError:
    _registry_available = False

__all__ = [
    'VectorAgent',
    'VectorReaderAgent',
    'VectorWriterAgent'
]