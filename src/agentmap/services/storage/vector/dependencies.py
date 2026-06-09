"""
Dependency handling for vector storage components.

This module centralizes all optional imports for LangChain and vector store
backends, providing fallback handling and availability checking.
"""

# Optional langchain import for vector operations
try:
    import langchain
except ImportError:
    langchain = None

# Optional embeddings imports
try:
    from langchain_openai import OpenAIEmbeddings
except ImportError:
    try:
        from langchain_community.embeddings import OpenAIEmbeddings
    except ImportError:
        OpenAIEmbeddings = None

try:
    from langchain_community.vectorstores import FAISS
except ImportError:
    FAISS = None


__all__ = [
    "langchain",
    "OpenAIEmbeddings",
    "FAISS",
]
