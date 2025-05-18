"""
File document reader agent implementation.

This module provides an agent for reading various document types using LangChain loaders,
focusing on text documents, PDFs, Markdown, HTML, and DOCX.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from agentmap.agents.builtins.storage.base_storage_agent import (
    BaseStorageAgent, DocumentResult, log_operation)
from agentmap.agents.builtins.storage.mixins import ReaderOperationsMixin, StorageErrorHandlerMixin
from agentmap.logging import get_logger

logger = get_logger(__name__)


class FileReaderAgent(BaseStorageAgent, ReaderOperationsMixin, StorageErrorHandlerMixin):
    """
    Enhanced document reader agent using LangChain document loaders.
    
    Reads various document formats including text, PDF, Markdown, HTML, and DOCX,
    with options for chunking and filtering.
    """
    
    def __init__(self, name: str, prompt: str, context: Optional[Dict[str, Any]] = None):
        """
        Initialize the file reader agent.
        
        Args:
            name: Name of the agent node
            prompt: Prompt or instruction
            context: Additional context including chunking and format configuration
        """
        super().__init__(name, prompt, context)
        
        # Extract document processing configuration from context
        context = context or {}
        self.chunk_size = int(context.get("chunk_size", 1000))
        self.chunk_overlap = int(context.get("chunk_overlap", 200))
        self.should_split = context.get("should_split", False)
        self.include_metadata = context.get("include_metadata", True)
        
        # For testing - allows a test to inject a mock loader
        self._test_loader = None
    
    def _initialize_client(self) -> None:
        """No client needed for filesystem operations."""
        pass
    
    def _log_operation_start(self, collection: str, inputs: Dict[str, Any]) -> None:
        """
        Log the start of a file read operation.
        
        Args:
            collection: File path
            inputs: Input dictionary
        """
        logger.debug(f"[{self.__class__.__name__}] Starting read operation on file: {collection}")
    
    def _validate_inputs(self, inputs: Dict[str, Any]) -> None:
        """
        Validate inputs for file read operations.
        
        Args:
            inputs: Input dictionary
            
        Raises:
            ValueError: If inputs are invalid
        """
        super()._validate_inputs(inputs)
        self._validate_reader_inputs(inputs)
        
        # Add file-specific validation
        file_path = self.get_collection(inputs)
        if not os.path.exists(file_path) and not self._test_loader:
            raise FileNotFoundError(f"File not found: {file_path}")
    
    def _execute_operation(self, collection: str, inputs: Dict[str, Any]) -> Any:
        """
        Execute read operation for file.
        
        Args:
            collection: File path
            inputs: Input dictionary
            
        Returns:
            Read operation result
        """
        # Extract parameters
        document_id = inputs.get("document_id")
        query = inputs.get("query")
        path = inputs.get("path")
        output_format = inputs.get("format", "default")
        
        # Log the read operation
        self._log_read_operation(collection, document_id, query, path)
        
        # Read the document
        documents = self._read_document(collection, document_id, query, path)
        
        # Format the result based on requested format
        if output_format == "raw":
            # Just return the raw documents
            return documents
        elif output_format == "text":
            # Return just the text content
            if isinstance(documents, list):
                return "\n\n".join(doc.page_content for doc in documents if hasattr(doc, 'page_content'))
            elif hasattr(documents, 'page_content'):
                return documents.page_content
            else:
                return str(documents)
        else:
            # Default format - return structured result
            return self._format_result(documents, collection)
    
    def _handle_operation_error(self, error: Exception, collection: str, inputs: Dict[str, Any]) -> DocumentResult:
        """
        Handle file read operation errors.
        
        Args:
            error: The exception that occurred
            collection: File path
            inputs: Input dictionary
            
        Returns:
            DocumentResult with error information
        """
        if isinstance(error, FileNotFoundError):
            return DocumentResult(
                success=False,
                file_path=collection,
                error=f"File not found: {collection}"
            )
        
        return self._handle_storage_error(
            error,
            "file read",
            collection,
            file_path=collection
        )
    
    def _read_document(
        self, 
        file_path: str, 
        document_id: Optional[str] = None, 
        query: Optional[Dict[str, Any]] = None, 
        path: Optional[str] = None
    ) -> Any:
        """
        Read a document using LangChain document loaders.
        
        Args:
            file_path: Path to the file
            document_id: Optional section ID
            query: Optional query parameters
            path: Optional path within document
            
        Returns:
            Document content
        """
        # Use test loader if provided (for testing)
        if self._test_loader:
            loader = self._test_loader
        else:
            # Validate file exists
            file_path = os.path.expanduser(file_path)
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # Get appropriate loader
            loader = self._get_loader(file_path)
        
        # Load documents
        try:
            documents = loader.load()
            
            # Apply document ID filter if provided
            if document_id:
                documents = self._filter_by_id(documents, document_id)
                if not documents:
                    return None
            
            # Apply query filter if provided
            if query:
                documents = self._apply_query_filter(documents, query)
            
            # Apply path extraction if provided
            if path:
                return self._apply_document_path(documents, path)
            
            return documents
        except Exception as e:
            logger.error(f"Error loading {file_path}: {str(e)}")
            raise ValueError(f"Error loading {file_path}: {str(e)}")
    
    def _get_loader(self, file_path: str) -> Any:
        """
        Select appropriate LangChain document loader based on file extension.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            LangChain document loader instance
            
        Raises:
            ValueError: For unsupported file types
            ImportError: When dependencies for a file type aren't installed
        """
        file_path = file_path.lower()
        
        # Try using the new import paths first
        try:
            try:
                from langchain_community.document_loaders import TextLoader
                from langchain_community.document_loaders import PyPDFLoader
                from langchain_community.document_loaders import UnstructuredMarkdownLoader
                from langchain_community.document_loaders import UnstructuredHTMLLoader
                from langchain_community.document_loaders import UnstructuredWordDocumentLoader
                from langchain_community.document_loaders import CSVLoader
            except ImportError:
                # Fall back to legacy import paths
                from langchain.document_loaders import (
                    TextLoader, PyPDFLoader, UnstructuredMarkdownLoader,
                    UnstructuredHTMLLoader, UnstructuredWordDocumentLoader, CSVLoader
                )
            
            if file_path.endswith('.txt'):
                return TextLoader(file_path)
            elif file_path.endswith('.pdf'):
                return PyPDFLoader(file_path)
            elif file_path.endswith('.md'):
                return UnstructuredMarkdownLoader(file_path)
            elif file_path.endswith('.html') or file_path.endswith('.htm'):
                return UnstructuredHTMLLoader(file_path)
            elif file_path.endswith('.docx') or file_path.endswith('.doc'):
                return UnstructuredWordDocumentLoader(file_path)
            elif file_path.endswith('.csv'):
                return CSVLoader(file_path)
            else:
                # Default to text loader for unknown types
                return TextLoader(file_path)
        except ImportError as e:
            # Create a simple loader that returns a document with the file content
            logger.warning(f"LangChain document loaders not available ({e}), using fallback loader")
            return self._create_fallback_loader(file_path)
        except Exception as e:
            raise ValueError(f"Error creating loader for {file_path}: {e}")
    
    def _create_fallback_loader(self, file_path: str) -> Any:
        """
        Create a fallback loader when LangChain is not available.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Simple loader object with a load method
        """
        # Define a simple Document class for fallback
        class SimpleDocument:
            def __init__(self, content, metadata=None):
                self.page_content = content
                self.metadata = metadata or {"source": file_path}
        
        # Create a simple loader
        class FallbackLoader:
            def __init__(self, file_path):
                self.file_path = file_path
                
            def load(self):
                with open(self.file_path, 'r') as f:
                    content = f.read()
                return [SimpleDocument(content)]
        
        return FallbackLoader(file_path)
    
    def _filter_by_id(self, documents: List[Any], document_id: str) -> List[Any]:
        """
        Filter documents by ID or index.
        
        Args:
            documents: List of documents
            document_id: Document ID or index
            
        Returns:
            Filtered document list
        """
        # Try to filter by metadata ID
        filtered = [doc for doc in documents if doc.metadata.get('id') == document_id]
        
        # If no matches by ID, try as index if it's numeric
        if not filtered and document_id.isdigit():
            idx = int(document_id)
            if 0 <= idx < len(documents):
                return [documents[idx]]
        
        return filtered if filtered else []
    
    def _apply_document_path(self, documents: Union[List[Any], Any], path: str) -> Any:
        """
        Extract content from document(s) at specified path.
        
        Args:
            documents: Document or list of documents
            path: Path expression (e.g., "metadata.source" or "0.content")
            
        Returns:
            Content at specified path
        """
        if not path:
            return documents
            
        result = []
        
        # Handle single document case
        if not isinstance(documents, list):
            documents = [documents]
            
        for doc in documents:
            # Check for metadata paths
            if path.startswith("metadata.") and hasattr(doc, "metadata"):
                meta_key = path.split(".", 1)[1]
                if meta_key in doc.metadata:
                    result.append(doc.metadata[meta_key])
            # Default to page content
            elif hasattr(doc, "page_content"):
                result.append(doc.page_content)
            else:
                result.append(doc)
        
        return result
    
    def _apply_query_filter(self, documents: List[Any], query: Union[Dict[str, Any], str]) -> List[Any]:
        """
        Filter documents based on query parameters.
        
        Args:
            documents: List of documents
            query: Query string or dictionary
            
        Returns:
            Filtered document list
        """
        if not documents:
            return []
            
        filtered_docs = []
        
        if isinstance(query, dict):
            # Filter by metadata
            for doc in documents:
                if not hasattr(doc, "metadata"):
                    continue
                    
                matches = True
                for k, v in query.items():
                    if doc.metadata.get(k) != v:
                        matches = False
                        break
                        
                if matches:
                    filtered_docs.append(doc)
        
        elif isinstance(query, str):
            # Simple text search in content
            for doc in documents:
                if not hasattr(doc, "page_content"):
                    continue
                    
                if query.lower() in doc.page_content.lower():
                    filtered_docs.append(doc)
        
        return filtered_docs
    
    def _format_result(self, documents: Any, file_path: str) -> DocumentResult:
        """
        Format the read result as a DocumentResult.
        
        Args:
            documents: Documents read from file
            file_path: Path to the file
            
        Returns:
            Structured result object
        """
        # Convert documents to a serializable format
        formatted_docs = []
        
        if isinstance(documents, list):
            for i, doc in enumerate(documents):
                if hasattr(doc, "page_content"):
                    # LangChain document
                    item = {
                        "content": doc.page_content
                    }
                    # Include metadata if requested
                    if self.include_metadata and hasattr(doc, "metadata"):
                        item["metadata"] = doc.metadata
                    formatted_docs.append(item)
                else:
                    # Other types
                    formatted_docs.append(str(doc))
        elif hasattr(documents, "page_content"):
            # Single LangChain document
            formatted_docs = {
                "content": documents.page_content
            }
            if self.include_metadata and hasattr(documents, "metadata"):
                formatted_docs["metadata"] = documents.metadata
        else:
            # Other types
            formatted_docs = documents
        
        # Build the result object
        return DocumentResult(
            success=True,
            file_path=file_path,
            data=formatted_docs,
            count=len(formatted_docs) if isinstance(formatted_docs, list) else 1,
            is_collection=isinstance(formatted_docs, list)
        )