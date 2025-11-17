"""
CSV File Operations module.

Handles low-level file I/O operations for CSV storage.
"""

import os
from typing import Any, Dict

import pandas as pd


class CSVFileOperations:
    """
    Handles CSV file reading and writing operations.

    This class encapsulates all file I/O logic for CSV operations,
    including directory management and pandas DataFrame operations.
    """

    @staticmethod
    def ensure_directory_exists(file_path: str) -> None:
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

    @staticmethod
    def read_csv_file(
        file_path: str,
        encoding: str,
        default_options: Dict[str, Any],
        logger=None,
        **kwargs
    ) -> pd.DataFrame:
        """
        Read CSV file with error handling.

        Args:
            file_path: Path to CSV file
            encoding: File encoding
            default_options: Default pandas read options
            logger: Logger instance for debug messages
            **kwargs: Additional pandas read_csv parameters

        Returns:
            DataFrame with CSV data

        Raises:
            FileNotFoundError: If CSV file doesn't exist
            Exception: For other read errors
        """
        try:
            # Merge default options with provided kwargs
            read_options = default_options.copy()
            read_options["encoding"] = encoding
            read_options.update(kwargs)

            df = pd.read_csv(file_path, **read_options)
            if logger:
                logger.debug(f"Read {len(df)} rows from {file_path}")
            return df

        except FileNotFoundError:
            if logger:
                logger.debug(f"CSV file not found: {file_path}")
            raise
        except Exception as e:
            if logger:
                logger.error(f"Error reading CSV file {file_path}: {e}")
            raise

    @staticmethod
    def write_csv_file(
        df: pd.DataFrame,
        file_path: str,
        encoding: str,
        mode: str = "w",
        base_directory: str = None,
        logger=None,
        **kwargs
    ) -> None:
        """
        Write DataFrame to CSV file.

        Args:
            df: DataFrame to write
            file_path: Path to CSV file
            encoding: File encoding
            mode: Write mode ('w' for write, 'a' for append)
            base_directory: Optional base directory to create if using injection
            logger: Logger instance for debug messages
            **kwargs: Additional pandas to_csv parameters

        Raises:
            PermissionError: If file cannot be written due to permissions
            OSError: If other OS-level errors occur
        """
        try:
            # Ensure base directory exists when using injection (deferred from initialization)
            if base_directory:
                os.makedirs(base_directory, exist_ok=True)

            CSVFileOperations.ensure_directory_exists(file_path)

            # Set default write options
            write_options = {"index": False, "encoding": encoding}
            write_options.update(kwargs)

            # Handle header for append mode
            if mode == "a" and os.path.exists(file_path):
                write_options["header"] = False

            df.to_csv(file_path, mode=mode, **write_options)
            if logger:
                logger.debug(f"Wrote {len(df)} rows to {file_path} (mode: {mode})")

        except (PermissionError, OSError):
            # Let permission and OS errors propagate to be handled by caller
            raise
        except Exception as e:
            if logger:
                logger.error(f"Error writing CSV file {file_path}: {e}")
            raise
