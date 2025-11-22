"""
Storage helper utilities for interaction handling.

Provides collection normalization, legacy migration support, and
common storage operations for the interaction handler service.
"""

import pickle
from pathlib import Path
from typing import Any, Optional

from agentmap.services.storage.types import WriteMode


class StorageHelpers:
    """
    Helper class for storage operations in interaction handling.

    Handles:
    - Collection name normalization
    - Pickle serialization/deserialization
    - Legacy storage migration
    - Read/write wrapper operations
    """

    def __init__(self, file_storage, logger):
        """
        Initialize storage helpers.

        Args:
            file_storage: File storage service instance
            logger: Logger instance for operations
        """
        self.file_storage = file_storage
        self.logger = logger

    def normalize_collection_name(self, collection: str) -> str:
        """
        Normalize storage collection to be relative to the base directory.

        This ensures collection names are consistent regardless of how they're
        specified, preventing duplicate storage paths.

        Args:
            collection: Collection name to normalize

        Returns:
            Normalized collection name relative to base directory
        """
        if not collection:
            return ""

        base_dir = str(self.file_storage.client.get("base_directory", ""))
        base_dir_normalized = base_dir.replace("\\", "/").rstrip("/")
        collection_normalized = str(collection).replace("\\", "/").strip("/")

        if base_dir_normalized and collection_normalized.startswith(
            base_dir_normalized
        ):
            remainder = collection_normalized[len(base_dir_normalized) :].lstrip("/")
            return remainder or ""

        return collection_normalized

    def write_collection(self, collection: str, **kwargs):
        """
        Write data to a collection with normalized path.

        Args:
            collection: Collection name
            **kwargs: Additional arguments passed to file_storage.write()

        Returns:
            StorageResult from file storage
        """
        normalized_collection = self.normalize_collection_name(collection)
        return self.file_storage.write(collection=normalized_collection, **kwargs)

    def read_collection(self, collection: str, **kwargs):
        """
        Read data from a collection with normalized path.

        Args:
            collection: Collection name
            **kwargs: Additional arguments passed to file_storage.read()

        Returns:
            Data from file storage or None if not found
        """
        normalized_collection = self.normalize_collection_name(collection)
        return self.file_storage.read(collection=normalized_collection, **kwargs)

    def find_legacy_thread_file(
        self, thread_id: str, threads_collection: str
    ) -> Optional[Path]:
        """
        Locate legacy-stored thread metadata files within the interactions namespace.

        This supports migration from older storage layouts where collections
        may have been nested differently.

        Args:
            thread_id: Thread ID to search for
            threads_collection: Threads collection name

        Returns:
            Path to legacy thread file if found, None otherwise
        """
        base_dir_value = self.file_storage.client.get("base_directory")
        if not base_dir_value:
            return None

        base_dir = Path(base_dir_value)
        expected_dir = base_dir / self.normalize_collection_name(threads_collection)
        expected_path = expected_dir / f"{thread_id}.pkl"

        if expected_path.exists():
            return expected_path

        if not base_dir.exists():
            return None

        # Search recursively for legacy files in different locations
        for path in base_dir.rglob(f"{thread_id}.pkl"):
            if path != expected_path:
                self.logger.debug(f"Found legacy thread file: {path}")
                return path

        return None

    def serialize_to_pickle(self, data: Any) -> bytes:
        """
        Serialize data to pickle format.

        Args:
            data: Data to serialize

        Returns:
            Pickled bytes
        """
        return pickle.dumps(data)

    def deserialize_from_pickle(self, data_bytes: bytes) -> Any:
        """
        Deserialize data from pickle format.

        Args:
            data_bytes: Pickled bytes to deserialize

        Returns:
            Deserialized data
        """
        return pickle.loads(data_bytes)

    def read_legacy_file(self, file_path: Path) -> Any:
        """
        Read and deserialize a legacy pickle file.

        Args:
            file_path: Path to legacy file

        Returns:
            Deserialized data from file
        """
        with file_path.open("rb") as f:
            return pickle.load(f)

    def migrate_legacy_file(
        self, thread_id: str, thread_data: Any, threads_collection: str
    ) -> bool:
        """
        Migrate legacy thread file to normalized location.

        Args:
            thread_id: Thread ID being migrated
            thread_data: Thread data to write
            threads_collection: Target collection name

        Returns:
            True if migration successful, False otherwise
        """
        try:
            data_bytes = self.serialize_to_pickle(thread_data)
            result = self.write_collection(
                collection=threads_collection,
                data=data_bytes,
                document_id=f"{thread_id}.pkl",
                mode=WriteMode.WRITE,
                binary_mode=True,
            )

            if result.success:
                self.logger.debug(f"📦 Migrated legacy thread: {thread_id}")
                return True
            else:
                self.logger.warning(
                    f"Failed to migrate legacy thread {thread_id}: {result.error}"
                )
                return False

        except Exception as e:
            self.logger.error(f"Error migrating legacy thread {thread_id}: {str(e)}")
            return False
