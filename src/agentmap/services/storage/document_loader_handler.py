"""
Document Loader Handler for FileStorageService.

This module provides LangChain document loader integration,
supporting various document formats and providing fallback mechanisms.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from logging import Logger


class DocumentLoaderHandler:
    """
    Handles document loading using LangChain loaders.

    Provides methods to load various document formats, filter documents,
    and extract specific content from loaded documents.
    """

    def __init__(self, logger: "Logger"):
        """
        Initialize the document loader handler.

        Args:
            logger: Logger instance for warnings and errors
        """
        self._logger = logger

    def get_file_loader(self, file_path: str) -> Any:
        """
        Get appropriate LangChain document loader.

        Args:
            file_path: Path to the document file

        Returns:
            LangChain document loader instance

        Raises:
            ValueError: For unsupported file types
            ImportError: When dependencies for a file type aren't installed
        """
        file_ext = Path(file_path).suffix.lower()

        try:
            if file_ext == ".txt":
                from langchain_community.document_loaders import TextLoader

                return TextLoader(file_path)
            elif file_ext == ".pdf":
                from langchain_community.document_loaders import PyPDFLoader

                return PyPDFLoader(file_path)
            elif file_ext == ".md":
                from langchain_community.document_loaders import (
                    UnstructuredMarkdownLoader,
                )

                return UnstructuredMarkdownLoader(file_path)
            elif file_ext in [".html", ".htm"]:
                from langchain_community.document_loaders import UnstructuredHTMLLoader

                return UnstructuredHTMLLoader(file_path)
            elif file_ext in [".docx", ".doc"]:
                from langchain_community.document_loaders import (
                    UnstructuredWordDocumentLoader,
                )

                return UnstructuredWordDocumentLoader(file_path)
            elif file_ext == ".csv":
                from langchain_community.document_loaders import CSVLoader

                return CSVLoader(file_path)
            else:
                # Default to text loader for unknown types
                from langchain_community.document_loaders import TextLoader

                return TextLoader(file_path)
        except ImportError as e:
            self._logger.warning(f"LangChain document loaders not available ({e})")
            return self.create_fallback_loader(file_path)
        except Exception as e:
            raise ValueError(f"Error creating loader for {file_path}: {e}")

    def create_fallback_loader(self, file_path: str) -> Any:
        """
        Create fallback loader when LangChain unavailable.

        Args:
            file_path: Path to the document file

        Returns:
            Simple loader object with a load method
        """

        # Define a simple Document class for fallback
        class SimpleDocument:
            def __init__(self, content: str, metadata: Optional[Dict] = None):
                self.page_content = content
                self.metadata = metadata or {"source": file_path}

        # Create a simple loader
        class FallbackLoader:
            def __init__(self, file_path: str):
                self.file_path = file_path

            def load(self) -> List[SimpleDocument]:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                return [SimpleDocument(content)]

        return FallbackLoader(file_path)

    def filter_by_id(self, documents: List[Any], document_id: str) -> List[Any]:
        """
        Filter documents by ID or index.

        Args:
            documents: List of documents
            document_id: Document ID or index

        Returns:
            Filtered document list
        """
        # Try to filter by metadata ID
        filtered = [
            doc
            for doc in documents
            if hasattr(doc, "metadata") and doc.metadata.get("id") == document_id
        ]

        # If no matches by ID, try as index if it's numeric
        if not filtered and document_id.isdigit():
            idx = int(document_id)
            if 0 <= idx < len(documents):
                return [documents[idx]]

        return filtered

    def apply_document_path(self, documents: Union[List[Any], Any], path: str) -> Any:
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

    def apply_query_filter(
        self, documents: List[Any], query: Union[Dict[str, Any], str]
    ) -> List[Any]:
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
