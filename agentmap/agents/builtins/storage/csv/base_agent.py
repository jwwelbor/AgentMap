"""
Base CSV storage agent implementation.

This module provides common functionality for working with CSV files,
including reading, writing, and filtering operations.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Union

import pandas as pd

from agentmap.agents.builtins.storage.base_storage_agent import (
    BaseStorageAgent, DocumentResult, log_operation)
from agentmap.logging import get_logger

logger = get_logger(__name__)


class CSVAgent(BaseStorageAgent):
    """
    Base class for CSV storage agents with shared functionality.
    
    Provides common methods for reading, writing, and filtering CSV data
    that can be used by both reader and writer implementations.
    """
    
    def _ensure_directory_exists(self, file_path: str) -> None:
        """
        Ensure the directory for a file path exists.
        
        Args:
            file_path: Path to file
        """
        directory = os.path.dirname(os.path.abspath(file_path))
        os.makedirs(directory, exist_ok=True)
    
    def _check_file_exists(self, file_path: str) -> bool:
        """
        Check if a file exists and log appropriately.
        
        Args:
            file_path: Path to file
            
        Returns:
            True if file exists, False otherwise
        """
        exists = os.path.exists(file_path)
        
        if not exists:
            logger.debug(f"File does not exist: {file_path}")
        return exists
    
    def _read_csv(self, file_path: str, **kwargs) -> pd.DataFrame:
        """
        Read a CSV file with standardized error handling.
        
        Args:
            file_path: Path to CSV file
            **kwargs: Additional parameters to pass to pandas.read_csv
            
        Returns:
            DataFrame containing CSV data
            
        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the file contains invalid CSV data
        """
        try:
            # Set sensible defaults for CSV reading
            read_kwargs = {
                "encoding": "utf-8",
                "skipinitialspace": True,
                "skip_blank_lines": True,
                "on_bad_lines": "warn"
            }
            # Override defaults with any provided kwargs
            read_kwargs.update(kwargs)
            
            df = pd.read_csv(file_path, **read_kwargs)
            logger.debug(f"Read {len(df)} rows from {file_path}")
            return df
        except FileNotFoundError:
            logger.debug(f"CSV file not found: {file_path}")
            raise FileNotFoundError(f"File not found: {file_path}")
        except Exception as e:
            error_msg = f"Error reading CSV file {file_path}: {str(e)}"
            logger.error(error_msg)
            self._handle_error("CSV Read Error", error_msg, e)
    
    def _write_csv(
        self, 
        df: pd.DataFrame, 
        file_path: str, 
        mode: str = 'w', 
        header: bool = True,
        **kwargs
    ) -> None:
        """
        Write a DataFrame to CSV with standardized error handling.
        
        Args:
            df: DataFrame to write
            file_path: Path to CSV file
            mode: File open mode ('w' for write, 'a' for append)
            header: Whether to write header row
            **kwargs: Additional parameters to pass to DataFrame.to_csv
            
        Raises:
            ValueError: If there's an error writing the CSV
        """
        try:
            # Ensure directory exists
            self._ensure_directory_exists(file_path)
            
            # Set sensible defaults for CSV writing
            write_kwargs = {
                "index": False,
                "encoding": "utf-8"
            }
            # Override defaults with any provided kwargs
            write_kwargs.update(kwargs)
            
            # Write to CSV
            df.to_csv(file_path, mode=mode, header=header, **write_kwargs)
            
            logger.debug(f"Wrote {len(df)} rows to {file_path} (mode: {mode})")
        except Exception as e:
            error_msg = f"Error writing to CSV file {file_path}: {str(e)}"
            logger.error(error_msg)
            self._handle_error("CSV Write Error", error_msg, e)
    
    def _apply_filters(self, df: pd.DataFrame, inputs: Dict[str, Any]) -> pd.DataFrame:
        """
        Apply common filtering operations from inputs.
        
        Args:
            df: DataFrame to filter
            inputs: Input dictionary with filter parameters
            
        Returns:
            Filtered DataFrame
        """
        # Apply query filter
        query = inputs.get("query")
        if query:
            if isinstance(query, str):
                try:
                    df = df.query(query)
                    logger.debug(f"Applied query filter: {query}, {len(df)} rows remaining")
                except Exception as e:
                    logger.warning(f"Failed to apply query filter '{query}': {str(e)}")
            elif isinstance(query, dict):
                for col, value in query.items():
                    if col in df.columns:
                        df = df[df[col] == value]
                logger.debug(f"Applied dict filter, {len(df)} rows remaining")
        
        # Apply ID filter
        id_value = inputs.get("id")
        if id_value is not None:
            id_field = inputs.get("id_field", "id")
            if id_field in df.columns:
                df = df[df[id_field] == id_value]
                logger.debug(f"Applied ID filter: {id_field}={id_value}, {len(df)} rows remaining")
        
        # Apply limit
        limit = inputs.get("limit")
        if limit and isinstance(limit, int) and limit > 0:
            df = df.head(limit)
            logger.debug(f"Applied limit: {limit}")
        
        return df
    
    def _format_data_for_output(
        self, 
        df: pd.DataFrame, 
        format_type: str = "records"
    ) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Format a DataFrame for output in the requested format.
        
        Args:
            df: DataFrame to format
            format_type: Output format type ('records', 'dict', 'list', 'csv', etc.)
            
        Returns:
            Formatted data
        """
        if df is None or df.empty:
            logger.debug("DataFrame is empty, returning empty list")
            return []
        
        format_type = format_type.lower()
        
        # Dictionary of format handlers to make code more maintainable
        format_handlers = {
            "records": lambda df: df.to_dict(orient="records"),
            "list": lambda df: df.to_dict(orient="records"),
            "dict": lambda df: df.to_dict(orient="index"),
            "series": lambda df: df.iloc[0].to_dict() if len(df) > 0 else {},
            "csv": lambda df: df.to_csv(index=False),
            "json": lambda df: df.to_json(orient="records")
        }
        
        # Get the handler for the requested format or use records as default
        handler = format_handlers.get(format_type)
        
        if handler:
            result = handler(df)
            logger.debug(f"Formatted DataFrame as {format_type}")
            return result
        else:
            # Default to records format
            logger.warning(f"Unknown format type '{format_type}', defaulting to 'records'")
            return df.to_dict(orient="records")
    
    def _initialize_client(self) -> None:
        """No client initialization needed for CSV files."""
        pass