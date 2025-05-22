# agentmap/logging/service.py
from typing import Any, Dict, Optional
import logging
from pathlib import Path

from agentmap.logging.logger import get_logger, configure_logging, TRACE
from agentmap.logging.manager import LoggerManager


class LoggingService:
    """
    Centralized logging service that can be injected via DI.

    This service manages logger configuration and provides a consistent
    interface for getting loggers throughout the application.
    """

    def __init__(self, logging_config: Dict[str, Any]):
        """
        Initialize the logging service with configuration.

        Args:
            logging_config: Logging configuration dictionary
        """
        self.config = logging_config
        self._initialized = False
        self._manager = LoggerManager()

    def initialize(self):
        """Initialize the logging system with the provided configuration."""
        if self._initialized:
            return

        # Configure the global logging system
        configure_logging(self.config)
        self._initialized = True

    def get_logger(self, name: str = "AgentMap", **kwargs) -> logging.Logger:
        """
        Get a logger with the specified name and configuration.

        Args:
            name: Logger name
            **kwargs: Additional logger configuration

        Returns:
            Configured logger instance
        """
        # Ensure logging is initialized
        if not self._initialized:
            self.initialize()

        # Get logger from the manager
        logger = self._manager.get_logger(name, **kwargs)

        # Apply any service-level configuration
        self._apply_service_config(logger)

        return logger

    def _apply_service_config(self, logger: logging.Logger):
        """Apply service-level configuration to a logger."""
        # Set level from config if specified
        level_name = self.config.get("level", "INFO").upper()
        if level_name == "TRACE":
            level = TRACE
        else:
            level = getattr(logging, level_name, logging.INFO)

        if logger.level == logging.NOTSET or logger.level > level:
            logger.setLevel(level)

    def get_class_logger(self, obj: Any) -> logging.Logger:
        """
        Get a logger for a class instance.

        Args:
            obj: Class instance

        Returns:
            Logger with name based on the class
        """
        class_name = obj.__class__.__name__
        module_name = obj.__class__.__module__
        logger_name = f"{module_name}.{class_name}"
        return self.get_logger(logger_name)

    def set_level(self, name: str, level: str):
        """
        Set the level for a specific logger.

        Args:
            name: Logger name
            level: Log level (DEBUG, INFO, WARNING, ERROR, TRACE)
        """
        logger = self.get_logger(name)

        if level.upper() == "TRACE":
            logger.setLevel(TRACE)
        else:
            logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    def reset(self):
        """Reset the logging system (useful for testing)."""
        self._manager.reset()
        self._initialized = False