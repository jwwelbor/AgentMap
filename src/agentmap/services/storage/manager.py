"""
Storage service manager for AgentMap.

This module provides a centralized manager for storage services,
handling provider registration, service instantiation, and lifecycle management.
"""

from typing import Any, Dict, List, Optional, Type

from agentmap.services.config.app_config_service import AppConfigService
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
        self, configuration: AppConfigService, logging_service: LoggingService
    ):
        """
        Initialize the storage service manager.

        Args:
            configuration: Application configuration service
            logging_service: Logging service for creating loggers
        """
        self.configuration = configuration
        self.logging_service = logging_service
        self._logger = logging_service.get_class_logger(self)

        # Storage for services and service classes
        self._services: Dict[str, StorageService] = {}
        self._service_classes: Dict[str, Type[BaseStorageService]] = {}
        self._factories: Dict[str, StorageServiceFactory] = {}

        # Cache for default provider
        self._default_provider: Optional[str] = None

        # Auto-register available providers
        self._auto_register_providers()

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
            service = service_class(
                provider_name, self.configuration, self.logging_service
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
            config_data = self.configuration.get_value(f"storage.{provider_name}", {})

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
            self._default_provider = self.configuration.get_value(
                "storage.default_provider",
                "csv",  # Fallback to CSV as it's most commonly available
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
        return sorted(list(providers))

    def is_provider_available(self, provider_name: str) -> bool:
        """
        Check if a storage provider is available.

        Args:
            provider_name: Name of the provider

        Returns:
            True if provider is available
        """
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

        info = {}

        for provider in providers_to_check:
            provider_info = {
                "available": self.is_provider_available(provider),
                "cached": provider in self._services,
                "type": "class" if provider in self._service_classes else "factory",
            }

            # Add health status if service is cached
            if provider in self._services:
                try:
                    provider_info["healthy"] = self._services[provider].health_check()
                except Exception:
                    provider_info["healthy"] = False

            info[provider] = provider_info

        return info

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

        self._logger.info("Storage service manager shutdown complete")
