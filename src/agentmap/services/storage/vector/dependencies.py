"""
Dependency handling for vector storage components.

This module centralizes all optional imports for LangChain and vector store
backends, providing fallback handling and availability checking.
"""

from importlib import import_module
from types import ModuleType
from typing import Any, Optional, cast


def _load_optional_module(module_name: str) -> Optional[ModuleType]:
    """Import an optional module without making it a required dependency."""
    try:
        return import_module(module_name)
    except ImportError:
        return None


def _load_optional_symbol(module_name: str, symbol_name: str) -> Any:
    """Load an optional symbol, returning None when its package is unavailable."""
    module = _load_optional_module(module_name)
    if module is None:
        return None
    return getattr(module, symbol_name, None)


# Optional langchain import for vector operations
langchain: Optional[ModuleType] = _load_optional_module("langchain")

# Optional embeddings imports
OpenAIEmbeddings: Optional[type[Any]] = cast(
    Optional[type[Any]],
    _load_optional_symbol("langchain_openai", "OpenAIEmbeddings")
    or _load_optional_symbol("langchain_community.embeddings", "OpenAIEmbeddings"),
)

FAISS: Optional[type[Any]] = cast(
    Optional[type[Any]],
    _load_optional_symbol("langchain_community.vectorstores", "FAISS"),
)


__all__ = [
    "langchain",
    "OpenAIEmbeddings",
    "FAISS",
]
