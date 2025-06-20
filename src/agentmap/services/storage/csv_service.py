"""
CSV Storage Service implementation for AgentMap.

This module provides a concrete implementation of the storage service
for CSV files using pandas, following existing CSV agent patterns.
"""
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from agentmap.services.storage.base import BaseStorageService
from agentmap.services.storage.types import StorageResult, WriteMode


class CSVStorageService(BaseStorageService):
    """
    CSV storage service implementation using pandas.
    
    Provides storage operations for CSV files with support for
    reading, writing, querying, and filtering data.
    """
    
    def _initialize_client(self) -> Any:
        """
        Initialize CSV client.
        
        For CSV operations, we don't need a complex client.
        Just ensure base directory exists and return a simple config.
        
        Returns:
            Configuration dict for CSV operations
            
        Raises:
            OSError: If base directory cannot be created or accessed
        """
        base_dir = self._config.get_option("base_directory", "./data")
        encoding = self._config.get_option("encoding", "utf-8")
        
        # Ensure base directory exists - fail fast if we can't create it
        try:
            os.makedirs(base_dir, exist_ok=True)
        except (OSError, PermissionError) as e:
            raise OSError(f"Cannot create base directory '{base_dir}': {e}")
        
        return {
            "base_directory": base_dir,
            "encoding": encoding,
            "default_options": {
                "skipinitialspace": True,
                "skip_blank_lines": True,
                "on_bad_lines": "warn"
            }
        }
    
    def _perform_health_check(self) -> bool:
        """
        Perform health check for CSV storage.
        
        Checks if base directory is accessible and we can perform
        basic pandas operations and file operations.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            base_dir = self.client["base_directory"]
            
            # Check if directory exists
            if not os.path.exists(base_dir):
                return False
            
            # Test actual write access by creating a temporary file
            import tempfile
            test_file_path = os.path.join(base_dir, ".health_check_test.tmp")
            try:
                with open(test_file_path, 'w', encoding=self.client["encoding"]) as f:
                    f.write("test")
                # Clean up test file
                os.remove(test_file_path)
            except (OSError, PermissionError):
                return False
            
            # Test basic pandas operation
            test_df = pd.DataFrame({"test": [1, 2, 3]})
            if len(test_df) != 3:
                return False
            
            return True
        except Exception as e:
            self._logger.debug(f"CSV health check failed: {e}")
            return False
    
    def _get_file_path(self, collection: str) -> str:
        """
        Get full file path for a collection.
        
        Args:
            collection: Collection name (can be relative or absolute path)
            
        Returns:
            Full file path
        """
        if os.path.isabs(collection):
            return collection
        
        base_dir = self.client["base_directory"]
        
        # Ensure .csv extension
        if not collection.lower().endswith('.csv'):
            collection = f"{collection}.csv"
        
        return os.path.join(base_dir, collection)
    
    def _ensure_directory_exists(self, file_path: str) -> None:
        """
        Ensure the directory for a file path exists.
        
        Args:
            file_path: Path to file
        """
        directory = os.path.dirname(os.path.abspath(file_path))
        os.makedirs(directory, exist_ok=True)
    
    def _read_csv_file(self, file_path: str, **kwargs) -> pd.DataFrame:
        """
        Read CSV file with error handling.
        
        Args:
            file_path: Path to CSV file
            **kwargs: Additional pandas read_csv parameters
            
        Returns:
            DataFrame with CSV data
        """
        try:
            # Merge default options with provided kwargs
            read_options = self.client["default_options"].copy()
            read_options["encoding"] = self.client["encoding"]
            read_options.update(kwargs)
            
            df = pd.read_csv(file_path, **read_options)
            self._logger.debug(f"Read {len(df)} rows from {file_path}")
            return df
            
        except FileNotFoundError:
            self._logger.debug(f"CSV file not found: {file_path}")
            raise
        except Exception as e:
            self._handle_error("read_csv", e, file_path=file_path)
    
    def _write_csv_file(
        self, 
        df: pd.DataFrame, 
        file_path: str, 
        mode: str = 'w',
        **kwargs
    ) -> None:
        """
        Write DataFrame to CSV file.
        
        Args:
            df: DataFrame to write
            file_path: Path to CSV file
            mode: Write mode ('w' for write, 'a' for append)
            **kwargs: Additional pandas to_csv parameters
        """
        try:
            self._ensure_directory_exists(file_path)
            
            # Set default write options
            write_options = {
                "index": False,
                "encoding": self.client["encoding"]
            }
            write_options.update(kwargs)
            
            # Handle header for append mode
            if mode == 'a' and os.path.exists(file_path):
                write_options["header"] = False
            
            df.to_csv(file_path, mode=mode, **write_options)
            self._logger.debug(f"Wrote {len(df)} rows to {file_path} (mode: {mode})")
            
        except Exception as e:
            self._handle_error("write_csv", e, file_path=file_path)
    
    def _apply_query_filter(self, df: pd.DataFrame, query: Dict[str, Any]) -> pd.DataFrame:
        """
        Apply query filters to DataFrame.
        
        Args:
            df: DataFrame to filter
            query: Query parameters
            
        Returns:
            Filtered DataFrame
        """
        # Make a copy to avoid modifying original
        filtered_df = df.copy()
        
        # Apply field-based filters
        for field, value in query.items():
            if field in ['limit', 'offset', 'sort', 'order']:
                continue  # Skip special parameters
                
            if field in filtered_df.columns:
                if isinstance(value, list):
                    # Handle list values as "in" filter
                    filtered_df = filtered_df[filtered_df[field].isin(value)]
                else:
                    # Exact match filter
                    filtered_df = filtered_df[filtered_df[field] == value]
        
        # Apply sorting
        sort_field = query.get('sort')
        if sort_field and sort_field in filtered_df.columns:
            ascending = query.get('order', 'asc').lower() != 'desc'
            filtered_df = filtered_df.sort_values(by=sort_field, ascending=ascending)
        
        # Apply pagination
        offset = query.get('offset', 0)
        limit = query.get('limit')
        
        if offset and isinstance(offset, int) and offset > 0:
            filtered_df = filtered_df.iloc[offset:]
        
        if limit and isinstance(limit, int) and limit > 0:
            filtered_df = filtered_df.head(limit)
        
        return filtered_df
    
    def read(
        self, 
        collection: str, 
        document_id: Optional[str] = None,
        query: Optional[Dict[str, Any]] = None,
        path: Optional[str] = None,
        **kwargs
    ) -> Any:
        """
        Read data from CSV file.
        
        Args:
            collection: CSV file name/path
            document_id: Row ID to read (looks for 'id' column)
            query: Query parameters for filtering
            path: Not used for CSV (no nested structure)
            **kwargs: Additional parameters (format, id_field, pandas options)
            
        Returns:
            DataFrame, dict, or list depending on query
        """
        try:
            file_path = self._get_file_path(collection)
            
            if not os.path.exists(file_path):
                self._logger.debug(f"CSV file does not exist: {file_path}")
                return pd.DataFrame()  # Return empty DataFrame
            
            # Extract service-specific parameters
            format_type = kwargs.pop('format', 'dataframe')
            id_field = kwargs.pop('id_field', 'id')
            
            # Read the CSV file (remaining kwargs go to pandas)
            df = self._read_csv_file(file_path, **kwargs)
            
            # Apply document_id filter
            if document_id is not None:
                if id_field in df.columns:
                    df = df[df[id_field] == document_id]
                    if len(df) == 1:
                        return df.iloc[0].to_dict()  # Return single record as dict
                    elif len(df) == 0:
                        return None
            
            # Apply query filters
            if query:
                df = self._apply_query_filter(df, query)
            
            # Return format based on request
            if format_type == 'records':
                return df.to_dict(orient='records')
            elif format_type == 'dict':
                return df.to_dict(orient='index')
            else:
                return df  # Return DataFrame by default
                
        except Exception as e:
            self._handle_error("read", e, collection=collection, document_id=document_id)
    
    def write(
        self,
        collection: str,
        data: Any,
        document_id: Optional[str] = None,
        mode: WriteMode = WriteMode.WRITE,
        path: Optional[str] = None,
        **kwargs
    ) -> StorageResult:
        """
        Write data to CSV file.
        
        Args:
            collection: CSV file name/path
            data: Data to write (DataFrame, dict, or list of dicts)
            document_id: Row ID for updates (looks for 'id' column)
            mode: Write mode (write, append, update)
            path: Not used for CSV
            **kwargs: Additional parameters
            
        Returns:
            StorageResult with operation details
        """
        try:
            file_path = self._get_file_path(collection)
            
            # Extract service-specific parameters
            id_field = kwargs.pop('id_field', 'id')
            
            # Convert data to DataFrame
            if isinstance(data, pd.DataFrame):
                df = data.copy()
            elif isinstance(data, dict):
                df = pd.DataFrame([data])
            elif isinstance(data, list):
                df = pd.DataFrame(data)
            else:
                raise ValueError(f"Unsupported data type: {type(data)}")
            
            rows_written = len(df)
            file_existed = os.path.exists(file_path)
            
            if mode == WriteMode.WRITE:
                # Overwrite file
                self._write_csv_file(df, file_path, mode='w', **kwargs)
                return self._create_success_result(
                    "write",
                    collection=collection,
                    file_path=file_path,
                    rows_written=rows_written,
                    created_new=not file_existed
                )
            
            elif mode == WriteMode.APPEND:
                # Append to file
                write_mode = 'a' if file_existed else 'w'
                self._write_csv_file(df, file_path, mode=write_mode, **kwargs)
                return self._create_success_result(
                    "append",
                    collection=collection,
                    file_path=file_path,
                    rows_written=rows_written
                )
            
            elif mode == WriteMode.UPDATE:
                # Update existing rows or append new ones
                if not file_existed:
                    # File doesn't exist, just write new data
                    self._write_csv_file(df, file_path, mode='w', **kwargs)
                    return self._create_success_result(
                        "update",
                        collection=collection,
                        file_path=file_path,
                        rows_written=rows_written,
                        created_new=True
                    )
                
                # Read existing data and merge
                existing_df = self._read_csv_file(file_path)
                
                if id_field in df.columns and id_field in existing_df.columns:
                    # Merge on ID field
                    updated_df = existing_df.copy()
                    for _, row in df.iterrows():
                        row_id = row[id_field]
                        mask = updated_df[id_field] == row_id
                        if mask.any():
                            # Update existing row - use proper column assignment
                            for col in row.index:
                                if col in updated_df.columns:
                                    updated_df.loc[mask, col] = row[col]
                        else:
                            # Append new row
                            updated_df = pd.concat([updated_df, row.to_frame().T], ignore_index=True)
                    
                    self._write_csv_file(updated_df, file_path, mode='w', **kwargs)
                    return self._create_success_result(
                        "update",
                        collection=collection,
                        file_path=file_path,
                        rows_written=rows_written,
                        total_affected=len(updated_df)
                    )
                else:
                    # No ID field, just append
                    self._write_csv_file(df, file_path, mode='a', **kwargs)
                    return self._create_success_result(
                        "update",
                        collection=collection,
                        file_path=file_path,
                        rows_written=rows_written
                    )
            
            else:
                return self._create_error_result(
                    "write",
                    f"Unsupported write mode: {mode}",
                    collection=collection
                )
                
        except Exception as e:
            self._handle_error("write", e, collection=collection, mode=mode.value)
    
    def delete(
        self,
        collection: str,
        document_id: Optional[str] = None,
        path: Optional[str] = None,
        **kwargs
    ) -> StorageResult:
        """
        Delete from CSV file.
        
        Args:
            collection: CSV file name/path
            document_id: Row ID to delete (looks for 'id' column)
            path: Not used for CSV
            **kwargs: Additional parameters
            
        Returns:
            StorageResult with operation details
        """
        try:
            file_path = self._get_file_path(collection)
            
            # Extract service-specific parameters
            id_field = kwargs.pop('id_field', 'id')
            
            if document_id is None:
                # Delete entire file
                if os.path.exists(file_path):
                    os.remove(file_path)
                    return self._create_success_result(
                        "delete",
                        collection=collection,
                        file_path=file_path,
                        file_deleted=True
                    )
                else:
                    return self._create_error_result(
                        "delete",
                        f"File not found: {file_path}",
                        collection=collection
                    )
            
            # Delete specific row(s)
            if not os.path.exists(file_path):
                return self._create_error_result(
                    "delete",
                    f"File not found: {file_path}",
                    collection=collection
                )
            
            df = self._read_csv_file(file_path)
            
            if id_field not in df.columns:
                return self._create_error_result(
                    "delete",
                    f"ID field '{id_field}' not found in CSV",
                    collection=collection
                )
            
            # Filter out rows to delete
            initial_count = len(df)
            df_filtered = df[df[id_field] != document_id]
            deleted_count = initial_count - len(df_filtered)
            
            if deleted_count == 0:
                return self._create_error_result(
                    "delete",
                    f"Document with ID '{document_id}' not found",
                    collection=collection,
                    document_id=document_id
                )
            
            # Write back the filtered data
            self._write_csv_file(df_filtered, file_path, mode='w')
            
            return self._create_success_result(
                "delete",
                collection=collection,
                file_path=file_path,
                document_id=document_id,
                total_affected=deleted_count
            )
            
        except Exception as e:
            self._handle_error("delete", e, collection=collection, document_id=document_id)
    
    def exists(
        self, 
        collection: str, 
        document_id: Optional[str] = None
    ) -> bool:
        """
        Check if CSV file or document exists.
        
        Args:
            collection: CSV file name/path
            document_id: Row ID to check (looks for 'id' column)
            
        Returns:
            True if exists, False otherwise
        """
        try:
            file_path = self._get_file_path(collection)
            
            if document_id is None:
                # Check if file exists
                return os.path.exists(file_path)
            
            # Check if document exists in file
            if not os.path.exists(file_path):
                return False
            
            df = self._read_csv_file(file_path)
            id_field = 'id'  # Default ID field for exists check
            
            if id_field in df.columns:
                return (df[id_field] == document_id).any()
            
            return False
            
        except Exception as e:
            self._logger.debug(f"Error checking existence: {e}")
            return False
    
    def count(
        self,
        collection: str,
        query: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Count rows in CSV file.
        
        Args:
            collection: CSV file name/path
            query: Optional query parameters for filtering
            
        Returns:
            Number of rows
        """
        try:
            file_path = self._get_file_path(collection)
            
            if not os.path.exists(file_path):
                return 0
            
            df = self._read_csv_file(file_path)
            
            if query:
                df = self._apply_query_filter(df, query)
            
            return len(df)
            
        except Exception as e:
            self._logger.debug(f"Error counting rows: {e}")
            return 0
    
    def list_collections(self) -> List[str]:
        """
        List all CSV files in the base directory.
        
        Returns:
            List of CSV file names
        """
        try:
            base_dir = self.client["base_directory"]
            
            if not os.path.exists(base_dir):
                return []
            
            csv_files = []
            for item in os.listdir(base_dir):
                if item.lower().endswith('.csv'):
                    csv_files.append(item)
            
            return sorted(csv_files)
            
        except Exception as e:
            self._logger.debug(f"Error listing collections: {e}")
            return []
