# agentmap/logging/logger_utils.py
import logging
import os
import threading
from typing import Dict, Optional, Set

# Track loggers that have been configured to prevent duplicate configuration
_CONFIGURED_LOGGERS: Set[str] = set()
_LOGGER_LOCK = threading.RLock()

def ensure_unique_handlers(logger):
    """
    Ensure logger has no duplicate handlers by checking handler identities.
    
    Args:
        logger: Logger instance to check
    """
    with _LOGGER_LOCK:
        # Use a set to detect duplicate handler types
        handler_types = set()
        handlers_to_remove = []
        
        for handler in logger.handlers:
            handler_id = (type(handler), getattr(handler, 'baseFilename', None), 
                         getattr(handler, 'stream', None))
            
            if handler_id in handler_types:
                # This is a duplicate handler
                handlers_to_remove.append(handler)
            else:
                handler_types.add(handler_id)
        
        # Remove any duplicate handlers
        for handler in handlers_to_remove:
            logger.removeHandler(handler)

def get_clean_logger(name, propagate=True):
    """
    Get a logger with unique handlers that won't cause duplicate logs.
    
    Args:
        name: Logger name
        propagate: Whether this logger should propagate to parent loggers
        
    Returns:
        Configured logger with unique handlers
    """
    with _LOGGER_LOCK:
        logger = logging.getLogger(name)
        logger.propagate = propagate
        
        # Remove duplicate handlers if any exist
        ensure_unique_handlers(logger)
        
        # Return the cleaned logger
        return logger

def configure_basic_logger(logger, level=None, formatter=None):
    """
    Configure a basic logger with a console handler if it has no handlers.
    
    Args:
        logger: Logger instance to configure
        level: Optional log level to set
        formatter: Optional formatter to use
    """
    with _LOGGER_LOCK:
        logger_name = logger.name
        
        # Only configure once
        if logger_name in _CONFIGURED_LOGGERS:
            return
        
        # Mark as configured
        _CONFIGURED_LOGGERS.add(logger_name)
        
        # Only add handler if none exist
        if not logger.handlers:
            # Create console handler
            console_handler = logging.StreamHandler()
            
            # Use provided formatter or create a default one
            if formatter is None:
                formatter = logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
            
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        
        # Set log level if provided
        if level is not None:
            logger.setLevel(level)

def fix_root_logger():
    """Fix the root logger to prevent duplicate logging."""
    root_logger = logging.getLogger()
    
    # If root logger has multiple StreamHandlers, remove duplicates
    stream_handlers = [h for h in root_logger.handlers if isinstance(h, logging.StreamHandler)]
    
    if len(stream_handlers) > 1:
        # Keep only the first stream handler
        for handler in stream_handlers[1:]:
            root_logger.removeHandler(handler)

def debug_loggers():
    """Return debugging information about all loggers."""
    result = {}
    root = logging.getLogger()
    
    # Get root logger info
    result["root"] = {
        "level": logging.getLevelName(root.level),
        "handlers": [type(h).__name__ for h in root.handlers],
        "disabled": root.disabled,
        "propagate": root.propagate
    }
    
    # Find all loggers
    manager = root.manager
    for logger_name in manager.loggerDict:
        logger = logging.getLogger(logger_name)
        result[logger_name] = {
            "level": logging.getLevelName(logger.level),
            "handlers": [type(h).__name__ for h in logger.handlers],
            "disabled": logger.disabled,
            "propagate": logger.propagate
        }
    
    return result