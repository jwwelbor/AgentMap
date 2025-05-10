"""
File document reader agent implementation.

This module provides an agent for reading various document types using LangChain loaders,
focusing on text documents, PDFs, Markdown, HTML, and DOCX.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# In agentmap/agents/builtins/storage/file/reader.py
# In agentmap/agents/builtins/storage/file/reader.py
try:
    # New import path
    from langchain_community.document_loaders import (
        CSVLoader, TextLoader,  # Add all the classes being imported
        # other imports...
    )
except ImportError:
    # Legacy import path
    from langchain.document_loaders import (
        CSVLoader, TextLoader,  # Same imports as above
        # other imports...
    )

from langchain.text_splitter import RecursiveCharacterTextSplitter

from agentmap.agents.builtins.storage.base_storage_agent import (
    BaseStorageAgent, DocumentResult, log_operation
)
from agentmap.logging import get_logger

logger = get_logger(__name__)


class FileReaderAgent(BaseStorageAgent):
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
            prompt: File path or prompt with path
            context: Additional configuration including:
                - chunk_size: Size of text chunks when splitting (default: 1000)
                - chunk_overlap: Overlap between chunks (default: 200)
                - should_split: Whether to split documents (default: False)
                - input_fields: Input fields to use
                - output_field: Output field to return results
        """
        super().__init__(name, prompt, context)
        
        # Extract document processing configuration from context
        context = context or {}
        self.chunk_size = int(context.get("chunk_size", 1000))
        self.chunk_overlap = int(context.get("chunk_overlap", 200))
        self.should_split = context.get("should_split", False)
        self.include_metadata = context.get("include_metadata", True)
    
    def _initialize_client(self) -> None:
        """No client needed for filesystem operations."""
        pass
    
    @log_operation
    def process(self, inputs: Dict[str, Any]) -> Any:
        """
        Process inputs and read document(s).
        
        Args:
            inputs: Dictionary with keys:
                - collection: File path or collection name
                - document_id: Optional specific document section
                - query: Optional filtering criteria
                - path: Optional path within document
                - format: Optional output format (default: 'default')
                
        Returns:
            Documents read from the specified location, optionally filtered
        """
        # Get the file path from inputs
        file_path = self.get_collection(inputs)
        
        # Extract optional parameters
        document_id = inputs.get("document_id")
        query = inputs.get("query")
        path = inputs.get("path")
        output_format = inputs.get("format", "default")
        
        try:
            # Read the document
            documents = self._read_document(file_path, document_id, query, path)
            
            # Format the result based on requested format
            if output_format == "raw":
                # Just return the raw documents
                return documents
            elif output_format == "text":
                # Return just the text content
                if isinstance(documents, list):
                    return "\n\n".join(doc.page_content for doc in documents)
                elif hasattr(documents, 'page_content'):
                    return documents.page_content
                else:
                    return str(documents)
            else:
                # Default format - return structured result
                return self._format_result(documents, file_path)
                
        except Exception as e:
            # Handle and log the error
            return self._handle_error_result(file_path, e)
    
    def _read_document(self, file_path: str, document_id=None, query=None, path=None) -> Any:
        """
        Read a document using LangChain document loaders.
        
        Args:
            file_path: Path to the document file
            document_id: Optional specific document ID or section
            query: Optional query parameters
            path: Optional path within document
            
        Returns:
            Loaded documents from the file
            
        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: For unsupported file types
        """
        # Validate file exists
        file_path = os.path.expanduser(file_path)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Load document using LangChain
        loader = self._get_loader(file_path)
        documents = loader.load()
        
        # Split documents if requested
        if self.should_split and documents:
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap
            )
            documents = text_splitter.split_documents(documents)
        
        # If document_id is specified, filter to just that document
        if document_id is not None:
            documents = self._filter_by_id(documents, document_id)
        
        # If path is specified, extract that path from documents
        if path and documents:
            documents = self._apply_document_path(documents, path)
        
        # If query is specified, filter documents
        if query and documents:
            documents = self._apply_query_filter(documents, query)
        
        return documents
    
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
        
        if file_path.endswith('.txt'):
            try:
                from langchain.document_loaders import TextLoader
                return TextLoader(file_path)
            except ImportError:
                raise ImportError("langchain is required. Install with 'pip install langchain'")
                
        elif file_path.endswith('.pdf'):
            try:
                from langchain.document_loaders import PyPDFLoader
                return PyPDFLoader(file_path)
            except ImportError:
                raise ImportError("PDF support requires additional dependencies. Install with 'pip install \"unstructured[pdf]\"'")
                
        elif file_path.endswith('.md'):
            try:
                from langchain.document_loaders import UnstructuredMarkdownLoader
                return UnstructuredMarkdownLoader(file_path)
            except ImportError:
                raise ImportError("Markdown support requires additional dependencies. Install with 'pip install \"unstructured[md]\"'")
                
        elif file_path.endswith('.html') or file_path.endswith('.htm'):
            try:
                from langchain.document_loaders import UnstructuredHTMLLoader
                return UnstructuredHTMLLoader(file_path)
            except ImportError:
                raise ImportError("HTML support requires additional dependencies. Install with 'pip install unstructured'")
                
        elif file_path.endswith('.docx') or file_path.endswith('.doc'):
            try:
                from langchain.document_loaders import UnstructuredWordDocumentLoader
                return UnstructuredWordDocumentLoader(file_path)
            except ImportError:
                raise ImportError("Word document support requires additional dependencies. Install with 'pip install python-docx'")
                
        else:
            raise ValueError(f"Unsupported file type: {file_path}. Use specialized agent for this format.")
    
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
    
    def _handle_error_result(self, file_path: str, exception: Exception) -> DocumentResult:
        """
        Create an error result object.
        
        Args:
            file_path: Path to the file
            exception: Exception that occurred
            
        Returns:
            Error result object
        """
        # Log the error
        logger.error(f"Error reading file {file_path}: {str(exception)}")
        
        # Map common exceptions to appropriate errors
        if isinstance(exception, FileNotFoundError):
            error_msg = f"File not found: {file_path}"
        elif isinstance(exception, PermissionError):
            error_msg = f"Permission denied for file: {file_path}"
        elif isinstance(exception, ValueError) and "Unsupported file type" in str(exception):
            error_msg = str(exception)
        else:
            error_msg = f"Error reading file: {str(exception)}"
        
        # Return formatted error
        return DocumentResult(
            success=False,
            file_path=file_path,
            error=error_msg
        )