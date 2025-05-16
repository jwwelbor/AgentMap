"""
Base document storage types and utilities.

This module provides the base classes and mixins for document-oriented storage,
including readers, writers, and path manipulation utilities.
"""

from agentmap.agents.builtins.storage.document.base_agent import (
    DocumentStorageAgent, DocumentReaderAgent, DocumentWriterAgent
)
from agentmap.agents.builtins.storage.base_storage_agent import DocumentResult, WriteMode
from agentmap.agents.builtins.storage.document.path_mixin import DocumentPathMixin

__all__ = [
    'DocumentStorageAgent',
    'DocumentReaderAgent',
    'DocumentWriterAgent',
    'DocumentResult',
    'WriteMode',
    'DocumentPathMixin',
]