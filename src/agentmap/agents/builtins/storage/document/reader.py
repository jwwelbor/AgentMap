"""
Base document reader agent implementation.

This module provides the foundation for reading documents from various
storage backends, with standardized error handling and result formatting.
"""

from __future__ import annotations

from typing import Any, Dict

from agentmap.agents.builtins.storage.document.base_agent import (
    DocumentStorageAgent,
)
from agentmap.models.storage import DocumentResult


class DocumentReaderAgent(DocumentStorageAgent):
    """
    Base class for document reader agents.

    Provides common functionality for reading documents from various storage backends.
    Concrete implementations are provided for JSON, Firebase, etc.
    """

    def _validate_inputs(self, inputs: Dict[str, Any]) -> None:
        """
        Validate inputs for read operations.

        Args:
            inputs: Input dictionary

        Raises:
            ValueError: If inputs are invalid
        """
        self._validate_reader_inputs(inputs)

    def _execute_operation(self, collection: str, inputs: Dict[str, Any]) -> Any:
        """
        Execute read operation.

        Args:
            collection: Collection identifier
            inputs: Input dictionary

        Returns:
            Read operation result
        """
        # Extract optional parameters
        document_id = inputs.get("document_id")
        query = inputs.get("query")
        path = inputs.get("path")

        # Log the operation details
        self._log_read_operation(collection, document_id, query, path)

        # Perform the actual read operation
        return self._read_document(collection, document_id, query, path)

    def _process_result(self, result: Any, inputs: Dict[str, Any]) -> Any:
        """
        Process read operation result.

        Args:
            result: Read operation result
            inputs: Input dictionary

        Returns:
            Processed result
        """
        # Return default value if result is None and default is provided
        if result is None and "default" in inputs:
            self.log_debug(f"[{self.__class__.__name__}] Using default value")
            return inputs["default"]

        return result

    def _handle_operation_error(
        self, error: Exception, collection: str, inputs: Dict[str, Any]
    ) -> DocumentResult:
        """
        Handle read operation errors.

        Args:
            error: The exception that occurred
            collection: Collection identifier
            inputs: Input dictionary

        Returns:
            DocumentResult with error information
        """
        return self._handle_storage_error(
            error,
            "read",
            collection,
            document_id=inputs.get("document_id"),
            path=inputs.get("path"),
        )
