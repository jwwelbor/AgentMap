"""
JSON document reader agent implementation.

This module provides a simple agent for reading data from JSON files
that delegates to JSONStorageService for the actual implementation.
"""

from __future__ import annotations

from typing import Any, Dict

from agentmap.agents.builtins.storage.json.base_agent import JSONDocumentAgent


class JSONDocumentReaderAgent(JSONDocumentAgent):
    """
    Simple agent for reading data from JSON documents via JSONStorageService.

    Delegates all JSON operations to the service layer for clean separation of concerns.
    """

    def _execute_operation(self, collection: str, inputs: Dict[str, Any]) -> Any:
        """
        Execute read operation for JSON files by delegating to JSONStorageService.

        Args:
            collection: JSON file path
            inputs: Input dictionary

        Returns:
            JSON data based on query and path
        """
        self.log_info(f"Reading from {collection}")

        # Extract parameters for the service
        document_id = inputs.get("document_id") or inputs.get("id")
        query = inputs.get("query")
        path = inputs.get("path")

        # Extract JSON-specific parameters
        output_format = inputs.get("format", "raw")
        id_field = inputs.get("id_field", "id")
        use_envelope = inputs.get("use_envelope", False)

        # Call the JSON storage service
        result = self.json_service.read(
            collection=collection,
            document_id=document_id,
            query=query,
            path=path,
            format=output_format,
            id_field=id_field,
        )

        # Handle envelope format if requested (for backward compatibility)
        if use_envelope and result is not None:
            return {
                "success": True,
                "document_id": document_id or collection,
                "data": result,
                "is_collection": isinstance(result, (list, dict)),
            }

        return result
