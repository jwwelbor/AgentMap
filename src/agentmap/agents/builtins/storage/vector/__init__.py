"""
Vector storage module for AgentMap.

This module provides integration with vector databases through LangChain,
supporting similarity search and document storage operations.

Agent registration is handled by ApplicationBootstrapService during application
bootstrap, not at import time. This provides clean separation of concerns.
"""

from agentmap.agents.builtins.storage.vector.base_agent import VectorAgent
from agentmap.agents.builtins.storage.vector.reader import VectorReaderAgent
from agentmap.agents.builtins.storage.vector.writer import VectorWriterAgent

__all__ = ["VectorAgent", "VectorReaderAgent", "VectorWriterAgent"]
