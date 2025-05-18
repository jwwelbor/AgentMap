"""
File storage agents for AgentMap.

This module provides agents for reading from and writing to various file formats
beyond what specialized agents (like CSV or JSON) already handle.
"""

from agentmap.agents.builtins.storage.file.reader import FileReaderAgent
from agentmap.agents.builtins.storage.file.writer import FileWriterAgent

# Register agents with the registry when available
try:
    from agentmap.agents.registry import register_agent
    
    # Register the File agents
    register_agent("file_reader", FileReaderAgent)
    register_agent("file_writer", FileWriterAgent)
    
    _registry_available = True
except ImportError:
    _registry_available = False

__all__ = [
    'FileReaderAgent',
    'FileWriterAgent',
]