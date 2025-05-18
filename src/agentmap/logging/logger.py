# agentmap/logging/logger.py
import logging
import os
from typing import Dict, Optional, Any

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
    
    # Create new logger
    logger = logging.getLogger(name)
    
    # Only configure if no handlers exist
    if not logger.handlers:
        # Basic configuration with reasonable defaults
        handler = logging.StreamHandler()
        formatter = logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        # Set level from environment or default
        level_name = os.environ.get("AGENTMAP_LOG_LEVEL", "INFO").upper()
        try:
            level = TRACE if level_name == "TRACE" else getattr(logging, level_name, logging.INFO)
        except AttributeError:
            level = logging.INFO
        
        logger.setLevel(level)
    
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
    
    _LOGGING_CONFIGURED = True
    
    # Configure root logger
    root_logger = logging.getLogger()
    
    # Clear existing handlers if reconfiguring
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
    
    # Set level if specified
    if "level" in config:
        level_name = config["level"].upper()
        level = TRACE if level_name == "TRACE" else getattr(logging, level_name, logging.INFO)
        root_logger.setLevel(level)
    
    # Set format
    log_format = config.get("format", "[%(levelname)s] %(name)s: %(message)s")
    formatter = logging.Formatter(log_format)
    
    # Create handler
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
    
    # Update all existing loggers
    for name, logger in _LOGGER_REGISTRY.items():
        # Configure specific level if defined
        if "loggers" in config and name in config["loggers"]:
            logger_config = config["loggers"][name]
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