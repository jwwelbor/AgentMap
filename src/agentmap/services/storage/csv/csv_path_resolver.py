"""
CSV Path Resolver - File path resolution logic.

This module provides file path resolution for CSV collections,
handling both configured collections and dynamic paths.
"""

import os
from typing import Any, Optional


class CSVPathResolver:
    """
    Handles file path resolution for CSV collections.

    Responsibilities:
    - Resolving collection names to file paths
    - Handling absolute vs relative paths
    - Supporting configured collections
    - Managing .csv extension handling
    - Path validation integration
    """

    def __init__(
        self,
        base_directory: str,
        configuration: Any,  # StorageConfigService
        file_path_service: Optional[Any] = None,  # FilePathService (optional)
        logger: Optional[Any] = None,
    ):
        """
        Initialize CSVPathResolver.

        Args:
            base_directory: Base directory for CSV files
            configuration: Storage configuration service
            file_path_service: Optional file path service for validation
            logger: Logger instance for logging operations
        """
        self.base_directory = base_directory
        self.configuration = configuration
        self._file_path_service = file_path_service
        self._logger = logger

    def get_file_path(self, collection: str) -> str:
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
            base_dir = self.base_directory

            # Ensure .csv extension
            if not collection.lower().endswith(".csv"):
                collection = f"{collection}.csv"

            if not collection.startswith(base_dir):
                collection = os.path.join(base_dir, collection)

            file_path = collection

        # Validate path using file_path_service if available
        if self._file_path_service:
            try:
                self._file_path_service.validate_safe_path(
                    file_path, self.base_directory
                )
            except Exception as e:
                if self._logger:
                    self._logger.error(f"Path validation failed for {file_path}: {e}")
                raise ValueError(f"Unsafe file path: {e}")

        return file_path
