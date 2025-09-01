"""
Base document writer agent implementation.

This module provides the foundation for writing documents to various
storage backends, with standardized validation and error handling.
"""

from __future__ import annotations

from typing import Any, Dict

from agentmap.agents.builtins.storage.document.base_agent import (
    DocumentStorageAgent,
)
from agentmap.models.storage import DocumentResult, WriteMode


class DocumentWriterAgent(DocumentStorageAgent):
    """
    Base class for document writer agents.

    Provides common functionality for writing documents to various storage backends.
    Concrete implementations are provided for JSON, Firebase, etc.
    """

    def _validate_inputs(self, inputs: Dict[str, Any]) -> None:
        """
        Validate inputs for write operations.

        Args:
            inputs: Input dictionary

        Raises:
            ValueError: If inputs are invalid
        """
        self._validate_writer_inputs(inputs)

    def _execute_operation(
        self, collection: str, inputs: Dict[str, Any]
    ) -> DocumentResult:
        """
        Execute write operation.

        Args:
            collection: Collection identifier
            inputs: Input dictionary

        Returns:
            Write operation result
        """
        # Get required data for non-delete operations
        data = inputs.get("data")
        mode_str = inputs.get("mode", "append").lower()

        # Convert string mode to enum
        mode = WriteMode.from_string(mode_str)

        # Extract optional parameters
        document_id = inputs.get("document_id")
        path = inputs.get("path")

        # Log the operation details
        self._log_write_operation(collection, mode, document_id, path)

        # Perform the actual write operation
        return self._write_document(collection, data, document_id, mode, path)

    def _handle_operation_error(
        self, error: Exception, collection: str, inputs: Dict[str, Any]
    ) -> DocumentResult:
        """
        Handle write operation errors.

        Args:
            error: The exception that occurred
            collection: Collection identifier
            inputs: Input dictionary

        Returns:
            DocumentResult with error information
        """
        mode_str = inputs.get("mode", "append").lower()
        return self._handle_storage_error(
            error,
            mode_str,
            collection,
            mode=mode_str,
            document_id=inputs.get("document_id"),
            path=inputs.get("path"),
        )
