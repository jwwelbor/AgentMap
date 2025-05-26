"""
Base vector storage agent implementation.

This module provides the foundation for vector storage operations,
with integration for LangChain and common vector database operations.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Union

from agentmap.agents.builtins.storage.base_storage_agent import (
    BaseStorageAgent, DocumentResult, log_operation)
from agentmap.agents.mixins import StorageErrorHandlerMixin
from agentmap.logging import get_logger

logger = get_logger(__name__)


class VectorAgent(BaseStorageAgent, StorageErrorHandlerMixin):
    """
    Base class for vector storage operations with LangChain.
    
    Provides shared functionality for vector database operations,
    including embedding creation, vector store initialization,
    and common utility methods.
    """
    
    def __init__(self, name: str, prompt: str, context: Optional[Dict[str, Any]] = None):
        """
        Initialize the vector storage agent.
        
        Args:
            name: Name of the agent node
            prompt: Prompt or instruction
            context: Additional context including:
                - store_key: Key to store vectorstore in context (default: "_vector_store")
                - persist_directory: Directory for vector store persistence (default: "./.vectorstore")
                - provider: Vector store provider (default: "chroma")
                - embedding_model: Embedding model to use (default: "openai")
        """
        super().__init__(name, prompt, context or {})
        self.store_key = context.get("store_key", "_vector_store") if context else "_vector_store"
        self.persist_directory = context.get("persist_directory", "./.vectorstore") if context else "./.vectorstore"
        self.provider = context.get("provider", "chroma") if context else "chroma"
        self.embedding_model = context.get("embedding_model", "openai") if context else "openai"
        self.input_fields = context.get("input_fields", ["query"]) if context else ["query"]
        self.output_field = context.get("output_field", "result") if context else "result"
    
    def _initialize_client(self) -> None:
        """
        No client initialization needed for vector storage.
        
        Vector stores are initialized on demand during operations.
        """
        self._client = True  # Just a placeholder
    
    def _validate_inputs(self, inputs: Dict[str, Any]) -> None:
        """
        Validate inputs for vector operations.
        
        Args:
            inputs: Input dictionary
            
        Raises:
            ValueError: If inputs are invalid
        """
        super()._validate_inputs(inputs)
        
        # Check for required input field
        input_field = self.input_fields[0]
        if input_field not in inputs:
            raise ValueError(f"Missing required input field: {input_field}")
    
    def _check_langchain(self) -> bool:
        """
        Check if LangChain is available.
        
        Returns:
            True if LangChain is available, False otherwise
        """
        try:
            # Try to import langchain
            import langchain
            return True
        except ImportError:
            self.log_error("LangChain not installed. Use 'pip install langchain langchain-openai'")
            return False
    
    def _get_or_create_vectorstore(self, inputs: Dict[str, Any]) -> Any:
        """
        Get or create vector store based on configuration.
        
        Args:
            inputs: Input dictionary that may contain an existing vector store
            
        Returns:
            Initialized vector store or error dictionary
        """
        # Check if vector store exists in context
        if self.store_key in inputs:
            return inputs[self.store_key]
        
        # Check for LangChain availability
        if not self._check_langchain():
            return {"error": "LangChain not installed. Install with 'pip install langchain langchain-openai'"}
        
        # Get embeddings model
        embeddings = self._create_embeddings()
        if isinstance(embeddings, dict) and "error" in embeddings:
            return embeddings  # Return error if embedding creation failed
        
        # Create store based on provider
        provider = self.provider.lower()
        
        try:
            if provider == "chroma":
                return self._create_chroma_store(embeddings, inputs)
            elif provider == "faiss":
                return self._create_faiss_store(embeddings, inputs)
            else:
                return {"error": f"Unsupported vector store provider: {provider}"}
        except Exception as e:
            return self._handle_storage_error(
                e, "vector_store_initialization", self.provider,
                error_msg=f"Failed to initialize vector store: {str(e)}"
            )
    
    def _create_embeddings(self) -> Any:
        """
        Create embeddings model based on configuration.
        
        Returns:
            Initialized embeddings model or error dictionary
        """
        embedding_type = self.embedding_model.lower()
        
        try:
            try:
                # Try to import with newer langchain structure
                from langchain_openai import OpenAIEmbeddings
            except ImportError:
                # Fall back to legacy imports
                from langchain.embeddings import OpenAIEmbeddings
            
            if embedding_type == "openai":
                return OpenAIEmbeddings()
            else:
                return {"error": f"Unsupported embedding model: {embedding_type}"}
        except Exception as e:
            return self._handle_storage_error(
                e, "embeddings_initialization", embedding_type,
                error_msg=f"Failed to initialize embeddings: {str(e)}"
            )
    
    def _create_chroma_store(self, embeddings: Any, inputs: Dict[str, Any]) -> Any:
        """
        Create Chroma vector store.
        
        Args:
            embeddings: Embeddings model
            inputs: Input dictionary to store the vector store
            
        Returns:
            Initialized vector store or error dictionary
        """
        try:
            try:
                # Try to import with newer langchain structure
                from langchain_chroma import Chroma
            except ImportError:
                # Fall back to legacy imports
                from langchain.vectorstores import Chroma
            
            # Create directory if needed
            os.makedirs(self.persist_directory, exist_ok=True)
            
            # Create vector store
            vector_store = Chroma(
                persist_directory=self.persist_directory,
                embedding_function=embeddings
            )
            
            # Store in context
            inputs[self.store_key] = vector_store
            
            return vector_store
        except ImportError:
            return {"error": "Chroma not installed. Install with 'pip install chromadb'"}
        except Exception as e:
            return self._handle_storage_error(
                e, "chroma_store_creation", self.persist_directory,
                error_msg=f"Failed to create Chroma store: {str(e)}"
            )
    
    def _create_faiss_store(self, embeddings: Any, inputs: Dict[str, Any]) -> Any:
        """
        Create FAISS vector store.
        
        Args:
            embeddings: Embeddings model
            inputs: Input dictionary to store the vector store
            
        Returns:
            Initialized vector store or error dictionary
        """
        try:
            try:
                # Try to import with newer langchain structure
                from langchain_community.vectorstores import FAISS
            except ImportError:
                # Fall back to legacy imports
                from langchain.vectorstores import FAISS
            
            # Create directory if needed
            os.makedirs(self.persist_directory, exist_ok=True)
            
            # Check if FAISS index already exists
            import os.path
            index_file = os.path.join(self.persist_directory, "index.faiss")
            
            if os.path.exists(index_file):
                # Load existing index
                vector_store = FAISS.load_local(self.persist_directory, embeddings)
            else:
                # Create empty index with a placeholder document
                vector_store = FAISS.from_texts(
                    ["This is a placeholder document for initialization"], 
                    embeddings
                )
                # Save the index
                vector_store.save_local(self.persist_directory)
            
            # Store in context
            inputs[self.store_key] = vector_store
            
            return vector_store
        except ImportError:
            return {"error": "FAISS not installed. Install with 'pip install faiss-cpu'"}
        except Exception as e:
            return self._handle_storage_error(
                e, "faiss_store_creation", self.persist_directory,
                error_msg=f"Failed to create FAISS store: {str(e)}"
            )
    
    def _format_vector_result(self, success: bool, data: Any = None, error: str = None, **kwargs) -> Dict[str, Any]:
        """
        Format vector operation results.
        
        Args:
            success: Whether the operation was successful
            data: Result data
            error: Error message, if any
            **kwargs: Additional result fields
            
        Returns:
            Formatted result dictionary
        """
        result = {"status": "success" if success else "error"}
        
        if data is not None:
            result["data"] = data
            
        if error is not None:
            result["error"] = error
            
        # Add any additional fields
        result.update(kwargs)
        
        return result
    
    def _handle_operation_error(
        self, 
        error: Exception, 
        collection: str, 
        inputs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle vector operation errors.
        
        Args:
            error: The exception that occurred
            collection: Vector operation name or identifier
            inputs: Input dictionary
            
        Returns:
            Error result dictionary
        """
        self.log_error(f"Vector operation error ({collection}): {str(error)}")
        return self._format_vector_result(
            success=False,
            error=f"Operation failed: {str(error)}"
        )