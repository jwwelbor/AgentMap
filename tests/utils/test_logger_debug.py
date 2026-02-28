"""Debug test to understand mock logger structure."""

import unittest

from tests.utils.mock_service_factory import MockServiceFactory


class TestLoggerDebug(unittest.TestCase):
    def test_mock_logger_structure(self):
        """Test to understand the mock logger structure."""
        # Create mock logging service using factory
        mock_logging = MockServiceFactory.create_mock_logging_service()

        # Get a logger
        logger = mock_logging.get_class_logger(self)

        # Print logger structure
        print(f"Logger type: {type(logger)}")
        print(f"Logger.debug type: {type(logger.debug)}")
        print(f"Logger.debug attributes: {dir(logger.debug)}")

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


if __name__ == "__main__":
    unittest.main()
