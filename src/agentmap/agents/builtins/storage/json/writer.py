"""
JSON document writer agent implementation.

This module provides a simple agent for writing data to JSON files
that delegates to JSONStorageService for the actual implementation.
"""

from __future__ import annotations

from typing import Any, Dict

from agentmap.agents.builtins.storage.json.base_agent import JSONDocumentAgent
from agentmap.models.storage import DocumentResult, WriteMode


class JSONDocumentWriterAgent(JSONDocumentAgent):
    """
    Simple agent for writing data to JSON documents via JSONStorageService.

    Delegates all JSON operations to the service layer for clean separation of concerns.
    """

    def _execute_operation(
        self, collection: str, inputs: Dict[str, Any]
    ) -> DocumentResult:
        """
        Execute write operation for JSON files by delegating to JSONStorageService.

        Args:
            collection: JSON file path
            inputs: Input dictionary

        Returns:
            Result of the write operation
        """
        self.log_info(f"Writing to {collection}")

        # Get the data to write
        data = inputs.get("data")
        if data is None:
            return DocumentResult(
                success=False, file_path=collection, error="No data provided to write"
            )

        # Get write mode
        mode_str = inputs.get("mode", "append").lower()
        try:
            mode = WriteMode.from_string(mode_str)
        except ValueError as e:
            return DocumentResult(success=False, file_path=collection, error=str(e))

        # Extract additional parameters
        document_id = inputs.get("document_id") or inputs.get("id")
        path = inputs.get("path")
        id_field = inputs.get("id_field", "id")

        # Call the JSON storage service
        result = self.json_service.write(
            collection=collection,
            data=data,
            document_id=document_id,
            mode=mode,
            path=path,
            id_field=id_field,
        )

        return result
