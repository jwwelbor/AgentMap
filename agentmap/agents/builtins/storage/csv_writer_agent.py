"""
CSV writer agent implementation.

This module provides an agent for writing data to CSV files,
with support for creating, appending, and updating data.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Union, cast

import pandas as pd

from agentmap.agents.builtins.storage.base_csv_agent import BaseCSVAgent
from agentmap.agents.builtins.storage.base_storage_agent import (
    DocumentResult, WriteMode, log_operation)
from agentmap.logging import get_logger

logger = get_logger(__name__)


class CSVWriterAgent(BaseCSVAgent):
    """
    Agent for writing data to CSV files.
    
    Writes data to CSV files with support for creation, appending, and updates.
    """
    
    @log_operation
    def process(self, inputs: Dict[str, Any]) -> DocumentResult:
        """
        Write data to a CSV file.
        
        Args:
            inputs: Dictionary containing input values, including:
                - collection: Path to the CSV file
                - data: Data to write (list of dicts, dict, or DataFrame)
                - mode: Write mode (write, append, update)
                - id_field: Field to use as ID for updates
                
        Returns:
            DocumentResult with operation results and metadata
            
        Raises:
            ValueError: If required inputs are missing or invalid
        """
        # Get the CSV file path
        csv_path = self.get_collection(inputs)
        logger.info(f"Writing to {csv_path}")
        
        # Get the data to write
        data = inputs.get("data")
        if data is None:
            self._handle_error("Missing Data", "No data provided to write")
        
        try:
            # Convert data to DataFrame
            df = self._convert_to_dataframe(data)
            
            # Get write mode
            mode_str = inputs.get("mode", "write").lower()
            try:
                mode = WriteMode.from_string(mode_str)
            except ValueError:
                logger.warning(f"Invalid mode '{mode_str}', using 'write' mode")
                mode = WriteMode.WRITE
            
            # Handle different write modes
            if mode == WriteMode.WRITE:
                return self._write_mode_create(csv_path, df)
            elif mode == WriteMode.APPEND:
                return self._write_mode_append(csv_path, df)
            elif mode == WriteMode.UPDATE:
                id_field = inputs.get("id_field", "id")
                return self._write_mode_update(csv_path, df, id_field)
            else:
                # Default to write mode
                return self._write_mode_create(csv_path, df)
                
        except Exception as e:
            return DocumentResult(
                success=False,
                mode=mode_str,
                file_path=csv_path,
                error=str(e)
            )
    
    def _convert_to_dataframe(self, data: Any) -> pd.DataFrame:
        """
        Convert input data to a pandas DataFrame.
        
        Args:
            data: Input data in various formats (DataFrame, dict, list, etc.)
            
        Returns:
            DataFrame containing the data
            
        Raises:
            ValueError: If data cannot be converted to DataFrame
        """
        if isinstance(data, pd.DataFrame):
            return data
        elif isinstance(data, dict):
            # Single dictionary
            return pd.DataFrame([data])
        elif isinstance(data, list):
            # List of dictionaries or values
            return pd.DataFrame(data)
        else:
            raise ValueError(f"Unsupported data type: {type(data)}")
    
    def _write_mode_create(self, csv_path: str, df: pd.DataFrame) -> DocumentResult:
        """
        Write mode: Create or overwrite file.
        
        Args:
            csv_path: Path to the CSV file
            df: DataFrame to write
            
        Returns:
            Result of the write operation
        """
        file_exists = os.path.exists(csv_path)
        
        try:
            self._write_csv(df, csv_path)
            
            return DocumentResult(
                success=True,
                mode=WriteMode.WRITE.value,
                file_path=csv_path,
                rows_written=len(df),
                created_new=not file_exists
            )
        except Exception as e:
            return DocumentResult(
                success=False,
                mode=WriteMode.WRITE.value,
                file_path=csv_path,
                error=str(e)
            )
    
    def _write_mode_append(self, csv_path: str, df: pd.DataFrame) -> DocumentResult:
        """
        Write mode: Append to existing file.
        
        Args:
            csv_path: Path to the CSV file
            df: DataFrame to append
            
        Returns:
            Result of the write operation
        """
        file_exists = os.path.exists(csv_path)
        
        try:
            if file_exists:
                # Read existing file to ensure column alignment
                existing_df = self._read_csv(csv_path)
                
                # Make sure column order matches the existing file
                # We need to reorder the columns in the new dataframe to match the existing one
                if not df.empty and not existing_df.empty:
                    # Get columns present in both dataframes
                    common_cols = [col for col in existing_df.columns if col in df.columns]
                    
                    # If we have common columns to work with
                    if common_cols:
                        # For any columns in the existing df that aren't in the new df, add them with NaN
                        for col in existing_df.columns:
                            if col not in df.columns:
                                df[col] = None
                        
                        # Reorder columns to match existing dataframe
                        df = df[existing_df.columns]
                
                # Append to file
                self._write_csv(df, csv_path, mode='a', header=False)
            else:
                # Create new file
                self._write_csv(df, csv_path)
            
            return DocumentResult(
                success=True,
                mode=WriteMode.APPEND.value,
                file_path=csv_path,
                rows_written=len(df),
                created_new=not file_exists
            )
        except Exception as e:
            return DocumentResult(
                success=False,
                mode=WriteMode.APPEND.value,
                file_path=csv_path,
                error=str(e)
            )
    
    def _write_mode_update(
        self, 
        csv_path: str, 
        df: pd.DataFrame, 
        id_field: str
    ) -> DocumentResult:
        """
        Write mode: Update existing records.
        
        Args:
            csv_path: Path to the CSV file
            df: DataFrame with updates
            id_field: Field to use as ID for matching records
            
        Returns:
            Result of the update operation
        """
        file_exists = os.path.exists(csv_path)
        
        try:
            if file_exists:
                # Read existing file
                existing_df = self._read_csv(csv_path)
                
                # Ensure ID field exists
                if id_field not in existing_df.columns:
                    return DocumentResult(
                        success=False,
                        mode=WriteMode.UPDATE.value,
                        file_path=csv_path,
                        error=f"ID field '{id_field}' not found in existing CSV"
                    )
                
                # Track updated and added records
                updated_rows = 0
                added_rows = 0
                updated_ids = []
                
                # Process each row in the update data
                for _, row in df.iterrows():
                    if id_field in row:
                        # Extract ID
                        id_value = row[id_field]
                        
                        # Find matching row in existing data
                        mask = existing_df[id_field] == id_value
                        if any(mask):
                            # Update existing row
                            for col in df.columns:
                                if col in existing_df.columns:
                                    existing_df.loc[mask, col] = row[col]
                            updated_rows += 1
                            # Preserve the original type of the ID
                            updated_ids.append(id_value)
                        else:
                            # Add new row
                            # First make sure it has all the columns of the existing dataframe
                            new_row = pd.DataFrame([row])
                            for col in existing_df.columns:
                                if col not in new_row.columns:
                                    new_row[col] = None
                            
                            # Now add the row
                            existing_df = pd.concat([existing_df, new_row[existing_df.columns]], ignore_index=True)
                            added_rows += 1
                
                # Write updated data back to CSV
                self._write_csv(existing_df, csv_path)
                
                return DocumentResult(
                    success=True,
                    mode=WriteMode.UPDATE.value,
                    file_path=csv_path,
                    rows_updated=updated_rows,
                    rows_added=added_rows,
                    total_affected=updated_rows + added_rows,
                    updated_ids=updated_ids
                )
            else:
                # File doesn't exist, create new
                self._write_csv(df, csv_path)
                
                return DocumentResult(
                    success=True,
                    mode=WriteMode.UPDATE.value,
                    file_path=csv_path,
                    rows_written=len(df),
                    created_new=True
                )
        except Exception as e:
            return DocumentResult(
                success=False,
                mode=WriteMode.UPDATE.value,
                file_path=csv_path,
                error=str(e)
            )