"""
Test GraphRunnerService host protocol configuration using dependency injection.

Verifies that GraphRunnerService uses the injected HostProtocolConfigurationService
instead of accessing the container directly, following proper DI principles.
"""
import unittest
from unittest.mock import Mock, MagicMock, patch

from agentmap.services.graph_runner_service import GraphRunnerService
from agentmap.services.host_protocol_configuration_service import HostProtocolConfigurationService


class TestGraphRunnerServiceHostProtocolDI(unittest.TestCase):
    """Test that GraphRunnerService follows DI principles for host protocol configuration."""
    
    def setUp(self):
        """Set up test dependencies."""
        # Create mock services
        self.mock_graph_definition = Mock()
        self.mock_graph_execution = Mock()
        self.mock_compilation = Mock()
        self.mock_graph_bundle = Mock()
        self.mock_agent_factory = Mock()
        self.mock_llm_service = Mock()
        self.mock_storage_manager = Mock()
        self.mock_node_registry = Mock()
        self.mock_logging_service = Mock()
        self.mock_app_config = Mock()
        self.mock_execution_tracking = Mock()
        self.mock_execution_policy = Mock()
        self.mock_state_adapter = Mock()
        self.mock_dependency_checker = Mock()
        self.mock_graph_assembly = Mock()
        self.mock_prompt_manager = Mock()
        
        # Create mock host protocol configuration service
        self.mock_host_protocol_config = Mock(spec=HostProtocolConfigurationService)
        self.mock_host_protocol_config.configure_host_protocols.return_value = 2
        self.mock_host_protocol_config.get_configuration_status.return_value = {
            "configuration_potential": [
                {"protocol": "DatabaseProtocol", "service": "db_service", "agent_implements": True}
            ],
            "summary": {
                "configuration_ready": 1,
                "total_services_available": 3,
                "total_protocols_implemented": 1
            }
        }
        
        # Configure logging
        self.mock_logger = Mock()
        self.mock_logging_service.get_class_logger.return_value = self.mock_logger
        self.mock_logging_service.get_logger.return_value = self.mock_logger
        
        # Configure app config
        self.mock_app_config.is_host_application_enabled.return_value = True
        
    def test_graph_runner_accepts_host_protocol_service_not_container(self):
        """Test that GraphRunnerService accepts HostProtocolConfigurationService in constructor."""
        # Create GraphRunnerService with host protocol configuration service
        runner = GraphRunnerService(
            graph_definition_service=self.mock_graph_definition,
            graph_execution_service=self.mock_graph_execution,
            compilation_service=self.mock_compilation,
            graph_bundle_service=self.mock_graph_bundle,
            agent_factory_service=self.mock_agent_factory,
            llm_service=self.mock_llm_service,
            storage_service_manager=self.mock_storage_manager,
            node_registry_service=self.mock_node_registry,
            logging_service=self.mock_logging_service,
            app_config_service=self.mock_app_config,
            execution_tracking_service=self.mock_execution_tracking,
            execution_policy_service=self.mock_execution_policy,
            state_adapter_service=self.mock_state_adapter,
            dependency_checker_service=self.mock_dependency_checker,
            graph_assembly_service=self.mock_graph_assembly,
            prompt_manager_service=self.mock_prompt_manager,
            host_protocol_configuration_service=self.mock_host_protocol_config
        )
        
        # Verify the service is stored, not a container
        self.assertEqual(runner.host_protocol_configuration, self.mock_host_protocol_config)
        self.assertTrue(runner._host_services_available)
        self.assertFalse(hasattr(runner, 'application_container'))
        
    def test_configure_host_services_uses_injected_service(self):
        """Test that _configure_host_services uses the injected service."""
        # Create GraphRunnerService
        runner = GraphRunnerService(
            graph_definition_service=self.mock_graph_definition,
            graph_execution_service=self.mock_graph_execution,
            compilation_service=self.mock_compilation,
            graph_bundle_service=self.mock_graph_bundle,
            agent_factory_service=self.mock_agent_factory,
            llm_service=self.mock_llm_service,
            storage_service_manager=self.mock_storage_manager,
            node_registry_service=self.mock_node_registry,
            logging_service=self.mock_logging_service,
            app_config_service=self.mock_app_config,
            execution_tracking_service=self.mock_execution_tracking,
            execution_policy_service=self.mock_execution_policy,
            state_adapter_service=self.mock_state_adapter,
            dependency_checker_service=self.mock_dependency_checker,
            graph_assembly_service=self.mock_graph_assembly,
            prompt_manager_service=self.mock_prompt_manager,
            host_protocol_configuration_service=self.mock_host_protocol_config
        )
        
        # Create mock agent
        mock_agent = Mock()
        mock_agent.name = "test_agent"
        
        # Call _configure_host_services
        result = runner._configure_host_services(mock_agent)
        
        # Verify the service method was called, not a container method
        self.mock_host_protocol_config.configure_host_protocols.assert_called_once_with(mock_agent)
        self.assertEqual(result, 2)  # The mocked return value
        
    def test_get_host_service_status_uses_injected_service(self):
        """Test that get_host_service_status uses the injected service."""
        # Create GraphRunnerService
        runner = GraphRunnerService(
            graph_definition_service=self.mock_graph_definition,
            graph_execution_service=self.mock_graph_execution,
            compilation_service=self.mock_compilation,
            graph_bundle_service=self.mock_graph_bundle,
            agent_factory_service=self.mock_agent_factory,
            llm_service=self.mock_llm_service,
            storage_service_manager=self.mock_storage_manager,
            node_registry_service=self.mock_node_registry,
            logging_service=self.mock_logging_service,
            app_config_service=self.mock_app_config,
            execution_tracking_service=self.mock_execution_tracking,
            execution_policy_service=self.mock_execution_policy,
            state_adapter_service=self.mock_state_adapter,
            dependency_checker_service=self.mock_dependency_checker,
            graph_assembly_service=self.mock_graph_assembly,
            prompt_manager_service=self.mock_prompt_manager,
            host_protocol_configuration_service=self.mock_host_protocol_config
        )
        
        # Create mock agent
        mock_agent = Mock()
        mock_agent.name = "test_agent"
        
        # Call get_host_service_status
        status = runner.get_host_service_status(mock_agent)
        
        # Verify the service method was called
        self.mock_host_protocol_config.get_configuration_status.assert_called_once_with(mock_agent)
        
        # Verify status structure
        self.assertEqual(status["agent_name"], "test_agent")
        self.assertEqual(status["services_configured"], 1)
        self.assertEqual(status["registry_stats"]["total_services"], 3)
        self.assertEqual(status["registry_stats"]["total_protocols"], 1)
        
    def test_host_services_disabled_when_service_not_provided(self):
        """Test that host services are disabled when service is not provided."""
        # Create GraphRunnerService without host protocol configuration service
        runner = GraphRunnerService(
            graph_definition_service=self.mock_graph_definition,
            graph_execution_service=self.mock_graph_execution,
            compilation_service=self.mock_compilation,
            graph_bundle_service=self.mock_graph_bundle,
            agent_factory_service=self.mock_agent_factory,
            llm_service=self.mock_llm_service,
            storage_service_manager=self.mock_storage_manager,
            node_registry_service=self.mock_node_registry,
            logging_service=self.mock_logging_service,
            app_config_service=self.mock_app_config,
            execution_tracking_service=self.mock_execution_tracking,
            execution_policy_service=self.mock_execution_policy,
            state_adapter_service=self.mock_state_adapter,
            dependency_checker_service=self.mock_dependency_checker,
            graph_assembly_service=self.mock_graph_assembly,
            prompt_manager_service=self.mock_prompt_manager,
            host_protocol_configuration_service=None  # Not provided
        )
        
        # Verify host services are not available
        self.assertIsNone(runner.host_protocol_configuration)
        self.assertFalse(runner._host_services_available)
        
        # Create mock agent
        mock_agent = Mock()
        mock_agent.name = "test_agent"
        
        # Call _configure_host_services - should return 0
        result = runner._configure_host_services(mock_agent)
        self.assertEqual(result, 0)
        
        # Get status - should show error
        status = runner.get_host_service_status(mock_agent)
        self.assertEqual(status["error"], "HostProtocolConfigurationService not available")
        
    def test_no_direct_container_access(self):
        """Test that GraphRunnerService doesn't access container directly."""
        # Create GraphRunnerService
        runner = GraphRunnerService(
            graph_definition_service=self.mock_graph_definition,
            graph_execution_service=self.mock_graph_execution,
            compilation_service=self.mock_compilation,
            graph_bundle_service=self.mock_graph_bundle,
            agent_factory_service=self.mock_agent_factory,
            llm_service=self.mock_llm_service,
            storage_service_manager=self.mock_storage_manager,
            node_registry_service=self.mock_node_registry,
            logging_service=self.mock_logging_service,
            app_config_service=self.mock_app_config,
            execution_tracking_service=self.mock_execution_tracking,
            execution_policy_service=self.mock_execution_policy,
            state_adapter_service=self.mock_state_adapter,
            dependency_checker_service=self.mock_dependency_checker,
            graph_assembly_service=self.mock_graph_assembly,
            prompt_manager_service=self.mock_prompt_manager,
            host_protocol_configuration_service=self.mock_host_protocol_config
        )
        
        # Verify no container-related attributes
        self.assertFalse(hasattr(runner, 'application_container'))
        self.assertFalse(hasattr(runner, 'container'))
        self.assertFalse(hasattr(runner, '_container'))
        
        # Verify proper service attribute exists
        self.assertTrue(hasattr(runner, 'host_protocol_configuration'))
        self.assertIsInstance(runner.host_protocol_configuration, Mock)


if __name__ == "__main__":
    unittest.main()
