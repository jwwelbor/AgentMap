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
            page_content = data.page_content
            if not isinstance(page_content, str):
                raise TypeError("Document page_content must be a string")
            return page_content
        elif (
            isinstance(data, list)
            and data
            and all(hasattr(document, "page_content") for document in data)
        ):
            # List of LangChain documents
            page_contents = [document.page_content for document in data]
            if not all(isinstance(content, str) for content in page_contents):
                raise TypeError("Document page_content must be a string")
            return "\n\n".join(page_contents)
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
