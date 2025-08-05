"""
Integration test for host protocol configuration using dependency injection.

Tests that the ApplicationContainer properly wires HostProtocolConfigurationService
to GraphRunnerService, following clean DI principles.
"""
import unittest
from unittest.mock import Mock
from pathlib import Path
import tempfile
import shutil

from agentmap.di import initialize_di
from agentmap.di.containers import ApplicationContainer
from agentmap.services.host_protocol_configuration_service import HostProtocolConfigurationService
from agentmap.services.host_service_registry import HostServiceRegistry


class MockDatabaseProtocol:
    """Mock protocol for testing."""
    def configure_database_service(self, service):
        pass


class MockDatabaseAgent:
    """Mock agent that implements the protocol."""
    def __init__(self):
        self.name = "test_db_agent"
        self.database_service = None
        
    def configure_database_service(self, service):
        self.database_service = service


class TestHostProtocolIntegration(unittest.TestCase):
    """Integration tests for host protocol configuration in DI container."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary directory for configs
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = self._create_test_config()
        
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        
    def _create_test_config(self) -> Path:
        """Create minimal test configuration."""
        config_path = Path(self.temp_dir) / "test_config.yaml"
        
        config_content = """logging:
  level: DEBUG

llm:
  anthropic:
    api_key: "test_key"
    model: "claude-3-5-sonnet-20241022"
    
host_application:
  enabled: true
"""
        
        with open(config_path, 'w') as f:
            f.write(config_content)
            
        return config_path
        
    def test_host_protocol_configuration_service_is_created(self):
        """Test that HostProtocolConfigurationService is created by container."""
        # Create container
        container = initialize_di(str(self.config_path))
        
        # Get the service
        service = container.host_protocol_configuration_service()
        
        # Verify it's the correct type
        self.assertIsInstance(service, HostProtocolConfigurationService)
        self.assertTrue(hasattr(service, 'configure_host_protocols'))
        self.assertTrue(hasattr(service, 'get_configuration_status'))
        
    def test_graph_runner_receives_host_protocol_service(self):
        """Test that GraphRunnerService receives HostProtocolConfigurationService."""
        # Create container
        container = initialize_di(str(self.config_path))
        
        # Get GraphRunnerService
        graph_runner = container.graph_runner_service()
        
        # Verify it has the host protocol configuration service, not the container
        self.assertTrue(hasattr(graph_runner, 'host_protocol_configuration'))
        self.assertIsInstance(graph_runner.host_protocol_configuration, HostProtocolConfigurationService)
        self.assertTrue(graph_runner._host_services_available)
        
        # Verify it doesn't have container reference
        self.assertFalse(hasattr(graph_runner, 'application_container'))
        
    def test_host_protocol_configuration_workflow(self):
        """Test the complete workflow of host protocol configuration."""
        # Create container
        container = initialize_di(str(self.config_path))
        
        # Register a mock host service
        mock_db_service = Mock()
        mock_db_service.name = "test_database"
        
        # Get the host service registry and register a service
        registry = container.host_service_registry()
        registry.register_service_provider(
            service_name="database_service",
            provider=lambda: mock_db_service,  # Provider is a factory function
            protocols=[MockDatabaseProtocol]
        )
        
        # Create a mock agent that implements the protocol
        agent = MockDatabaseAgent()
        
        # Get GraphRunnerService
        graph_runner = container.graph_runner_service()
        
        # Configure host services on the agent
        count = graph_runner._configure_host_services(agent)
        
        # Since MockDatabaseAgent doesn't actually implement MockDatabaseProtocol
        # according to isinstance(), this should return 0
        self.assertEqual(count, 0)
        
        # But let's test the service directly
        host_config_service = container.host_protocol_configuration_service()
        
        # Get configuration status
        status = host_config_service.get_configuration_status(agent)
        
        # Verify status structure
        self.assertIn('agent_name', status)
        self.assertEqual(status['agent_name'], 'test_db_agent')
        self.assertIn('available_services', status)
        self.assertIn('summary', status)
        
    def test_host_protocol_configuration_uses_service_not_container(self):
        """Test that host protocol configuration is done via service, not container."""
        # Create container
        container = initialize_di(str(self.config_path))
        
        # Get the HostProtocolConfigurationService
        host_config_service = container.host_protocol_configuration_service()
        self.assertIsNotNone(host_config_service)
        
        # Create a mock agent
        agent = Mock()
        agent.name = "test_agent"
        
        # Call the service method directly (not through container)
        result = host_config_service.configure_host_protocols(agent)
        
        # Should return a number (0 since no protocols match)
        self.assertIsInstance(result, int)
        self.assertEqual(result, 0)  # No services configured since mock doesn't implement protocols
        
        # Verify GraphRunnerService would use the same service
        graph_runner = container.graph_runner_service()
        # GraphRunner should have the service, not the container
        self.assertIsNotNone(graph_runner.host_protocol_configuration)
        self.assertIsInstance(graph_runner.host_protocol_configuration, HostProtocolConfigurationService)
        
    def test_graceful_degradation_without_host_services(self):
        """Test that system works without host services enabled."""
        # Create config without host_application
        config_path = Path(self.temp_dir) / "minimal_config.yaml"
        config_content = """logging:
  level: DEBUG

llm:
  anthropic:
    api_key: "test_key"
    model: "claude-3-5-sonnet-20241022"
    
host_application:
  enabled: false
"""
        
        with open(config_path, 'w') as f:
            f.write(config_content)
            
        # Create container
        container = initialize_di(str(config_path))
        
        # Get GraphRunnerService
        graph_runner = container.graph_runner_service()
        
        # Should still work but host services should be disabled
        self.assertIsNotNone(graph_runner)
        
        # Create mock agent
        agent = Mock()
        agent.name = "test_agent"
        
        # Configure host services should return 0
        count = graph_runner._configure_host_services(agent)
        self.assertEqual(count, 0)
        
        # Get status should indicate disabled
        status = graph_runner.get_host_service_status(agent)
        self.assertEqual(status['error'], 'Host application support disabled')


if __name__ == '__main__':
    unittest.main()
