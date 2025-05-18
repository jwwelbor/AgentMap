# agentmap/logging/manager.py - New file
import logging
import threading
import weakref
from typing import Dict, Optional, Set, Any, List
import os
import hashlib


class LoggerManager:
    """
    Thread-safe singleton manager for all loggers in the application.
    Prevents duplicate handlers and ensures consistent configuration.
    """
    _instance = None
    _lock = threading.RLock()
    _initialized = False
    _loggers = weakref.WeakValueDictionary()  # Use weak refs to avoid memory leaks
    _configured_loggers = set()
    _handler_fingerprints = set()  # For deduplication

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(LoggerManager, cls).__new__(cls)
                cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize the manager."""
        self._initialized = True

        # Configure root logger to prevent default handler creation
        root_logger = logging.getLogger()
        if not root_logger.handlers:
            null_handler = logging.NullHandler()
            root_logger.addHandler(null_handler)

        # Fix existing loggers
        self._fix_existing_loggers()

    def _fix_existing_loggers(self):
        """Fix any loggers that already exist."""
        root = logging.getLogger()

        # Fix root logger
        self._remove_duplicate_handlers(root)

        # Fix all other existing loggers
        for name in list(root.manager.loggerDict.keys()):
            logger = logging.getLogger(name)
            self._remove_duplicate_handlers(logger)

            # Add to our registry
            self._loggers[name] = logger

    def _get_handler_fingerprint(self, handler):
        """Generate a unique fingerprint for a handler."""
        handler_type = type(handler).__name__
        formatter = getattr(handler, 'formatter', None)
        fmt_string = getattr(formatter, '_fmt', '') if formatter else ''
        level = getattr(handler, 'level', logging.NOTSET)

        # For file handlers
        filename = getattr(handler, 'baseFilename', None)

        # For stream handlers
        stream_name = 'unknown'
        stream = getattr(handler, 'stream', None)
        if stream:
            if hasattr(stream, 'name'):
                stream_name = stream.name
            elif stream in (sys.stdout, sys.__stdout__):
                stream_name = '<stdout>'
            elif stream in (sys.stderr, sys.__stderr__):
                stream_name = '<stderr>'

        # Create fingerprint
        fingerprint = f"{handler_type}:{level}:{fmt_string}:{filename}:{stream_name}"
        return fingerprint

    def _remove_duplicate_handlers(self, logger):
        """Remove any duplicate handlers from a logger."""
        fingerprints = set()
        handlers_to_remove = []

        for handler in logger.handlers:
            fingerprint = self._get_handler_fingerprint(handler)
            if fingerprint in fingerprints:
                handlers_to_remove.append(handler)
            else:
                fingerprints.add(fingerprint)

        # Remove duplicate handlers
        for handler in handlers_to_remove:
            logger.removeHandler(handler)

    def get_logger(self, name: str, **kwargs) -> logging.Logger:
        """
        Get a logger with guaranteed unique handlers.

        Args:
            name: Logger name
            **kwargs: Additional configuration options
                - propagate: Whether to propagate to parent (default: True)
                - level: Log level (default: None - inherit)

        Returns:
            Configured logger
        """
        with self._lock:
            # Return cached logger if available
            if name in self._loggers:
                logger = self._loggers[name]
                self._remove_duplicate_handlers(logger)  # Extra safety check
                return logger

            # Create new logger
            logger = logging.getLogger(name)

            # Configure propagation
            propagate = kwargs.get('propagate', True)
            logger.propagate = propagate

            # Set level if provided
            level = kwargs.get('level')
            if level is not None:
                logger.setLevel(level)

            # Ensure no duplicate handlers
            self._remove_duplicate_handlers(logger)

            # Store in registry
            self._loggers[name] = logger
            return logger

    def configure_logger(self, logger, **kwargs):
        """
        Configure a logger, ensuring it's only done once.

        Args:
            logger: Logger to configure
            **kwargs: Configuration options
                - level: Log level
                - format: Log format
                - handler: Handler type ('console', 'null', etc.)
                - propagate: Whether to propagate to parent
        """
        with self._lock:
            # Make sure we only configure once
            logger_id = id(logger)
            if logger_id in self._configured_loggers:
                return

            self._configured_loggers.add(logger_id)

            # Set propagation
            propagate = kwargs.get('propagate')
            if propagate is not None:
                logger.propagate = propagate

            # Set level
            level = kwargs.get('level')
            if level is not None:
                logger.setLevel(level)

            # Add handler if requested and none exist
            handler_type = kwargs.get('handler', 'console' if not logger.handlers else None)
            if handler_type:
                if handler_type == 'console':
                    handler = logging.StreamHandler()
                    format_str = kwargs.get('format', '[%(levelname)s] %(name)s: %(message)s')
                    formatter = logging.Formatter(format_str)
                    handler.setFormatter(formatter)
                    logger.addHandler(handler)
                elif handler_type == 'null':
                    handler = logging.NullHandler()
                    logger.addHandler(handler)

    def reset(self):
        """Reset the manager (mainly for testing)."""
        with self._lock:
            for name, logger in list(self._loggers.items()):
                for handler in list(logger.handlers):
                    logger.removeHandler(handler)

            self._loggers.clear()
            self._configured_loggers.clear()
            self._handler_fingerprints.clear()


# Import sys for use in _get_handler_fingerprint
import sys

# Create singleton instance
_manager = LoggerManager()


# Public API
def get_logger(name="AgentMap", **kwargs):
    """Get a logger with guaranteed unique handlers."""
    logger = _manager.get_logger(name, **kwargs)
    logger.propagate = kwargs.get('propagate', True)
    return logger


def configure_logger(logger, **kwargs):
    """Configure a logger with guaranteed unique configuration."""
    return _manager.configure_logger(logger, **kwargs)


def reset():
    """Reset all loggers (mainly for testing)."""
    return _manager.reset()