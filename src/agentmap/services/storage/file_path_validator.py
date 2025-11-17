"""
File Path Validator for FileStorageService.

This module provides path validation and security functionality,
preventing directory traversal attacks and ensuring safe file operations.
"""

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from logging import Logger


class FilePathValidator:
    """
    Handles path validation and security for file storage operations.

    Provides methods to validate file paths, prevent directory traversal attacks,
    and ensure all file operations stay within the designated base directory.
    """

    def __init__(self, base_directory: str, logger: "Logger"):
        """
        Initialize the path validator.

        Args:
            base_directory: Base directory for all file operations
            logger: Logger instance for security warnings
        """
        self.base_directory = Path(base_directory).resolve()
        self._logger = logger

    def validate_file_path(self, file_path: str) -> str:
        """
        Validate file path is within base directory bounds (security).

        Enhanced validation that checks for path traversal attacks,
        absolute paths, and dangerous characters across all platforms.

        Args:
            file_path: Path to validate

        Returns:
            Validated and normalized path

        Raises:
            ValueError: If path tries to escape base directory
        """
        # Check for null bytes and other dangerous characters
        if "\0" in file_path:
            raise ValueError(
                f"Path {file_path} is outside base directory (contains null bytes)"
            )

        # Check for obvious directory traversal patterns
        # Normalize separators for cross-platform compatibility
        normalized_path = file_path.replace("\\", "/").replace("//", "/")

        # Check for parent directory references
        if "../" in normalized_path or normalized_path.startswith("../"):
            raise ValueError(
                f"Path {file_path} is outside base directory (contains directory traversal)"
            )

        # Check if it's an absolute path that's clearly outside our base
        if Path(file_path).is_absolute():
            # On Windows, check for different drive letters or system paths
            if os.name == "nt":
                # Block access to Windows system directories
                lower_path = file_path.lower()
                dangerous_windows_paths = [
                    "c:\\windows",
                    "c:\\program files",
                    "c:\\system32",
                    "/windows",
                    "/program files",
                    "/system32",
                ]
                for dangerous in dangerous_windows_paths:
                    if dangerous in lower_path:
                        raise ValueError(
                            f"Path {file_path} is outside base directory (system path)"
                        )
            else:
                # On Unix-like systems, block access to system directories
                dangerous_unix_paths = [
                    "/etc",
                    "/usr",
                    "/var",
                    "/bin",
                    "/sbin",
                    "/root",
                    "/sys",
                    "/proc",
                ]
                for dangerous in dangerous_unix_paths:
                    if (
                        normalized_path.startswith(dangerous + "/")
                        or normalized_path == dangerous
                    ):
                        raise ValueError(
                            f"Path {file_path} is outside base directory (system path)"
                        )

        # Resolve the path and check if it's within base directory
        raw_path = Path(file_path)
        if raw_path.is_absolute():
            full_path = raw_path.resolve()
        else:
            try:
                relative_suffix = raw_path.relative_to(self.base_directory)
            except ValueError:
                relative_suffix = raw_path
            full_path = (self.base_directory / relative_suffix).resolve()

        try:
            # Check if the resolved path is within base directory
            full_path.relative_to(self.base_directory)
            return str(full_path)
        except ValueError:
            raise ValueError(
                f"Path {file_path} is outside base directory {self.base_directory}"
            )

    def resolve_file_path(
        self, collection: str, document_id: str | None = None
    ) -> Path:
        """
        Resolve full file path from collection and document_id.

        Args:
            collection: Directory path (collection)
            document_id: Filename (document_id)

        Returns:
            Full file path
        """
        if document_id is None:
            # Collection only - treat as directory
            return self.base_directory / collection
        else:
            # Collection + document_id - treat as directory + filename
            return self.base_directory / collection / document_id

    def ensure_directory(self, directory_path: Path) -> None:
        """
        Create directory if it doesn't exist.

        Args:
            directory_path: Path to directory
        """
        directory_path.mkdir(parents=True, exist_ok=True)
