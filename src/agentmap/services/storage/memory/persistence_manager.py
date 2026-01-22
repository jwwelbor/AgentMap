"""
Persistence Manager for AgentMap Memory Storage.

This module provides file-based persistence for in-memory storage,
allowing data to be saved and loaded from disk.
"""

import json
import logging
import os
import time
from typing import Any, Dict, Optional


class PersistenceManager:
    """
    File-based persistence for memory storage.

    Handles saving and loading storage state to/from JSON files.
    """

    def __init__(self, logger: logging.Logger):
        """
        Initialize persistence manager.

        Args:
            logger: Logger instance for logging operations
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
            storage: Storage dictionary
            metadata: Metadata dictionary
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

    def load_from_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Load storage state from persistence file.

        Args:
            file_path: Path to persistence file

        Returns:
            Dictionary with storage, metadata, and stats or None if load fails
        """
        try:
            if not os.path.exists(file_path):
                self._logger.debug(f"Persistence file not found: {file_path}")
                return None

            with open(file_path, "r", encoding="utf-8") as f:
                persistence_data = json.load(f)

            self._logger.debug(f"Loaded memory storage from {file_path}")
            return persistence_data

        except Exception as e:
            self._logger.warning(f"Failed to load persistence data: {e}")
            return None
