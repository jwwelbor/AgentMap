"""Base configuration manager with shared utilities."""

import logging
from typing import Any, Dict, Optional, TypeVar

from agentmap.services.config.config_service import ConfigService

T = TypeVar("T")


class BaseConfigManager:
    """
    Base configuration manager with shared utilities.

    Provides common functionality for specialized configuration managers.
    """

    def __init__(
        self,
        config_service: ConfigService,
        config_data: Dict[str, Any],
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize base configuration manager.

        Args:
            config_service: ConfigService instance for infrastructure operations
            config_data: Loaded configuration data
            logger: Logger instance for logging
        """
        self._config_service = config_service
        self._config_data = config_data
        self._logger = logger or logging.getLogger(__name__)

    def get_section(self, section: str, default: T = None) -> Dict[str, Any]:
        """Get a configuration section."""
        return self._config_data.get(section, default)

    def get_value(self, path: str, default: T = None) -> T:
        """Get a specific configuration value using dot notation."""
        return self._config_service.get_value_from_config(
            self._config_data, path, default
        )

    def _merge_with_defaults(
        self, config: Dict[str, Any], defaults: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Recursively merge configuration with defaults.

        Args:
            config: User configuration
            defaults: Default configuration

        Returns:
            Merged configuration
        """
        result = defaults.copy()

        for key, value in config.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._merge_with_defaults(value, result[key])
            else:
                result[key] = value

        return result
