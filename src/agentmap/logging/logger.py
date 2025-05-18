# agentmap/logging/logger.py (updated)
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

# Import our manager
from agentmap.logging.manager import get_logger as _get_manager_logger
from agentmap.logging.manager import configure_logger, reset as _reset_manager


def get_logger(name="AgentMap", propagate=True):
    """
    Get a logger with the AgentMap configuration.

    Args:
        name: Logger name
        propagate: Whether to propagate messages to parent loggers

    Returns:
        Configured logger
    """
    # Get level from environment or default
    level_name = os.environ.get("AGENTMAP_LOG_LEVEL", "INFO").upper()
    try:
        level = TRACE if level_name == "TRACE" else getattr(logging, level_name, logging.INFO)
    except AttributeError:
        level = logging.INFO

    # Get logger and configure it
    logger = logging.getLogger(name)

    # Set propagation flag
    logger.propagate = propagate

    # Configure if not already configured
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("[%(levelname)s] %(name)s: %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(level)

    return logger


def configure_logging(config: Optional[Dict[str, Any]] = None):
    """
    Configure logging system from configuration.

    Args:
        config: Logging configuration dictionary
    """
    # Skip if config is empty
    if not config:
        return

    # Configure root logger
    root_logger = _get_manager_logger("")

    # Set level if specified
    if "level" in config:
        level_name = config["level"].upper()
        level = TRACE if level_name == "TRACE" else getattr(logging, level_name, logging.INFO)
        configure_logger(root_logger, level=level)

    # Set format
    log_format = config.get("format", "[%(levelname)s] %(name)s: %(message)s")

    # Configure existing handlers
    for handler in root_logger.handlers:
        if isinstance(handler, logging.Handler) and not isinstance(handler, logging.NullHandler):
            handler.setFormatter(logging.Formatter(log_format))

    # Add handler if needed
    if not any(not isinstance(h, logging.NullHandler) for h in root_logger.handlers):
        configure_logger(root_logger, format=log_format, handler="console")

    # Configure specific loggers
    if "loggers" in config:
        for logger_name, logger_config in config["loggers"].items():
            logger = get_logger(logger_name)

            # Extract configuration
            level = None
            if "level" in logger_config:
                level_name = logger_config["level"].upper()
                level = TRACE if level_name == "TRACE" else getattr(logging, level_name, logging.INFO)

            # Configure the logger
            configure_logger(
                logger,
                level=level,
                format=log_format,
                propagate=logger_config.get("propagate")
            )


def reset_logging():
    """Reset logging configuration. Mainly for testing."""
    _reset_manager()


def inspect_loggers():
    """
    Return diagnostic information about all loggers for debugging.

    Returns:
        Dictionary with logger information
    """
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