"""
Vector storage package for AgentMap.

This package provides modular components for vector database operations:
- dependencies: Import handling for optional LangChain components
- embeddings: Embedding model management
- providers: Vector store factory (FAISS)
- service: Main VectorStorageService implementation
"""

from agentmap.services.storage.vector.dependencies import (
    FAISS,
    OpenAIEmbeddings,
    langchain,
)
from agentmap.services.storage.vector.service import VectorStorageService

__all__ = [
    "VectorStorageService",
    "langchain",
    "OpenAIEmbeddings",
    "FAISS",
]
