"""
Storage service manager for AgentMap.

This module provides a centralized manager for storage services,
handling provider registration, service instantiation, and lifecycle management.
"""

from typing import Any, Dict, List, Optional, Type

from agentmap.services.config.storage_config_service import StorageConfigService
from agentmap.services.file_path_service import FilePathService
from agentmap.services.logging_service import LoggingService
from agentmap.services.storage.base import BaseStorageService
from agentmap.services.storage.protocols import StorageService, StorageServiceFactory
from agentmap.services.storage.types import (
    StorageServiceConfigurationError,
    StorageServiceNotAvailableError,
)


class StorageServiceManager:
    """
    Manager for multiple storage service providers.

    Handles registration of storage providers, service instantiation,
    and provides access to storage services throughout the application.
    """

    def __init__(
        self,
        configuration: StorageConfigService,
        logging_service: LoggingService,
        file_path_service: FilePathService,
        blob_storage_service: Optional[Any] = None,
    ):
        """
        Initialize the storage service manager.

        Args:
            configuration: Storage configuration service for storage-specific config access
            logging_service: Logging service for creating loggers
            file_path_service: File path service for path validation and operations
            blob_storage_service: Optional blob storage service for cloud storage operations
        """
        self.configuration = configuration
        self.logging_service = logging_service
        self.file_path_service = file_path_service
        self._logger = logging_service.get_class_logger(self)
        self.blob_storage_service = blob_storage_service

        # Storage for services and service classes
        self._services: Dict[str, StorageService] = {}
        self._service_classes: Dict[str, Type[BaseStorageService]] = {}
        self._factories: Dict[str, StorageServiceFactory] = {}

        # Cache for default provider
        self._default_provider: Optional[str] = None

        # Auto-register available providers
        self._auto_register_providers()

        # Register blob storage if available
        self._register_blob_storage_integration()

        self._logger.info("StorageServiceManager initialized")

    def _auto_register_providers(self) -> None:
        """
        Auto-register all available storage service providers.

        This method attempts to import and register all concrete
        storage service implementations.
        """
        try:
            # Import the auto-registration function
            from agentmap.services.storage import register_all_providers

            # Register all available providers
            register_all_providers(self)

            self._logger.info("Auto-registered storage service providers")
        except ImportError as e:
            self._logger.warning(f"Could not auto-register providers: {e}")
        except Exception as e:
            self._logger.error(f"Error during auto-registration: {e}")

    def register_provider(
        self, provider_name: str, service_class: Type[BaseStorageService]
    ) -> None:
        """
        Register a storage service provider.

        Args:
            provider_name: Name of the provider (e.g., "csv", "json", "firebase")
            service_class: Class that implements the storage service

        Raises:
            StorageServiceConfigurationError: If provider_name is invalid or service_class is invalid
        """
        # Validate provider name
        if (
            not provider_name
            or not isinstance(provider_name, str)
            or not provider_name.strip()
        ):
            raise StorageServiceConfigurationError(
                "Provider name must be a non-empty string"
            )

        if not issubclass(service_class, BaseStorageService):
            raise StorageServiceConfigurationError(
                f"Service class for {provider_name} must inherit from BaseStorageService"
            )

        self._service_classes[provider_name] = service_class
        self._logger.info(f"Registered storage provider: {provider_name}")

    def register_factory(
        self, provider_name: str, factory: StorageServiceFactory
    ) -> None:
        """
        Register a storage service factory.

        Args:
            provider_name: Name of the provider
            factory: Factory instance for creating services

        Raises:
            StorageServiceConfigurationError: If provider_name is invalid
        """
        # Validate provider name
        if (
            not provider_name
            or not isinstance(provider_name, str)
            or not provider_name.strip()
        ):
            raise StorageServiceConfigurationError(
                "Provider name must be a non-empty string"
            )

        self._factories[provider_name] = factory
        self._logger.info(f"Registered storage factory: {provider_name}")

    def get_service(self, provider_name: str) -> StorageService:
        """
        Get or create a storage service instance.

        Args:
            provider_name: Name of the provider

        Returns:
            StorageService instance

        Raises:
            StorageServiceNotAvailableError: If provider is not registered
            StorageServiceConfigurationError: If service creation fails
        """
        # Return cached service if available
        if provider_name in self._services:
            return self._services[provider_name]

        # Try to create service from registered class
        if provider_name in self._service_classes:
            return self._create_service_from_class(provider_name)

        # Try to create service from factory
        if provider_name in self._factories:
            return self._create_service_from_factory(provider_name)

        # Provider not found
        available_providers = self.list_available_providers()
        raise StorageServiceNotAvailableError(
            f"Storage provider '{provider_name}' is not registered. "
            f"Available providers: {', '.join(available_providers)}"
        )

    def _create_service_from_class(self, provider_name: str) -> StorageService:
        """
        Create a service instance from a registered class.

        Args:
            provider_name: Name of the provider

        Returns:
            StorageService instance
        """
        try:
            service_class = self._service_classes[provider_name]

            # Get base directory from storage configuration (reads from storage.yaml)
            base_directory = self.configuration.get_base_directory()

            service = service_class(
                provider_name,
                self.configuration,
                self.logging_service,
                base_directory=base_directory,
                file_path_service=self.file_path_service,
            )

            # Cache the service
            self._services[provider_name] = service

            self._logger.info(f"Created storage service: {provider_name}")
            return service

        except Exception as e:
            self._logger.error(f"Failed to create storage service {provider_name}: {e}")
            raise StorageServiceConfigurationError(
                f"Failed to create storage service for {provider_name}: {str(e)}"
            ) from e

    def _create_service_from_factory(self, provider_name: str) -> StorageService:
        """
        Create a service instance from a factory.

        Args:
            provider_name: Name of the provider

        Returns:
            StorageService instance
        """
        try:
            factory = self._factories[provider_name]
            # Use storage-specific configuration methods instead of generic access
            config_data = self.configuration.get_provider_config(provider_name)

            service = factory.create_service(provider_name, config_data)

            # Cache the service
            self._services[provider_name] = service

            self._logger.info(f"Created storage service from factory: {provider_name}")
            return service

        except Exception as e:
            self._logger.error(
                f"Failed to create storage service {provider_name} from factory: {e}"
            )
            raise StorageServiceConfigurationError(
                f"Failed to create storage service for {provider_name} from factory: {str(e)}"
            ) from e

    def get_default_service(self) -> StorageService:
        """
        Get the default storage service.

        Returns:
            Default StorageService instance
        """
        if self._default_provider is None:
            # Determine default provider using storage-specific logic
            if self.configuration.is_csv_storage_enabled():
                self._default_provider = "csv"
            elif self.configuration.is_vector_storage_enabled():
                self._default_provider = self.configuration.get_default_provider(
                    "vector"
                )
            elif self.configuration.is_kv_storage_enabled():
                self._default_provider = self.configuration.get_default_provider("kv")
            else:
                # Fallback to CSV as most basic storage
                self._default_provider = "csv"
                self._logger.warning(
                    "No storage types enabled, falling back to CSV provider"
                )

        return self.get_service(self._default_provider)

    def list_available_providers(self) -> List[str]:
        """
        List all available storage providers.

        Returns:
            List of provider names
        """
        providers = set()
        providers.update(self._service_classes.keys())
        providers.update(self._factories.keys())

        # Include blob storage if available
        if self.is_blob_storage_enabled():
            providers.add("blob")

        return sorted(list(providers))

    def is_provider_available(self, provider_name: str) -> bool:
        """
        Check if a storage provider is available.

        Args:
            provider_name: Name of the provider

        Returns:
            True if provider is available
        """
        if provider_name == "blob":
            return self.is_blob_storage_enabled()

        return (
            provider_name in self._service_classes or provider_name in self._factories
        )

    def health_check(self, provider_name: Optional[str] = None) -> Dict[str, bool]:
        """
        Perform health check on storage services.

        Args:
            provider_name: Optional specific provider to check.
                         If None, checks all registered providers.

        Returns:
            Dictionary mapping provider names to health status
        """
        results = {}

        if provider_name:
            # Check specific provider
            providers_to_check = [provider_name]
        else:
            # Check all available providers
            providers_to_check = self.list_available_providers()

        for provider in providers_to_check:
            try:
                service = self.get_service(provider)
                results[provider] = service.health_check()
            except Exception as e:
                self._logger.error(f"Health check failed for {provider}: {e}")
                results[provider] = False

        return results

    def clear_cache(self, provider_name: Optional[str] = None) -> None:
        """
        Clear cached services.

        Args:
            provider_name: Optional specific provider to clear.
                         If None, clears all cached services.
        """
        if provider_name:
            if provider_name in self._services:
                del self._services[provider_name]
                self._logger.info(
                    f"Cleared cache for storage provider: {provider_name}"
                )
        else:
            self._services.clear()
            self._logger.info("Cleared all storage service caches")

    def get_service_info(self, provider_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get information about storage services.

        Args:
            provider_name: Optional specific provider to get info for.
                         If None, returns info for all providers.

        Returns:
            Dictionary with service information
        """
        if provider_name:
            providers_to_check = [provider_name]
        else:
            providers_to_check = self.list_available_providers()
            # Include blob storage in the list if available
            if self.is_blob_storage_enabled() and "blob" not in providers_to_check:
                providers_to_check.append("blob")

        info = {}

        for provider in providers_to_check:
            if provider == "blob":
                # Special handling for blob storage
                provider_info = {
                    "available": self.is_blob_storage_enabled(),
                    "cached": True,  # Blob storage is always cached when available
                    "type": "blob_service",
                }
                # Add health status for blob storage
                if self.blob_storage_service:
                    try:
                        provider_info["healthy"] = (
                            self.blob_storage_service.health_check()
                        )
                    except Exception:
                        provider_info["healthy"] = False
            else:
                provider_info = {
                    "available": self.is_provider_available(provider),
                    "cached": provider in self._services,
                    "type": "class" if provider in self._service_classes else "factory",
                }

                # Add health status if service is cached
                if provider in self._services:
                    try:
                        provider_info["healthy"] = self._services[
                            provider
                        ].health_check()
                    except Exception:
                        provider_info["healthy"] = False

            info[provider] = provider_info

        return info

    def _register_blob_storage_integration(self) -> None:
        """
        Register blob storage service integration if available.

        This allows the storage manager to provide access to blob storage
        capabilities through the standard storage service interface.
        """
        if self.blob_storage_service is not None:
            # Register blob storage as a special service type
            self._services["blob"] = self.blob_storage_service
            self._logger.info("Blob storage service integrated with storage manager")
        else:
            self._logger.info(
                "Blob storage service not available - blob operations disabled"
            )

    def is_blob_storage_enabled(self) -> bool:
        """
        Check if blob storage capabilities are available.

        Returns:
            True if blob storage service is available
        """
        return self.blob_storage_service is not None

    def get_blob_storage_service(self) -> Optional[Any]:
        """
        Get the blob storage service if available.

        Returns:
            Blob storage service instance or None if not available
        """
        return self.blob_storage_service

    def shutdown(self) -> None:
        """
        Shutdown all storage services and clean up resources.
        """
        self._logger.info("Shutting down storage service manager")

        # Clear all caches
        self.clear_cache()

        # Clear registrations
        self._service_classes.clear()
        self._factories.clear()

        # Clear blob storage reference
        self.blob_storage_service = None

        self._logger.info("Storage service manager shutdown complete")
