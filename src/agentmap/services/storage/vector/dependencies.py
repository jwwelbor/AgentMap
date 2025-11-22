"""
Dependency handling for vector storage components.
"""

try:
    import langchain
except ImportError:
    langchain = None

try:
    from langchain_openai import OpenAIEmbeddings
except ImportError:
    try:
        from langchain_community.embeddings import OpenAIEmbeddings
    except ImportError:
        OpenAIEmbeddings = None

try:
    from langchain_chroma import Chroma
except ImportError:
    try:
        from langchain_community.vectorstores import Chroma
    except ImportError:
        Chroma = None

try:
    from langchain_community.vectorstores import FAISS
except ImportError:
    FAISS = None

__all__ = ["langchain", "OpenAIEmbeddings", "Chroma", "FAISS"]
