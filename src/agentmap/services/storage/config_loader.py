"""
Configuration loader mixin for storage services.

This module provides configuration loading functionality that can be mixed into
storage services to handle provider-specific configuration loading.
"""

from typing import Any

from agentmap.services.storage.types import StorageConfig


class ConfigLoaderMixin:
    """
    Mixin class providing configuration loading functionality for storage services.

    This mixin handles:
    - Loading provider-specific configuration
    - Falling back to storage type configs
    - Creating minimal configs on failure

    Expected attributes on the class using this mixin:
    - provider_name: str
    - configuration: StorageConfigService
    - _logger: Logger instance
    """

    # Type hints for attributes expected from the base class
    provider_name: str
    configuration: Any
    _logger: Any

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
            config_data = self._get_provider_config_data()
            config_data = self._apply_fallback_config(config_data)
            config_data = self._ensure_provider_name(config_data)
            self._check_provider_status()

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

    def _get_provider_config_data(self) -> dict:
        """
        Get provider configuration data from the configuration service.

        Returns:
            Configuration dictionary for the provider
        """
        # Use storage-specific configuration methods instead of generic access
        if self.provider_name in ["firebase", "mongodb", "supabase", "local"]:
            # Use named provider methods for known providers
            method_name = f"get_{self.provider_name}_config"
            if hasattr(self.configuration, method_name):
                return getattr(self.configuration, method_name)()
            else:
                return self.configuration.get_provider_config(self.provider_name)
        else:
            # Use generic provider method for other providers
            return self.configuration.get_provider_config(self.provider_name)

    def _apply_fallback_config(self, config_data: dict) -> dict:
        """
        Apply fallback configuration if provider config is empty.

        Args:
            config_data: Current configuration data

        Returns:
            Configuration data with fallback applied if needed
        """
        storage_type_providers = ["csv", "vector", "memory", "file", "kv", "blob", "json"]

        if not config_data and self.provider_name in storage_type_providers:
            storage_type_method = f"get_{self.provider_name}_config"
            if hasattr(self.configuration, storage_type_method):
                config_data = getattr(self.configuration, storage_type_method)()
                self._logger.debug(
                    f"[{self.provider_name}] Using storage type config as fallback"
                )

        return config_data or {}

    def _ensure_provider_name(self, config_data: dict) -> dict:
        """
        Ensure provider name is present in configuration data.

        Args:
            config_data: Configuration data

        Returns:
            Configuration data with provider name
        """
        if "provider" not in config_data:
            config_data["provider"] = self.provider_name
        return config_data

    def _check_provider_status(self) -> None:
        """
        Check if the provider is properly configured and log warning if not.
        """
        if not self.configuration.is_provider_configured(self.provider_name):
            self._logger.warning(
                f"[{self.provider_name}] Provider is not properly configured or disabled"
            )


__all__ = ["ConfigLoaderMixin"]
