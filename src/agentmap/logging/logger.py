# agentmap/logging/logger.py
import logging
import os
from typing import Dict, Optional, Any

from agentmap.logging.logger_utils import (
    get_clean_logger,
    configure_basic_logger,
    fix_root_logger,
    debug_loggers
)

# Define custom TRACE level (lower than DEBUG)
TRACE = 5  # Lower number = more verbose
logging.addLevelName(TRACE, "TRACE")

# Add a trace method to the logger class
def trace(self, message, *args, **kwargs):
    if self.isEnabledFor(TRACE):
        self._log(TRACE, message, args, **kwargs)

# Add the method to the Logger class
logging.Logger.trace = trace

# Singleton logger instance cache
_LOGGER_REGISTRY = {}
_LOGGING_CONFIGURED = False

def get_logger(name="AgentMap"):
    """
    Get a logger with the AgentMap configuration.
    
    Args:
        name: Logger name
        
    Returns:
        Configured logger
    """
    global _LOGGER_REGISTRY
    
    # Check if logger already exists in registry
    if name in _LOGGER_REGISTRY:
        return _LOGGER_REGISTRY[name]
    
    # Get a clean logger with unique handlers
    logger = get_clean_logger(name)
    
    # Configure the logger if needed
    if not logger.handlers:
        # Get level from environment or default
        level_name = os.environ.get("AGENTMAP_LOG_LEVEL", "INFO").upper()
        try:
            level = TRACE if level_name == "TRACE" else getattr(logging, level_name, logging.INFO)
        except AttributeError:
            level = logging.INFO
        
        # Configure with basic console handler
        configure_basic_logger(logger, level=level)
    
    # Store in registry
    _LOGGER_REGISTRY[name] = logger
    
    return logger

def configure_logging(config: Optional[Dict[str, Any]] = None):
    """
    Configure logging system from configuration.
    
    Args:
        config: Logging configuration dictionary
    """
    global _LOGGING_CONFIGURED, _LOGGER_REGISTRY
    
    # Skip if already configured or config is empty
    if _LOGGING_CONFIGURED or not config:
        return
    
    # Fix root logger first to prevent duplication
    fix_root_logger()
    
    _LOGGING_CONFIGURED = True
    
    # Configure root logger
    root_logger = get_clean_logger("")  # Empty string is root logger
    
    # Set level if specified
    if "level" in config:
        level_name = config["level"].upper()
        level = TRACE if level_name == "TRACE" else getattr(logging, level_name, logging.INFO)
        root_logger.setLevel(level)
    
    # Set format
    log_format = config.get("format", "[%(levelname)s] %(name)s: %(message)s")
    formatter = logging.Formatter(log_format)
    
    # Configure root logger with the formatter
    for handler in root_logger.handlers:
        handler.setFormatter(formatter)
    
    # If no handlers, add one
    if not root_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
    
    # Configure specific loggers
    if "loggers" in config:
        for logger_name, logger_config in config["loggers"].items():
            logger = get_logger(logger_name)
            
            # Set level if specified
            if "level" in logger_config:
                level_name = logger_config["level"].upper()
                level = TRACE if level_name == "TRACE" else getattr(logging, level_name, logging.INFO)
                logger.setLevel(level)
            
            # Update handlers with new formatter
            for handler in logger.handlers:
                handler.setFormatter(formatter)

def reset_logging():
    """Reset logging configuration. Mainly for testing."""
    global _LOGGER_REGISTRY, _LOGGING_CONFIGURED
    
    # Reset all loggers in the registry
    for name, logger in _LOGGER_REGISTRY.items():
        # Remove all handlers
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
    
    # Clear registry and reset flag
    _LOGGER_REGISTRY = {}
    _LOGGING_CONFIGURED = False

def inspect_loggers():
    """
    Return diagnostic information about all loggers for debugging.
    
    Returns:
        Dictionary with logger information
    """
    return debug_loggers()