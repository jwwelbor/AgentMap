"""
Simplified integration test for HostServiceRegistry.

Tests the core functionality without GraphRunnerService integration,
which requires more complex container setup.
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from typing import Any, Protocol, runtime_checkable
from unittest.mock import Mock

from agentmap.di import initialize_di
from agentmap.services.host_service_registry import HostServiceRegistry
from agentmap.agents.base_agent import BaseAgent


# Test protocol for integration testing
@runtime_checkable
class EmailServiceProtocol(Protocol):
    """Protocol for email service functionality."""
    
    def send_email(self, to: str, subject: str, body: str) -> bool:
        """Send an email."""
        ...


# Test service implementation
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


class TestHostServiceRegistryCore(unittest.TestCase):
    """Core integration tests for HostServiceRegistry."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary directory for test configs
        self.temp_dir = tempfile.mkdtemp()
        self.test_config_path = self._create_test_config()
        
        # Initialize DI container
        self.container = initialize_di(str(self.test_config_path))
        
        # Get the host service registry
        self.registry = self.container.host_service_registry()
        
        # Create mock service
        self.mock_email_service = MockEmailService()
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_test_config(self) -> Path:
        """Create a minimal test configuration file."""
        config_path = Path(self.temp_dir) / "test_config.yaml"
        config_content = """logging:
  level: DEBUG
  version: 1
  formatters:
    default:
      format: '[%(levelname)s] %(name)s: %(message)s'
  handlers:
    console:
      class: logging.StreamHandler
      formatter: default
  root:
    level: DEBUG
    handlers: [console]

llm:
  anthropic:
    api_key: "test_key"

host_application:
  enabled: true
"""
        with open(config_path, 'w') as f:
            f.write(config_content)
        return config_path
    
    def test_host_service_registry_available(self):
        """Test that HostServiceRegistry is available from DI container."""
        self.assertIsNotNone(self.registry)
        self.assertIsInstance(self.registry, HostServiceRegistry)
    
    def test_service_registration_and_retrieval(self):
        """Test basic service registration and retrieval."""
        # Register service
        self.registry.register_service_provider(
            "email_service",
            lambda: self.mock_email_service,
            protocols=[EmailServiceProtocol],
            metadata={"version": "1.0"}
        )
        
        # Verify registration
        self.assertTrue(self.registry.is_service_registered("email_service"))
        
        # Retrieve service
        provider = self.registry.get_service_provider("email_service")
        self.assertIsNotNone(provider)
        
        # Get service instance
        service_instance = provider()
        self.assertIsInstance(service_instance, MockEmailService)
        
        # Test service works
        result = service_instance.send_email("test@example.com", "Test", "Body")
        self.assertTrue(result)
        self.assertEqual(len(service_instance.emails_sent), 1)
    
    def test_protocol_registration(self):
        """Test protocol registration and lookup."""
        # Register with protocol
        self.registry.register_service_provider(
            "email_service",
            MockEmailService,
            protocols=[EmailServiceProtocol]
        )
        
        # Verify protocol is registered
        self.assertTrue(self.registry.is_protocol_implemented(EmailServiceProtocol))
        
        # Look up by protocol
        service_name = self.registry.get_protocol_implementation(EmailServiceProtocol)
        self.assertEqual(service_name, "email_service")
        
        # Discover by protocol
        services = self.registry.discover_services_by_protocol(EmailServiceProtocol)
        self.assertIn("email_service", services)
    
    def test_registry_summary(self):
        """Test registry summary functionality."""
        # Register multiple services
        self.registry.register_service_provider(
            "service1",
            Mock,
            metadata={"type": "test"}
        )
        self.registry.register_service_provider(
            "service2",
            Mock,
            protocols=[EmailServiceProtocol]
        )
        
        # Get summary
        summary = self.registry.get_registry_summary()
        
        # Verify summary contents
        self.assertEqual(summary["total_services"], 2)
        self.assertIn("service1", summary["registered_services"])
        self.assertIn("service2", summary["registered_services"])
        self.assertTrue(summary["registry_health"]["providers_storage_ok"])
    
    def test_manual_agent_configuration(self):
        """Test manual configuration pattern for agents."""
        # Register service
        self.registry.register_service_provider(
            "email_service",
            lambda: self.mock_email_service,
            protocols=[EmailServiceProtocol]
        )
        
        # Manual configuration pattern that users can follow
        class NotificationAgent(BaseAgent):
            """Example agent that uses host services."""
            
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self._email_service = None
            
            def configure_email_service(self, email_service: Any) -> None:
                """Configure email service."""
                self._email_service = email_service
            
            def send_notification(self, to: str, message: str) -> bool:
                """Send notification using configured service."""
                if self._email_service:
                    return self._email_service.send_email(to, "Notification", message)
                return False
        
        # Create agent
        agent = NotificationAgent(
            name="test_agent",
            prompt="Send notifications"
        )
        
        # Manual configuration (what host applications would do)
        email_provider = self.registry.get_service_provider("email_service")
        if email_provider:
            email_service = email_provider()
            agent.configure_email_service(email_service)
        
        # Test it works
        result = agent.send_notification("user@example.com", "Test message")
        self.assertTrue(result)
        self.assertEqual(len(self.mock_email_service.emails_sent), 1)


if __name__ == '__main__':
    unittest.main()
