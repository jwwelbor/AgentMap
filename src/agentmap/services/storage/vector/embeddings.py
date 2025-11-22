"""
Embedding model management for vector storage.

This module handles the creation and caching of embedding models
used for vector operations.
"""

import sys
from typing import Any, Dict, Optional
import logging

from agentmap.services.storage.vector import dependencies as vector_deps


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


class EmbeddingsManager:
    """
    Manages embedding model creation and caching.

    Supports OpenAI embeddings with caching for efficient reuse.
    """

    def __init__(self, client_config: Dict[str, Any], logger: logging.Logger):
        """
        Initialize the embeddings manager.

        Args:
            client_config: Client configuration containing embedding settings
            logger: Logger instance for error reporting
        """
        self._client_config = client_config
        self._logger = logger

    def get_embeddings(self) -> Optional[Any]:
        """
        Get or create embeddings model.

        Returns:
            Embeddings model instance or None if creation fails
        """
        # Return cached embeddings if available
        if self._client_config.get("_embeddings") is not None:
            return self._client_config["_embeddings"]

        embedding_type = self._client_config.get("embedding_model", "openai").lower()

        try:
            # Get OpenAIEmbeddings from parent module (allows test patching)
            OpenAIEmbeddings = _get_parent_module_attr("OpenAIEmbeddings")

            if OpenAIEmbeddings is None:
                self._logger.error(
                    "OpenAI embeddings not available. Install with 'pip install langchain-openai'"
                )
                return None

            if embedding_type == "openai":
                embeddings = OpenAIEmbeddings()
                self._client_config["_embeddings"] = embeddings
                return embeddings
            else:
                self._logger.error(f"Unsupported embedding model: {embedding_type}")
                return None

        except Exception as e:
            self._logger.error(f"Failed to initialize embeddings: {e}")
            return None

    def clear_cache(self) -> None:
        """Clear the cached embeddings model."""
        self._client_config["_embeddings"] = None


__all__ = ["EmbeddingsManager"]
