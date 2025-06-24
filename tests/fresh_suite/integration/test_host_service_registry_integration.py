"""
Integration tests for HostServiceRegistry with DI container.

These tests verify that the HostServiceRegistry is properly integrated
with the dependency injection container and works end-to-end with
GraphRunnerService for host service injection.
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from typing import Any, Protocol, runtime_checkable
from unittest.mock import Mock, patch

from agentmap.di import initialize_di
from agentmap.services.host_service_registry import HostServiceRegistry
from agentmap.agents.base_agent import BaseAgent
from tests.utils.mock_service_factory import MockServiceFactory


# Test protocol for integration testing
@runtime_checkable
class EmailServiceProtocol(Protocol):
    """Protocol for email service functionality."""
    
    def send_email(self, to: str, subject: str, body: str) -> bool:
        """Send an email."""
        ...


@runtime_checkable
class SMSServiceProtocol(Protocol):
    """Protocol for SMS service functionality."""
    
    def send_sms(self, to: str, message: str) -> bool:
        """Send an SMS."""
        ...


# Test service implementations
class MockEmailService:
    """Mock email service for testing."""
    
    def __init__(self):
        self.emails_sent = []
    
    def send_email(self, to: str, subject: str, body: str) -> bool:
        self.emails_sent.append({
            'to': to,
            'subject': subject,
            'body': body
        })
        return True


class MockSMSService:
    """Mock SMS service for testing."""
    
    def __init__(self):
        self.sms_sent = []
    
    def send_sms(self, to: str, message: str) -> bool:
        self.sms_sent.append({
            'to': to,
            'message': message
        })
        return True


# Test agent that implements the protocols
class NotificationAgent(BaseAgent):
    """Test agent that can use email and SMS services."""
    
    # Explicitly implement protocol methods to ensure isinstance works
    def send_email(self, to: str, subject: str, body: str) -> bool:
        """Delegate to configured email service."""
        return self.email_service.send_email(to, subject, body)
    
    def send_sms(self, to: str, message: str) -> bool:
        """Delegate to configured SMS service."""
        return self.sms_service.send_sms(to, message)
    
    def __init__(self, name: str, prompt: str, context=None, **kwargs):
        super().__init__(name, prompt, context, **kwargs)
        self._email_service = None
        self._sms_service = None
    
    def configure_email_service(self, email_service: Any) -> None:
        """Configure email service for this agent."""
        self._email_service = email_service
        self.log_debug("Email service configured")
    
    def configure_sms_service(self, sms_service: Any) -> None:
        """Configure SMS service for this agent."""
        self._sms_service = sms_service
        self.log_debug("SMS service configured")
    
    @property
    def email_service(self) -> Any:
        """Get email service."""
        if self._email_service is None:
            raise ValueError("Email service not configured")
        return self._email_service
    
    @property
    def sms_service(self) -> Any:
        """Get SMS service."""
        if self._sms_service is None:
            raise ValueError("SMS service not configured")
        return self._sms_service
    
    def process(self, inputs: dict) -> Any:
        """Process notification request."""
        notification_type = inputs.get('type', 'email')
        
        if notification_type == 'email':
            return self.email_service.send_email(
                inputs['to'],
                inputs['subject'],
                inputs['body']
            )
        elif notification_type == 'sms':
            return self.sms_service.send_sms(
                inputs['to'],
                inputs['message']
            )
        else:
            raise ValueError(f"Unknown notification type: {notification_type}")


class TestHostServiceRegistryIntegration(unittest.TestCase):
    """Integration tests for HostServiceRegistry with complete DI flow."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary directory for test configs
        self.temp_dir = tempfile.mkdtemp()
        self.test_config_path = self._create_test_config()
        
        # Initialize DI container
        self.container = initialize_di(str(self.test_config_path))
        
        # Get the host service registry
        self.registry = self.container.host_service_registry()
        
        # Create mock services
        self.mock_email_service = MockEmailService()
        self.mock_sms_service = MockSMSService()
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_test_config(self) -> Path:
        """Create a minimal test configuration file."""
        config_path = Path(self.temp_dir) / "test_config.yaml"
        config_content = """logging:
  level: DEBUG

llm:
  anthropic:
    api_key: "test_key"

host_application:
  enabled: true
  protocol_folders: []
"""
        with open(config_path, 'w') as f:
            f.write(config_content)
        return config_path
    
    # =============================================================================
    # Test 1: Registry Available in Container
    # =============================================================================
    
    def test_host_service_registry_available_in_container(self):
        """Test that HostServiceRegistry is available from DI container."""
        # Assert
        self.assertIsNotNone(self.registry)
        self.assertIsInstance(self.registry, HostServiceRegistry)
        
        # Verify it's a singleton
        registry2 = self.container.host_service_registry()
        self.assertIs(self.registry, registry2)
    
    # =============================================================================
    # Test 2: Service Registration Through Registry
    # =============================================================================
    
    def test_register_services_in_registry(self):
        """Test registering host services in the registry."""
        # Register email service
        self.registry.register_service_provider(
            "email_service",
            lambda: self.mock_email_service,
            protocols=[EmailServiceProtocol],
            metadata={"type": "notification", "provider": "mock"}
        )
        
        # Register SMS service
        self.registry.register_service_provider(
            "sms_service",
            lambda: self.mock_sms_service,
            protocols=[SMSServiceProtocol],
            metadata={"type": "notification", "provider": "mock"}
        )
        
        # Verify services are registered
        self.assertTrue(self.registry.is_service_registered("email_service"))
        self.assertTrue(self.registry.is_service_registered("sms_service"))
        
        # Verify protocols are implemented
        self.assertTrue(self.registry.is_protocol_implemented(EmailServiceProtocol))
        self.assertTrue(self.registry.is_protocol_implemented(SMSServiceProtocol))
        
        # Verify service lookup by protocol
        email_service_name = self.registry.get_protocol_implementation(EmailServiceProtocol)
        self.assertEqual(email_service_name, "email_service")
        
        sms_service_name = self.registry.get_protocol_implementation(SMSServiceProtocol)
        self.assertEqual(sms_service_name, "sms_service")
    
    # =============================================================================
    # Test 3: Container Registration Updates Registry
    # =============================================================================
    
    def test_container_registration_updates_registry(self):
        """Test that registry can be used to register services for the container."""
        # Register through registry directly (container integration happens via GraphRunnerService)
        self.registry.register_service_provider(
            "email_service",
            MockEmailService,
            protocols=[EmailServiceProtocol],
            metadata={"registered_via": "registry"}
        )
        
        # Verify it's in the registry
        self.assertTrue(self.registry.is_service_registered("email_service"))
        self.assertTrue(self.registry.is_protocol_implemented(EmailServiceProtocol))
        
        # Verify metadata was passed
        metadata = self.registry.get_service_metadata("email_service")
        self.assertIsNotNone(metadata)
        self.assertEqual(metadata.get("registered_via"), "registry")
    
    # =============================================================================
    # Test 4: GraphRunnerService Integration
    # =============================================================================
    
    def test_graph_runner_service_configures_host_services(self):
        """Test that GraphRunnerService can configure host services on agents."""
        # Register services in registry first
        self.registry.register_service_provider(
            "email_service",
            lambda: self.mock_email_service,
            protocols=[EmailServiceProtocol]
        )
        self.registry.register_service_provider(
            "sms_service",
            lambda: self.mock_sms_service,
            protocols=[SMSServiceProtocol]
        )
        
        # Get GraphRunnerService
        graph_runner = self.container.graph_runner_service()
        
        # Verify that the host protocol configuration service was injected properly
        self.assertIsNotNone(graph_runner.host_protocol_configuration)
        self.assertTrue(graph_runner._host_services_available)
        
        # Create test agent
        agent = NotificationAgent(
            name="test_notification",
            prompt="Send notifications",
            logger=MockServiceFactory.create_mock_logging_service().get_logger("test")
        )
        
        # Configure agent services
        configured_count = graph_runner._configure_host_services(agent)
        
        # Verify services were configured
        self.assertEqual(configured_count, 2)
        
        # Verify agent can use the services
        self.assertIsNotNone(agent._email_service)
        self.assertIsNotNone(agent._sms_service)
        
        # Test that services work
        result = agent.process({
            'type': 'email',
            'to': 'test@example.com',
            'subject': 'Test',
            'body': 'Test email'
        })
        self.assertTrue(result)
        self.assertEqual(len(self.mock_email_service.emails_sent), 1)
    
    # =============================================================================
    # Test 5: Complete End-to-End Flow
    # =============================================================================
    
    def test_complete_end_to_end_flow(self):
        """Test complete flow from registration to agent execution."""
        # Step 1: Register services through registry
        self.registry.register_service_provider(
            "email_service",
            lambda: self.mock_email_service,
            protocols=[EmailServiceProtocol]
        )
        
        # Step 2: Verify registry has the service
        self.assertTrue(self.registry.is_service_registered("email_service"))
        
        # Step 3: Get the GraphRunnerService
        graph_runner = self.container.graph_runner_service()
        
        # Verify GraphRunnerService has access to host protocol configuration service
        self.assertIsNotNone(graph_runner.host_protocol_configuration)
        
        # Create agent
        agent = NotificationAgent(
            name="test_agent",
            prompt="Test",
            logger=MockServiceFactory.create_mock_logging_service().get_logger("test")
        )
        
        # Use GraphRunnerService's host service configuration
        configured_count = graph_runner._configure_host_services(agent)
        
        # Step 4: Verify configuration
        self.assertEqual(configured_count, 1)
        self.assertIsNotNone(agent._email_service)
        
        # Step 5: Test functionality
        email_sent = agent.email_service.send_email(
            "user@example.com",
            "Integration Test",
            "This is an integration test"
        )
        self.assertTrue(email_sent)
        self.assertEqual(len(self.mock_email_service.emails_sent), 1)
        self.assertEqual(
            self.mock_email_service.emails_sent[0]['subject'],
            "Integration Test"
        )
    
    # =============================================================================
    # Test 6: Registry Summary and Validation
    # =============================================================================
    
    def test_registry_summary_and_validation(self):
        """Test registry summary and validation features."""
        # Register multiple services
        self.registry.register_service_provider(
            "email_service",
            MockEmailService,
            protocols=[EmailServiceProtocol],
            metadata={"version": "1.0"}
        )
        self.registry.register_service_provider(
            "sms_service",
            MockSMSService,
            protocols=[SMSServiceProtocol],
            metadata={"version": "2.0"}
        )
        
        # Get registry summary
        summary = self.registry.get_registry_summary()
        
        # Verify summary
        self.assertEqual(summary["total_services"], 2)
        self.assertEqual(summary["total_protocols"], 2)
        self.assertIn("email_service", summary["registered_services"])
        self.assertIn("sms_service", summary["registered_services"])
        self.assertTrue(summary["registry_health"]["providers_storage_ok"])
        
        # Validate services
        email_validation = self.registry.validate_service_provider("email_service")
        self.assertTrue(email_validation["valid"])
        self.assertTrue(email_validation["checks"]["provider_exists"])
        self.assertTrue(email_validation["checks"]["has_protocols"])
    
    # =============================================================================
    # Test 7: Service Discovery by Protocol
    # =============================================================================
    
    def test_service_discovery_by_protocol(self):
        """Test discovering services by protocol implementation."""
        # Register multiple services implementing same protocol
        self.registry.register_service_provider(
            "email_service_primary",
            MockEmailService,
            protocols=[EmailServiceProtocol]
        )
        self.registry.register_service_provider(
            "email_service_backup",
            MockEmailService,
            protocols=[EmailServiceProtocol]
        )
        
        # Discover services
        email_services = self.registry.discover_services_by_protocol(EmailServiceProtocol)
        
        # Should find both services (discover_services_by_protocol returns all implementations)
        self.assertEqual(len(email_services), 2)
        self.assertIn("email_service_primary", email_services)
        self.assertIn("email_service_backup", email_services)
    
    # =============================================================================
    # Test 8: Graceful Degradation
    # =============================================================================
    
    def test_graceful_degradation_when_registry_not_available(self):
        """Test that system degrades gracefully when registry is not available."""
        # Get GraphRunnerService
        graph_runner = self.container.graph_runner_service()
        
        # Verify host protocol configuration service is available first
        self.assertIsNotNone(graph_runner.host_protocol_configuration)
        
        # Create agent
        agent = NotificationAgent(
            name="test_agent",
            prompt="Test",
            logger=MockServiceFactory.create_mock_logging_service().get_logger("test")
        )
        
        # Mock the configure_host_protocols method to fail
        original_configure = graph_runner.host_protocol_configuration.configure_host_protocols
        
        def failing_configure(agent):
            raise Exception("Configuration unavailable")
        
        # Replace the method temporarily
        graph_runner.host_protocol_configuration.configure_host_protocols = failing_configure
        
        try:
            # This should handle the error gracefully
            configured_count = graph_runner._configure_host_services(agent)
            
            # No services configured due to configuration failure
            self.assertEqual(configured_count, 0)
        finally:
            # Restore original method
            graph_runner.host_protocol_configuration.configure_host_protocols = original_configure
    
    # =============================================================================
    # Test 9: Registry Cleanup
    # =============================================================================
    
    def test_registry_cleanup_operations(self):
        """Test registry cleanup and unregistration."""
        # Register services
        self.registry.register_service_provider(
            "email_service",
            MockEmailService,
            protocols=[EmailServiceProtocol]
        )
        
        # Verify registered
        self.assertTrue(self.registry.is_service_registered("email_service"))
        
        # Unregister
        success = self.registry.unregister_service("email_service")
        self.assertTrue(success)
        
        # Verify cleaned up
        self.assertFalse(self.registry.is_service_registered("email_service"))
        self.assertFalse(self.registry.is_protocol_implemented(EmailServiceProtocol))
        
        # Clear entire registry
        self.registry.register_service_provider("test1", Mock())
        self.registry.register_service_provider("test2", Mock())
        self.assertEqual(len(self.registry.list_registered_services()), 2)
        
        self.registry.clear_registry()
        self.assertEqual(len(self.registry.list_registered_services()), 0)


if __name__ == '__main__':
    unittest.main()
