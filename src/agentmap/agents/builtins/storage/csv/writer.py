"""
CSV writer agent implementation.

This module provides a simple agent for writing data to CSV files
that delegates to CSVStorageService for the actual implementation.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from agentmap.agents.builtins.storage.csv.base_agent import CSVAgent
from agentmap.agents.builtins.storage.base_storage_agent import log_operation
from agentmap.services.storage import DocumentResult, WriteMode
from agentmap.agents.mixins import WriterOperationsMixin
from agentmap.logging import get_logger

logger = get_logger(__name__)


class CSVWriterAgent(CSVAgent, WriterOperationsMixin):
    """
    Simple agent for writing data to CSV files via CSVStorageService.
    
    Delegates all CSV operations to the service layer for clean separation of concerns.
    """
    
    def _execute_operation(self, collection: str, inputs: Dict[str, Any]) -> DocumentResult:
        """
        Execute write operation for CSV files by delegating to CSVStorageService.
        
        Args:
            collection: CSV file path
            inputs: Input dictionary
            
        Returns:
            Write operation result
        """
        self.log_info(f"Writing to {collection}")
        
        # Get the data to write
        data = inputs.get("data")
        if data is None:
            return DocumentResult(
                success=False,
                file_path=collection,
                error="No data provided to write"
            )
        
        # Get write mode
        mode_str = inputs.get("mode", "write").lower()
        try:
            mode = WriteMode.from_string(mode_str)
        except ValueError:
            self.log_warning(f"Invalid mode '{mode_str}', using 'write' mode")
            mode = WriteMode.WRITE
        
        # Extract additional parameters
        document_id = inputs.get("document_id")
        path = inputs.get("path")
        id_field = inputs.get("id_field", "id")
        
        # Call the CSV storage service
        result = self.csv_service.write(
            collection=collection,
            data=data,
            document_id=document_id,
            mode=mode,
            path=path,
            id_field=id_field
        )
        
        return result