"""
CSV reader agent implementation.

This module provides a simple agent for reading data from CSV files
that delegates to CSVStorageService for the actual implementation.
"""

from __future__ import annotations

from typing import Any, Dict

from agentmap.agents.builtins.storage.csv.base_agent import CSVAgent


class CSVReaderAgent(CSVAgent):
    """Simple agent for reading data from CSV files via CSVStorageService."""

    def _execute_operation(self, collection: str, inputs: Dict[str, Any]) -> Any:
        """
        Execute read operation for CSV files by delegating to CSVStorageService.

        Args:
            collection: CSV file path
            inputs: Input dictionary

        Returns:
            CSV data in requested format
        """
        self.log_info(f"Reading from {collection}")

        # Extract parameters for the service
        document_id = inputs.get("document_id") or inputs.get("id")
        query = inputs.get("query")
        path = inputs.get("path")

        # Extract format and other CSV-specific parameters
        output_format = inputs.get("format", "records")
        id_field = inputs.get("id_field", "id")

        # Call the CSV storage service
        result = self.csv_service.read(
            collection=collection,
            document_id=document_id,
            query=query,
            path=path,
            format=output_format,
            id_field=id_field,
        )

        return result

    def _log_operation_start(self, collection: str, inputs: Dict[str, Any]) -> None:
        """
        Log the start of a CSV read operation.

        Args:
            collection: CSV file path
            inputs: Input dictionary
        """
        format_type = inputs.get("format", "records")
        self.log_debug(
            f"[{self.__class__.__name__}] Starting CSV read operation on {collection} (format: {format_type})"
        )
