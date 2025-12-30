"""
Content Processor for FileStorageService.

This module provides content preparation and conversion functionality,
handling various data types and formats for file storage operations.
"""

from typing import Any, Union


class ContentProcessor:
    """
    Processes and converts content for file operations.

    Provides methods to prepare various data types (strings, bytes, documents,
    dictionaries, etc.) for writing to files.
    """

    @staticmethod
    def prepare_content(data: Any) -> Union[str, bytes]:
        """
        Convert data to writable content.

        Args:
            data: Input data in various formats

        Returns:
            String or bytes content for writing
        """
        if hasattr(data, "page_content"):
            # Single LangChain document
            return data.page_content
        elif isinstance(data, list) and data and hasattr(data[0], "page_content"):
            # List of LangChain documents
            return "\n\n".join(doc.page_content for doc in data)
        elif isinstance(data, dict):
            # Try to extract content from dictionary
            if "content" in data:
                return str(data["content"])
            else:
                # Convert whole dict to string
                return str(data)
        elif isinstance(data, bytes):
            # Binary data
            return data
        else:
            # Convert to string directly
            return str(data)
