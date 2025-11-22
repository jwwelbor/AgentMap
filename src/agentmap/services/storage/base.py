"""
Base storage service implementation for AgentMap.

This module provides the abstract base class for storage services,
following the Template Method pattern and established service patterns.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from agentmap.services.config.storage_config_service import StorageConfigService
from agentmap.services.file_path_service import FilePathService
from agentmap.services.logging_service import LoggingService
from agentmap.services.storage.config_loader import ConfigLoaderMixin
from agentmap.services.storage.error_handling import ErrorHandlerMixin
from agentmap.services.storage.path_resolver import PathResolverMixin
from agentmap.services.storage.protocols import StorageService
from agentmap.services.storage.types import (
    StorageConfig,
    StorageResult,
    StorageServiceConfigurationError,
    WriteMode,
)


class BaseStorageService(
    PathResolverMixin, ConfigLoaderMixin, ErrorHandlerMixin, StorageService, ABC
):
    """
    Base implementation for storage services.

    Provides common functionality for all storage services following
    the Template Method pattern. Concrete implementations need to
    implement provider-specific methods.

    Inherits from:
    - PathResolverMixin: Path resolution and validation
    - ConfigLoaderMixin: Provider configuration loading
    - ErrorHandlerMixin: Error handling and result creation
    - StorageService: Protocol interface
    - ABC: Abstract base class
    """

    def __init__(
        self,
        provider_name: str,
        configuration: StorageConfigService,
        logging_service: LoggingService,
        file_path_service: Optional[FilePathService] = None,
        base_directory: Optional[str] = None,
    ):
        """
        Initialize the base storage service.

        Args:
            provider_name: Name of the storage provider
            configuration: Storage configuration service for storage-specific config access
            logging_service: Logging service for creating loggers
            file_path_service: Optional file path service for path validation and security
            base_directory: Optional base directory for storage operations (for system storage)
        """
        self.provider_name = provider_name
        self.configuration = configuration
        self._logger = logging_service.get_class_logger(self)
        self._file_path_service = file_path_service
        self._base_directory = base_directory
        self._client = None
        self._config = self._load_provider_config()
        self._is_initialized = False

    def get_provider_name(self) -> str:
        """Get the storage provider name."""
        return self.provider_name

    def health_check(self) -> bool:
        """
        Check if storage service is healthy and accessible.

        Returns:
            True if service is healthy, False otherwise
        """
        try:
            self._logger.debug(f"[{self.provider_name}] Performing health check")
            result = self._perform_health_check()
            self._logger.debug(f"[{self.provider_name}] Health check result: {result}")
            return result
        except Exception as e:
            self._logger.error(f"[{self.provider_name}] Health check failed: {e}")
            return False

    @property
    def client(self) -> Any:
        """
        Get or initialize the storage client.

        Returns:
            Storage client instance
        """
        if self._client is None:
            try:
                self._logger.trace(f"[{self.provider_name}] Initializing client")
                self._client = self._initialize_client()
                self._is_initialized = True
                self._logger.info(
                    f"[{self.provider_name}] Client initialized successfully"
                )
            except Exception as e:
                self._logger.error(
                    f"[{self.provider_name}] Failed to initialize client: {e}"
                )
                raise StorageServiceConfigurationError(
                    f"Failed to initialize {self.provider_name} client: {str(e)}"
                )
        return self._client

    def list_collections(self) -> List[str]:
        """List all available collections."""
        self._logger.debug(f"[{self.provider_name}] list_collections not implemented")
        return []

    def create_collection(
        self, collection: str, schema: Optional[Dict[str, Any]] = None
    ) -> StorageResult:
        """Create a new collection (if supported by provider)."""
        self._logger.debug(f"[{self.provider_name}] create_collection not supported")
        return self._create_error_result(
            "create_collection",
            f"Collection creation not supported by {self.provider_name}",
            collection=collection,
        )

    def count(self, collection: str, query: Optional[Dict[str, Any]] = None) -> int:
        """Count documents/records in collection."""
        self._logger.debug(f"[{self.provider_name}] count not implemented")
        return 0

    def exists(self, collection: str, document_id: Optional[str] = None) -> bool:
        """Check if collection or document exists in storage."""
        self._logger.debug(f"[{self.provider_name}] exists not implemented")
        return False

    @abstractmethod
    def _initialize_client(self) -> Any:
        """Initialize the storage client."""

    @abstractmethod
    def _perform_health_check(self) -> bool:
        """Perform provider-specific health check."""

    @abstractmethod
    def read(
        self,
        collection: str,
        document_id: Optional[str] = None,
        query: Optional[Dict[str, Any]] = None,
        path: Optional[str] = None,
        **kwargs,
    ) -> Any:
        """Read data from storage."""

    @abstractmethod
    def write(
        self,
        collection: str,
        data: Any,
        document_id: Optional[str] = None,
        mode: WriteMode = WriteMode.WRITE,
        path: Optional[str] = None,
        **kwargs,
    ) -> StorageResult:
        """Write data to storage."""

    @abstractmethod
    def delete(
        self,
        collection: str,
        document_id: Optional[str] = None,
        path: Optional[str] = None,
        **kwargs,
    ) -> StorageResult:
        """Delete from storage."""

    def batch_write(
        self,
        collection: str,
        data: List[Dict[str, Any]],
        mode: WriteMode = WriteMode.WRITE,
        **kwargs,
    ) -> StorageResult:
        """Write multiple documents/records in a batch operation."""
        self._logger.debug(
            f"[{self.provider_name}] Performing batch write of {len(data)} items"
        )

        total_written = 0
        errors = []

        for i, item in enumerate(data):
            try:
                result = self.write(collection, item, mode=mode, **kwargs)
                if result.success:
                    total_written += 1
                else:
                    errors.append(f"Item {i}: {result.error}")
            except Exception as e:
                errors.append(f"Item {i}: {str(e)}")

        if errors:
            error_msg = "; ".join(errors[:5])
            if len(errors) > 5:
                error_msg += f" (and {len(errors) - 5} more errors)"

            return self._create_error_result(
                "batch_write",
                error_msg,
                collection=collection,
                total_affected=total_written,
                error_count=len(errors),
            )

        return self._create_success_result(
            "batch_write", collection=collection, total_affected=total_written
        )
