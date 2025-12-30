"""
File I/O Handler for FileStorageService.

This module provides low-level file reading and writing operations,
handling both text and binary files with proper encoding and error handling.
"""

from pathlib import Path
from typing import TYPE_CHECKING

from agentmap.services.storage.types import StorageResult, WriteMode

if TYPE_CHECKING:
    from logging import Logger


class FileIOHandler:
    """
    Handles low-level file I/O operations.

    Provides methods for reading and writing text and binary files
    with proper encoding, error handling, and mode management.
    """

    def __init__(
        self,
        encoding: str = "utf-8",
        newline: str | None = None,
        logger: "Logger" = None,
    ):
        """
        Initialize the file I/O handler.

        Args:
            encoding: Default text encoding
            newline: Newline character for text files
            logger: Logger instance for error reporting
        """
        self.encoding = encoding
        self.newline = newline
        self._logger = logger

    def read_text_file(self, file_path: Path, encoding: str | None = None) -> str:
        """
        Read text file content.

        Args:
            file_path: Path to text file
            encoding: Optional encoding override

        Returns:
            File content as string
        """
        enc = encoding or self.encoding

        with open(file_path, "r", encoding=enc) as f:
            return f.read()

    def read_binary_file(self, file_path: Path) -> bytes:
        """
        Read binary file content.

        Args:
            file_path: Path to binary file

        Returns:
            File content as bytes
        """
        with open(file_path, "rb") as f:
            return f.read()

    def write_text_file(
        self,
        file_path: Path,
        content: str,
        mode: WriteMode,
        file_exists: bool,
        collection: str,
        encoding: str | None = None,
        newline: str | None = None,
        error_result_creator=None,
        success_result_creator=None,
    ) -> StorageResult:
        """
        Write content to text file.

        Args:
            file_path: Path to file
            content: Content to write
            mode: Write mode
            file_exists: Whether file existed before operation
            collection: Collection name for error reporting
            encoding: Optional encoding override
            newline: Optional newline override
            error_result_creator: Function to create error results
            success_result_creator: Function to create success results

        Returns:
            StorageResult with operation details
        """
        enc = encoding or self.encoding
        nl = newline if newline is not None else self.newline

        try:
            # Handle different write modes
            if mode == WriteMode.WRITE:
                # Create or overwrite file
                with open(file_path, "w", encoding=enc, newline=nl) as f:
                    f.write(content)

                return success_result_creator(
                    "write",
                    collection=collection,
                    file_path=str(file_path),
                    created_new=not file_exists,
                )

            elif mode == WriteMode.APPEND:
                # Append to existing file or create new
                with open(file_path, "a", encoding=enc, newline=nl) as f:
                    if file_exists:
                        # Add a newline before appending if needed
                        f.write("\n\n")
                    f.write(content)

                return success_result_creator(
                    "append",
                    collection=collection,
                    file_path=str(file_path),
                    created_new=not file_exists,
                )

            elif mode == WriteMode.UPDATE:
                # For text files, update is the same as write for simplicity
                with open(file_path, "w", encoding=enc, newline=nl) as f:
                    f.write(content)

                return success_result_creator(
                    "update",
                    collection=collection,
                    file_path=str(file_path),
                    created_new=not file_exists,
                )

            # Other modes not supported for simple text files
            return error_result_creator(
                "write",
                f"Unsupported write mode for text files: {mode}",
                collection=collection,
                file_path=str(file_path),
            )

        except (PermissionError, OSError) as e:
            # Handle permission and OS errors gracefully
            error_msg = f"Permission denied: {str(e)}"
            if self._logger:
                self._logger.error(
                    f"Permission error writing to {file_path}: {error_msg}"
                )
            return error_result_creator(
                "write", error_msg, collection=collection, file_path=str(file_path)
            )

    def write_binary_file(
        self,
        file_path: Path,
        content: bytes,
        mode: WriteMode,
        file_exists: bool,
        collection: str,
        error_result_creator=None,
        success_result_creator=None,
    ) -> StorageResult:
        """
        Write content to binary file.

        Args:
            file_path: Path to file
            content: Binary content to write
            mode: Write mode
            file_exists: Whether file existed before operation
            collection: Collection name for error reporting
            error_result_creator: Function to create error results
            success_result_creator: Function to create success results

        Returns:
            StorageResult with operation details
        """
        try:
            # Handle different write modes
            if mode == WriteMode.WRITE:
                # Create or overwrite file
                with open(file_path, "wb") as f:
                    f.write(content)

                return success_result_creator(
                    "write",
                    collection=collection,
                    file_path=str(file_path),
                    created_new=not file_exists,
                )

            elif mode == WriteMode.APPEND:
                # Append to existing file or create new
                with open(file_path, "ab") as f:
                    f.write(content)

                return success_result_creator(
                    "append",
                    collection=collection,
                    file_path=str(file_path),
                    created_new=not file_exists,
                )

            elif mode == WriteMode.UPDATE:
                # For binary files, update is the same as write
                with open(file_path, "wb") as f:
                    f.write(content)

                return success_result_creator(
                    "update",
                    collection=collection,
                    file_path=str(file_path),
                    created_new=not file_exists,
                )

            # Other modes not supported for binary files
            return error_result_creator(
                "write",
                f"Unsupported write mode for binary files: {mode}",
                collection=collection,
                file_path=str(file_path),
            )

        except (PermissionError, OSError) as e:
            # Handle permission and OS errors gracefully
            error_msg = f"Permission denied: {str(e)}"
            if self._logger:
                self._logger.error(
                    f"Permission error writing to {file_path}: {error_msg}"
                )
            return error_result_creator(
                "write", error_msg, collection=collection, file_path=str(file_path)
            )
