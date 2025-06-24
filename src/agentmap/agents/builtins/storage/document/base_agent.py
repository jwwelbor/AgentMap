"""
Base document storage agent implementation.

This module provides the foundation for document-based storage agents,
with methods for reading, writing, and manipulating structured documents.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, TypeVar, Union

from agentmap.agents.builtins.storage.base_storage_agent import (
    BaseStorageAgent,
)
from agentmap.models.storage import DocumentResult, WriteMode

T = TypeVar("T")  # Generic type for document data


class DocumentStorageAgent(BaseStorageAgent):
    """
    Base class for document storage agents.

    Provides a common interface for working with document-oriented storage
    systems like JSON files, Firebase, Supabase, CosmosDB, etc.

    This abstract class defines the contract that all document storage
    implementations must follow.
    """

    def _read_document(
        self,
        collection: str,
        document_id: Optional[str] = None,
        query: Optional[Dict[str, Any]] = None,
        path: Optional[str] = None,
    ) -> Any:
        """
        Read a document or collection of documents.

        Args:
            collection: Collection identifier
            document_id: Optional specific document ID
            query: Optional query parameters
            path: Optional path within document

        Returns:
            Document data

        Raises:
            NotImplementedError: When not implemented by subclass
        """
        raise NotImplementedError("Subclasses must implement _read_document")

    def _write_document(
        self,
        collection: str,
        data: Any,
        document_id: Optional[str] = None,
        mode: Union[WriteMode, str] = WriteMode.WRITE,
        path: Optional[str] = None,
    ) -> DocumentResult:
        """
        Write a document or update an existing one.

        Args:
            collection: Collection identifier
            data: Data to write
            document_id: Optional document ID
            mode: Write mode (write, update, merge, delete)
            path: Optional path within document

        Returns:
            Operation result

        Raises:
            NotImplementedError: When not implemented by subclass
        """
        raise NotImplementedError("Subclasses must implement _write_document")

    def _apply_document_query(self, data: Any, query: Dict[str, Any]) -> Any:
        """
        Apply query filtering to document data.

        Args:
            data: Document data to filter
            query: Query parameters

        Returns:
            Filtered data

        Raises:
            NotImplementedError: When not implemented by subclass
        """
        raise NotImplementedError("Subclasses must implement _apply_document_query")

    def _apply_document_path(self, data: Any, path: str) -> Any:
        """
        Extract data from a specific path within a document.

        Args:
            data: Document data
            path: Path expression (e.g. "users.0.name")

        Returns:
            Data at specified path

        Raises:
            NotImplementedError: When not implemented by subclass
        """
        raise NotImplementedError("Subclasses must implement _apply_document_path")

    def _update_document_path(self, data: Any, path: str, value: Any) -> Any:
        """
        Update data at a specific path within a document.

        Args:
            data: Document data
            path: Path expression
            value: New value

        Returns:
            Updated document

        Raises:
            NotImplementedError: When not implemented by subclass
        """
        raise NotImplementedError("Subclasses must implement _update_document_path")

    def _ensure_document_exists(self, collection: str, document_id: str) -> bool:
        """
        Check if a document exists.

        Args:
            collection: Collection identifier
            document_id: Document ID

        Returns:
            True if document exists

        Raises:
            NotImplementedError: When not implemented by subclass
        """
        raise NotImplementedError("Subclasses must implement _ensure_document_exists")
