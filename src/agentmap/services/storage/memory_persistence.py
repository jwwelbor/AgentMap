"""
Persistence operations for memory storage service.

This module handles saving and loading memory storage data to/from disk.
"""

import json
import os
import time
from typing import Any, Dict


class MemoryPersistenceManager:
    """
    Manages persistence operations for memory storage.

    Handles saving and loading storage state to/from JSON files.
    """

    def __init__(self, logger):
        """
        Initialize persistence manager.

        Args:
            logger: Logger instance for debugging and warnings
        """
        self._logger = logger

    def save_to_file(
        self,
        file_path: str,
        storage: Dict[str, Dict[str, Any]],
        metadata: Dict[str, Dict[str, Dict[str, Any]]],
        stats: Dict[str, Any],
    ) -> None:
        """
        Save current storage state to persistence file.

        Args:
            file_path: Path to persistence file
            storage: Storage data structure
            metadata: Metadata structure
            stats: Statistics dictionary
        """
        try:
            persistence_data = {
                "storage": storage,
                "metadata": metadata,
                "stats": stats,
                "saved_at": time.time(),
            }

            # Ensure directory exists
            os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(persistence_data, f, indent=2, default=str)

            self._logger.debug(f"Saved memory storage to {file_path}")
        except Exception as e:
            self._logger.warning(f"Failed to save persistence data: {e}")

    def load_from_file(
        self, file_path: str
    ) -> tuple[
        Dict[str, Dict[str, Any]], Dict[str, Dict[str, Dict[str, Any]]], Dict[str, Any]
    ]:
        """
        Load storage state from persistence file.

        Args:
            file_path: Path to persistence file

        Returns:
            Tuple of (storage, metadata, stats) dictionaries
        """
        try:
            if not os.path.exists(file_path):
                self._logger.debug(f"Persistence file not found: {file_path}")
                return {}, {}, {}

            with open(file_path, "r", encoding="utf-8") as f:
                persistence_data = json.load(f)

            storage = persistence_data.get("storage", {})
            metadata = persistence_data.get("metadata", {})
            stats = persistence_data.get("stats", {})

            self._logger.debug(f"Loaded memory storage from {file_path}")
            return storage, metadata, stats

        except Exception as e:
            self._logger.warning(f"Failed to load persistence data: {e}")
            return {}, {}, {}
