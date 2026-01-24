"""Debug test to understand mock logger structure."""

from unittest.mock import Mock

from tests.utils.mock_service_factory import MockServiceFactory

# Create mock logging service using factory
mock_logging = MockServiceFactory.create_mock_logging_service()

# Get a logger
logger = mock_logging.get_class_logger("test")

# Print logger structure
print(f"Logger type: {type(logger)}")
print(f"Logger.debug type: {type(logger.debug)}")

# Check if .called exists
print(f"Has .called: {hasattr(logger.debug, 'called')}")
print(f"Initial .called value: {logger.debug.called}")

# Call debug
logger.debug("Test message")

# Check again
print(f"After call .called value: {logger.debug.called}")

# Check call_args_list
print(f"Call args list: {logger.debug.call_args_list}")

# Also check calls attribute
print(f"Logger.calls: {logger.calls}")
