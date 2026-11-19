# agentmap/logging/service.py
"""
Centralized logging service for dependency injection.

Provides DI-only access to logging throughout the application. This is the
ONLY way to get loggers in the application - no helper methods or bypasses allowed.
"""

import logging
import logging.config
from typing import Any, Dict, Optional, cast

from agentmap.exceptions.service_exceptions import LoggingNotConfiguredException

# Define custom TRACE level
TRACE_LEVEL = 5
setattr(logging, "TRACE", TRACE_LEVEL)
logging.addLevelName(TRACE_LEVEL, "TRACE")


def _trace_method(
    logger: logging.Logger, message: object, *args: Any, **kwargs: Any
) -> None:
    """Log a message at the custom TRACE level."""
    if logger.isEnabledFor(TRACE_LEVEL):
        logger._log(TRACE_LEVEL, message, args, **kwargs)


class TraceLogger(logging.Logger):
    """Typing view for standard loggers extended with the TRACE method."""

    def trace(self, message: object, *args: Any, **kwargs: Any) -> None:
        _trace_method(self, message, *args, **kwargs)


setattr(logging.Logger, "trace", _trace_method)


def trace(message: object, *args: Any, **kwargs: Any) -> None:
    """Log a message at TRACE on the root logger."""
    _trace_method(logging.getLogger(), message, *args, **kwargs)


setattr(logging, "trace", trace)


class LoggingService:
    """
    Centralized logging service for dependency injection.

    This is the ONLY way to get loggers in the application. All logging
    access must go through this service via dependency injection.

    Key principles:
    - No helper methods or global functions that bypass DI
    - Explicit initialization required before use
    - Raises exceptions if used before initialization
    - Supports service patterns used throughout the codebase
    """

    def __init__(self, configuration: Optional[Dict[str, Any]] = None):
        """
        Initialize LoggingService with configuration.

        Args:
            configuration: Logging configuration dictionary for dictConfig
        """
        self._configuration = configuration or {}
        self._initialized = False
        self._logger_cache: Dict[str, TraceLogger] = {}

    def initialize(self) -> None:
        """
        Initialize logging configuration.

        Must be called before any logging operations. Typically called
        during DI container initialization.
        """
        if self._initialized:
            return

        try:
            if self._configuration:
                # Add TRACE support to internal mappings before applying dictConfig
                logging._nameToLevel["TRACE"] = TRACE_LEVEL
                logging._levelToName[TRACE_LEVEL] = "TRACE"
                logging.config.dictConfig(self._configuration)
            else:
                # Minimal default configuration if no config provided
                logging.basicConfig(
                    level=logging.INFO, format="[%(levelname)s] %(name)s: %(message)s"
                )
        except Exception as e:
            # If configuration fails, fall back to basic config
            logging.basicConfig(
                level=logging.INFO, format="[%(levelname)s] %(name)s: %(message)s"
            )
            # Log the configuration error using the basic setup
            logger = logging.getLogger(__name__)
            logger.warning(f"Logging configuration failed, using basic setup: {e}")

        self._initialized = True

    def get_logger(self, name: Optional[str] = None) -> TraceLogger:
        """
        Get a logger instance with the given name.

        Args:
            name: Logger name (defaults to calling module if None)

        Returns:
            Logger instance

        Raises:
            LoggingNotConfiguredException: If service not initialized
        """
        if not self._initialized:
            raise LoggingNotConfiguredException(
                "LoggingService not initialized. Call initialize() first or check DI configuration."
            )

        logger_name = name or __name__

        # Cache loggers for efficiency
        if logger_name not in self._logger_cache:
            self._logger_cache[logger_name] = cast(
                TraceLogger, logging.getLogger(logger_name)
            )

        return self._logger_cache[logger_name]

    def get_class_logger(self, instance: object) -> TraceLogger:
        """
        Get a logger for a class instance using module.ClassName pattern.

        This method matches the pattern used throughout the codebase where
        services get loggers based on their class and module location.

        Args:
            instance: Class instance to create logger name from

        Returns:
            Logger instance with name based on class module and name

        Raises:
            LoggingNotConfiguredException: If service not initialized
        """
        if not self._initialized:
            raise LoggingNotConfiguredException(
                "LoggingService not initialized. Call initialize() first or check DI configuration."
            )

        # Create logger name from class module and name
        class_module = instance.__class__.__module__
        class_name = instance.__class__.__name__
        logger_name = f"{class_module}.{class_name}"

        # Cache loggers for efficiency
        if logger_name not in self._logger_cache:
            self._logger_cache[logger_name] = cast(
                TraceLogger, logging.getLogger(logger_name)
            )

        return self._logger_cache[logger_name]

    def get_module_logger(self, module_name: str) -> TraceLogger:
        """
        Get a logger for a specific module.

        Args:
            module_name: Module name for the logger

        Returns:
            Logger instance for the module

        Raises:
            LoggingNotConfiguredException: If service not initialized
        """
        if not self._initialized:
            raise LoggingNotConfiguredException(
                "LoggingService not initialized. Call initialize() first or check DI configuration."
            )

        # Cache loggers for efficiency
        if module_name not in self._logger_cache:
            self._logger_cache[module_name] = cast(
                TraceLogger, logging.getLogger(module_name)
            )

        return self._logger_cache[module_name]

    def is_initialized(self) -> bool:
        """
        Check if the logging service has been initialized.

        Returns:
            True if initialized, False otherwise
        """
        return self._initialized

    def reset(self) -> None:
        """
        Reset logging configuration and clear caches.

        Primarily used for testing to ensure clean state between tests.
        """
        # Clear all handlers from cached loggers
        for logger in self._logger_cache.values():
            for handler in list(logger.handlers):
                logger.removeHandler(handler)
                handler.close()

        # Clear the cache
        self._logger_cache.clear()

        # Reset root logger
        root_logger = logging.getLogger()
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)
            handler.close()

        # Reset initialization state
        self._initialized = False

        # Reset logging level and format to defaults
        logging.basicConfig(level=logging.WARNING, force=True)

    def get_effective_level(self, logger_name: Optional[str] = None) -> int:
        """
        Get the effective logging level for a logger.

        Args:
            logger_name: Logger name (uses root logger if None)

        Returns:
            Effective logging level as integer

        Raises:
            LoggingNotConfiguredException: If service not initialized
        """
        if not self._initialized:
            raise LoggingNotConfiguredException(
                "LoggingService not initialized. Call initialize() first or check DI configuration."
            )

        logger = logging.getLogger(logger_name)
        return logger.getEffectiveLevel()

    def set_level(self, level: int, logger_name: Optional[str] = None) -> None:
        """
        Set logging level for a specific logger or root logger.

        Args:
            level: Logging level (from logging module constants)
            logger_name: Logger name (uses root logger if None)

        Raises:
            LoggingNotConfiguredException: If service not initialized
        """
        if not self._initialized:
            raise LoggingNotConfiguredException(
                "LoggingService not initialized. Call initialize() first or check DI configuration."
            )

        logger = logging.getLogger(logger_name)
        logger.setLevel(level)

        # Update cache if logger is cached
        if logger_name and logger_name in self._logger_cache:
            self._logger_cache[logger_name] = cast(TraceLogger, logger)

    def get_service_info(self) -> Dict[str, Any]:
        """
        Get information about the logging service for debugging.

        Returns:
            Dictionary with service status and configuration info
        """
        return {
            "initialized": self._initialized,
            "cached_loggers": list(self._logger_cache.keys()),
            "cached_logger_count": len(self._logger_cache),
            "has_configuration": bool(self._configuration),
            "root_logger_level": logging.getLogger().getEffectiveLevel(),
            "root_logger_handlers": [
                type(h).__name__ for h in logging.getLogger().handlers
            ],
        }


def _get_logger_from_di(name: Optional[str] = None) -> TraceLogger:
    try:
        from agentmap.runtime.runtime_manager import RuntimeManager

        if RuntimeManager.is_initialized():
            logging_service = RuntimeManager.get_container().logging_service()
            return cast(TraceLogger, logging_service.get_logger(name or __name__))
    except Exception:
        pass

    import logging

    return cast(TraceLogger, logging.getLogger(name or __name__))


def _get_bootstrap_logger(name: Optional[str] = None) -> TraceLogger:
    logger_name = f"bootstrap.{name or __name__}"
    return cast(TraceLogger, logging.getLogger(logger_name))
