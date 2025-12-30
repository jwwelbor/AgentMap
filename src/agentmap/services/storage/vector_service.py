"""
Vector Storage Service implementation for AgentMap.

This module provides a concrete implementation of the storage service
for vector databases, extracted from VectorAgent functionality.
Supports Chroma, FAISS, and other LangChain vector stores.

Note: This module re-exports from the refactored vector package
for backwards compatibility.
"""

# Re-export the main service class for backwards compatibility
from agentmap.services.storage.vector.service import VectorStorageService

# Re-export dependencies for backwards compatibility with tests
from agentmap.services.storage.vector.dependencies import (
    langchain,
    OpenAIEmbeddings,
    Chroma,
    FAISS,
)

__all__ = [
    "VectorStorageService",
    "langchain",
    "OpenAIEmbeddings",
    "Chroma",
    "FAISS",
]
