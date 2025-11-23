# services/graph/bundle_storage.py

from pathlib import Path
from typing import Any, Dict, Optional

from agentmap.models.graph_bundle import GraphBundle
from agentmap.services.config.app_config_service import AppConfigService
from agentmap.services.file_path_service import FilePathService
from agentmap.services.graph.bundle_serializer import BundleSerializer
from agentmap.services.logging_service import LoggingService
from agentmap.services.storage.system_manager import SystemStorageManager
from agentmap.services.storage.types import StorageResult, WriteMode


class BundleStorage:
    """Handles storage operations for graph bundles.

    This class is responsible for saving, loading, and deleting bundles
    from the file system, using appropriate storage services.
    """

    def __init__(
        self,
        logging_service: LoggingService,
        bundle_serializer: BundleSerializer,
        system_storage_manager: SystemStorageManager,
        file_path_service: FilePathService,
        app_config_service: Optional[AppConfigService] = None,
    ):
        """Initialize the bundle storage.

        Args:
            logging_service: Service for logging operations
            bundle_serializer: Service for bundle serialization/deserialization
            system_storage_manager: System storage manager for system cache storage
            file_path_service: File path service for centralized secure path handling
            app_config_service: Application config service for cache path (optional)
        """
        self.logger = logging_service.get_class_logger(self)
        self.serializer = bundle_serializer
        self.system_storage_manager = system_storage_manager
        self.file_path_service = file_path_service
        self.app_config_service = app_config_service

    def save_bundle(self, bundle: GraphBundle, path: Path) -> Optional[StorageResult]:
        """Persist the bundle to disk in appropriate format.

        Saves metadata-only bundles as JSON. Uses SystemStorageManager for system bundles
        in cache_folder/bundles and JSONStorageService for user storage.

        Args:
            bundle: GraphBundle to save
            path: Path to save the bundle to (can be Path or str)

        Returns:
            StorageResult if successful, None otherwise

        Raises:
            ValueError: If required storage service is not available
            IOError: If save operation fails
        """
        # Ensure path is a Path object
        path = Path(path)

        # Use system storage for cache_folder/bundles
        self.logger.debug(f"Using SystemStorageManager for system bundle: {path}")

        # Serialize bundle to dictionary
        data = self.serializer.serialize_metadata_bundle(bundle)

        # Get JSON storage service for "bundles" namespace
        storage_service = self.system_storage_manager.get_json_storage("bundles")

        result = storage_service.write(
            collection=path.name, data=data, mode=WriteMode.WRITE
        )

        if result.success:
            self.logger.debug(
                f"Saved system bundle to cache_folder/bundles/{path.name} with csv_hash {bundle.csv_hash}"
            )
            return result
        else:
            error_msg = f"Failed to save system bundle: {result.error}"
            self.logger.error(error_msg)
            raise IOError(error_msg)

    def load_bundle(self, path: Path) -> Optional[GraphBundle]:
        """Load a GraphBundle from a file.

        Automatically detects format (JSON for metadata)
        and loads appropriately. Uses SystemStorageManager for system bundles
        in cache_folder/bundles and JSONStorageService for user storage.

        Args:
            path: Path to load the bundle from (can be Path or str)

        Returns:
            GraphBundle or None if loading fails

        Raises:
            ValueError: If required storage service is not available
        """
        try:
            # Ensure path is a Path object
            path = Path(path)

            # Use system storage for cache_folder/bundles
            self.logger.debug(f"Using SystemStorageManager for system bundle: {path}")

            # Get JSON storage service for "bundles" namespace
            storage_service = self.system_storage_manager.get_json_storage("bundles")
            data = storage_service.read(
                collection=path.name,
            )

            if data is None:
                self.logger.error(f"No data found in system bundle file: {path}")
                return None

            return self.serializer.deserialize_metadata_bundle(data)

        except Exception as e:
            self.logger.error(f"Failed to load GraphBundle from {path}: {e}")
            return None

    def delete_bundle(self, bundle: GraphBundle) -> bool:
        """Delete a cached bundle file from disk.

        Uses the bundle's csv_hash and graph_name to locate and delete the cached bundle file
        using consistent path format from FilePathService.
        This method only handles file deletion - registry cleanup should be
        handled separately by the caller if needed.

        Args:
            bundle: GraphBundle containing the csv_hash to identify the cached file

        Returns:
            True if bundle file was deleted, False if file not found

        Raises:
            ValueError: If bundle has no csv_hash
            PermissionError: If insufficient permissions to delete file
            IOError: If deletion fails for other reasons
        """
        # Check for csv_hash first, before any other operations
        # Note: GraphBundle.__post_init__ converts None to "unknown_hash"
        if (
            bundle.csv_hash is None
            or bundle.csv_hash == ""
            or bundle.csv_hash == "unknown_hash"
        ):
            raise ValueError(
                "Bundle has no csv_hash - cannot identify cached file to delete"
            )

        try:
            # Use FilePathService to get consistent bundle path
            bundle_path = self.file_path_service.get_bundle_path(
                csv_hash=bundle.csv_hash, graph_name=bundle.graph_name
            )

            if not bundle_path.exists():
                self.logger.debug(f"Bundle file not found for deletion: {bundle_path}")
                return False

            # Delete the bundle file
            bundle_path.unlink()
            self.logger.info(
                f"Deleted cached bundle: {bundle_path.name} for graph '{bundle.graph_name}'"
            )
            return True

        except PermissionError as e:
            error_msg = f"Permission denied when deleting bundle file: {e}"
            self.logger.error(error_msg)
            raise PermissionError(error_msg)
        except Exception as e:
            error_msg = f"Failed to delete bundle file: {e}"
            self.logger.error(error_msg)
            raise IOError(error_msg)

    def is_cache_path(self, path: Path) -> bool:
        """Check if the given path is within the cache_folder.

        Args:
            path: Path to check

        Returns:
            True if path is within cache_folder, False otherwise
        """
        if not self.app_config_service:
            return False

        try:
            cache_folder = Path(self.app_config_service.get_cache_folder())
            return cache_folder in path.parents or path.parent == cache_folder
        except Exception as e:
            self.logger.debug(f"Could not determine if path is in cache folder: {e}")
            return False
