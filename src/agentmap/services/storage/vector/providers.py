"""
Vector store provider implementations.

This module provides factory functions for creating and managing
different vector store backends (Chroma, FAISS, etc.).
"""

import logging
import os
import sys
from typing import Any, Dict, Optional

from agentmap.services.storage.vector import dependencies as vector_deps
from agentmap.services.storage.vector.embeddings import EmbeddingsManager


def _get_parent_module_attr(attr_name: str) -> Any:
    """
    Get an attribute from the parent vector_service module.

    This allows test patches on agentmap.services.storage.vector_service
    to take effect when checking dependencies.
    """
    parent_module = sys.modules.get("agentmap.services.storage.vector_service")
    if parent_module:
        return getattr(parent_module, attr_name, None)
    # Fall back to dependencies module
    return getattr(vector_deps, attr_name, None)


class VectorStoreFactory:
    """
    Factory for creating and caching vector store instances.

    Supports Chroma and FAISS backends with automatic caching.
    """

    def __init__(
        self,
        client_config: Dict[str, Any],
        embeddings_manager: EmbeddingsManager,
        logger: logging.Logger,
    ):
        """
        Initialize the vector store factory.

        Args:
            client_config: Client configuration containing store settings
            embeddings_manager: Manager for embedding models
            logger: Logger instance for error reporting
        """
        self._client_config = client_config
        self._embeddings_manager = embeddings_manager
        self._logger = logger

    def check_langchain(self) -> bool:
        """
        Check if LangChain is available.

        Returns:
            True if LangChain is available, False otherwise
        """
        langchain = _get_parent_module_attr("langchain")
        if langchain is None:
            self._logger.error(
                "LangChain not installed. Use 'pip install langchain langchain-openai'"
            )
            return False
        return True

    def get_vector_store(self, collection: str = "default") -> Optional[Any]:
        """
        Get or create vector store for collection.

        Args:
            collection: Collection name

        Returns:
            Vector store instance or None if creation fails
        """
        # Check cache first
        vector_stores = self._client_config.get("_vector_stores", {})
        if collection in vector_stores:
            return vector_stores[collection]

        if not self.check_langchain():
            return None

        embeddings = self._embeddings_manager.get_embeddings()
        if embeddings is None:
            return None

        provider = self._client_config.get("provider", "chroma").lower()

        try:
            if provider == "chroma":
                vector_store = self._create_chroma_store(embeddings, collection)
            elif provider == "faiss":
                vector_store = self._create_faiss_store(embeddings, collection)
            else:
                self._logger.error(f"Unsupported vector store provider: {provider}")
                return None

            # Cache the vector store
            if vector_store is not None:
                if "_vector_stores" not in self._client_config:
                    self._client_config["_vector_stores"] = {}
                self._client_config["_vector_stores"][collection] = vector_store

            return vector_store

        except Exception as e:
            self._logger.error(f"Failed to create vector store: {e}")
            return None

    def _create_chroma_store(self, embeddings: Any, collection: str) -> Optional[Any]:
        """
        Create Chroma vector store.

        Args:
            embeddings: Embedding model instance
            collection: Collection name

        Returns:
            Chroma vector store instance or None if creation fails
        """
        try:
            # Get Chroma from parent module (allows test patching)
            Chroma = _get_parent_module_attr("Chroma")

            if Chroma is None:
                self._logger.error(
                    "Chroma not installed. Install with 'pip install chromadb'"
                )
                return None

            persist_dir = os.path.join(
                self._client_config["persist_directory"], collection
            )
            os.makedirs(persist_dir, exist_ok=True)

            return Chroma(
                persist_directory=persist_dir,
                embedding_function=embeddings,
                collection_name=collection,
            )

        except Exception as e:
            self._logger.error(f"Failed to create Chroma store: {e}")
            return None

    def _create_faiss_store(self, embeddings: Any, collection: str) -> Optional[Any]:
        """
        Create FAISS vector store.

        Args:
            embeddings: Embedding model instance
            collection: Collection name

        Returns:
            FAISS vector store instance or None if creation fails
        """
        try:
            # Get FAISS from parent module (allows test patching)
            FAISS = _get_parent_module_attr("FAISS")

            if FAISS is None:
                self._logger.error(
                    "FAISS not installed. Install with 'pip install faiss-cpu'"
                )
                return None

            persist_dir = os.path.join(
                self._client_config["persist_directory"], collection
            )
            os.makedirs(persist_dir, exist_ok=True)

            index_file = os.path.join(persist_dir, "index.faiss")

            if os.path.exists(index_file):
                return FAISS.load_local(persist_dir, embeddings)
            else:
                # Create empty index with placeholder
                vector_store = FAISS.from_texts(
                    ["Placeholder document for initialization"], embeddings
                )
                vector_store.save_local(persist_dir)
                return vector_store

        except Exception as e:
            self._logger.error(f"Failed to create FAISS store: {e}")
            return None

    def remove_from_cache(self, collection: str) -> None:
        """
        Remove a collection from the cache.

        Args:
            collection: Collection name to remove
        """
        vector_stores = self._client_config.get("_vector_stores", {})
        if collection in vector_stores:
            del vector_stores[collection]


__all__ = ["VectorStoreFactory"]
