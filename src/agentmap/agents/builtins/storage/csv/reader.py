"""
CSV reader agent implementation.

This module provides an agent for reading data from CSV files,
with support for filtering, querying, and formatting results.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from agentmap.agents.builtins.storage.csv.base_agent import CSVAgent
from agentmap.agents.builtins.storage.base_storage_agent import DocumentResult, log_operation
from agentmap.agents.builtins.storage.mixins import ReaderOperationsMixin
from agentmap.logging import get_logger

logger = get_logger(__name__)


class CSVReaderAgent(CSVAgent, ReaderOperationsMixin):
    """Agent for reading data from CSV files."""
    
    def _execute_operation(self, collection: str, inputs: Dict[str, Any]) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Execute read operation for CSV files.
        
        Args:
            collection: CSV file path
            inputs: Input dictionary
            
        Returns:
            Formatted CSV data
        """
        self.log_info(f"Reading from {collection}")
        
        # Check if file exists
        if not self._check_file_exists(collection):
            self._handle_error("File Not Found", f"CSV file not found: {collection}")
        
        try:
            # Read CSV with pandas
            df = self._read_csv(collection)
            
            # Apply filters
            df = self._apply_filters(df, inputs)
            
            # Handle single record case
            return_single = (
                inputs.get("id") is not None and 
                len(df) == 1 and 
                not inputs.get("return_list", False)
            )
            
            if return_single:
                # Return the first (and only) row as a dictionary
                return df.iloc[0].to_dict()
            
            # Format output based on requested format
            output_format = inputs.get("format", "records")
            return self._format_data_for_output(df, output_format)
            
        except Exception as e:
            self._handle_error("CSV Processing Error", f"Error processing {collection}", e)
    
    def _log_operation_start(self, collection: str, inputs: Dict[str, Any]) -> None:
        """
        Log the start of a CSV read operation.
        
        Args:
            collection: CSV file path
            inputs: Input dictionary
        """
        format_type = inputs.get("format", "records")
        self.log_debug(f"[{self.__class__.__name__}] Starting CSV read operation on {collection} (format: {format_type})")