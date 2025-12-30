"""
Vector storage package for AgentMap.

This package provides modular components for vector database operations:
- dependencies: Import handling for optional LangChain components
- embeddings: Embedding model management
- providers: Vector store factory (Chroma, FAISS)
- service: Main VectorStorageService implementation
"""

from agentmap.services.storage.vector.service import VectorStorageService
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
