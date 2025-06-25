"""
Base document storage types and utilities.

This module provides the base classes and mixins for document-oriented storage,
including readers, writers, and path manipulation utilities.
"""

from agentmap.agents.builtins.storage.document.base_agent import DocumentStorageAgent
from agentmap.agents.builtins.storage.document.path_mixin import DocumentPathMixin
from agentmap.agents.builtins.storage.document.reader import DocumentReaderAgent
from agentmap.agents.builtins.storage.document.writer import DocumentWriterAgent

# Import types from models (where they belong)
from agentmap.models.storage import DocumentResult, WriteMode

__all__ = [
    "DocumentStorageAgent",
    "DocumentReaderAgent",
    "DocumentWriterAgent",
    "DocumentResult",
    "WriteMode",
    "DocumentPathMixin",
]
