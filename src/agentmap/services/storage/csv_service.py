"""
CSV Storage Service implementation for AgentMap.

This module provides a concrete implementation of the storage service
for CSV files using pandas, following existing CSV agent patterns.

Configuration Integration:
- Uses StorageConfigService for domain-specific configuration access
- Leverages named domain methods: get_csv_config(), get_csv_data_path(), etc.
- Supports collection-specific configuration via get_collection_config()
- Implements fail-fast behavior when CSV storage is disabled
- Follows established configuration architecture patterns
"""

import os
from typing import Any, Dict, List, Optional

import pandas as pd

from agentmap.services.storage.base import BaseStorageService
from agentmap.services.storage.types import (
    StorageProviderError,
    StorageResult,
    WriteMode,
)


class CSVStorageService(BaseStorageService):
    """
    CSV storage service implementation using pandas.

    Provides storage operations for CSV files with support for
    reading, writing, querying, and filtering data.

    Configuration Pattern:
    - Uses StorageConfigService named domain methods instead of generic access
    - Leverages get_csv_config(), get_csv_data_path(), is_csv_storage_enabled()
    - Supports collection-specific configuration via get_collection_config()
    - Follows configuration architecture patterns from docs/contributing/architecture/configuration-patterns.md
    """

    def __init__(
        self,
        provider_name: str,
        configuration,  # StorageConfigService (avoid circular import)
        logging_service,  # LoggingService (avoid circular import)
        file_path_service=None,  # FilePathService (optional for path validation)
        base_directory: str = None,  # Optional base directory for injection
    ):
        """
        Initialize CSVStorageService.

        Args:
            provider_name: Name of the storage provider
            configuration: Storage configuration service
            logging_service: Logging service for creating loggers
            file_path_service: Optional file path service for path validation and security
            base_directory: Optional base directory for storage operations (for system storage)
        """
        # Call parent's __init__ with all parameters including new injection parameters
        super().__init__(
            provider_name,
            configuration,
            logging_service,
            file_path_service,
            base_directory,
        )

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
        # Use StorageConfigService named domain methods instead of generic access
        csv_config = self.configuration.get_csv_config()

        # Use injected base_directory if available, otherwise use StorageConfigService
        if self.base_directory:
            base_dir = str(self.base_directory)
            # Note: Directory creation is deferred until write operations to maintain
            # backward compatibility with error handling (especially for read operations)
        else:
            # Use the path accessor with business logic (already ensures directory exists)
            base_dir = str(self.configuration.get_csv_data_path())

        encoding = csv_config.get("encoding", "utf-8")

        # Additional validation for fail-fast behavior (only when not using injection)
        if not self.base_directory and not self.configuration.is_csv_storage_enabled():
            raise OSError("CSV storage is not enabled in configuration")

        return {
            "base_directory": base_dir,
            "encoding": encoding,
            "default_options": {
                "skipinitialspace": True,
                "skip_blank_lines": True,
                "on_bad_lines": "warn",
            },
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

            test_file_path = os.path.join(base_dir, ".health_check_test.tmp")
            try:
                with open(test_file_path, "w", encoding=self.client["encoding"]) as f:
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

        Uses StorageConfigService collection configuration when available,
        falls back to default behavior for absolute paths or unconfigured collections.
        Uses file_path_service for path validation when available.

        Args:
            collection: Collection name (can be relative or absolute path)

        Returns:
            Full file path

        Raises:
            ValueError: If path validation fails when file_path_service is available
        """
        if os.path.isabs(collection):
            file_path = collection
        elif self.configuration.has_collection("csv", collection):
            # Use the configured collection file path
            file_path = str(self.configuration.get_collection_file_path(collection))
        else:
            # Fallback to default behavior for unconfigured collections
            base_dir = self.client["base_directory"]

            # Ensure .csv extension
            if not collection.lower().endswith(".csv"):
                collection = f"{collection}.csv"

            if not collection.startswith(base_dir):
                collection = os.path.join(base_dir, collection)

            file_path = collection

        # Validate path using file_path_service if available
        if self._file_path_service:
            try:
                # Use base_directory if available for validation, otherwise use client base_directory
                validation_base = (
                    self.base_directory
                    if self.base_directory
                    else self.client["base_directory"]
                )
                self._file_path_service.validate_safe_path(file_path, validation_base)
            except Exception as e:
                self._logger.error(f"Path validation failed for {file_path}: {e}")
                raise ValueError(f"Unsafe file path: {e}")

        return file_path

    def _ensure_directory_exists(self, file_path: str) -> None:
        """
        Ensure the directory for a file path exists.

        Args:
            file_path: Path to file

        Raises:
            PermissionError: If directory cannot be created due to permissions
            OSError: If other OS-level errors occur
        """
        directory = os.path.dirname(os.path.abspath(file_path))
        try:
            os.makedirs(directory, exist_ok=True)
        except (PermissionError, OSError):
            # Let permission errors propagate to be handled by caller
            raise

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
        self, df: pd.DataFrame, file_path: str, mode: str = "w", **kwargs
    ) -> None:
        """
        Write DataFrame to CSV file.

        Args:
            df: DataFrame to write
            file_path: Path to CSV file
            mode: Write mode ('w' for write, 'a' for append)
            **kwargs: Additional pandas to_csv parameters

        Raises:
            PermissionError: If file cannot be written due to permissions
            OSError: If other OS-level errors occur
        """
        try:
            # Ensure base directory exists when using injection (deferred from _initialize_client)
            if self.base_directory:
                os.makedirs(self.base_directory, exist_ok=True)

            self._ensure_directory_exists(file_path)

            # Set default write options
            write_options = {"index": False, "encoding": self.client["encoding"]}
            write_options.update(kwargs)

            # Handle header for append mode
            if mode == "a" and os.path.exists(file_path):
                write_options["header"] = False

            df.to_csv(file_path, mode=mode, **write_options)
            self._logger.debug(f"Wrote {len(df)} rows to {file_path} (mode: {mode})")

        except (PermissionError, OSError):
            # Let permission and OS errors propagate to be handled by write method
            raise
        except Exception as e:
            self._handle_error("write_csv", e, file_path=file_path)

    def _detect_id_column(self, df: pd.DataFrame) -> Optional[str]:
        """
        Detect the ID column using smart detection logic.

        Priority:
        1. Exact match: "id" (case insensitive)
        2. Ends with "_id": user_id, customer_id, etc.
        3. Starts with "id_": id_user, etc.
        4. If multiple candidates, prefer "id" > first column > alphabetical

        Args:
            df: DataFrame to analyze

        Returns:
            Column name to use as ID, or None if no suitable column found
        """
        if df.empty or len(df.columns) == 0:
            return None

        columns = df.columns.tolist()
        candidates = []

        # Check for exact "id" match (case insensitive)
        for col in columns:
            if col.lower() == "id":
                return col  # Immediate return for exact match

        # Check for columns ending with "_id"
        for col in columns:
            if col.lower().endswith("_id"):
                candidates.append((col, "ends_with_id"))

        # Check for columns starting with "id_"
        for col in columns:
            if col.lower().startswith("id_"):
                candidates.append((col, "starts_with_id"))

        # If we have candidates, prioritize them
        if candidates:
            # Prefer ends_with_id over starts_with_id
            ends_with_id = [col for col, type_ in candidates if type_ == "ends_with_id"]
            if ends_with_id:
                # If multiple, prefer first column, then alphabetical
                return min(ends_with_id, key=lambda x: (columns.index(x), x.lower()))

            starts_with_id = [
                col for col, type_ in candidates if type_ == "starts_with_id"
            ]
            if starts_with_id:
                return min(starts_with_id, key=lambda x: (columns.index(x), x.lower()))

        # No ID column found
        return None

    def _apply_query_filter(
        self, df: pd.DataFrame, query: Dict[str, Any]
    ) -> pd.DataFrame:
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
            if field in ["limit", "offset", "sort", "order"]:
                continue  # Skip special parameters

            if field in filtered_df.columns:
                if isinstance(value, list):
                    # Handle list values as "in" filter
                    filtered_df = filtered_df[filtered_df[field].isin(value)]
                else:
                    # Exact match filter
                    filtered_df = filtered_df[filtered_df[field] == value]

        # Apply sorting
        sort_field = query.get("sort")
        if sort_field and sort_field in filtered_df.columns:
            ascending = query.get("order", "asc").lower() != "desc"
            filtered_df = filtered_df.sort_values(by=sort_field, ascending=ascending)

        # Apply pagination
        offset = query.get("offset", 0)
        limit = query.get("limit")

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
        id_field: Optional[str] = None,
        **kwargs,
    ) -> Any:
        """
        Read data from CSV file.

        Smart ID detection:
        - Automatically detects ID column (id, user_id, etc.)
        - Falls back to row index if no ID column found
        - Returns single row dict when document_id provided
        - Returns formatted data when document_id is None

        Args:
            collection: CSV file name/path
            document_id: Row ID to read or row index (0, 1, 2...)
            query: Query parameters for filtering (table-like)
            path: Not used for CSV (no nested structure)
            id_field: Custom ID field name (overrides auto-detection)
            **kwargs: Additional parameters (format, pandas options)

        Returns:
            None if not found, or formatted data based on format parameter:
            - format="dict" (default): {0: row_dict, 1: row_dict, ...}
            - format="records": [row_dict, row_dict, ...]
            - format="dataframe": pd.DataFrame
        """
        try:
            file_path = self._get_file_path(collection)

            if not os.path.exists(file_path):
                self._logger.debug(f"CSV file does not exist: {file_path}")
                return None

            # Extract service-specific parameters
            format_type = kwargs.pop("format", "dict")  # Default to dict

            # Read the CSV file (remaining kwargs go to pandas)
            df = self._read_csv_file(file_path, **kwargs)

            if df.empty:
                return None

            # Handle document_id lookup
            if document_id is not None:
                # First check if there's a batch column (multi-row document_id)
                batch_column = "_document_id"
                if batch_column in df.columns:
                    # Look for batch with matching document_id
                    matching_rows = df[df[batch_column] == document_id]
                    if len(matching_rows) > 0:
                        # Return all rows in the batch (excluding the batch column)
                        result_df = matching_rows.drop(columns=[batch_column])
                        return result_df.to_dict(orient="records")

                # No batch column found, try smart ID column detection for single row
                id_column = id_field if id_field else self._detect_id_column(df)

                if id_column is not None:
                    # Use detected ID column
                    # Convert document_id to match column type
                    try:
                        # Try to convert document_id to match the column's dtype
                        if pd.api.types.is_numeric_dtype(df[id_column]):
                            # Convert to numeric if the column is numeric
                            search_value = pd.to_numeric(document_id)
                        else:
                            # Keep as string for text columns
                            search_value = str(document_id)

                        matching_rows = df[df[id_column] == search_value]
                        if len(matching_rows) > 0:
                            return matching_rows.iloc[0].to_dict()
                    except (ValueError, TypeError):
                        # Conversion failed, try direct string comparison
                        matching_rows = df[
                            df[id_column].astype(str) == str(document_id)
                        ]
                        if len(matching_rows) > 0:
                            return matching_rows.iloc[0].to_dict()

                # No ID column or ID not found - try row index fallback
                try:
                    row_index = int(document_id)
                    if 0 <= row_index < len(df):
                        return df.iloc[row_index].to_dict()
                except (ValueError, TypeError):
                    pass

                # Document not found
                return None

            # No document_id provided - return all data
            # Apply query filters if provided
            if query:
                df = self._apply_query_filter(df, query)

            # Return data in requested format
            if format_type == "dataframe":
                return df
            elif format_type == "records":
                return df.to_dict(orient="records")
            elif format_type == "dict":
                return df.to_dict(orient="index")
            else:
                raise ValueError(f"Unsupported format: {format_type}")

        except Exception as e:
            self._logger.debug(f"Error reading CSV: {e}")
            return None

    def write(
        self,
        collection: str,
        data: Any,
        document_id: Optional[str] = None,
        mode: WriteMode = WriteMode.WRITE,
        path: Optional[str] = None,
        **kwargs,
    ) -> StorageResult:
        """
        Write data to CSV file.

        Smart writing:
        - When document_id provided: updates/inserts single row using detected ID column
        - When document_id not provided: writes all data (list/DataFrame)
        - Auto-detects ID column or falls back to row index

        Args:
            collection: CSV file name/path
            data: Data to write (DataFrame, dict, or list of dicts)
            document_id: Row ID for single-row operations
            mode: Write mode (write, append, update)
            path: Not used for CSV
            **kwargs: Additional parameters (including id_field for custom ID column)

        Returns:
            StorageResult with operation details
        """
        try:
            # Extract service-specific parameters that shouldn't go to pandas
            id_field = kwargs.pop("id_field", None)  # Extract id_field from kwargs
            file_path = self._get_file_path(collection)
            file_existed = os.path.exists(file_path)

            if not file_existed and not self.configuration.is_csv_auto_create_enabled():
                return self._create_error_result(
                    "write",
                    f"CSV file does not exist: {file_path}. Enable auto_create_files: true in CSV config to create automatically.",
                    collection=collection,
                    file_path=file_path,
                )

            # Convert data to DataFrame
            if isinstance(data, pd.DataFrame):
                df = data.copy()
            elif isinstance(data, dict):
                df = pd.DataFrame([data])
            elif isinstance(data, list):
                df = pd.DataFrame(data)
            else:
                raise StorageProviderError(f"Unsupported data type: {type(data)}")

            # Handle document_id-based operations
            if document_id is not None:
                # Check if this is single-row or multi-row operation
                if len(df) == 1:
                    # Read existing file to determine ID column
                    existing_df = None
                    id_column = id_field  # Use provided id_field if available
                    if file_existed:
                        try:
                            existing_df = self._read_csv_file(file_path)
                            if id_column is None:  # Only detect if not provided
                                id_column = self._detect_id_column(existing_df)
                        except Exception:
                            existing_df = None

                    # If no existing file, try to detect ID from new data
                    if id_column is None:
                        id_column = self._detect_id_column(df)

                    # Ensure the document_id is in the data
                    if id_column is not None:
                        # Set the ID column value
                        df[id_column] = document_id
                    else:
                        # No ID column detected - create one
                        id_column = "id"
                        df[id_column] = document_id

                    # Handle single-row write based on mode and existing data
                    if mode == WriteMode.WRITE or not file_existed:
                        # Overwrite or create new file
                        self._write_csv_file(df, file_path, mode="w", **kwargs)
                        return self._create_success_result(
                            "write",
                            collection=collection,
                            document_id=document_id,
                            file_path=file_path,
                            rows_written=len(df),
                            created_new=not file_existed,
                        )

                    elif mode == WriteMode.UPDATE:
                        # Update existing row or append new row
                        if existing_df is not None and id_column in existing_df.columns:
                            # Try to update existing row
                            mask = existing_df[id_column].astype(str) == str(
                                document_id
                            )
                            if mask.any():
                                # Update existing row
                                for col in df.columns:
                                    if col in existing_df.columns:
                                        existing_df.loc[mask, col] = df[col].iloc[0]
                                updated_df = existing_df
                            else:
                                # Append new row
                                updated_df = pd.concat(
                                    [existing_df, df], ignore_index=True
                                )
                        else:
                            # No existing data, just write new
                            updated_df = df

                        self._write_csv_file(updated_df, file_path, mode="w", **kwargs)
                        return self._create_success_result(
                            "update",
                            collection=collection,
                            document_id=document_id,
                            file_path=file_path,
                            rows_written=len(df),
                        )

                    elif mode == WriteMode.APPEND:
                        # Append new row
                        write_mode = "a" if file_existed else "w"
                        self._write_csv_file(df, file_path, mode=write_mode, **kwargs)
                        return self._create_success_result(
                            "append",
                            collection=collection,
                            document_id=document_id,
                            file_path=file_path,
                            rows_written=len(df),
                        )

                else:
                    # Multi-row operation: use document_id as batch identifier
                    # Add a special column to track the batch/document ID
                    batch_column = "_document_id"
                    df[batch_column] = document_id

                    if mode == WriteMode.WRITE or not file_existed:
                        # Overwrite or create new file
                        self._write_csv_file(df, file_path, mode="w", **kwargs)
                        return self._create_success_result(
                            "write",
                            collection=collection,
                            document_id=document_id,
                            file_path=file_path,
                            rows_written=len(df),
                            created_new=not file_existed,
                        )

                    elif mode == WriteMode.UPDATE:
                        # Replace existing batch or append new batch
                        if file_existed:
                            existing_df = self._read_csv_file(file_path)
                            if batch_column in existing_df.columns:
                                # Remove existing rows with same document_id
                                filtered_df = existing_df[
                                    existing_df[batch_column] != document_id
                                ]
                                # Append new batch
                                updated_df = pd.concat(
                                    [filtered_df, df], ignore_index=True
                                )
                            else:
                                # No batch column in existing data, just append
                                updated_df = pd.concat(
                                    [existing_df, df], ignore_index=True
                                )
                        else:
                            updated_df = df

                        self._write_csv_file(updated_df, file_path, mode="w", **kwargs)
                        return self._create_success_result(
                            "update",
                            collection=collection,
                            document_id=document_id,
                            file_path=file_path,
                            rows_written=len(df),
                        )

                    elif mode == WriteMode.APPEND:
                        # Append new batch
                        write_mode = "a" if file_existed else "w"
                        self._write_csv_file(df, file_path, mode=write_mode, **kwargs)
                        return self._create_success_result(
                            "append",
                            collection=collection,
                            document_id=document_id,
                            file_path=file_path,
                            rows_written=len(df),
                        )

            else:
                # Bulk data operations (no document_id)
                rows_written = len(df)

                if mode == WriteMode.WRITE:
                    # Overwrite file
                    self._write_csv_file(df, file_path, mode="w", **kwargs)
                    return self._create_success_result(
                        "write",
                        collection=collection,
                        file_path=file_path,
                        rows_written=rows_written,
                        created_new=not file_existed,
                    )

                elif mode == WriteMode.APPEND:
                    # Append to file
                    write_mode = "a" if file_existed else "w"
                    self._write_csv_file(df, file_path, mode=write_mode, **kwargs)
                    return self._create_success_result(
                        "append",
                        collection=collection,
                        file_path=file_path,
                        rows_written=rows_written,
                    )

                elif mode == WriteMode.UPDATE:
                    # For bulk updates without document_id, merge on detected ID column
                    if file_existed:
                        existing_df = self._read_csv_file(file_path)
                        id_column = self._detect_id_column(existing_df)

                        if id_column and id_column in df.columns:
                            # Merge DataFrames on ID column
                            updated_df = existing_df.copy()
                            for _, row in df.iterrows():
                                row_id = row[id_column]
                                mask = updated_df[id_column] == row_id
                                if mask.any():
                                    # Update existing row
                                    for col in row.index:
                                        if col in updated_df.columns:
                                            updated_df.loc[mask, col] = row[col]
                                else:
                                    # Append new row
                                    updated_df = pd.concat(
                                        [updated_df, row.to_frame().T],
                                        ignore_index=True,
                                    )

                            self._write_csv_file(
                                updated_df, file_path, mode="w", **kwargs
                            )
                            return self._create_success_result(
                                "update",
                                collection=collection,
                                file_path=file_path,
                                rows_written=rows_written,
                                total_affected=len(updated_df),
                            )
                        else:
                            # No ID column, just append
                            self._write_csv_file(df, file_path, mode="a", **kwargs)
                            return self._create_success_result(
                                "update",
                                collection=collection,
                                file_path=file_path,
                                rows_written=rows_written,
                            )
                    else:
                        # File doesn't exist, create it
                        self._write_csv_file(df, file_path, mode="w", **kwargs)
                        return self._create_success_result(
                            "update",
                            collection=collection,
                            file_path=file_path,
                            rows_written=rows_written,
                            created_new=True,
                        )

            return self._create_error_result(
                "write", f"Unsupported write mode: {mode}", collection=collection
            )

        except (PermissionError, OSError) as e:
            # Handle permission and OS errors gracefully
            error_msg = f"Permission denied: {str(e)}"
            self._logger.error(
                f"[{self.provider_name}] {error_msg} (collection={collection}, file_path={file_path})"
            )
            return self._create_error_result("write", error_msg, collection=collection)
        except StorageProviderError:
            # Let StorageProviderError propagate to caller
            raise
        except Exception as e:
            return self._create_error_result(
                "write", f"Write operation failed: {str(e)}", collection=collection
            )

    def delete(
        self,
        collection: str,
        document_id: Optional[str] = None,
        path: Optional[str] = None,
        id_field: Optional[str] = None,
        **kwargs,
    ) -> StorageResult:
        """
        Delete from CSV file.

        Uses smart ID detection to find and delete rows.
        Falls back to row index if no ID column found.

        Args:
            collection: CSV file name/path
            document_id: Row ID to delete or row index
            path: Not used for CSV
            id_field: Custom ID field name (overrides auto-detection)
            **kwargs: Additional parameters

        Returns:
            StorageResult with operation details
        """
        try:
            file_path = self._get_file_path(collection)

            if document_id is None:
                # Delete entire file
                if os.path.exists(file_path):
                    os.remove(file_path)
                    return self._create_success_result(
                        "delete",
                        collection=collection,
                        file_path=file_path,
                        file_deleted=True,
                    )
                else:
                    return self._create_error_result(
                        "delete", f"File not found: {file_path}", collection=collection
                    )

            # Delete specific row(s)
            if not os.path.exists(file_path):
                return self._create_error_result(
                    "delete", f"File not found: {file_path}", collection=collection
                )

            df = self._read_csv_file(file_path)

            if df.empty:
                return self._create_error_result(
                    "delete", "CSV file is empty", collection=collection
                )

            initial_count = len(df)

            # First check if there's a batch column (multi-row document_id)
            batch_column = "_document_id"
            id_column = None  # Track which column was used for deletion

            if batch_column in df.columns:
                # Delete all rows with matching document_id
                df_filtered = df[df[batch_column] != document_id]
                id_column = batch_column
            else:
                # Try smart ID column detection for single row
                id_column = id_field if id_field else self._detect_id_column(df)

                if id_column is not None:
                    # Delete using detected ID column
                    try:
                        # Try to convert document_id to match column type
                        if pd.api.types.is_numeric_dtype(df[id_column]):
                            search_value = pd.to_numeric(document_id)
                        else:
                            search_value = str(document_id)

                        df_filtered = df[df[id_column] != search_value]
                    except (ValueError, TypeError):
                        # Conversion failed, try direct string comparison
                        df_filtered = df[df[id_column].astype(str) != str(document_id)]
                else:
                    # No ID column found - fail with clear error message
                    return self._create_error_result(
                        "delete",
                        f"ID field not found in CSV and no custom id_field specified. Available columns: {list(df.columns)}",
                        collection=collection,
                        document_id=document_id,
                    )

            deleted_count = initial_count - len(df_filtered)

            if deleted_count == 0:
                return self._create_error_result(
                    "delete",
                    f"Document with ID '{document_id}' not found",
                    collection=collection,
                    document_id=document_id,
                )

            # Write back the filtered data
            self._write_csv_file(df_filtered, file_path, mode="w")

            # Convert document_id to match the ID column type for consistency
            result_document_id = document_id
            if id_column and id_column in df.columns:
                try:
                    if pd.api.types.is_numeric_dtype(df[id_column]):
                        result_document_id = pd.to_numeric(document_id)
                except (ValueError, TypeError):
                    # Keep as string if conversion fails
                    pass

            return self._create_success_result(
                "delete",
                collection=collection,
                file_path=file_path,
                document_id=result_document_id,
                total_affected=deleted_count,
            )

        except Exception as e:
            return self._create_error_result(
                "delete", f"Delete operation failed: {str(e)}", collection=collection
            )

    def exists(
        self,
        collection: str,
        document_id: Optional[str] = None,
        id_field: Optional[str] = None,
    ) -> bool:
        """
        Check if CSV file or document exists.

        Uses smart ID detection to check document existence.
        Falls back to row index if no ID column found.

        Args:
            collection: CSV file name/path
            document_id: Row ID to check or row index
            id_field: Custom ID field name (overrides auto-detection)

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

            # If file is empty, document doesn't exist
            if len(df) == 0:
                return False

            # First check if there's a batch column (multi-row document_id)
            batch_column = "_document_id"
            if batch_column in df.columns:
                # Check for batch with matching document_id
                return document_id in df[batch_column].values

            # Try smart ID column detection for single row
            id_column = id_field if id_field else self._detect_id_column(df)

            if id_column is not None:
                # Check using detected ID column
                try:
                    # Try to convert document_id to match column type
                    if pd.api.types.is_numeric_dtype(df[id_column]):
                        search_value = pd.to_numeric(document_id)
                    else:
                        search_value = str(document_id)

                    return search_value in df[id_column].values
                except (ValueError, TypeError):
                    # Conversion failed, try direct string comparison
                    return str(document_id) in df[id_column].astype(str).values
            else:
                # No ID column - try row index fallback
                try:
                    row_index = int(document_id)
                    return 0 <= row_index < len(df)
                except (ValueError, TypeError):
                    return False

        except Exception as e:
            self._logger.debug(f"Error checking existence: {e}")
            return False

    def count(self, collection: str, query: Optional[Dict[str, Any]] = None) -> int:
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
        List all CSV collections.

        Returns both configured collections from StorageConfigService
        and CSV files found in the base directory.

        Returns:
            List of collection names (configured collections + CSV file names)
        """
        try:
            collections = set()

            # Add configured collections from StorageConfigService
            try:
                configured_collections = self.configuration.list_collections("csv")
                collections.update(configured_collections)
            except Exception as e:
                self._logger.debug(f"Could not get configured collections: {e}")

            # Add CSV files found in base directory
            base_dir = self.client["base_directory"]
            if os.path.exists(base_dir):
                for item in os.listdir(base_dir):
                    if item.lower().endswith(".csv"):
                        # Remove .csv extension for collection name
                        collection_name = (
                            item[:-4] if item.lower().endswith(".csv") else item
                        )
                        collections.add(collection_name)

            return sorted(list(collections))

        except Exception as e:
            self._logger.debug(f"Error listing collections: {e}")
            return []
