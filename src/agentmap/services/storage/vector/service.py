"""
Vector Storage Service implementation for AgentMap.
"""

import os
import shutil
from typing import Any, Dict, List, Optional

from agentmap.services.config.storage_config_service import StorageConfigService
from agentmap.services.logging_service import LoggingService
from agentmap.services.storage.base import BaseStorageService
from agentmap.services.storage.types import StorageResult, WriteMode
from agentmap.services.storage.vector.embeddings import EmbeddingsManager
from agentmap.services.storage.vector.providers import VectorStoreFactory


class VectorStorageService(BaseStorageService):
    """
    Vector storage service using composition with EmbeddingsManager and VectorStoreFactory.

    This service orchestrates vector storage operations by delegating to specialized
    components rather than implementing the logic directly.
    """

    def __init__(
        self,
        provider_name: str,
        configuration: StorageConfigService,
        logging_service: LoggingService,
        file_path_service: Any = None,
        base_directory: str = None,
    ):
        super().__init__(
            provider_name,
            configuration,
            logging_service,
            file_path_service,
            base_directory,
        )

        # Initialize composed services after client is initialized
        self._embeddings_manager: Optional[EmbeddingsManager] = None
        self._vector_store_factory: Optional[VectorStoreFactory] = None

    def _initialize_client(self) -> Dict[str, Any]:
        """Initialize vector storage client configuration and composed services."""
        vector_config = self.configuration.get_vector_config()
        store_key = vector_config.get("store_key", "_vector_store")
        persist_directory = str(self.configuration.get_vector_data_path())
        provider = vector_config.get("provider", "chroma")
        embedding_model = vector_config.get("embedding_model", "openai")
        k = vector_config.get("k", 4)
        if isinstance(k, str):
            k = int(k)
        config = {
            "store_key": store_key,
            "persist_directory": persist_directory,
            "provider": provider,
            "embedding_model": embedding_model,
            "k": k,
            "_vector_stores": {},
            "_embeddings": None,
        }
        os.makedirs(config["persist_directory"], exist_ok=True)

        # Initialize composed services
        self._embeddings_manager = EmbeddingsManager(config, self._logger)
        self._vector_store_factory = VectorStoreFactory(
            config, self._embeddings_manager, self._logger
        )

        return config

    def _get_vector_store(self, collection: str = "default") -> Any:
        """
        Get vector store for collection (delegates to factory).

        This method provides backward compatibility for tests and legacy code.
        New code should use self._vector_store_factory.get_vector_store directly.
        """
        return self._vector_store_factory.get_vector_store(collection)

    def _perform_health_check(self) -> bool:
        """Check if vector storage dependencies are available."""
        try:
            if not self._vector_store_factory.check_langchain():
                return False
            persist_dir = self.client["persist_directory"]
            if not os.path.exists(persist_dir):
                os.makedirs(persist_dir, exist_ok=True)
            if not os.access(persist_dir, os.W_OK | os.R_OK):
                return False
            embeddings = self._embeddings_manager.get_embeddings()
            return embeddings is not None
        except Exception as e:
            self._logger.debug(f"Vector health check failed: {e}")
            return False

    def read(
        self,
        collection: str,
        document_id: Optional[str] = None,
        query: Optional[Dict[str, Any]] = None,
        path: Optional[str] = None,
        **kwargs,
    ) -> Any:
        """Perform similarity search on vector store."""
        try:
            vector_store = self._get_vector_store(collection)
            if vector_store is None:
                self._logger.error(
                    f"Failed to get vector store for collection: {collection}"
                )
                return None
            if query and "text" in query:
                search_query = query["text"]
            elif query and "query" in query:
                search_query = query["query"]
            else:
                self._logger.error(
                    "No search query provided in 'text' or 'query' field"
                )
                return None
            k = kwargs.get("k", self.client["k"])
            metadata_keys = kwargs.get("metadata_keys")
            results = vector_store.similarity_search(search_query, k=k)
            formatted_results = []
            for doc in results:
                result_item = {"content": doc.page_content}
                if hasattr(doc, "metadata"):
                    if metadata_keys:
                        result_item["metadata"] = {
                            k: v for k, v in doc.metadata.items() if k in metadata_keys
                        }
                    else:
                        result_item["metadata"] = doc.metadata
                formatted_results.append(result_item)
            return formatted_results
        except Exception as e:
            self._handle_error("read", e, collection=collection)
            return None

    def write(
        self,
        collection: str,
        data: Any,
        document_id: Optional[str] = None,
        mode: WriteMode = WriteMode.WRITE,
        path: Optional[str] = None,
        **kwargs,
    ) -> StorageResult:
        """Store documents in vector database."""
        try:
            vector_store = self._get_vector_store(collection)
            if vector_store is None:
                return self._create_error_result(
                    "write", "Failed to initialize vector store", collection=collection
                )
            ids = []
            stored_count = 0
            if hasattr(data, "page_content"):
                self._logger.debug(f"Writing single LangChain document to {collection}")
                ids = vector_store.add_documents([data])
                stored_count = 1
            elif isinstance(data, list) and data and hasattr(data[0], "page_content"):
                self._logger.debug(
                    f"Writing {len(data)} LangChain documents to {collection}"
                )
                ids = vector_store.add_documents(data)
                stored_count = len(data)
            else:
                if not isinstance(data, list):
                    data = [data]
                texts = [str(doc) for doc in data]
                self._logger.debug(
                    f"Writing {len(texts)} text documents to {collection}"
                )
                ids = vector_store.add_texts(texts)
                stored_count = len(texts)
            if ids is None:
                ids = []
            should_persist = kwargs.get("should_persist", True)
            if should_persist and hasattr(vector_store, "persist"):
                self._logger.debug(
                    f"Persisting vector store for collection {collection}"
                )
                vector_store.persist()
            return self._create_success_result(
                "write", collection=collection, total_affected=stored_count, ids=ids
            )
        except Exception as e:
            return self._create_error_result(
                "write", f"Vector storage failed: {str(e)}", collection=collection
            )

    def delete(
        self,
        collection: str,
        document_id: Optional[str] = None,
        path: Optional[str] = None,
        **kwargs,
    ) -> StorageResult:
        """Delete from vector database."""
        try:
            if document_id is None:
                # Delete entire collection
                self._vector_store_factory.remove_from_cache(collection)
                persist_dir = os.path.join(self.client["persist_directory"], collection)
                if os.path.exists(persist_dir):
                    shutil.rmtree(persist_dir)
                return self._create_success_result(
                    "delete", collection=collection, is_collection=True
                )
            else:
                # Individual document deletion
                vector_store = self._get_vector_store(collection)
                if vector_store is None:
                    return self._create_error_result(
                        "delete", "Vector store not found", collection=collection
                    )
                if hasattr(vector_store, "delete"):
                    vector_store.delete([document_id])
                    return self._create_success_result(
                        "delete",
                        collection=collection,
                        document_id=document_id,
                        total_affected=1,
                    )
                else:
                    return self._create_error_result(
                        "delete",
                        "Individual document deletion not supported by this vector store",
                        collection=collection,
                    )
        except Exception as e:
            self._handle_error(
                "delete", e, collection=collection, document_id=document_id
            )
            return self._create_error_result(
                "delete", f"Vector deletion failed: {str(e)}", collection=collection
            )

    def exists(self, collection: str, document_id: Optional[str] = None) -> bool:
        try:
            if collection in self.client["_vector_stores"]:
                return True
            persist_dir = os.path.join(self.client["persist_directory"], collection)
            return os.path.exists(persist_dir)
        except Exception as e:
            self._logger.debug(f"Error checking existence: {e}")
            return False

    def count(self, collection: str, query: Optional[Dict[str, Any]] = None) -> int:
        """Count documents in vector collection."""
        try:
            vector_store = self._get_vector_store(collection)
            if vector_store is None:
                return 0

            # Use efficient count methods if available for the provider
            if hasattr(vector_store, "_collection") and hasattr(
                vector_store._collection, "count"
            ):  # Chroma
                return vector_store._collection.count()
            if hasattr(vector_store, "index") and hasattr(
                vector_store.index, "ntotal"
            ):  # FAISS
                return vector_store.index.ntotal

            # Fallback to less efficient method
            self._logger.warning(
                "Using inefficient similarity_search to count documents. "
                "Consider implementing a provider-specific count method."
            )
            results = vector_store.similarity_search("", k=10000)
            return len(results)

        except Exception as e:
            self._logger.debug(f"Error counting documents: {e}")
            return 0

    def list_collections(self) -> List[str]:
        try:
            persist_dir = self.client["persist_directory"]
            if not os.path.exists(persist_dir):
                return []
            collections = []
            for item in os.listdir(persist_dir):
                item_path = os.path.join(persist_dir, item)
                if os.path.isdir(item_path):
                    collections.append(item)
            return sorted(collections)
        except Exception as e:
            self._logger.debug(f"Error listing collections: {e}")
            return []

    def similarity_search(
        self, collection: str, query: str, k: int = None, **kwargs
    ) -> List[Dict]:
        if k is None:
            k = self.client["k"]
        result = self.read(collection=collection, query={"text": query}, k=k, **kwargs)
        return result or []

    def add_documents(
        self, collection: str, documents: List[Any], **kwargs
    ) -> List[str]:
        result = self.write(collection=collection, data=documents, **kwargs)
        if result and result.success and hasattr(result, "ids"):
            return result.ids
        return []


__all__ = ["VectorStorageService"]
