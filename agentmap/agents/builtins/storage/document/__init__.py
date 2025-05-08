# agentmap/agents/builtins/storage/document/__init__.py
"""
Base document storage types and utilities.

This module provides the base classes and mixins for document-oriented storage,
including readers, writers, and path manipulation utilities.
"""

from agentmap.agents.builtins.storage.document.document_storage_agent import (
    BaseDocumentStorageAgent, DocumentReaderAgent, DocumentWriterAgent, DocumentResult, WriteMode
)
from agentmap.agents.builtins.storage.document.document_path_mixin import DocumentPathMixin

__all__ = [
    'BaseDocumentStorageAgent',
    'DocumentReaderAgent',
    'DocumentWriterAgent',
    'DocumentResult',
    'WriteMode',
    'DocumentPathMixin',
]