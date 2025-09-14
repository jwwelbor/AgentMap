"""Temporary patch for MockServiceFactory to fix logging test issues."""

from unittest.mock import Mock
from typing import Dict, Any, Optional


def create_fixed_mock_logging_service(logger_name: str = "test") -> Mock:
    """
    Create a fixed mock logging service that properly caches loggers.
    """
    mock_service = Mock()
    
    # Cache for loggers to ensure same instance is returned for same class
    logger_cache = {}
    
    def create_mock_logger(name: str) -> Mock:
        """Create a mock logger with call tracking."""
        mock_logger = Mock()
        mock_logger.name = name
        mock_logger.calls = []  # Track calls for verification
        
        # Configure logging methods to track calls
        def track_log_call(level, message, *args, **kwargs):
            mock_logger.calls.append((level, message, args, kwargs))
        
        # Create new Mock objects for each logging method to preserve call_args_list
        mock_logger.debug = Mock(side_effect=lambda msg, *args, **kwargs: track_log_call("debug", msg, *args, **kwargs))
        mock_logger.info = Mock(side_effect=lambda msg, *args, **kwargs: track_log_call("info", msg, *args, **kwargs))
        mock_logger.warning = Mock(side_effect=lambda msg, *args, **kwargs: track_log_call("warning", msg, *args, **kwargs))
        mock_logger.error = Mock(side_effect=lambda msg, *args, **kwargs: track_log_call("error", msg, *args, **kwargs))
        mock_logger.trace = Mock(side_effect=lambda msg, *args, **kwargs: track_log_call("trace", msg, *args, **kwargs))
        
        return mock_logger
    
    def get_class_logger(instance_or_name) -> Mock:
        """Get logger for class instance or by name - handle both patterns."""
        if isinstance(instance_or_name, str):
            logger_name = instance_or_name
        elif hasattr(instance_or_name, '__class__'):
            logger_name = instance_or_name.__class__.__name__
        else:
            logger_name = str(type(instance_or_name).__name__)
        
        # Return cached logger if exists, otherwise create and cache
        if logger_name not in logger_cache:
            logger_cache[logger_name] = create_mock_logger(logger_name)
        return logger_cache[logger_name]
    
    # Configure service methods
    mock_service.get_class_logger.side_effect = get_class_logger
    
    return mock_service


# Monkey patch the MockServiceFactory
import sys
if 'tests.utils.mock_service_factory' in sys.modules:
    sys.modules['tests.utils.mock_service_factory'].MockServiceFactory.create_mock_logging_service = staticmethod(create_fixed_mock_logging_service)
