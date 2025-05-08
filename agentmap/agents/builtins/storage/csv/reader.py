"""
CSV reader agent implementation.

This module provides an agent for reading data from CSV files,
with support for filtering, querying, and formatting results.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from agentmap.agents.builtins.storage.csv.base_agent import CSVAgent
from agentmap.agents.builtins.storage.base_storage_agent import DocumentResult, log_operation
from agentmap.logging import get_logger

logger = get_logger(__name__)


class CSVReaderAgent(CSVAgent):
    """Agent for reading data from CSV files."""
    
    @log_operation
    def process(self, inputs: Dict[str, Any]) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Read and process data from a CSV file.
        
        Args:
            inputs: Dictionary containing:
                - collection: Path to the CSV file
                - query: Optional query parameters (string or dict)
                - id: Optional record ID to find
                - id_field: Optional field to use as ID (default: 'id')
                - limit: Optional maximum number of records to return
                - format: Optional output format (default: 'records')
                
        Returns:
            Formatted CSV data as specified in the format parameter
            
        Raises:
            ValueError: If required inputs are missing or invalid
            FileNotFoundError: If the CSV file doesn't exist
        """
        # Get file path
        csv_path = self.get_collection(inputs)
        logger.info(f"Reading from {csv_path}")
        
        # Check if file exists
        if not self._check_file_exists(csv_path):
            self._handle_error("File Not Found", f"CSV file not found: {csv_path}")
        
        try:
            # Read CSV with pandas
            df = self._read_csv(csv_path)
            
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
            self._handle_error("CSV Processing Error", f"Error processing {csv_path}", e)