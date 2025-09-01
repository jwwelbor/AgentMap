"""
Vector Storage Service implementation for AgentMap.

This module provides a concrete implementation of the storage service
for vector databases, extracted from VectorAgent functionality.
Supports Chroma, FAISS, and other LangChain vector stores.
"""

import os
import shutil
from typing import Any, Dict, List, Optional

from agentmap.services.config.storage_config_service import StorageConfigService
from agentmap.services.logging_service import LoggingService
from agentmap.services.storage.base import BaseStorageService
from agentmap.services.storage.types import StorageResult, WriteMode

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

# Optional vector store imports
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
    try:
        from langchain_community.vectorstores import FAISS
    except ImportError:
        FAISS = None


class VectorStorageService(BaseStorageService):
    """
    Vector storage service implementation using LangChain.

    Provides vector database operations including similarity search,
    document storage, and support for multiple vector store backends.
    """

    def __init__(
        self,
        provider_name: str,
        configuration: StorageConfigService,
        logging_service: LoggingService,
        file_path_service: Any = None,
        base_directory: str = None,
    ):
        """Initialize VectorStorageService with configuration service (following BaseStorageService pattern)."""
        # Call parent constructor first
        super().__init__(
            provider_name,
            configuration,
            logging_service,
            file_path_service,
            base_directory,
        )

        # Vector-specific initialization will be handled in _initialize_client
        # Logger is now inherited from BaseStorageService

    # client property is inherited from BaseStorageService

    def _initialize_client(self) -> Dict[str, Any]:
        """
        Initialize vector storage client configuration.

        Returns:
            Configuration dict for vector operations
        """
        # Get vector configuration using StorageConfigService
        vector_config = self.configuration.get_vector_config()

        # Get configuration values with defaults
        store_key = vector_config.get("store_key", "_vector_store")
        persist_directory = str(self.configuration.get_vector_data_path())
        provider = vector_config.get("provider", "chroma")
        embedding_model = vector_config.get("embedding_model", "openai")
        k = vector_config.get("k", 4)

        # Ensure k is an integer
        if isinstance(k, str):
            k = int(k)

        config = {
            "store_key": store_key,
            "persist_directory": persist_directory,
            "provider": provider,
            "embedding_model": embedding_model,
            "k": k,
            # Vector store instances will be cached here
            "_vector_stores": {},
            "_embeddings": None,
        }

        # Ensure persist directory exists
        os.makedirs(config["persist_directory"], exist_ok=True)

        return config

    # health_check method is inherited from BaseStorageService

    def _perform_health_check(self) -> bool:
        """Check if vector storage dependencies are available."""
        try:
            # Check LangChain availability
            if not self._check_langchain():
                return False

            # Check if persist directory is accessible
            persist_dir = self.client["persist_directory"]
            if not os.path.exists(persist_dir):
                os.makedirs(persist_dir, exist_ok=True)

            if not os.access(persist_dir, os.W_OK | os.R_OK):
                return False

            # Try to create embeddings model
            embeddings = self._get_embeddings()
            return embeddings is not None

        except Exception as e:
            self._logger.debug(f"Vector health check failed: {e}")
            return False

    # Error handling methods are inherited from BaseStorageService

    def _check_langchain(self) -> bool:
        """Check if LangChain is available."""
        if langchain is None:
            self._logger.error(
                "LangChain not installed. Use 'pip install langchain langchain-openai'"
            )
            return False
        return True

    def _get_embeddings(self) -> Any:
        """Get or create embeddings model."""
        if self.client["_embeddings"] is not None:
            return self.client["_embeddings"]

        embedding_type = self.client["embedding_model"].lower()

        try:
            if OpenAIEmbeddings is None:
                self._logger.error(
                    "OpenAI embeddings not available. Install with 'pip install langchain-openai'"
                )
                return None

            if embedding_type == "openai":
                embeddings = OpenAIEmbeddings()
                self.client["_embeddings"] = embeddings
                return embeddings
            else:
                self._logger.error(f"Unsupported embedding model: {embedding_type}")
                return None
        except Exception as e:
            self._logger.error(f"Failed to initialize embeddings: {e}")
            return None

    def _get_vector_store(self, collection: str = "default") -> Any:
        """Get or create vector store for collection."""
        # Check cache first
        if collection in self.client["_vector_stores"]:
            return self.client["_vector_stores"][collection]

        if not self._check_langchain():
            return None

        embeddings = self._get_embeddings()
        if embeddings is None:
            return None

        provider = self.client["provider"].lower()

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
                self.client["_vector_stores"][collection] = vector_store
            return vector_store

        except Exception as e:
            self._logger.error(f"Failed to create vector store: {e}")
            return None

    def _create_chroma_store(self, embeddings: Any, collection: str) -> Any:
        """Create Chroma vector store."""
        try:
            if Chroma is None:
                self._logger.error(
                    "Chroma not installed. Install with 'pip install chromadb'"
                )
                return None

            persist_dir = os.path.join(self.client["persist_directory"], collection)
            os.makedirs(persist_dir, exist_ok=True)

            return Chroma(
                persist_directory=persist_dir,
                embedding_function=embeddings,
                collection_name=collection,
            )
        except Exception as e:
            self._logger.error(f"Failed to create Chroma store: {e}")
            return None

    def _create_faiss_store(self, embeddings: Any, collection: str) -> Any:
        """Create FAISS vector store."""
        try:
            if FAISS is None:
                self._logger.error(
                    "FAISS not installed. Install with 'pip install faiss-cpu'"
                )
                return None

            persist_dir = os.path.join(self.client["persist_directory"], collection)
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

    def read(
        self,
        collection: str,
        document_id: Optional[str] = None,
        query: Optional[Dict[str, Any]] = None,
        path: Optional[str] = None,
        **kwargs,
    ) -> Any:
        """
        Perform similarity search on vector store.

        Args:
            collection: Vector store collection name
            document_id: Not used for vector operations
            query: Should contain 'text' key for search query
            path: Not used for vector operations
            **kwargs: Additional parameters (k, metadata_keys, etc.)

        Returns:
            Search results or None if failed
        """
        try:
            vector_store = self._get_vector_store(collection)
            if vector_store is None:
                self._logger.error(
                    f"Failed to get vector store for collection: {collection}"
                )
                return None

            # Extract search parameters
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

            # Perform similarity search
            results = vector_store.similarity_search(search_query, k=k)

            # Format results
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
        """
        Store documents in vector database.

        Args:
            collection: Vector store collection name
            data: Documents to store (text, dict, list, or LangChain docs)
            document_id: Not used for vector operations
            mode: Write mode (vector stores typically append)
            path: Not used for vector operations
            **kwargs: Additional parameters

        Returns:
            StorageResult with operation details
        """
        try:
            # Get vector store for the collection
            vector_store = self._get_vector_store(collection)
            if vector_store is None:
                return self._create_error_result(
                    "write", "Failed to initialize vector store", collection=collection
                )

            # Initialize variables
            ids = []
            stored_count = 0

            # Handle different document formats
            if hasattr(data, "page_content"):  # Single LangChain document
                self._logger.debug(f"Writing single LangChain document to {collection}")
                ids = vector_store.add_documents([data])
                stored_count = 1
            elif isinstance(data, list) and data and hasattr(data[0], "page_content"):
                # List of LangChain documents
                self._logger.debug(
                    f"Writing {len(data)} LangChain documents to {collection}"
                )
                ids = vector_store.add_documents(data)
                stored_count = len(data)
            else:
                # Convert to text and add
                if not isinstance(data, list):
                    data = [data]
                texts = [str(doc) for doc in data]
                self._logger.debug(
                    f"Writing {len(texts)} text documents to {collection}"
                )
                ids = vector_store.add_texts(texts)
                stored_count = len(texts)

            # Ensure ids is a list (some vector stores might return None)
            if ids is None:
                ids = []

            # Persist if supported and requested
            should_persist = kwargs.get("should_persist", True)
            if should_persist and hasattr(vector_store, "persist"):
                self._logger.debug(
                    f"Persisting vector store for collection {collection}"
                )
                vector_store.persist()

            # Create success result
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
        """
        Delete from vector database.

        Args:
            collection: Vector store collection name
            document_id: Document ID to delete (if supported)
            path: Not used for vector operations
            **kwargs: Additional parameters

        Returns:
            StorageResult with operation details
        """
        try:
            if document_id is None:
                # Delete entire collection
                if collection in self.client["_vector_stores"]:
                    del self.client["_vector_stores"][collection]

                # Remove persist directory
                persist_dir = os.path.join(self.client["persist_directory"], collection)
                if os.path.exists(persist_dir):
                    shutil.rmtree(persist_dir)

                return self._create_success_result(
                    "delete", collection=collection, is_collection=True
                )
            else:
                # Individual document deletion (if supported by vector store)
                vector_store = self._get_vector_store(collection)
                if vector_store is None:
                    return self._create_error_result(
                        "delete", "Vector store not found", collection=collection
                    )

                # Note: Not all vector stores support individual document deletion
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
        """
        Check if vector collection exists.

        Args:
            collection: Vector store collection name
            document_id: Not used for vector operations

        Returns:
            True if collection exists, False otherwise
        """
        try:
            if collection in self.client["_vector_stores"]:
                return True

            persist_dir = os.path.join(self.client["persist_directory"], collection)
            return os.path.exists(persist_dir)

        except Exception as e:
            self._logger.debug(f"Error checking existence: {e}")
            return False

    def count(self, collection: str, query: Optional[Dict[str, Any]] = None) -> int:
        """
        Count documents in vector collection.

        Note: Most vector stores don't provide direct count functionality.
        This is a basic implementation.

        Args:
            collection: Vector store collection name
            query: Optional query parameters

        Returns:
            Estimated count (may not be exact)
        """
        try:
            vector_store = self._get_vector_store(collection)
            if vector_store is None:
                return 0

            # Basic implementation - try to get all docs with large k
            # This is not ideal but most vector stores don't have count methods
            results = vector_store.similarity_search("", k=10000)  # Rough estimate
            return len(results)

        except Exception as e:
            self._logger.debug(f"Error counting documents: {e}")
            return 0

    def list_collections(self) -> List[str]:
        """
        List all vector collections.

        Returns:
            List of collection names
        """
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

    # Vector-specific convenience methods
    def similarity_search(
        self, collection: str, query: str, k: int = None, **kwargs
    ) -> List[Dict]:
        """
        Direct similarity search interface.

        Args:
            collection: Vector store collection name
            query: Search query text
            k: Number of results to return
            **kwargs: Additional parameters

        Returns:
            List of search results
        """
        if k is None:
            k = self.client["k"]

        result = self.read(collection=collection, query={"text": query}, k=k, **kwargs)

        return result or []

    def add_documents(
        self, collection: str, documents: List[Any], **kwargs
    ) -> List[str]:
        """
        Add documents to vector store.

        Args:
            collection: Vector store collection name
            documents: List of documents to add
            **kwargs: Additional parameters

        Returns:
            List of document IDs if available
        """
        result = self.write(collection=collection, data=documents, **kwargs)

        if result and result.success and hasattr(result, "ids"):
            return result.ids
        return []
