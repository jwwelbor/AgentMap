"""
File storage agents for AgentMap.

This module provides agents for reading from and writing to various file formats
beyond what specialized agents (like CSV or JSON) already handle.
"""

from agentmap.agents.builtins.storage.file.reader import FileReaderAgent
from agentmap.agents.builtins.storage.file.writer import FileWriterAgent

__all__ = [
    'FileReaderAgent',
    'FileWriterAgent',
]