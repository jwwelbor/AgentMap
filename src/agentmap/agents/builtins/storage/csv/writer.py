"""
CSV writer agent implementation.

This module provides a simple agent for writing data to CSV files
that delegates to CSVStorageService for the actual implementation.
"""

from __future__ import annotations

from typing import Any, Dict

from agentmap.agents.builtins.storage.csv.base_agent import CSVAgent
from agentmap.models.storage import DocumentResult, WriteMode


class CSVWriterAgent(CSVAgent):
    """
    Simple agent for writing data to CSV files via CSVStorageService.

    Delegates all CSV operations to the service layer for clean separation of concerns.
    """

    def _execute_operation(
        self, collection: str, inputs: Dict[str, Any]
    ) -> DocumentResult:
        """
        Execute write operation for CSV files by delegating to CSVStorageService.

        Args:
            collection: CSV file path
            inputs: Input dictionary where keys can be column names

        Returns:
            Write operation result
        """
        self.log_info(f"Writing to {collection}")

        # Get the data to write - use 'data' field if present, otherwise use input fields directly
        if "data" in inputs:
            # Backward compatibility: use 'data' field if it exists
            data = inputs.get("data")
        else:
            # Use input fields directly as CSV columns (excluding control fields)
            control_fields = {
                "mode",
                "document_id",
                "path",
                "id_field",
                "collection",
                "file_path",
                "csv_file",
            }
            data = {k: v for k, v in inputs.items() if k not in control_fields}

        if not data:
            return DocumentResult(
                success=False, file_path=collection, error="No data provided to write"
            )

        # Get write mode
        mode_str = inputs.get("mode", "append").lower()
        try:
            mode = WriteMode.from_string(mode_str)
        except ValueError:
            self.log_warning(f"Invalid mode '{mode_str}', using 'append' mode")
            mode = WriteMode.APPEND

        # Extract additional parameters
        document_id = inputs.get("document_id")
        path = inputs.get("path")
        id_field = inputs.get(
            "id_field"
        )  # Don't force a default, let service auto-detect

        # Build kwargs for the CSV storage service
        write_kwargs = {}
        if id_field is not None:
            write_kwargs["id_field"] = id_field

        # Call the CSV storage service
        result = self.csv_service.write(
            collection=collection,
            data=data,
            document_id=document_id,
            mode=mode,
            path=path,
            **write_kwargs,
        )

        return result
