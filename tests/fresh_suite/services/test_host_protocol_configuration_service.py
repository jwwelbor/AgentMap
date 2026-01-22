"""
Unit tests for HostProtocolConfigurationService.

Tests the service that handles host protocol configuration,
including method name generation and protocol configuration.
"""

import unittest
from unittest.mock import MagicMock, Mock

from agentmap.services.host_protocol_configuration_service import (
    HostProtocolConfigurationService,
)


class TestHostProtocolConfigurationService(unittest.TestCase):
    """Test the HostProtocolConfigurationService."""

    def setUp(self):
        """Set up test fixtures."""
        # Create mock dependencies
        self.mock_registry = Mock()
        self.mock_logging_service = Mock()
        self.mock_logger = Mock()
        self.mock_logging_service.get_logger.return_value = self.mock_logger

        # Create service instance
        self.service = HostProtocolConfigurationService(
            self.mock_registry, self.mock_logging_service
        )

    def test_method_name_generation(self):
        """Test _get_configure_method_name for various protocol names."""
        test_cases = [
            # (Protocol name, Expected method name)
            ("EmailServiceProtocol", "configure_email_service"),
            ("SMSServiceProtocol", "configure_sms_service"),
            ("DatabaseProtocol", "configure_database_service"),
            ("MyCustomProtocol", "configure_my_custom_service"),
            ("HTTPServiceProtocol", "configure_http_service"),
            ("XMLParserProtocol", "configure_xml_parser_service"),
            ("JSONAPIProtocol", "configure_jsonapi_service"),
            ("IOTDeviceProtocol", "configure_iot_device_service"),
            ("S3StorageProtocol", "configure_s3_storage_service"),
            ("AIMLServiceProtocol", "configure_aiml_service"),
            ("SimpleProtocol", "configure_simple_service"),
            ("Protocol", "configure__service"),  # Edge case
            ("SomeService", "configure_some_service_service"),  # No Protocol suffix
        ]

        for protocol_name, expected_method in test_cases:
            # Create mock protocol with __name__ attribute
            mock_protocol = type(protocol_name, (), {})

            # Test method name generation
            result = self.service._get_configure_method_name(mock_protocol)

            self.assertEqual(
                result,
                expected_method,
                f"Failed for {protocol_name}: expected {expected_method}, got {result}",
            )

    def test_configure_host_protocols_success(self):
        """Test successful protocol configuration."""
        # Create mock protocol
        MockProtocol = type("TestServiceProtocol", (), {})

        # Create mock agent
        mock_agent = Mock()
        mock_agent.name = "test_agent"
        mock_agent.configure_test_service = Mock()

        # Set up registry to return service
        self.mock_registry.list_registered_services.return_value = ["test_service"]
        self.mock_registry.get_service_protocols.return_value = [MockProtocol]
        self.mock_registry.get_service_provider.return_value = (
            lambda: "mock_service_instance"
        )

        # Make isinstance work by adding the protocol to agent's class
        mock_agent.__class__ = type("MockAgent", (MockProtocol,), {})

        # Configure protocols
        count = self.service.configure_host_protocols(mock_agent)

        # Verify
        self.assertEqual(count, 1)
        mock_agent.configure_test_service.assert_called_once_with(
            "mock_service_instance"
        )

    def test_configure_host_protocols_no_matching_protocols(self):
        """Test configuration when agent doesn't implement any protocols."""
        # Create mock agent
        mock_agent = Mock()
        mock_agent.name = "test_agent"

        # Set up registry
        self.mock_registry.list_registered_services.return_value = ["test_service"]
        self.mock_registry.get_service_protocols.return_value = [
            type("UnimplementedProtocol", (), {})
        ]

        # Configure protocols
        count = self.service.configure_host_protocols(mock_agent)

        # Verify no services configured
        self.assertEqual(count, 0)

    def test_configure_host_protocols_missing_configure_method(self):
        """Test when agent implements protocol but lacks configure method."""
        # Create mock protocol
        MockProtocol = type("TestServiceProtocol", (), {})

        # Create mock agent that implements protocol but has no configure method
        mock_agent = Mock()
        mock_agent.name = "test_agent"
        # Remove the configure method
        del mock_agent.configure_test_service

        # Make isinstance work
        mock_agent.__class__ = type("MockAgent", (MockProtocol,), {})

        # Set up registry
        self.mock_registry.list_registered_services.return_value = ["test_service"]
        self.mock_registry.get_service_protocols.return_value = [MockProtocol]
        self.mock_registry.get_service_provider.return_value = (
            lambda: "mock_service_instance"
        )

        # Configure protocols
        count = self.service.configure_host_protocols(mock_agent)

        # Verify no services configured (method missing)
        self.assertEqual(count, 0)

    def test_get_configuration_status(self):
        """Test getting configuration status for an agent."""
        # Create mock protocol
        MockProtocol = type("TestServiceProtocol", (), {})

        # Create mock agent with proper class
        class MockAgent(MockProtocol):
            def __init__(self):
                self.name = "test_agent"
                self.configure_test_service = Mock()

        mock_agent = MockAgent()

        # Set up registry
        self.mock_registry.list_registered_services.return_value = [
            "test_service",
            "other_service",
        ]
        self.mock_registry.get_service_protocols.return_value = [MockProtocol]

        # Get status
        status = self.service.get_configuration_status(mock_agent)

        # Verify status structure
        self.assertEqual(status["agent_name"], "test_agent")
        self.assertEqual(status["agent_type"], "MockAgent")
        self.assertIn("implemented_protocols", status)
        self.assertIn("available_services", status)
        self.assertIn("configuration_potential", status)
        self.assertIn("summary", status)

        # Verify services listed
        self.assertEqual(len(status["available_services"]), 2)
        self.assertIn("test_service", status["available_services"])

    def test_error_handling_in_configure_host_protocols(self):
        """Test error handling during protocol configuration."""
        # Create mock agent
        mock_agent = Mock()
        mock_agent.name = "test_agent"

        # Make registry raise exception
        self.mock_registry.list_registered_services.side_effect = Exception(
            "Registry error"
        )

        # Configure protocols - should handle error gracefully
        count = self.service.configure_host_protocols(mock_agent)

        # Verify error was logged but no crash
        self.assertEqual(count, 0)
        self.mock_logger.error.assert_called()

    def test_skip_protocol_placeholders(self):
        """Test that protocol: prefixed services are skipped."""
        # Create mock agent
        mock_agent = Mock()
        mock_agent.name = "test_agent"

        # Set up registry with protocol placeholder
        self.mock_registry.list_registered_services.return_value = [
            "protocol:some_protocol",
            "real_service",
        ]
        self.mock_registry.get_service_protocols.return_value = []

        # Configure protocols
        count = self.service.configure_host_protocols(mock_agent)

        # Verify protocol placeholder was skipped
        self.assertEqual(count, 0)
        # get_service_protocols should only be called for real_service
        self.mock_registry.get_service_protocols.assert_called_once_with("real_service")


if __name__ == "__main__":
    unittest.main()
