"""
Vector Storage Service implementation for AgentMap.

This module provides a concrete implementation of the storage service
for vector databases, extracted from VectorAgent functionality.
Supports the FAISS LangChain vector store backend.

Note: This module re-exports from the refactored vector package
for backwards compatibility.
"""

# Re-export dependencies for backwards compatibility with tests
from agentmap.services.storage.vector.dependencies import (
    FAISS,
    OpenAIEmbeddings,
    langchain,
)

# Re-export the main service class for backwards compatibility
from agentmap.services.storage.vector.service import VectorStorageService

__all__ = [
    "VectorStorageService",
    "langchain",
    "OpenAIEmbeddings",
    "FAISS",
]
