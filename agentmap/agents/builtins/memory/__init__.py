"""
Memory module for conversation history.

This module provides utilities for working with LangChain memory objects,
including serialization and deserialization for state persistence.
"""

from agentmap.agents.builtins.memory.utils import (
    serialize_memory,
    deserialize_memory,
    LANGCHAIN_AVAILABLE
)

__all__ = [
    'serialize_memory',
    'deserialize_memory',
    'LANGCHAIN_AVAILABLE'
]