# agentmap/config/service.py
"""
Infrastructure service for loading configuration files with bootstrap logging.

Provides singleton ConfigService for efficient file loading, YAML parsing,
and configuration merging across the application.
"""
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml

from agentmap.exceptions.base_exceptions import ConfigurationException


class ConfigService:
    """
    Singleton utility service for loading configuration files with bootstrap logging.

    This service handles the infrastructure concerns of configuration loading:
    - File I/O and YAML parsing
    - Merging with defaults
    - Bootstrap logging during early initialization
    - Thread-safe singleton pattern

    Domain-specific configuration logic should be implemented in separate services
    that use this infrastructure service.
    """

    _instance = None
    _lock = threading.RLock()

    def __new__(cls):
        """Ensure only one instance exists (singleton pattern)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize the service once."""
        self._bootstrap_logger = None
        self._setup_bootstrap_logging()

    def _setup_bootstrap_logging(self):
        """Set up bootstrap logger for config loading before real logging is available."""
        # Only set up basic config if no handlers exist to avoid conflicts
        if not logging.getLogger().handlers:
            logging.basicConfig(
                level=os.environ.get("AGENTMAP_CONFIG_LOG_LEVEL", "INFO").upper(),
                format="(CONFIG-BOOTSTRAP) [%(asctime)s] %(levelname)s: %(message)s",
            )
        self._bootstrap_logger = logging.getLogger("config.bootstrap")

    def replace_logger(self, logger: logging.Logger):
        """Replace bootstrap logger with real logger once logging service is online."""
        if logger and self._bootstrap_logger:
            # Clean up bootstrap logger handlers
            for handler in list(self._bootstrap_logger.handlers):
                self._bootstrap_logger.removeHandler(handler)
            self._bootstrap_logger.propagate = False

            # Switch to real logger
            self._bootstrap_logger = logger
            self._bootstrap_logger.debug(
                "[ConfigService] Replaced bootstrap logger with real logger"
            )

    def load_config(self, config_path: Optional[Union[str, Path]]) -> Dict[str, Any]:
        """
        Load configuration from YAML file.

        Args:
            config_path: Path to config file or None for empty config

        Returns:
            Configuration dictionary (empty if no path provided)

        Raises:
            ConfigurationException: If file exists but can't be parsed
        """
        if config_path is None:
            self._bootstrap_logger.debug(
                "No config path provided, returning empty config"
            )
            return {}

        config_file = Path(config_path)
        self._bootstrap_logger.info(f"Loading configuration from: {config_file}")

        # Load user config if file exists
        if config_file.exists():
            try:
                with config_file.open() as f:
                    user_config = yaml.safe_load(f) or {}
                self._bootstrap_logger.info(
                    f"Successfully loaded configuration from {config_file}"
                )

                # Log top-level sections for visibility
                sections = list(user_config.keys())
                self._bootstrap_logger.info(
                    f"Loaded configuration sections: {sections}"
                )

                return user_config

            except Exception as e:
                error_msg = f"Failed to parse config file {config_file}: {e}"
                self._bootstrap_logger.error(error_msg)
                raise ConfigurationException(error_msg) from e
        else:
            self._bootstrap_logger.warning(
                f"Config file not found at {config_file}. Returning empty config."
            )
            return {}

    def get_value_from_config(
        self, config_data: Dict[str, Any], path: str, default: Any = None
    ) -> Any:
        """
        Get value by dot notation from provided config data.

        Args:
            config_data: Configuration dictionary to search in
            path: Dot-separated path to configuration value (e.g. "llm.openai.api_key")
            default: Default value to return if path not found

        Returns:
            Configuration value or default if not found
        """
        parts = path.split(".")
        current = config_data

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return default
        return current
