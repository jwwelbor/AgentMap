"""
File Type Detector for FileStorageService.

This module provides file type detection functionality,
determining whether files should be handled as text or binary.
"""

from pathlib import Path


class FileTypeDetector:
    """
    Detects file types and determines appropriate handling strategy.

    Provides methods to identify text files, binary files, and determine
    the correct reading/writing mode for various file formats.
    """

    def __init__(self, allow_binary: bool = True):
        """
        Initialize the file type detector.

        Args:
            allow_binary: Whether binary file operations are allowed
        """
        self.allow_binary = allow_binary

        # Supported text file extensions
        self.text_extensions = [
            ".txt",
            ".md",
            ".html",
            ".htm",
            ".csv",
            ".log",
            ".py",
            ".js",
            ".json",
            ".yaml",
            ".yml",
            ".xml",
            ".rst",
        ]

        # Binary file extensions
        self.binary_extensions = [
            ".pdf",
            ".docx",
            ".doc",
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".zip",
            ".tar",
            ".gz",
            ".exe",
            ".dll",
        ]

    def is_text_file(self, file_path: str) -> bool:
        """
        Check if file is a supported text file.

        Args:
            file_path: Path to file

        Returns:
            True if supported text file, False otherwise
        """
        ext = Path(file_path).suffix.lower()
        return ext in self.text_extensions

    def is_binary_file(self, file_path: str) -> bool:
        """
        Check if file should be handled as binary.

        Args:
            file_path: Path to file

        Returns:
            True if binary file, False otherwise
        """
        if not self.allow_binary:
            return False

        ext = Path(file_path).suffix.lower()
        return ext in self.binary_extensions
