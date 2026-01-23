"""
CSV File Handler - Low-level CSV file I/O operations.

This module provides a focused handler for CSV file reading, writing,
and directory management operations.
"""

import os
from typing import Any, Dict, Optional

import pandas as pd


class CSVFileHandler:
    """
    Handles low-level CSV file I/O operations.

    Responsibilities:
    - Reading CSV files with pandas
    - Writing CSV files with pandas
    - Directory existence management
    - Error handling for file operations
    """

    def __init__(
        self,
        encoding: str = "utf-8",
        default_options: Dict[str, Any] = None,
        logger: Optional[Any] = None,
    ):
        """
        Initialize CSVFileHandler.

        Args:
            encoding: Default encoding for CSV files
            default_options: Default pandas read options
            logger: Logger instance for logging operations
        """
        self.encoding = encoding
        self.default_options = default_options or {
            "skipinitialspace": True,
            "skip_blank_lines": True,
            "on_bad_lines": "warn",
        }
        self._logger = logger

    def read_csv_file(self, file_path: str, **kwargs) -> pd.DataFrame:
        """
        Read CSV file with error handling.

        Args:
            file_path: Path to CSV file
            **kwargs: Additional pandas read_csv parameters

        Returns:
            DataFrame with CSV data

        Raises:
            FileNotFoundError: If file doesn't exist
            Exception: For other read errors
        """
        try:
            # Merge default options with provided kwargs
            read_options = self.default_options.copy()
            read_options["encoding"] = self.encoding
            read_options.update(kwargs)

            df = pd.read_csv(file_path, **read_options)
            if self._logger:
                self._logger.debug(f"Read {len(df)} rows from {file_path}")
            return df

        except FileNotFoundError:
            if self._logger:
                self._logger.debug(f"CSV file not found: {file_path}")
            raise
        except Exception as e:
            if self._logger:
                self._logger.error(f"Error reading CSV file {file_path}: {e}")
            raise

    def write_csv_file(
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
            self.ensure_directory_exists(file_path)

            # Set default write options
            write_options = {"index": False, "encoding": self.encoding}
            write_options.update(kwargs)

            # Handle header for append mode
            if mode == "a" and os.path.exists(file_path):
                write_options["header"] = False

            df.to_csv(file_path, mode=mode, **write_options)
            if self._logger:
                self._logger.debug(
                    f"Wrote {len(df)} rows to {file_path} (mode: {mode})"
                )

        except (PermissionError, OSError):
            # Let permission and OS errors propagate
            raise
        except Exception as e:
            if self._logger:
                self._logger.error(f"Error writing CSV file {file_path}: {e}")
            raise

    def ensure_directory_exists(self, file_path: str) -> None:
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

    def file_exists(self, file_path: str) -> bool:
        """
        Check if a file exists.

        Args:
            file_path: Path to file

        Returns:
            True if file exists, False otherwise
        """
        return os.path.exists(file_path)
