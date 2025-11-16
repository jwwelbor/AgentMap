"""
Base storage service implementation for AgentMap.

This module provides the abstract base class for storage services,
following the Template Method pattern and established service patterns.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

from agentmap.services.config.storage_config_service import StorageConfigService
from agentmap.services.file_path_service import FilePathService
from agentmap.services.logging_service import LoggingService
from agentmap.services.storage.protocols import StorageService
from agentmap.services.storage.types import (
    StorageConfig,
    StorageProviderError,
    StorageResult,
    StorageServiceConfigurationError,
    StorageServiceError,
    WriteMode,
)


class BaseStorageService(StorageService, ABC):
    """
    Base implementation for storage services.

    Provides common functionality for all storage services following
    the Template Method pattern. Concrete implementations need to
    implement provider-specific methods.
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

    @property
    def base_directory(self) -> Optional[str]:
        """
        Get the base directory for storage operations.

        Returns:
            Base directory path or None if not configured
        """
        return self._base_directory

    def get_full_path(self, key: str) -> str:
        """
        Get the full path for a storage key.

        Handles different path resolution strategies based on storage configuration:
        - For system storage (dict config): uses base_directory/key directly
        - For user storage (StorageConfigService): uses base_directory/storage_config_default_directory/key

        Args:
            key: Storage key/collection name

        Returns:
            Full resolved path for storage operations

        Raises:
            ValueError: If path cannot be resolved or is unsafe
        """
        if not key:
            raise ValueError("Storage key cannot be empty")

        # For system storage with base_directory injection (dict config)
        if self._base_directory:
            # Use base_directory directly with key
            full_path = str(Path(self._base_directory) / key)

            # Validate path if file_path_service is available
            if self._file_path_service:
                try:
                    self._file_path_service.validate_safe_path(
                        full_path, self._base_directory
                    )
                except Exception as e:
                    self._logger.error(
                        f"[{self.provider_name}] Path validation failed for {full_path}: {e}"
                    )
                    raise ValueError(f"Unsafe storage path: {e}")

            self._logger.trace(
                f"[{self.provider_name}] Resolved system storage path: {full_path}"
            )
            return full_path

        # For user storage (StorageConfigService) - use configuration's default directory
        else:
            try:
                # Get base directory from configuration
                config_base_dir = self.configuration.get_base_directory()
                if not config_base_dir:
                    raise ValueError(
                        "No base directory configured in StorageConfigService"
                    )

                # Combine with key
                full_path = str(Path(config_base_dir) / key)

                # Validate path if file_path_service is available
                if self._file_path_service:
                    try:
                        self._file_path_service.validate_safe_path(
                            full_path, config_base_dir
                        )
                    except Exception as e:
                        self._logger.error(
                            f"[{self.provider_name}] Path validation failed for {full_path}: {e}"
                        )
                        raise ValueError(f"Unsafe storage path: {e}")

                self._logger.trace(
                    f"[{self.provider_name}] Resolved user storage path: {full_path}"
                )
                return full_path

            except Exception as e:
                self._logger.error(
                    f"[{self.provider_name}] Failed to resolve storage path for key '{key}': {e}"
                )
                raise ValueError(f"Cannot resolve storage path: {e}")

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

    # Template method pattern for configuration loading
    def _load_provider_config(self) -> StorageConfig:
        """
        Load provider-specific configuration using StorageConfigService methods.

        Returns:
            StorageConfig for this provider
        """
        if self.provider_name.startswith("system_"):
            return (
                self.configuration
            )  # System storage is static dict src\agentmap\services\storage\system_manager.py

        try:

            # Use storage-specific configuration methods instead of generic access
            if self.provider_name in ["firebase", "mongodb", "supabase", "local"]:
                # Use named provider methods for known providers
                method_name = f"get_{self.provider_name}_config"
                if hasattr(self.configuration, method_name):
                    config_data = getattr(self.configuration, method_name)()
                else:
                    config_data = self.configuration.get_provider_config(
                        self.provider_name
                    )
            else:
                # Use generic provider method for other providers
                config_data = self.configuration.get_provider_config(self.provider_name)

            # Fallback to storage type configs if provider config is empty
            if not config_data and self.provider_name in [
                "csv",
                "vector",
                "memory",
                "file",
                "kv",
                "blob",
                "json",
            ]:
                storage_type_method = f"get_{self.provider_name}_config"
                if hasattr(self.configuration, storage_type_method):
                    config_data = getattr(self.configuration, storage_type_method)()
                    self._logger.debug(
                        f"[{self.provider_name}] Using storage type config as fallback"
                    )

            # Add provider name if not present
            if "provider" not in config_data:
                config_data["provider"] = self.provider_name

            # Check if provider is configured and enabled
            if not self.configuration.is_provider_configured(self.provider_name):
                self._logger.warning(
                    f"[{self.provider_name}] Provider is not properly configured or disabled"
                )

            config = StorageConfig.from_dict(config_data)
            self._logger.debug(
                f"[{self.provider_name}] Loaded configuration using StorageConfigService"
            )
            return config
        except Exception as e:
            self._logger.error(
                f"[{self.provider_name}] Failed to load configuration: {e}"
            )
            # Return minimal config to prevent startup failures
            return StorageConfig(provider=self.provider_name)

    # Template method pattern for client initialization
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

    # Error handling helper
    def _handle_error(self, operation: str, error: Exception, **context) -> None:
        """
        Handle storage operation errors consistently.

        Args:
            operation: The operation that failed
            error: The exception that occurred
            **context: Additional context for error reporting
        """
        error_msg = f"Storage {operation} failed for {self.provider_name}: {str(error)}"
        self._logger.error(f"[{self.provider_name}] {error_msg}")

        # Add context to error if available
        if context:
            context_str = ", ".join(f"{k}={v}" for k, v in context.items())
            error_msg += f" (Context: {context_str})"

        # Raise appropriate exception type
        if isinstance(error, StorageServiceError):
            raise error
        else:
            raise StorageProviderError(error_msg) from error

    def _create_error_result(
        self, operation: str, error: str, **context
    ) -> StorageResult:
        """
        Create a standardized error result.

        Args:
            operation: The operation that failed
            error: Error message
            **context: Additional context

        Returns:
            StorageResult with error information
        """
        return StorageResult(success=False, operation=operation, error=error, **context)

    def _create_success_result(self, operation: str, **context) -> StorageResult:
        """
        Create a standardized success result.

        Args:
            operation: The operation that succeeded
            **context: Additional context

        Returns:
            StorageResult with success information
        """
        return StorageResult(success=True, operation=operation, **context)

    # Default implementations for optional methods
    def list_collections(self) -> List[str]:
        """
        List all available collections.

        Default implementation returns empty list.
        Subclasses should override if they support collection listing.

        Returns:
            List of collection names/identifiers
        """
        self._logger.debug(f"[{self.provider_name}] list_collections not implemented")
        return []

    def create_collection(
        self, collection: str, schema: Optional[Dict[str, Any]] = None
    ) -> StorageResult:
        """
        Create a new collection (if supported by provider).

        Default implementation returns not-supported error.
        Subclasses should override if they support collection creation.

        Args:
            collection: Collection name/identifier
            schema: Optional schema definition

        Returns:
            StorageResult with creation details
        """
        self._logger.debug(f"[{self.provider_name}] create_collection not supported")
        return self._create_error_result(
            "create_collection",
            f"Collection creation not supported by {self.provider_name}",
            collection=collection,
        )

    def count(self, collection: str, query: Optional[Dict[str, Any]] = None) -> int:
        """
        Count documents/records in collection.

        Default implementation returns 0.
        Subclasses should override with actual counting logic.

        Args:
            collection: Collection/table/file identifier
            query: Optional query parameters for filtering

        Returns:
            Number of matching documents/records
        """
        self._logger.debug(f"[{self.provider_name}] count not implemented")
        return 0

    def exists(self, collection: str, document_id: Optional[str] = None) -> bool:
        """
        Check if collection or document exists in storage.

        Default implementation returns False.
        Subclasses should override with actual existence checking.

        Args:
            collection: Collection/table/file identifier
            document_id: Optional specific document/record ID

        Returns:
            True if exists, False otherwise
        """
        self._logger.debug(f"[{self.provider_name}] exists not implemented")
        return False

    # Abstract methods that must be implemented by subclasses
    @abstractmethod
    def _initialize_client(self) -> Any:
        """
        Initialize the storage client.

        This method must be implemented by subclasses to set up
        their specific client connection.

        Returns:
            Storage client instance
        """

    @abstractmethod
    def _perform_health_check(self) -> bool:
        """
        Perform provider-specific health check.

        This method must be implemented by subclasses to check
        if their storage backend is accessible and healthy.

        Returns:
            True if healthy, False otherwise
        """

    @abstractmethod
    def read(
        self,
        collection: str,
        document_id: Optional[str] = None,
        query: Optional[Dict[str, Any]] = None,
        path: Optional[str] = None,
        **kwargs,
    ) -> Any:
        """
        Read data from storage.

        This method must be implemented by subclasses with
        provider-specific read logic.

        Args:
            collection: Collection/table/file identifier
            document_id: Optional specific document/record ID
            query: Optional query parameters for filtering
            path: Optional path within document (for nested data)
            **kwargs: Provider-specific parameters

        Returns:
            Data from storage
        """

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
        """
        Write data to storage.

        This method must be implemented by subclasses with
        provider-specific write logic.

        Args:
            collection: Collection/table/file identifier
            data: Data to write
            document_id: Optional specific document/record ID
            mode: Write mode (write, append, update, etc.)
            path: Optional path within document (for nested updates)
            **kwargs: Provider-specific parameters

        Returns:
            StorageResult with operation details
        """

    @abstractmethod
    def delete(
        self,
        collection: str,
        document_id: Optional[str] = None,
        path: Optional[str] = None,
        **kwargs,
    ) -> StorageResult:
        """
        Delete from storage.

        This method must be implemented by subclasses with
        provider-specific delete logic.

        Args:
            collection: Collection/table/file identifier
            document_id: Optional specific document/record ID
            path: Optional path within document (for partial deletion)
            **kwargs: Provider-specific parameters

        Returns:
            StorageResult with operation details
        """

    def batch_write(
        self,
        collection: str,
        data: List[Dict[str, Any]],
        mode: WriteMode = WriteMode.WRITE,
        **kwargs,
    ) -> StorageResult:
        """
        Write multiple documents/records in a batch operation.

        Default implementation uses individual write calls.
        Subclasses can override for optimized batch operations.

        Args:
            collection: Collection/table/file identifier
            data: List of data items to write
            mode: Write mode for all items
            **kwargs: Provider-specific parameters

        Returns:
            StorageResult with batch operation details
        """
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
            error_msg = "; ".join(errors[:5])  # Limit to first 5 errors
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
