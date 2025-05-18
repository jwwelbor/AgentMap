"""
LLM Agent module with LangChain integration.

This module provides a base class for LLM agents with LangChain integration,
including prompt template management and conversation memory.
"""

from agentmap.agents.builtins.llm.llm_agent import (
    LLMAgent
)

from agentmap.agents.builtins.memory.utils import (
    serialize_memory, 
    deserialize_memory
)
__all__ = ['LLMAgent', 'serialize_memory', 'deserialize_memory']